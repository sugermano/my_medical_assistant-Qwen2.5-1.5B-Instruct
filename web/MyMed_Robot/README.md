# 智医助手 - Web前端

基于Vue3 + Element Plus的AI医疗助手前端应用，提供智能问诊和用药建议服务。

## 📋 项目特性

- ✨ **现代化技术栈**: Vue 3 + Vite + Element Plus
- 🔌 **实时通信**: WebSocket长连接支持
- 💬 **智能对话**: 支持文本消息和结构化报告卡片
- 📊 **用户反馈**: 完整的评价系统
- 🎨 **精美UI**: 响应式设计，支持移动端
- 🔄 **自动重连**: WebSocket断线自动重连机制

## 🚀 快速开始

### 环境要求

- Node.js >= 16.0.0
- npm >= 8.0.0

### 安装依赖

```bash
cd web
npm install
```

### 开发运行

```bash
npm run dev
```

应用将在 `http://localhost:5173` 启动

### 生产构建

```bash
npm run build
```

构建产物将生成在 `dist` 目录

### 预览生产构建

```bash
npm run preview
```

## 📁 项目结构

```
web/
├── src/
│   ├── components/          # Vue组件
│   │   ├── ChatWindow.vue   # 聊天窗口主组件
│   │   ├── MessageItem.vue  # 消息项组件
│   │   ├── ReportCard.vue   # 报告卡片组件
│   │   └── FeedbackDialog.vue # 反馈对话框
│   ├── services/            # 服务层
│   │   └── websocket.js     # WebSocket通信管理
│   ├── styles/              # 全局样式
│   │   └── main.css         # 主样式文件
│   ├── App.vue              # 根组件
│   └── main.js              # 入口文件
├── index.html               # HTML模板
├── vite.config.js           # Vite配置
├── package.json             # 项目配置
└── README.md               # 项目文档
```

## 🔧 配置说明

### 后端API配置

WebSocket服务地址在 `src/services/websocket.js` 中配置：

```javascript
// 默认连接到 ws://localhost:8000
const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/medical/${this.sessionId}`
```

如需修改后端地址，请编辑此文件。

### Vite代理配置

`vite.config.js` 中已配置WebSocket代理：

```javascript
server: {
  proxy: {
    '/ws': {
      target: 'ws://localhost:8000',
      ws: true
    }
  }
}
```

## 💡 核心功能

### 1. WebSocket通信

- 自动连接后端服务
- 断线自动重连（最多5次）
- 消息队列管理
- 连接状态监控

### 2. 消息类型支持

#### 文本消息
```json
{
  "role": "assistant",
  "type": "text",
  "content": "消息内容"
}
```

#### 报告卡片
```json
{
  "role": "assistant",
  "type": "report_card",
  "content": {
    "summary_analysis": "症状分析",
    "medical_warning": "otc_safe",
    "recommended_products": [...],
    "additional_advice": "健康建议"
  }
}
```

### 3. 用户反馈系统

- 5星评分
- 文字评价
- 快捷标签选择

## 🎨 UI组件说明

### ChatWindow
主聊天窗口组件，包含：
- 消息列表显示
- 加载状态提示
- 消息输入框
- 自动滚动

### MessageItem
消息项组件，支持：
- 用户/AI消息区分
- 文本/报告卡片渲染
- 时间戳显示

### ReportCard
报告卡片组件，展示：
- 症状分析
- 医疗警告
- 推荐药品
- 健康建议

### FeedbackDialog
反馈对话框，包含：
- 评分功能
- 评价输入
- 快捷标签

## 🔗 与后端集成

### 启动后端服务

1. 进入项目根目录
2. 安装Python依赖
3. 启动FastAPI服务：

```bash
# 在项目根目录
cd serve
python -m uvicorn service:app --reload --host 0.0.0.0 --port 8000
```

### 完整运行流程

1. **启动后端**（终端1）：
```bash
cd serve
python -m uvicorn service:app --reload --host 0.0.0.0 --port 8000
```

2. **启动前端**（终端2）：
```bash
cd web
npm run dev
```

3. **访问应用**：
打开浏览器访问 `http://localhost:5173`

## 🐛 常见问题

### 1. WebSocket连接失败

**问题**: 前端显示"连接失败"

**解决方案**:
- 确认后端服务已启动在 8000 端口
- 检查防火墙设置
- 查看浏览器控制台的错误信息

### 2. 依赖安装失败

**问题**: `npm install` 报错

**解决方案**:
```bash
# 清除缓存
npm cache clean --force

# 删除node_modules和package-lock.json
rm -rf node_modules package-lock.json

# 重新安装
npm install
```

### 3. 端口被占用

**问题**: 5173端口已被占用

**解决方案**:
修改 `vite.config.js` 中的端口：
```javascript
server: {
  port: 3000  // 改为其他端口
}
```

## 📝 开发注意事项

1. **代码规范**: 遵循Vue 3 Composition API风格
2. **组件设计**: 保持组件单一职责
3. **样式管理**: 使用scoped避免样式污染
4. **性能优化**: 合理使用v-if和v-show
5. **错误处理**: 完善的异常捕获机制

## 🔐 安全考虑

- WebSocket连接使用会话ID隔离
- 输入内容长度限制
- XSS防护（使用v-html时需注意）
- CORS配置正确

## 📈 未来扩展

- [ ] 添加用户登录系统
- [ ] 支持历史会话查看
- [ ] 添加语音输入功能
- [ ] 支持图片上传
- [ ] 多语言国际化
- [ ] 夜间模式切换
- [ ] PWA支持

## 📞 技术支持

如有问题，请查看项目文档或提交Issue。

## 📄 许可证

MIT License
