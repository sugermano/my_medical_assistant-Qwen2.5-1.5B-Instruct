#!/usr/bin/env python3
"""
药物审方与相互作用检查脚本（三步优化版 + 缓存优化）

工作流程：
1. 先查数据库缓存获取药品说明书
2. 缓存未命中才调用极速数据API
3. 结合用户健康档案（过敏史、慢性病）进行LLM审方

使用方式:
    python check_interaction.py "布洛芬,阿司匹林" "胃溃疡病史"
    python check_interaction.py "感冒灵" --allergies "青霉素过敏" --chronic "高血压"
    python check_interaction.py "布洛芬" --user_id 123 --json
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
# Step 1: 获取药品说明书（缓存优化）
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
                "prescription_type": "处方药" if result.get("prescription") == 1 else "OTC",
                "full_description": result.get("desc", ""),
                "contraindications": "",  # 可从desc中提取
                "source": "API"
            }
    except Exception as e:
        print(f"⚠️ API获取失败 [{drug_name}]: {e}", file=sys.stderr)
        return None


async def get_drug_safety_info_with_cache(drug_names: List[str]) -> List[Dict]:
    """
    获取药品安全信息（带缓存优化）
    
    优先级：数据库缓存 → API → 本地知识库
    """
    if not drug_names:
        return []
    
    print(f"📋 [Step 1] 获取药品说明书（缓存优化）...", file=sys.stderr)
    
    # Step 1: 批量查询数据库缓存
    cached_drugs = db.get_drugs_from_cache(drug_names)
    print(f"💾 [Cache] 缓存命中: {list(cached_drugs.keys())} / {drug_names}", file=sys.stderr)
    
    drug_infos = []
    uncached_names = []
    
    for name in drug_names:
        if name in cached_drugs:
            drug_infos.append(cached_drugs[name])
        else:
            uncached_names.append(name)
    
    # Step 2: 对未命中的药品调用API
    if uncached_names:
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
                    # API失败，从本地知识库获取
                    print(f"  🔄 {name}: API未命中，从本地知识库获取...", file=sys.stderr)
                    local_docs = get_knowledge(f"{name} 禁忌症 不良反应 慎用人群")
                    local_info = _extract_content_from_knowledge(local_docs)
                    info = {
                        "drug_name": name,
                        "name": name,
                        "prescription_type": "未知",
                        "full_description": local_info[:800] if local_info else "暂无",
                        "source": "本地知识库"
                    }
                    drug_infos.append(info)
                    # 本地知识库的信息也存入缓存
                    if local_info:
                        db.save_drug_to_cache({
                            "drug_name": name,
                            "full_description": local_info[:1500],
                            "source": "本地知识库"
                        })
            
            # 批量存入缓存（API成功的）
            if api_results:
                db.save_drugs_to_cache(api_results)
    
    # 补充本地知识库信息（如果缓存/API都没有完整禁忌信息）
    for i, info in enumerate(drug_infos):
        if not info.get("full_description") and not info.get("contraindications"):
            name = drug_names[i] if i < len(drug_names) else info.get("drug_name", "")
            local_docs = get_knowledge(f"{name} 禁忌症 不良反应")
            local_info = _extract_content_from_knowledge(local_docs)
            drug_infos[i]["full_description"] = local_info[:800] if local_info else "暂无"
            drug_infos[i]["source"] = "本地知识库(补充)"
    
    return drug_infos


# ==========================================
# Step 2: 获取用户健康档案
# ==========================================
def get_user_health_profile(user_id: str = None, allergies: str = None, chronic_diseases: str = None) -> Dict:
    """
    获取用户健康档案
    
    优先级：数据库 → 命令行参数 → 空档案
    """
    profile = {
        "allergies": [],
        "chronic_diseases": [],
        "current_medications": [],
        "special_conditions": []
    }
    
    # 1. 从数据库查询
    if user_id:
        try:
            db_profile = db.get_user_profile(user_id)
            if db_profile:
                profile["allergies"] = db_profile.get("allergies", [])
                profile["chronic_diseases"] = db_profile.get("chronic_diseases", [])
                print(f"📊 [Step 2] 从数据库获取用户档案: 过敏={profile['allergies']}, 慢性病={profile['chronic_diseases']}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ 数据库查询失败: {e}", file=sys.stderr)
    
    # 2. 使用命令行参数补充
    if allergies:
        profile["allergies"].extend([a.strip() for a in allergies.split(",") if a.strip()])
    if chronic_diseases:
        profile["chronic_diseases"].extend([c.strip() for c in chronic_diseases.split(",") if c.strip()])
    
    # 去重
    profile["allergies"] = list(set(profile["allergies"]))
    profile["chronic_diseases"] = list(set(profile["chronic_diseases"]))
    
    return profile


# ==========================================
# Step 3: LLM 审方
# ==========================================
async def analyze_drug_safety(drug_infos: List[Dict], user_profile: Dict, llm) -> Dict:
    """
    使用 LLM 分析药物安全性，结合用户档案进行审方
    """
    print(f"🔍 [Step 3] LLM审方分析...", file=sys.stderr)
    
    # 构建药品信息汇总
    drug_summaries = []
    for info in drug_infos:
        desc = info.get("full_description") or info.get("desc") or "无详细信息"
        drug_summaries.append(f"""
【药品】：{info.get('name') or info.get('drug_name', '未知')}
【类型】：{info.get('prescription_type', '未知')}
【来源】：{info.get('source', '未知')}
【说明书/禁忌信息】：
{desc[:800] if desc else '暂无'}
""")
    
    # 构建用户档案字符串
    allergies_str = ", ".join(user_profile.get("allergies", [])) or "无已知过敏"
    chronic_str = ", ".join(user_profile.get("chronic_diseases", [])) or "无已知慢性病"
    medications_str = ", ".join(user_profile.get("current_medications", [])) or "无"
    special_str = ", ".join(user_profile.get("special_conditions", [])) or "无"
    
    # 审方提示词
    review_prompt = f"""
你是一名资深临床药师，请对以下用药方案进行安全审查。

【患者健康档案】
- 过敏史：{allergies_str}
- 慢性病：{chronic_str}
- 当前用药：{medications_str}
- 特殊情况：{special_str}

【拟用药品】
{"".join(drug_summaries)}

【审查要求】
请从以下方面进行分析：

1. **过敏风险**：检查药品成分是否与患者过敏史冲突
2. **慢性病禁忌**：检查药品是否有针对患者慢性病的禁忌
3. **药物相互作用**：如果多个药品，检查是否有相互作用
4. **特殊人群**：检查是否有针对特殊情况（如孕期）的警告

【输出格式】（JSON）
{{
    "risk_level": "[安全]/[慎用]/[禁用]",
    "warnings": ["具体警告1", "具体警告2"],
    "recommendations": ["建议1", "建议2"],
    "drug_interactions": ["相互作用描述"],
    "summary": "简明总结（不超过100字）"
}}

请直接返回JSON，不要其他内容：
"""
    
    try:
        response = await asyncio.to_thread(llm.invoke, review_prompt)
        content = response.content.strip()
        
        # 解析 JSON
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return result
        else:
            return {
                "risk_level": "[风险未知]",
                "warnings": ["无法解析审方结果"],
                "recommendations": ["建议咨询医生或药师"],
                "drug_interactions": [],
                "summary": content[:200]
            }
    except Exception as e:
        print(f"⚠️ 审方分析失败: {e}", file=sys.stderr)
        return {
            "risk_level": "[风险未知]",
            "warnings": [f"审方分析异常: {str(e)}"],
            "recommendations": ["建议咨询医生或药师"],
            "drug_interactions": [],
            "summary": "系统无法完成自动审方，请务必咨询专业人士"
        }


# ==========================================
# 主函数
# ==========================================
async def check_interaction_async(
    drug_names: List[str],
    user_id: str = None,
    allergies: str = None,
    chronic_diseases: str = None,
    medical_history: str = None
) -> Dict:
    """
    三步药物审方检查（带缓存优化）
    
    Args:
        drug_names: 药品名称列表
        user_id: 用户ID（从数据库获取档案）
        allergies: 过敏史（逗号分隔）
        chronic_diseases: 慢性病（逗号分隔）
        medical_history: 综合病史描述
    
    Returns:
        {
            "success": True/False,
            "drugs": [药名列表],
            "user_profile": {用户档案},
            "analysis": {审方分析结果},
            "conclusion": "最终结论",
            "cache_stats": {"hits": X, "api_calls": Y}
        }
    """
    llm = get_llm()
    
    # Step 1: 获取药品说明书（缓存优化）
    drug_infos = await get_drug_safety_info_with_cache(drug_names)
    
    # Step 2: 获取用户健康档案
    user_profile = get_user_health_profile(user_id, allergies, chronic_diseases)
    
    # 如果提供了 medical_history，补充到档案中
    if medical_history:
        history_lower = medical_history.lower()
        if "过敏" in history_lower:
            user_profile["allergies"].append(medical_history)
        if any(d in history_lower for d in ["高血压", "糖尿病", "心脏病", "肝病", "肾病", "胃溃疡", "哮喘"]):
            user_profile["chronic_diseases"].append(medical_history)
        if any(s in history_lower for s in ["孕", "哺乳", "备孕"]):
            user_profile["special_conditions"].append(medical_history)
    
    print(f"📊 用户档案: 过敏={user_profile['allergies']}, 慢性病={user_profile['chronic_diseases']}", file=sys.stderr)
    
    # Step 3: LLM 审方
    analysis = await analyze_drug_safety(drug_infos, user_profile, llm)
    
    # 生成最终结论
    risk_level = analysis.get("risk_level", "[风险未知]")
    summary = analysis.get("summary", "")
    warnings = analysis.get("warnings", [])
    
    conclusion = f"【安全风控结论】：{risk_level}\n"
    if warnings:
        conclusion += "⚠️ 警告：" + "; ".join(warnings[:3]) + "\n"
    conclusion += f"📋 {summary}"
    
    # 统计缓存命中情况
    cache_hits = sum(1 for info in drug_infos if info.get("source") in ["本地知识库", "缓存"])
    api_calls = sum(1 for info in drug_infos if info.get("source") == "API")
    
    return {
        "success": True,
        "drugs": drug_names,
        "user_profile": user_profile,
        "analysis": analysis,
        "conclusion": conclusion,
        "cache_stats": {"hits": cache_hits, "api_calls": api_calls}
    }


def check_drug_interaction(drug_list: List[str], medical_history: str = "") -> str:
    """同步包装函数（兼容旧接口）"""
    result = asyncio.run(check_interaction_async(
        drug_names=drug_list,
        medical_history=medical_history
    ))
    return result.get("conclusion", "审方失败")


def main():
    parser = argparse.ArgumentParser(description='药物审方与相互作用检查（三步优化版 + 缓存优化）')
    parser.add_argument('drugs', help='药品列表（逗号分隔）')
    parser.add_argument('medical_history', nargs='?', default='', help='患者病史/过敏史（可选）')
    parser.add_argument('--user_id', type=str, help='用户ID（从数据库获取档案）')
    parser.add_argument('--allergies', type=str, help='过敏史（逗号分隔）')
    parser.add_argument('--chronic', type=str, help='慢性病（逗号分隔）')
    parser.add_argument('--json', action='store_true', help='输出完整JSON格式')
    
    args = parser.parse_args()
    
    # 解析药品列表
    drug_list = [d.strip() for d in args.drugs.split(',') if d.strip()]
    
    if not drug_list:
        print("错误: 请提供至少一个药品名称", file=sys.stderr)
        sys.exit(1)
    
    result = asyncio.run(check_interaction_async(
        drug_names=drug_list,
        user_id=args.user_id,
        allergies=args.allergies,
        chronic_diseases=args.chronic,
        medical_history=args.medical_history
    ))
    
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result.get("conclusion", "审方失败"))


if __name__ == "__main__":
    main()
