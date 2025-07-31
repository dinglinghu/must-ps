"""
智能体模块
提供基于ADK框架的多智能体系统核心组件
"""

from .multi_agent_system import MultiAgentSystem
from .simulation_scheduler_agent import SimulationSchedulerAgent
from .satellite_agent import SatelliteAgent
from .leader_agent import LeaderAgent
# ADKStandardDiscussionSystem已删除，功能由ADKParallelDiscussionGroupManager替代

__all__ = [
    'MultiAgentSystem',
    'SimulationSchedulerAgent',
    'SatelliteAgent', 
    'LeaderAgent',
    # 'ADKStandardDiscussionSystem' - 已删除，功能由ADKParallelDiscussionGroupManager替代
]
