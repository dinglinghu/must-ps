"""
卫星可见性计算器
基于STK服务的实时可见性计算和协商功能
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json

from .realistic_meta_task_structures import (
    InitialMetaTaskPackage, SatelliteVisibilityReport, MissileVisibilityInfo,
    VisibilityWindow, ObservationQualityAssessment, ResourceRequirementAssessment,
    SatelliteStatusInfo, CalculationQualityInfo, Position3D, Velocity3D
)

logger = logging.getLogger(__name__)

class SatelliteVisibilityCalculator:
    """卫星可见性计算器"""
    
    def __init__(self, satellite_id: str, stk_interface=None, config_manager=None):
        self.satellite_id = satellite_id
        self.stk_interface = stk_interface
        self.config_manager = config_manager
        
        # 计算配置
        self.calculation_timeout = 30.0  # seconds
        self.min_elevation_threshold = 10.0  # degrees
        self.time_step = 10.0  # seconds
        
        # 缓存
        self._visibility_cache = {}
        self._cache_expiry = {}
        
        logger.info(f"✅ 卫星可见性计算器初始化完成: {satellite_id}")
    
    async def calculate_visibility_for_meta_task(
        self, 
        meta_task_package: InitialMetaTaskPackage
    ) -> SatelliteVisibilityReport:
        """为元任务包计算可见性"""
        
        try:
            logger.info(f"🔍 开始为元任务包计算可见性: {meta_task_package.task_package_id}")
            start_time = datetime.now()
            
            # 1. 获取卫星当前状态
            satellite_status = await self._get_satellite_status()
            
            # 2. 为每个导弹计算可见性
            missile_visibility = {}
            
            for missile_target in meta_task_package.missile_targets:
                missile_id = missile_target.missile_id
                logger.info(f"   计算导弹 {missile_id} 的可见性...")
                
                # 检查缓存
                cached_result = self._get_cached_visibility(missile_id, missile_target)
                if cached_result:
                    missile_visibility[missile_id] = cached_result
                    continue
                
                # 计算可见性
                visibility_info = await self._calculate_missile_visibility(
                    missile_target, meta_task_package.coordination_requirements
                )
                
                if visibility_info:
                    missile_visibility[missile_id] = visibility_info
                    # 缓存结果
                    self._cache_visibility_result(missile_id, visibility_info)
            
            # 3. 创建计算质量信息
            calculation_duration = (datetime.now() - start_time).total_seconds()
            calculation_quality = CalculationQualityInfo(
                stk_version="STK 12.0",
                calculation_model="HPOP",
                precision_level=meta_task_package.coordination_requirements.visibility_calculation_precision,
                time_step=self.time_step,
                calculation_span=(start_time, datetime.now()),
                calculation_confidence=0.9,
                known_limitations=["大气模型简化", "地球重力场简化"],
                accuracy_estimates={"position": 10.0, "velocity": 1.0}  # meters, m/s
            )
            
            # 4. 创建可见性报告
            report = SatelliteVisibilityReport(
                satellite_id=self.satellite_id,
                report_id=f"VIS_REPORT_{self.satellite_id}_{start_time.strftime('%Y%m%d_%H%M%S')}",
                calculation_time=start_time,
                stk_calculation_duration=calculation_duration,
                missile_visibility=missile_visibility,
                satellite_status=satellite_status,
                calculation_quality=calculation_quality
            )
            
            logger.info(f"✅ 可见性计算完成，耗时 {calculation_duration:.2f}s，处理 {len(missile_visibility)} 个导弹")
            return report
            
        except Exception as e:
            logger.error(f"❌ 可见性计算失败: {e}")
            raise
    
    async def _calculate_missile_visibility(
        self, 
        missile_target, 
        coordination_requirements
    ) -> Optional[MissileVisibilityInfo]:
        """计算单个导弹的可见性"""
        
        try:
            missile_id = missile_target.missile_id
            trajectory = missile_target.predicted_trajectory
            
            # 1. 调用STK计算可见性窗口
            visibility_windows = await self._call_stk_visibility_calculation(
                trajectory, coordination_requirements.stk_calculation_timeout
            )
            
            if not visibility_windows:
                logger.warning(f"⚠️ 导弹 {missile_id} 无可见性窗口")
                return None
            
            # 2. 评估观测质量
            quality_assessment = self._assess_observation_quality(
                visibility_windows, missile_target.observation_requirements
            )
            
            # 3. 评估资源需求
            resource_assessment = self._assess_resource_requirements(
                visibility_windows, missile_target
            )
            
            return MissileVisibilityInfo(
                missile_id=missile_id,
                visibility_windows=visibility_windows,
                observation_quality_assessment=quality_assessment,
                resource_requirement_assessment=resource_assessment
            )
            
        except Exception as e:
            logger.error(f"❌ 导弹 {missile_target.missile_id} 可见性计算失败: {e}")
            return None
    
    async def _call_stk_visibility_calculation(
        self, 
        trajectory, 
        timeout: float
    ) -> List[VisibilityWindow]:
        """调用STK进行可见性计算"""
        
        try:
            # 模拟STK调用（实际实现需要调用真实的STK COM接口）
            await asyncio.sleep(0.5)  # 模拟计算时间
            
            # 基于轨迹生成可见性窗口
            windows = []
            current_time = trajectory.launch_time
            end_time = trajectory.launch_time + timedelta(seconds=trajectory.estimated_flight_duration)
            
            # 简化的可见性计算逻辑
            window_count = 0
            while current_time < end_time and window_count < 5:  # 最多5个窗口
                # 模拟可见性窗口
                window_start = current_time + timedelta(seconds=window_count * 300)  # 每5分钟一个窗口
                window_end = window_start + timedelta(seconds=180)  # 3分钟窗口
                
                if window_end > end_time:
                    window_end = end_time
                
                if window_start >= end_time:
                    break
                
                # 模拟几何参数
                elevation = 15.0 + window_count * 10.0  # 递增的仰角
                
                window = VisibilityWindow(
                    window_id=f"VIS_WIN_{self.satellite_id}_{window_count}",
                    start_time=window_start,
                    end_time=window_end,
                    duration=(window_end - window_start).total_seconds(),
                    max_elevation=elevation + 5.0,
                    min_elevation=max(10.0, elevation - 5.0),
                    avg_elevation=elevation,
                    max_range=2000.0,  # km
                    min_range=800.0,   # km
                    sun_angle=90.0,
                    earth_shadow_percentage=0.0,
                    atmospheric_conditions="clear",
                    geometric_dilution_of_precision=2.5,
                    signal_to_noise_ratio=15.0,
                    tracking_accuracy_estimate=50.0  # meters
                )
                
                windows.append(window)
                window_count += 1
                current_time = window_end + timedelta(seconds=120)  # 2分钟间隔
            
            logger.info(f"   STK计算完成，生成 {len(windows)} 个可见性窗口")
            return windows
            
        except Exception as e:
            logger.error(f"❌ STK可见性计算失败: {e}")
            return []
    
    def _assess_observation_quality(
        self, 
        visibility_windows: List[VisibilityWindow], 
        observation_requirements
    ) -> ObservationQualityAssessment:
        """评估观测质量"""
        
        try:
            if not visibility_windows:
                return ObservationQualityAssessment(
                    overall_quality_score=0.0,
                    geometric_quality=0.0,
                    temporal_coverage=0.0,
                    tracking_continuity=0.0,
                    measurement_accuracy=0.0,
                    limiting_factors=["无可见性窗口"],
                    improvement_suggestions=["调整轨道参数", "增加观测卫星"]
                )
            
            # 计算几何质量
            avg_elevation = sum(w.avg_elevation for w in visibility_windows) / len(visibility_windows)
            geometric_quality = min(1.0, avg_elevation / 45.0)  # 45度为满分
            
            # 计算时间覆盖
            total_visibility_time = sum(w.duration for w in visibility_windows)
            required_time = observation_requirements.min_observation_duration
            temporal_coverage = min(1.0, total_visibility_time / required_time)
            
            # 计算跟踪连续性
            gaps = []
            for i in range(len(visibility_windows) - 1):
                gap = (visibility_windows[i+1].start_time - visibility_windows[i].end_time).total_seconds()
                gaps.append(gap)
            
            max_gap = max(gaps) if gaps else 0.0
            tracking_continuity = max(0.0, 1.0 - max_gap / 300.0)  # 5分钟为基准
            
            # 计算测量精度
            avg_accuracy = sum(w.tracking_accuracy_estimate for w in visibility_windows) / len(visibility_windows)
            required_accuracy = observation_requirements.position_accuracy_requirement
            measurement_accuracy = min(1.0, required_accuracy / avg_accuracy)
            
            # 综合质量分数
            overall_quality = (geometric_quality * 0.3 + 
                             temporal_coverage * 0.3 + 
                             tracking_continuity * 0.2 + 
                             measurement_accuracy * 0.2)
            
            # 识别限制因素
            limiting_factors = []
            improvement_suggestions = []
            
            if geometric_quality < 0.7:
                limiting_factors.append("仰角过低")
                improvement_suggestions.append("等待更高仰角窗口")
            
            if temporal_coverage < 0.8:
                limiting_factors.append("观测时间不足")
                improvement_suggestions.append("增加观测窗口")
            
            if tracking_continuity < 0.6:
                limiting_factors.append("观测间隙过大")
                improvement_suggestions.append("协调多星观测")
            
            return ObservationQualityAssessment(
                overall_quality_score=overall_quality,
                geometric_quality=geometric_quality,
                temporal_coverage=temporal_coverage,
                tracking_continuity=tracking_continuity,
                measurement_accuracy=measurement_accuracy,
                limiting_factors=limiting_factors,
                improvement_suggestions=improvement_suggestions
            )
            
        except Exception as e:
            logger.error(f"❌ 观测质量评估失败: {e}")
            return ObservationQualityAssessment(
                overall_quality_score=0.0,
                geometric_quality=0.0,
                temporal_coverage=0.0,
                tracking_continuity=0.0,
                measurement_accuracy=0.0
            )
    
    def _assess_resource_requirements(
        self, 
        visibility_windows: List[VisibilityWindow], 
        missile_target
    ) -> ResourceRequirementAssessment:
        """评估资源需求"""
        
        try:
            total_observation_time = sum(w.duration for w in visibility_windows)
            threat_level = missile_target.threat_level
            
            # 功率需求评估
            base_power = 100.0  # watts
            power_multiplier = 1.0 + (threat_level - 1) * 0.2  # 威胁等级影响
            estimated_power = base_power * power_multiplier
            
            # 存储需求评估
            data_rate = 10.0  # MB per minute
            estimated_data_volume = (total_observation_time / 60.0) * data_rate
            
            # 通信需求评估
            downlink_ratio = 0.8  # 80%数据需要下传
            estimated_downlink = estimated_data_volume * downlink_ratio
            
            # 处理复杂度评估
            if threat_level >= 4:
                processing_complexity = "high"
                estimated_processing_time = total_observation_time * 0.5
            elif threat_level >= 3:
                processing_complexity = "medium"
                estimated_processing_time = total_observation_time * 0.3
            else:
                processing_complexity = "low"
                estimated_processing_time = total_observation_time * 0.1
            
            return ResourceRequirementAssessment(
                estimated_power_consumption=estimated_power,
                estimated_data_volume=estimated_data_volume,
                estimated_downlink_requirement=estimated_downlink,
                downlink_urgency="real_time" if threat_level >= 4 else "near_real_time",
                processing_complexity=processing_complexity,
                estimated_processing_time=estimated_processing_time
            )
            
        except Exception as e:
            logger.error(f"❌ 资源需求评估失败: {e}")
            return ResourceRequirementAssessment(
                estimated_power_consumption=100.0,
                estimated_data_volume=100.0,
                estimated_downlink_requirement=80.0,
                downlink_urgency="near_real_time",
                processing_complexity="medium",
                estimated_processing_time=60.0
            )
    
    async def _get_satellite_status(self) -> SatelliteStatusInfo:
        """获取卫星状态"""
        
        try:
            # 模拟获取卫星状态（实际实现需要从卫星系统获取）
            return SatelliteStatusInfo(
                current_position=Position3D(lat=0.0, lon=0.0, alt=600.0),  # 600km轨道
                current_velocity=Velocity3D(vx=7.5, vy=0.0, vz=0.0),  # 7.5km/s
                power_level=0.85,  # 85%功率
                storage_available=8000.0,  # 8GB可用存储
                thermal_status="normal",
                current_tasks=[],
                available_capacity=0.7,  # 70%可用容量
                payload_status={"optical": "normal", "infrared": "normal"},
                communication_status="normal",
                attitude_control_status="normal"
            )
            
        except Exception as e:
            logger.error(f"❌ 获取卫星状态失败: {e}")
            return SatelliteStatusInfo(
                current_position=Position3D(lat=0.0, lon=0.0, alt=600.0),
                current_velocity=Velocity3D(vx=7.5, vy=0.0, vz=0.0),
                power_level=0.5,
                storage_available=5000.0,
                thermal_status="unknown"
            )
    
    def _get_cached_visibility(self, missile_id: str, missile_target) -> Optional[MissileVisibilityInfo]:
        """获取缓存的可见性结果"""
        
        try:
            cache_key = f"{missile_id}_{missile_target.predicted_trajectory.launch_time.isoformat()}"
            
            if cache_key in self._visibility_cache:
                expiry_time = self._cache_expiry.get(cache_key, datetime.min)
                if datetime.now() < expiry_time:
                    logger.info(f"   使用缓存的可见性结果: {missile_id}")
                    return self._visibility_cache[cache_key]
                else:
                    # 清理过期缓存
                    del self._visibility_cache[cache_key]
                    del self._cache_expiry[cache_key]
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取缓存可见性失败: {e}")
            return None
    
    def _cache_visibility_result(self, missile_id: str, visibility_info: MissileVisibilityInfo):
        """缓存可见性结果"""
        
        try:
            cache_key = f"{missile_id}_{datetime.now().isoformat()}"
            self._visibility_cache[cache_key] = visibility_info
            self._cache_expiry[cache_key] = datetime.now() + timedelta(minutes=10)  # 10分钟过期
            
            # 清理旧缓存
            if len(self._visibility_cache) > 100:  # 最多缓存100个结果
                oldest_key = min(self._cache_expiry.keys(), key=lambda k: self._cache_expiry[k])
                del self._visibility_cache[oldest_key]
                del self._cache_expiry[oldest_key]
                
        except Exception as e:
            logger.error(f"❌ 缓存可见性结果失败: {e}")
    
    def get_calculation_statistics(self) -> Dict[str, Any]:
        """获取计算统计信息"""
        
        return {
            'satellite_id': self.satellite_id,
            'cache_size': len(self._visibility_cache),
            'calculation_timeout': self.calculation_timeout,
            'min_elevation_threshold': self.min_elevation_threshold,
            'time_step': self.time_step
        }
