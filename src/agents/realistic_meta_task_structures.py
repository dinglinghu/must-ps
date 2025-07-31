"""
现实预警星座场景下的元任务数据结构
基于实际约束条件设计的多智能体任务规划数据格式
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Tuple, Optional
import json
import logging

logger = logging.getLogger(__name__)

# ==================== 基础数据结构 ====================

@dataclass
class Position3D:
    """三维位置"""
    lat: float  # 纬度
    lon: float  # 经度
    alt: float  # 高度 (km)

@dataclass
class Velocity3D:
    """三维速度"""
    vx: float  # km/s
    vy: float  # km/s
    vz: float  # km/s

# ==================== 地面发送的数据结构 ====================

@dataclass
class TrajectoryKeyPoint:
    """关键轨迹点"""
    timestamp: datetime
    position: Position3D
    estimated_velocity: float  # km/s
    flight_phase: str  # "boost", "midcourse", "terminal"
    confidence_level: float  # 0-1

@dataclass
class FlightPhasePredict:
    """飞行阶段预测"""
    phase_name: str
    estimated_start_time: datetime
    estimated_end_time: datetime
    estimated_altitude_range: Tuple[float, float]  # km
    observation_priority: float  # 0-1
    tracking_difficulty: float  # 0-1

@dataclass
class PredictedTrajectory:
    """预测轨迹信息"""
    launch_position: Position3D
    predicted_impact_position: Position3D
    launch_time: datetime
    estimated_flight_duration: float  # seconds
    
    # 关键轨迹点（粗粒度）
    key_trajectory_points: List[TrajectoryKeyPoint] = field(default_factory=list)
    
    # 飞行阶段预测
    predicted_flight_phases: List[FlightPhasePredict] = field(default_factory=list)

@dataclass
class TrajectoryUncertainty:
    """轨迹不确定性"""
    position_uncertainty: float  # meters (1-sigma)
    velocity_uncertainty: float  # m/s (1-sigma)
    time_uncertainty: float  # seconds (1-sigma)
    uncertainty_growth_rate: float  # per second
    confidence_level: float  # 0-1

@dataclass
class ObservationRequirements:
    """观测需求"""
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
class MissileTargetInfo:
    """导弹目标信息（地面已知部分）"""
    missile_id: str
    threat_level: int  # 1-5
    
    # 轨迹预测信息
    predicted_trajectory: PredictedTrajectory
    
    # 观测需求
    observation_requirements: ObservationRequirements
    
    # 不确定性信息
    trajectory_uncertainty: TrajectoryUncertainty

@dataclass
class MissionRequirements:
    """任务要求"""
    min_tracking_duration: float  # seconds
    required_position_accuracy: float  # meters
    required_velocity_accuracy: float  # m/s
    
    # 覆盖要求
    min_coverage_percentage: float  # 0-1
    max_coverage_gap: float  # seconds
    
    # 冗余要求
    min_simultaneous_observers: int
    preferred_simultaneous_observers: int

@dataclass
class CoordinationRequirements:
    """协调要求"""
    max_discussion_time: float  # seconds
    required_consensus_level: float  # 0-1
    fallback_strategy: str  # "priority_based", "resource_based", "random"
    
    # STK计算要求
    stk_calculation_timeout: float  # seconds
    visibility_calculation_precision: str  # "high", "medium", "low"

@dataclass
class InitialMetaTaskPackage:
    """地面发送的初始元任务包"""
    
    # 基础信息
    task_package_id: str
    creation_time: datetime
    priority_level: int  # 1-5
    
    # 导弹目标信息
    missile_targets: List[MissileTargetInfo]
    
    # 任务要求
    mission_requirements: MissionRequirements
    
    # 候选卫星信息
    candidate_satellites: List[str]  # 卫星ID列表
    
    # 协调要求
    coordination_requirements: CoordinationRequirements
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            'task_package_id': self.task_package_id,
            'creation_time': self.creation_time.isoformat(),
            'priority_level': self.priority_level,
            'missile_count': len(self.missile_targets),
            'candidate_satellites': self.candidate_satellites,
            'mission_requirements': {
                'min_tracking_duration': self.mission_requirements.min_tracking_duration,
                'required_position_accuracy': self.mission_requirements.required_position_accuracy,
                'min_coverage_percentage': self.mission_requirements.min_coverage_percentage,
                'min_simultaneous_observers': self.mission_requirements.min_simultaneous_observers
            },
            'coordination_requirements': {
                'max_discussion_time': self.coordination_requirements.max_discussion_time,
                'stk_calculation_timeout': self.coordination_requirements.stk_calculation_timeout,
                'visibility_calculation_precision': self.coordination_requirements.visibility_calculation_precision
            }
        }

# ==================== 卫星计算的数据结构 ====================

@dataclass
class VisibilityWindow:
    """可见性窗口"""
    window_id: str
    start_time: datetime
    end_time: datetime
    duration: float  # seconds
    
    # 几何参数
    max_elevation: float  # degrees
    min_elevation: float  # degrees
    avg_elevation: float  # degrees
    max_range: float  # km
    min_range: float  # km
    
    # 观测条件
    sun_angle: float  # degrees
    earth_shadow_percentage: float  # 0-1
    atmospheric_conditions: str
    
    # 质量指标
    geometric_dilution_of_precision: float
    signal_to_noise_ratio: float
    tracking_accuracy_estimate: float  # meters

@dataclass
class ObservationQualityAssessment:
    """观测质量评估"""
    overall_quality_score: float  # 0-1
    
    # 分项评估
    geometric_quality: float  # 0-1
    temporal_coverage: float  # 0-1
    tracking_continuity: float  # 0-1
    measurement_accuracy: float  # 0-1
    
    # 限制因素
    limiting_factors: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)

@dataclass
class PowerConsumptionPoint:
    """功率消耗点"""
    timestamp: datetime
    power_watts: float

@dataclass
class DataGenerationPoint:
    """数据生成点"""
    timestamp: datetime
    data_mb: float

@dataclass
class ResourceRequirementAssessment:
    """资源需求评估"""
    # 功率需求
    estimated_power_consumption: float = 100.0  # watts
    power_consumption_profile: List[PowerConsumptionPoint] = field(default_factory=list)

    # 存储需求
    estimated_data_volume: float = 100.0  # MB
    data_generation_profile: List[DataGenerationPoint] = field(default_factory=list)
    
    # 通信需求
    estimated_downlink_requirement: float = 80.0  # MB
    downlink_urgency: str = "near_real_time"  # "real_time", "near_real_time", "batch"

    # 计算需求
    processing_complexity: str = "medium"  # "low", "medium", "high"
    estimated_processing_time: float = 60.0  # seconds

@dataclass
class MissileVisibilityInfo:
    """单个导弹的可见性信息"""
    missile_id: str
    
    # 可见性窗口
    visibility_windows: List[VisibilityWindow] = field(default_factory=list)
    
    # 观测质量评估
    observation_quality_assessment: ObservationQualityAssessment = None
    
    # 资源需求评估
    resource_requirement_assessment: ResourceRequirementAssessment = None

@dataclass
class SatelliteStatusInfo:
    """卫星状态信息"""
    current_position: Position3D
    current_velocity: Velocity3D
    
    # 资源状态
    power_level: float  # 0-1
    storage_available: float  # MB
    thermal_status: str  # "normal", "warning", "critical"
    
    # 任务状态
    current_tasks: List[str] = field(default_factory=list)  # 当前任务ID列表
    available_capacity: float = 1.0  # 0-1
    
    # 设备状态
    payload_status: Dict[str, str] = field(default_factory=dict)  # 载荷状态
    communication_status: str = "normal"
    attitude_control_status: str = "normal"

@dataclass
class CalculationQualityInfo:
    """计算质量信息"""
    stk_version: str
    calculation_model: str
    precision_level: str
    
    # 计算参数
    time_step: float  # seconds
    calculation_span: Tuple[datetime, datetime]
    
    # 质量指标
    calculation_confidence: float  # 0-1
    known_limitations: List[str] = field(default_factory=list)
    accuracy_estimates: Dict[str, float] = field(default_factory=dict)

@dataclass
class SatelliteVisibilityReport:
    """卫星可见性报告"""
    
    # 报告基础信息
    satellite_id: str
    report_id: str
    calculation_time: datetime
    stk_calculation_duration: float  # seconds
    
    # 导弹可见性信息
    missile_visibility: Dict[str, MissileVisibilityInfo] = field(default_factory=dict)
    
    # 卫星状态信息
    satellite_status: SatelliteStatusInfo = None
    
    # 计算质量信息
    calculation_quality: CalculationQualityInfo = None
    
    def get_total_visibility_time(self, missile_id: str) -> float:
        """获取对特定导弹的总可见时间"""
        if missile_id not in self.missile_visibility:
            return 0.0
        
        return sum(window.duration for window in self.missile_visibility[missile_id].visibility_windows)
    
    def get_best_visibility_window(self, missile_id: str) -> Optional[VisibilityWindow]:
        """获取对特定导弹的最佳可见性窗口"""
        if missile_id not in self.missile_visibility:
            return None
        
        windows = self.missile_visibility[missile_id].visibility_windows
        if not windows:
            return None
        
        # 按观测质量排序，选择最佳窗口
        return max(windows, key=lambda w: w.avg_elevation * w.duration)
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """转换为摘要字典格式"""
        return {
            'satellite_id': self.satellite_id,
            'report_id': self.report_id,
            'calculation_time': self.calculation_time.isoformat(),
            'stk_calculation_duration': self.stk_calculation_duration,
            'missile_count': len(self.missile_visibility),
            'total_visibility_windows': sum(len(mv.visibility_windows) for mv in self.missile_visibility.values()),
            'satellite_power_level': self.satellite_status.power_level if self.satellite_status else 0.0,
            'satellite_available_capacity': self.satellite_status.available_capacity if self.satellite_status else 0.0,
            'calculation_confidence': self.calculation_quality.calculation_confidence if self.calculation_quality else 0.0
        }

# ==================== 工具函数 ====================

class RealisticMetaTaskBuilder:
    """现实元任务构建器"""
    
    @staticmethod
    def create_initial_meta_task_package(
        missile_data: List[Dict[str, Any]], 
        candidate_satellites: List[str],
        priority_level: int = 3
    ) -> InitialMetaTaskPackage:
        """创建初始元任务包"""
        
        try:
            # 转换导弹数据
            missile_targets = []
            for missile in missile_data:
                missile_target = RealisticMetaTaskBuilder._convert_missile_data(missile)
                missile_targets.append(missile_target)
            
            # 创建任务要求
            mission_requirements = MissionRequirements(
                min_tracking_duration=300.0,  # 5分钟
                required_position_accuracy=100.0,  # 100米
                required_velocity_accuracy=10.0,  # 10m/s
                min_coverage_percentage=0.8,  # 80%覆盖
                max_coverage_gap=60.0,  # 最大60秒空隙
                min_simultaneous_observers=2,
                preferred_simultaneous_observers=3
            )
            
            # 创建协调要求
            coordination_requirements = CoordinationRequirements(
                max_discussion_time=120.0,  # 2分钟讨论时间
                required_consensus_level=0.7,  # 70%共识
                fallback_strategy="priority_based",
                stk_calculation_timeout=30.0,  # 30秒STK计算超时
                visibility_calculation_precision="high"
            )
            
            package = InitialMetaTaskPackage(
                task_package_id=f"META_TASK_PKG_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                creation_time=datetime.now(),
                priority_level=priority_level,
                missile_targets=missile_targets,
                mission_requirements=mission_requirements,
                candidate_satellites=candidate_satellites,
                coordination_requirements=coordination_requirements
            )
            
            return package
            
        except Exception as e:
            logger.error(f"❌ 创建初始元任务包失败: {e}")
            raise
    
    @staticmethod
    def _convert_missile_data(missile_data: Dict[str, Any]) -> MissileTargetInfo:
        """转换导弹数据为MissileTargetInfo"""
        
        # 创建轨迹预测
        launch_pos = missile_data.get('launch_position', {})
        target_pos = missile_data.get('target_position', {})
        
        predicted_trajectory = PredictedTrajectory(
            launch_position=Position3D(
                lat=launch_pos.get('lat', 0.0),
                lon=launch_pos.get('lon', 0.0),
                alt=launch_pos.get('alt', 0.0)
            ),
            predicted_impact_position=Position3D(
                lat=target_pos.get('lat', 0.0),
                lon=target_pos.get('lon', 0.0),
                alt=target_pos.get('alt', 0.0)
            ),
            launch_time=datetime.fromisoformat(missile_data.get('launch_time', datetime.now().isoformat())),
            estimated_flight_duration=missile_data.get('flight_time', 1800.0)
        )
        
        # 创建观测需求
        threat_level = missile_data.get('threat_level', 3)
        observation_requirements = ObservationRequirements(
            min_observation_duration=30.0 if threat_level >= 4 else 20.0,
            preferred_observation_duration=60.0 if threat_level >= 4 else 45.0,
            min_elevation_angle=10.0,
            preferred_elevation_angle=30.0,
            required_sensors=['optical', 'infrared'],
            preferred_sensors=['optical', 'infrared', 'radar'] if threat_level >= 4 else ['optical', 'infrared'],
            min_observation_frequency=2.0 if threat_level >= 4 else 1.0,
            position_accuracy_requirement=100.0 if threat_level >= 4 else 200.0,
            velocity_accuracy_requirement=10.0 if threat_level >= 4 else 20.0
        )
        
        # 创建不确定性信息
        trajectory_uncertainty = TrajectoryUncertainty(
            position_uncertainty=50.0 if threat_level >= 4 else 100.0,
            velocity_uncertainty=5.0,
            time_uncertainty=2.0,
            uncertainty_growth_rate=0.1,
            confidence_level=0.8
        )
        
        return MissileTargetInfo(
            missile_id=missile_data['missile_id'],
            threat_level=threat_level,
            predicted_trajectory=predicted_trajectory,
            observation_requirements=observation_requirements,
            trajectory_uncertainty=trajectory_uncertainty
        )
