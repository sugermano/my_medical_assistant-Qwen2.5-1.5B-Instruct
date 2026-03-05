<template>
  <div class="sidebar">
    <!-- Logo and User Section -->
    <div class="sidebar-header">
      <div class="logo-section">
        <el-icon :size="32" color="#409EFF"><ChatDotRound /></el-icon>
        <span class="logo-text">智医助手</span>
      </div>
      
      <el-button 
        type="primary" 
        :icon="Plus" 
        class="new-chat-btn"
        @click="$emit('new-chat')"
      >
        开始新对话
      </el-button>
    </div>

    <!-- Session List -->
    <div class="session-list">
      <div 
        v-for="session in sessions" 
        :key="session.session_id"
        :class="['session-item', { active: session.session_id === currentSessionId }]"
        @click="$emit('select-session', session.session_id)"
      >
        <div class="session-content">
          <el-icon class="session-icon"><ChatLineRound /></el-icon>
          <div class="session-info">
            <div class="session-title">{{ session.title }}</div>
            <div class="session-meta">
              {{ formatDate(session.created_at) }} · {{ session.message_count }}条消息
            </div>
          </div>
        </div>
        <el-dropdown trigger="click" @command="(cmd) => handleCommand(cmd, session)">
          <el-icon class="session-more"><MoreFilled /></el-icon>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="rename">
                <el-icon><Edit /></el-icon>
                重命名
              </el-dropdown-item>
              <el-dropdown-item command="delete" divided>
                <el-icon><Delete /></el-icon>
                删除
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </div>

    <!-- User Profile Section -->
    <div class="sidebar-footer">
      <el-dropdown trigger="click" @command="handleUserCommand">
        <div class="user-profile">
          <el-avatar :size="40" :icon="UserFilled" />
          <div class="user-info">
            <div class="user-name">{{ userName }}</div>
            <div class="user-status">在线</div>
          </div>
          <el-icon><ArrowDown /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon>
              个人资料
            </el-dropdown-item>
            <el-dropdown-item command="health">
              <el-icon><Document /></el-icon>
              健康档案
            </el-dropdown-item>
            <el-dropdown-item command="logout" divided>
              <el-icon><SwitchButton /></el-icon>
              退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { 
  ChatDotRound, 
  Plus, 
  ChatLineRound, 
  MoreFilled,
  Edit,
  Delete,
  UserFilled,
  User,
  Document,
  SwitchButton,
  ArrowDown
} from '@element-plus/icons-vue'
import { ElMessageBox, ElMessage } from 'element-plus'

const props = defineProps({
  sessions: {
    type: Array,
    default: () => []
  },
  currentSessionId: {
    type: String,
    default: ''
  },
  userName: {
    type: String,
    default: '用户'
  }
})

const emit = defineEmits(['new-chat', 'select-session', 'delete-session', 'rename-session', 'show-profile', 'logout'])

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  const now = new Date()
  const diff = now - date
  const days = Math.floor(diff / (1000 * 60 * 60 * 24))
  
  if (days === 0) return '今天'
  if (days === 1) return '昨天'
  if (days < 7) return `${days}天前`
  
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

const handleCommand = async (command, session) => {
  if (command === 'delete') {
    try {
      await ElMessageBox.confirm(
        '确定要删除这个对话吗？删除后无法恢复。',
        '确认删除',
        {
          confirmButtonText: '删除',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )
      emit('delete-session', session.session_id)
    } catch {
      // 用户取消删除
    }
  } else if (command === 'rename') {
    try {
      const { value } = await ElMessageBox.prompt('请输入新的对话标题', '重命名', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        inputValue: session.title,
        inputPattern: /.+/,
        inputErrorMessage: '标题不能为空'
      })
      emit('rename-session', session.session_id, value)
    } catch {
      // 用户取消重命名
    }
  }
}

const handleUserCommand = (command) => {
  if (command === 'profile' || command === 'health') {
    emit('show-profile', command)
  } else if (command === 'logout') {
    emit('logout')
  }
}
</script>

<style scoped>
.sidebar {
  width: 280px;
  height: 100vh;
  background: #f8f9fa;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
}

.sidebar-header {
  padding: 20px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.logo-section {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.logo-text {
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.new-chat-btn {
  width: 100%;
  height: 40px;
  border-radius: 8px;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  margin: 2px 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
}

.session-item:hover {
  background: #e5e7eb;
}

.session-item.active {
  background: #dbeafe;
  border-left: 3px solid #409EFF;
}

.session-content {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
  min-width: 0;
}

.session-icon {
  font-size: 20px;
  color: #666;
  flex-shrink: 0;
}

.session-info {
  flex: 1;
  min-width: 0;
}

.session-title {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.session-more {
  font-size: 18px;
  color: #999;
  opacity: 0;
  transition: opacity 0.2s;
  cursor: pointer;
  flex-shrink: 0;
}

.session-item:hover .session-more {
  opacity: 1;
}

.session-more:hover {
  color: #409EFF;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid #e5e7eb;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.user-profile:hover {
  background: #e5e7eb;
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-status {
  font-size: 12px;
  color: #10b981;
  margin-top: 2px;
}

/* 滚动条样式 */
.session-list::-webkit-scrollbar {
  width: 6px;
}

.session-list::-webkit-scrollbar-track {
  background: transparent;
}

.session-list::-webkit-scrollbar-thumb {
  background: #d1d5db;
  border-radius: 3px;
}

.session-list::-webkit-scrollbar-thumb:hover {
  background: #9ca3af;
}
</style>
