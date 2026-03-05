from langchain_classic.llms.base import LLM
from typing import Dict, Any, Mapping
from pydantic.v1 import Field

'''
自定义 LLM
继承自 langchain.llms.base.LLM
原生接口地址
'''
class Self_LLM(LLM):
    url: str = None
    model_name: str = "glm-4-plus"
    request_timeout: float = None # 访问时延上限
    temperature: float = 0.1
    api_key: str = None
    model_kwargs: Dict[str, Any] = Field(default_factory=dict) # 必备的可选参数

    # 定义一个返回默认参数的方法
    @property
    def _default_params(self) -> Dict[str, Any]:
        # 获取调用默认参数
        normal_params = {
            "temperature": self.temperature,
            "request_timeout": self.request_timeout
        }
        return {**normal_params}
    
    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        # 获取指定参数
        return {**{"model_name": self.model_name}, **self._default_params} 



