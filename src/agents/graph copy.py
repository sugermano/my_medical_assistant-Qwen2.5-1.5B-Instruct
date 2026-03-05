import os
import sys
import json
from typing import TypedDict, Annotated, List, Literal, Optional
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 1. 定义结构化输出模型 (Pydantic)
# ==========================================

# 引入我们在上面定义的 Pydantic 模型
from src.agents.models import ConsultationState, MedicalReport
# 引入工具
from src.agents.tools import search_drug_database, check_drug_interaction, search_product_info
# --- 问诊 Prompt ---
from src.agents.prompts import INQUIRY_PROMPT, REPORT_PROMPT

# ==========================================
# 2. 模型与 Prompt 初始化
# ==========================================

llm = init_chat_model(
    model="Qwen/Qwen2.5-7B-Instruct",
    model_provider="openai",
    temperature=0.1,
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.cn/v1"
)

# ==========================================
# 3. 图节点定义 (Nodes)
# ==========================================

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]

async def inquiry_node(state: AgentState):
    """【问诊节点】分析对话，决定是追问还是生成报告"""
    print("--- [Node] Doctor Inquiry ---")
    
    # 绑定结构化输出 (决策模型)
    analyzer = llm.with_structured_output(ConsultationState)
    chain = INQUIRY_PROMPT | analyzer
    
    decision = await chain.ainvoke({"messages": state["messages"]})
    
    # 1. 紧急情况处理
    if decision.status == "emergency":
        return {"messages": [AIMessage(content="🚨 监测到紧急情况！请立即前往医院就诊，切勿依赖 AI 建议。")]}
    
    # 2. 继续追问
    if decision.status == "continue_asking":
        return {"messages": [AIMessage(content=decision.next_question)]}
    
    # 3. 准备生成报告 (使用隐藏的 SystemMessage 传递状态给下一个节点，或者直接在 Edge 里处理)
    # 这里我们返回一个特殊标记，Router 会识别它并导向 Report Node
    return {"messages": [SystemMessage(content="DECISION: READY_TO_REPORT")]}

async def report_node(state: AgentState):
    print("--- [Node] Pharmacist Reporting ---")
    messages = state["messages"]
    user_query = messages[-2].content  # 用户症状描述
    
    # 1. 第一步：检索相关药典条目
    drug_context = search_drug_database.invoke(user_query)
    # drug_context 即为您展示的那段包含“8、藿香正气液”的字符串
    
    # 2. 第二步：让 LLM 从文本中“选药”并“提取名称”
    # 我们先用一个小规模的 invoke 来获取药品列表，用于安全检查
    selection_prompt = f"""
    根据用户描述：{user_query}
    从以下药典文本中提取最对症的 1-2 个药品通用名：
    {drug_context}
    只需返回药品名称列表，用逗号隔开。
    """
    selected_drugs_text = (await llm.ainvoke(selection_prompt)).content
    selected_drugs = [d.strip() for d in selected_drugs_text.split("，") if d.strip()]
    
    # 3. 第三步：执行安全检查（调用工具）
    # 提取病史（这里可以从 context 提取，暂时假设为“无”）
    # medical_history = "用户描述的既往史或过敏史" 
    medical_history_prompt = f"""
    根据用户描述：{user_query}提取用户的既往史或过敏史，如果没有相关信息，则写‘无’
    """
    medical_history = (await llm.ainvoke(medical_history_prompt)).content
    
    # 重点：使用字典传参，避免 items 错误
    interaction_context = check_drug_interaction.invoke({
        "drug_list": selected_drugs,
        "medical_history": medical_history
    })
    
    # 4. 第四步：生成最终结构化报告
    reporter = llm.with_structured_output(MedicalReport)
    
    # 构建最终渲染 Prompt
    # 1. 确保 drug_context 转化为干净的字符串
    context_str = ""
    if isinstance(drug_context, list):
        context_str = "\n".join([d.page_content if hasattr(d, 'page_content') else str(d) for d in drug_context])
    else:
        context_str = str(drug_context)

    # 2. 调用模型
    report = await (REPORT_PROMPT | reporter).ainvoke({
        "drug_context": context_str,
        "interaction_context": interaction_context, # 这里的 interaction_context 是工具调用的返回字符串
        "user_symptoms": user_query
    })
    
    # report = await (REPORT_PROMPT | reporter).ainvoke(final_input)
    
    return {"messages": [AIMessage(content=report.model_dump_json())]}

# ==========================================
# 4. 图构建与路由
# ==========================================

def router(state: AgentState) -> Literal["continue", "report", "end"]:
    """路由逻辑：决定下一步去哪里"""
    messages = state["messages"]
    last_message = messages[-1]
    
    # 检查是否有特殊标记
    if isinstance(last_message, SystemMessage) and "READY_TO_REPORT" in last_message.content:
        return "report"
    
    if isinstance(last_message, AIMessage):
        if "🚨" in str(last_message.content):
            return "end"
        # 如果是普通 AI 回复（追问），则返回给用户（END当前运行，等待下一次输入）
        return "continue"
            
    return "continue"

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("doctor", inquiry_node)
workflow.add_node("pharmacist", report_node)

workflow.set_entry_point("doctor")

workflow.add_conditional_edges(
    "doctor",
    router,
    {
        "continue": END,        # 暂停，等待用户回复
        "report": "pharmacist", # 进入报告生成
        "end": END              # 结束
    }
)
workflow.add_edge("pharmacist", END)

# 初始化记忆系统 (必须，否则无法追问)
checkpointer = MemorySaver()

# 编译应用
app = workflow.compile(checkpointer=checkpointer)