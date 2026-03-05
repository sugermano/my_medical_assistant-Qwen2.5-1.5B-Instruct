<template>
  <el-drawer
    v-model="visible"
    :title="drawerTitle"
    direction="rtl"
    size="500px"
    @close="handleClose"
  >
    <div class="profile-container">
      <el-tabs v-model="activeTab" v-if="type === 'health'">
        <el-tab-pane label="基本信息" name="basic">
          <BasicInfoForm :user-data="profileData" @save="handleSaveBasic" />
        </el-tab-pane>
        <el-tab-pane label="健康档案" name="health">
          <HealthProfileForm :health-data="profileData" @save="handleSaveHealth" />
        </el-tab-pane>
      </el-tabs>
      
      <BasicInfoForm v-else :user-data="profileData" @save="handleSaveBasic" />
    </div>
  </el-drawer>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import BasicInfoForm from './profile/BasicInfoForm.vue'
import HealthProfileForm from './profile/HealthProfileForm.vue'

const props = defineProps({
  modelValue: Boolean,
  type: {
    type: String,
    default: 'profile' // 'profile' or 'health'
  }
})

const emit = defineEmits(['update:modelValue', 'profile-updated'])

const visible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

const activeTab = ref('basic')
const profileData = ref({})

const drawerTitle = computed(() => {
  return props.type === 'health' ? '健康档案管理' : '个人资料'
})

// 加载用户资料
const loadProfile = async () => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.get('http://localhost:8000/api/user/profile', {
      headers: { Authorization: `Bearer ${token}` }
    })
    
    if (response.data.success) {
      profileData.value = response.data.data
    }
  } catch (error) {
    ElMessage.error('加载资料失败')
  }
}

// 保存基本信息
const handleSaveBasic = async (formData) => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.put(
      'http://localhost:8000/api/user/profile',
      formData,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    
    if (response.data.success) {
      ElMessage.success('保存成功')
      emit('profile-updated')
      loadProfile()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

// 保存健康档案
const handleSaveHealth = async (formData) => {
  try {
    const token = localStorage.getItem('token')
    const response = await axios.put(
      'http://localhost:8000/api/user/profile',
      formData,
      { headers: { Authorization: `Bearer ${token}` } }
    )
    
    if (response.data.success) {
      ElMessage.success('健康档案已更新')
      emit('profile-updated')
      loadProfile()
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  }
}

const handleClose = () => {
  visible.value = false
}

// 监听drawer打开时加载数据
watch(visible, (newVal) => {
  if (newVal) {
    loadProfile()
    activeTab.value = props.type === 'health' ? 'health' : 'basic'
  }
})
</script>

<style scoped>
.profile-container {
  padding: 20px 0;
}
</style>
