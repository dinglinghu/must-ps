"""
现实预警星座多智能体滚动任务规划系统核心模块 v2.0.0

提供基于ADK框架的多智能体协同、滚动任务规划、甘特图可视化等核心功能
"""

# 版本信息
__version__ = "2.0.0"
__author__ = "现实预警星座多智能体系统开发团队"
__description__ = "基于ADK框架的分布式多智能体协同任务规划系统"

# 核心组件导入
from .agents import (
    MultiAgentSystem,
    SimulationSchedulerAgent,
    SatelliteAgent,
    LeaderAgent,
    ADKStandardDiscussionSystem
)

from .planning import (
    RollingPlanningCycleManager,
    MissileTargetDistributor,
    OptimizationCalculator
)

from .constellation import (
    ConstellationManager,
    SatelliteAgentFactory
)

from .visualization import (
    HierarchicalGanttManager,
    AdvancedGanttGenerator
)

# 主要类导出
__all__ = [
    # 智能体相关
    'MultiAgentSystem',
    'SimulationSchedulerAgent', 
    'SatelliteAgent',
    'LeaderAgent',
    'ADKStandardDiscussionSystem',
    
    # 规划相关
    'RollingPlanningCycleManager',
    'MissileTargetDistributor',
    'OptimizationCalculator',
    
    # 星座相关
    'ConstellationManager',
    'SatelliteAgentFactory',
    
    # 可视化相关
    'HierarchicalGanttManager',
    'AdvancedGanttGenerator'
]
