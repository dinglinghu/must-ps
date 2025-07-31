"""
协调管理器
负责多智能体间的协调、消息传递和状态同步
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, asdict
from enum import Enum

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.sessions import Session
from google.genai import types

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于协调管理器")


class MessageType(Enum):
    """消息类型枚举"""
    TASK_ASSIGNMENT = "task_assignment"
    COORDINATION_REQUEST = "coordination_request"
    STATUS_UPDATE = "status_update"
    DECISION_RESULT = "decision_result"
    GROUP_INVITATION = "group_invitation"
    GROUP_DISSOLUTION = "group_dissolution"


@dataclass
class AgentMessage:
    """智能体消息数据结构"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1-5, 5为最高优先级
    requires_response: bool = False
    response_timeout: Optional[int] = None  # 秒


@dataclass
class CoordinationSession:
    """协调会话数据结构"""
    session_id: str
    participants: List[str]
    coordinator: str
    topic: str
    status: str  # 'active', 'completed', 'failed', 'timeout'
    created_time: datetime
    messages: List[AgentMessage]
    results: Dict[str, Any]


class CoordinationManager:
    """
    协调管理器
    
    负责多智能体间的协调、消息传递和状态同步。
    基于ADK框架的Session State和Event系统实现。
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化协调管理器
        
        Args:
            config: 协调配置参数
        """
        self.config = config or {}
        
        # 注册的智能体
        self.registered_agents: Dict[str, BaseAgent] = {}
        
        # 活跃的协调会话
        self.active_sessions: Dict[str, CoordinationSession] = {}
        
        # 消息队列
        self.message_queue: List[AgentMessage] = []
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # 配置参数
        self.max_message_queue_size = self.config.get('max_message_queue_size', 1000)
        self.message_timeout = self.config.get('message_timeout', 300)  # 5分钟
        self.coordination_timeout = self.config.get('coordination_timeout', 1800)  # 30分钟
        
        # 初始化消息处理器
        self._initialize_message_handlers()
        
        # 运行状态
        self.is_running = False
        
        logger.info("🤝 协调管理器初始化完成")
    
    def _initialize_message_handlers(self):
        """初始化消息处理器"""
        self.message_handlers = {
            MessageType.TASK_ASSIGNMENT: self._handle_task_assignment,
            MessageType.COORDINATION_REQUEST: self._handle_coordination_request,
            MessageType.STATUS_UPDATE: self._handle_status_update,
            MessageType.DECISION_RESULT: self._handle_decision_result,
            MessageType.GROUP_INVITATION: self._handle_group_invitation,
            MessageType.GROUP_DISSOLUTION: self._handle_group_dissolution
        }
    
    def register_agent(self, agent: BaseAgent):
        """注册智能体"""
        self.registered_agents[agent.name] = agent
        logger.info(f"🤖 智能体 {agent.name} 已注册到协调管理器")
    
    def unregister_agent(self, agent_name: str):
        """注销智能体"""
        if agent_name in self.registered_agents:
            del self.registered_agents[agent_name]
            logger.info(f"🤖 智能体 {agent_name} 已从协调管理器注销")
    
    async def send_message(
        self,
        sender_id: str,
        receiver_id: str,
        message_type: MessageType,
        content: Dict[str, Any],
        priority: int = 1,
        requires_response: bool = False,
        response_timeout: Optional[int] = None
    ) -> str:
        """
        发送消息
        
        Args:
            sender_id: 发送者ID
            receiver_id: 接收者ID
            message_type: 消息类型
            content: 消息内容
            priority: 优先级
            requires_response: 是否需要响应
            response_timeout: 响应超时时间
            
        Returns:
            消息ID
        """
        message_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        message = AgentMessage(
            message_id=message_id,
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type=message_type,
            content=content,
            timestamp=datetime.now(),
            priority=priority,
            requires_response=requires_response,
            response_timeout=response_timeout
        )
        
        # 添加到消息队列
        self.message_queue.append(message)
        
        # 按优先级排序
        self.message_queue.sort(key=lambda x: (-x.priority, x.timestamp))
        
        # 限制队列大小
        if len(self.message_queue) > self.max_message_queue_size:
            self.message_queue = self.message_queue[:self.max_message_queue_size]
        
        logger.info(f"📨 消息 {message_id} 已发送: {sender_id} -> {receiver_id}")
        
        return message_id
    
    async def process_messages(self, ctx: InvocationContext) -> List[Event]:
        """处理消息队列"""
        events = []
        processed_messages = []
        
        for message in self.message_queue[:10]:  # 每次处理最多10条消息
            try:
                # 检查接收者是否存在
                if message.receiver_id not in self.registered_agents:
                    logger.warning(f"接收者 {message.receiver_id} 未注册，跳过消息 {message.message_id}")
                    processed_messages.append(message)
                    continue
                
                # 处理消息
                handler = self.message_handlers.get(message.message_type)
                if handler:
                    result = await handler(message, ctx)
                    
                    # 生成事件
                    event = Event(
                        author="CoordinationManager",
                        content=types.Content(parts=[types.Part(text=result)])
                    )
                    events.append(event)
                
                processed_messages.append(message)
                
            except Exception as e:
                logger.error(f"处理消息 {message.message_id} 失败: {e}")
                processed_messages.append(message)
        
        # 移除已处理的消息
        for msg in processed_messages:
            if msg in self.message_queue:
                self.message_queue.remove(msg)
        
        return events
    
    async def create_coordination_session(
        self,
        session_id: str,
        participants: List[str],
        coordinator: str,
        topic: str,
        ctx: InvocationContext
    ) -> bool:
        """
        创建协调会话
        
        Args:
            session_id: 会话ID
            participants: 参与者列表
            coordinator: 协调者
            topic: 协调主题
            ctx: 调用上下文
            
        Returns:
            创建是否成功
        """
        try:
            # 检查参与者是否都已注册
            for participant in participants:
                if participant not in self.registered_agents:
                    logger.error(f"参与者 {participant} 未注册")
                    return False
            
            # 创建协调会话
            session = CoordinationSession(
                session_id=session_id,
                participants=participants,
                coordinator=coordinator,
                topic=topic,
                status='active',
                created_time=datetime.now(),
                messages=[],
                results={}
            )
            
            self.active_sessions[session_id] = session
            
            # 保存到ADK会话状态
            ctx.session.state[f'coordination_session_{session_id}'] = asdict(session)
            
            # 向所有参与者发送邀请
            for participant in participants:
                await self.send_message(
                    sender_id="CoordinationManager",
                    receiver_id=participant,
                    message_type=MessageType.GROUP_INVITATION,
                    content={
                        'session_id': session_id,
                        'coordinator': coordinator,
                        'topic': topic,
                        'participants': participants
                    },
                    priority=3
                )
            
            logger.info(f"🤝 协调会话 {session_id} 创建成功，参与者: {participants}")
            return True
            
        except Exception as e:
            logger.error(f"创建协调会话失败: {e}")
            return False
    
    async def end_coordination_session(
        self,
        session_id: str,
        results: Dict[str, Any],
        ctx: InvocationContext
    ) -> bool:
        """结束协调会话"""
        try:
            if session_id not in self.active_sessions:
                logger.warning(f"协调会话 {session_id} 不存在")
                return False
            
            session = self.active_sessions[session_id]
            session.status = 'completed'
            session.results = results
            
            # 更新ADK会话状态
            ctx.session.state[f'coordination_session_{session_id}'] = asdict(session)
            
            # 通知所有参与者
            for participant in session.participants:
                await self.send_message(
                    sender_id="CoordinationManager",
                    receiver_id=participant,
                    message_type=MessageType.GROUP_DISSOLUTION,
                    content={
                        'session_id': session_id,
                        'results': results,
                        'status': 'completed'
                    },
                    priority=3
                )
            
            # 移除活跃会话
            del self.active_sessions[session_id]
            
            logger.info(f"🤝 协调会话 {session_id} 已结束")
            return True
            
        except Exception as e:
            logger.error(f"结束协调会话失败: {e}")
            return False
    
    # 消息处理器实现
    async def _handle_task_assignment(self, message: AgentMessage, ctx: InvocationContext) -> str:
        """处理任务分配消息"""
        try:
            content = message.content
            task_info = content.get('task_info', {})
            
            # 将任务信息保存到接收者的状态中
            receiver_key = f"agent_{message.receiver_id}_tasks"
            if receiver_key not in ctx.session.state:
                ctx.session.state[receiver_key] = []
            
            ctx.session.state[receiver_key].append({
                'task_id': task_info.get('task_id'),
                'assigned_time': datetime.now().isoformat(),
                'sender': message.sender_id,
                'status': 'assigned'
            })
            
            return f"任务分配消息已处理: {message.sender_id} -> {message.receiver_id}"
            
        except Exception as e:
            return f"任务分配消息处理失败: {e}"
    
    async def _handle_coordination_request(self, message: AgentMessage, ctx: InvocationContext) -> str:
        """处理协调请求消息"""
        try:
            content = message.content
            request_type = content.get('request_type')
            
            # 根据请求类型处理
            if request_type == 'join_discussion':
                group_id = content.get('group_id')
                # 处理加入讨论组请求
                return f"协调请求已处理: 加入讨论组 {group_id}"
            
            elif request_type == 'resource_check':
                # 处理资源检查请求
                return "协调请求已处理: 资源状态检查"
            
            else:
                return f"未知的协调请求类型: {request_type}"
                
        except Exception as e:
            return f"协调请求处理失败: {e}"
    
    async def _handle_status_update(self, message: AgentMessage, ctx: InvocationContext) -> str:
        """处理状态更新消息"""
        try:
            content = message.content
            status_type = content.get('status_type')
            status_data = content.get('status_data', {})
            
            # 更新智能体状态
            status_key = f"agent_{message.sender_id}_status"
            ctx.session.state[status_key] = {
                'type': status_type,
                'data': status_data,
                'timestamp': datetime.now().isoformat()
            }
            
            return f"状态更新已处理: {message.sender_id} - {status_type}"
            
        except Exception as e:
            return f"状态更新处理失败: {e}"
    
    async def _handle_decision_result(self, message: AgentMessage, ctx: InvocationContext) -> str:
        """处理决策结果消息"""
        try:
            content = message.content
            decision_id = content.get('decision_id')
            result = content.get('result', {})
            
            # 保存决策结果
            decision_key = f"decision_{decision_id}"
            ctx.session.state[decision_key] = {
                'sender': message.sender_id,
                'result': result,
                'timestamp': datetime.now().isoformat()
            }
            
            return f"决策结果已处理: {decision_id}"
            
        except Exception as e:
            return f"决策结果处理失败: {e}"
    
    async def _handle_group_invitation(self, message: AgentMessage, ctx: InvocationContext) -> str:
        """处理讨论组邀请消息"""
        try:
            content = message.content
            session_id = content.get('session_id')
            
            # 自动接受邀请（在实际实现中可能需要智能体确认）
            invitation_key = f"agent_{message.receiver_id}_invitations"
            if invitation_key not in ctx.session.state:
                ctx.session.state[invitation_key] = []
            
            ctx.session.state[invitation_key].append({
                'session_id': session_id,
                'status': 'accepted',
                'timestamp': datetime.now().isoformat()
            })
            
            return f"讨论组邀请已处理: {session_id}"
            
        except Exception as e:
            return f"讨论组邀请处理失败: {e}"
    
    async def _handle_group_dissolution(self, message: AgentMessage, ctx: InvocationContext) -> str:
        """处理讨论组解散消息"""
        try:
            content = message.content
            session_id = content.get('session_id')
            
            # 清理相关状态
            dissolution_key = f"agent_{message.receiver_id}_dissolutions"
            if dissolution_key not in ctx.session.state:
                ctx.session.state[dissolution_key] = []
            
            ctx.session.state[dissolution_key].append({
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
            
            return f"讨论组解散已处理: {session_id}"
            
        except Exception as e:
            return f"讨论组解散处理失败: {e}"
    
    def get_agent_status(self, agent_name: str, ctx: InvocationContext) -> Optional[Dict[str, Any]]:
        """获取智能体状态"""
        status_key = f"agent_{agent_name}_status"
        return ctx.session.state.get(status_key)
    
    def get_coordination_sessions(self) -> List[CoordinationSession]:
        """获取所有协调会话"""
        return list(self.active_sessions.values())
    
    def get_message_queue_status(self) -> Dict[str, Any]:
        """获取消息队列状态"""
        return {
            'queue_size': len(self.message_queue),
            'max_size': self.max_message_queue_size,
            'active_sessions': len(self.active_sessions),
            'registered_agents': len(self.registered_agents)
        }
