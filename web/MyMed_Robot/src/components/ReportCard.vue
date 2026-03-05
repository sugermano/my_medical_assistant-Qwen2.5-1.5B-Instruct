<template>
  <div class="report-card">
    <!-- 卡片标题 -->
    <div class="report-header">
      <el-icon :size="24" color="#409EFF"><Document /></el-icon>
      <h3>诊疗建议报告</h3>
    </div>

    <!-- 症状分析 -->
    <div v-if="report.summary_analysis" class="report-section">
      <div class="section-title">
        <el-icon color="#67C23A"><Memo /></el-icon>
        <span>症状分析</span>
      </div>
      <div class="section-content">
        <p>{{ report.summary_analysis }}</p>
      </div>
    </div>

    <!-- 医疗警告 -->
    <div v-if="report.medical_warning" class="report-section warning-section">
      <div class="section-title">
        <el-icon color="#F56C6C"><Warning /></el-icon>
        <span>重要提示</span>
      </div>
      <div class="section-content">
        <el-alert
          :title="getWarningText(report.medical_warning)"
          :type="getWarningType(report.medical_warning)"
          :closable="false"
          show-icon
        />
      </div>
    </div>

    <!-- 推荐药品 -->
    <div v-if="report.recommended_products && report.recommended_products.length > 0" class="report-section">
      <div class="section-title">
        <el-icon color="#409EFF"><Tickets /></el-icon>
        <span>推荐药品</span>
      </div>
      <div class="section-content">
        <div 
          v-for="(product, index) in report.recommended_products" 
          :key="index"
          class="product-item"
        >
          <div class="product-header">
            <div class="product-name">
              <el-icon color="#409EFF"><Postcard /></el-icon>
              <strong>{{ product.name || product }}</strong>
            </div>
            <el-tag v-if="product.type" size="small" type="info">
              {{ product.type }}
            </el-tag>
          </div>
          
          <div v-if="product.dosage" class="product-detail">
            <span class="detail-label">用法用量：</span>
            <span>{{ product.dosage }}</span>
          </div>
          
          <div v-if="product.precautions" class="product-detail">
            <span class="detail-label">注意事项：</span>
            <span>{{ product.precautions }}</span>
          </div>
          
          <div v-if="product.description" class="product-detail">
            <span class="detail-label">说明：</span>
            <span>{{ product.description }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 额外建议 -->
    <div v-if="report.additional_advice" class="report-section">
      <div class="section-title">
        <el-icon color="#E6A23C"><ChatLineSquare /></el-icon>
        <span>健康建议</span>
      </div>
      <div class="section-content">
        <p>{{ report.additional_advice }}</p>
      </div>
    </div>

    <!-- 快速反馈 -->
    <div class="report-footer">
      <div class="quick-feedback">
        <span class="feedback-label">这个建议对您有帮助吗？</span>
        <div class="feedback-buttons">
          <el-button 
            type="success" 
            plain 
            size="small"
            @click="handleQuickFeedback('good')"
          >
            <el-icon><Select /></el-icon>
            有帮助
          </el-button>
          <el-button 
            type="warning" 
            plain 
            size="small"
            @click="handleQuickFeedback('bad')"
          >
            <el-icon><CloseBold /></el-icon>
            没帮助
          </el-button>
          <el-button 
            type="primary" 
            plain 
            size="small"
            @click="handleDetailedFeedback"
          >
            <el-icon><Star /></el-icon>
            详细评价
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { defineEmits } from 'vue'
import { 
  Document, 
  Memo, 
  Warning, 
  Tickets, 
  Postcard,
  ChatLineSquare, 
  Star,
  Select,
  CloseBold
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

const props = defineProps({
  report: {
    type: Object,
    required: true
  }
})

const emit = defineEmits(['feedback'])

// 获取警告文本
const getWarningText = (warning) => {
  const warningMap = {
    'otc_safe': '根据您的症状，可以考虑使用非处方药（OTC）。但如果症状持续或加重，请及时就医。',
    'pharmacist_consult': '建议您咨询药师或医生后再用药，以确保用药安全。',
    'hospital_urgent': '您的症状可能需要医生诊断！请尽快前往医院就诊。',
    'default': warning
  }
  return warningMap[warning] || warningMap['default']
}

// 获取警告类型
const getWarningType = (warning) => {
  const typeMap = {
    'otc_safe': 'success',
    'pharmacist_consult': 'warning',
    'hospital_urgent': 'error'
  }
  return typeMap[warning] || 'info'
}

// 快速反馈
const handleQuickFeedback = (type) => {
  const rating = type === 'good' ? 5 : 2
  const comment = type === 'good' ? '建议有帮助' : '建议需要改进'
  
  emit('quick-feedback', { rating, comment, tags: [type === 'good' ? '建议实用' : '需要改进'] })
  
  ElMessage.success(type === 'good' ? '感谢您的反馈！' : '我们会继续改进')
}

// 详细反馈
const handleDetailedFeedback = () => {
  emit('detailed-feedback')
}
</script>

<style scoped>
.report-card {
  background: white;
  border-radius: 12px;
  padding: 24px;
  width: 96%;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  animation: cardSlideUp 0.4s ease-out;
}

.report-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #E4E7ED;
}

.report-header h3 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.report-section {
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 600;
  color: #606266;
}

.section-content {
  padding-left: 28px;
}

.section-content p {
  margin: 0;
  line-height: 1.8;
  color: #606266;
}

/* 警告区域 */
.warning-section {
  margin: 20px 0;
}

/* 药品列表 */
.product-item {
  background: #F5F7FA;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  border-left: 4px solid #409EFF;
}

.product-item:last-child {
  margin-bottom: 0;
}

.product-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.product-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  color: #303133;
}

.product-detail {
  margin-top: 8px;
  font-size: 14px;
  line-height: 1.6;
  color: #606266;
}

.detail-label {
  font-weight: 600;
  color: #909399;
  margin-right: 4px;
}

/* 底部 */
.report-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #E4E7ED;
}

.quick-feedback {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.feedback-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.feedback-buttons {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

@keyframes cardSlideUp {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .report-card {
    padding: 16px;
  }
  
  .product-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
}
</style>
