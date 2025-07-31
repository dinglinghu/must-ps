#!/usr/bin/env python3
"""
ADK多智能体航天预警星座导弹目标跟踪系统主启动脚本
基于Google ADK框架实现，严格按照官方文档设计

系统特性：
1. 基于ADK框架的真实智能体（禁用虚拟智能体）
2. Walker星座到ADK智能体的一对一映射
3. 基于距离优势的导弹目标智能分发
4. ADK Parallel Fan-Out/Gather Pattern讨论组
5. 滚动任务规划周期管理（一次只建立一个讨论组）
6. 基于ADK Java项目的UI监控界面
"""

import asyncio
import logging
import signal
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 导入系统组件
from src.agents.multi_agent_system import MultiAgentSystem
from src.agents.satellite_agent_factory import SatelliteAgentFactory
from src.agents.missile_target_distributor import MissileTargetDistributor, MissileTarget
from src.agents.adk_parallel_discussion_group import ADKParallelDiscussionGroupManager
from src.agents.rolling_planning_cycle_manager import RollingPlanningCycleManager
from src.constellation.constellation_manager import ConstellationManager
from src.ui.adk_monitoring_ui import ADKMonitoringUI
from src.utils.config_manager import get_config_manager
from src.utils.time_manager import get_time_manager
from src.meta_task.meta_task_manager import get_meta_task_manager
from src.stk_interface.missile_manager import get_missile_manager
from src.stk_interface.visibility_calculator import get_visibility_calculator

# 配置日志 - 解决Windows编码问题
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('adk_system.log', encoding='utf-8')
    ]
)

# 设置控制台编码
import os
if os.name == 'nt':  # Windows系统
    os.system('chcp 65001')  # 设置为UTF-8编码

logger = logging.getLogger(__name__)


class ADKSystemLauncher:
    """ADK系统启动器"""
    
    def __init__(self):
        """初始化系统启动器"""
        self.config_manager = get_config_manager()
        self.time_manager = get_time_manager(self.config_manager)
        
        # 核心系统组件
        self.multi_agent_system: Optional[MultiAgentSystem] = None
        self.constellation_manager: Optional[ConstellationManager] = None
        self.satellite_factory: Optional[SatelliteAgentFactory] = None
        self.missile_distributor: Optional[MissileTargetDistributor] = None
        self.discussion_group_manager: Optional[ADKParallelDiscussionGroupManager] = None
        self.planning_cycle_manager: Optional[RollingPlanningCycleManager] = None

        # 元任务和轨迹管理组件
        self.meta_task_manager = None
        self.missile_manager = None
        self.visibility_calculator = None

        # UI监控组件
        self.monitoring_ui: Optional[ADKMonitoringUI] = None
        self.ui_thread: Optional[threading.Thread] = None
        
        # 系统状态
        self.is_running = False
        self.shutdown_event = threading.Event()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info("ADK系统启动器初始化完成")
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"📡 接收到信号 {signum}，开始优雅关闭系统...")
        self.shutdown_event.set()
    
    async def initialize_system(self) -> bool:
        """
        初始化系统组件
        
        Returns:
            是否成功初始化
        """
        try:
            logger.info("开始初始化ADK多智能体系统...")

            # 1. 初始化多智能体系统
            logger.info("1. 初始化多智能体系统...")
            self.multi_agent_system = MultiAgentSystem(self.config_manager)

            # 2. 初始化星座管理器
            logger.info("2. 初始化星座管理器...")
            self.constellation_manager = ConstellationManager(self.config_manager)

            # 3. 初始化卫星智能体工厂
            logger.info("3. 初始化卫星智能体工厂...")
            self.satellite_factory = SatelliteAgentFactory(self.config_manager)

            # 4. 创建Walker星座对应的ADK智能体
            logger.info("4. 创建Walker星座ADK智能体...")
            satellite_agents = await self.satellite_factory.create_satellite_agents_from_walker_constellation(
                self.constellation_manager
            )

            if not satellite_agents:
                logger.error("创建卫星智能体失败")
                return False

            logger.info(f"成功创建 {len(satellite_agents)} 个卫星智能体")

            # 4.1. 注册卫星智能体到多智能体系统
            logger.info("4.1. 注册卫星智能体到多智能体系统...")
            success = self.multi_agent_system.register_satellite_agents(satellite_agents)
            if not success:
                logger.error("注册卫星智能体到多智能体系统失败")
                return False

            # 5. 初始化导弹目标分发器
            logger.info("5. 初始化导弹目标分发器...")
            self.missile_distributor = MissileTargetDistributor(self.config_manager)

            # 6. 初始化讨论组管理器
            logger.info("6. 初始化ADK讨论组管理器...")
            self.discussion_group_manager = ADKParallelDiscussionGroupManager(self.config_manager)

            # 7. 初始化元任务和轨迹管理组件
            logger.info("7. 初始化元任务和轨迹管理组件...")
            self.missile_manager = get_missile_manager(self.config_manager)
            self.visibility_calculator = get_visibility_calculator(self.config_manager)
            self.meta_task_manager = get_meta_task_manager(
                self.config_manager,
                self.time_manager,
                self.missile_manager,
                self.visibility_calculator
            )

            # 8. 初始化滚动规划周期管理器
            logger.info("8. 初始化滚动规划周期管理器...")
            self.planning_cycle_manager = RollingPlanningCycleManager(self.config_manager)
            self.planning_cycle_manager.set_satellite_factory(self.satellite_factory)
            self.planning_cycle_manager.set_meta_task_manager(self.meta_task_manager)
            self.planning_cycle_manager.set_discussion_group_manager(self.discussion_group_manager)

            # 9. 初始化UI监控界面
            logger.info("9. 初始化ADK监控UI...")
            self.monitoring_ui = ADKMonitoringUI(host="localhost", port=8081)
            self.monitoring_ui.set_system_components(
                multi_agent_system=self.multi_agent_system,
                satellite_factory=self.satellite_factory,
                discussion_group_manager=self.discussion_group_manager,
                planning_cycle_manager=self.planning_cycle_manager,
                missile_distributor=self.missile_distributor
            )
            
            logger.info("系统组件初始化完成")
            return True

        except Exception as e:
            logger.error(f"系统初始化失败: {e}")
            return False
    
    async def start_system(self) -> bool:
        """
        启动系统
        
        Returns:
            是否成功启动
        """
        try:
            logger.info("启动ADK多智能体系统...")

            # 1. 启动多智能体系统
            logger.info("1. 启动多智能体系统...")
            success = await self.multi_agent_system.start_system()
            if not success:
                logger.error("多智能体系统启动失败")
                return False

            # 2. 启动滚动规划
            logger.info("2. 启动滚动任务规划...")
            success = await self.planning_cycle_manager.start_rolling_planning()
            if not success:
                logger.error("滚动规划启动失败")
                return False

            # 3. 启动UI监控界面（在单独线程中）
            logger.info("3. 启动ADK监控UI...")
            self.ui_thread = threading.Thread(
                target=self._run_monitoring_ui,
                daemon=True
            )
            self.ui_thread.start()

            # 4. 启动监控
            self.monitoring_ui.start_monitoring()

            self.is_running = True
            logger.info("ADK多智能体系统启动完成")
            logger.info("监控UI地址: http://localhost:8081")
            
            return True
            
        except Exception as e:
            logger.error(f"系统启动失败: {e}")
            return False
    
    def _run_monitoring_ui(self):
        """运行监控UI（在单独线程中）"""
        try:
            self.monitoring_ui.run(debug=False)
        except Exception as e:
            logger.error(f"监控UI运行异常: {e}")
    
    async def run_simulation_loop(self):
        """运行仿真循环"""
        try:
            logger.info("开始仿真循环...")

            simulation_counter = 0

            while self.is_running and not self.shutdown_event.is_set():
                try:
                    simulation_counter += 1
                    current_time = self.time_manager.get_current_simulation_time()

                    logger.info(f"仿真周期 {simulation_counter} - {current_time}")

                    # 1. 模拟导弹目标检测
                    detected_missiles = self._simulate_missile_detection(simulation_counter)

                    if detected_missiles:
                        logger.info(f"检测到 {len(detected_missiles)} 个导弹目标")

                        # 2. 执行规划周期
                        cycle_info = await self.planning_cycle_manager.check_and_execute_planning_cycle(
                            detected_missiles
                        )

                        if cycle_info:
                            logger.info(f"执行规划周期: {cycle_info.cycle_id}")

                    # 3. 更新卫星位置（模拟）
                    await self._update_satellite_positions()

                    # 4. 等待下一个仿真步长
                    await asyncio.sleep(5)  # 5秒仿真步长

                except Exception as e:
                    logger.error(f"仿真循环异常: {e}")
                    await asyncio.sleep(10)  # 出错时等待更长时间

            logger.info("仿真循环结束")

        except Exception as e:
            logger.error(f"仿真循环失败: {e}")
    
    def _simulate_missile_detection(self, simulation_counter: int) -> List[MissileTarget]:
        """
        模拟导弹目标检测
        
        Args:
            simulation_counter: 仿真计数器
            
        Returns:
            检测到的导弹目标列表
        """
        try:
            # 每10个周期模拟一次导弹检测
            if simulation_counter % 10 != 0:
                return []
            
            # 随机生成1-3个导弹目标
            import random
            missile_count = random.randint(1, 3)
            
            missiles = []
            for i in range(missile_count):
                missile = MissileTarget(
                    missile_id=f"sim_missile_{simulation_counter}_{i+1}",
                    launch_position={
                        'lat': 40.0 + random.uniform(-5, 5),
                        'lon': 116.0 + random.uniform(-5, 5),
                        'alt': 0.0
                    },
                    target_position={
                        'lat': 50.0 + random.uniform(-5, 5),
                        'lon': 126.0 + random.uniform(-5, 5),
                        'alt': 0.0
                    },
                    launch_time=datetime.now(),
                    flight_time=random.uniform(300, 900),
                    trajectory_points=[
                        {
                            'position': {
                                'lat': 40.0 + j * 0.1,
                                'lon': 116.0 + j * 0.1,
                                'alt': j * 20
                            },
                            'time': datetime.now() + timedelta(seconds=j*10)
                        }
                        for j in range(10)
                    ],
                    priority=random.uniform(0.5, 1.0),
                    threat_level=random.choice(['low', 'medium', 'high']),
                    metadata={'simulation': True, 'counter': simulation_counter}
                )
                missiles.append(missile)
            
            return missiles
            
        except Exception as e:
            logger.error(f"❌ 模拟导弹检测失败: {e}")
            return []
    
    async def _update_satellite_positions(self):
        """更新卫星位置（模拟）"""
        try:
            if self.satellite_factory:
                # 模拟位置更新
                positions_data = {}
                satellite_agents = self.satellite_factory.get_all_satellite_agents()
                
                for satellite_id in satellite_agents.keys():
                    # 简化的位置更新
                    positions_data[satellite_id] = {
                        'lat': 0.0,  # 实际应该从轨道预测获取
                        'lon': 0.0,
                        'alt': 1800.0,
                        'timestamp': datetime.now()
                    }
                
                await self.satellite_factory.update_satellite_positions(positions_data)
                
        except Exception as e:
            logger.error(f"❌ 更新卫星位置失败: {e}")
    
    async def shutdown_system(self):
        """关闭系统"""
        try:
            logger.info("🛑 开始关闭ADK多智能体系统...")
            
            self.is_running = False
            
            # 1. 停止滚动规划
            if self.planning_cycle_manager:
                await self.planning_cycle_manager.stop_rolling_planning()
            
            # 2. 停止监控
            if self.monitoring_ui:
                self.monitoring_ui.stop_monitoring()
            
            # 3. 关闭多智能体系统
            if self.multi_agent_system:
                await self.multi_agent_system.shutdown_system()
            
            # 4. 关闭讨论组
            if self.discussion_group_manager:
                await self.discussion_group_manager.force_close_all_groups()
            
            logger.info("✅ ADK多智能体系统关闭完成")
            
        except Exception as e:
            logger.error(f"❌ 系统关闭异常: {e}")


async def main():
    """主函数"""
    try:
        logger.info("启动ADK多智能体航天预警星座导弹目标跟踪系统")
        logger.info("系统特性:")
        logger.info("   [OK] 基于Google ADK框架的真实智能体")
        logger.info("   [OK] Walker星座到ADK智能体一对一映射")
        logger.info("   [OK] 基于距离优势的导弹目标智能分发")
        logger.info("   [OK] ADK Parallel Fan-Out/Gather Pattern讨论组")
        logger.info("   [OK] 滚动任务规划周期管理")
        logger.info("   [OK] 基于ADK Java项目的UI监控界面")
        logger.info("   [NO] 严禁使用虚拟智能体")
        
        # 创建系统启动器
        launcher = ADKSystemLauncher()
        
        # 初始化系统
        success = await launcher.initialize_system()
        if not success:
            logger.error("❌ 系统初始化失败，退出")
            return
        
        # 启动系统
        success = await launcher.start_system()
        if not success:
            logger.error("❌ 系统启动失败，退出")
            return
        
        # 运行仿真循环
        try:
            await launcher.run_simulation_loop()
        except KeyboardInterrupt:
            logger.info("📡 接收到中断信号")
        finally:
            await launcher.shutdown_system()
        
    except Exception as e:
        logger.error(f"❌ 主函数异常: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 程序被用户中断")
    except Exception as e:
        logger.error(f"❌ 程序异常退出: {e}")
        sys.exit(1)
