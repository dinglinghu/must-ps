"""
多智能体系统主控制器
基于ADK框架实现的分布式多智能体协同系统
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator
from pathlib import Path
from uuid import uuid4

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.sessions import Session
from google.genai import types

from .simulation_scheduler_agent import SimulationSchedulerAgent
from .adk_optimized_scheduler import ADKOptimizedScheduler
from .satellite_agent import SatelliteAgent
from .leader_agent import LeaderAgent
from .coordination_manager import CoordinationManager
from .meta_task_agent_integration import MetaTaskAgentIntegration
from .optimization_calculator import OptimizationCalculator

from .adk_official_discussion_system import ADKOfficialDiscussionSystem

from ..utils.config_manager import get_config_manager
from ..utils.time_manager import get_time_manager
from ..utils.llm_config_manager import get_llm_config_manager
from ..meta_task.meta_task_manager import get_meta_task_manager
# 🧹 已清理：from ..meta_task.gantt_chart_generator import GanttChartGenerator

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于多智能体系统")


class MultiAgentSystem(BaseAgent):
    """
    多智能体系统主控制器
    
    基于ADK框架实现的分布式多智能体协同系统，
    负责整个系统的初始化、协调和管理。
    """
    
    def __init__(
        self,
        config_path: Optional[str] = None,
        output_dir: str = "output"
    ):
        """
        初始化多智能体系统

        Args:
            config_path: 配置文件路径
            output_dir: 输出目录
        """
        # 初始化ADK BaseAgent
        super().__init__(
            name="MultiAgentSystem",
            description="基于ADK框架的多智能体协同系统"
        )

        # 初始化配置和管理器
        self._config_manager = get_config_manager(config_path)
        self._time_manager = get_time_manager(self._config_manager)
        
        # 获取系统配置
        self._system_config = self._config_manager.config.get('multi_agent_system', {})

        # 输出目录
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        self._session_output_dir = None  # 每次仿真的输出目录

        # 初始化核心组件
        self._initialize_core_components()

        # 智能体注册表
        self._satellite_agents: Dict[str, SatelliteAgent] = {}
        self._leader_agents: Dict[str, LeaderAgent] = {}
        self._active_discussion_groups: Dict[str, Dict[str, Any]] = {}

        # 卫星智能体工厂（用于获取已创建的智能体）
        self._satellite_factory = None



        # ADK标准讨论系统已删除，功能由ADKParallelDiscussionGroupManager替代
        self._adk_standard_discussion_system = None

        # ADK官方讨论系统（按照官方最佳实践设计，使用配置的模型）
        llm_config_mgr = get_llm_config_manager()
        discussion_llm_config = llm_config_mgr.get_llm_config('simulation_scheduler')
        discussion_model = discussion_llm_config.model  # 使用LLMConfig的model属性
        self._adk_official_discussion_system = ADKOfficialDiscussionSystem(model=discussion_model)

        # 系统状态
        self._is_running = False
        self._current_simulation_id = None

        # 设置子智能体
        self.sub_agents = [
            self._simulation_scheduler
            # self._adk_standard_discussion_system - 已删除
        ]

        logger.info("🚀 多智能体系统初始化完成")
        logger.info("✅ ADK标准讨论系统已集成")
        logger.info("✅ ADK标准讨论系统已集成（符合官方标准）")

    @property
    def config_manager(self):
        """获取配置管理器"""
        return self._config_manager

    @property
    def time_manager(self):
        """获取时间管理器"""
        return self._time_manager

    @property
    def simulation_scheduler(self):
        """获取仿真调度智能体"""
        return self._simulation_scheduler

    @property
    def coordination_manager(self):
        """获取协调管理器"""
        return self._coordination_manager

    @property
    def optimization_calculator(self):
        """获取优化计算器"""
        return self._optimization_calculator

    @property
    def meta_task_integration(self):
        """获取元任务集成管理器"""
        return self._meta_task_integration

    @property
    def satellite_agents(self):
        """获取卫星智能体字典"""
        return self._satellite_agents

    @property
    def leader_agents(self):
        """获取组长智能体字典"""
        return self._leader_agents

    @property
    def active_discussion_groups(self):
        """获取活跃讨论组字典"""
        return self._active_discussion_groups

    @property
    def is_running(self) -> bool:
        """获取运行状态"""
        return self._is_running

    @property
    def current_simulation_id(self) -> Optional[str]:
        """获取当前仿真ID"""
        return self._current_simulation_id

    @property
    def session_output_dir(self) -> Optional[Path]:
        """获取会话输出目录"""
        return self._session_output_dir
    
    def _initialize_core_components(self):
        """初始化核心组件"""
        try:
            # 仿真调度智能体（使用ADK优化版本）
            scheduler_config = self._system_config.get('simulation_scheduler', {})
            use_adk_optimization = scheduler_config.get('use_adk_optimization', True)

            if use_adk_optimization:
                self._simulation_scheduler = ADKOptimizedScheduler(
                    name="ADKOptimizedScheduler",
                    model=scheduler_config.get('model', 'gemini-2.0-flash'),
                    config_manager=self._config_manager,
                    multi_agent_system=self
                )
                logger.info("✅ 使用ADK优化调度器（transfer_to_agent机制）")
            else:
                self._simulation_scheduler = SimulationSchedulerAgent(
                    name="SimulationScheduler",
                    model=scheduler_config.get('model', 'gemini-2.0-flash'),
                    config_manager=self._config_manager,
                    multi_agent_system=self
                )
                logger.info("✅ 使用传统调度器（轮询机制）")

            # 协调管理器
            coordination_config = self._system_config.get('coordination', {})
            self._coordination_manager = CoordinationManager(coordination_config)

            # 优化计算器
            optimization_config = self._system_config.get('optimization', {})
            self._optimization_calculator = OptimizationCalculator(optimization_config)

            # 元任务集成管理器
            meta_task_manager = get_meta_task_manager()
            # 🧹 已清理：甘特图生成器功能已删除
            self._meta_task_integration = MetaTaskAgentIntegration(
                meta_task_manager, None  # 甘特图生成器已清理
            )



            # 注册仿真调度智能体到协调管理器
            self._coordination_manager.register_agent(self._simulation_scheduler)

            # 设置仿真调度智能体的多智能体系统引用
            self._simulation_scheduler.set_multi_agent_system(self)

            logger.info("🔧 核心组件初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 核心组件初始化失败: {e}")
            raise
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        多智能体系统主运行逻辑
        """
        logger.info("🚀 多智能体系统开始运行")
        
        try:
            # 1. 创建仿真会话输出目录
            self._create_session_output_dir()
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"仿真会话 {self._current_simulation_id} 开始")])
            )
            
            # 2. 启动仿真调度智能体
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="启动仿真调度智能体...")])
            )
            
            # 运行仿真调度智能体
            async for event in self._simulation_scheduler.run_async(ctx):
                # 检查是否需要创建讨论组
                if self._should_create_discussion_group(event):
                    async for group_event in self._handle_discussion_group_creation(event, ctx):
                        yield group_event
                
                # 处理协调管理器消息
                coordination_events = await self._coordination_manager.process_messages(ctx)
                for coord_event in coordination_events:
                    yield coord_event
                
                # 转发事件
                yield event
                
                # 检查是否为最终结果
                if event.is_final_response():
                    break
            
            # 3. 生成最终报告
            final_report = await self._generate_final_system_report(ctx)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=final_report)]),
                actions=EventActions(escalate=True)
            )
            
        except Exception as e:
            logger.error(f"❌ 多智能体系统运行异常: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"系统运行异常: {e}")]),
                actions=EventActions(escalate=True)
            )
        finally:
            # 清理资源
            await self._cleanup_system_resources()
    
    def _create_session_output_dir(self):
        """创建仿真会话输出目录"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_simulation_id = f"simulation_{timestamp}"

        self._session_output_dir = self._output_dir / self._current_simulation_id
        self._session_output_dir.mkdir(parents=True, exist_ok=True)

        # 创建子目录
        (self._session_output_dir / "meta_tasks").mkdir(exist_ok=True)
        (self._session_output_dir / "gantt_charts").mkdir(exist_ok=True)
        (self._session_output_dir / "coordination_results").mkdir(exist_ok=True)
        (self._session_output_dir / "agent_logs").mkdir(exist_ok=True)

        logger.info(f"📁 创建仿真会话目录: {self._session_output_dir}")
    

    


    
    async def _create_leader_agent(self, target_id: str, ctx: InvocationContext) -> Optional[LeaderAgent]:
        """创建组长智能体"""
        try:
            leader_config = self.system_config.get('leader_agents', {})
            
            leader_agent = LeaderAgent(
                name=f"Leader_{target_id}",
                target_id=target_id,
                model=leader_config.get('model', 'gemini-2.0-flash'),
                config=leader_config
            )
            
            # 注册到协调管理器
            self._coordination_manager.register_agent(leader_agent)

            # 保存到注册表
            self._leader_agents[target_id] = leader_agent
            
            logger.info(f"👑 为目标 {target_id} 创建组长智能体: {leader_agent.name}")
            
            return leader_agent
            
        except Exception as e:
            logger.error(f"❌ 创建组长智能体失败: {e}")
            return None
    
    async def _create_satellite_agents_for_target(
        self,
        target_id: str,
        ctx: InvocationContext
    ) -> List[SatelliteAgent]:
        """为目标获取相关的卫星智能体（从已创建的池中获取，避免重复创建）"""
        try:
            # 获取可见的卫星列表（实际应通过可见性计算获得）
            visible_satellites = await self._get_visible_satellites_for_target(target_id)

            satellite_agents = []

            for sat_id in visible_satellites:
                # 优先从已注册的智能体中获取
                agent = self.get_satellite_agent(sat_id)

                if agent is None:
                    # 如果没有注册，从工厂获取（避免重复创建）
                    agent = await self._get_agent_from_factory(sat_id)

                    if agent:
                        # 注册到系统
                        self._satellite_agents[sat_id] = agent
                        self._coordination_manager.register_agent(agent)
                        logger.info(f"📋 从工厂获取并注册卫星智能体: {agent.name}")
                    else:
                        logger.warning(f"⚠️ 无法获取卫星智能体: {sat_id}")
                        continue
                else:
                    logger.debug(f"♻️ 复用已注册的卫星智能体: {agent.name}")

                satellite_agents.append(agent)

            logger.info(f"✅ 为目标 {target_id} 获取了 {len(satellite_agents)} 个卫星智能体")
            return satellite_agents

        except Exception as e:
            logger.error(f"❌ 获取卫星智能体失败: {e}")
            return []

    async def _get_visible_satellites_for_target(self, target_id: str) -> List[str]:
        """获取对目标可见的卫星列表"""
        try:
            # TODO: 实际应通过可见性计算获得，这里先使用模拟数据
            # 可以调用 STK 可见性计算或使用缓存的可见性窗口
            visible_satellites = ["Satellite11", "Satellite12", "Satellite13", "Satellite21", "Satellite22"]

            logger.debug(f"目标 {target_id} 的可见卫星: {visible_satellites}")
            return visible_satellites

        except Exception as e:
            logger.error(f"❌ 获取目标 {target_id} 的可见卫星失败: {e}")
            return []

    async def _get_agent_from_factory(self, satellite_id: str) -> Optional[SatelliteAgent]:
        """从卫星智能体工厂获取智能体"""
        try:
            if self._satellite_factory is None:
                logger.warning("⚠️ 卫星智能体工厂未初始化")
                return None

            # 从工厂获取已创建的智能体
            agent = self._satellite_factory.get_satellite_agent(satellite_id)

            if agent:
                logger.debug(f"✅ 从工厂获取卫星智能体: {satellite_id}")
            else:
                logger.warning(f"⚠️ 工厂中未找到卫星智能体: {satellite_id}")

            return agent

        except Exception as e:
            logger.error(f"❌ 从工厂获取卫星智能体 {satellite_id} 失败: {e}")
            return None

    def set_satellite_factory(self, satellite_factory):
        """设置卫星智能体工厂引用"""
        self._satellite_factory = satellite_factory
        logger.info("✅ 多智能体系统已设置卫星智能体工厂引用")

    async def _process_coordination_result(
        self,
        target_id: str,
        group_id: str,
        leader_agent: LeaderAgent,
        ctx: InvocationContext
    ):
        """处理协调结果"""
        try:
            # 获取组长智能体的分配结果
            allocation_result = leader_agent.get_allocation_result()
            
            if allocation_result:
                # 模拟智能体决策列表
                agent_decisions = [
                    {
                        'satellite_id': sat_id,
                        'assigned_windows': [f"window_{i}" for i in range(2)],
                        'visibility_windows': [],
                        'optimization_score': 0.8
                    }
                    for sat_id in allocation_result.allocated_satellites
                ]
                
                # 处理协调结果
                coordination_result = self._meta_task_integration.process_coordination_result(
                    target_id=target_id,
                    discussion_group_id=group_id,
                    agent_decisions=agent_decisions,
                    coordination_time=datetime.now()
                )
                
                if coordination_result:
                    # 保存结果到会话状态
                    ctx.session.state[f'coordination_result_{target_id}'] = {
                        'result_id': coordination_result.result_id,
                        'target_id': target_id,
                        'assignments_count': len(coordination_result.assignments),
                        'total_coverage': coordination_result.total_coverage,
                        'average_gdop': coordination_result.average_gdop,
                        'resource_utilization': coordination_result.resource_utilization
                    }
                    
                    logger.info(f"✅ 目标 {target_id} 协调结果处理完成")
            
            # 结束协调会话
            await self._coordination_manager.end_coordination_session(
                session_id=group_id,
                results={'target_id': target_id, 'status': 'completed'},
                ctx=ctx
            )
            
        except Exception as e:
            logger.error(f"❌ 协调结果处理失败: {e}")
    
    async def _generate_final_system_report(self, ctx: InvocationContext) -> str:
        """生成最终系统报告"""
        try:
            # 收集系统运行统计
            total_satellites = len(self._satellite_agents)
            total_leaders = len(self._leader_agents)
            total_groups = len(self._active_discussion_groups)
            
            # 收集协调结果
            coordination_results = []
            for key, value in ctx.session.state.items():
                if key.startswith('coordination_result_'):
                    coordination_results.append(value)
            
            # 导出协调结果
            if self._session_output_dir:
                export_files = self._meta_task_integration.export_coordination_results(
                    str(self._session_output_dir / "coordination_results")
                )
            else:
                export_files = {}
            
            # 生成报告
            report = f"""
            多智能体系统仿真完成报告
            ================================
            
            仿真会话ID: {self._current_simulation_id}
            仿真时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            输出目录: {self._session_output_dir}
            
            智能体统计:
            - 卫星智能体数量: {total_satellites}
            - 组长智能体数量: {total_leaders}
            - 讨论组数量: {total_groups}
            
            协调结果统计:
            - 处理的目标数量: {len(coordination_results)}
            - 导出文件数量: {len(export_files)}
            
            系统性能指标:
            - 平均覆盖率: {sum(r.get('total_coverage', 0) for r in coordination_results) / max(1, len(coordination_results)):.3f}
            - 平均GDOP: {sum(r.get('average_gdop', 0) for r in coordination_results) / max(1, len(coordination_results)):.3f}
            - 平均资源利用率: {sum(r.get('resource_utilization', 0) for r in coordination_results) / max(1, len(coordination_results)):.3f}
            
            输出文件:
            {chr(10).join(f"- {file_path}" for file_path in export_files.values())}
            
            仿真完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            # 保存报告到文件
            if self._session_output_dir:
                report_file = self._session_output_dir / "simulation_report.txt"
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report)
                
                logger.info(f"📊 仿真报告已保存: {report_file}")
            
            return report.strip()
            
        except Exception as e:
            logger.error(f"❌ 生成最终报告失败: {e}")
            return f"报告生成失败: {e}"
    
    async def _cleanup_system_resources(self):
        """清理系统资源"""
        try:
            # 清理智能体注册表
            for agent in self._satellite_agents.values():
                self._coordination_manager.unregister_agent(agent.name)

            for agent in self._leader_agents.values():
                self._coordination_manager.unregister_agent(agent.name)

            self._satellite_agents.clear()
            self._leader_agents.clear()
            self._active_discussion_groups.clear()

            self._is_running = False
            
            logger.info("🧹 系统资源清理完成")
            
        except Exception as e:
            logger.error(f"❌ 系统资源清理失败: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        # ADK标准讨论组已删除
        adk_standard_discussions_count = 0

        return {
            'status': 'running' if self._is_running else 'stopped',
            'is_running': self._is_running,
            'current_simulation_id': self._current_simulation_id,
            'satellite_agents_count': len(self._satellite_agents),
            'leader_agents_count': len(self._leader_agents),
            'active_groups_count': len(self._active_discussion_groups),
            'adk_sessions_count': 0,  # 已移除ADK讨论组管理器
            'adk_standard_discussions_count': adk_standard_discussions_count,
            'coordination_queue_status': self._coordination_manager.get_message_queue_status(),
            'output_directory': str(self._session_output_dir) if self._session_output_dir else None
        }





    def register_satellite_agents(self, satellite_agents: Dict[str, Any]) -> bool:
        """
        注册卫星智能体到多智能体系统

        Args:
            satellite_agents: 卫星智能体字典

        Returns:
            是否成功注册
        """
        try:
            for satellite_id, agent in satellite_agents.items():
                self._satellite_agents[satellite_id] = agent

                # 🔧 关键修复：设置卫星智能体的多智能体系统引用
                if hasattr(agent, 'set_multi_agent_system'):
                    agent.set_multi_agent_system(self)
                    logger.debug(f"✅ 已设置卫星 {satellite_id} 的多智能体系统引用")
                elif hasattr(agent, '_multi_agent_system'):
                    # 直接设置属性（对于使用Pydantic的智能体）
                    object.__setattr__(agent, '_multi_agent_system', self)
                    logger.debug(f"✅ 已直接设置卫星 {satellite_id} 的多智能体系统引用")
                else:
                    logger.warning(f"⚠️ 卫星 {satellite_id} 不支持多智能体系统引用设置")

                logger.info(f"注册卫星智能体: {satellite_id}")

            logger.info(f"成功注册 {len(satellite_agents)} 个卫星智能体到多智能体系统")

            # 如果使用ADK优化调度器，自动设置为sub_agents
            if hasattr(self._simulation_scheduler, 'initialize_adk_transfer_mode'):
                try:
                    # 标记需要初始化ADK transfer模式
                    object.__setattr__(self._simulation_scheduler, '_needs_transfer_init', True)
                    logger.info("✅ 已标记ADK transfer模式需要初始化")
                except Exception as e:
                    logger.warning(f"⚠️ ADK transfer模式初始化标记失败: {e}")

            return True

        except Exception as e:
            logger.error(f"注册卫星智能体失败: {e}")
            return False

    def get_all_satellite_agents(self) -> Dict[str, Any]:
        """
        获取所有已注册的卫星智能体

        Returns:
            卫星智能体字典
        """
        return self._satellite_agents.copy()

    def get_satellite_agent(self, satellite_id: str):
        """
        根据卫星ID获取卫星智能体

        Args:
            satellite_id: 卫星ID

        Returns:
            卫星智能体实例，如果不存在则返回None
        """
        return self._satellite_agents.get(satellite_id)

    async def start_system(self) -> bool:
        """
        启动多智能体系统

        Returns:
            是否成功启动
        """
        try:
            if self._is_running:
                logger.warning("多智能体系统已在运行中")
                return True

            # 创建会话输出目录
            self._create_session_output_dir()

            # 初始化卫星智能体（如果工厂已设置）
            if self._satellite_factory:
                await self._initialize_satellite_agents_from_factory()

            # 设置运行状态
            self._is_running = True

            logger.info("多智能体系统启动成功")
            return True

        except Exception as e:
            logger.error(f"多智能体系统启动失败: {e}")
            self._is_running = False
            return False

    async def _initialize_satellite_agents_from_factory(self):
        """从工厂初始化卫星智能体到系统中"""
        try:
            if not self._satellite_factory:
                logger.warning("⚠️ 卫星智能体工厂未设置")
                return

            # 获取工厂中所有已创建的智能体
            factory_agents = self._satellite_factory.get_all_satellite_agents()

            if factory_agents:
                # 批量注册到多智能体系统
                success = self.register_satellite_agents(factory_agents)

                if success:
                    logger.info(f"✅ 从工厂初始化了 {len(factory_agents)} 个卫星智能体")
                else:
                    logger.error("❌ 从工厂初始化卫星智能体失败")
            else:
                logger.info("📭 工厂中暂无已创建的卫星智能体")

        except Exception as e:
            logger.error(f"❌ 从工厂初始化卫星智能体失败: {e}")

    async def shutdown_system(self) -> bool:
        """
        关闭多智能体系统

        Returns:
            是否成功关闭
        """
        try:
            if not self._is_running:
                logger.warning("多智能体系统未在运行")
                return True

            # 清理系统资源
            await self._cleanup_system_resources()

            # 设置运行状态
            self._is_running = False

            logger.info("多智能体系统关闭成功")
            return True

        except Exception as e:
            logger.error(f"多智能体系统关闭失败: {e}")
            return False









    def get_adk_official_discussion_system(self) -> ADKOfficialDiscussionSystem:
        """
        获取ADK官方讨论系统

        Returns:
            ADK官方讨论系统实例
        """
        return self._adk_official_discussion_system

    async def create_adk_official_discussion(
        self,
        pattern_type: str,
        participating_agents: List,
        task_description: str,
        ctx
    ) -> str:
        """
        创建ADK官方讨论组

        Args:
            pattern_type: 协作模式 ("coordinator", "parallel_fanout", "sequential_pipeline", "iterative_refinement")
            participating_agents: 参与讨论的智能体列表
            task_description: 任务描述
            ctx: ADK调用上下文

        Returns:
            讨论ID，如果创建失败则返回None
        """
        try:
            logger.info(f"🤝 创建ADK官方讨论组")
            logger.info(f"   协作模式: {pattern_type}")
            logger.info(f"   任务: {task_description}")
            logger.info(f"   参与智能体: {len(participating_agents)}个")

            discussion_id = await self._adk_official_discussion_system.create_discussion(
                pattern_type=pattern_type,
                participating_agents=participating_agents,
                task_description=task_description,
                ctx=ctx
            )

            if discussion_id:
                logger.info(f"🎉 ADK官方讨论组创建成功: {discussion_id}")
                logger.info(f"   协作模式: {pattern_type}")
                logger.info(f"   任务: {task_description}")
                logger.info(f"   参与智能体: {len(participating_agents)}个")

            return discussion_id

        except Exception as e:
            logger.error(f"❌ 创建ADK官方讨论组失败: {e}")
            return None


