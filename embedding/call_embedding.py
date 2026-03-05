from embedding.zhipuai_embedding import ZhipuAIEmbeddings

def get_embedding(embedding_name: str, emdedding_key: str=None):
    if embedding_name == 'zhipuai':
        return ZhipuAIEmbeddings(zhipuai_api_key=emdedding_key)
    else:
        raise ValueError(f'embedding {embedding_name} not support')