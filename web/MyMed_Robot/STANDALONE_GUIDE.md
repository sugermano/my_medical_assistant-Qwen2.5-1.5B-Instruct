# 智医助手 - 独立版本使用指南

## 问题说明

由于遇到 npm 权限问题导致无法安装 vite 和其他依赖，我们提供了一个**完全独立**的HTML版本，无需任何依赖即可使用。

## 解决方案

已创建 `web/standalone.html` 文件，这是一个包含所有功能的单页面应用，特点：

- ✅ 无需安装任何 npm 依赖
- ✅ 无需构建工具（vite、webpack等）
- ✅ 直接在浏览器中打开即可使用
- ✅ 包含完整的UI和功能

## 使用步骤

### 1. 启动后端服务

打开终端，执行以下命令启动FastAPI后端：

```bash
# 方法1: 使用 uvicorn 直接启动
python -m uvicorn serve.service:app --host 0.0.0.0 --port 8000 --reload

# 方法2: 如果上述命令不work，尝试修改路径
cd d:\gitRepository\my_medical_assistant-Qwen2.5-1.5B-Instruct
python -m uvicorn serve.service:app --host 0.0.0.0 --port 8000
```

看到以下输出表示启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
```

### 2. 打开前端页面

有两种方式：

**方式A: 直接双击打开（推荐）**
```
直接双击 web/standalone.html 文件
```

**方式B: 使用浏览器打开**
```
在浏览器地址栏输入：
file:///d:/gitRepository/my_medical_assistant-Qwen2.5-1.5B-Instruct/web/standalone.html
```

### 3. 开始使用

1. 页面打开后会自动连接到后端 WebSocket 服务（localhost:8000）
2. 状态栏显示"已连接"表示成功
3. 在输入框输入症状，例如："我头痛发烧38度"
4. AI会智能问诊并给出用药建议
5. 完成后可以对咨询进行评分

## 功能特性

### 核心功能
- 🤖 智能问诊对话
- 💊 结构化用药建议报告
- ⭐ 用户满意度评分系统
- 📱 响应式设计（支持移动端）

### 界面元素
- 渐变色主题设计
- 消息气泡动画
- 打字指示器
- 药品报告卡片
- 模态反馈对话框

## 故障排查

### 问题1: 页面显示"连接错误"

**原因**: 后端服务未启动或端口不正确

**解决方案**:
1. 检查后端是否在运行
2. 确认后端监听端口为 8000
3. 查看浏览器控制台（F12）是否有错误信息

### 问题2: CORS跨域错误

**原因**: 后端已配置CORS，但可能被浏览器安全策略阻止

**解决方案**:
```python
# 检查 serve/service.py 中是否包含：
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 问题3: WebSocket连接失败

**解决方案**:
1. 确认 URL 为 `ws://localhost:8000` 而非 `wss://`
2. 检查防火墙是否阻止了 8000 端口
3. 尝试使用 127.0.0.1 替代 localhost

## 与Vue版本的对比

| 特性 | standalone.html | Vue版本 |
|-----|----------------|---------|
| 依赖 | 无 | 需要 node_modules |
| 构建 | 不需要 | 需要 vite build |
| 开发体验 | 修改即刷新 | 热更新 |
| 适用场景 | 快速部署、演示 | 大型项目开发 |

## 如果想使用Vue版本

如果解决了权限问题，想使用Vue版本：

```bash
cd web

# 清理缓存
npm cache clean --force

# 使用管理员权限运行 PowerShell
# 右键点击 PowerShell -> "以管理员身份运行"

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 技术架构

### 前端
- 纯 HTML + CSS + JavaScript
- 原生 WebSocket API
- 响应式布局

### 后端
- FastAPI WebSocket 服务
- LangGraph 智能问诊流程
- SQLite 数据库存储

## 下一步

系统已完整实现以下功能：
1. ✅ WebSocket 实时通信
2. ✅ 智能多轮问诊
3. ✅ 结构化药品推荐
4. ✅ 用户反馈收集
5. ✅ 健康档案管理
6. ✅ 长期记忆能力

可以直接用于演示和测试！
