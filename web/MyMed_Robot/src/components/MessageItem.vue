<template>
  <div 
    class="message-item" 
    :class="[`message-${message.role}`, { 'message-report': message.type === 'report_card' }]"
  >
    <!-- AI消息头像 -->
    <div v-if="message.role === 'assistant'" class="message-avatar">
      <el-icon :size="20"><Avatar /></el-icon>
    </div>

    <!-- 消息内容 -->
    <div class="message-content">
      <!-- 普通文本消息 -->
      <div v-if="message.type === 'text'" class="message-bubble">
        <div class="message-text" v-html="formatMessage(message.content)"></div>
        <div class="message-time">{{ formatTime(message.timestamp) }}</div>
      </div>

      <!-- 报告卡片 -->
      <ReportCard 
        v-else-if="message.type === 'report_card'"
        :report="message.content"
        @quick-feedback="handleQuickFeedback"
        @detailed-feedback="handleDetailedFeedback"
      />
    </div>

    <!-- 用户消息头像 -->
    <div v-if="message.role === 'user'" class="message-avatar user-avatar">
      <el-icon :size="20"><User /></el-icon>
    </div>
  </div>
</template>

<script setup>
import { Avatar, User } from '@element-plus/icons-vue'
import ReportCard from './ReportCard.vue'

const props = defineProps({
  message: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['quick-feedback', 'detailed-feedback'])

// 传递快速反馈事件
const handleQuickFeedback = (feedback) => {
  emit('quick-feedback', feedback)
}

// 传递详细反馈事件
const handleDetailedFeedback = () => {
  emit('detailed-feedback')
}

// 格式化消息文本（支持换行等）
const formatMessage = (text) => {
  return text
    .replace(/\n/g, '<br>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
}

// 格式化时间
const formatTime = (timestamp) => {
  if (!timestamp) return ''
  const date = new Date(timestamp)
  const hours = date.getHours().toString().padStart(2, '0')
  const minutes = date.getMinutes().toString().padStart(2, '0')
  return `${hours}:${minutes}`
}
</script>

<style scoped>
.message-item {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
  animation: messageSlideIn 0.3s ease-out;
}

.message-assistant {
  flex-direction: row;
}

.message-user {
  flex-direction: row;
  display: flex;
  justify-content: flex-end;
}

.message-avatar {
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

.user-avatar {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
}

.message-content {
  flex: 1;
  max-width: 70%;
  display: flex;
  flex-direction: column;
}

.message-user .message-content {
  align-items: flex-end;
}

.message-bubble {
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  position: relative;
}

.message-assistant .message-bubble {
  background: white;
  border-top-left-radius: 4px;
}

.message-user .message-bubble {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-top-right-radius: 4px;
}

.message-text {
  font-size: 15px;
  line-height: 1.6;
  word-wrap: break-word;
}

.message-time {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  text-align: right;
}

.message-user .message-time {
  color: rgba(255, 255, 255, 0.8);
}

/* 报告卡片容器 */
.message-report .message-content {
  max-width: 90%;
}

@keyframes messageSlideIn {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .message-content {
    max-width: 85%;
  }
  
  .message-report .message-content {
    max-width: 95%;
  }
}
</style>
