<template>
  <el-dialog
    v-model="dialogVisible"
    title="评价诊疗建议"
    width="500px"
    :before-close="handleClose"
  >
    <div class="feedback-content">
      <!-- 评分 -->
      <div class="feedback-section">
        <div class="section-label">
          <el-icon><Star /></el-icon>
          <span>整体满意度</span>
        </div>
        <el-rate
          v-model="formData.rating"
          :colors="['#F56C6C', '#E6A23C', '#67C23A']"
          show-text
          :texts="['很差', '较差', '一般', '满意', '非常满意']"
          size="large"
        />
      </div>

      <!-- 评价内容 -->
      <div class="feedback-section">
        <div class="section-label">
          <el-icon><Edit /></el-icon>
          <span>详细评价（可选）</span>
        </div>
        <el-input
          v-model="formData.comment"
          type="textarea"
          :rows="4"
          placeholder="请分享您的使用体验或建议..."
          maxlength="500"
          show-word-limit
        />
      </div>

      <!-- 快捷标签 -->
      <div class="feedback-section">
        <div class="section-label">
          <el-icon><CollectionTag /></el-icon>
          <span>快捷评价</span>
        </div>
        <div class="quick-tags">
          <el-tag
            v-for="tag in quickTags"
            :key="tag"
            :type="selectedTags.includes(tag) ? 'primary' : 'info'"
            :effect="selectedTags.includes(tag) ? 'dark' : 'plain'"
            @click="toggleTag(tag)"
            style="cursor: pointer; margin: 4px;"
          >
            {{ tag }}
          </el-tag>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button 
          type="primary" 
          @click="handleSubmit"
          :disabled="!formData.rating"
        >
          提交评价
        </el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { Star, Edit, CollectionTag } from '@element-plus/icons-vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['update:modelValue', 'submit'])

// 对话框显示状态
const dialogVisible = computed({
  get: () => props.modelValue,
  set: (val) => emit('update:modelValue', val)
})

// 表单数据
const formData = ref({
  rating: 0,
  comment: ''
})

// 选中的快捷标签
const selectedTags = ref([])

// 快捷标签选项
const quickTags = [
  '专业准确',
  '回复及时',
  '建议实用',
  '解释清晰',
  '用药安全',
  '需要改进'
]

// 切换标签选择
const toggleTag = (tag) => {
  const index = selectedTags.value.indexOf(tag)
  if (index > -1) {
    selectedTags.value.splice(index, 1)
  } else {
    selectedTags.value.push(tag)
  }
}

// 关闭对话框
const handleClose = () => {
  dialogVisible.value = false
  resetForm()
}

// 提交反馈
const handleSubmit = () => {
  if (!formData.value.rating) {
    return
  }

  const feedback = {
    rating: formData.value.rating,
    comment: formData.value.comment,
    tags: selectedTags.value
  }

  emit('submit', feedback)
  handleClose()
}

// 重置表单
const resetForm = () => {
  formData.value = {
    rating: 0,
    comment: ''
  }
  selectedTags.value = []
}

// 监听对话框打开，重置表单
watch(dialogVisible, (newVal) => {
  if (newVal) {
    resetForm()
  }
})
</script>

<style scoped>
.feedback-content {
  padding: 10px 0;
}

.feedback-section {
  margin-bottom: 24px;
}

.feedback-section:last-child {
  margin-bottom: 0;
}

.section-label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
  color: #606266;
}

.quick-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

/* Element Plus Rate 组件自定义 */
:deep(.el-rate) {
  height: 40px;
  display: flex;
  align-items: center;
}

:deep(.el-rate__text) {
  font-size: 14px;
  color: #606266;
  margin-left: 12px;
}
</style>
