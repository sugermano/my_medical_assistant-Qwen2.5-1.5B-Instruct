#!/usr/bin/env python3
"""
MCP 集成测试脚本
测试 MCP 服务器和工具是否正常工作
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

async def test_mcp_wrapper():
    """测试 MCP Wrapper"""
    print("\n" + "="*60)
    print("🧪 测试 1: MCP Tool Wrapper 初始化")
    print("="*60)
    
    try:
        from src.agents.tools import MCPToolWrapper
        wrapper = MCPToolWrapper()
        
        if wrapper.mcp_available:
            print("✅ MCP 可用")
            print(f"   MCP 版本: {wrapper.mcp_version}")
        else:
            print("⚠️  MCP 不可用，使用降级模式")
            print(f"   原因: {wrapper.mcp_error}")
        
        return wrapper.mcp_available
    except Exception as e:
        print(f"❌ MCP Wrapper 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_search_drug():
    """测试药品搜索工具"""
    print("\n" + "="*60)
    print("🧪 测试 2: 药品搜索工具 (mcp_search_drug)")
    print("="*60)
    
    try:
        from src.agents.tools import mcp_search_drug
        
        # 测试查询
        test_query = "感冒发烧"
        print(f"📝 测试查询: {test_query}")
        
        result = await mcp_search_drug.ainvoke({
            "query": test_query,
            "top_k": 3
        })
        
        print(f"✅ 搜索成功")
        print(f"   结果预览: {str(result)[:200]}...")
        return True
        
    except Exception as e:
        print(f"❌ 药品搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_check_interaction():
    """测试药物相互作用检查工具"""
    print("\n" + "="*60)
    print("🧪 测试 3: 药物相互作用检查 (mcp_check_interaction)")
    print("="*60)
    
    try:
        from src.agents.tools import mcp_check_interaction
        
        # 测试查询
        test_drugs = ["阿司匹林", "布洛芬"]
        test_patient_info = "有胃溃疡病史"
        
        print(f"📝 测试药品: {test_drugs}")
        print(f"📝 患者信息: {test_patient_info}")
        
        result = await mcp_check_interaction.ainvoke({
            "drugs": test_drugs,
            "patient_info": test_patient_info
        })
        
        print(f"✅ 检查成功")
        print(f"   结果预览: {str(result)[:200]}...")
        return True
        
    except Exception as e:
        print(f"❌ 药物相互作用检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_local_fallback():
    """测试本地降级功能"""
    print("\n" + "="*60)
    print("🧪 测试 4: 本地降级功能")
    print("="*60)
    
    try:
        from src.agents.tools import search_drug_database
        
        # 测试本地搜索
        test_query = "头痛"
        print(f"📝 测试本地搜索: {test_query}")
        
        result = search_drug_database.invoke(test_query)
        
        print(f"✅ 本地搜索成功")
        print(f"   结果预览: {str(result)[:200]}...")
        return True
        
    except Exception as e:
        print(f"❌ 本地降级测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_performance():
    """性能测试"""
    print("\n" + "="*60)
    print("🧪 测试 5: 性能对比")
    print("="*60)
    
    import time
    
    try:
        from src.agents.tools import mcp_search_drug, search_drug_database
        
        test_query = "感冒"
        
        # 测试 MCP 调用
        start = time.time()
        try:
            await mcp_search_drug.ainvoke({"query": test_query, "top_k": 3})
            mcp_time = time.time() - start
            print(f"⏱️  MCP 调用耗时: {mcp_time:.3f}s")
        except Exception as e:
            print(f"⚠️  MCP 调用失败: {e}")
            mcp_time = None
        
        # 测试本地调用
        start = time.time()
        search_drug_database.invoke(test_query)
        local_time = time.time() - start
        print(f"⏱️  本地调用耗时: {local_time:.3f}s")
        
        if mcp_time:
            overhead = ((mcp_time - local_time) / local_time) * 100
            print(f"📊 MCP 开销: {overhead:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False

async def test_config():
    """测试配置文件"""
    print("\n" + "="*60)
    print("🧪 测试 6: MCP 配置")
    print("="*60)
    
    try:
        import json
        config_path = Path(".mcp/config.json")
        
        if not config_path.exists():
            print("❌ 配置文件不存在: .mcp/config.json")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print("✅ 配置文件存在")
        print(f"   配置的服务器数: {len(config.get('mcpServers', {}))}")
        
        for server_name, server_config in config.get('mcpServers', {}).items():
            print(f"   - {server_name}")
            print(f"     命令: {server_config.get('command')}")
            print(f"     参数: {server_config.get('args')}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置测试失败: {e}")
        return False

def print_summary(results: dict):
    """打印测试摘要"""
    print("\n" + "="*60)
    print("📊 测试摘要")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    print(f"\n总测试数: {total}")
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"成功率: {(passed/total)*100:.1f}%\n")
    
    # 详细结果
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("\n" + "="*60)
    
    if failed == 0:
        print("🎉 所有测试通过！MCP 集成工作正常。")
    else:
        print("⚠️  部分测试失败，请检查日志。")
        print("💡 提示: 如果 MCP 不可用，系统会自动降级到本地模式。")
    print("="*60)

async def main():
    """主测试函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║              MCP 集成测试套件                             ║
║              医疗助手系统 - 自动化测试                     ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    results = {}
    
    # 运行所有测试
    results["MCP Wrapper 初始化"] = await test_mcp_wrapper()
    results["药品搜索工具"] = await test_search_drug()
    results["药物相互作用检查"] = await test_check_interaction()
    results["本地降级功能"] = await test_local_fallback()
    results["性能对比"] = await test_performance()
    results["配置文件"] = await test_config()
    
    # 打印摘要
    print_summary(results)
    
    # 返回退出码
    all_passed = all(results.values())
    sys.exit(0 if all_passed else 1)

if __name__ == "__main__":
    asyncio.run(main())
