#!/usr/bin/env python3
"""
ADK开发UI启动脚本
基于ADK官方设计的多智能体系统管理界面
"""

import sys
import logging
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 全局变量，用于避免重复初始化
_multi_agent_system = None

def check_dependencies():
    """检查依赖项"""
    missing_deps = []
    
    try:
        import flask
    except ImportError:
        missing_deps.append("flask")
    
    try:
        import flask_socketio
    except ImportError:
        missing_deps.append("flask-socketio")
    
    if missing_deps:
        print("❌ 缺少以下依赖项:")
        for dep in missing_deps:
            print(f"   - {dep}")
        print("\n请运行以下命令安装:")
        print(f"pip install {' '.join(missing_deps)}")
        return False
    
    return True

def get_or_create_multi_agent_system():
    """🔧 修复：UI启动时不自动初始化多智能体系统"""
    global _multi_agent_system

    # 检查是否是Flask重启进程
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # 这是Flask重启后的子进程，直接返回None，让UI自己处理
        logger.info("🔄 检测到Flask重启进程，跳过多智能体系统初始化")
        return None

    # 🔧 修复：UI启动时不自动创建多智能体系统
    # UI应该只提供监控功能，不应该启动仿真系统
    if _multi_agent_system is None:
        print("\n📱 UI启动模式：仅提供监控和管理功能")
        print("💡 如需启动仿真系统，请运行: python main.py")
        print("⚠️ UI不会自动初始化多智能体系统和STK场景")
        _multi_agent_system = None

    return _multi_agent_system

def main():
    """主函数"""
    print("🌐 ADK开发UI - 多智能体系统管理界面")
    print("=" * 60)
    print("基于Google ADK开源框架设计")
    print("官方项目: https://github.com/google/adk-java")
    print("=" * 60)
    
    # 检查依赖项
    if not check_dependencies():
        return False
    
    # 检查配置文件
    config_file = Path("config/config.yaml")
    if not config_file.exists():
        print("⚠️ 配置文件不存在: config/config.yaml")
        print("系统将在没有配置的情况下启动UI界面")
    
    # 创建必要目录
    Path("logs").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)
    
    try:
        # 导入并启动UI
        from src.ui.adk_dev_ui import ADKDevUI

        print("\n🚀 启动ADK开发UI...")
        print("功能特性:")
        print("- 智能体管理和监控")
        print("- 实时会话管理")
        print("- 系统日志查看")
        print("- 多智能体协调调试")
        print("- 讨论组实时监控")
        print("- 基于ADK框架的专业界面")

        # 获取或创建多智能体系统（避免重复初始化）
        multi_agent_system = get_or_create_multi_agent_system()

        print("\n�📱 访问地址: http://localhost:8080")
        print("📋 主要页面:")
        print("   - 主页: http://localhost:8080/")
        print("   - 讨论组监控: http://localhost:8080/discussion-groups")
        print("   - 智能体管理: http://localhost:8080/agents")
        print("   - 会话管理: http://localhost:8080/sessions")
        print("⏹️ 按 Ctrl+C 停止服务器")
        print("=" * 60)

        # 创建并运行UI
        ui = ADKDevUI(host="localhost", port=8080)

        # 连接多智能体系统
        if multi_agent_system:
            ui.multi_agent_system = multi_agent_system
            print("✅ 多智能体系统已连接到UI")

        # 使用非debug模式启动，避免重启问题
        ui.run(debug=False)

        return True
        
    except KeyboardInterrupt:
        print("\n⏹️ 服务器已停止")
        return True
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        logger.error(f"启动失败: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
