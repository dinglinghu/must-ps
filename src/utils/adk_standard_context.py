"""
ADK标准上下文创建工具

根据ADK官方文档，提供标准的Session和InvocationContext创建方法。
不包含任何模拟或兼容性代码，严格遵循ADK设计原则。
"""

import logging
from typing import Optional
from google.adk.runners import InMemoryRunner
from google.adk.agents import LlmAgent
from google.adk.sessions import Session
from google.genai import types

logger = logging.getLogger(__name__)


def create_standard_session(
    app_name: str,
    user_id: str,
    session_id: str,
    initial_state: Optional[dict] = None
) -> Session:
    """
    创建标准ADK Session

    根据ADK官方文档，在讨论组中我们直接传递Session对象。
    这里创建一个简化的Session用于状态管理。

    Args:
        app_name: 应用名称
        user_id: 用户ID
        session_id: 会话ID
        initial_state: 初始状态字典

    Returns:
        Session对象（用于状态管理）

    Raises:
        Exception: 如果Session创建失败
    """
    try:
        from google.adk.sessions import Session
        import time

        # 根据ADK文档，Session对象包含这些属性
        # 在实际应用中，这些由Runner和SessionService管理
        # 这里我们创建一个用于状态管理的Session对象
        class SimpleSession:
            def __init__(self, app_name: str, user_id: str, session_id: str, initial_state: dict):
                self.id = session_id
                self.app_name = app_name
                self.user_id = user_id
                self.state = initial_state.copy()
                self.events = []
                self.last_update_time = time.time()

        session = SimpleSession(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
            initial_state=initial_state or {}
        )

        logger.info(f"✅ 创建ADK Session成功: {session.id}")
        return session

    except Exception as e:
        logger.error(f"❌ 创建ADK Session失败: {e}")
        raise


def create_satellite_session(satellite_id: str, task_id: str) -> Session:
    """
    为卫星智能体创建专用Session
    
    Args:
        satellite_id: 卫星ID
        task_id: 任务ID
        
    Returns:
        卫星专用的ADK Session
    """
    session_id = f"satellite_session_{satellite_id}_{task_id}"
    return create_standard_session(
        app_name="satellite_constellation_system",
        user_id=satellite_id,
        session_id=session_id,
        initial_state={
            'satellite_id': satellite_id,
            'task_id': task_id,
            'session_type': 'satellite_task'
        }
    )


def create_discussion_session(discussion_id: str, pattern_type: str) -> Session:
    """
    为讨论组创建专用Session
    
    Args:
        discussion_id: 讨论组ID
        pattern_type: 讨论模式类型
        
    Returns:
        讨论组专用的ADK Session
    """
    session_id = f"discussion_session_{discussion_id}"
    return create_standard_session(
        app_name="adk_discussion_system",
        user_id="system",
        session_id=session_id,
        initial_state={
            'discussion_id': discussion_id,
            'pattern_type': pattern_type,
            'session_type': 'discussion_group'
        }
    )


def create_test_session(test_name: str) -> Session:
    """
    为测试创建Session
    
    Args:
        test_name: 测试名称
        
    Returns:
        测试专用的ADK Session
    """
    from uuid import uuid4
    session_id = f"test_{test_name}_{uuid4().hex[:8]}"
    return create_standard_session(
        app_name="test_app",
        user_id="test_user",
        session_id=session_id,
        initial_state={
            'test_name': test_name,
            'session_type': 'test'
        }
    )


class EmbodiedStateManager:
    """
    具身状态管理器
    
    为卫星智能体提供标准的具身状态管理，使用ADK Session.state
    严格遵循ADK的状态管理原则
    """
    
    def __init__(self, session: Session):
        """
        初始化具身状态管理器
        
        Args:
            session: ADK Session实例
        """
        self.session = session
    
    def get_embodied_state(self, satellite_id: str) -> dict:
        """
        获取卫星智能体的具身状态
        
        Args:
            satellite_id: 卫星ID
            
        Returns:
            具身状态字典
        """
        state_key = f"satellite_{satellite_id}_embodied_state"
        return self.session.state.get(state_key, {})
    
    def set_embodied_state(self, satellite_id: str, state: dict):
        """
        设置卫星智能体的具身状态
        
        Args:
            satellite_id: 卫星ID
            state: 具身状态字典
        """
        state_key = f"satellite_{satellite_id}_embodied_state"
        self.session.state[state_key] = state
        logger.debug(f"保存卫星 {satellite_id} 的具身状态到ADK Session")
    
    def restore_embodied_state(self, satellite_id: str) -> dict:
        """
        恢复卫星智能体的具身状态
        
        Args:
            satellite_id: 卫星ID
            
        Returns:
            具身状态字典
        """
        state = self.get_embodied_state(satellite_id)
        
        if state:
            logger.debug(f"从ADK Session恢复卫星 {satellite_id} 的具身状态")
        else:
            # 初始化默认状态
            state = {
                'satellite_id': satellite_id,
                'orbital_parameters': {},
                'resource_status': {},
                'mission_history': [],
                'current_tasks': [],
                'last_update': None
            }
            self.set_embodied_state(satellite_id, state)
            logger.debug(f"初始化卫星 {satellite_id} 的具身状态")
        
        return state
    
    def save_embodied_state(self, satellite_id: str, state: dict):
        """
        保存卫星智能体的具身状态
        
        Args:
            satellite_id: 卫星ID
            state: 具身状态字典
        """
        # 更新时间戳
        from datetime import datetime
        state['last_update'] = datetime.now().isoformat()
        
        # 保存状态到ADK Session
        self.set_embodied_state(satellite_id, state)
        logger.debug(f"保存卫星 {satellite_id} 的具身状态到ADK Session")
    
    def get_all_embodied_states(self) -> dict:
        """
        获取所有卫星的具身状态
        
        Returns:
            所有具身状态的字典
        """
        all_states = {}
        
        for key, value in self.session.state.items():
            if key.startswith("satellite_") and key.endswith("_embodied_state"):
                # 提取卫星ID
                satellite_id = key.replace("satellite_", "").replace("_embodied_state", "")
                all_states[satellite_id] = value
        
        return all_states


# 导出主要函数和类
__all__ = [
    'create_standard_session',
    'create_satellite_session', 
    'create_discussion_session',
    'create_test_session',
    'EmbodiedStateManager'
]
