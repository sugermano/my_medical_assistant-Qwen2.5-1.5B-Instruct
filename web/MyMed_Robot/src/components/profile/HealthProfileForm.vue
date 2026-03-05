<template>
  <div class="health-profile-form">
    <el-alert
      title="重要提示"
      type="info"
      :closable="false"
      show-icon
      class="form-alert"
    >
      完善您的健康档案，AI将根据您的个人情况提供更精准的用药建议。
    </el-alert>

    <el-form
      ref="formRef"
      :model="formData"
      label-position="top"
      class="profile-form"
    >
      <el-form-item label="药物过敏史">
        <el-select
          v-model="formData.allergies"
          multiple
          filterable
          allow-create
          placeholder="请选择或输入过敏药物"
          style="width: 100%"
        >
          <el-option
            v-for="item in commonAllergies"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
        <div class="form-tip">例如：青霉素、磺胺类等</div>
      </el-form-item>

      <el-form-item label="慢性疾病史">
        <el-select
          v-model="formData.chronic_diseases"
          multiple
          filterable
          allow-create
          placeholder="请选择或输入慢性疾病"
          style="width: 100%"
        >
          <el-option
            v-for="item in commonDiseases"
            :key="item"
            :label="item"
            :value="item"
          />
        </el-select>
        <div class="form-tip">例如：高血压、糖尿病、心脏病等</div>
      </el-form-item>

      <div class="current-profile" v-if="hasHealthInfo">
        <el-divider content-position="left">当前健康档案</el-divider>
        
        <div class="info-section" v-if="formData.allergies && formData.allergies.length">
          <div class="info-label">
            <el-icon color="#f56c6c"><Warning /></el-icon>
            药物过敏史
          </div>
          <el-tag
            v-for="item in formData.allergies"
            :key="item"
            type="danger"
            class="info-tag"
          >
            {{ item }}
          </el-tag>
        </div>

        <div class="info-section" v-if="formData.chronic_diseases && formData.chronic_diseases.length">
          <div class="info-label">
            <el-icon color="#e6a23c"><Document /></el-icon>
            慢性疾病史
          </div>
          <el-tag
            v-for="item in formData.chronic_diseases"
            :key="item"
            type="warning"
            class="info-tag"
          >
            {{ item }}
          </el-tag>
        </div>
      </div>

      <el-form-item>
        <el-button type="primary" @click="handleSave" :loading="loading">
          保存健康档案
        </el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { Warning, Document } from '@element-plus/icons-vue'

const props = defineProps({
  healthData: {
    type: Object,
    default: () => ({})
  }
})

const emit = defineEmits(['save'])

const formRef = ref(null)
const loading = ref(false)

const formData = reactive({
  allergies: [],
  chronic_diseases: []
})

// 常见过敏药物
const commonAllergies = [
  '青霉素',
  '头孢类',
  '磺胺类',
  '阿司匹林',
  '链霉素',
  '异烟肼',
  '碘造影剂'
]

// 常见慢性疾病
const commonDiseases = [
  '高血压',
  '糖尿病',
  '冠心病',
  '心律失常',
  '慢性胃炎',
  '慢性肾炎',
  '哮喘',
  '慢阻肺',
  '肝炎',
  '类风湿关节炎',
  '甲状腺疾病'
]

const hasHealthInfo = computed(() => {
  return (formData.allergies && formData.allergies.length > 0) ||
         (formData.chronic_diseases && formData.chronic_diseases.length > 0)
})

// 监听props变化并更新表单
watch(() => props.healthData, (newData) => {
  if (newData) {
    formData.allergies = newData.allergies || []
    formData.chronic_diseases = newData.chronic_diseases || []
  }
}, { immediate: true, deep: true })

const handleSave = async () => {
  loading.value = true
  try {
    emit('save', {
      allergies: formData.allergies,
      chronic_diseases: formData.chronic_diseases
    })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.health-profile-form {
  padding: 0 20px;
}

.form-alert {
  margin-bottom: 24px;
}

.profile-form {
  margin-top: 20px;
}

.form-tip {
  font-size: 12px;
  color: #999;
  margin-top: 8px;
}

.current-profile {
  margin: 24px 0;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.info-section {
  margin-bottom: 16px;
}

.info-section:last-child {
  margin-bottom: 0;
}

.info-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin-bottom: 12px;
}

.info-tag {
  margin-right: 8px;
  margin-bottom: 8px;
}
</style>
