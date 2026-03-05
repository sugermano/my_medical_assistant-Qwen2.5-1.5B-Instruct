#!/usr/bin/env python3
"""
快速启动脚本 - 用于验证环境和配置
"""

import os
import sys
from pathlib import Path


def check_python_version():
    """检查 Python 版本"""
    print("1. 检查 Python 版本...")
    if sys.version_info < (3, 10):
        print("❌ Python 版本需要 >= 3.10")
        print(f"   当前版本: {sys.version}")
        return False
    print(f"✅ Python 版本: {sys.version.split()[0]}")
    return True


def check_env_file():
    """检查环境变量文件"""
    print("\n2. 检查环境配置...")
    env_path = Path(".env")
    env_example_path = Path(".env.example")

    if not env_path.exists():
        if env_example_path.exists():
            print("⚠️  .env 文件不存在")
            print("   请复制 .env.example 到 .env 并填写配置")
            print("   命令: cp .env.example .env")
            return False
        else:
            print("❌ .env.example 文件也不存在")
            return False

    # 检查关键配置
    with open(env_path, encoding='utf-8') as f:
        content = f.read()
        if "your_siliconflow_api_key_here" in content:
            print("⚠️  请在 .env 文件中配置 SILICONFLOW_API_KEY")
            return False

    print("✅ 环境配置文件存在")
    return True


def check_dependencies():
    """检查依赖包"""
    print("\n3. 检查依赖包...")
    required_packages = [
        "langchain",
        "langgraph",
        "fastapi",
        "uvicorn",
        "faiss",
        "sentence_transformers",
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)

    if missing:
        print("\n缺少以下依赖包，请安装：")
        print("使用 uv:")
        print("  uv pip install -r requirements.txt")
        print("\n或使用 pip:")
        print("  pip install -r requirements.txt")
        return False

    return True


def check_api_key():
    """检查 API Key"""
    print("\n4. 检查 API Key...")
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("SILICONFLOW_API_KEY")
    if not api_key or api_key == "your_siliconflow_api_key_here":
        print("❌ SILICONFLOW_API_KEY 未配置或无效")
        print("   请在 .env 文件中设置正确的 API Key")
        print("   获取地址: https://siliconflow.cn")
        return False

    print(f"✅ API Key 已配置 (前8位: {api_key[:8]}...)")
    return True


def create_directories():
    """创建必要的目录"""
    print("\n5. 创建数据目录...")
    dirs = ["data", "faiss_index"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)
        print(f"✅ {dir_name}/")
    return True


def main():
    """主函数"""
    print("="*70)
    print("🚀 智能客服系统 - 快速启动检查")
    print("="*70)

    checks = [
        check_python_version,
        check_env_file,
        check_dependencies,
        check_api_key,
        create_directories,
    ]

    all_passed = True
    for check in checks:
        if not check():
            all_passed = False

    print("\n" + "="*70)
    if all_passed:
        print("✅ 所有检查通过！")
        print("\n启动服务器:")
        print("  python project10_customer_service_system_v2.py")
        print("\n或使用 uv:")
        print("  uv run python project10_customer_service_system_v2.py")
        print("\n启动测试客户端:")
        print("  python project10_customer_service_system_v2.py client")
        print("="*70)
        return 0
    else:
        print("❌ 存在问题，请先解决上述错误")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
