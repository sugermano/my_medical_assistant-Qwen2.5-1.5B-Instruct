"""
LangChain V1+ 结构化输出模型定义
使用 Pydantic BaseModel 确保 AI 输出的可靠性和类型安全
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

# --- A. 最终输出报告模型 (对应图1) ---
class ProductItem(BaseModel):
    name: str = Field(description="药品通用名+规格")
    image_url: str = Field(description="药品图片链接")
    price: str = Field(description="参考价格")
    dosage: str = Field(description="单次用量")
    
class MedicalReport(BaseModel):
    summary_analysis: str = Field(description="① 总结分析：用户症状与药物的适配性摘要")
    applicability_analysis: str = Field(description="② 适用性分析：详细解释药理作用和对症情况")
    drug_info: str = Field(description="③ 药品信息：功能主治、用法用量、注意事项（Markdown格式列表）")
    medical_warning: str = Field(description="④ 就医提醒：红线症状预警")
    recommended_products: List[ProductItem] = Field(description="⑤ 参考商品列表")

# --- B. 中间决策模型 (控制流程) ---
class ConsultationState(BaseModel):
    status: Literal["continue_asking", "ready_to_report", "emergency"] = Field(
        description="当前状态：continue_asking(信息不足需追问), ready_to_report(生成报告), emergency(紧急情况)"
    )
    missing_info: Optional[str] = Field(
        description="如果状态是 continue_asking，列出还需要询问什么（如：持续时间、过敏史、是否怀孕）"
    )
    next_question: Optional[str] = Field(
        description="如果状态是 continue_asking，生成给用户的追问话术（亲切、专业）"
    )

class UserProfileUpdate(BaseModel):
    """用于从对话中提取用户基本信息"""
    age: Optional[int] = Field(None, description="用户的年龄，如果提到")
    gender: Optional[str] = Field(None, description="用户的性别，如果提到")
    allergies: List[str] = Field(default=[], description="提到的过敏药物或食物")
    chronic_diseases: List[str] = Field(default=[], description="提到的慢性病")
    has_update: bool = Field(False, description="本次对话是否包含上述任何信息的更新")

class FeedbackExtraction(BaseModel):
    """用于提取用户评价"""
    rating: int = Field(description="用户满意度评分 1-5，如果未明确提及但表示感谢/满意则为5")
    comment: str = Field(description="用户的具体评价内容")