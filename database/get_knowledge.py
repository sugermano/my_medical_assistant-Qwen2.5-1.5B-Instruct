import sys
sys.path.append('D:/gitRepository/my_medical_assistant-Qwen2.5-1.5B-Instruct')
import os
from langchain_community.vectorstores import Chroma
from embedding.zhipuai_embedding import ZhipuAIEmbeddings
from FlagEmbedding import FlagReranker
import jieba
from rank_bm25 import BM25Okapi
from dotenv import load_dotenv
load_dotenv()

# --- 1. 混合检索函数 ---
def hybrid_search(vectordb, sim_docs, query, top_k=20):
    # 注意：BM25 需要分词
    tokenized_corpus = [list(jieba.cut(doc.page_content)) for doc in sim_docs]
    bm25 = BM25Okapi(tokenized_corpus)
    # --- 路一：向量检索 (Dense) ---
    dense_results = vectordb.similarity_search(query, k=top_k)
    
    # --- 路二：BM25 检索 (Sparse) ---
    tokenized_query = list(jieba.cut(query))
    # BM25 返回的是文档内容，我们需要映射回 Document 对象
    # 这里为了演示简单，直接取 top_k
    bm25_docs = bm25.get_top_n(tokenized_query, sim_docs, n=top_k)
    
    # --- 3. 融合 (去重合并) ---
    # 使用字典推导式去重，Key 为文档内容或唯一ID
    combined_results = {doc.page_content: doc for doc in dense_results + bm25_docs}
    unique_docs = list(combined_results.values())
    
    return unique_docs

# --- 2. 重排序 ---
def rerank_results(reranker, query, retrieved_docs, top_k=3):
    """
    使用 BGE-Reranker 精排，并且可以根据规则进行加权
    query: 用户的问题 (str)
    retrieved_docs: 向量检索回来的文档列表 (list of str)
    """
    if not retrieved_docs:
        return []
        
    # 1. 构造配对
    pairs = [[query, doc.page_content] for doc in retrieved_docs]
    
    # 2. 计算原始相关性得分 (Raw Logits)
    # BGE 的分数通常在 -10 (无关) 到 10 (极其相关) 之间
    original_scores = reranker.compute_score(pairs)
    
    # 3. --- 核心修改：应用加权逻辑 ---
    weighted_results = []
    
    for doc, score in zip(retrieved_docs, original_scores):
        final_score = score
        
        # --- 加权规则区域 (根据你的业务定制) ---
        
        # 规则 A: 优先推荐本院/自有药品库的数据 (通过 metadata 判断)
        # 假设你的 Excel 数据 metadata 里有 type="structured_drug"
        if doc.metadata.get("type") == "structured_drug":
            final_score += 3.0  # 强力加分 (相当于极大提升排名)
            # print(final_score)
            
        # 规则 B: 优先推荐包含“禁忌”或“警示”的关键安全信息
        if "禁忌" in doc.page_content or "慎用" in doc.page_content:
            final_score += 1.5  # 中等加分，安全第一
            
        # 规则 C: 降权非医疗来源的闲聊数据 (如果有)
        # if doc.metadata.get("category") == "chitchat":
        #     final_score -= 5.0  # 强力扣分
            
        # -----------------------------------
        
        weighted_results.append((doc, final_score))
    
    # 4. 按“最终分数”从高到低排序
    sorted_docs = sorted(weighted_results, key=lambda x: x[1], reverse=True)
    
    # 5. 返回前 Top_K 个文档内容 (如果你后续流程需要 metadata，这里也可以直接返回 doc 对象)
    return [doc[0] for doc in sorted_docs[:top_k]]

# --- 3. 接入 Reranker---
# 假设你已经有了 reranker 模型
def get_knowledge(query):
    embedding =ZhipuAIEmbeddings(zhipuai_api_key=os.getenv('ZHIPUAI_API_KEY'))
    
    # use_fp16=True 非常重要，能省一半显存
    reranker = FlagReranker('BAAI/bge-reranker-base', use_fp16=True) 
    
    persist_directory = 'D:/gitRepository/my_medical_assistant-Qwen2.5-1.5B-Instruct/new_vector_db'
    vectordb = Chroma(
        persist_directory=persist_directory,
        embedding_function=embedding
    )
    sim_docs = vectordb.similarity_search(query, k=20)

    
    # 1. 混合召回 (可能返回 10~20 条)
    candidates = hybrid_search(vectordb, sim_docs, query, top_k=20)
    
    # 2. Rerank 精排 (BGE-Reranker 会教做人)
    # 将 candidates 和 query 输入 Reranker，取 Top-2
    final_docs = rerank_results(reranker, query, candidates, top_k=3)

    return final_docs
    
# res = get_knowledge('发烧37.5')
# print(res)