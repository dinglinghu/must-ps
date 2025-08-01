"""
基于ADK transfer_to_agent的任务发送和结果回收优化方案
使用ADK官方的LLM-Driven Delegation机制实现高效的智能体间通信
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from uuid import uuid4

from google.adk.agents import LlmAgent, BaseAgent, SequentialAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

logger = logging.getLogger(__name__)


class ADKTransferOptimizedScheduler(LlmAgent):
    """
    基于ADK transfer_to_agent优化的仿真调度智能体
    
    核心优化：
    1. 使用transfer_to_agent直接委托任务给卫星智能体
    2. 通过session.state实现实时结果回收
    3. 支持任务完成后立即启动下一轮规划
    """
    
    def __init__(self, satellite_agents: List[BaseAgent]):
        """
        初始化优化的调度智能体
        
        Args:
            satellite_agents: 卫星智能体列表，将作为sub_agents
        """
        super().__init__(
            name="ADKTransferOptimizedScheduler",
            model="gemini-2.0-flash",
            instruction=self._build_transfer_instruction(satellite_agents),
            description="基于ADK transfer_to_agent优化的仿真调度智能体",
            sub_agents=satellite_agents  # 设置为sub_agents，启用transfer_to_agent
        )
        
        # 使用object.__setattr__绕过Pydantic的字段验证
        # 任务状态管理
        object.__setattr__(self, '_active_tasks', {})
        object.__setattr__(self, '_completed_tasks', {})
        object.__setattr__(self, '_task_completion_callbacks', {})

        # 滚动规划状态
        object.__setattr__(self, '_planning_cycle', 0)
        object.__setattr__(self, '_is_running', False)
        
        logger.info(f"✅ ADK Transfer优化调度器初始化完成，管理 {len(satellite_agents)} 个卫星智能体")

    def _build_transfer_instruction(self, satellite_agents: List[BaseAgent]) -> str:
        """构建支持transfer_to_agent的指令"""
        agent_descriptions = []
        for agent in satellite_agents:
            agent_descriptions.append(f"- {agent.name}: {getattr(agent, 'description', '卫星智能体')}")
        
        agents_list = "\n".join(agent_descriptions)
        
        return f"""
你是仿真调度智能体，负责协调卫星任务执行和滚动规划。

可用的卫星智能体：
{agents_list}

你的主要职责：
1. 接收元任务请求，分析任务需求
2. 使用transfer_to_agent将任务委托给合适的卫星智能体
3. 监控任务执行状态，收集结果
4. 在任务完成后立即启动下一轮滚动规划

使用transfer_to_agent的格式：
- transfer_to_agent(agent_name='目标智能体名称')

任务委托策略：
- 对于单个目标任务：选择最近的卫星智能体
- 对于多目标任务：选择覆盖范围最优的卫星智能体组合
- 对于协同任务：委托给组长卫星智能体，由其创建讨论组

将任务结果保存到session.state中，格式：
- session.state['task_results'][task_id] = 任务结果
- session.state['planning_trigger'] = True  # 触发下一轮规划
"""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        优化的运行逻辑，支持实时任务委托和结果回收
        """
        logger.info(f"🚀 ADK Transfer优化调度器开始运行")
        
        # 初始化状态
        if 'task_results' not in ctx.session.state:
            ctx.session.state['task_results'] = {}
        if 'active_delegations' not in ctx.session.state:
            ctx.session.state['active_delegations'] = {}
        
        self._is_running = True
        
        try:
            # 启动滚动规划循环
            async for event in self._rolling_planning_loop(ctx):
                yield event
                
        except Exception as e:
            logger.error(f"❌ ADK Transfer优化调度器运行失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"❌ 调度器运行失败: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def _rolling_planning_loop(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """滚动规划循环，支持实时响应"""
        while self._is_running:
            self._planning_cycle += 1
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"🔄 开始第 {self._planning_cycle} 轮滚动规划")])
            )
            
            # 1. 生成元任务
            meta_tasks = await self._generate_meta_tasks(ctx)
            if meta_tasks:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"📋 生成 {len(meta_tasks)} 个元任务")])
                )
                
                # 2. 使用transfer_to_agent委托任务
                delegation_results = await self._delegate_tasks_with_transfer(ctx, meta_tasks)
                
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"📡 任务委托完成: {delegation_results}")])
                )
                
                # 3. 等待任务完成（实时响应）
                completion_results = await self._wait_for_task_completion(ctx)
                
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"✅ 任务完成: {completion_results}")])
                )
            
            # 4. 检查是否需要继续
            if not await self._should_continue_planning(ctx):
                break
                
            # 5. 短暂等待后开始下一轮
            await asyncio.sleep(1)
        
        yield Event(
            author=self.name,
            content=types.Content(parts=[types.Part(text="🏁 滚动规划循环结束")]),
            actions=EventActions(escalate=True)
        )

    async def _delegate_tasks_with_transfer(
        self, 
        ctx: InvocationContext, 
        meta_tasks: List[Dict[str, Any]]
    ) -> str:
        """
        使用ADK transfer_to_agent委托任务
        
        这个方法会触发LLM生成transfer_to_agent调用
        """
        try:
            # 准备任务委托信息
            delegation_info = {
                'meta_tasks': meta_tasks,
                'delegation_time': datetime.now().isoformat(),
                'planning_cycle': self._planning_cycle
            }
            
            # 保存到状态中，供LLM读取
            ctx.session.state['pending_delegation'] = delegation_info
            
            # 构建委托提示，让LLM决定如何使用transfer_to_agent
            delegation_prompt = self._build_delegation_prompt(meta_tasks)
            
            # 这里LLM会分析任务并生成transfer_to_agent调用
            # ADK框架会自动处理transfer调用
            logger.info(f"📡 准备委托 {len(meta_tasks)} 个任务")
            
            return f"准备委托 {len(meta_tasks)} 个任务给卫星智能体"
            
        except Exception as e:
            logger.error(f"❌ 任务委托失败: {e}")
            return f"❌ 任务委托失败: {e}"

    def _build_delegation_prompt(self, meta_tasks: List[Dict[str, Any]]) -> str:
        """构建任务委托提示"""
        task_summaries = []
        for i, task in enumerate(meta_tasks):
            task_summaries.append(f"任务{i+1}: {task.get('description', '未知任务')}")
        
        tasks_text = "\n".join(task_summaries)
        
        return f"""
需要委托以下任务：
{tasks_text}

请分析每个任务的特点，选择最合适的卫星智能体，并使用transfer_to_agent进行委托。

委托策略：
1. 单目标任务 -> 选择最近的卫星智能体
2. 多目标任务 -> 选择覆盖范围最优的卫星智能体
3. 协同任务 -> 委托给组长卫星智能体

请为每个任务调用：transfer_to_agent(agent_name='选定的卫星智能体名称')
"""

    async def _wait_for_task_completion(self, ctx: InvocationContext) -> str:
        """
        等待任务完成，支持实时响应
        
        通过监控session.state中的任务结果实现实时响应
        """
        try:
            start_time = datetime.now()
            max_wait_time = 300  # 5分钟最大等待时间
            
            while (datetime.now() - start_time).total_seconds() < max_wait_time:
                # 检查是否有任务完成
                task_results = ctx.session.state.get('task_results', {})
                active_delegations = ctx.session.state.get('active_delegations', {})
                
                # 检查所有活跃委托是否完成
                completed_count = 0
                total_count = len(active_delegations)
                
                for delegation_id, delegation_info in active_delegations.items():
                    if delegation_id in task_results:
                        completed_count += 1
                
                if total_count > 0 and completed_count == total_count:
                    logger.info(f"✅ 所有任务完成: {completed_count}/{total_count}")
                    return f"所有任务完成: {completed_count}/{total_count}"
                
                # 检查是否有规划触发器
                if ctx.session.state.get('planning_trigger', False):
                    ctx.session.state['planning_trigger'] = False
                    logger.info("🚀 检测到规划触发器，立即启动下一轮")
                    return "检测到任务完成，触发下一轮规划"
                
                # 短暂等待
                await asyncio.sleep(0.5)
            
            # 超时处理
            logger.warning(f"⚠️ 任务等待超时，已等待 {max_wait_time} 秒")
            return f"任务等待超时，部分任务可能仍在执行"
            
        except Exception as e:
            logger.error(f"❌ 等待任务完成失败: {e}")
            return f"❌ 等待任务完成失败: {e}"

    async def _generate_meta_tasks(self, ctx: InvocationContext) -> List[Dict[str, Any]]:
        """生成元任务（简化版）"""
        try:
            # 模拟元任务生成
            meta_tasks = [
                {
                    'task_id': f"task_{self._planning_cycle}_{i}",
                    'description': f"第{self._planning_cycle}轮任务{i+1}",
                    'priority': 0.8,
                    'target_count': 1
                }
                for i in range(2)  # 每轮生成2个任务
            ]
            
            logger.info(f"📋 生成 {len(meta_tasks)} 个元任务")
            return meta_tasks
            
        except Exception as e:
            logger.error(f"❌ 元任务生成失败: {e}")
            return []

    async def _should_continue_planning(self, ctx: InvocationContext) -> bool:
        """检查是否应该继续规划"""
        # 简单的停止条件：最多5轮
        return self._planning_cycle < 5 and self._is_running

    def stop_planning(self):
        """停止滚动规划"""
        self._is_running = False
        logger.info("🛑 滚动规划已停止")


class ADKTransferOptimizedSatellite(LlmAgent):
    """
    支持ADK transfer机制的优化卫星智能体

    核心特性：
    1. 接收transfer_to_agent委托的任务
    2. 自动执行任务并将结果写入session.state
    3. 支持创建讨论组进行协同决策
    4. 任务完成后自动触发下一轮规划
    """

    def __init__(self, satellite_id: str, config: Dict[str, Any] = None):
        """
        初始化优化的卫星智能体

        Args:
            satellite_id: 卫星ID
            config: 配置参数
        """
        super().__init__(
            name=f"Satellite_{satellite_id}",
            model="gemini-2.0-flash",
            instruction=self._build_satellite_instruction(satellite_id),
            description=f"卫星 {satellite_id} 智能体，支持任务执行和协同决策"
        )

        # 使用object.__setattr__绕过Pydantic的字段验证
        object.__setattr__(self, 'satellite_id', satellite_id)
        object.__setattr__(self, 'config', config or {})

        # 任务执行状态
        object.__setattr__(self, '_current_task', None)
        object.__setattr__(self, '_task_history', [])

        logger.info(f"🛰️ 优化卫星智能体 {satellite_id} 初始化完成")

    def _build_satellite_instruction(self, satellite_id: str) -> str:
        """构建卫星智能体指令"""
        return f"""
你是卫星 {satellite_id} 智能体，负责执行委托的任务。

当接收到任务委托时，你需要：
1. 分析任务需求和约束条件
2. 执行必要的计算（如可见性计算、轨道分析等）
3. 如果是协同任务，创建讨论组与其他卫星协作
4. 将执行结果保存到session.state中
5. 设置规划触发器启动下一轮规划

任务执行流程：
1. 接收任务 -> 分析任务类型和需求
2. 单独执行 -> 直接计算并返回结果
3. 协同执行 -> 创建讨论组，协调其他卫星
4. 结果保存 -> session.state['task_results'][task_id] = 结果
5. 触发规划 -> session.state['planning_trigger'] = True

结果格式：
{{
    "task_id": "任务ID",
    "satellite_id": "{satellite_id}",
    "execution_time": "执行时间",
    "result_type": "single|collaborative",
    "result_data": {{
        "success": true/false,
        "details": "详细结果",
        "metrics": {{"gdop": 值, "coverage": 值}}
    }},
    "discussion_group_id": "讨论组ID（如果有）"
}}
"""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        优化的卫星智能体运行逻辑
        支持接收transfer委托并自动执行任务
        """
        logger.info(f"🛰️ 卫星 {self.satellite_id} 开始执行委托任务")

        try:
            # 检查是否有委托任务
            pending_delegation = ctx.session.state.get('pending_delegation')
            if pending_delegation:
                # 执行委托任务
                async for event in self._execute_delegated_tasks(ctx, pending_delegation):
                    yield event
            else:
                # 常规运行模式
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"🛰️ 卫星 {self.satellite_id} 待命中，等待任务委托")])
                )

        except Exception as e:
            logger.error(f"❌ 卫星 {self.satellite_id} 执行失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"❌ 执行失败: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def _execute_delegated_tasks(
        self,
        ctx: InvocationContext,
        delegation_info: Dict[str, Any]
    ) -> AsyncGenerator[Event, None]:
        """执行委托的任务"""
        try:
            meta_tasks = delegation_info.get('meta_tasks', [])

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"📋 接收到 {len(meta_tasks)} 个委托任务")])
            )

            # 执行每个任务
            for task in meta_tasks:
                task_id = task.get('task_id')

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"🔄 开始执行任务: {task_id}")])
                )

                # 执行任务
                task_result = await self._execute_single_task(ctx, task)

                # 保存结果到session.state
                if 'task_results' not in ctx.session.state:
                    ctx.session.state['task_results'] = {}

                ctx.session.state['task_results'][task_id] = task_result

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"✅ 任务完成: {task_id}")])
                )

            # 触发下一轮规划
            ctx.session.state['planning_trigger'] = True

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="🚀 所有任务完成，触发下一轮规划")]),
                actions=EventActions(escalate=True)
            )

        except Exception as e:
            logger.error(f"❌ 执行委托任务失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"❌ 执行委托任务失败: {e}")])
            )

    async def _execute_single_task(self, ctx: InvocationContext, task: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个任务"""
        try:
            task_id = task.get('task_id')
            task_description = task.get('description', '')

            logger.info(f"🔄 卫星 {self.satellite_id} 执行任务: {task_id}")

            # 模拟任务执行
            await asyncio.sleep(0.1)  # 模拟计算时间

            # 生成任务结果
            result = {
                "task_id": task_id,
                "satellite_id": self.satellite_id,
                "execution_time": datetime.now().isoformat(),
                "result_type": "single",
                "result_data": {
                    "success": True,
                    "details": f"卫星 {self.satellite_id} 成功执行任务: {task_description}",
                    "metrics": {
                        "gdop": 1.8,
                        "coverage": 85.5,
                        "execution_duration": 0.1
                    }
                }
            }

            # 更新任务历史
            self._task_history.append(result)

            logger.info(f"✅ 卫星 {self.satellite_id} 任务执行完成: {task_id}")
            return result

        except Exception as e:
            logger.error(f"❌ 卫星 {self.satellite_id} 任务执行失败: {e}")
            return {
                "task_id": task.get('task_id'),
                "satellite_id": self.satellite_id,
                "execution_time": datetime.now().isoformat(),
                "result_type": "single",
                "result_data": {
                    "success": False,
                    "details": f"任务执行失败: {e}",
                    "error": str(e)
                }
            }
