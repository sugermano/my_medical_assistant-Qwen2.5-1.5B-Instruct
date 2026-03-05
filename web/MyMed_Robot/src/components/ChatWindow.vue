<template>
  <div class="chat-window">
    <!-- 🔥 顶栏 - 显示当前对话标题 -->
    <div class="chat-header">
      <div class="header-title">
        <el-icon :size="20"><ChatLineSquare /></el-icon>
        <span>{{ sessionTitle }}</span>
      </div>
    </div>

    <!-- 消息列表区域 -->
    <div class="messages-container" ref="messagesContainer">
      <div class="messages-list">
        <MessageItem
          v-for="message in messages"
          :key="message.id"
          :message="message"
          @quick-feedback="handleQuickFeedback"
          @detailed-feedback="handleDetailedFeedback"
        />
        
        <!-- 加载中提示 -->
        <div v-if="isLoading" class="loading-message">
          <div class="loading-avatar">
            <el-icon class="is-loading" :size="20"><Loading /></el-icon>
          </div>
          <div class="loading-content">
            <div class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <!-- 🔥 动态显示处理阶段状态 -->
            <span class="loading-text">{{ processingStatus || 'AI正在思考...' }}</span>
            <!-- 🔥 进度条显示 -->
            <el-progress 
              :percentage="processingProgress" 
              :status="processingProgress === 100 ? 'success' : undefined"
              :stroke-width="6"
              :show-text="false"
            />
          </div>
        </div>

        <!-- 空状态 -->
        <div v-if="messages.length === 0 && !isLoading" class="empty-state">
          <el-icon :size="80" color="#C0C4CC"><ChatLineSquare /></el-icon>
          <p>开始您的健康咨询</p>
          <p class="empty-hint">请描述您的症状，我会为您提供专业建议</p>
        </div>
      </div>
    </div>

    <!-- 浮动评价按钮 -->
    <div v-if="hasReportMessages" class="floating-feedback-btn">
      <el-button 
        type="primary" 
        circle 
        size="large"
        @click="showFeedbackDialog = true"
      >
        <el-icon :size="24"><Star /></el-icon>
      </el-button>
      <div class="feedback-tooltip">评价此次咨询</div>
    </div>

    <!-- 输入区域 -->
    <div class="input-container">
      <el-input
        v-model="inputMessage"
        type="textarea"
        :rows="3"
        placeholder="请描述您的症状（例如：头痛、发烧等）..."
        :disabled="isLoading"
        @keydown.ctrl.enter="handleSend"
        resize="none"
      />
      <div class="input-actions">
        <div class="input-hint">
          <el-icon><InfoFilled /></el-icon>
          <span>Ctrl + Enter 发送</span>
        </div>
        <el-button 
          type="primary" 
          :loading="isLoading"
          :disabled="!inputMessage.trim()"
          @click="handleSend"
        >
          <el-icon v-if="!isLoading"><Promotion /></el-icon>
          发送
        </el-button>
      </div>
    </div>

    <!-- 反馈对话框 -->
    <FeedbackDialog
      v-model="showFeedbackDialog"
      @submit="handleFeedbackSubmit"
    />
  </div>
</template>

<script setup>
import { ref, nextTick, watch, computed } from 'vue'
import { Loading, ChatLineSquare, InfoFilled, Promotion, Star } from '@element-plus/icons-vue'
import MessageItem from './MessageItem.vue'
import FeedbackDialog from './FeedbackDialog.vue'

const props = defineProps({
  messages: {
    type: Array,
    default: () => []
  },
  isLoading: {
    type: Boolean,
    default: false
  },
  processingStatus: {
    type: String,
    default: ''
  },
  sessionTitle: {
    type: String,
    default: '新对话'
  }
})

const emit = defineEmits(['send-message', 'submit-feedback', 'quick-feedback'])

// 状态
const inputMessage = ref('')
const messagesContainer = ref(null)
const showFeedbackDialog = ref(false)

// 🔥 根据处理状态计算进度
const processingProgress = computed(() => {
  const status = props.processingStatus.toLowerCase()
  if (!status || status.includes('分析您的问题')) return 10
  if (status.includes('检索知识库')) return 30
  if (status.includes('分析药物适用性')) return 50
  if (status.includes('检查用药安全')) return 70
  if (status.includes('生成用药建议报告') || status.includes('生成报告')) return 90
  return 10
})

// 检查是否有报告消息
const hasReportMessages = computed(() => {
  return props.messages.some(msg => msg.type === 'report_card')
})

// 发送消息
const handleSend = () => {
  if (inputMessage.value.trim() && !props.isLoading) {
    emit('send-message', inputMessage.value.trim())
    inputMessage.value = ''
  }
}

// 自动滚动到底部
const scrollToBottom = () => {
  nextTick(() => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  })
}

// 监听消息变化，自动滚动
watch(() => props.messages.length, () => {
  scrollToBottom()
})

watch(() => props.isLoading, () => {
  scrollToBottom()
})

// 处理反馈提交
const handleFeedbackSubmit = (feedback) => {
  emit('submit-feedback', feedback)
}

// 处理快速反馈（从ReportCard触发）
const handleQuickFeedback = (feedback) => {
  emit('quick-feedback', feedback)
}

// 处理详细反馈（从ReportCard触发）
const handleDetailedFeedback = () => {
  showFeedbackDialog.value = true
}
</script>

<style scoped>
.chat-window {
  width: 100%;
  height: 100%;
  background: white;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 🔥 顶栏样式 */
.chat-header {
  padding: 16px 24px;
  background: white;
  border-bottom: 1px solid #EBEEF5;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-title .el-icon {
  color: #409EFF;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

.messages-list {
  max-width: 75%;
  margin: 0 auto;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 80px 20px;
  color: #909399;
}

.empty-state p {
  margin: 20px 0 10px;
  font-size: 18px;
  font-weight: 500;
}

.empty-hint {
  font-size: 14px;
  color: #C0C4CC;
}

/* 加载消息 */
.loading-message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: fadeIn 0.3s;
}

.loading-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.loading-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 12px 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #409EFF;
  animation: typing 1.4s infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

.loading-text {
  font-size: 12px;
  color: #909399;
  padding-left: 4px;
}

@keyframes typing {
  0%, 60%, 100% {
    transform: translateY(0);
    opacity: 0.5;
  }
  30% {
    transform: translateY(-10px);
    opacity: 1;
  }
}

/* 输入区域 */
.input-container {
  padding: 20px;
  background: white;
  border-top: 1px solid #EBEEF5;
}

.input-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
}

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #909399;
}

/* 滚动条样式 */
.messages-container::-webkit-scrollbar {
  width: 6px;
}

.messages-container::-webkit-scrollbar-thumb {
  background: #DCDFE6;
  border-radius: 3px;
}

.messages-container::-webkit-scrollbar-thumb:hover {
  background: #C0C4CC;
}

/* 浮动反馈按钮 */
.floating-feedback-btn {
  position: fixed;
  bottom: 150px;
  right: 40px;
  z-index: 100;
  animation: float 3s ease-in-out infinite;
}

.floating-feedback-btn .el-button {
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4);
}

.floating-feedback-btn:hover .feedback-tooltip {
  opacity: 1;
  visibility: visible;
}

.feedback-tooltip {
  position: absolute;
  right: 70px;
  top: 50%;
  transform: translateY(-50%);
  background: #303133;
  color: white;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 13px;
  white-space: nowrap;
  opacity: 0;
  visibility: hidden;
  transition: all 0.3s;
}

.feedback-tooltip::after {
  content: '';
  position: absolute;
  right: -6px;
  top: 50%;
  transform: translateY(-50%);
  border: 6px solid transparent;
  border-left-color: #303133;
}

@keyframes float {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
