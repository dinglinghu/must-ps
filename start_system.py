#!/usr/bin/env python3
"""
现实预警星座多智能体系统快速启动脚本 v2.0.0
提供多种启动模式的便捷入口
"""

import asyncio
import sys
import os
from pathlib import Path
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))


def print_banner():
    """打印系统横幅"""
    print("=" * 80)
    print("🌟 现实预警星座多智能体滚动任务规划系统 v2.0.0")
    print("   基于Google ADK框架的分布式多智能体协同系统")
    print("=" * 80)


def print_features():
    """打印系统特性"""
    print("系统特性:")
    print("✅ 基于Google ADK框架的真实智能体架构")
    print("✅ Walker星座到ADK智能体一对一映射")
    print("✅ 基于距离优势的导弹目标智能分发")
    print("✅ ADK官方讨论组协作模式")
    print("✅ 滚动任务规划周期管理")
    print("✅ 分层甘特图可视化系统")
    print("✅ 专业UI监控界面")
    print("❌ 严禁使用虚拟智能体")
    print("-" * 80)


async def start_complete_system():
    """启动完整系统"""
    print("🚀 启动完整多智能体系统...")
    
    try:
        from main import main
        success = await main()
        return success
    except Exception as e:
        print(f"❌ 完整系统启动失败: {e}")
        return False


async def start_ui_only():
    """仅启动UI监控界面"""
    print("📱 启动UI监控界面...")
    
    try:
        from demos.demo_ui_monitoring import main
        await main()
        return True
    except Exception as e:
        print(f"❌ UI启动失败: {e}")
        return False


async def start_gantt_demo():
    """启动甘特图演示"""
    print("📊 启动甘特图可视化演示...")
    
    try:
        from demos.demo_gantt_visualization import main
        await main()
        return True
    except Exception as e:
        print(f"❌ 甘特图演示启动失败: {e}")
        return False


def run_tests():
    """运行系统测试"""
    print("🧪 运行系统测试...")
    
    try:
        import subprocess
        result = subprocess.run([
            sys.executable, "-m", "pytest", "tests/", "-v"
        ], cwd=Path(__file__).parent)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 测试运行失败: {e}")
        return False


def check_dependencies():
    """检查系统依赖"""
    print("🔍 检查系统依赖...")
    
    required_packages = [
        'google-adk',
        'asyncio',
        'aiohttp',
        'pandas',
        'numpy',
        'matplotlib',
        'plotly',
        'PyYAML',
        'flask'
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package.replace('-', '_'))
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} (缺失)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n⚠️ 缺失依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    else:
        print("\n✅ 所有依赖包已安装")
        return True


def check_config():
    """检查配置文件"""
    print("📋 检查配置文件...")
    
    config_file = Path("config/config.yaml")
    if config_file.exists():
        print("✅ 配置文件存在")
        return True
    else:
        print("❌ 配置文件不存在: config/config.yaml")
        print("请确保配置文件存在并正确配置")
        return False


def show_help():
    """显示帮助信息"""
    print("使用方法:")
    print("  python start_system.py [模式]")
    print("")
    print("可用模式:")
    print("  complete    - 启动完整多智能体系统 (默认)")
    print("  ui          - 仅启动UI监控界面")
    print("  gantt       - 启动甘特图可视化演示")
    print("  test        - 运行系统测试")
    print("  check       - 检查系统依赖和配置")
    print("  help        - 显示此帮助信息")
    print("")
    print("示例:")
    print("  python start_system.py complete")
    print("  python start_system.py ui")
    print("  python start_system.py check")


async def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="现实预警星座多智能体系统启动器 v2.0.0"
    )
    parser.add_argument(
        'mode',
        nargs='?',
        default='complete',
        choices=['complete', 'ui', 'gantt', 'test', 'check', 'help'],
        help='启动模式'
    )
    
    args = parser.parse_args()
    
    print_banner()
    
    if args.mode == 'help':
        show_help()
        return True
    
    print_features()
    
    # 检查基本环境
    if args.mode != 'check':
        if not check_config():
            return False
    
    try:
        if args.mode == 'complete':
            success = await start_complete_system()
        elif args.mode == 'ui':
            success = await start_ui_only()
        elif args.mode == 'gantt':
            success = await start_gantt_demo()
        elif args.mode == 'test':
            success = run_tests()
        elif args.mode == 'check':
            deps_ok = check_dependencies()
            config_ok = check_config()
            success = deps_ok and config_ok
        else:
            print(f"❌ 未知模式: {args.mode}")
            show_help()
            return False
        
        if success:
            print("\n🎉 操作成功完成")
        else:
            print("\n💥 操作失败")
        
        return success
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断操作")
        return False
    except Exception as e:
        print(f"\n💥 系统异常: {e}")
        return False


if __name__ == "__main__":
    # 确保必要目录存在
    os.makedirs("logs", exist_ok=True)
    os.makedirs("reports", exist_ok=True)
    
    # 运行主函数
    success = asyncio.run(main())
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
