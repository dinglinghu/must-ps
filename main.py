#!/usr/bin/env python3
"""
现实预警星座多智能体滚动任务规划系统 v2.0.0
主程序入口

基于Google ADK框架实现的分布式多智能体协同系统，
专门用于天基低轨预警系统的多星多任务规划。
"""

import asyncio
import logging
import sys
import os
from pathlib import Path
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

# 导入核心组件
from src.agents import MultiAgentSystem
from src.utils import get_config_manager, get_time_manager
from src.constellation import ConstellationManager
from ui.adk_monitoring_ui import ADKMonitoringUI

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/constellation_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ConstellationSystemLauncher:
    """现实预警星座系统启动器"""
    
    def __init__(self):
        self.config_manager = None
        self.time_manager = None
        self.multi_agent_system = None

        self.constellation_manager = None
        self.monitoring_ui = None
        self.is_running = False
    
    async def initialize_system(self) -> bool:
        """初始化系统"""
        try:
            logger.info("🚀 初始化现实预警星座多智能体系统 v2.0.0")
            
            # 1. 初始化配置管理器
            logger.info("1. 初始化配置管理器...")
            self.config_manager = get_config_manager("config/config.yaml")
            
            # 2. 初始化时间管理器
            logger.info("2. 初始化时间管理器...")
            self.time_manager = get_time_manager()
            
            # 3. 初始化多智能体系统
            logger.info("3. 初始化多智能体系统...")
            self.multi_agent_system = MultiAgentSystem(self.config_manager)

            # 4. 初始化星座管理器
            logger.info("4. 初始化星座管理器...")
            self.constellation_manager = ConstellationManager(None, self.config_manager)

            # 5. 初始化卫星智能体工厂并连接到多智能体系统
            logger.info("5. 初始化卫星智能体工厂...")
            await self._initialize_satellite_factory()
            
            # 6. 初始化监控UI
            logger.info("6. 初始化监控UI...")
            self.monitoring_ui = ADKMonitoringUI()
            
            logger.info("✅ 系统初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"❌ 系统初始化失败: {e}")
            return False

    async def _initialize_satellite_factory(self):
        """初始化卫星智能体工厂并创建智能体池"""
        try:
            from src.agents.satellite_agent_factory import SatelliteAgentFactory

            # 创建卫星智能体工厂
            self.satellite_factory = SatelliteAgentFactory(self.config_manager)

            # 设置多智能体系统引用
            self.satellite_factory.set_multi_agent_system(self.multi_agent_system)

            # 将工厂引用设置到多智能体系统
            self.multi_agent_system.set_satellite_factory(self.satellite_factory)

            # 从Walker星座创建智能体池
            satellite_agents = await self.satellite_factory.create_satellite_agents_from_walker_constellation(
                self.constellation_manager
            )

            if satellite_agents:
                logger.info(f"✅ 卫星智能体工厂创建了 {len(satellite_agents)} 个智能体")
            else:
                logger.warning("⚠️ 卫星智能体工厂未创建任何智能体")

        except Exception as e:
            logger.error(f"❌ 初始化卫星智能体工厂失败: {e}")
            raise
    
    async def start_system(self) -> bool:
        """启动系统"""
        try:
            logger.info("🚀 启动现实预警星座多智能体系统...")
            
            # 1. 启动多智能体系统
            logger.info("1. 启动多智能体系统...")
            success = await self.multi_agent_system.start_system()
            if not success:
                logger.error("多智能体系统启动失败")
                return False
            
            # 2. 启动监控UI
            logger.info("2. 启动监控UI...")
            self.monitoring_ui.start_monitoring()
            
            self.is_running = True
            logger.info("✅ 系统启动完成")
            logger.info("📱 监控UI地址: http://localhost:8080")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 系统启动失败: {e}")
            return False
    
    async def run_system(self):
        """运行系统主循环"""
        try:
            logger.info("🔄 进入系统主循环...")
            
            while self.is_running:
                # 系统运行中，多智能体系统会自动处理规划周期
                # 短暂休眠
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("⏹️ 用户中断系统运行")
        except Exception as e:
            logger.error(f"❌ 系统运行异常: {e}")
        finally:
            await self.stop_system()
    
    async def stop_system(self):
        """停止系统"""
        try:
            logger.info("⏹️ 停止系统...")
            
            self.is_running = False
            
            # 停止多智能体系统
            if self.multi_agent_system:
                await self.multi_agent_system.stop_system()
            
            # 停止监控UI
            if self.monitoring_ui:
                self.monitoring_ui.stop_monitoring()
            
            logger.info("✅ 系统已停止")
            
        except Exception as e:
            logger.error(f"❌ 系统停止异常: {e}")


async def main():
    """主函数"""
    try:
        print("🌟 现实预警星座多智能体滚动任务规划系统 v2.0.0")
        print("=" * 80)
        print("系统特性:")
        print("✅ 基于Google ADK框架的真实智能体架构")
        print("✅ Walker星座到ADK智能体一对一映射")
        print("✅ 基于距离优势的导弹目标智能分发")
        print("✅ ADK官方讨论组协作模式")
        print("✅ 滚动任务规划周期管理")
        # 🧹 已清理：甘特图可视化系统已删除
        print("✅ 专业UI监控界面")
        print("❌ 严禁使用虚拟智能体")
        print("=" * 80)
        
        # 检查配置文件
        config_file = Path("config/config.yaml")
        if not config_file.exists():
            print("❌ 配置文件不存在: config/config.yaml")
            return False
        
        # 创建系统启动器
        launcher = ConstellationSystemLauncher()
        
        # 初始化系统
        success = await launcher.initialize_system()
        if not success:
            print("❌ 系统初始化失败，退出")
            return False
        
        # 启动系统
        success = await launcher.start_system()
        if not success:
            print("❌ 系统启动失败，退出")
            return False
        
        print("\n🎯 系统运行中...")
        print("📱 访问监控界面: http://localhost:8080")
        print("⏹️ 按 Ctrl+C 停止系统")
        
        # 运行系统
        await launcher.run_system()
        
        print("\n✅ 系统运行完成")
        return True
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断系统")
        return False
    except Exception as e:
        print(f"\n💥 系统异常: {e}")
        logger.error(f"系统异常: {e}")
        return False


if __name__ == "__main__":
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    # 运行系统
    success = asyncio.run(main())
    
    if success:
        print("🎉 系统运行成功")
        sys.exit(0)
    else:
        print("💥 系统运行失败")
        sys.exit(1)
