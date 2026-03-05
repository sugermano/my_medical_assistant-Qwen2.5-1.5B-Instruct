<template>
  <div class="login-container">
    <div class="login-card">
      <div class="login-header">
        <el-icon :size="48" color="#409EFF"><UserFilled /></el-icon>
        <h1>{{ isLogin ? '登录' : '注册' }}</h1>
        <p>智医助手 - 您的AI健康伙伴</p>
      </div>

      <el-form 
        ref="formRef" 
        :model="formData" 
        :rules="rules" 
        label-position="top"
        class="login-form"
      >
        <el-form-item label="用户名" prop="username">
          <el-input 
            v-model="formData.username" 
            placeholder="请输入用户名"
            :prefix-icon="User"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input 
            v-model="formData.password" 
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item v-if="!isLogin" label="姓名" prop="name">
          <el-input 
            v-model="formData.name" 
            placeholder="请输入真实姓名"
            size="large"
          />
        </el-form-item>

        <el-form-item v-if="!isLogin" label="性别" prop="gender">
          <el-radio-group v-model="formData.gender">
            <el-radio label="Male">男</el-radio>
            <el-radio label="Female">女</el-radio>
            <el-radio label="Other">其他</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item v-if="!isLogin" label="出生年份" prop="birth_year">
          <el-input-number 
            v-model="formData.birth_year" 
            :min="1900" 
            :max="new Date().getFullYear()"
            placeholder="请输入出生年份"
            style="width: 100%"
            size="large"
          />
        </el-form-item>

        <el-button 
          type="primary" 
          size="large"
          :loading="loading"
          @click="handleSubmit"
          class="submit-btn"
        >
          {{ isLogin ? '登录' : '注册' }}
        </el-button>

        <div class="switch-mode">
          <el-button link @click="toggleMode">
            {{ isLogin ? '还没有账号？立即注册' : '已有账号？立即登录' }}
          </el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Lock, UserFilled } from '@element-plus/icons-vue'
import axios from 'axios'

const emit = defineEmits(['login-success'])

const isLogin = ref(true)
const loading = ref(false)
const formRef = ref(null)

const formData = reactive({
  username: '',
  password: '',
  name: '',
  gender: 'Unknown',
  birth_year: null
})

const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 20, message: '用户名长度在 3 到 20 个字符', trigger: 'blur' }
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少6个字符', trigger: 'blur' }
  ],
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' }
  ]
}

const toggleMode = () => {
  isLogin.value = !isLogin.value
  // 清空表单
  formRef.value?.resetFields()
}

const handleSubmit = async () => {
  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    loading.value = true

    const endpoint = isLogin.value ? '/api/auth/login' : '/api/auth/register'
    const payload = isLogin.value 
      ? { username: formData.username, password: formData.password }
      : formData

    const response = await axios.post(`http://localhost:8000${endpoint}`, payload)

    if (response.data.success) {
      ElMessage.success(response.data.message)
      
      // 存储token和用户信息
      localStorage.setItem('token', response.data.token)
      localStorage.setItem('user_id', response.data.user_id)
      localStorage.setItem('username', response.data.username)
      localStorage.setItem('name', response.data.name || formData.name)

      // 触发登录成功事件
      emit('login-success', {
        token: response.data.token,
        user_id: response.data.user_id,
        username: response.data.username,
        name: response.data.name || formData.name
      })
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败，请重试')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-container {
  min-height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 20px;
}

.login-card {
  background: white;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
  padding: 40px;
  width: 100%;
  max-width: 450px;
  animation: slideIn 0.3s ease-out;
}

@keyframes slideIn {
  from {
    opacity: 0;
    transform: translateY(-20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.login-header h1 {
  font-size: 28px;
  font-weight: 600;
  margin: 15px 0 8px;
  color: #333;
}

.login-header p {
  color: #666;
  font-size: 14px;
}

.login-form {
  margin-top: 20px;
}

.submit-btn {
  width: 100%;
  margin-top: 10px;
  height: 44px;
  font-size: 16px;
  font-weight: 600;
}

.switch-mode {
  text-align: center;
  margin-top: 16px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #333;
}
</style>
