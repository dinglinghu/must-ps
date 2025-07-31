"""
增强的任务信息数据结构
基于现有TaskInfo扩展，保持向后兼容性
"""

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import json
import logging

logger = logging.getLogger(__name__)

@dataclass
class EnhancedTrajectoryPoint:
    """增强的轨迹点信息"""
    timestamp: datetime
    position: Dict[str, float]  # {'lat': float, 'lon': float, 'alt': float}
    velocity: Dict[str, float]  # {'vx': float, 'vy': float, 'vz': float}
    acceleration: Optional[Dict[str, float]]  # {'ax': float, 'ay': float, 'az': float}
    flight_phase: str  # "boost", "midcourse", "terminal"
    altitude_km: float
    velocity_kmps: float

@dataclass
class FlightPhaseInfo:
    """飞行阶段信息"""
    phase_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    altitude_range: Tuple[float, float]  # (min_alt, max_alt) km
    velocity_range: Tuple[float, float]  # (min_vel, max_vel) km/s
    observation_priority: float  # 0-1
    observation_difficulty: float  # 0-1

@dataclass
class ObservationRequirements:
    """观测需求信息"""
    min_observation_duration: float  # seconds
    preferred_observation_duration: float  # seconds
    min_elevation_angle: float  # degrees
    preferred_elevation_angle: float  # degrees
    required_sensors: List[str]
    preferred_sensors: List[str]
    min_observation_frequency: float  # observations per minute
    position_accuracy_requirement: float  # meters
    velocity_accuracy_requirement: float  # m/s

@dataclass
class VisibilityWindow:
    """可见性窗口信息"""
    satellite_id: str
    missile_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    max_elevation: float  # degrees
    min_elevation: float  # degrees
    avg_elevation: float  # degrees
    observation_quality: float  # 0-1
    geometric_dilution_of_precision: float  # GDOP
    sun_angle: float  # degrees
    earth_shadow: bool
    atmospheric_conditions: str  # "clear", "cloudy", "degraded"

@dataclass
class ResourceRequirements:
    """资源需求信息"""
    power_consumption: float  # watts
    storage_requirement: float  # MB
    communication_requirement: float  # Mbps
    thermal_impact: float  # temperature increase
    pointing_accuracy_required: float  # arcseconds
    slew_rate_required: float  # degrees per second

@dataclass
class ConflictInfo:
    """冲突信息"""
    conflict_id: str
    conflict_type: str  # "time", "resource", "geometric"
    severity: float  # 0-1
    conflicting_tasks: List[str]
    resolution_suggestions: List[Dict[str, Any]]

class EnhancedTaskInfo:
    """增强的任务信息类"""
    
    def __init__(self, 
                 task_id: str,
                 target_id: str,
                 start_time: datetime,
                 end_time: datetime,
                 priority: float,
                 status: str = 'pending',
                 metadata: Dict[str, Any] = None):
        
        # 基础信息（保持与原TaskInfo兼容）
        self.task_id = task_id
        self.target_id = target_id
        self.start_time = start_time
        self.end_time = end_time
        self.priority = priority
        self.status = status
        self.metadata = metadata or {}
        
        # 增强信息
        self.missile_info: Dict[str, Any] = {}
        self.trajectory_points: List[EnhancedTrajectoryPoint] = []
        self.flight_phases: List[FlightPhaseInfo] = []
        self.observation_requirements: Optional[ObservationRequirements] = None
        self.uncertainty_info: Dict[str, float] = {}
        
        # 可见性信息
        self.visibility_windows: List[VisibilityWindow] = []
        self.constellation_visibility: Dict[str, Any] = {}
        
        # 资源约束
        self.resource_requirements: Optional[ResourceRequirements] = None
        
        # 冲突信息
        self.potential_conflicts: List[ConflictInfo] = []
        
        # 增强标志
        self.is_enhanced = True
        self.enhancement_version = "1.0"
    
    def to_basic_task_info(self):
        """转换为基础TaskInfo格式（向后兼容）"""
        from .satellite_agent import TaskInfo
        
        # 将增强信息打包到metadata中
        enhanced_metadata = self.metadata.copy()
        enhanced_metadata.update({
            'is_enhanced': self.is_enhanced,
            'enhancement_version': self.enhancement_version,
            'missile_info': self.missile_info,
            'trajectory_points_count': len(self.trajectory_points),
            'flight_phases_count': len(self.flight_phases),
            'visibility_windows_count': len(self.visibility_windows),
            'has_observation_requirements': self.observation_requirements is not None,
            'has_resource_requirements': self.resource_requirements is not None,
            'conflicts_count': len(self.potential_conflicts)
        })
        
        return TaskInfo(
            task_id=self.task_id,
            target_id=self.target_id,
            start_time=self.start_time,
            end_time=self.end_time,
            priority=self.priority,
            status=self.status,
            metadata=enhanced_metadata
        )
    
    @classmethod
    def from_basic_task_info(cls, basic_task: 'TaskInfo') -> 'EnhancedTaskInfo':
        """从基础TaskInfo创建增强任务（向上兼容）"""
        enhanced_task = cls(
            task_id=basic_task.task_id,
            target_id=basic_task.target_id,
            start_time=basic_task.start_time,
            end_time=basic_task.end_time,
            priority=basic_task.priority,
            status=basic_task.status,
            metadata=basic_task.metadata
        )
        
        # 如果metadata中包含增强信息，则恢复
        if basic_task.metadata.get('is_enhanced'):
            enhanced_task.missile_info = basic_task.metadata.get('missile_info', {})
            # 其他增强信息的恢复逻辑...
        
        return enhanced_task
    
    def add_trajectory_point(self, trajectory_point: EnhancedTrajectoryPoint):
        """添加轨迹点"""
        self.trajectory_points.append(trajectory_point)
    
    def add_flight_phase(self, flight_phase: FlightPhaseInfo):
        """添加飞行阶段"""
        self.flight_phases.append(flight_phase)
    
    def add_visibility_window(self, visibility_window: VisibilityWindow):
        """添加可见性窗口"""
        self.visibility_windows.append(visibility_window)
    
    def add_conflict(self, conflict: ConflictInfo):
        """添加冲突信息"""
        self.potential_conflicts.append(conflict)
    
    def get_critical_flight_phases(self) -> List[FlightPhaseInfo]:
        """获取关键飞行阶段"""
        return [phase for phase in self.flight_phases 
                if phase.observation_priority > 0.7]
    
    def get_best_visibility_windows(self, satellite_id: str = None) -> List[VisibilityWindow]:
        """获取最佳可见性窗口"""
        windows = self.visibility_windows
        if satellite_id:
            windows = [w for w in windows if w.satellite_id == satellite_id]
        
        # 按观测质量排序
        return sorted(windows, key=lambda w: w.observation_quality, reverse=True)
    
    def calculate_total_observation_time(self, satellite_id: str = None) -> float:
        """计算总观测时间"""
        windows = self.visibility_windows
        if satellite_id:
            windows = [w for w in windows if w.satellite_id == satellite_id]
        
        return sum(w.duration_seconds for w in windows)
    
    def has_conflicts(self) -> bool:
        """检查是否有冲突"""
        return len(self.potential_conflicts) > 0
    
    def get_high_severity_conflicts(self) -> List[ConflictInfo]:
        """获取高严重性冲突"""
        return [conflict for conflict in self.potential_conflicts 
                if conflict.severity > 0.7]
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'task_id': self.task_id,
            'target_id': self.target_id,
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'priority': self.priority,
            'status': self.status,
            'metadata': self.metadata,
            'is_enhanced': self.is_enhanced,
            'enhancement_version': self.enhancement_version,
            'missile_info': self.missile_info,
            'trajectory_points_count': len(self.trajectory_points),
            'flight_phases_count': len(self.flight_phases),
            'visibility_windows_count': len(self.visibility_windows),
            'conflicts_count': len(self.potential_conflicts),
            'total_observation_time': self.calculate_total_observation_time(),
            'has_conflicts': self.has_conflicts()
        }
    
    def to_json(self) -> str:
        """转换为JSON格式"""
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)
    
    def __str__(self) -> str:
        return f"EnhancedTaskInfo(task_id={self.task_id}, target_id={self.target_id}, enhanced={self.is_enhanced})"
    
    def __repr__(self) -> str:
        return self.__str__()


class EnhancedTaskInfoBuilder:
    """增强任务信息构建器"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置构建器"""
        self._task_info = None
        return self
    
    def create_basic_task(self, task_id: str, target_id: str, 
                         start_time: datetime, end_time: datetime,
                         priority: float) -> 'EnhancedTaskInfoBuilder':
        """创建基础任务"""
        self._task_info = EnhancedTaskInfo(
            task_id=task_id,
            target_id=target_id,
            start_time=start_time,
            end_time=end_time,
            priority=priority
        )
        return self
    
    def add_missile_info(self, missile_info: Dict[str, Any]) -> 'EnhancedTaskInfoBuilder':
        """添加导弹信息"""
        if self._task_info:
            self._task_info.missile_info = missile_info
        return self
    
    def add_observation_requirements(self, requirements: ObservationRequirements) -> 'EnhancedTaskInfoBuilder':
        """添加观测需求"""
        if self._task_info:
            self._task_info.observation_requirements = requirements
        return self
    
    def add_resource_requirements(self, requirements: ResourceRequirements) -> 'EnhancedTaskInfoBuilder':
        """添加资源需求"""
        if self._task_info:
            self._task_info.resource_requirements = requirements
        return self
    
    def build(self) -> EnhancedTaskInfo:
        """构建增强任务信息"""
        if not self._task_info:
            raise ValueError("必须先创建基础任务")
        
        result = self._task_info
        self.reset()
        return result
