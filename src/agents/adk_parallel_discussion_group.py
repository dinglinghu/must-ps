"""
ADK并行讨论组管理器
基于ADK Parallel Fan-Out/Gather Pattern实现的讨论组管理器

严格按照ADK官方设计：
- 使用ParallelAgent进行并发讨论
- 使用Session State进行状态管理
- 支持智能体包装器确保Session State同步
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4

# ADK框架导入
from google.adk.agents import BaseAgent, ParallelAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.sessions import Session
from google.genai import types

# 导入全局Session管理器
from ..utils.adk_session_manager import get_adk_session_manager

logger = logging.getLogger(__name__)


class ADKParallelDiscussionGroupManager(BaseAgent):
    """
    ADK并行讨论组管理器
    基于ADK Parallel Fan-Out/Gather Pattern实现
    """
    
    def __init__(self, config_manager=None):
        super().__init__(
            name="ADKParallelDiscussionGroupManager",
            description="基于ADK ParallelAgent的并行讨论组管理器"
        )
        
        self.config_manager = config_manager
        self._active_discussions: Dict[str, ParallelAgent] = {}
        self._session_manager = get_adk_session_manager()
        
        logger.info("✅ ADK并行讨论组管理器初始化完成")
    
    async def create_discussion_group(
        self,
        task_info: Dict[str, Any],
        participating_agents: List[BaseAgent],
        coordination_type: str = "parallel"
    ) -> Optional[str]:
        """
        创建ADK并行讨论组
        
        Args:
            task_info: 任务信息
            participating_agents: 参与讨论的智能体列表
            coordination_type: 协调类型（默认为parallel）
            
        Returns:
            讨论组ID，如果创建失败则返回None
        """
        try:
            discussion_id = f"parallel_discussion_{uuid4().hex[:8]}"
            
            # 创建并行讨论组
            discussion_group = ADKParallelDiscussionGroup(
                discussion_id=discussion_id,
                participating_agents=participating_agents,
                task_description=task_info.get('description', '并行讨论任务')
            )
            
            # 注册到活跃讨论组
            self._active_discussions[discussion_id] = discussion_group
            
            # 记录到Session State
            discussion_info = {
                'discussion_id': discussion_id,
                'type': 'parallel',
                'task_info': task_info,
                'participating_agents': [agent.name for agent in participating_agents],
                'created_time': datetime.now().isoformat(),
                'status': 'active'
            }
            
            self._session_manager.add_adk_discussion(discussion_id, discussion_info)
            
            logger.info(f"✅ ADK并行讨论组创建成功: {discussion_id}")
            return discussion_id
            
        except Exception as e:
            logger.error(f"❌ 创建ADK并行讨论组失败: {e}")
            return None
    
    def get_active_discussions(self) -> Dict[str, Dict[str, Any]]:
        """获取活跃的讨论组信息"""
        discussions = {}
        for discussion_id, discussion_group in self._active_discussions.items():
            discussions[discussion_id] = {
                'id': discussion_id,
                'type': 'parallel',
                'name': discussion_group.name,
                'description': discussion_group.description,
                'status': 'active',
                'created_time': getattr(discussion_group, '_created_time', datetime.now()).isoformat()
            }
        return discussions
    
    async def dissolve_discussion_group(self, discussion_id: str) -> bool:
        """
        解散讨论组
        
        Args:
            discussion_id: 讨论组ID
            
        Returns:
            是否成功解散
        """
        try:
            if discussion_id in self._active_discussions:
                # 从活跃讨论组中移除
                del self._active_discussions[discussion_id]
                
                # 更新Session State
                discussion_info = self._session_manager.get_session_state_value(
                    "adk_standard_discussions", {}
                ).get(discussion_id)
                
                if discussion_info:
                    discussion_info['status'] = 'dissolved'
                    discussion_info['dissolved_time'] = datetime.now().isoformat()
                    self._session_manager.add_adk_discussion(discussion_id, discussion_info)
                
                logger.info(f"✅ ADK并行讨论组已解散: {discussion_id}")
                return True
            else:
                logger.warning(f"⚠️ 讨论组不存在: {discussion_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 解散讨论组失败: {e}")
            return False


class ADKParallelDiscussionGroup(ParallelAgent):
    """
    ADK并行讨论组
    基于ADK ParallelAgent实现的并发讨论组
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
        # 为每个智能体创建包装器
        wrapped_agents = []
        for agent in participating_agents:
            wrapper = self._create_session_aware_wrapper(agent, discussion_id, task_description)
            wrapped_agents.append(wrapper)
        
        super().__init__(
            name=f"ParallelDiscussion_{discussion_id}",
            description=f"并行讨论组 for {discussion_id}",
            sub_agents=wrapped_agents
        )
        
        self._discussion_id = discussion_id
        self._task_description = task_description
        self._participating_agents = participating_agents
        self._created_time = datetime.now()
        
        logger.info(f"✅ ADK并行讨论组创建: {discussion_id}")
    
    def _create_session_aware_wrapper(self, agent: BaseAgent, discussion_id: str, task_description: str):
        """创建Session State感知的智能体包装器"""
        
        class SessionAwareWrapper(BaseAgent):
            def __init__(self, wrapped_agent: BaseAgent, discussion_id: str, task_description: str):
                super().__init__(
                    name=f"Wrapper_{wrapped_agent.name}",
                    description=f"Session感知包装器 for {wrapped_agent.name}"
                )
                self._wrapped_agent = wrapped_agent
                self._discussion_id = discussion_id
                self._task_description = task_description
            
            async def run(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
                """运行包装的智能体，确保Session State同步"""
                try:
                    # 在Session State中记录讨论参与
                    if ctx.session:
                        discussion_key = f"discussion_{self._discussion_id}"
                        if discussion_key not in ctx.session.state:
                            ctx.session.state[discussion_key] = {
                                'task_description': self._task_description,
                                'participants': [],
                                'messages': []
                            }
                        
                        # 添加参与者
                        if self._wrapped_agent.name not in ctx.session.state[discussion_key]['participants']:
                            ctx.session.state[discussion_key]['participants'].append(self._wrapped_agent.name)
                    
                    # 运行原始智能体
                    async for event in self._wrapped_agent.run(ctx):
                        # 在Session State中记录消息
                        if ctx.session and hasattr(event, 'content'):
                            discussion_key = f"discussion_{self._discussion_id}"
                            ctx.session.state[discussion_key]['messages'].append({
                                'author': self._wrapped_agent.name,
                                'content': str(event.content),
                                'timestamp': datetime.now().isoformat()
                            })
                        
                        yield event
                        
                except Exception as e:
                    logger.error(f"❌ {self._wrapped_agent.name} 讨论包装器运行失败: {e}")
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part.from_text(f"Error: {e}")]),
                        actions=EventActions(escalate=True)
                    )
        
        return SessionAwareWrapper(agent, discussion_id, task_description)
