---
name: drug-search
description: 智能药品搜索与审方。当用户描述症状询问用药、查询药品说明书、或请求审查用药安全时使用。采用三步流程+缓存优化：本地知识库→数据库缓存→API，最大限度减少外部API调用。
tags: drug-rag, drug-api, medication-review, interaction-check, safety, cache
tags_cn: 药品智能搜索, 极速数据API, 审方, 用药安全, 缓存优化
---

# drug-search：智能药品搜索与审方（三步优化版 + 缓存优化）

## 核心流程

```
用户症状 → Step1: 本地RAG+LLM提取候选药名 
          ├── 本地有完整信息 → 直接使用 不调API
          └── 本地无完整信息 → Step2: 大模型根据描述生成常用药名，查数据库缓存
                              ├── 命中 → 直接使用 不调API
                              └── 未命中 → 调API → 存入缓存
          → Step3: LLM审方+用户画像 → 输出
```

### Step 1：症状 → 候选药名
- 先从本地知识库（ChromaDB）搜索相关药品描述
- 用 LLM 从描述中提取 3-5 个通用药名
- **判断信息完整性**：本地是否有完整的用法用量、禁忌症等
- **兜底逻辑**：如果本地没找到具体药名，用 LLM 常识推荐常见 OTC

### Step 2：候选药名 → 获取说明书（缓存优化）
- **🔥 本地信息完整时**：直接使用，不调API，同时存入缓存
- **本地信息不完整时**：
  - 先查数据库缓存表 `drug_info_cache`
  - 缓存命中 → 直接使用
  - 缓存未命中 → 调用极速数据API → 结果存入缓存

### Step 3：审方 + 用户画像
- 结合用户健康档案（过敏史、慢性病）
- LLM 进行安全审查，输出风险分级

---

## 数据库缓存表

```sql
CREATE TABLE IF NOT EXISTS drug_info_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT UNIQUE NOT NULL,    -- 药名（索引）
    full_description TEXT,             -- 完整说明书
    contraindications TEXT,            -- 禁忌症
    dosage_info TEXT,                  -- 用法用量
    prescription_type TEXT,            -- OTC/处方药
    manufacturer TEXT,                 -- 厂家
    source TEXT,                       -- 来源（API/本地知识库）
    updated_at TIMESTAMP
);
```

### 缓存方法
| 方法 | 功能 |
|------|------|
| `db.get_drug_from_cache(drug_name)` | 单个查询 |
| `db.get_drugs_from_cache(drug_names)` | 批量查询 |
| `db.save_drug_to_cache(drug_info)` | 单个存储 |
| `db.save_drugs_to_cache(drug_infos)` | 批量存储 |

---

## API调用节省场景

| 场景 | API调用 | 说明 |
|------|---------|------|
| 本地知识库有完整信息 | ❌ 不调用 | 直接使用本地数据 |
| 数据库缓存命中 | ❌ 不调用 | 使用缓存数据 |
| LLM兜底+缓存命中 | ❌ 不调用 | 常见药已缓存 |
| 首次查询新药 | ✅ 调用 | 存入缓存供后续使用 |

---

## 工作流A：药品智能搜索

### 触发场景
- "我头痛发烧，吃什么药"
- "感冒咳嗽用什么药好"
- "布洛芬说明书"

### 调用方式

```bash
# 命令行
python scripts/search_drug.py "头痛发烧"
python scripts/search_drug.py "感冒咳嗽" --json
```

```python
# 代码调用
from search_drug import search_drug_async
result = await search_drug_async("头痛发烧")
# result = {
#     "success": True,
#     "drugs": ["布洛芬", "对乙酰氨基酚"],
#     "drug_infos": [...],
#     "summary": "用药建议...",
#     "cache_stats": {"hits": 2, "api_calls": 0}  # 缓存统计
# }
```

### 输出示例
```
【推荐药物】布洛芬（OTC）
【用法用量】成人每次200-400mg，每日3次
【来源】本地知识库
【注意事项】胃溃疡患者慎用
如症状持续请就医
```

---

## 工作流B：药物审方检查

### 触发场景
- "布洛芬和阿司匹林能一起吃吗"
- "我有胃溃疡，能吃止痛药吗"
- "帮我审查这个用药方案"

### 调用方式

```bash
# 命令行
python scripts/check_interaction.py "布洛芬,阿司匹林" "胃溃疡病史"
python scripts/check_interaction.py "感冒灵" --allergies "青霉素" --chronic "高血压"
python scripts/check_interaction.py "布洛芬" --user_id 123 --json
```

```python
# 代码调用
from check_interaction import check_interaction_async
result = await check_interaction_async(
    drug_names=["布洛芬", "阿司匹林"],
    allergies="青霉素过敏",
    chronic_diseases="高血压,胃溃疡"
)
# result = {
#     "risk_level": "[慎用]",
#     "warnings": ["胃溃疡患者使用NSAIDs类药物可能加重症状"],
#     "recommendations": ["建议选择对乙酰氨基酚替代"],
#     "cache_stats": {"hits": 1, "api_calls": 1}  # 缓存统计
# }
```

### 输出格式
```
【安全风控结论】：[慎用]
⚠️ 警告：胃溃疡患者使用布洛芬可能加重症状
📋 建议使用对乙酰氨基酚替代，或咨询医生
```

---

## API 配置

### 极速数据 API
- **AppKey**: `9ffa21c8cfde253b`
- **配额**: 100次/天
- **药品搜索**: `https://api.jisuapi.com/medicine/query?appkey=KEY&name=药名`
- **药品详情**: `https://api.jisuapi.com/medicine/detail?appkey=KEY&medicine_id=ID`

### 返回字段
| 字段 | 说明 |
|------|------|
| name | 药品名称 |
| spec | 规格 |
| prescription | 1=处方药, 2=OTC |
| desc | 说明书全文 |
| manufacturer | 生产厂家 |

---

## 安全策略

1. **处方药提示**：检测到处方药时提示"需凭处方购买"
2. **过敏检查**：匹配用户过敏史与药品成分
3. **慢性病禁忌**：检查与慢性病的冲突
4. **相互作用**：多药联用时检查相互作用
5. **兜底提醒**：始终提示"如症状持续请就医"

---

## 脚本说明

```
scripts/
├── search_drug.py         # 智能药品搜索（三步流程+缓存优化）
└── check_interaction.py   # 审方与相互作用检查（缓存优化）
```

### 依赖
- `aiohttp`: 异步HTTP请求
- `database/get_knowledge.py`: 本地RAG检索
- `database/medical_database.py`: 用户档案+药品缓存数据库
- LLM API（`SILICONFLOW_API_KEY`）

---

## 预期效果

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 每次查询API调用 | 3-5次 | 0-1次 |
| 首次查询响应 | 3-5秒 | 3-5秒 |
| 缓存命中响应 | - | <1秒 |
| 日API配额消耗 | ~100次 | ~20次 |
