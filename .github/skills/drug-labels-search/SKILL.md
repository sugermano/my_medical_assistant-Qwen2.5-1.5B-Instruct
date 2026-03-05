---
name: drug-labels-search
description: 使用自然语言查询搜索FDA药品标签。通过Valyu获取官方药品信息、适应症和安全数据。
keywords:
- fda-drug-labels
- drug-safety
- indications
- pharmacology
- drug-interactions
- semantic-search
license: MIT
tags: fda-drug-labels, natural-language-search, valyu-api, semantic-search, drug-information-retrieval
tags_cn: FDA药品标签, 自然语言查询, Valyu API, 语义搜索, 药品信息检索
---

# FDA药品标签搜索

使用Valyu的语义搜索API，通过自然语言查询搜索完整的FDA药品标签数据库，包括处方信息、警告和官方标签内容。

## 该工具的强大之处

- **无需解析API参数**：直接传入自然语言查询即可，无需构建复杂的搜索参数
- **语义搜索**：理解查询的含义，而非仅进行关键词匹配
- **全文访问**：返回完整的药品标签信息，包括适应症、剂量、警告和不良反应
- **图片链接**：在可用时提供标签图片
- **全面覆盖**：可访问所有FDA药品标签数据

## 要求

1. Node.js 18+（使用内置的fetch）
2. 从https://platform.valyu.ai获取Valyu API密钥（赠送10美元免费额度）

## 重要提示：脚本路径解析

本文档中的`scripts/search`命令是相对于该工具的安装目录的。

在运行任何命令之前，请使用以下命令定位脚本：

```bash
DRUG_LABELS_SCRIPT=$(find ~/.claude/plugins/cache -name "search" -path "*/drug-labels-search/*/scripts/*" -type f 2>/dev/null | head -1)
```

然后使用完整路径执行所有命令：
```bash
$DRUG_LABELS_SCRIPT "ibuprofen warnings" 15
```

## API密钥设置流程

当你运行搜索并收到`"setup_required": true`时，请按照以下流程操作：

1. **向用户索要API密钥**：
   "要搜索FDA药品标签，我需要你的Valyu API密钥。可前往https://platform.valyu.ai免费获取（含10美元额度）"

2. **用户提供密钥后，运行以下命令**：
   ```bash
   scripts/search setup <api-key>
   ```

3. **重新尝试原搜索**。

## 使用场景

- 获取官方FDA药品信息和适应症
- 查询禁忌症和警告
- 获取剂量和给药指导
- 临床药理学数据
- 药物相互作用信息
- 不良反应和安全监测
## 输出格式

```json
{
  "success": true,
  "type": "drug_labels_search",
  "query": "ibuprofen warnings",
  "result_count": 10,
  "results": [
    {
      "title": "Drug Label Title",
      "url": "https://fda.gov/...",
      "content": "Label content, warnings, dosing...",
      "source": "drug-labels",
      "relevance_score": 0.95,
      "images": ["https://example.com/label.jpg"]
    }
  ],
  "cost": 0.025
}
```

## 结果处理

### 使用jq工具

```bash
# 获取药品名称
scripts/search "query" 10 | jq -r '.results[].title'

# 获取URL
scripts/search "query" 10 | jq -r '.results[].url'

# 提取完整内容
scripts/search "query" 10 | jq -r '.results[].content'
```

## 常见使用案例

### 安全信息查询

```bash
# 查找安全数据
scripts/search "anticoagulant bleeding risk warnings" 50
```

### 处方指导

```bash
# 搜索剂量信息
scripts/search "pediatric dosing guidelines for antibiotics" 20
```

### 药物相互作用

```bash
# 查找相互作用数据
scripts/search "CYP450 drug interaction warnings" 15
```

### 监管信息

```bash
# 搜索审批数据
scripts/search "accelerated approval indications oncology" 25
```


## 错误处理

所有命令都会返回包含`success`字段的JSON：

```json
{
  "success": false,
  "error": "Error message"
}
```

退出码：
- `0` - 成功
- `1` - 错误（查看JSON获取详情）

## API端点

- 基础URL: `https://api.valyu.ai/v1`
- 端点: `/search`
- 认证方式: X-API-Key请求头

## 架构

```
scripts/
├── search          # Bash包装脚本
└── search.mjs      # Node.js命令行工具
```

使用Node.js内置的`fetch()`进行直接API调用，无外部依赖。

## 集成到你的项目中

如果你正在构建AI项目，并希望将药品标签搜索直接集成到应用中，请使用Valyu SDK：

### Python集成

```python
from valyu import Valyu

client = Valyu(api_key="your-api-key")

response = client.search(
    query="your search query here",
    included_sources=["valyu/valyu-drug-labels"],
    max_results=20
)

for result in response["results"]:
    print(f"Title: {result['title']}")
    print(f"URL: {result['url']}")
    print(f"Content: {result['content'][:500]}...")
```

### TypeScript集成

```typescript
import { Valyu } from "valyu-js";

const client = new Valyu("your-api-key");

const response = await client.search({
  query: "your search query here",
  includedSources: ["valyu/valyu-drug-labels"],
  maxResults: 20
});

response.results.forEach((result) => {
  console.log(`Title: ${result.title}`);
  console.log(`URL: ${result.url}`);
  console.log(`Content: ${result.content.substring(0, 500)}...`);
});
```

查看[Valyu文档](https://docs.valyu.ai)获取完整的集成示例和SDK参考。