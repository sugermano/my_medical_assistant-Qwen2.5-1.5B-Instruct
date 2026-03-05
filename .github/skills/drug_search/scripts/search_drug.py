#!/usr/bin/env python3
"""
药品智能搜索脚本（三步优化版 + 缓存优化）

工作流程：
1. 症状 → 候选药名（本地知识库 + LLM兜底）
2. 候选药名 → 查数据库缓存 → 缓存未命中才调API
3. 整合输出精简摘要

使用方式:
    python search_drug.py "头痛发烧"
    python search_drug.py "感冒咳嗽" --json
"""
import sys
import os
import json
import argparse
import aiohttp
import asyncio
from typing import List, Dict, Optional

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, PROJECT_ROOT)

from database.get_knowledge import get_knowledge
from database.medical_database import MedicalDatabase
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# 极速数据 API 配置
JISU_API_KEY = "9ffa21c8cfde253b"
JISU_SEARCH_URL = "https://api.jisuapi.com/medicine/query"
JISU_DETAIL_URL = "https://api.jisuapi.com/medicine/detail"

# 数据库实例
db = MedicalDatabase()

# 初始化 LLM
def get_llm():
    return init_chat_model(
        model="Qwen/Qwen2.5-7B-Instruct",
        model_provider="openai",
        temperature=0.1,
        api_key=os.getenv("SILICONFLOW_API_KEY"),
        base_url="https://api.siliconflow.cn/v1"
    )


# ==========================================
# Step 1: 症状 → 候选药名 + 本地信息判断
# ==========================================
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


async def extract_drug_names_from_symptoms(symptoms: str, llm) -> tuple:
    """
    从症状中提取候选药名，并判断本地是否有完整信息
    
    Returns:
        (候选药名列表, 本地是否有完整信息, 是否使用了LLM兜底)
    """
    print(f"🔍 [Step 1] 从症状提取候选药名: {symptoms}", file=sys.stderr)
    
    # 1. 从本地知识库搜索
    raw_docs = get_knowledge(symptoms)
    raw_result = _extract_content_from_knowledge(raw_docs)
    local_has_info = bool(raw_result and len(raw_result) > 100)
    
    # 2. 用 LLM 从搜索结果中提取药名和判断信息完整性
    extract_prompt = f"""
你是一个专业的药品信息提取专家。请从以下药品说明书片段中提取：
1. 具体的药品通用名
2. 是否包含该药的完整说明书信息（用法用量、禁忌症等）

【用户症状】：{symptoms}
【搜索结果】：{raw_result[:2000] if raw_result else "无"}

【输出格式】（JSON）：
{{
    "drugs": ["药名1", "药名2", "药名3"],
    "has_full_info": true/false
}}

如果搜索结果中没有明确药名，drugs 返回空列表 []。
请直接返回JSON：
"""
    
    drugs = []
    local_info_available = False
    llm_fallback_used = False
    
    try:
        response = await asyncio.to_thread(llm.invoke, extract_prompt)
        content = response.content.strip()
        
        # 尝试解析 JSON
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
        print(f"⚠️ 药名提取失败: {e}", file=sys.stderr)
        drugs = []
    
    # 3. 兜底逻辑：如果本地知识库没搜到药名，用 LLM 常识推荐
    if not drugs:
        print("⚠️ 本地指南未命中具体药物，触发大模型常识兜底...", file=sys.stderr)
        llm_fallback_used = True
        
        fallback_prompt = f"""
作为专业全科医生，针对症状"{symptoms}"，请列举 3 种国内最常见的非处方药(OTC)通用名。
请确保药物是安全、常用的。只返回 JSON 数组，例如 ["布洛芬", "对乙酰氨基酚"]。

【症状分析案例】：
- 头痛/发烧 -> 布洛芬、对乙酰氨基酚
- 咳嗽 -> 氢溴酸右美沙芬、氨溴索
- 感冒 -> 复方氨酚烷胺、感冒灵
- 腹泻 -> 蒙脱石散、黄连素
- 便秘 -> 乳果糖、开塞露

请根据"{symptoms}"返回药名列表：
"""
        
        try:
            response = await asyncio.to_thread(llm.invoke, fallback_prompt)
            content = response.content.strip()
            if content.startswith("["):
                drugs = json.loads(content)
                drugs = [d.strip() for d in drugs if d][:3]
        except Exception as e:
            print(f"⚠️ 兜底推荐失败: {e}", file=sys.stderr)
            drugs = ["布洛芬", "对乙酰氨基酚"]
    
    print(f"✅ [Step 1] 候选药名: {drugs}, 本地有完整信息: {local_info_available}, LLM兜底: {llm_fallback_used}", file=sys.stderr)
    return drugs[:5], local_info_available, llm_fallback_used


# ==========================================
# Step 2: 获取药品详情（缓存优化）
# ==========================================
async def fetch_drug_from_api(drug_name: str, session: aiohttp.ClientSession) -> Optional[Dict]:
    """从极速数据 API 获取药品详情（仅在缓存未命中时调用）"""
    try:
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
        print(f"⚠️ API获取失败 [{drug_name}]: {e}", file=sys.stderr)
        return None


async def get_drug_info_with_cache(drug_names: List[str], use_api_fallback: bool = True) -> List[Dict]:
    """
    获取药品信息（带缓存优化）
    
    优先级：数据库缓存 → API（可选）
    """
    if not drug_names:
        return []
    
    # Step 1: 批量查询数据库缓存
    cached_drugs = db.get_drugs_from_cache(drug_names)
    print(f"💾 [Cache] 缓存命中: {list(cached_drugs.keys())} / {drug_names}", file=sys.stderr)
    
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
        print(f"🌐 [API] 需要调用API获取: {uncached_names}", file=sys.stderr)
        async with aiohttp.ClientSession() as session:
            tasks = [fetch_drug_from_api(name, session) for name in uncached_names]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            api_results = []
            for name, resp in zip(uncached_names, responses):
                if isinstance(resp, dict) and resp.get("full_description"):
                    drug_infos.append(resp)
                    api_results.append(resp)
                    print(f"  ✅ {name}: API获取成功", file=sys.stderr)
                else:
                    drug_infos.append({
                        "drug_name": name,
                        "name": name,
                        "full_description": "",
                        "prescription_type": "未知",
                        "source": "未知"
                    })
                    print(f"  ⚠️ {name}: API未命中", file=sys.stderr)
            
            # 批量存入缓存
            if api_results:
                db.save_drugs_to_cache(api_results)
    elif uncached_names:
        for name in uncached_names:
            drug_infos.append({
                "drug_name": name,
                "name": name,
                "full_description": "",
                "prescription_type": "未知",
                "source": "未知"
            })
    
    return drug_infos


async def get_drug_info_from_local_and_cache(drug_names: List[str], local_info_available: bool) -> List[Dict]:
    """
    根据本地信息可用性，决定获取药品信息的方式
    """
    drug_infos = []
    
    if local_info_available:
        # 🔥 本地知识库有完整信息，直接使用，不调API
        print("📚 [Step 2] 使用本地知识库信息，无需调用API", file=sys.stderr)
        for name in drug_names:
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
            db.save_drug_to_cache({
                "drug_name": name,
                "full_description": local_info[:1500] if local_info else "",
                "source": "本地知识库"
            })
    else:
        # 🔥 本地无完整信息，需要查缓存/API
        print("🔄 [Step 2] 查询数据库缓存...", file=sys.stderr)
        drug_infos = await get_drug_info_with_cache(drug_names, use_api_fallback=True)
    
    return drug_infos


# ==========================================
# Step 3: 整合输出
# ==========================================
async def format_drug_summary(drug_infos: List[Dict], symptoms: str, llm) -> str:
    """将药品信息整合成用户友好的摘要"""
    print(f"📝 [Step 3] 整合药品信息...", file=sys.stderr)
    
    if not drug_infos:
        return "未找到相关药品信息，建议咨询医生或药师。"
    
    drug_summaries = []
    for info in drug_infos:
        desc = info.get("full_description") or info.get("desc") or ""
        drug_summaries.append(f"""
【药品名称】：{info.get('name') or info.get('drug_name', '未知')}
【类型】：{info.get('prescription_type', '未知')}
【来源】：{info.get('source', '未知')}
【说明书摘要】：
{desc[:400] if desc else '暂无详细说明'}
""")
    
    final_prompt = f"""
你是一个专业的药师。用户症状是"{symptoms}"，以下是相关药品信息：

{"".join(drug_summaries)}

请生成一个简洁的用药建议，包括：
1. 推荐药物（优先OTC）
2. 用法用量要点
3. 主要注意事项

格式要求：
- 不超过300字
- 使用【】标注关键信息
- 最后提醒"如症状持续请就医"

输出：
"""
    
    try:
        response = await asyncio.to_thread(llm.invoke, final_prompt)
        return response.content
    except Exception as e:
        print(f"⚠️ 生成建议失败: {e}", file=sys.stderr)
        return "\n".join(drug_summaries)


# ==========================================
# 主函数
# ==========================================
async def search_drug_async(symptoms: str, context_info: dict = None) -> Dict:
    """
    三步智能药品搜索（带缓存优化）
    
    Args:
        symptoms: 用户症状
        context_info: 上下文信息（可选）
    
    Returns:
        {
            "success": True/False,
            "drugs": [药名列表],
            "drug_infos": [详细信息列表],
            "summary": "综合建议",
            "cache_stats": {"hits": X, "api_calls": Y}
        }
    """
    llm = get_llm()
    
    # Step 1: 症状 → 候选药名
    drug_names, local_info_available, llm_fallback_used = await extract_drug_names_from_symptoms(symptoms, llm)
    
    if not drug_names:
        return {
            "success": False,
            "drugs": [],
            "drug_infos": [],
            "summary": "未能识别相关药品，建议咨询医生。",
            "cache_stats": {"hits": 0, "api_calls": 0}
        }
    
    # Step 2: 候选药名 → 获取详情（缓存优化）
    if local_info_available and not llm_fallback_used:
        drug_infos = await get_drug_info_from_local_and_cache(drug_names, True)
    else:
        drug_infos = await get_drug_info_from_local_and_cache(drug_names, False)
    
    # Step 3: 整合输出
    summary = await format_drug_summary(drug_infos, symptoms, llm)
    
    # 统计缓存命中情况
    cache_hits = sum(1 for info in drug_infos if info.get("source") in ["本地知识库", "缓存"])
    api_calls = sum(1 for info in drug_infos if info.get("source") == "API")
    
    return {
        "success": True,
        "drugs": drug_names,
        "drug_infos": drug_infos,
        "summary": summary,
        "cache_stats": {"hits": cache_hits, "api_calls": api_calls}
    }


def search_drug(symptoms: str, context_info: dict = None) -> str:
    """同步包装函数"""
    result = asyncio.run(search_drug_async(symptoms, context_info))
    return result.get("summary", "搜索失败")


def main():
    parser = argparse.ArgumentParser(description='药品智能搜索（三步优化版 + 缓存优化）')
    parser.add_argument('symptoms', help='症状描述（如"头痛发烧"）')
    parser.add_argument('--context', type=str, default='{}', help='上下文信息（JSON格式）')
    parser.add_argument('--json', action='store_true', help='输出完整JSON格式')
    
    args = parser.parse_args()
    
    try:
        context_info = json.loads(args.context)
    except json.JSONDecodeError:
        context_info = {}
    
    result = asyncio.run(search_drug_async(args.symptoms, context_info))
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("summary", "搜索失败"))


if __name__ == "__main__":
    main()
