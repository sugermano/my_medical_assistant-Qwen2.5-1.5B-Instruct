from llm.zhipuai_llm import ZhipuAILLM

def model_to_llm(model_name: str=None, temperature: float=0.6, api_key: str=None):
    # print(model_name)
    if 'glm' in model_name:
        llm = ZhipuAILLM(model=model_name, zhipuai_api_key=api_key, temperature=temperature)
    else:
        raise ValueError(f'model {model_name} not support')
    return llm