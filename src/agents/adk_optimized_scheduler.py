"""
ADK优化的仿真调度智能体
使用ADK transfer_to_agent机制替代传统轮询机制
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from .adk_transfer_integration import ADKTransferIntegratedScheduler
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)


class ADKOptimizedScheduler(ADKTransferIntegratedScheduler):
    """
    ADK优化的仿真调度智能体
    
    这是新的默认调度器，完全基于ADK transfer_to_agent机制：
    1. 默认启用ADK transfer模式
    2. 自动初始化卫星智能体为sub_agents
    3. 使用transfer_to_agent替代所有轮询机制
    4. 通过session.state实现实时通信
    5. 支持立即规划触发
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化ADK优化调度器
        """
        # 调用父类初始化
        super().__init__(*args, **kwargs)

        # 默认启用transfer模式
        object.__setattr__(self, '_transfer_enabled', True)
        object.__setattr__(self, '_auto_initialize_transfer', True)

        # 重写工具集，集成传统调度器的所有工具
        self.tools = self._create_optimized_tools()

        logger.info("🚀 ADK优化调度器初始化完成（默认启用transfer模式）")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        重写运行方法，自动初始化ADK transfer模式
        """
        try:
            # 检查是否需要初始化ADK transfer模式
            needs_init = getattr(self, '_needs_transfer_init', False) or (self._auto_initialize_transfer and not self._transfer_enabled)

            if needs_init:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="🔄 自动初始化ADK transfer模式...")])
                )

                success = await self.initialize_adk_transfer_mode()
                if success:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text="✅ ADK transfer模式初始化成功")])
                    )
                    # 清除初始化标记
                    object.__setattr__(self, '_needs_transfer_init', False)
                else:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text="⚠️ ADK transfer模式初始化失败，使用传统模式")])
                    )
            
            # 设置session.state引用
            if ctx and hasattr(ctx, 'session') and hasattr(ctx.session, 'state'):
                self.set_session_state(ctx.session.state)
                
                # 初始化session.state结构
                if 'task_results' not in ctx.session.state:
                    ctx.session.state['task_results'] = {}
                if 'planning_trigger' not in ctx.session.state:
                    ctx.session.state['planning_trigger'] = False
                if 'pending_delegations' not in ctx.session.state:
                    ctx.session.state['pending_delegations'] = {}
                
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="✅ ADK transfer session.state已初始化")])
                )
            
            # 显示当前模式
            mode = "ADK Transfer模式" if self._transfer_enabled else "传统模式"
            satellite_count = len(getattr(self, 'sub_agents', []))
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"🎯 运行模式: {mode}，管理 {satellite_count} 个卫星智能体")])
            )
            
            # 调用父类的运行逻辑
            async for event in super()._run_async_impl(ctx):
                yield event
                
        except Exception as e:
            logger.error(f"❌ ADK优化调度器运行失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"❌ 运行失败: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def start_optimized_planning_cycle(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        启动优化的规划周期，使用ADK transfer机制
        """
        try:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="🚀 启动ADK优化的滚动规划周期")])
            )
            
            if not self._transfer_enabled:
                # 如果transfer未启用，尝试初始化
                success = await self.initialize_adk_transfer_mode()
                if not success:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text="⚠️ ADK transfer初始化失败，回退到传统模式")])
                    )
                    # 调用父类的传统规划方法
                    async for event in super()._run_async_impl(ctx):
                        yield event
                    return
            
            # 使用ADK transfer的优化规划流程
            planning_cycle = 1
            max_cycles = 5  # 最大规划周期数
            
            while planning_cycle <= max_cycles:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"📋 开始第 {planning_cycle} 轮ADK优化规划")])
                )
                
                # 1. 生成元任务集
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="🎯 生成元任务集...")])
                )
                
                # 获取活跃导弹目标
                missile_targets = await self._get_active_missile_targets()
                
                if missile_targets:
                    # 为每个目标生成元任务并使用ADK transfer委托
                    for missile_info in missile_targets:
                        missile_id = missile_info.get('missile_id', 'unknown')
                        
                        yield Event(
                            author=self.name,
                            content=types.Content(parts=[types.Part(text=f"📡 为导弹 {missile_id} 委托任务（ADK transfer）")])
                        )
                        
                        # 使用ADK transfer委托任务
                        result = await self._delegate_missile_task_with_transfer(ctx, missile_info)
                        
                        yield Event(
                            author=self.name,
                            content=types.Content(parts=[types.Part(text=f"✅ 导弹 {missile_id} 任务委托结果: {result}")])
                        )
                
                # 2. 等待任务完成（使用ADK transfer机制）
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="⏳ 等待ADK transfer任务完成...")])
                )
                
                await self._wait_for_all_tasks_completion()
                
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"✅ 第 {planning_cycle} 轮规划完成")])
                )
                
                # 3. 检查是否需要继续规划
                if not missile_targets:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text="🎯 无活跃目标，规划周期结束")])
                    )
                    break
                
                planning_cycle += 1
                
                # 短暂等待后开始下一轮
                await asyncio.sleep(1)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="🎉 ADK优化规划周期完成")]),
                actions=EventActions(escalate=True)
            )
            
        except Exception as e:
            logger.error(f"❌ ADK优化规划周期失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"❌ 规划周期失败: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def _delegate_missile_task_with_transfer(self, ctx: InvocationContext, missile_info: Dict[str, Any]) -> str:
        """
        使用ADK transfer委托导弹跟踪任务
        """
        try:
            missile_id = missile_info.get('missile_id', 'unknown')
            
            # 构建任务信息
            task_info = {
                'task_id': f"missile_tracking_{missile_id}_{uuid4().hex[:8]}",
                'task_type': 'missile_tracking',
                'description': f"跟踪导弹 {missile_id}",
                'target_id': missile_id,
                'priority': 0.8,
                'metadata': {
                    'missile_info': missile_info,
                    'requires_discussion_group': True,
                    'delegation_time': datetime.now().isoformat()
                }
            }
            
            # 使用ADK transfer委托任务
            result = await self.delegate_task_with_transfer(ctx, task_info)
            
            logger.info(f"📡 导弹 {missile_id} 任务委托结果: {result}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 委托导弹任务失败: {e}")
            return f"委托失败: {e}"

    async def _get_active_missile_targets(self) -> List[Dict[str, Any]]:
        """获取活跃的导弹目标"""
        try:
            # 这里应该从STK或其他数据源获取活跃导弹
            # 暂时返回模拟数据
            return [
                {
                    'missile_id': 'Missile_001',
                    'launch_time': datetime.now().isoformat(),
                    'launch_position': {'lat': 40.0, 'lon': 116.0, 'alt': 0},
                    'status': 'active'
                }
            ]
        except Exception as e:
            logger.error(f"❌ 获取活跃导弹目标失败: {e}")
            return []

    def get_optimization_status(self) -> Dict[str, Any]:
        """获取优化状态"""
        return {
            'scheduler_type': 'ADKOptimizedScheduler',
            'transfer_enabled': getattr(self, '_transfer_enabled', False),
            'auto_initialize': getattr(self, '_auto_initialize_transfer', False),
            'satellite_count': len(getattr(self, 'sub_agents', [])),
            'pending_tasks': len(getattr(self, '_pending_tasks', set())),
            'session_state_available': hasattr(self, '_session_state') and self._session_state is not None
        }

    def _create_optimized_tools(self) -> List[FunctionTool]:
        """创建ADK优化的工具集，继承传统调度器的所有功能"""
        tools = []

        # 1. 完整系统初始化工具（继承传统功能）
        async def initialize_complete_system() -> str:
            """初始化完整的卫星智能体系统（ADK优化版本）"""
            try:
                logger.info("🎯 ADK优化工具：开始初始化完整系统...")

                # 调用父类的系统初始化方法
                result = await super(ADKOptimizedScheduler, self)._create_stk_scenario_internal()

                if "❌" in result:
                    return result

                # ADK优化：自动初始化transfer模式
                if not self._transfer_enabled:
                    success = await self.initialize_adk_transfer_mode()
                    if success:
                        result += "\n✅ ADK transfer模式已启用"
                    else:
                        result += "\n⚠️ ADK transfer模式启用失败，使用传统模式"

                return result

            except Exception as e:
                logger.error(f"❌ ADK优化系统初始化失败: {e}")
                return f"❌ ADK优化系统初始化失败: {e}"

        tools.append(FunctionTool(func=initialize_complete_system))

        # 2. ADK优化的滚动规划工具
        async def start_optimized_rolling_planning() -> str:
            """启动ADK优化的滚动规划"""
            try:
                logger.info("🚀 启动ADK优化的滚动规划...")

                if not self._transfer_enabled:
                    # 如果transfer未启用，尝试初始化
                    success = await self.initialize_adk_transfer_mode()
                    if not success:
                        return "⚠️ ADK transfer初始化失败，回退到传统滚动规划"

                # 使用ADK transfer的优化规划流程
                planning_result = "🚀 ADK优化滚动规划已启动\n"

                # 获取活跃导弹目标
                active_missiles = await self._get_active_missiles_with_trajectories()

                if active_missiles:
                    planning_result += f"📡 发现 {len(active_missiles)} 个活跃导弹目标\n"

                    # 使用ADK transfer委托任务
                    for missile_info in active_missiles:
                        missile_id = missile_info.get('missile_id', 'unknown')

                        # 构建任务信息
                        task_info = {
                            'task_id': f"missile_tracking_{missile_id}_{uuid4().hex[:8]}",
                            'task_type': 'missile_tracking',
                            'description': f"跟踪导弹 {missile_id}",
                            'target_id': missile_id,
                            'priority': 0.8,
                            'metadata': {
                                'missile_info': missile_info,
                                'requires_discussion_group': True,
                                'delegation_time': datetime.now().isoformat()
                            }
                        }

                        # 使用ADK transfer委托任务
                        result = await self.delegate_task_with_transfer(None, task_info)
                        planning_result += f"📡 导弹 {missile_id} 任务委托: {result}\n"
                else:
                    planning_result += "📊 当前无活跃导弹目标，执行常规巡逻任务\n"

                return planning_result

            except Exception as e:
                logger.error(f"❌ ADK优化滚动规划失败: {e}")
                return f"❌ ADK优化滚动规划失败: {e}"

        tools.append(FunctionTool(func=start_optimized_rolling_planning))

        # 3. 继承传统调度器的其他工具
        try:
            # 获取父类的工具
            parent_tools = super()._create_tools()

            # 过滤掉重复的工具，保留传统功能
            for tool in parent_tools:
                if hasattr(tool, 'func') and hasattr(tool.func, '__name__'):
                    func_name = tool.func.__name__
                    # 跳过已经优化的工具
                    if func_name not in ['initialize_complete_system']:
                        tools.append(tool)
                        logger.debug(f"✅ 继承传统工具: {func_name}")

        except Exception as e:
            logger.warning(f"⚠️ 继承传统工具失败: {e}")

        logger.info(f"🔧 ADK优化工具集创建完成，共 {len(tools)} 个工具")
        return tools

    async def _get_active_missiles_with_trajectories(self) -> List[Dict[str, Any]]:
        """获取活跃导弹及其轨迹信息（继承传统方法）"""
        try:
            # 调用父类的方法获取活跃导弹
            if hasattr(super(), '_get_active_missiles_with_trajectories'):
                return await super()._get_active_missiles_with_trajectories()
            else:
                # 如果父类方法不存在，使用简化版本
                return await self._get_active_missile_targets()
        except Exception as e:
            logger.error(f"❌ 获取活跃导弹轨迹失败: {e}")
            return []

    async def _create_stk_scenario_internal(self) -> str:
        """创建STK场景（ADK优化版本）"""
        try:
            logger.info("🛰️ ADK优化：创建STK场景...")

            # 调用父类的STK场景创建方法
            result = await super()._create_stk_scenario_internal()

            # ADK优化：场景创建后自动初始化transfer模式
            if "✅" in result and not self._transfer_enabled:
                success = await self.initialize_adk_transfer_mode()
                if success:
                    result += "\n🚀 ADK transfer模式已自动启用"

                    # 获取创建的卫星智能体数量
                    satellite_count = len(getattr(self, 'sub_agents', []))
                    result += f"\n📡 已将 {satellite_count} 个卫星智能体设置为sub_agents"

            return result

        except Exception as e:
            logger.error(f"❌ ADK优化STK场景创建失败: {e}")
            return f"❌ ADK优化STK场景创建失败: {e}"
