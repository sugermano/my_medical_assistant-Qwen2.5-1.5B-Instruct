#!/usr/bin/env python3
"""
MCP 集成安装脚本
自动安装和配置 MCP 依赖
"""

import subprocess
import sys
import os
import json
from pathlib import Path

def print_step(step: str):
    """打印步骤信息"""
    print(f"\n{'='*60}")
    print(f"🔧 {step}")
    print(f"{'='*60}\n")

def check_python_version():
    """检查 Python 版本"""
    print_step("检查 Python 版本")
    version = sys.version_info
    print(f"当前 Python 版本: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ 错误: MCP 需要 Python 3.8 或更高版本")
        sys.exit(1)
    
    print("✅ Python 版本满足要求")

def install_dependencies():
    """安装 MCP 依赖"""
    print_step("安装 MCP 依赖")
    
    dependencies = [
        "mcp",
        "langchain-mcp",
        "aiohttp",
        "pydantic"
    ]
    
    for dep in dependencies:
        print(f"📦 安装 {dep}...")
        try:
            subprocess.check_call([
                sys.executable, 
                "-m", 
                "pip", 
                "install", 
                dep,
                "--upgrade"
            ])
            print(f"✅ {dep} 安装成功")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  {dep} 安装失败: {e}")
            print("尝试继续...")

def create_mcp_directories():
    """创建 MCP 目录结构"""
    print_step("创建目录结构")
    
    directories = [
        "mcp_servers",
        ".mcp"
    ]
    
    for dir_name in directories:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            print(f"✅ 创建目录: {dir_name}")
        else:
            print(f"ℹ️  目录已存在: {dir_name}")

def verify_mcp_files():
    """验证 MCP 文件"""
    print_step("验证文件")
    
    required_files = [
        "mcp_servers/drug_database_server.py",
        ".mcp/config.json"
    ]
    
    all_exist = True
    for file_path in required_files:
        if Path(file_path).exists():
            print(f"✅ 文件存在: {file_path}")
        else:
            print(f"❌ 文件缺失: {file_path}")
            all_exist = False
    
    return all_exist

def update_config():
    """更新 MCP 配置"""
    print_step("更新配置")
    
    config_path = Path(".mcp/config.json")
    project_root = str(Path.cwd().absolute()).replace('\\', '\\\\')
    
    config = {
        "mcpServers": {
            "drug-database": {
                "command": "python",
                "args": ["mcp_servers/drug_database_server.py"],
                "env": {
                    "PYTHONPATH": project_root
                }
            }
        }
    }
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 配置已更新")
    print(f"   项目路径: {project_root}")

def test_mcp_import():
    """测试 MCP 导入"""
    print_step("测试导入")
    
    try:
        import mcp
        print(f"✅ MCP 导入成功 (版本: {getattr(mcp, '__version__', 'unknown')})")
    except ImportError as e:
        print(f"❌ MCP 导入失败: {e}")
        return False
    
    try:
        from src.agents.tools import MCPToolWrapper
        wrapper = MCPToolWrapper()
        if wrapper.mcp_available:
            print("✅ MCP Tool Wrapper 初始化成功")
        else:
            print("⚠️  MCP Tool Wrapper 初始化失败（将使用降级模式）")
    except Exception as e:
        print(f"⚠️  MCP Tool Wrapper 测试异常: {e}")
    
    return True

def print_next_steps():
    """打印后续步骤"""
    print_step("安装完成！")
    
    print("""
🎉 MCP 集成安装成功！

📚 后续步骤：

1. 启动 MCP 服务器（可选）:
   python mcp_servers/drug_database_server.py

2. 启动主服务:
   python main.py

3. 在 Agent 中使用 MCP 工具:
   from src.agents.tools import mcp_search_drug, mcp_check_interaction

4. 查看详细文档:
   打开 MCP_INTEGRATION_GUIDE.md

📖 更多信息：
   - MCP 官方文档: https://modelcontextprotocol.io/
   - 项目文档: MCP_INTEGRATION_GUIDE.md

⚠️  注意事项：
   - MCP 集成目前处于 Beta 阶段
   - 如果 MCP 服务不可用，系统将自动降级到本地模式
   - 建议在测试环境中充分验证后再部署到生产环境

💡 提示：
   使用 'python install_mcp.py --help' 查看更多选项
    """)

def main():
    """主函数"""
    print("""
╔══════════════════════════════════════════════════════════╗
║         MCP 集成自动安装脚本                              ║
║         医疗助手系统 - Model Context Protocol             ║
╚══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # 步骤 1: 检查 Python 版本
        check_python_version()
        
        # 步骤 2: 安装依赖
        install_dependencies()
        
        # 步骤 3: 创建目录
        create_mcp_directories()
        
        # 步骤 4: 验证文件
        files_ok = verify_mcp_files()
        if not files_ok:
            print("\n⚠️  警告: 部分 MCP 文件缺失")
            print("   请确保已从代码库获取完整的 MCP 文件")
        
        # 步骤 5: 更新配置
        update_config()
        
        # 步骤 6: 测试导入
        test_mcp_import()
        
        # 步骤 7: 打印后续步骤
        print_next_steps()
        
    except KeyboardInterrupt:
        print("\n\n❌ 安装被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ 安装过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
