from langchain_classic.chains.conversational_retrieval.base import ConversationalRetrievalChain
from qa_chain.get_vectordb import get_vectordb
from qa_chain.model_to_llm import model_to_llm
import re

class My_QA_chain:
    """"
    带历史记录的问答链  
    - model：调用的模型名称
    - temperature：温度系数，控制生成的随机性
    - top_k：返回检索的前k个相似文档
    - chat_history：历史记录，输入一个列表，默认是一个空列表
    - history_len：控制保留的最近 history_len 次对话
    - file_path：建库文件所在路径
    - persist_path：向量数据库持久化路径
    - api_key：星火、百度文心、OpenAI、智谱都需要传递的参数
    - embedding：使用的embedding模型
    - embedding_key：使用的embedding模型的秘钥（智谱或者OpenAI）
    """

    def __init__(
        self,
        model_name: str=None,
        temperature: float=0.6,
        top_k: int=4,
        chat_history: list=[],
        file_path: str=None,
        persist_path: str=None,
        api_key: str=None,
        embedding: str='zhipuai',
        embedding_key: str=None
        ):
        self.model_name = model_name
        self.temperature = temperature
        self.top_k = top_k
        self.chat_history = chat_history
        self.file_path = file_path
        self.persist_path = persist_path
        self.api_key = api_key
        self.embedding = embedding
        self.embedding_key = embedding_key

        self.vectordb = get_vectordb(self.file_path, self.persist_path, self.embedding, self.embedding_key)

    def clear_history(self):
        return self.chat_history.clear()
    
    def change_history_length(self, history_len: int=1):
        """
        保存指定对话轮次的历史记录
        输入参数：
        - history_len ：控制保留的最近 history_len 次对话
        - chat_history：当前的历史对话记录
        输出：返回最近 history_len 次对话
        """
        n = len(self.chat_history)
        return self.chat_history[n - history_len:]
    
    def answer(self, question: str=None, temperature=None, top_k=4):
        """"
        核心方法，调用问答链
        arguments: 
        - question：用户提问
        """
        if len(question) == 0:
            return '', self.chat_history
        
        if temperature == None:
            temperature = self.temperature

        llm = model_to_llm(self.model_name, temperature, api_key=self.api_key)

        retriever = self.vectordb.as_retriever(search_type='similarity', kwargs={'k': top_k}) # 默认similarity，k=4

        qa = ConversationalRetrievalChain.from_llm(llm=llm, retriever=retriever)
        
        # result里有question、chat_history、answer
        result = qa.invoke(input={'question': question, 'chat_history': self.chat_history})

        answer = result['answer']
        answer = re.sub(r"\\n", '<br/>', answer)
        self.chat_history.append((question, answer)) #更新历史记录

        return answer, self.chat_history #返回本次回答和更新后的历史记录
