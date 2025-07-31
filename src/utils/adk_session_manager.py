"""
ADK Session State管理器
用于在整个应用中共享ADK Session State
"""

import logging
from typing import Dict, Any, Optional
from google.adk.sessions import Session

logger = logging.getLogger(__name__)


class ADKSessionManager:
    """
    ADK Session State管理器
    
    提供全局的Session State访问，确保UI和讨论组系统
    能够访问相同的Session State数据。
    """
    
    _instance: Optional['ADKSessionManager'] = None
    _global_session: Optional[Session] = None
    
    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化ADK Session管理器"""
        if not hasattr(self, '_initialized'):
            self._initialized = True
            self._create_global_session()
            logger.info("✅ ADK Session管理器初始化完成")
    
    def _create_global_session(self):
        """创建全局Session"""
        try:
            self._global_session = Session(
                id="global_adk_session",
                app_name="adk_multi_agent_system",
                user_id="system"
            )
            logger.info("✅ 全局ADK Session创建成功")
        except Exception as e:
            logger.error(f"❌ 创建全局ADK Session失败: {e}")
            self._global_session = None
    
    def get_global_session(self) -> Optional[Session]:
        """
        获取全局Session
        
        Returns:
            全局Session实例，如果创建失败则返回None
        """
        return self._global_session
    
    def get_session_state(self) -> Dict[str, Any]:
        """
        获取Session State
        
        Returns:
            Session State字典
        """
        if self._global_session:
            return self._global_session.state
        return {}
    
    def set_session_state(self, key: str, value: Any):
        """
        设置Session State
        
        Args:
            key: 状态键
            value: 状态值
        """
        if self._global_session:
            self._global_session.state[key] = value
            logger.debug(f"✅ Session State已更新: {key}")
        else:
            logger.warning("⚠️ 全局Session未初始化，无法设置状态")
    
    def get_session_state_value(self, key: str, default: Any = None) -> Any:
        """
        获取Session State中的特定值
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值
        """
        if self._global_session:
            return self._global_session.state.get(key, default)
        return default
    
    def update_session_state(self, updates: Dict[str, Any]):
        """
        批量更新Session State
        
        Args:
            updates: 要更新的状态字典
        """
        if self._global_session:
            self._global_session.state.update(updates)
            logger.debug(f"✅ Session State批量更新: {len(updates)}个键")
        else:
            logger.warning("⚠️ 全局Session未初始化，无法批量更新状态")
    
    def clear_session_state(self):
        """清空Session State"""
        if self._global_session:
            self._global_session.state.clear()
            logger.info("✅ Session State已清空")
        else:
            logger.warning("⚠️ 全局Session未初始化，无法清空状态")
    
    def get_adk_discussions(self) -> Dict[str, Any]:
        """
        获取ADK标准讨论组
        
        Returns:
            ADK标准讨论组字典
        """
        discussions_key = "adk_standard_discussions"
        return self.get_session_state_value(discussions_key, {})
    
    def add_adk_discussion(self, discussion_id: str, discussion_info: Dict[str, Any]):
        """
        添加ADK标准讨论组
        
        Args:
            discussion_id: 讨论ID
            discussion_info: 讨论信息
        """
        discussions_key = "adk_standard_discussions"
        discussions = self.get_session_state_value(discussions_key, {})
        discussions[discussion_id] = discussion_info
        self.set_session_state(discussions_key, discussions)
        logger.info(f"✅ ADK讨论组已添加: {discussion_id}")
    
    def remove_adk_discussion(self, discussion_id: str):
        """
        移除ADK标准讨论组
        
        Args:
            discussion_id: 讨论ID
        """
        discussions_key = "adk_standard_discussions"
        discussions = self.get_session_state_value(discussions_key, {})
        if discussion_id in discussions:
            del discussions[discussion_id]
            self.set_session_state(discussions_key, discussions)
            logger.info(f"✅ ADK讨论组已移除: {discussion_id}")
        else:
            logger.warning(f"⚠️ ADK讨论组不存在: {discussion_id}")
    
    def get_discussion_state(self, discussion_id: str) -> Dict[str, Any]:
        """
        获取特定讨论组的状态
        
        Args:
            discussion_id: 讨论ID
            
        Returns:
            讨论组状态字典
        """
        state_key = f"discussion_{discussion_id}"
        return self.get_session_state_value(state_key, {})
    
    def update_discussion_state(self, discussion_id: str, state_updates: Dict[str, Any]):
        """
        更新特定讨论组的状态
        
        Args:
            discussion_id: 讨论ID
            state_updates: 状态更新
        """
        state_key = f"discussion_{discussion_id}"
        current_state = self.get_session_state_value(state_key, {})
        current_state.update(state_updates)
        self.set_session_state(state_key, current_state)
        logger.debug(f"✅ 讨论组状态已更新: {discussion_id}")
    
    def get_sequential_discussion_state(self, discussion_id: str) -> Dict[str, Any]:
        """
        获取顺序讨论组的状态
        
        Args:
            discussion_id: 讨论ID
            
        Returns:
            顺序讨论组状态字典
        """
        state_key = f"sequential_discussion_{discussion_id}"
        return self.get_session_state_value(state_key, {})
    
    def update_sequential_discussion_state(self, discussion_id: str, state_updates: Dict[str, Any]):
        """
        更新顺序讨论组的状态
        
        Args:
            discussion_id: 讨论ID
            state_updates: 状态更新
        """
        state_key = f"sequential_discussion_{discussion_id}"
        current_state = self.get_session_state_value(state_key, {})
        current_state.update(state_updates)
        self.set_session_state(state_key, current_state)
        logger.debug(f"✅ 顺序讨论组状态已更新: {discussion_id}")
    
    def get_all_discussion_states(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有讨论组状态
        
        Returns:
            所有讨论组状态字典
        """
        all_states = {}
        session_state = self.get_session_state()
        
        for key, value in session_state.items():
            if key.startswith('discussion_') or key.startswith('sequential_discussion_'):
                all_states[key] = value
        
        return all_states
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取Session State统计信息
        
        Returns:
            统计信息字典
        """
        session_state = self.get_session_state()
        adk_discussions = self.get_adk_discussions()
        all_discussion_states = self.get_all_discussion_states()
        
        return {
            'total_session_keys': len(session_state),
            'adk_discussions_count': len(adk_discussions),
            'discussion_states_count': len(all_discussion_states),
            'session_initialized': self._global_session is not None,
            'session_id': self._global_session.id if self._global_session else None
        }


# 全局实例
_global_session_manager = None

def get_adk_session_manager() -> ADKSessionManager:
    """
    获取全局ADK Session管理器实例
    
    Returns:
        ADK Session管理器实例
    """
    global _global_session_manager
    if _global_session_manager is None:
        _global_session_manager = ADKSessionManager()
    return _global_session_manager
