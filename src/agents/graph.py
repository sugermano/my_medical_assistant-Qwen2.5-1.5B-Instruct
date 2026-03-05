import os
import json
import asyncio
from typing import TypedDict, Annotated, List, Literal, Optional, Callable, Any
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph.message import add_messages
from langchain.chat_models import init_chat_model
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

# 引入数据库实例 (确保单例模式或在函数内实例化)
from database.medical_database import MedicalDatabase
db = MedicalDatabase()

# 引入缓存模块
from cache.redis_cache import cached, cached_sync, drug_search_key_func

# 引入模型
from src.agents.models import ConsultationState, MedicalReport, UserProfileUpdate, FeedbackExtraction
# 引入 Prompt
from src.agents.prompts import INQUIRY_PROMPT, REPORT_PROMPT
# 引入 RAG 知识库检索（Skill 模式：直接调用底层函数，不依赖 tools.py）
from database.get_knowledge import get_knowledge
# 引入 aiohttp 用于调用极速数据 API
import aiohttp

load_dotenv()

# 极速数据 API 配置
JISU_API_KEY = "9ffa21c8cfde253b"
JISU_SEARCH_URL = "https://api.jisuapi.com/medicine/query"
JISU_DETAIL_URL = "https://api.jisuapi.com/medicine/detail"


def _extract_content_from_knowledge(knowledge_result) -> str:
    """从 get_knowledge 返回的 Document 列表中提取文本内容"""
    if not knowledge_result:
        return ""
    
    # get_knowledge 返回的是 Document 对象列表
    if isinstance(knowledge_result, list):
        contents = []
        for doc in knowledge_result:
            if hasattr(doc, 'page_content'):
                contents.append(doc.page_content)
            elif isinstance(doc, str):
                contents.append(doc)
        return "\n".join(contents)
    elif hasattr(knowledge_result, 'page_content'):
        return knowledge_result.page_content
    elif isinstance(knowledge_result, str):
        return knowledge_result
    else:
        return str(knowledge_result)


# ==========================================
# 状态回调机制 - 用于向前端推送处理进度
# ==========================================
_status_callbacks = {}  # session_id -> callback function

def register_status_callback(session_id: str, callback: Callable[[str], Any]):
    """注册状态回调函数"""
    _status_callbacks[session_id] = callback

def unregister_status_callback(session_id: str):
    """注销状态回调函数"""
    if session_id in _status_callbacks:
        del _status_callbacks[session_id]

async def send_status(session_id: str, status: str):
    """发送处理状态到前端"""
    if session_id in _status_callbacks:
        callback = _status_callbacks[session_id]
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(status)
            else:
                callback(status)
        except Exception as e:
            print(f"⚠️ 状态回调失败: {e}")

llm = init_chat_model(
    model="Qwen/Qwen2.5-7B-Instruct",
    model_provider="openai",
    temperature=0.1,
    max_tokens=4096,
    api_key=os.getenv("SILICONFLOW_API_KEY"),
    base_url="https://api.siliconflow.cn/v1"
)

# ==========================================
# 状态定义 (增加用户ID和当前流程阶段)
# ==========================================
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    history_summary: str  # [新增] 存储历史消息的摘要
    session_id: str  # 必须传入 session_id 以便存库
    user_id: str     # 必须传入 user_id
    workflow_stage: str # 'inquiry', 'reporting', 'feedback', 'finished'
    inquiry_round: int  # 🔥 新增：问诊轮数计数器
    collected_info: dict  # 🔥 新增：已收集的信息结构化存储

# ==========================================
# 节点 1: 问诊与信息提取节点
# ==========================================
# 在进入 inquiry_node 之前执行一个“清理”动作
async def manage_memory(state: AgentState):
    """
    内存管理：如果消息超过阈值，提取核心信息并压缩。
    
    🔥 改进点：
    1. 明确区分"主诉症状"和"补充信息"
    2. 主诉症状永不丢失，优先级最高
    3. 慢性病史作为背景，不应覆盖主诉
    """
    messages = state["messages"]
    
    # 设定阈值：例如超过 6 条消息触发压缩
    if len(messages) > 6:
        # 只取除了最后 2 条（当前上下文）以外的所有旧消息进行总结
        to_summarize = messages[:-2]
        
        summary_prompt = f"""
        请从以下医疗咨询对话中提取关键信息，**特别注意区分主诉和背景**：

        【提取要求】
        1. **主诉症状**（最重要！用户最初描述的不适）：
           - 症状名称（如头痛、发烧）
           - 持续时间（如3天、昨晚开始）
           - 严重程度（如剧烈、轻微）
        
        2. **补充信息**（追问后得到的）：
           - 伴随症状
           - 诱因或加重因素
        
        3. **健康背景**（不是主诉！）：
           - 过敏史
           - 慢性病史
        
        【格式要求】
        主诉：[用户最初描述的症状]
        补充：[后续追问得到的信息]
        背景：[过敏史、慢性病等]
        
        对话内容：
        {to_summarize}
        """
        summary_response = await llm.ainvoke(summary_prompt)
        
        return summary_response.content
    
    return state.get("history_summary", "")

async def inquiry_node(state: AgentState):
    print("--- [Node] Doctor Inquiry & Context Management ---")
    messages = state["messages"]
    user_id = state["user_id"]
    session_id = state["session_id"]
    
    # 🔥 新增：初始化或更新问诊轮数
    inquiry_round = state.get("inquiry_round", 0)
    collected_info = state.get("collected_info", {
        "chief_complaint": None,  # 主诉
        "duration": None,  # 持续时间
        "severity": None,  # 严重程度
        "accompanying_symptoms": [],  # 伴随症状
        "allergies": None,  # 过敏史
        "chronic_diseases": None,  # 慢性病
        "asked_questions": []  # 已问过的问题类型
    })
    
    # 🔥 问诊轮数限制：最多5-6轮
    MAX_INQUIRY_ROUNDS = 5
    
    # 🔥 加载会话持久化上下文
    session_context = await asyncio.to_thread(db.get_session_context, session_id)
    if session_context and session_context.get("symptoms"):
        print(f"📋 加载历史上下文: 症状={session_context['symptoms'][:2]}, 禁忌={session_context['contraindications']}")
        # 从会话上下文更新 collected_info
        if session_context.get("symptoms"):
            collected_info["chief_complaint"] = session_context["symptoms"][0] if session_context["symptoms"] else None
        if session_context.get("contraindications"):
            collected_info["allergies"] = "已知" if any("过敏" in c for c in session_context["contraindications"]) else None
            collected_info["chronic_diseases"] = "已知" if session_context["contraindications"] else None

    last_msg = messages[-1] if messages else None
    if state.get("workflow_stage") == "awaiting_feedback_input":
        return {}
    # 如果处于待确认状态，且用户发了新消息，我们要判断是否要"破开"这个状态
    if state.get("workflow_stage") == "awaiting_confirmation":
        if isinstance(last_msg, HumanMessage):
            content = last_msg.content.lower()
            confirmation_words = ["好", "谢", "ok", "再见"] # 最好不要关键词匹配，目前没时间做
            
            # 如果不是确认语（比如问"能吃藿香正气丸吗"），继续处理新问题
            if not any(word in content for word in confirmation_words):
                print("🔄 检测到新问题，继续处理...")
                # 不要直接 return，让它继续执行下面的问诊逻辑
                # 只需要修改 stage，后面的代码会处理
                pass
            else:
                # 如果是确认语，我们什么都不做，让它透传给 router
                return {}
        else:
            return {}
    
    # ==================================================
    # 1. 动态上下文压缩 (Memory Management)
    # ==================================================
    # 设定阈值：当消息超过 6 条时，触发自动总结
    current_summary = state.get("history_summary", "")
    
    if len(messages) > 6:
        print("📝 [Logic] 消息过长，正在更新对话摘要...")
        # 总结除了最后两条以外的所有旧消息
        to_summarize = messages[:-2]
        summary_prompt = f"请简要总结以下对话中的医疗核心信息（主诉、病史、禁忌）：\n{to_summarize}"
        # 这里的 summary 不要用 structured_output，用普通文本即可
        summary_res = await llm.ainvoke(summary_prompt)
        current_summary = summary_res.content
    
    # ==================================================
    # 2. 隐式提取用户信息 (保持原有逻辑，优化提取范围)
    # ==================================================
    profile_extractor = llm.with_structured_output(UserProfileUpdate)
    extract_prompt = ChatPromptTemplate.from_messages([
        ("system", "你是一个信息提取助手。请只从最新的回复中提取健康档案信息。"),
        ("human", "{text}")
    ])
    
    last_user_msg = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    
    if last_user_msg:
        try:
            profile_data = await (extract_prompt | profile_extractor).ainvoke({"text": last_user_msg})
            if profile_data.has_update:
                print(f"🔄 更新数据库画像: {profile_data}")
                db.update_health_profile(
                    user_id, 
                    allergies=profile_data.allergies,
                    chronic_diseases=profile_data.chronic_diseases
                )
        except Exception as e:
            print(f"⚠️ 提取失败: {e}")

    # ==================================================
    # 3. 注入长期背景 (过去问诊记录)
    # ==================================================
    # 这一步实现了你最初的要求：get_past_consultations
    past_records = db.get_past_consultations(user_id, limit=2)
    past_str = "无" if not past_records else "; ".join([f"{r['created_at']}: {r['symptom_summary']}" for r in past_records])

    # ==================================================
    # 4. 🔥 轮数检查和强制结束逻辑
    # ==================================================
    inquiry_round += 1
    print(f"📊 当前问诊轮数: {inquiry_round}/{MAX_INQUIRY_ROUNDS}")
    
    # 🔥 硬性限制：超过最大轮数，强制生成报告
    if inquiry_round > MAX_INQUIRY_ROUNDS:
        print(f"⚠️ 问诊轮数达到上限({MAX_INQUIRY_ROUNDS})，强制进入报告阶段")
        # 检查是否有基本的主诉信息
        if not collected_info["chief_complaint"] and not session_context.get("symptoms"):
            # 如果连主诉都没有，给一个提示
            return {
                "messages": [AIMessage(content="我需要了解您的主要症状才能提供建议。请简要描述您哪里不舒服？")],
                "workflow_stage": "inquiry",
                "inquiry_round": inquiry_round,
                "collected_info": collected_info
            }
        
        # 有主诉信息，强制进入报告
        return {
            "messages": [SystemMessage(content="DECISION: READY_TO_REPORT")],
            "workflow_stage": "reporting",
            "history_summary": current_summary,
            "inquiry_round": inquiry_round,
            "collected_info": collected_info
        }
    
    # 🔥 软性限制：第4轮开始提示即将结束
    if inquiry_round >= 4:
        print(f"💡 接近问诊上限，优先考虑结束问诊")
    
    # ==================================================
    # 5. 决策逻辑 (使用优化后的上下文)
    # ==================================================
    analyzer = llm.with_structured_output(ConsultationState)
    
    # 🔥 构建完整上下文，包含所有已收集的信息和轮数提示
    context_parts = []
    
    # Part 0: 轮数提示（新增）
    context_parts.append(f"【问诊进度】当前第{inquiry_round}轮，最多{MAX_INQUIRY_ROUNDS}轮")
    
    # Part 1: 历史摘要（如果存在）
    if current_summary:
        context_parts.append(f"【历史摘要】\n{current_summary}")
    
    # Part 2: 历史问诊记录（避免推荐重复无效的药物）
    if past_records:
        context_parts.append(f"【过往问诊】\n{past_str}")
    
    # Part 3: 当前会话上下文（症状、禁忌）- 从数据库加载
    if session_context:
        context_info = []
        if session_context.get("symptoms"):
            context_info.append(f"已知主诉：{', '.join(session_context['symptoms'][:2])}")
            collected_info["chief_complaint"] = session_context['symptoms'][0]
        if session_context.get("contraindications"):
            context_info.append(f"已知禁忌：{', '.join(session_context['contraindications'][:3])}")
            collected_info["allergies"] = "已知"
            collected_info["chronic_diseases"] = "已知"
        if context_info:
            context_parts.append(f"【本次会话已收集】\n" + "\n".join(context_info))
    
    # Part 4: 已问过的问题类型（避免重复）
    if collected_info["asked_questions"]:
        context_parts.append(f"【已询问过】{', '.join(collected_info['asked_questions'])}")
    
    # 构建上下文消息
    if context_parts:
        context_message = SystemMessage(content="\n\n".join(context_parts))
        # 取最近3-4条消息（确保包含当前问答）
        recent_messages = messages[-4:] if len(messages) >= 4 else messages
        messages_with_context = [context_message] + recent_messages
    else:
        # 没有历史上下文时，使用更多消息以包含主诉
        messages_with_context = messages[-6:] if len(messages) > 6 else messages
    
    try:
        decision = await (INQUIRY_PROMPT | analyzer).ainvoke({
            "messages": messages_with_context
        })
    except Exception as e:
        print(f"❌ 决策节点解析失败: {e}")
        # 容错处理：如果解析失败，强制继续追问或尝试结束
        return {
            "workflow_stage": "inquiry", 
            "messages": [AIMessage(content="请再详细描述一下您的感觉。")],
            "inquiry_round": inquiry_round,
            "collected_info": collected_info
        }

    # ==================================================
    # 6. 🔥 智能问题类型追踪（避免重复询问）
    # ==================================================
    if decision.status == "continue_asking" and decision.next_question:
        # 分析AI即将提出的问题类型
        question_lower = decision.next_question.lower()
        
        # 定义问题类型关键词映射
        question_types = {
            "症状描述": ["哪里不舒服", "什么症状", "主要症状", "感觉怎么样"],
            "持续时间": ["多久", "什么时候开始", "持续时间", "几天了"],
            "严重程度": ["严重吗", "程度", "频繁", "剧烈"],
            "伴随症状": ["还有", "其他症状", "伴随", "同时"],
            "过敏史": ["过敏", "过敏史", "对什么药"],
            "慢性病": ["慢性病", "长期服药", "病史", "基础疾病"],
            "诱因": ["诱因", "什么引起", "之前做了什么", "吃了什么"]
        }
        
        # 识别当前问题类型
        current_type = None
        for q_type, keywords in question_types.items():
            if any(kw in question_lower for kw in keywords):
                current_type = q_type
                break
        
        # 检查是否重复
        if current_type and current_type in collected_info["asked_questions"]:
            print(f"⚠️ 检测到重复问题类型: {current_type}")
            # 检查信息是否充足，如果充足就直接进入报告
            if collected_info["chief_complaint"] and collected_info["duration"]:
                print(f"💡 信息已充足，强制进入报告阶段")
                return {
                    "messages": [SystemMessage(content="DECISION: READY_TO_REPORT")],
                    "workflow_stage": "reporting",
                    "history_summary": current_summary,
                    "inquiry_round": inquiry_round,
                    "collected_info": collected_info
                }
        
        # 记录新的问题类型
        if current_type and current_type not in collected_info["asked_questions"]:
            collected_info["asked_questions"].append(current_type)
            print(f"📝 记录问题类型: {current_type}")
        
        # 🔥 更新collected_info结构（从对话中提取）
        if "症状" in question_lower or "不舒服" in question_lower:
            # 尝试从用户最后的回复中提取主诉
            if last_user_msg and not collected_info["chief_complaint"]:
                collected_info["chief_complaint"] = last_user_msg[:50]  # 截取前50字符
        
        if any(kw in question_lower for kw in ["多久", "时间"]):
            # 从回复中寻找时间信息
            time_patterns = ["天", "小时", "周", "月", "昨天", "今天"]
            if last_user_msg and any(p in last_user_msg for p in time_patterns):
                collected_info["duration"] = "已知"

    # ==================================================
    # 7. 状态分流
    # ==================================================
    if decision.status == "emergency":
        return {
            "messages": [AIMessage(content="🚨 监测到紧急情况！请立即前往医院就诊。")], 
            "workflow_stage": "finished",
            "inquiry_round": inquiry_round,
            "collected_info": collected_info
        }
    
    if decision.status == "continue_asking":
        return {
            "messages": [AIMessage(content=decision.next_question)], 
            "workflow_stage": "inquiry",
            "history_summary": current_summary,
            "inquiry_round": inquiry_round,
            "collected_info": collected_info
        }
    
    # 满足条件，进入报告阶段
    return {
        "messages": [SystemMessage(content="DECISION: READY_TO_REPORT")], 
        "workflow_stage": "reporting",
        "history_summary": current_summary,
        "inquiry_round": inquiry_round,
        "collected_info": collected_info
    }

# ==========================================
# Skill 模式：药品智能搜索（三步优化版 + 缓存优化）
# 优先级：本地知识库 → 数据库缓存 → API
# ==========================================
async def _fetch_drug_from_api(drug_name: str, session: aiohttp.ClientSession) -> dict:
    """从极速数据 API 获取单个药品详情（仅在缓存未命中时调用）"""
    try:
        # 搜索药品获取 medicine_id
        search_url = f"{JISU_SEARCH_URL}?appkey={JISU_API_KEY}&name={drug_name}"
        async with session.get(search_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if data.get("status") != 0 or not data.get("result", {}).get("list"):
                return None
            
            results = data["result"]["list"]
            otc_results = [r for r in results if r.get("prescription") == 2]
            selected = otc_results[0] if otc_results else results[0]
            medicine_id = selected.get("medicine_id")
        
        # 获取详情
        detail_url = f"{JISU_DETAIL_URL}?appkey={JISU_API_KEY}&medicine_id={medicine_id}"
        async with session.get(detail_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            if data.get("status") != 0:
                return None
            
            result = data.get("result", {})
            return {
                "drug_name": drug_name,
                "name": result.get("name", drug_name),
                "spec": result.get("spec", ""),
                "manufacturer": result.get("manufacturer", ""),
                "prescription_type": "处方药" if result.get("prescription") == 1 else "OTC",
                "full_description": result.get("desc", ""),
                "source": "API"
            }
    except Exception as e:
        print(f"⚠️ API获取失败 [{drug_name}]: {e}")
        return None


async def _get_drug_info_with_cache(drug_names: list, use_api_fallback: bool = True) -> list:
    """
    获取药品信息（带缓存优化）
    
    优先级：数据库缓存 → API（可选）
    
    Args:
        drug_names: 药品名称列表
        use_api_fallback: 缓存未命中时是否调用API
        
    Returns:
        药品信息列表
    """
    if not drug_names:
        return []
    
    # Step 1: 批量查询数据库缓存
    cached_drugs = await asyncio.to_thread(db.get_drugs_from_cache, drug_names)
    print(f"💾 [Cache] 缓存命中: {list(cached_drugs.keys())} / {drug_names}")
    
    # 分离命中和未命中
    drug_infos = []
    uncached_names = []
    
    for name in drug_names:
        if name in cached_drugs:
            drug_infos.append(cached_drugs[name])
        else:
            uncached_names.append(name)
    
    # Step 2: 对未命中的药品调用API（如果启用）
    if uncached_names and use_api_fallback:
        print(f"🌐 [API] 需要调用API获取: {uncached_names}")
        async with aiohttp.ClientSession() as session:
            tasks = [_fetch_drug_from_api(name, session) for name in uncached_names]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理API响应并存入缓存
            api_results = []
            for name, resp in zip(uncached_names, responses):
                if isinstance(resp, dict) and resp.get("full_description"):
                    drug_infos.append(resp)
                    api_results.append(resp)
                    print(f"  ✅ {name}: API获取成功")
                else:
                    # API也失败，返回空信息
                    drug_infos.append({
                        "drug_name": name,
                        "name": name,
                        "full_description": "",
                        "prescription_type": "未知",
                        "source": "未知"
                    })
                    print(f"  ⚠️ {name}: API未命中")
            
            # 批量存入缓存（仅API成功的）
            if api_results:
                await asyncio.to_thread(db.save_drugs_to_cache, api_results)
    elif uncached_names:
        # 不调用API，返回空信息
        for name in uncached_names:
            drug_infos.append({
                "drug_name": name,
                "name": name,
                "full_description": "",
                "prescription_type": "未知",
                "source": "未知"
            })
    
    return drug_infos


async def _search_drug_impl_async(query: str) -> str:
    """
    药品智能搜索实现（三步优化版 + 缓存优化 - 异步）
    
    流程优化：
    1. 从本地知识库+LLM提取候选药名 + 本地药品信息
    2. 如果本地有完整信息 → 直接使用，不调API
    3. 如果本地无完整信息 → 查数据库缓存 → 缓存未命中才调API
    4. LLM整合输出
    """
    print(f"🔍 [Skill] 智能药品搜索: {query}")
    
    # === Step 1: 症状 → 候选药名 + 本地药品信息 ===
    raw_docs = get_knowledge(query)
    raw_result = _extract_content_from_knowledge(raw_docs)
    local_has_drug_info = bool(raw_result and len(raw_result) > 100)  # 判断本地是否有足够信息
    
    extract_prompt = f"""
你是一个专业的药品信息提取专家。请从以下药品说明书片段中提取：
1. 具体的药品通用名
2. 是否包含该药的完整说明书信息（用法用量、禁忌症等）

【用户症状】：{query}
【搜索结果】：{raw_result[:2000]}

【输出格式】（JSON）：
{{
    "drugs": ["药名1", "药名2", "药名3"],
    "has_full_info": true/false,
    "local_info_summary": "简要描述搜索结果中包含的药品信息"
}}

如果搜索结果中没有明确药名，drugs 返回空列表 []。
"""
    
    drugs = []
    local_info_available = False
    
    try:
        response = await llm.ainvoke(extract_prompt)
        content = response.content.strip()
        # 尝试解析JSON
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            drugs = [d.strip() for d in parsed.get("drugs", []) if d and d != "无"][:5]
            local_info_available = parsed.get("has_full_info", False)
        elif content.startswith("["):
            drugs = json.loads(content)
            drugs = [d.strip() for d in drugs if d and d != "无"][:5]
    except Exception as e:
        print(f"⚠️ 药名提取失败: {e}")
        drugs = []
    
    # 兜底：如果本地没找到药名，用LLM常识推荐
    llm_fallback_used = False
    if not drugs:
        print("⚠️ 本地未命中具体药物，触发大模型常识兜底...")
        llm_fallback_used = True
        fallback_prompt = f"""
作为专业全科医生，针对症状"{query}"，请列举 3 种国内最常见的非处方药(OTC)通用名。
只返回 JSON 数组，例如 ["布洛芬", "对乙酰氨基酚"]。
"""
        try:
            response = await llm.ainvoke(fallback_prompt)
            content = response.content.strip()
            if content.startswith("["):
                drugs = json.loads(content)[:3]
        except:
            drugs = ["布洛芬", "对乙酰氨基酚"]
    
    print(f"✅ [Step 1] 候选药名: {drugs}, 本地有完整信息: {local_info_available}, LLM兜底: {llm_fallback_used}")
    
    # === Step 2: 获取药品详情（缓存优化） ===
    drug_infos = []
    
    if local_info_available and not llm_fallback_used:
        # 🔥 本地知识库有完整信息，直接使用，不调API
        print("📚 [Step 2] 使用本地知识库信息，无需调用API")
        for name in drugs:
            local_docs = get_knowledge(f"{name} 用法用量 禁忌症 功能主治")
            local_info = _extract_content_from_knowledge(local_docs)
            drug_infos.append({
                "drug_name": name,
                "name": name,
                "full_description": local_info[:800] if local_info else "",
                "prescription_type": "未知",
                "source": "本地知识库"
            })
            # 同时存入缓存，下次可以直接用
            await asyncio.to_thread(db.save_drug_to_cache, {
                "drug_name": name,
                "full_description": local_info[:1500] if local_info else "",
                "source": "本地知识库"
            })
    else:
        # 🔥 本地无完整信息或LLM兜底，需要查缓存/API
        print("🔄 [Step 2] 查询数据库缓存...")
        drug_infos = await _get_drug_info_with_cache(drugs, use_api_fallback=True)
    
    # === Step 3: LLM整合输出 ===
    drug_summaries = []
    for info in drug_infos:
        desc = info.get('full_description') or info.get('desc') or '暂无'
        drug_summaries.append(f"""
【药品名称】：{info.get('name') or info.get('drug_name', '未知')}
【类型】：{info.get('prescription_type') or info.get('prescription', '未知')}
【来源】：{info.get('source', '未知')}
【说明书摘要】：
{desc[:400]}
""")
    
    final_prompt = f"""
你是专业药师。用户症状是"{query}"，以下是相关药品信息：

{"".join(drug_summaries)}

请生成简洁的用药建议：
1. 推荐药物（优先OTC）
2. 用法用量要点
3. 主要注意事项
- 不超过300字
- 最后提醒"如症状持续请就医"
"""
    
    try:
        response = await llm.ainvoke(final_prompt)
        return response.content
    except Exception as e:
        return "\n".join(drug_summaries)


def _search_drug_impl(query: str) -> str:
    """同步包装函数"""
    return asyncio.run(_search_drug_impl_async(query))


async def _check_drug_interaction_impl_async(drug_list: list, medical_history: str) -> str:
    """
    药物审方检查实现（三步优化版 + 缓存优化 - 异步）
    
    流程优化：
    1. 先查数据库缓存获取药品说明书
    2. 缓存未命中才调API
    3. 结合用户健康档案进行LLM审方
    """
    print(f"🛡️ [Skill] 审方检查: {drug_list} vs {medical_history}")
    
    # === Step 1: 获取药品说明书（使用缓存优化） ===
    drug_infos = await _get_drug_info_with_cache(drug_list, use_api_fallback=True)
    
    # 补充本地知识库信息（如果缓存/API都没有完整信息）
    for i, info in enumerate(drug_infos):
        if not info.get("full_description") and not info.get("contraindications"):
            name = drug_list[i] if i < len(drug_list) else info.get("drug_name", "")
            local_docs = get_knowledge(f"{name} 禁忌症 不良反应")
            local_info = _extract_content_from_knowledge(local_docs)
            drug_infos[i]["full_description"] = local_info[:800] if local_info else "暂无"
            drug_infos[i]["source"] = "本地知识库(补充)"
    
    # === Step 2: 构建审方提示 ===
    drug_summaries = []
    for info in drug_infos:
        drug_summaries.append(f"""
【药品】：{info.get('name', '未知')}
【说明书/禁忌信息】：
{info.get('desc', '暂无')[:800]}
""")
    
    review_prompt = f"""
你是资深临床药师，请对以下用药方案进行安全审查。

【患者病史/过敏史】：{medical_history if medical_history else "未知"}

【拟用药品】
{"".join(drug_summaries)}

【审查要求】
1. 检查过敏风险
2. 检查慢性病禁忌
3. 检查药物相互作用

【输出格式】
风险等级：[安全]/[慎用]/[禁用]
原因：xxx（简要说明核心冲突点）
"""
    
    try:
        response = await llm.ainvoke(review_prompt)
        return f"【安全风控结论】：{response.content.strip()}"
    except Exception as e:
        return f"【安全风控结论】：[风险未知] 审方失败，请咨询医生。错误：{str(e)}"


def _check_drug_interaction_impl(drug_list: list, medical_history: str) -> str:
    """同步包装函数"""
    return asyncio.run(_check_drug_interaction_impl_async(drug_list, medical_history))


# ==========================================
# 缓存包装函数 - 用于药品检索（使用智能key生成 + 上下文）
# ==========================================
@cached(ttl=7200, prefix="drug_search", key_func=drug_search_key_func)  # 使用症状关键词作为key
async def search_drug_cached(query: str, context_info: dict = None):
    """
    带缓存的药品检索（优化版 - 基于上下文，Skill 模式）
    
    缓存策略：
    - 使用症状关键词而非完整查询作为key
    - 结合上下文（历史对话、慢性病、过敏史）提取更准确的症状
    - 相似症状（如"头痛发烧"和"发烧头痛"）可以命中同一缓存
    - 大幅提高缓存命中率
    
    Args:
        query: 当前查询文本
        context_info: 上下文信息字典，包含：
            - current_query: 当前查询
            - chronic_diseases: 慢性病列表
            - allergies: 过敏史列表
            - recent_messages: 最近的对话消息列表
    """
    # 在线程池中运行同步函数（Skill 模式：直接调用内联实现）
    result = await asyncio.to_thread(_search_drug_impl, query)
    return result

# ==========================================
# 节点 2: 药师报告节点 (带并行化+缓存+状态回调)
# ==========================================
async def report_node(state: AgentState):
    # [新增拦截逻辑] 如果已经是待确认状态，不要执行问诊，直接透传状态给 router
    if state.get("workflow_stage") == "awaiting_confirmation":
        return {"messages": []} # 不做任何修改，原样交给 router 判断
    
    print("--- [Node] Pharmacist Reporting (With Parallel + Cache) ---")
    messages = state["messages"]
    user_id = state["user_id"]
    session_id = state["session_id"]
    history_summary = state.get("history_summary", "")
    
    # 🔥 改进：智能提取主诉，而不是只取最后一条消息
    # 1. 先尝试从历史摘要中提取主诉
    # 2. 如果没有摘要，从前几轮对话中提取
    # 3. 避免用最后一条消息（可能只是补充信息）
    
    user_query = "用户未描述症状"
    
    # 方案A：如果有历史摘要，从摘要中提取主诉
    if history_summary and "主诉" in history_summary:
        print("📋 从历史摘要中提取主诉")
        user_query = history_summary
    else:
        # 方案B：从整个对话历史中智能提取主诉
        print("🔍 从对话历史中提取主诉")
        user_messages = [m.content for m in messages if isinstance(m, HumanMessage)]
        
        if len(user_messages) > 0:
            # 使用LLM提取主诉（强调时间顺序）
            extraction_prompt = f"""
            从以下用户的多轮对话中，提取**最初的主诉症状**（而非后续补充）：
            
            对话记录（按时间顺序）：
            {chr(10).join([f"{i+1}. {msg}" for i, msg in enumerate(user_messages)])}
            
            【提取要求】
            - 主诉应该是用户**最开始描述的不适症状**
            - 如果第1条消息就描述了症状，直接使用第1条
            - 如果后续有补充，可以合并，但主诉优先
            - 不要用慢性病史替代主诉
            - 格式：主诉症状 + 持续时间 + 严重程度
            
            示例：
            - 好的输出："头痛持续3天，阵发性加重"
            - 差的输出："有高血压病史，昨天吃了止痛药"
            
            请提取主诉：
            """
            
            try:
                extraction_result = await llm.ainvoke(extraction_prompt)
                user_query = extraction_result.content.strip()
                print(f"✅ 提取的主诉: {user_query}")
            except Exception as e:
                print(f"⚠️ 主诉提取失败，使用前3条消息: {e}")
                # 降级方案：使用前3条用户消息
                user_query = " | ".join(user_messages[:3])

    # ==================================================
    # 🔥 A. 并行获取：用户档案 + 问诊历史 + 药品检索
    # ==================================================
    await send_status(session_id, "正在检索知识库...")
    
    # 创建并行任务
    profile_task = asyncio.create_task(
        asyncio.to_thread(db.get_user_profile, user_id)
    )
    history_task = asyncio.create_task(
        asyncio.to_thread(db.get_past_consultations, user_id, 3)
    )
    
    # 获取慢性病信息用于搜索（先快速获取profile）
    profile = await profile_task
    chronic = ", ".join(profile.get("chronic_diseases", [])) or "无"
    
    # 🔥 带缓存的药品检索（传入完整上下文）
    # 构建包含历史信息的查询上下文
    context_info = {
        "current_query": user_query,
        "chronic_diseases": profile.get("chronic_diseases", []),
        "allergies": profile.get("allergies", []),
        "recent_messages": [m.content for m in messages[-5:] if isinstance(m, HumanMessage)]
    }
    
    search_query = f"{user_query} (患者有{chronic}病史)"
    drug_task = asyncio.create_task(search_drug_cached(search_query, context_info))
    
    # 等待剩余任务完成
    past_records, drug_context_raw = await asyncio.gather(
        history_task, drug_task
    )
    
    print(f"✅ 并行任务完成: profile={bool(profile)}, history={len(past_records)}, drugs={bool(drug_context_raw)}")
    
    # ==================================================
    # B. 格式化用户健康档案
    # ==================================================
    allergies = ", ".join(profile.get("allergies", [])) or "无"
    age = profile.get("age", "未知")
    
    user_profile_str = f"""
    - 年龄: {age}
    - 过敏史: {allergies}
    - 慢性病: {chronic}
    """

    # ==================================================
    # C. 格式化过往问诊历史
    # ==================================================
    past_consultation_str = "无历史记录"
    if past_records:
        history_list = []
        for rec in past_records:
            record_time = rec['created_at']
            symptom = rec['symptom_summary']
            drugs = rec['recommended_drugs']
            history_list.append(f"- [{record_time}] 曾因'{symptom}'咨询，当时推荐了: {drugs}")
        past_consultation_str = "\n".join(history_list)

    # ==================================================
    # D. 处理药品检索结果
    # ==================================================
    context_str = ""
    if isinstance(drug_context_raw, list):
        context_str = "\n".join([d.get("content", str(d)) for d in drug_context_raw])
    else:
        context_str = str(drug_context_raw)

    # ==================================================
    # 🔥 E. 发送状态：正在分析药物
    # ==================================================
    await send_status(session_id, "正在分析药物适用性...")
    
    # 1. 让 LLM 粗选药
    selection_prompt = f"基于药典：\n{context_str}\n针对用户症状'{user_query}'，选出1-2个药名。只返回名字，逗号分隔。"
    selected_drugs_text = (await llm.ainvoke(selection_prompt)).content
    selected_drugs = [d.strip() for d in selected_drugs_text.split("，") if d.strip()]

    # ==================================================
    # 🔥 F. 发送状态：正在检查安全性
    # ==================================================
    await send_status(session_id, "正在检查用药安全...")
    
    # 2. 构造完整的病史字符串用于检查
    full_medical_history = f"过敏史:{allergies}; 慢性病:{chronic}; 既往用药记录:{past_consultation_str}"
    
    # 药物相互作用检查（Skill 模式：直接调用内联实现）
    interaction_context = await asyncio.to_thread(
        _check_drug_interaction_impl,
        selected_drugs,
        full_medical_history
    )

    # ==================================================
    # 🔥 G. 发送状态：正在生成报告
    # ==================================================
    await send_status(session_id, "正在生成用药建议报告...")
    
    reporter = llm.with_structured_output(MedicalReport)
    
    report = await (REPORT_PROMPT | reporter).ainvoke({
        "drug_context": context_str,
        "interaction_context": interaction_context,
        "user_profile_str": user_profile_str,
        "past_consultation_str": past_consultation_str,
        "user_symptoms": user_query
    })

    # ==================================================
    # H. 存储问诊记录到数据库
    # ==================================================
    try:
        await asyncio.to_thread(
            db.save_consultation_result,
            session_id,
            user_id,
            report.model_dump()
        )
        print("✅ 问诊记录已归档")
    except Exception as e:
        print(f"⚠️ 问诊记录存储失败: {e}")

    # ==================================================
    # 🔥 I. 提取并持久化会话上下文（症状、禁忌、反馈）
    # ==================================================
    try:
        # 从对话中提取结构化信息
        extraction_prompt = f"""
        从以下医疗咨询对话中提取关键信息，以JSON格式输出：
        
        对话历史：
        {[m.content for m in messages if isinstance(m, (HumanMessage, AIMessage))]}
        
        用户档案：{user_profile_str}
        
        【提取规则 - 按重要性排序】
        1. **symptoms（主诉症状）**：
           - **最重要！** 用户最初描述的主要不适
           - 包含时间、程度、特征
           - 示例：["头痛持续3天，阵发性", "发烧38度昨晚开始"]
        
        2. **contraindications（禁忌信息）**：
           - 过敏史（药物、食物）
           - 慢性病史（高血压、糖尿病等）
           - 特殊状态（孕期、哺乳期）
           - 示例：["青霉素过敏", "高血压病史"]
        
        3. **feedback（用户反馈）**：
           - 对之前建议的评价
           - 示例：["上次推荐的药很有效"]
        
        ⚠️ 注意：
        - 症状 ≠ 慢性病史
        - "有高血压" 是禁忌，不是症状
        - 症状应该是"本次咨询的新发不适"
        
        JSON格式：
        {{
            "symptoms": ["主诉症状1", "主诉症状2"],
            "contraindications": ["禁忌1", "禁忌2"],
            "feedback": ["反馈1"]
        }}
        """
        
        extraction_result = await llm.ainvoke(extraction_prompt)
        
        # 解析提取结果
        try:
            import re
            # 尝试从响应中提取JSON
            json_match = re.search(r'\{.*\}', extraction_result.content, re.DOTALL)
            if json_match:
                extracted_data = json.loads(json_match.group())
            else:
                # 如果没有找到JSON，使用默认值
                extracted_data = {
                    "symptoms": [user_query],
                    "contraindications": profile.get("allergies", []) + profile.get("chronic_diseases", []),
                    "feedback": []
                }
        except json.JSONDecodeError:
            # JSON解析失败，使用默认值
            extracted_data = {
                "symptoms": [user_query],
                "contraindications": profile.get("allergies", []) + profile.get("chronic_diseases", []),
                "feedback": []
            }
        
        # 存储到数据库
        await asyncio.to_thread(
            db.update_session_context,
            session_id,
            extracted_data
        )
        print(f"✅ 会话上下文已持久化: {len(extracted_data.get('symptoms', []))}个症状")
        
    except Exception as e:
        print(f"⚠️ 上下文提取/存储失败: {e}")

    return {
        "messages": [AIMessage(content=report.model_dump_json())],
        "workflow_stage": "awaiting_confirmation"
    }

# ==========================================
# 节点 3: 评价收集节点 (新增)
# ==========================================
# --- 节点 3.A: 主动询问评价节点 ---
async def ask_feedback_node(state: AgentState):
    """
    当用户确认收到报告（说“好的”）后，进入此节点。
    功能：只负责发出询问，不处理逻辑。
    """
    print("--- [Node] Asking for Feedback ---")
    
    # 返回询问话术，并将状态流转为 'awaiting_feedback_input' (等待用户输入评价)
    return {
        "messages": [AIMessage(content="请问您对本次咨询满意吗？(1-5分，欢迎留言)")],
        "workflow_stage": "awaiting_feedback_input" 
    }

# --- 节点 3.B: 存储评价节点 ---
async def save_feedback_node(state: AgentState):
    """
    当用户输入评价内容后，进入此节点。
    功能：提取评分 -> 存库 -> 致谢 -> 结束。
    """
    print("--- [Node] Saving Feedback ---")
    messages = state["messages"]
    last_user_msg = messages[-1].content
    session_id = state["session_id"]
    
    # 1. 提取评价
    extractor = llm.with_structured_output(FeedbackExtraction)
    prompt = f"用户对医疗咨询的反馈是：'{last_user_msg}'。请提取评分(1-5)和内容。如果只说了数字，就是评分。如果只表示感谢，评分为5。"
    
    try:
        feedback_data = await extractor.ainvoke(prompt)
        
        # 2. 存入数据库
        db.save_feedback(
            session_id=session_id,
            rating=feedback_data.rating,
            comment=feedback_data.comment,
            # accuracy_score=None # 目前只提取通用评分，如需准确性分可扩展 prompt
        )
        
        # 3. 回复致谢并结束
        return {
            "messages": [AIMessage(content="感谢您的反馈！祝您早日康复。")],
            "workflow_stage": "finished"
        }
        
    except Exception as e:
        print(f"Feedback Error: {e}")
        return {
            "messages": [AIMessage(content="收到，祝您健康！")],
            "workflow_stage": "finished"
        }
# async def feedback_node(state: AgentState):
#     print("--- [Node] Feedback Collection ---")
#     messages = state["messages"]
#     last_user_msg = messages[-1].content
#     session_id = state["session_id"] # 获取当前的会话 ID
    
#     # 1. 使用 LLM 分析评价内容并提取结构化数据
#     extractor = llm.with_structured_output(FeedbackExtraction)
#     feedback_prompt = f"分析用户评价：'{last_user_msg}'。提取评分(1-5)和内容。如果用户没给明确分，根据语气判断。"
    
#     try:
#         # 异步调用模型提取反馈
#         feedback = await extractor.ainvoke(feedback_prompt)
        
#         # 2. 调用 MedicalDatabase 中封装好的方法进行存储
#         db.save_feedback(
#             session_id=session_id, 
#             rating=feedback.rating, 
#             comment=feedback.comment
#         ) 
        
#         return {
#             "messages": [AIMessage(content="感谢您的反馈！祝您早日康复。")], 
#             "workflow_stage": "finished"
#         }
#     except Exception as e:
#         print(f"⚠️ 反馈处理或存储过程中出现错误: {e}")
#         # 即使反馈存储失败，也优雅地结束对话，避免中断用户体验
#         return {
#             "messages": [AIMessage(content="收到，祝您健康！")], 
#             "workflow_stage": "finished"
#         }

# ==========================================
# 路由逻辑
# ==========================================
def router(state: AgentState) -> Literal["doctor", "pharmacist", "ask_feedback", "save_feedback", "end"]:
    stage = state.get("workflow_stage", "inquiry")
    messages = state["messages"]
    print('目前stage：', stage)
    if not messages:
        return "doctor"
        
    last_msg = messages[-1]

    # --- 0. 完结状态拦截
    if stage == "finished":
        return "end"
    
    # --- 1. 优先处理：待确认阶段 (报告已发出，用户已回复) ---
    if stage == "awaiting_confirmation":
        if isinstance(last_msg, HumanMessage):
            content = last_msg.content.lower()
            if any(word in content for word in ["好", "谢", "ok", "再见", "可以"]):
                return "ask_feedback"
            # 如果不是确认语（说明用户有新问题），回到问诊节点
            # inquiry_node 会继续处理
            print("🔄 用户提出新问题，返回问诊节点")
            return "doctor"
        return "end"

    # [阶段二] 等待评价输入阶段 (AI已问"满意吗" -> 等待用户打分)
    if stage == "awaiting_feedback_input":
        if isinstance(last_msg, HumanMessage):
            # 用户只要回复了，无论说什么，都尝试去提取并存储
            return "save_feedback"
        return "end"
    
    # --- 2. 只有在处于问诊阶段且收到指令时，才进入药师节点 ---
    # 这样可以防止在 awaiting_confirmation 阶段因为历史消息里有 READY 指令而误入药师
    if stage == "reporting" or (stage == "inquiry" and isinstance(last_msg, SystemMessage) and "READY_TO_REPORT" in last_msg.content):
        return "pharmacist"

    # --- 3. 问诊阶段处理 ---
    if stage == "inquiry":
        if isinstance(last_msg, AIMessage):
            return "end"
        return "doctor"

    # --- 4. 反馈阶段处理 ---
    # if stage == "feedback":
    #     if isinstance(last_msg, AIMessage) and "感谢" in last_msg.content:
    #         return "end"
    #     return "feedback"

    return "doctor"

# 构建图
workflow = StateGraph(AgentState)
workflow.add_node("doctor", inquiry_node)
workflow.add_node("pharmacist", report_node)
workflow.add_node("ask_feedback", ask_feedback_node)   # 新增：负责提问
workflow.add_node("save_feedback", save_feedback_node) # 新增：负责存储

workflow.set_entry_point("doctor")

workflow.add_conditional_edges(
    "doctor",
    router,
    {"pharmacist": "pharmacist", "doctor": "doctor", 'ask_feedback': "ask_feedback", "save_feedback": "save_feedback", "end": END}
)

workflow.add_conditional_edges(
    "pharmacist", # 药师节点执行完后，会根据 report_node 设置的 stage 进入 router
    router,
    {"ask_feedback": "ask_feedback", "doctor": "doctor", "end": END}
)

workflow.add_conditional_edges(
    "ask_feedback",
    router,
    # 提问后，等待用户输入，通常会进入 end 等待 human input
    {"save_feedback": "save_feedback", "end": END}
)

workflow.add_conditional_edges(
    "save_feedback",
    router,
    # 存完后 finished -> end
    {"end": END}
)

# 必须使用 checkpointer
checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)
