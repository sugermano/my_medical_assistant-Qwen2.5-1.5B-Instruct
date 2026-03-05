# 智医助手前端 - 安装与启动指南

## 🔧 环境准备

### 1. 检查Node.js版本
```bash
node --version  # 应该 >= 16.0.0
npm --version   # 应该 >= 8.0.0
```

### 2. 如果Node.js版本过低，请升级
访问 https://nodejs.org/ 下载最新LTS版本

## 📦 解决npm安装权限问题

### Windows系统（推荐方案）

#### 方案1: 以管理员身份运行
1. 右键点击 `命令提示符` 或 `PowerShell`
2. 选择 "以管理员身份运行"
3. 进入项目目录执行：
```bash
cd web
npm install
```

#### 方案2: 清除npm缓存
```bash
# 清除npm缓存
npm cache clean --force

# 重新安装
cd web
npm install
```

#### 方案3: 使用国内镜像源
```bash
# 设置淘宝镜像
npm config set registry https://registry.npmmirror.com

# 安装依赖
cd web
npm install
```

#### 方案4: 使用yarn代替npm
```bash
# 安装yarn（如果没有）
npm install -g yarn

# 使用yarn安装依赖
cd web
yarn install
```

### Linux/Mac系统

```bash
# 清除缓存
sudo npm cache clean --force

# 安装依赖
cd web
npm install
```

## 🚀 启动项目

### 1. 启动后端服务（必须先启动）

打开第一个终端窗口：

```bash
# Windows
cd serve
python -m uvicorn service:app --reload --host 0.0.0.0 --port 8000

# Linux/Mac
cd serve
python3 -m uvicorn service:app --reload --host 0.0.0.0 --port 8000
```

等待看到：
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 2. 启动前端服务

打开第二个终端窗口：

```bash
cd web
npm run dev
```

或使用yarn：
```bash
cd web
yarn dev
```

等待看到：
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

### 3. 访问应用

打开浏览器访问：`http://localhost:5173`

## 🐛 常见问题排查

### 问题1: 端口被占用

**错误信息**: `Error: listen EADDRINUSE: address already in use :::5173`

**解决方案**:
```bash
# Windows - 查找并结束占用端口的进程
netstat -ano | findstr :5173
taskkill /PID <PID号> /F

# Linux/Mac
lsof -ti:5173 | xargs kill -9
```

或修改端口：编辑 `vite.config.js`
```javascript
server: {
  port: 3000  // 改为其他可用端口
}
```

### 问题2: WebSocket连接失败

**错误信息**: 前端显示"连接失败"或"连接中..."

**排查步骤**:
1. 确认后端服务已启动（检查终端1）
2. 确认后端运行在8000端口
3. 检查防火墙设置
4. 查看浏览器控制台（F12）的错误信息

### 问题3: 模块找不到

**错误信息**: `Cannot find module 'xxx'`

**解决方案**:
```bash
# 删除node_modules和lock文件
cd web
rm -rf node_modules package-lock.json  # Linux/Mac
# 或 Windows:
# rmdir /s node_modules
# del package-lock.json

# 重新安装
npm install
```

### 问题4: Python依赖缺失

**错误信息**: `ModuleNotFoundError: No module named 'fastapi'`

**解决方案**:
```bash
# 安装Python依赖
pip install fastapi uvicorn websockets langchain chromadb
# 或根据项目requirements.txt安装
pip install -r requirements.txt
```

## 📋 完整启动检查清单

- [ ] Node.js版本 >= 16.0.0
- [ ] Python环境已配置
- [ ] 后端依赖已安装（pip install）
- [ ] 前端依赖已安装（npm install）
- [ ] 后端服务已启动（8000端口）
- [ ] 前端服务已启动（5173端口）
- [ ] 浏览器可以访问 http://localhost:5173
- [ ] 页面显示"已连接"状态

## 💡 开发技巧

### 热重载
- 前端代码修改会自动刷新
- 后端代码修改会自动重启（uvicorn --reload）

### 调试
```bash
# 查看详细日志
cd web
npm run dev -- --debug

# 后端日志级别
cd serve
uvicorn service:app --reload --log-level debug
```

### 停止服务
- Windows: `Ctrl + C`
- Linux/Mac: `Ctrl + C`

## 📞 获取帮助

如果以上方法都无法解决问题：

1. 查看浏览器控制台（F12）的错误信息
2. 查看终端的完整错误日志
3. 检查项目README.md文档
4. 提交Issue并附上错误截图和日志

## 🎯 成功标志

当你看到以下界面时，说明启动成功：

- ✅ 浏览器显示"智医助手"界面
- ✅ 右上角显示"已连接"绿色标签
- ✅ 可以在输入框输入消息
- ✅ AI能够正常回复

祝你使用愉快！🎉
