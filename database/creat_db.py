import os
import sys
import re
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import tempfile
from dotenv import load_dotenv, find_dotenv
# from embedding.call_embedding import get_embedding
# from embedding.zhipuai_embedding import ZhipuAIEmbeddings
from embedding.call_embedding import get_embedding
from langchain_community.document_loaders import UnstructuredFileLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_community.document_loaders import UnstructuredExcelLoader
from langchain_core.document_loaders import BaseLoader
# from langchain_chroma import Chroma
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
import pandas as pd
# 首先实现基本配置

DEFAULT_DB_PATH = "./knowledge_db"
DEFAULT_PERSIST_PATH = "./new_vector_db"
ZHIPUAI_API_KEY = "8d93d86009e7476f9e2075d19caba91a.OerFNTg622jrnxJM"

# 处理 Excel：按行切分，保持实体完整性
class MedicalExcelLoader(BaseLoader):
    def __init__(self, file_path):
        self.file_path = file_path

    def load(self):
        """
        读取 Excel，每一行转为一个 Document 对象。
        假设 Excel 中有一列叫 'id' (唯一标识) 和其他业务列。
        """
        df = pd.read_excel(self.file_path)
        df = df.fillna("无")
        docs = []
        
        for index, row in df.iterrows():
            # 1. 提取唯一 ID (假设列名叫 'drug_id'，如果没有就用行号)
            unique_id = str(row.get('序号', f"row_{index}"))
            
            # 2. 构造文本内容 (Rich Semantic Text)
            # 不要直接转 dict，而是拼成自然语言，利于向量检索
            content = (
                f"【药品数据】\n"
                f"ID: {unique_id}\n"
                f"名称: {row.get('药品名称', '')}\n"
                f"功能主治: {row.get('功能主治', '')}\n"
                f"规格: {row.get('规格', '')}\n"
                f"用法用量: {row.get('用法用量', '')}\n"
                f"注意事项: {row.get('注意事项', '')}\n"
                f"成分: {row.get('成分', '')}\n"
                f"性状: {row.get('性状', '')}\n"
                f"疗程: {row.get('疗程', '')}\n"
            )
            
            # 构造 Metadata
            metadata = {
                "source": self.file_path,
                "type": "structured_drug",
                "row_id": unique_id
            }
            
            docs.append(Document(page_content=content, metadata=metadata))
        return docs

def file_loader(file, loaders):
    if isinstance(file, tempfile._TemporaryFileWrapper):
        file = file.name
    if not os.path.isfile(file):
        [file_loader(os.path.join(file, f), loaders) for f in  os.listdir(file)]
        return
    file_type = file.split('.')[-1]
    if file_type == 'pdf':
        loaders.append(PyMuPDFLoader(file))
    elif file_type == 'xlsx':
        loaders.append(MedicalExcelLoader(file))
        # loaders.append(UnstructuredExcelLoader(file))
    elif file_type == 'md':
        pattern = r"不存在|风控"
        match = re.search(pattern, file)
        if not match:
            loaders.append(UnstructuredMarkdownLoader(file))
    elif file_type == 'txt':
        loaders.append(UnstructuredFileLoader(file))
    return

def create_db(files=DEFAULT_DB_PATH, persist_directory=DEFAULT_PERSIST_PATH, embeddings="openai"):
    """
    该函数用于加载 PDF 文件，切分文档，生成文档的嵌入向量，创建向量数据库。

    参数:
    file: 存放文件的路径。
    embeddings: 用于生产 Embedding 的模型

    返回:
    vectordb: 创建的数据库。
    """
    if files == None:
        return "can't load empty file"
    if type(files) != list:
        files = [files]
    loaders = []
    [file_loader(file, loaders) for file in files]
    # docs = []
    # for loader in loaders:
    #     if loader is not None:
    #         docs.extend(loader.load())
    # 切分文档
    # 注意：PDF 需要切分，但 Excel 不需要切分（或者是已经切分好了）
    # 所以不能一股脑全扔进 RecursiveCharacterTextSplitter
    docs_final = []
    for loader in loaders:
        # 检查 Loader 类型
        if isinstance(loader, PyMuPDFLoader):
            # PDF: 先 load 再 split
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=512, chunk_overlap=128)
            split_docs = text_splitter.split_documents(loader.load())
            docs_final.extend(split_docs)
            print(f"PDF 处理完成，切分为 {len(split_docs)} 块")
        if isinstance(loader, MedicalExcelLoader):
            # Excel: 直接 load (因为我们在 Loader 里已经按行切好了)
            excel_docs = loader.load()
            docs_final.extend(excel_docs)
            print(f"Excel 处理完成，共 {len(excel_docs)} 行")

    if embeddings == 'zhipuai':
        embeddings = get_embedding(embedding_name='zhipuai', emdedding_key=ZHIPUAI_API_KEY)
    # 定义持久化路径
    # persist_directory = persist_directory
    # 加载数据库
    vectordb = Chroma.from_documents(
    documents=docs_final,
    embedding=embeddings,
    persist_directory=persist_directory  # 允许我们将persist_directory目录保存到磁盘上
    ) 

    vectordb.persist()
    return vectordb

def load_knowledge_db(path, embeddings):
    vectordb = Chroma(persist_directory=path, embedding_function=embeddings)
    return vectordb

if __name__ == "__main__":
    create_db(embeddings="zhipuai")
