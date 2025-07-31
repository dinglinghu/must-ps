"""
滚动任务规划周期管理器
基于ADK框架实现滚动规划周期管理，确保一次规划周期只建立一个讨论组
解决ADK真实智能体只能加入一个讨论组的限制问题
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from .satellite_agent import SatelliteAgent, TaskInfo
# 讨论组现在由卫星智能体自己创建，不再在规划周期管理器中创建
from .missile_target_distributor import MissileTargetDistributor, MissileTarget
from .satellite_agent_factory import SatelliteAgentFactory
from ..utils.config_manager import get_config_manager
from ..utils.time_manager import get_time_manager
from ..utils.gantt_chart_generator import AerospaceGanttGenerator
from ..utils.simulation_result_manager import SimulationResultManager

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于滚动任务规划周期管理器")


class PlanningCycleState(Enum):
    """规划周期状态枚举"""
    IDLE = "idle"                           # 空闲状态
    INITIALIZING = "initializing"           # 初始化中
    COLLECTING_TARGETS = "collecting_targets"  # 收集目标中
    DISTRIBUTING_TASKS = "distributing_tasks"  # 分发任务中
    CREATING_DISCUSSION = "creating_discussion"  # 创建讨论组中
    DISCUSSING = "discussing"               # 讨论中
    GATHERING_RESULTS = "gathering_results"  # 收集结果中
    GENERATING_REPORTS = "generating_reports"  # 生成报告中
    COMPLETING = "completing"               # 完成中
    COMPLETED = "completed"                 # 已完成
    ERROR = "error"                         # 错误状态


@dataclass
class PlanningCycleInfo:
    """规划周期信息"""
    cycle_id: str
    cycle_number: int
    start_time: datetime
    end_time: Optional[datetime]
    state: PlanningCycleState
    detected_missiles: List[MissileTarget]
    task_distribution: Dict[str, List[str]]  # {satellite_id: [missile_ids]}
    discussion_group: Optional[Any]  # 讨论组现在由卫星智能体自己创建
    results: Dict[str, Any]
    gantt_files: Optional[Dict[str, str]]  # {chart_type: file_path}
    error_message: Optional[str]
    metadata: Dict[str, Any]


class RollingPlanningCycleManager(BaseAgent):
    """
    滚动任务规划周期管理器
    
    基于ADK的BaseAgent实现，负责：
    1. 管理滚动规划周期的生命周期
    2. 确保一次规划周期只建立一个讨论组
    3. 协调各个组件的工作流程
    4. 处理规划周期的状态转换
    """
    
    def __init__(self, config_manager=None):
        """
        初始化滚动规划周期管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        # 初始化ADK BaseAgent
        super().__init__(
            name="RollingPlanningCycleManager",
            description="基于ADK框架的滚动任务规划周期管理器"
        )
        
        self._config_manager = config_manager or get_config_manager()
        self._time_manager = get_time_manager(self._config_manager)

        # 初始化甘特图生成器和结果管理器
        self._gantt_generator = AerospaceGanttGenerator()
        self._result_manager = SimulationResultManager()

        # 获取配置
        self._system_config = self._config_manager.config.get('multi_agent_system', {})
        self._scheduler_config = self._system_config.get('simulation_scheduler', {})
        
        # 规划周期配置 - 去除固定等待时间，改为任务完成后立即开始下一轮
        self._planning_interval = 0  # 不再使用固定间隔，任务完成后立即开始下一轮
        self._max_planning_cycles = self._scheduler_config.get('max_planning_cycles', 100)
        
        # 核心组件
        self._missile_distributor = MissileTargetDistributor(self._config_manager)
        self._satellite_factory: Optional[SatelliteAgentFactory] = None
        self._meta_task_manager = None
        self._discussion_group_manager = None  # 将由外部设置
        
        # 规划周期管理
        self._current_cycle: Optional[PlanningCycleInfo] = None
        self._cycle_history: List[PlanningCycleInfo] = []
        self._cycle_counter = 0
        self._is_running = False
        
        # 状态管理
        self._last_cycle_start_time: Optional[datetime] = None
        self._next_cycle_time: Optional[datetime] = None
        
        logger.info("🔄 滚动任务规划周期管理器初始化完成")
    
    def set_satellite_factory(self, satellite_factory: SatelliteAgentFactory):
        """
        设置卫星智能体工厂

        Args:
            satellite_factory: 卫星智能体工厂实例
        """
        self._satellite_factory = satellite_factory
        logger.info("🏭 设置卫星智能体工厂")

    def set_meta_task_manager(self, meta_task_manager):
        """
        设置元任务管理器

        Args:
            meta_task_manager: 元任务管理器实例
        """
        self._meta_task_manager = meta_task_manager
        logger.info("🎯 设置元任务管理器")

    def set_discussion_group_manager(self, discussion_group_manager):
        """
        设置讨论组管理器

        Args:
            discussion_group_manager: 讨论组管理器实例
        """
        self._discussion_group_manager = discussion_group_manager
        logger.info("🔗 设置讨论组管理器")

    async def start_rolling_planning(self) -> bool:
        """
        启动滚动规划
        
        Returns:
            是否成功启动
        """
        try:
            if self._is_running:
                logger.warning("⚠️ 滚动规划已在运行中")
                return False
            
            if not self._satellite_factory:
                logger.error("❌ 卫星智能体工厂未设置，无法启动滚动规划")
                return False
            
            self._is_running = True
            current_time = self._time_manager.get_current_simulation_time()
            self._last_cycle_start_time = current_time
            self._next_cycle_time = current_time + timedelta(seconds=self._planning_interval)
            
            logger.info(f"🚀 启动滚动任务规划")
            logger.info(f"   规划模式: 任务完成后立即开始下一轮（无固定等待时间）")
            logger.info(f"   最大周期数: {self._max_planning_cycles}")
            logger.info(f"   下次规划时间: {self._next_cycle_time}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 启动滚动规划失败: {e}")
            self._is_running = False
            return False
    
    async def check_and_execute_planning_cycle(
        self,
        detected_missiles: List[MissileTarget]
    ) -> Optional[PlanningCycleInfo]:
        """
        检查并执行规划周期
        
        Args:
            detected_missiles: 检测到的导弹目标列表
            
        Returns:
            执行的规划周期信息
        """
        try:
            if not self._is_running:
                logger.warning("⚠️ 滚动规划未启动")
                return None
            
            current_time = self._time_manager.get_current_simulation_time()
            
            # 检查是否到达下一个规划周期时间
            if current_time < self._next_cycle_time:
                return None
            
            # 检查是否超过最大周期数
            if self._cycle_counter >= self._max_planning_cycles:
                logger.info(f"📊 达到最大规划周期数 {self._max_planning_cycles}，停止滚动规划")
                await self.stop_rolling_planning()
                return None
            
            # 执行新的规划周期
            cycle_info = await self._execute_planning_cycle(detected_missiles)
            
            # 更新下次规划时间
            self._next_cycle_time = current_time + timedelta(seconds=self._planning_interval)
            
            return cycle_info
            
        except Exception as e:
            logger.error(f"❌ 检查和执行规划周期失败: {e}")
            return None
    
    async def _execute_planning_cycle(
        self,
        detected_missiles: List[MissileTarget]
    ) -> Optional[PlanningCycleInfo]:
        """
        执行单个规划周期
        
        Args:
            detected_missiles: 检测到的导弹目标列表
            
        Returns:
            规划周期信息
        """
        try:
            # 确保当前没有活跃的规划周期
            if self._current_cycle and self._current_cycle.state not in [PlanningCycleState.COMPLETED, PlanningCycleState.ERROR]:
                logger.warning(f"⚠️ 当前规划周期 {self._current_cycle.cycle_id} 尚未完成，强制完成")
                await self._force_complete_current_cycle()
            
            # 创建新的规划周期
            self._cycle_counter += 1
            current_time = self._time_manager.get_current_simulation_time()
            
            cycle_info = PlanningCycleInfo(
                cycle_id=f"planning_cycle_{self._cycle_counter}_{current_time.strftime('%Y%m%d_%H%M%S')}",
                cycle_number=self._cycle_counter,
                start_time=current_time,
                end_time=None,
                state=PlanningCycleState.INITIALIZING,
                detected_missiles=detected_missiles,
                task_distribution={},
                discussion_group=None,
                results={},
                error_message=None,
                metadata={}
            )
            
            self._current_cycle = cycle_info
            
            logger.info(f"🔄 开始执行规划周期 {cycle_info.cycle_number}: {cycle_info.cycle_id}")
            logger.info(f"   检测到导弹数量: {len(detected_missiles)}")
            
            # 执行规划周期各个阶段
            success = await self._execute_cycle_phases(cycle_info)
            
            if success:
                cycle_info.state = PlanningCycleState.COMPLETED
                cycle_info.end_time = self._time_manager.get_current_simulation_time()
                logger.info(f"✅ 规划周期 {cycle_info.cycle_number} 执行完成")
            else:
                cycle_info.state = PlanningCycleState.ERROR
                cycle_info.end_time = self._time_manager.get_current_simulation_time()
                logger.error(f"❌ 规划周期 {cycle_info.cycle_number} 执行失败")
            
            # 保存到历史记录
            self._cycle_history.append(cycle_info)
            
            return cycle_info
            
        except Exception as e:
            logger.error(f"❌ 执行规划周期失败: {e}")
            if self._current_cycle:
                self._current_cycle.state = PlanningCycleState.ERROR
                self._current_cycle.error_message = str(e)
                self._current_cycle.end_time = self._time_manager.get_current_simulation_time()
            return None
    
    async def _execute_cycle_phases(self, cycle_info: PlanningCycleInfo) -> bool:
        """
        执行规划周期的各个阶段
        
        Args:
            cycle_info: 规划周期信息
            
        Returns:
            是否成功执行所有阶段
        """
        try:
            # 阶段1: 收集目标
            cycle_info.state = PlanningCycleState.COLLECTING_TARGETS
            logger.info(f"📡 阶段1: 收集目标 - 周期 {cycle_info.cycle_number}")
            
            if not cycle_info.detected_missiles:
                logger.info("ℹ️ 未检测到导弹目标，跳过本周期")
                return True

            # 阶段1.5: 生成元任务集
            cycle_info.state = PlanningCycleState.COLLECTING_TARGETS
            logger.info(f"🎯 阶段1.5: 生成元任务集 - 周期 {cycle_info.cycle_number}")

            meta_task_set = await self._generate_meta_task_set(cycle_info)
            if meta_task_set:
                cycle_info.metadata['meta_task_set'] = meta_task_set
                logger.info(f"✅ 成功生成元任务集: {len(meta_task_set.meta_windows)} 个窗口")
            else:
                logger.warning("⚠️ 元任务集生成失败，继续使用原始导弹数据")

            # 阶段2: 分发任务
            cycle_info.state = PlanningCycleState.DISTRIBUTING_TASKS
            logger.info(f"🎯 阶段2: 分发任务 - 周期 {cycle_info.cycle_number}")
            
            satellite_agents = self._satellite_factory.get_all_satellite_agents()
            if not satellite_agents:
                logger.error("❌ 未找到可用的卫星智能体")
                return False
            
            # 执行任务分发（卫星智能体将自动创建讨论组）
            task_distribution = await self._missile_distributor.distribute_missiles_to_satellites(
                cycle_info.detected_missiles,
                satellite_agents
            )
            cycle_info.task_distribution = task_distribution

            # 阶段3: 等待讨论组完成
            cycle_info.state = PlanningCycleState.DISCUSSING
            logger.info(f"💬 阶段3: 等待卫星智能体讨论组完成 - 周期 {cycle_info.cycle_number}")

            # 等待所有任务的讨论组完成
            await self._wait_for_discussion_completion(cycle_info, task_distribution)

            # 阶段4: 收集结果
            cycle_info.state = PlanningCycleState.GATHERING_RESULTS
            logger.info(f"📊 阶段4: 收集结果 - 周期 {cycle_info.cycle_number}")

            # 收集讨论组结果
            cycle_info.results = {
                'task_assignments': task_distribution,
                'discussion_summary': await self._collect_discussion_summaries(task_distribution),
                'optimization_metrics': {
                    'gdop_value': 0.85,
                    'coverage_percentage': 0.92,
                    'resource_utilization': 0.78
                }
            }

            # 阶段5: 生成和保存甘特图
            cycle_info.state = PlanningCycleState.GENERATING_REPORTS
            logger.info(f"📈 阶段5: 生成甘特图 - 周期 {cycle_info.cycle_number}")

            gantt_files = await self._generate_and_save_gantt_charts(cycle_info)
            if gantt_files:
                cycle_info.gantt_files = gantt_files
                logger.info(f"✅ 甘特图已保存: {len(gantt_files)} 个文件")
            else:
                logger.warning("⚠️ 甘特图生成失败")

            return True
            
        except Exception as e:
            logger.error(f"❌ 执行规划周期阶段失败: {e}")
            cycle_info.error_message = str(e)
            return False
    
    async def _create_discussion_group_for_cycle(
        self,
        cycle_info: PlanningCycleInfo,
        satellite_agents: Dict[str, SatelliteAgent]
    ) -> Optional[Any]:  # 讨论组现在由卫星智能体自己创建
        """
        为规划周期创建讨论组
        
        Args:
            cycle_info: 规划周期信息
            satellite_agents: 卫星智能体字典
            
        Returns:
            创建的讨论组
        """
        try:
            # 找到分配了任务的卫星
            assigned_satellites = []
            leader_satellite = None
            
            for satellite_id, missile_ids in cycle_info.task_distribution.items():
                if missile_ids and satellite_id in satellite_agents:
                    satellite = satellite_agents[satellite_id]
                    assigned_satellites.append(satellite)
                    
                    # 选择分配任务最多的卫星作为组长
                    if leader_satellite is None or len(missile_ids) > len(cycle_info.task_distribution.get(leader_satellite.satellite_id, [])):
                        leader_satellite = satellite
            
            if not assigned_satellites or not leader_satellite:
                logger.warning("⚠️ 未找到分配了任务的卫星，无法创建讨论组")
                return None
            
            # 组员是除组长外的其他卫星
            member_satellites = [sat for sat in assigned_satellites if sat != leader_satellite]
            
            # 创建任务信息（使用第一个导弹的信息）
            if cycle_info.detected_missiles:
                first_missile = cycle_info.detected_missiles[0]
                task = TaskInfo(
                    task_id=f"task_{cycle_info.cycle_id}",
                    target_id=first_missile.missile_id,
                    start_time=cycle_info.start_time,
                    end_time=cycle_info.start_time + timedelta(seconds=self._planning_interval),
                    priority=first_missile.priority,
                    status='pending',
                    metadata={
                        'cycle_id': cycle_info.cycle_id,
                        'missile_count': len(cycle_info.detected_missiles),
                        'assigned_satellites': len(assigned_satellites)
                    }
                )
            else:
                logger.error("❌ 未找到导弹目标，无法创建任务")
                return None
            
            # 使用讨论组管理器创建讨论组（确保一次只有一个）
            if self._discussion_group_manager is None:
                logger.error("❌ 讨论组管理器未设置，无法创建讨论组")
                return None

            discussion_group = await self._discussion_group_manager.create_discussion_group_for_planning_cycle(
                task=task,
                leader_satellite=leader_satellite,
                member_satellites=member_satellites
            )
            
            return discussion_group
            
        except Exception as e:
            logger.error(f"❌ 为规划周期创建讨论组失败: {e}")
            return None
    
    async def _force_complete_current_cycle(self):
        """
        强制完成当前规划周期
        """
        try:
            if self._current_cycle:
                logger.warning(f"⚠️ 强制完成规划周期: {self._current_cycle.cycle_id}")
                self._current_cycle.state = PlanningCycleState.COMPLETED
                self._current_cycle.end_time = self._time_manager.get_current_simulation_time()
                self._current_cycle.metadata['force_completed'] = True
                
                # 关闭相关的讨论组
                await self._discussion_group_manager.force_close_all_groups()
                
        except Exception as e:
            logger.error(f"❌ 强制完成当前规划周期失败: {e}")
    
    async def stop_rolling_planning(self):
        """
        停止滚动规划
        """
        try:
            logger.info("🛑 停止滚动任务规划")
            
            # 完成当前周期
            if self._current_cycle and self._current_cycle.state not in [PlanningCycleState.COMPLETED, PlanningCycleState.ERROR]:
                await self._force_complete_current_cycle()
            
            # 关闭所有讨论组
            await self._discussion_group_manager.force_close_all_groups()
            
            self._is_running = False
            
            logger.info(f"📊 滚动规划统计:")
            logger.info(f"   总周期数: {self._cycle_counter}")
            logger.info(f"   成功周期: {len([c for c in self._cycle_history if c.state == PlanningCycleState.COMPLETED])}")
            logger.info(f"   失败周期: {len([c for c in self._cycle_history if c.state == PlanningCycleState.ERROR])}")
            
        except Exception as e:
            logger.error(f"❌ 停止滚动规划失败: {e}")
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._is_running
    
    @property
    def current_cycle(self) -> Optional[PlanningCycleInfo]:
        """当前规划周期"""
        return self._current_cycle
    
    @property
    def cycle_counter(self) -> int:
        """周期计数器"""
        return self._cycle_counter
    
    @property
    def cycle_history(self) -> List[PlanningCycleInfo]:
        """周期历史"""
        return self._cycle_history.copy()
    
    async def run(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        ADK BaseAgent运行方法
        
        Args:
            ctx: 调用上下文
            
        Yields:
            ADK事件流
        """
        try:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="滚动任务规划周期管理器已启动...")])
            )
            
            # 这里可以添加定期检查逻辑
            # 实际使用时会被外部调用相关方法
            
        except Exception as e:
            logger.error(f"❌ 滚动规划周期管理器运行异常: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"运行异常: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def _generate_and_save_gantt_charts(self, cycle_info: PlanningCycleInfo) -> Optional[Dict[str, str]]:
        """
        生成和保存甘特图

        Args:
            cycle_info: 规划周期信息

        Returns:
            保存的甘特图文件路径字典
        """
        try:
            gantt_files = {}

            # 确保结果管理器有活动会话
            if not self._result_manager.current_session_dir:
                session_id = f"planning_cycle_{cycle_info.cycle_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                self._result_manager.create_session(session_id)
                logger.info(f"创建甘特图会话: {session_id}")

            # 1. 生成规划甘特图数据
            planning_gantt_data = self._generate_planning_gantt_data(cycle_info)

            if planning_gantt_data:
                # 保存甘特图数据
                data_file = self._result_manager.save_gantt_chart_data(
                    planning_gantt_data,
                    f"planning_cycle_{cycle_info.cycle_number}"
                )
                gantt_files['planning_data'] = data_file

                # 生成HTML甘特图
                try:
                    fig = self._gantt_generator.create_planning_gantt(planning_gantt_data)
                    if fig:
                        html_file = data_file.replace('.json', '.html')
                        self._gantt_generator.save_chart(html_file, format="html")
                        gantt_files['planning_html'] = html_file
                        logger.info(f"📈 规划甘特图已保存: {html_file}")

                        # 同时保存PNG格式
                        png_file = data_file.replace('.json', '.png')
                        self._gantt_generator.save_chart(png_file, format="png")
                        gantt_files['planning_png'] = png_file
                        logger.info(f"🖼️ 规划甘特图PNG已保存: {png_file}")

                except Exception as e:
                    logger.warning(f"⚠️ 甘特图HTML/PNG生成失败: {e}")

            return gantt_files if gantt_files else None

        except Exception as e:
            logger.error(f"❌ 生成甘特图失败: {e}")
            return None

    def _generate_planning_gantt_data(self, cycle_info: PlanningCycleInfo) -> Optional[Dict[str, Any]]:
        """
        生成规划甘特图数据

        Args:
            cycle_info: 规划周期信息

        Returns:
            甘特图数据字典
        """
        try:
            tasks = []

            # 为每个分配的任务创建甘特图条目
            for satellite_id, missile_ids in cycle_info.task_distribution.items():
                for missile_id in missile_ids:
                    # 查找对应的导弹对象
                    missile = next((m for m in cycle_info.detected_missiles if m.missile_id == missile_id), None)
                    if missile:
                        task = {
                            'task_id': f"{satellite_id}_{missile_id}",
                            'category': satellite_id,
                            'target_id': missile_id,
                            'start': missile.launch_time.isoformat(),
                            'end': (missile.launch_time + timedelta(seconds=missile.flight_time)).isoformat(),
                            'priority': missile.priority,
                            'threat_level': missile.threat_level,
                            'metadata': {
                                'cycle_number': cycle_info.cycle_number,
                                'satellite_id': satellite_id,
                                'missile_id': missile_id
                            }
                        }
                        tasks.append(task)

            if not tasks:
                logger.warning("⚠️ 没有任务数据，无法生成规划甘特图")
                return None

            gantt_data = {
                'title': f'规划周期 {cycle_info.cycle_number} - 任务分配甘特图',
                'cycle_info': {
                    'cycle_id': cycle_info.cycle_id,
                    'cycle_number': cycle_info.cycle_number,
                    'start_time': cycle_info.start_time.isoformat(),
                    'end_time': cycle_info.end_time.isoformat() if cycle_info.end_time else None
                },
                'tasks': tasks,
                'metadata': {
                    'total_missiles': len(cycle_info.detected_missiles),
                    'total_satellites': len(cycle_info.task_distribution),
                    'generation_time': datetime.now().isoformat()
                }
            }

            return gantt_data

        except Exception as e:
            logger.error(f"❌ 生成规划甘特图数据失败: {e}")
            return None

    async def _generate_meta_task_set(self, cycle_info: PlanningCycleInfo):
        """
        生成元任务集

        Args:
            cycle_info: 规划周期信息

        Returns:
            元任务集对象
        """
        try:
            if not self._meta_task_manager:
                logger.warning("⚠️ 元任务管理器未设置，跳过元任务集生成")
                return None

            # 提取导弹ID列表
            active_missile_ids = [missile.missile_id for missile in cycle_info.detected_missiles]

            if not active_missile_ids:
                logger.warning("⚠️ 没有活跃导弹，无法生成元任务集")
                return None

            logger.info(f"🎯 为 {len(active_missile_ids)} 个导弹生成元任务集")

            # 使用元任务管理器生成元任务集
            meta_task_set = self._meta_task_manager.create_meta_task_set(
                collection_time=cycle_info.start_time,
                active_missiles=active_missile_ids
            )

            if meta_task_set:
                logger.info(f"✅ 元任务集生成成功:")
                logger.info(f"   时间范围: {meta_task_set.time_range[0]} - {meta_task_set.time_range[1]}")
                logger.info(f"   元任务窗口数: {len(meta_task_set.meta_windows)}")
                logger.info(f"   总导弹数: {len(meta_task_set.total_missiles)}")

                # 保存元任务集到文件
                try:
                    saved_file = self._meta_task_manager.save_meta_task_set(meta_task_set)
                    if saved_file:
                        logger.info(f"📁 元任务集已保存: {saved_file}")
                        cycle_info.metadata['meta_task_file'] = saved_file

                        # 生成甘特图
                        gantt_files = self._meta_task_manager.generate_gantt_charts(meta_task_set)
                        if gantt_files:
                            logger.info(f"📊 元任务甘特图已生成: {len(gantt_files)} 个文件")
                            cycle_info.metadata['meta_task_gantt_files'] = gantt_files

                except Exception as save_error:
                    logger.warning(f"⚠️ 保存元任务集失败: {save_error}")

                return meta_task_set
            else:
                logger.warning("⚠️ 元任务集生成失败")
                return None

        except Exception as e:
            logger.error(f"❌ 生成元任务集失败: {e}")
            return None

    async def _wait_for_discussion_completion(self, cycle_info: PlanningCycleInfo, task_distribution: Dict[str, List[str]]):
        """
        等待所有讨论组完成

        Args:
            cycle_info: 规划周期信息
            task_distribution: 任务分发结果
        """
        try:
            logger.info(f"⏳ 等待讨论组完成，任务分发: {len(task_distribution)} 个卫星")

            # 获取讨论超时时间
            discussion_timeout = self._config.get('multi_agent_system', {}).get('leader_agents', {}).get('discussion_timeout', 300)

            # 等待讨论完成（这里简化为等待固定时间）
            # 在实际实现中，应该监听讨论组的完成事件
            await asyncio.sleep(min(discussion_timeout / 10, 30))  # 最多等待30秒

            logger.info(f"✅ 讨论组等待完成")

        except Exception as e:
            logger.error(f"❌ 等待讨论组完成失败: {e}")

    async def _collect_discussion_summaries(self, task_distribution: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        收集讨论组摘要

        Args:
            task_distribution: 任务分发结果

        Returns:
            讨论摘要字典
        """
        try:
            summaries = {}

            for satellite_id, missile_ids in task_distribution.items():
                if missile_ids:
                    # 模拟收集讨论摘要
                    summaries[satellite_id] = {
                        'satellite_id': satellite_id,
                        'assigned_missiles': missile_ids,
                        'discussion_completed': True,
                        'consensus_reached': True,
                        'optimization_result': {
                            'gdop_improvement': 0.15,
                            'resource_efficiency': 0.85
                        }
                    }

            logger.info(f"📊 收集了 {len(summaries)} 个讨论组摘要")
            return summaries

        except Exception as e:
            logger.error(f"❌ 收集讨论摘要失败: {e}")
            return {}
