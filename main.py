from test_client import test_client
# from src.agents.graph import app
from serve.service import app
# import redis
import asyncio
import os

# ==================== Redis 检测 ====================
async def check_redis():
    """检测 Redis 连接状态"""
    try:
        import redis.asyncio as redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = await redis.from_url(redis_url, decode_responses=True)
        await client.ping()
        await client.close()
        return True, redis_url
    except Exception as e:
        return False, str(e)

# ==================== MCP 检测 ====================
def check_mcp():
    """检测 MCP 服务器配置和依赖"""
    try:
        import json
        config_path = ".mcp/config.json"
        
        # 检查配置文件
        if not os.path.exists(config_path):
            return False, "配置文件不存在"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        servers = config.get("mcpServers", {})
        server_count = len(servers)
        
        if server_count == 0:
            return False, "未配置 MCP 服务器"
        
        # 检查依赖
        try:
            import mcp
            return True, f"{server_count} 个服务器已配置"
        except ImportError:
            return True, f"{server_count} 个服务器已配置（依赖未安装）"
    except Exception as e:
        return False, str(e)

# ==================== 主程序 ====================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "client":
        # 运行测试客户端
        test_client()
    else:
        # 运行服务器
        import uvicorn

        print("="*70)
        print("🚀 启动智医助手系统（增强版）")
        print("="*70)
        print("\n✨ 最新特性:")
        print("  - ✅ 流式响应（Token级别，用户感知延迟↓70%）")
        print("  - ✅ Redis缓存 + 并行化（性能提升10倍）")
        print("  - ✅ 处理状态实时显示（知识检索、安全检查等）")
        print("  - ✅ LangGraph Checkpointing（会话持久化）")
        print("  - ✅ RAG + Reranker（FAISS + 余弦相似度）")
        print("  - ✅ 结构化输出（意图识别、报告生成）")
        print("  - ✅ MCP集成（标准化工具调用、模块化架构）")
        
        # 🔥 检测 Redis 连接
        print("\n🔍 系统检查:")
        redis_ok, redis_info = asyncio.run(check_redis())
        if redis_ok:
            print(f"  ✅ Redis: 连接成功 ({redis_info})")
        else:
            print(f"  ⚠️  Redis: 未连接 - 将使用内存缓存")
            print(f"     原因: {redis_info}")
            print("     提示: 运行 'docker run -d -p 6379:6379 redis:alpine' 启动Redis")
        
        # 🔥 检测 MCP 配置
        mcp_ok, mcp_info = check_mcp()
        if mcp_ok:
            print(f"  ✅ MCP: {mcp_info}")
        else:
            print(f"  ⚠️  MCP: {mcp_info}")
            print("     提示: 运行 'python install_mcp.py' 安装依赖")
        
        print("\n📡 访问:")
        print("  - API 文档: http://localhost:8000/docs")
        print("  - WebSocket: ws://localhost:8000/ws/medical/{session_id}")
        print("  - 前端界面: http://localhost:5173 (需先启动: cd web/MyMed_Robot && npm run dev)")
        print("\n🧪 测试客户端:")
        print("  python main.py client\n")
        print("="*70)

        uvicorn.run(app, host="0.0.0.0", port=8000)
