from __future__ import annotations

import logging
from typing import (
    Any,
    AsyncIterator,
    Dict,
    Iterator,
    List,
    Optional,
    ClassVar,
)

from langchain_classic.callbacks.manager import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun
)
# from langchain_classic.llms.base import LLM
from pydantic import Field, model_validator
from langchain_classic.schema.output import GenerationChunk
from langchain_classic.utils import get_from_dict_or_env
from llm.self_llm import Self_LLM

logger = logging.getLogger(__name__)

class ZhipuAILLM(Self_LLM):
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    # model_config: Dict[str, Any] = {
    #     'ignored_types': [Any]
    # }
    client: Any
    model: str = "glm-4-plus"
    zhipuai_api_key: Optional[str] = None

    incremental: Optional[bool] = True
    streaming: Optional[bool] = False
    request_timeout: Optional[int] = 60

    top_p: Optional[float] = 0.8
    temperature: Optional[float] = 0.95
    request_id: Optional[float] = None

    @model_validator(mode='before')
    def validate_enviroment(cls, values: Dict) -> Dict:
        values["zhipuai_api_key"] = get_from_dict_or_env(
            values,
            "zhipuai_api_key",
            "ZHIPUAI_API_KEY",
        )

        try:
            from zhipuai import ZhipuAI
            print(values["zhipuai_api_key"])
            values['client'] = ZhipuAI(api_key=values["zhipuai_api_key"])
        except ImportError:
            raise ValueError(
                "zhipuai package not found, please install it with "
                "`pip install zhipuai`"
            )
        return values
    
    @property
    def _identifying_params(self) -> Dict[str, Any]:
        return {
            **{"model": self.model},
            **super()._identifying_params,
        }
    
    @property
    def _llm_type(self) -> str:
        return 'zhipuai'
    
    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get the default parameters for calling OpenAI API."""
        normal_params = {
            "stream": self.streaming,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "request_id": self.request_id,
        }

        return {**normal_params, **self.model_kwargs}

    def _convert_prompt_msg_params(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> dict:
        return {
            **{"messages": [{"role": "user", "content": prompt}], "model": self.model},
            **self._default_params,
            **kwargs,
        }
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> str:
        if self.streaming:
            completion = ""
            for chunk in self._stream(prompt, stop, run_manager, **kwargs):
                completion += chunk.text
            return completion
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        response_payload = self.client.chat.completions.create(**params)
        return response_payload.choices[-1].message.content.strip('"').strip(" ")
    
    async def _acall(
        self, 
        prompt: str, 
        stop: Optional[List[str]] = None, 
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None, 
        **kwargs: Any) -> str:
        if self.streaming:
            completion = ""
            async for chunk in self._astream(prompt, stop, run_manager, **kwargs):
                completion += chunk.text
            return completion
        
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        response = await self.client.chat.asyncCompletions.create(**params)
        return response

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        for res in self.client.chat.completions.create(**params):
            chunk = GenerationChunk(text=res)
            yield chunk
            if run_manager:
                run_manager.on_llm_new_token(chunk.text)

    async def _astream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncIterator[GenerationChunk]:
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        for res in self.client.chat.completions.create(**params):
            chunk = GenerationChunk(text=res)
            yield chunk
            if run_manager:
                await run_manager.on_llm_new_token(chunk.text)