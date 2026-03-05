from embedding.call_embedding import get_embedding
from database.creat_db import create_db, load_knowledge_db
import os
def get_vectordb(
    file_path: str=None,
    persist_path: str=None,
    embedding_name: str='zhipuai',
    embedding_key: str=None):

    embedding = get_embedding(embedding_name, emdedding_key=embedding_key)
    if os.path.exists(persist_path):
        contents = os.listdir(persist_path)
        if len(contents) == 0:
            vectordb = create_db(file_path, persist_path, embedding)
            vectordb = load_knowledge_db(file_path, embedding)
        else:
            vectordb = load_knowledge_db(file_path, embedding)
    else:
        vectordb = create_db(file_path, persist_path, embedding)
        vectordb = load_knowledge_db(file_path, embedding)

    return vectordb