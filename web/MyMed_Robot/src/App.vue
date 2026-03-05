<template>
  <div id="app">
    <!-- 登录界面 -->
    <LoginView 
      v-if="!isAuthenticated" 
      @login-success="handleLoginSuccess"
    />

    <!-- 主应用界面 -->
    <div v-else class="main-layout">
      <!-- 侧边栏 -->
      <Sidebar
        :sessions="sessions"
        :current-session-id="currentSessionId"
        :user-name="userName"
        @new-chat="handleNewChat"
        @select-session="handleSelectSession"
        @delete-session="handleDeleteSession"
        @rename-session="handleRenameSession"
        @show-profile="handleShowProfile"
        @logout="handleLogout"
      />

      <!-- 主聊天区域 -->
      <div class="chat-area">
        <ChatWindow 
          v-if="currentSessionId"
          :key="currentSessionId"
          :messages="messages" 
          :is-loading="isLoading"
          :processing-status="processingStatus"
          :session-id="currentSessionId"
          :session-title="currentSessionTitle"
          @send-message="handleSendMessage"
          @submit-feedback="handleSubmitFeedback"
          @quick-feedback="handleQuickFeedback"
        />
        
        <div v-else class="empty-state">
          <el-empty description="选择或创建一个对话开始咨询">
            <el-button type="primary" @click="handleNewChat">开始新对话</el-button>
          </el-empty>
        </div>
      </div>

      <!-- 用户资料抽屉 -->
      <UserProfile
        v-model="showProfileDrawer"
        :type="profileType"
        @profile-updated="handleProfileUpdated"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import LoginView from './components/LoginView.vue'
import Sidebar from './components/Sidebar.vue'
import ChatWindow from './components/ChatWindow.vue'
import UserProfile from './components/UserProfile.vue'

// ==================== 状态管理 ====================
const isAuthenticated = ref(false)
const userName = ref('')
const userId = ref('')
const token = ref('')

const sessions = ref([])
const currentSessionId = ref('')
const messages = ref([])
const isLoading = ref(false)

const showProfileDrawer = ref(false)
const profileType = ref('profile') // 'profile' or 'health'

// WebSocket相关
let ws = null
const wsConnected = ref(false)

// ==================== API配置 ====================
const API_BASE = 'http://localhost:8000'

// 配置axios默认headers
const setupAxios = () => {
  axios.interceptors.request.use(config => {
    const authToken = localStorage.getItem('token')
    if (authToken) {
      config.headers.Authorization = `Bearer ${authToken}`
    }
    return config
  })

  axios.interceptors.response.use(
    response => response,
    error => {
      if (error.response?.status === 401) {
        handleLogout()
        ElMessage.error('登录已过期，请重新登录')
      }
      return Promise.reject(error)
    }
  )
}

// ==================== 初始化 ====================
onMounted(() => {
  setupAxios()
  checkAuth()
})

onUnmounted(() => {
  disconnectWebSocket()
})

// ==================== 认证相关 ====================
const checkAuth = () => {
  const storedToken = localStorage.getItem('token')
  const storedUserId = localStorage.getItem('user_id')
  const storedUserName = localStorage.getItem('name')

  if (storedToken && storedUserId) {
    token.value = storedToken
    userId.value = storedUserId
    userName.value = storedUserName || '用户'
    isAuthenticated.value = true
    
    // 加载会话列表
    loadSessions()
  }
}

const handleLoginSuccess = (userData) => {
  token.value = userData.token
  userId.value = userData.user_id
  userName.value = userData.name
  isAuthenticated.value = true
  
  ElMessage.success(`欢迎，${userData.name}！`)
  
  // 加载会话列表
  loadSessions()
}

const handleLogout = async () => {
  try {
    await ElMessageBox.confirm('确定要退出登录吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    // 断开WebSocket
    disconnectWebSocket()
    
    // 调用登出API
    try {
      await axios.post(`${API_BASE}/api/auth/logout`)
    } catch (error) {
      console.error('Logout API error:', error)
    }

    // 清除本地存储
    localStorage.removeItem('token')
    localStorage.removeItem('user_id')
    localStorage.removeItem('username')
    localStorage.removeItem('name')

    // 重置状态
    isAuthenticated.value = false
    sessions.value = []
    currentSessionId.value = ''
    messages.value = []

    ElMessage.success('已退出登录')
  } catch {
    // 用户取消
  }
}

// ==================== 会话管理 ====================
const loadSessions = async () => {
  try {
    const response = await axios.get(`${API_BASE}/api/sessions`)
    if (response.data.success) {
      sessions.value = response.data.data
      
      // 如果没有当前会话且有历史会话，选择最新的一个
      if (!currentSessionId.value && sessions.value.length > 0) {
        handleSelectSession(sessions.value[0].session_id)
      }
    }
  } catch (error) {
    console.error('加载会话列表失败:', error)
  }
}

const handleNewChat = async () => {
  try {
    const response = await axios.post(`${API_BASE}/api/sessions`, {
      title: '新对话'
    })
    
    if (response.data.success) {
      const newSession = response.data.data
      sessions.value.unshift(newSession)
      handleSelectSession(newSession.session_id)
      ElMessage.success('已创建新对话')
    }
  } catch (error) {
    ElMessage.error('创建对话失败')
  }
}

const handleSelectSession = async (sessionId) => {
  if (sessionId === currentSessionId.value) return

  // 断开旧的WebSocket连接
  disconnectWebSocket()

  currentSessionId.value = sessionId
  messages.value = []
  
  // 加载历史消息
  await loadSessionMessages(sessionId)
  
  // 连接WebSocket
  connectWebSocket(sessionId)
}

const loadSessionMessages = async (sessionId) => {
  try {
    const response = await axios.get(`${API_BASE}/api/sessions/${sessionId}/messages`)
    if (response.data.success) {
      messages.value = response.data.data.map((msg, index) => {
        const msgType = msg.msg_type || 'text'
        let content = msg.content
        
        // 如果是报告卡片类型，尝试解析JSON
        if (msgType === 'report_card') {
          try {
            content = JSON.parse(msg.content)
          } catch (e) {
            // 如果JSON解析失败，尝试去掉【系统总结】前缀再解析
            const cleanContent = msg.content.replace(/^【系统总结】/, '')
            try {
              content = JSON.parse(cleanContent)
            } catch (e2) {
              // 仍然失败，保持原始文本
              content = msg.content
            }
          }
        }
        
        return {
          id: index,
          role: msg.role,
          type: msgType,
          content: content,
          timestamp: new Date()
        }
      })
    }
  } catch (error) {
    console.error('加载历史消息失败:', error)
  }
}

const handleDeleteSession = async (sessionId) => {
  try {
    await axios.delete(`${API_BASE}/api/sessions/${sessionId}`)
    
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
    
    if (currentSessionId.value === sessionId) {
      disconnectWebSocket()
      currentSessionId.value = ''
      messages.value = []
      
      // 如果还有其他会话，选择第一个
      if (sessions.value.length > 0) {
        handleSelectSession(sessions.value[0].session_id)
      }
    }
    
    ElMessage.success('对话已删除')
  } catch (error) {
    ElMessage.error('删除对话失败')
  }
}

const handleRenameSession = async (sessionId, newTitle) => {
  try {
    // 调用后端API更新标题
    const response = await axios.put(`${API_BASE}/api/sessions/${sessionId}/title`, {
      title: newTitle
    })
    
    if (response.data.success) {
      // 更新本地状态
      const session = sessions.value.find(s => s.session_id === sessionId)
      if (session) {
        session.title = newTitle
      }
      ElMessage.success('重命名成功')
    }
  } catch (error) {
    console.error('重命名失败:', error)
    ElMessage.error('重命名失败，请重试')
  }
}

// 获取当前会话标题
const currentSessionTitle = computed(() => {
  const session = sessions.value.find(s => s.session_id === currentSessionId.value)
  return session?.title || '新对话'
})

// ==================== WebSocket通信 ====================
const connectWebSocket = (sessionId) => {
  const wsUrl = `ws://localhost:8000/ws/medical/${sessionId}`
  
  ws = new WebSocket(wsUrl)
  
  ws.onopen = () => {
    console.log('WebSocket连接成功')
    wsConnected.value = true
  }
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      handleIncomingMessage(data)
    } catch (error) {
      console.error('解析消息失败:', error)
    }
  }
  
  ws.onerror = (error) => {
    console.error('WebSocket错误:', error)
    wsConnected.value = false
  }
  
  ws.onclose = () => {
    console.log('WebSocket连接已关闭')
    wsConnected.value = false
  }
}

const disconnectWebSocket = () => {
  if (ws) {
    ws.close()
    ws = null
    wsConnected.value = false
  }
}

// 流式响应状态
const isStreaming = ref(false)
const streamingMessageId = ref(null)
const processingStatus = ref('') // 🔥 当前处理状态文本

const handleIncomingMessage = (data) => {
  console.log('收到消息:', data)
  
  // 🔥 处理状态消息（各种处理阶段）
  if (data.type === 'status') {
    isLoading.value = true
    isStreaming.value = false
    processingStatus.value = data.content // 更新处理状态
    return
  }
  
  // 🔥 处理流式内容
  if (data.type === 'stream') {
    if (!isStreaming.value) {
      // 创建新的流式消息占位符
      const newMessageId = Date.now() + Math.random()
      messages.value.push({
        id: newMessageId,
        role: 'assistant',
        type: 'text',
        content: data.content,
        streaming: true,
        timestamp: new Date()
      })
      streamingMessageId.value = newMessageId
      isStreaming.value = true
      isLoading.value = false // 关闭loading，显示流式消息
    } else {
      // 追加内容到最后一条消息
      const lastMsg = messages.value.find(m => m.id === streamingMessageId.value)
      if (lastMsg) {
        lastMsg.content += data.content
      }
    }
    return
  }
  
  // 🔥 处理流式丢弃（报告场景：丢弃之前流式发送的JSON文本）
  if (data.type === 'stream_discard') {
    if (isStreaming.value && streamingMessageId.value) {
      // 移除之前创建的流式消息（因为它是JSON文本，不应该显示）
      const msgIndex = messages.value.findIndex(m => m.id === streamingMessageId.value)
      if (msgIndex !== -1) {
        messages.value.splice(msgIndex, 1)
      }
      isStreaming.value = false
      streamingMessageId.value = null
    }
    return
  }
  
  // 🔥 处理流式结束
  if (data.type === 'stream_end') {
    if (isStreaming.value) {
      const lastMsg = messages.value.find(m => m.id === streamingMessageId.value)
      if (lastMsg) {
        lastMsg.streaming = false
      }
      isStreaming.value = false
      streamingMessageId.value = null
    }
    isLoading.value = false
    return
  }
  
  // 处理普通消息（兼容旧格式和报告卡片）
  const { role, type, content } = data
  
  // 如果是报告卡片，需要特殊处理
  if (type === 'report_card') {
    messages.value.push({
      id: Date.now() + Math.random(),
      role,
      type,
      content,
      timestamp: new Date()
    })
    isLoading.value = false
    isStreaming.value = false
    return
  }
  
  // 普通文本消息
  messages.value.push({
    id: Date.now() + Math.random(),
    role,
    type,
    content,
    timestamp: new Date()
  })
  
  if (role === 'assistant') {
    isLoading.value = false
    isStreaming.value = false
  }
}

const handleSendMessage = async (message) => {
  if (!message.trim()) {
    ElMessage.warning('请输入消息内容')
    return
  }
  
  if (!wsConnected.value) {
    ElMessage.error('未连接到服务器')
    return
  }
  
  // 添加用户消息
  messages.value.push({
    id: Date.now(),
    role: 'user',
    type: 'text',
    content: message,
    timestamp: new Date()
  })
  
  // 🔥 如果是第一条用户消息（不包括欢迎语），自动生成标题
  const userMessages = messages.value.filter(m => m.role === 'user')
  if (userMessages.length === 1) {
    // 延迟1秒后生成标题（等待对话有一定内容）
    setTimeout(async () => {
      try {
        const response = await axios.post(
          `${API_BASE}/api/sessions/${currentSessionId.value}/generate-title`
        )
        if (response.data.success) {
          const newTitle = response.data.title
          // 更新本地会话列表中的标题
          const session = sessions.value.find(s => s.session_id === currentSessionId.value)
          if (session) {
            session.title = newTitle
          }
        }
      } catch (error) {
        console.error('自动生成标题失败:', error)
      }
    }, 3000)
  }
  
  // 发送到服务器
  ws.send(JSON.stringify({ message }))
  
  isLoading.value = true
}

const handleSubmitFeedback = async (feedback) => {
  try {
    const token = localStorage.getItem('token')
    const comment = [feedback.comment, ...(feedback.tags || [])].filter(Boolean).join('; ')
    
    // 提交到后端API
    const response = await axios.post(
      `${API_BASE}/api/feedback`,
      {
        session_id: currentSessionId.value,
        rating: feedback.rating,
        comment: comment
      },
      { headers: { Authorization: `Bearer ${token}` } }
    )
    
    if (response.data.success) {
      ElMessage.success('感谢您的反馈！')
    }
  } catch (error) {
    console.error('提交反馈失败:', error)
    ElMessage.error('提交反馈失败，请重试')
  }
}

const handleQuickFeedback = async (feedback) => {
  try {
    const token = localStorage.getItem('token')
    const comment = feedback.tags ? feedback.tags.join('; ') : feedback.comment
    
    // 提交到后端API
    await axios.post(
      `${API_BASE}/api/feedback`,
      {
        session_id: currentSessionId.value,
        rating: feedback.rating,
        comment: comment
      },
      { headers: { Authorization: `Bearer ${token}` } }
    )
  } catch (error) {
    console.error('提交快速反馈失败:', error)
  }
}

// ==================== 用户资料 ====================
const handleShowProfile = (type) => {
  profileType.value = type
  showProfileDrawer.value = true
}

const handleProfileUpdated = () => {
  // 重新加载用户信息
  const storedName = localStorage.getItem('name')
  if (storedName) {
    userName.value = storedName
  }
}
</script>

<style scoped>
#app {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.main-layout {
  display: flex;
  height: 100vh;
  background: #ffffff;
}

.chat-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  background: #f8f9fa;
}
</style>
