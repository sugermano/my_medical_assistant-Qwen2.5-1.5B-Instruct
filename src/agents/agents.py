import sys
sys.path.append('D:/gitRepository/my_medical_assistant-Qwen2.5-1.5B-Instruct')
from typing import Literal, TypedDict, Annotated, List

from langchain_core.prompts import ChatPromptTemplate
from langchain.agents.middleware import SummarizationMiddleware, ModelCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages

from zhipuai import ZhipuAI
import os
import json

from src.agents.tools import search_drug_database, check_drug_interaction, assess_symptom_severity, generate_medicine_report
# 引入我们在上面定义的 Pydantic 模型
from src.agents.models import ConsultationState, MedicalReport
# 引入工具
from src.agents.tools import search_drug_database, check_drug_interaction, search_product_info
from dotenv import load_dotenv
load_dotenv()



# --- 状态定义 ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages] # 自动追加历史消息
    
class SeekMedicineAgent:
    """智医助手 Agent (LangGraph 版 - 支持多轮追问与结构化报告)"""

    def __init__(self):
        # 1. 初始化模型
        self.model = init_chat_model(
            model="Qwen/Qwen2.5-7B-Instruct",
            model_provider="openai",
            base_url="https://api.siliconflow.cn/v1",
            api_key=os.getenv("SILICONFLOW_API_KEY"),
            temperature=0.1 
        )
        
        # 2. 初始化记忆 (Checkpointer)
        self.checkpointer = MemorySaver()
        
        # 3. 构建图谱
        self.graph = self._build_graph()

    def _build_graph(self):
        """构建 LangGraph 工作流"""
        workflow = StateGraph(AgentState)

        # --- 定义节点 ---
        workflow.add_node("inquiry_node", self.inquiry_node)
        workflow.add_node("report_node", self.report_node)

        # --- 定义边 ---
        workflow.set_entry_point("inquiry_node")
        
        workflow.add_conditional_edges(
            "inquiry_node",
            self.router_logic,
            {
                "continue": END,           # 返回给用户，等待下一次输入
                "report": "report_node",   # 信息充足，进入报告生成
                "emergency": END           # 紧急情况，直接结束
            }
        )
        
        workflow.add_edge("report_node", END)

        return workflow.compile(checkpointer=self.checkpointer)

    # --- 节点逻辑 1: 问诊医生 ---
    async def inquiry_node(self, state: AgentState):
        """分析对话，决定是追问还是生成报告"""
        messages = state["messages"]
        
        # 绑定结构化输出 (决策模型)
        # 这一步模型会判断：信息是否够了？够了就 ready_to_report，不够就生成 next_question
        chain = INQUIRY_PROMPT | self.model.with_structured_output(ConsultationState)
        decision = await chain.ainvoke({"messages": messages})

        # 将决策结果保存到最后一轮消息的属性中，或者作为特殊消息插入
        # 这里我们直接返回决策生成的“追问”作为 AI 回复
        if decision.status == "continue_asking":
            return {"messages": [AIMessage(content=decision.next_question)]}
        elif decision.status == "emergency":
            return {"messages": [AIMessage(content="🚨 监测到紧急情况，请立即拨打120或前往急诊！")]}
        
        # 如果是 ready_to_report，这里不产出消息，只传递状态
        # 我们返回一个隐藏的系统消息标记，辅助 debug
        return {"messages": [SystemMessage(content=f"DECISION_MADE: {decision.status}")]}

    # --- 节点逻辑 2: 执业药师 ---
    async def report_node(self, state: AgentState):
        """调用工具查资料，生成最终 JSON 报告"""
        messages = state["messages"]
        
        # 1. 先进行 RAG 检索 (工具调用)
        # 提取用户最后的主诉
        # 实际场景中这里可以用 LLM 总结出搜索关键词
        search_query = messages[-2].content if len(messages) > 1 else "" 
        
        # 手动调用工具获取上下文 (也可以让 Agent 自动调，这里为了稳健手动调)
        drug_context = search_drug_database.invoke(search_query)
        interaction_check = check_drug_interaction.invoke(["待定药物"], "用户病史")
        
        # 2. 生成报告
        # 将工具查到的 Context 注入 Prompt
        chain = REPORT_PROMPT | self.model.with_structured_output(MedicalReport)
        
        report = await chain.ainvoke({
            "conversation_summary": messages,
            "drug_context": drug_context,
            "interaction_context": interaction_check
        })
        
        # 将 Pydantic 对象转为 JSON 字符串存入 content，前端收到后解析
        return {"messages": [AIMessage(content=report.json())]}

    # --- 路由逻辑 ---
    def router_logic(self, state: AgentState) -> Literal["continue", "report", "emergency"]:
        messages = state["messages"]
        last_message = messages[-1]
        
        # 检查 inquiry_node 的输出
        if isinstance(last_message, AIMessage):
            # 如果是 SystemMessage 标记了 ready，则进入报告
            # 注意：实际代码中可能需要更严谨的判断，比如在 AIMessage.additional_kwargs 里存 metadata
            if "DECISION_MADE: ready_to_report" in last_message.content: # 简单判断
                return "report"
            elif "DECISION_MADE: emergency" in last_message.content:
                return "emergency"
            elif "DECISION_MADE" in last_message.content: # 其他状态
                 return "continue"
            
            # 如果 last_message 是纯文本追问 (continue_asking 分支)
            if "DECISION_MADE" not in str(last_message.content): 
                return "continue"
        
        # 默认继续
        return "continue"

    # --- 对外接口 ---
    async def process(self, user_input: str, session_id: str) -> dict:
        """处理用户消息，返回结构化结果"""
        config = {"configurable": {"thread_id": session_id}}
        
        # 运行图
        # astream_events 或 invoke 均可，这里用 invoke 简化
        final_state = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=user_input)]},
            config=config
        )
        
        last_msg = final_state["messages"][-1]
        content = last_msg.content

        # 判断返回类型
        try:
            # 尝试解析是否为 JSON 报告
            import json
            if "summary_analysis" in content and "recommended_products" in content:
                return {
                    "type": "medical_report",  # 前端渲染卡片 (图1)
                    "data": json.loads(content)
                }
        except:
            pass

        return {
            "type": "text",  # 前端渲染气泡 (图2)
            "content": content
        }


# 智能寻药 Prompt (V1+ 结构化输出版本 - 带明确示例)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# --- 1. 问诊专家 Prompt (负责追问) ---
INQUIRY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一名专业的全科分诊医生。你的目标是收集足够的信息来判断用户是否适合使用某种药物，或评估病情。
    
    你需要收集的关键信息包括：
    1. **主诉症状**：具体哪里不舒服？
    2. **持续时间**：症状持续了多久？
    3. **诱因/加重因素**：是否吃过辛辣、熬夜等？
    4. **过敏史/病史**：是否有药物过敏、慢性病、孕期/哺乳期等特殊情况。
    
    【决策逻辑】
    - 如果用户只说了一句简单的症状（如“我头晕”），你必须追问细节。
    - 不要一次性问所有问题，每次问1-2个最关键的。
    - 如果信息已经足够判断病情或用药，或者用户表现出不耐烦，将 status 设为 'ready_to_report'。
    - 如果出现危急重症（胸痛、呼吸困难、吐血），将 status 设为 'emergency'。
    """),
    MessagesPlaceholder(variable_name="messages"),
])

# --- 2. 药事顾问 Prompt (负责出报告) ---
REPORT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """你是一名资深临床药师。根据收集到的用户病史，生成一份专业的用药指导报告。
    
    请严格按照以下结构生成 JSON 数据：
    1. **适配性总结**：用一句话判断药物是否适合用户。
    2. **详细分析**：结合用户具体的症状（如打嗝、胀气）解释药物（如多潘立酮）的作用机理。
    3. **药品信息**：提取关键的【功能主治】、【用法用量】、【禁忌症】。
    4. **推荐商品**：根据病情推荐 1-2 款通用名药物（如多潘立酮片、奥美拉唑等），包含模拟的价格和图片链接。
    
    注意：语气要温暖、专业，类似于“小团医生”。
    """),
    ("human", "对话历史摘要：{conversation_summary}")
])