<template>
  <el-form
    ref="formRef"
    :model="formData"
    :rules="rules"
    label-position="top"
    class="profile-form"
  >
    <el-form-item label="姓名" prop="name">
      <el-input v-model="formData.name" placeholder="请输入姓名" />
    </el-form-item>

    <el-form-item label="性别" prop="gender">
      <el-radio-group v-model="formData.gender">
        <el-radio label="Male">男</el-radio>
        <el-radio label="Female">女</el-radio>
        <el-radio label="Other">其他</el-radio>
      </el-radio-group>
    </el-form-item>

    <el-form-item label="出生年份" prop="birth_year">
      <el-input-number 
        v-model="formData.birth_year" 
        :min="1900" 
        :max="new Date().getFullYear()"
        style="width: 100%"
      />
    </el-form-item>

    <el-form-item label="联系电话" prop="phone">
      <el-input v-model="formData.phone" placeholder="请输入联系电话" />
    </el-form-item>

    <el-form-item>
      <el-button type="primary" @click="handleSave" :loading="loading">
        保存更改
      </el-button>
    </el-form-item>
  </el-form>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'

const props = defineProps({
  userData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['save'])

const formRef = ref(null)
const loading = ref(false)

const formData = reactive({
  name: '',
  gender: 'Unknown',
  birth_year: null,
  phone: ''
})

const rules = {
  name: [
    { required: true, message: '请输入姓名', trigger: 'blur' }
  ]
}

// 监听props变化并更新表单
watch(() => props.userData, (newData) => {
  if (newData) {
    formData.name = newData.name || ''
    formData.gender = newData.gender || 'Unknown'
    formData.birth_year = newData.birth_year || null
    formData.phone = newData.phone || ''
  }
}, { immediate: true, deep: true })

const handleSave = async () => {
  try {
    const valid = await formRef.value.validate()
    if (!valid) return

    loading.value = true
    emit('save', { ...formData })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.profile-form {
  padding: 0 20px;
}
</style>
