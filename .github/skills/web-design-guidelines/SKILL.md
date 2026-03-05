---
name: web-design-guidelines
description: 检查UI代码是否符合Web界面指南规范。当收到「审核我的UI」「检查可访问性」「审计设计」「审核UX」或「对照最佳实践检查我的网站」这类请求时使用。
argument-hint: <file-or-pattern>
tags: ui-code-review, web-interface-guidelines, accessibility-check, design-audit,
  ux-review
tags_cn: UI代码审核, Web界面指南, 可访问性检查, 设计审计, UX审核
---

# Web界面指南

检查文件是否符合Web界面指南规范。

## 工作原理

1. 从下方的源URL获取最新指南
2. 读取指定文件（或提示用户提供文件/匹配模式）
3. 对照获取到的指南中的所有规则进行检查
4. 以简洁的`file:line`格式输出检查结果

## 指南来源

每次审核前获取最新指南：

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

使用WebFetch获取最新规则。获取的内容包含所有规则和输出格式说明。

## 使用方法

当用户提供文件或匹配模式参数时：
1. 从上述源URL获取指南
2. 读取指定文件
3. 应用获取到的指南中的所有规则
4. 按照指南中指定的格式输出检查结果

如果未指定文件，请询问用户要审核哪些文件。