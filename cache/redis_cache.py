"""
Redis缓存模块 - 用于缓存药品检索结果等
"""
import redis.asyncio as redis
import json
import hashlib
from functools import wraps
from typing import Any, Optional
import os

# Redis连接配置
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# 全局Redis客户端
_redis_client = None
cache_client = None  # 导出给其他模块使用的同步客户端接口

async def get_redis_client():
    """获取Redis客户端（懒加载单例）"""
    global _redis_client, cache_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            # 测试连接
            await _redis_client.ping()
            cache_client = _redis_client  # 导出给其他模块使用
            print("✅ Redis连接成功")
        except Exception as e:
            print(f"⚠️ Redis连接失败: {e}，将使用内存缓存")
            _redis_client = None
            cache_client = None
    return _redis_client

# 内存缓存作为Redis不可用时的降级方案
_memory_cache = {}

def _generate_cache_key(func_name: str, args: tuple, kwargs: dict, key_func=None) -> str:
    """
    生成缓存键
    
    Args:
        func_name: 函数名
        args: 位置参数
        kwargs: 关键字参数
        key_func: 自定义key生成函数，接收args和kwargs，返回字符串
    """
    if key_func:
        # 使用自定义key函数
        try:
            custom_key = key_func(*args, **kwargs)
            return custom_key
        except Exception as e:
            print(f"⚠️ 自定义key函数失败: {e}，使用默认hash")
    
    # 默认：将参数转为字符串并哈希
    key_data = f"{func_name}:{str(args)}:{str(sorted(kwargs.items()))}"
    return hashlib.md5(key_data.encode()).hexdigest()

def cached(ttl: int = 3600, prefix: str = "", key_func=None):
    """
    异步缓存装饰器
    
    Args:
        ttl: 缓存过期时间（秒），默认1小时
        prefix: 缓存键前缀
        key_func: 自定义key生成函数，用于提取关键特征
                 例如：lambda query: extract_symptoms(query)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            cache_key = f"{prefix}:{_generate_cache_key(func.__name__, args, kwargs, key_func)}"
            
            # 尝试从Redis获取
            client = await get_redis_client()
            if client:
                try:
                    cached_result = await client.get(cache_key)
                    if cached_result:
                        print(f"🎯 缓存命中: {func.__name__}")
                        return json.loads(cached_result)
                except Exception as e:
                    print(f"⚠️ Redis读取失败: {e}")
            
            # 检查内存缓存
            if cache_key in _memory_cache:
                print(f"🎯 内存缓存命中: {func.__name__}")
                return _memory_cache[cache_key]
            
            # 未命中，调用原函数
            print(f"💨 缓存未命中，执行: {func.__name__}")
            result = await func(*args, **kwargs)
            
            # 写入缓存
            try:
                if client:
                    # 将结果序列化并存入Redis
                    serialized = json.dumps(result, ensure_ascii=False, default=str)
                    await client.setex(cache_key, ttl, serialized)
                    print(f"💾 已缓存到Redis: {func.__name__} (TTL={ttl}s)")
                else:
                    # 降级到内存缓存
                    _memory_cache[cache_key] = result
                    print(f"💾 已缓存到内存: {func.__name__}")
            except Exception as e:
                print(f"⚠️ 缓存写入失败: {e}")
                # 降级到内存缓存
                _memory_cache[cache_key] = result
            
            return result
        return wrapper
    return decorator

def cached_sync(ttl: int = 3600, prefix: str = ""):
    """
    同步函数的缓存装饰器（基于内存）
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{prefix}:{_generate_cache_key(func.__name__, args, kwargs)}"
            
            if cache_key in _memory_cache:
                print(f"🎯 内存缓存命中: {func.__name__}")
                return _memory_cache[cache_key]
            
            result = func(*args, **kwargs)
            _memory_cache[cache_key] = result
            print(f"💾 已缓存到内存: {func.__name__}")
            return result
        return wrapper
    return decorator

async def clear_cache(pattern: str = "*"):
    """清除缓存"""
    client = await get_redis_client()
    if client:
        try:
            keys = await client.keys(pattern)
            if keys:
                await client.delete(*keys)
                print(f"🗑️ 已清除 {len(keys)} 个缓存键")
        except Exception as e:
            print(f"⚠️ 清除缓存失败: {e}")
    
    # 同时清除内存缓存
    _memory_cache.clear()

async def get_cache_stats():
    """获取缓存统计"""
    client = await get_redis_client()
    stats = {"redis_connected": client is not None, "memory_cache_size": len(_memory_cache)}
    
    if client:
        try:
            info = await client.info("stats")
            stats["redis_hits"] = info.get("keyspace_hits", 0)
            stats["redis_misses"] = info.get("keyspace_misses", 0)
        except:
            pass
    
    return stats

# ==================== 药品检索专用key生成 ====================

def extract_symptom_keywords(query: str) -> str:
    """
    从查询中提取症状关键词，用于生成缓存key
    
    策略：
    1. 移除无关信息（慢性病史、患者信息等括号内容）
    2. 提取核心症状词
    3. 标准化（排序、去重）
    
    示例：
    "头痛发烧 (患者有高血压病史)" -> "发烧_头痛"
    "感冒流鼻涕" -> "感冒_流鼻涕"
    """
    import re
    
    # 1. 移除括号及其内容（通常是病史信息）
    query_clean = re.sub(r'\([^)]*\)', '', query)
    query_clean = re.sub(r'（[^）]*）', '', query_clean)
    
    # 2. 移除常见的描述词，保留核心症状
    noise_words = [
        '有点', '很', '特别', '非常', '一直', '最近', '总是', '经常',
        '我', '他', '她', '患者', '病人', '的', '了', '着', '过',
        '感觉', '觉得', '好像', '可能', '应该'
    ]
    for word in noise_words:
        query_clean = query_clean.replace(word, '')
    
    # 3. 提取症状关键词（常见症状词列表）
    common_symptoms = [
        '头痛', '头晕', '发烧', '发热', '咳嗽', '流鼻涕', '鼻塞', '喉咙痛', '咽痛',
        '腹痛', '肚子痛', '胃痛', '腹泻', '拉肚子', '便秘', '恶心', '呕吐', '想吐',
        '失眠', '睡不着', '疲劳', '乏力', '没力气',
        '感冒', '流感', '发炎', '过敏', '痒', '疼', '痛', '酸', '胀',
        '干咳', '咳痰', '气短', '胸闷', '心慌'
    ]
    
    # 提取匹配的症状词
    found_symptoms = []
    for symptom in common_symptoms:
        if symptom in query_clean:
            found_symptoms.append(symptom)
    
    # 4. 如果没有匹配到已知症状，使用清理后的文本前20个字符
    if not found_symptoms:
        # 移除空格和特殊字符
        key_text = re.sub(r'\s+', '', query_clean)
        key_text = re.sub(r'[^\w]', '', key_text)
        return key_text[:20] if key_text else "unknown"
    
    # 5. 排序并去重，生成标准化key
    symptoms_sorted = sorted(set(found_symptoms))
    return "_".join(symptoms_sorted)

def drug_search_key_func(query: str, context_info: dict = None) -> str:
    """
    药品搜索的key生成函数（基于上下文优化版）
    
    Args:
        query: 当前查询文本
        context_info: 上下文信息，包含：
            - current_query: 当前查询
            - chronic_diseases: 慢性病列表
            - allergies: 过敏史列表  
            - recent_messages: 最近的对话消息列表
    
    Returns:
        标准化的症状关键词key
    """
    if not context_info:
        # 降级到基础提取
        keyword = extract_symptom_keywords(query)
        print(f"🔑 生成缓存key(无上下文): {query[:30]}... -> {keyword}")
        return keyword
    
    # 1. 从当前查询提取症状
    current_symptoms = extract_symptom_keywords(context_info.get("current_query", query))
    
    # 2. 从最近对话中提取症状（合并上下文）
    recent_messages = context_info.get("recent_messages", [])
    all_text = " ".join(recent_messages[-3:])  # 最近3条消息
    context_symptoms = extract_symptom_keywords(all_text)
    
    # 3. 合并症状（去重、排序）
    if current_symptoms and context_symptoms:
        # 合并两个症状key
        combined = set(current_symptoms.split("_")) | set(context_symptoms.split("_"))
        # 过滤掉过长的或无效的
        combined = {s for s in combined if s and len(s) <= 20}
        keyword = "_".join(sorted(combined)[:3])  # 最多保留3个症状词
    else:
        keyword = current_symptoms or context_symptoms or "unknown"
    
    print(f"🔑 生成缓存key(含上下文): {query[:20]}... + 历史消息 -> {keyword}")
    return keyword
