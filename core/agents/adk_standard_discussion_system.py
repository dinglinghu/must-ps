"""
ADK标准讨论组系统
严格按照ADK官方设计实现的多智能体讨论组系统

基于ADK官方文档：
- 使用Session State进行智能体间通信
- 使用ParallelAgent进行并发讨论
- 使用SequentialAgent进行顺序协调
- 使用LLM-Driven Delegation进行智能体调用
- 使用transfer_to_agent进行智能体转移
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, AsyncGenerator
from uuid import uuid4

# ADK框架导入
from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.sessions import Session
from google.adk.tools import transfer_to_agent, FunctionTool
from google.genai import types

# 导入全局Session管理器
from ..utils.adk_session_manager import get_adk_session_manager

logger = logging.getLogger(__name__)


class ADKDiscussionCoordinator(LlmAgent):
    """
    ADK讨论协调器 - 使用LLM-Driven Delegation
    
    这是符合ADK官方设计的讨论组协调器，使用LlmAgent作为基础，
    通过transfer_to_agent实现智能体间的协调。
    """
    
    def __init__(
        self,
        discussion_id: str,
        participating_agents: List[BaseAgent],
        task_description: str,
        model: str = "gemini-2.0-flash"
    ):
        """
        初始化ADK讨论协调器
        
        Args:
            discussion_id: 讨论ID
            participating_agents: 参与讨论的智能体列表
            task_description: 任务描述
            model: 使用的LLM模型
        """
        # 创建智能体描述信息
        agent_descriptions = []
        for agent in participating_agents:
            agent_descriptions.append(f"- {agent.name}: {getattr(agent, 'description', '智能体')}")
        
        instruction = f"""
你是一个多智能体讨论协调器，负责协调以下任务的讨论：

任务描述: {task_description}

参与的智能体:
{chr(10).join(agent_descriptions)}

你的职责：
1. 分析任务需求
2. 使用transfer_to_agent将任务分配给合适的智能体
3. 收集各智能体的意见和建议
4. 协调达成共识
5. 生成最终决策

请按照以下步骤进行：
1. 首先分析任务
2. 依次咨询每个智能体的意见
3. 整合所有意见
4. 做出最终决策

使用transfer_to_agent(agent_name="智能体名称")来转移控制权给其他智能体。
"""
        
        super().__init__(
            name=f"DiscussionCoordinator_{discussion_id}",
            model=model,
            description=f"讨论协调器 for {discussion_id}",
            instruction=instruction,
            sub_agents=participating_agents  # 设置子智能体以启用transfer_to_agent
        )

        # 使用私有属性存储额外信息
        self._discussion_id = discussion_id
        self._participating_agents = participating_agents
        self._task_description = task_description
        
        logger.info(f"✅ ADK讨论协调器创建: {discussion_id}")


class ADKParallelDiscussionGroup(ParallelAgent):
    """
    ADK并行讨论组 - 使用ParallelAgent进行并发讨论
    
    符合ADK官方设计的并行讨论组，所有智能体同时进行讨论，
    结果通过Session State进行共享。
    """
    
    def __init__(
        self,
        discussion_id: str,
        participating_agents: List[BaseAgent],
        task_description: str
    ):
        """
        初始化ADK并行讨论组
        
        Args:
            discussion_id: 讨论ID
            participating_agents: 参与讨论的智能体列表
            task_description: 任务描述
        """
        # 为每个智能体创建包装器，确保它们能访问Session State
        wrapped_agents = []
        for agent in participating_agents:
            wrapper = self._create_session_aware_wrapper(agent, discussion_id, task_description)
            wrapped_agents.append(wrapper)
        
        super().__init__(
            name=f"ParallelDiscussion_{discussion_id}",
            description=f"并行讨论组 for {discussion_id}",
            sub_agents=wrapped_agents
        )

        # 使用私有属性存储额外信息
        self._discussion_id = discussion_id
        self._task_description = task_description
        self._participating_agents = participating_agents
        
        logger.info(f"✅ ADK并行讨论组创建: {discussion_id}")
    
    def _create_session_aware_wrapper(
        self,
        agent: BaseAgent,
        discussion_id: str,
        task_description: str
    ) -> BaseAgent:
        """
        创建Session State感知的智能体包装器
        
        Args:
            agent: 原始智能体
            discussion_id: 讨论ID
            task_description: 任务描述
            
        Returns:
            包装后的智能体
        """
        class SessionAwareWrapper(BaseAgent):
            def __init__(self, wrapped_agent: BaseAgent, discussion_id: str, task_description: str):
                super().__init__(
                    name=f"{wrapped_agent.name}_SessionWrapper",
                    description=f"Session感知包装器 for {wrapped_agent.name}"
                )
                # 使用私有属性存储包装信息
                self._wrapped_agent = wrapped_agent
                self._discussion_id = discussion_id
                self._task_description = task_description
                self._state_key = f"discussion_{discussion_id}"
            
            async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
                """
                运行包装的智能体，管理Session State
                """
                try:
                    # 1. 初始化或更新Session State中的讨论状态
                    if self._state_key not in ctx.session.state:
                        ctx.session.state[self._state_key] = {
                            'discussion_id': self._discussion_id,
                            'task_description': self._task_description,
                            'status': 'active',
                            'participants': [],
                            'contributions': {},
                            'start_time': datetime.now().isoformat(),
                            'current_round': 1
                        }

                    discussion_state = ctx.session.state[self._state_key]

                    # 2. 添加当前智能体到参与者列表
                    if self._wrapped_agent.name not in discussion_state['participants']:
                        discussion_state['participants'].append(self._wrapped_agent.name)

                    # 3. 为智能体提供任务上下文
                    ctx.session.state[f"{self._wrapped_agent.name}_task"] = self._task_description
                    ctx.session.state[f"{self._wrapped_agent.name}_discussion_id"] = self._discussion_id

                    # 4. 运行原始智能体
                    contribution_content = ""
                    async for event in self._wrapped_agent._run_async_impl(ctx):
                        # 5. 收集智能体的贡献
                        if event.content and event.content.text:
                            contribution_content += event.content.text

                        yield event

                    # 6. 将智能体的贡献保存到Session State
                    discussion_state['contributions'][self._wrapped_agent.name] = {
                        'content': contribution_content,
                        'timestamp': datetime.now().isoformat(),
                        'agent_name': self._wrapped_agent.name
                    }

                    # 7. 更新Session State
                    ctx.session.state[self._state_key] = discussion_state

                    logger.info(f"✅ {self._wrapped_agent.name} 完成讨论贡献")
                    
                except Exception as e:
                    logger.error(f"❌ {self._wrapped_agent.name} 讨论包装器运行失败: {e}")
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part.from_text(f"Error: {e}")]),
                        actions=EventActions(escalate=True)
                    )
        
        return SessionAwareWrapper(agent, discussion_id, task_description)


class ADKSequentialDiscussionGroup(SequentialAgent):
    """
    ADK顺序讨论组 - 使用SequentialAgent进行顺序协调
    
    符合ADK官方设计的顺序讨论组，智能体按顺序进行讨论，
    每个智能体可以看到前面智能体的讨论结果。
    """
    
    def __init__(
        self,
        discussion_id: str,
        participating_agents: List[BaseAgent],
        task_description: str
    ):
        """
        初始化ADK顺序讨论组
        
        Args:
            discussion_id: 讨论ID
            participating_agents: 参与讨论的智能体列表（按讨论顺序）
            task_description: 任务描述
        """
        # 为每个智能体创建包装器
        wrapped_agents = []
        for i, agent in enumerate(participating_agents):
            wrapper = self._create_sequential_wrapper(agent, discussion_id, task_description, i)
            wrapped_agents.append(wrapper)
        
        super().__init__(
            name=f"SequentialDiscussion_{discussion_id}",
            description=f"顺序讨论组 for {discussion_id}",
            sub_agents=wrapped_agents
        )

        # 使用私有属性存储额外信息
        self._discussion_id = discussion_id
        self._task_description = task_description
        self._participating_agents = participating_agents
        
        logger.info(f"✅ ADK顺序讨论组创建: {discussion_id}")
    
    def _create_sequential_wrapper(
        self,
        agent: BaseAgent,
        discussion_id: str,
        task_description: str,
        order: int
    ) -> BaseAgent:
        """
        创建顺序讨论的智能体包装器
        
        Args:
            agent: 原始智能体
            discussion_id: 讨论ID
            task_description: 任务描述
            order: 讨论顺序
            
        Returns:
            包装后的智能体
        """
        class SequentialWrapper(BaseAgent):
            def __init__(self, wrapped_agent: BaseAgent, discussion_id: str, task_description: str, order: int):
                super().__init__(
                    name=f"{wrapped_agent.name}_Sequential_{order}",
                    description=f"顺序讨论包装器 for {wrapped_agent.name}"
                )
                # 使用私有属性存储包装信息
                self._wrapped_agent = wrapped_agent
                self._discussion_id = discussion_id
                self._task_description = task_description
                self._order = order
                self._state_key = f"sequential_discussion_{discussion_id}"
            
            async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
                """
                运行顺序讨论智能体
                """
                try:
                    # 1. 初始化或获取讨论状态
                    if self._state_key not in ctx.session.state:
                        ctx.session.state[self._state_key] = {
                            'discussion_id': self._discussion_id,
                            'task_description': self._task_description,
                            'status': 'active',
                            'sequence': [],
                            'current_order': 0,
                            'start_time': datetime.now().isoformat()
                        }

                    discussion_state = ctx.session.state[self._state_key]

                    # 2. 为智能体提供前面智能体的讨论结果
                    previous_contributions = []
                    for prev_contrib in discussion_state['sequence']:
                        if prev_contrib['order'] < self._order:
                            previous_contributions.append(prev_contrib)

                    # 3. 构建上下文信息
                    context_info = f"任务: {self._task_description}\n"
                    if previous_contributions:
                        context_info += "\n前面智能体的讨论结果:\n"
                        for contrib in previous_contributions:
                            context_info += f"- {contrib['agent_name']}: {contrib['content']}\n"

                    ctx.session.state[f"{self._wrapped_agent.name}_context"] = context_info

                    # 4. 运行原始智能体
                    contribution_content = ""
                    async for event in self._wrapped_agent._run_async_impl(ctx):
                        if event.content and event.content.text:
                            contribution_content += event.content.text
                        yield event

                    # 5. 记录当前智能体的贡献
                    discussion_state['sequence'].append({
                        'order': self._order,
                        'agent_name': self._wrapped_agent.name,
                        'content': contribution_content,
                        'timestamp': datetime.now().isoformat()
                    })

                    discussion_state['current_order'] = self._order + 1

                    # 6. 更新Session State
                    ctx.session.state[self._state_key] = discussion_state

                    logger.info(f"✅ {self._wrapped_agent.name} 完成顺序讨论 (order: {self._order})")
                    
                except Exception as e:
                    logger.error(f"❌ {self._wrapped_agent.name} 顺序讨论失败: {e}")
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part.from_text(f"Error: {e}")]),
                        actions=EventActions(escalate=True)
                    )
        
        return SequentialWrapper(agent, discussion_id, task_description, order)


class ADKStandardDiscussionSystem(BaseAgent):
    """
    ADK标准讨论系统
    
    完全符合ADK官方设计的讨论组系统，支持：
    1. LLM-Driven Delegation (使用transfer_to_agent)
    2. ParallelAgent并发讨论
    3. SequentialAgent顺序讨论
    4. Session State智能体间通信
    """
    
    def __init__(self, name: str = "ADKStandardDiscussionSystem"):
        """
        初始化ADK标准讨论系统
        
        Args:
            name: 系统名称
        """
        super().__init__(
            name=name,
            description="基于ADK官方标准的讨论组系统"
        )
        
        # 活跃的讨论组（存储在Session State中）
        self._active_discussions: Dict[str, BaseAgent] = {}
        
        logger.info("✅ ADK标准讨论系统初始化完成")

        # 启动生命周期监控
        self._lifecycle_monitor_task = None
        self._start_lifecycle_monitor()
    
    async def create_discussion(
        self,
        discussion_type: str,
        participating_agents: List[BaseAgent],
        task_description: str,
        ctx: InvocationContext
    ) -> str:
        """
        创建ADK标准讨论组
        
        Args:
            discussion_type: 讨论类型 ("coordinator", "parallel", "sequential")
            participating_agents: 参与讨论的智能体列表
            task_description: 任务描述
            ctx: ADK调用上下文
            
        Returns:
            讨论ID
        """
        try:
            discussion_id = f"adk_discussion_{uuid4().hex[:8]}"
            
            # 根据类型创建相应的讨论组
            if discussion_type == "coordinator":
                discussion_agent = ADKDiscussionCoordinator(
                    discussion_id, participating_agents, task_description
                )
            elif discussion_type == "parallel":
                discussion_agent = ADKParallelDiscussionGroup(
                    discussion_id, participating_agents, task_description
                )
            elif discussion_type == "sequential":
                discussion_agent = ADKSequentialDiscussionGroup(
                    discussion_id, participating_agents, task_description
                )
            elif discussion_type == "hierarchical":
                # 使用coordinator类型作为hierarchical的实现
                # 因为coordinator本身就是层次化的协调模式
                discussion_agent = ADKDiscussionCoordinator(
                    discussion_id, participating_agents, task_description
                )
            else:
                raise ValueError(f"不支持的讨论类型: {discussion_type}")
            
            # 存储讨论组
            self._active_discussions[discussion_id] = discussion_agent

            # 使用全局Session管理器记录讨论组信息
            session_manager = get_adk_session_manager()
            discussion_info = {
                'discussion_id': discussion_id,
                'type': discussion_type,
                'participants': [agent.name for agent in participating_agents],
                'task_description': task_description,
                'status': 'active',
                'created_time': datetime.now().isoformat(),
                'agent_class': discussion_agent.__class__.__name__
            }
            session_manager.add_adk_discussion(discussion_id, discussion_info)

            # 同时在传入的ctx中记录（如果有的话）
            if ctx and hasattr(ctx, 'session') and ctx.session:
                discussions_key = "adk_standard_discussions"
                if discussions_key not in ctx.session.state:
                    ctx.session.state[discussions_key] = {}
                ctx.session.state[discussions_key][discussion_id] = discussion_info

            # 添加创建时间用于生命周期管理
            discussion_agent._created_time = datetime.now()
            discussion_agent._discussion_id = discussion_id
            discussion_agent._discussion_type = discussion_type

            # 确保生命周期监控已启动
            await self._ensure_lifecycle_monitor_started()

            logger.info(f"✅ ADK标准讨论组创建成功: {discussion_id} (类型: {discussion_type})")
            return discussion_id
            
        except Exception as e:
            logger.error(f"❌ 创建ADK标准讨论组失败: {e}")
            raise

    async def complete_discussion(self, discussion_id: str, ctx: InvocationContext = None) -> bool:
        """
        完成并解散讨论组

        Args:
            discussion_id: 讨论ID
            ctx: ADK调用上下文

        Returns:
            是否成功解散
        """
        try:
            if discussion_id in self._active_discussions:
                # 获取讨论组智能体
                discussion_agent = self._active_discussions[discussion_id]

                # 通知参与者讨论完成
                await self._notify_participants_completion(discussion_agent, ctx)

                # 清理内存中的讨论组
                del self._active_discussions[discussion_id]

                # 从Session Manager中移除
                session_manager = get_adk_session_manager()
                session_manager.remove_adk_discussion(discussion_id)

                # 从ctx中移除（如果有的话）
                if ctx and hasattr(ctx, 'session') and ctx.session:
                    discussions_key = "adk_standard_discussions"
                    if discussions_key in ctx.session.state and discussion_id in ctx.session.state[discussions_key]:
                        del ctx.session.state[discussions_key][discussion_id]

                logger.info(f"✅ 讨论组 {discussion_id} 已解散")
                return True
            else:
                logger.warning(f"⚠️ 讨论组 {discussion_id} 不存在，无法解散")
                return False

        except Exception as e:
            logger.error(f"❌ 解散讨论组 {discussion_id} 失败: {e}")
            return False

    async def _notify_participants_completion(self, discussion_agent: BaseAgent, ctx: InvocationContext = None):
        """通知参与者讨论完成"""
        try:
            # 获取参与者列表
            participants = getattr(discussion_agent, '_participating_agents', [])

            for participant in participants:
                if hasattr(participant, 'on_discussion_completed'):
                    await participant.on_discussion_completed(discussion_agent._discussion_id)

            logger.info(f"✅ 已通知 {len(participants)} 个参与者讨论完成")

        except Exception as e:
            logger.error(f"❌ 通知参与者失败: {e}")

    def _start_lifecycle_monitor(self):
        """启动生命周期监控"""
        try:
            if self._lifecycle_monitor_task is None:
                # 检查是否有运行中的事件循环
                try:
                    loop = asyncio.get_running_loop()
                    self._lifecycle_monitor_task = loop.create_task(self._monitor_discussion_lifecycle())
                    logger.info("✅ 讨论组生命周期监控已启动")
                except RuntimeError:
                    # 没有运行中的事件循环，延迟启动
                    logger.info("📋 生命周期监控将在首次使用时启动")
                    self._lifecycle_monitor_task = None
        except Exception as e:
            logger.error(f"❌ 启动生命周期监控失败: {e}")

    async def _ensure_lifecycle_monitor_started(self):
        """确保生命周期监控已启动"""
        try:
            if self._lifecycle_monitor_task is None:
                self._lifecycle_monitor_task = asyncio.create_task(self._monitor_discussion_lifecycle())
                logger.info("✅ 讨论组生命周期监控已启动")
        except Exception as e:
            logger.error(f"❌ 确保生命周期监控启动失败: {e}")

    async def _monitor_discussion_lifecycle(self):
        """监控讨论组生命周期，自动清理超时的讨论组"""
        while True:
            try:
                current_time = datetime.now()
                expired_discussions = []

                # 检查所有活跃讨论组
                for discussion_id, discussion_agent in self._active_discussions.items():
                    # 检查是否超时（20分钟）
                    if hasattr(discussion_agent, '_created_time'):
                        elapsed = (current_time - discussion_agent._created_time).total_seconds()
                        if elapsed > 1200:  # 20分钟超时
                            expired_discussions.append(discussion_id)
                            logger.warning(f"⚠️ 讨论组 {discussion_id} 超时 ({elapsed:.1f}s)，将自动解散")

                # 清理超时的讨论组
                for discussion_id in expired_discussions:
                    await self.complete_discussion(discussion_id, None)

                # 每分钟检查一次
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"❌ 讨论组生命周期监控失败: {e}")
                await asyncio.sleep(60)
    
    def get_active_discussions(self, ctx: InvocationContext = None) -> Dict[str, Any]:
        """
        从Session State获取活跃的讨论组

        Args:
            ctx: ADK调用上下文（可选）

        Returns:
            活跃讨论组信息
        """
        # 优先从全局Session管理器获取
        session_manager = get_adk_session_manager()
        discussions = session_manager.get_adk_discussions()

        # 如果全局Session管理器没有数据，尝试从ctx获取
        if not discussions and ctx and hasattr(ctx, 'session') and ctx.session:
            discussions_key = "adk_standard_discussions"
            discussions = ctx.session.state.get(discussions_key, {})

        return discussions

    def get_discussion_count(self) -> int:
        """
        获取活跃讨论组数量

        Returns:
            活跃讨论组数量
        """
        # 从全局Session管理器获取数量
        session_manager = get_adk_session_manager()
        discussions = session_manager.get_adk_discussions()
        return len(discussions)
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        ADK标准讨论系统的运行逻辑
        """
        try:
            active_count = len(self._active_discussions)
            discussions_in_state = len(self.get_active_discussions(ctx))
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part.from_text(
                        f"ADK标准讨论系统运行中\n"
                        f"- 内存中活跃讨论: {active_count}\n"
                        f"- Session State中讨论: {discussions_in_state}\n"
                        f"- 支持类型: coordinator, parallel, sequential"
                    )
                ])
            )
            
        except Exception as e:
            logger.error(f"❌ ADK标准讨论系统运行失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part.from_text(f"Error: {e}")]),
                actions=EventActions(escalate=True)
            )
