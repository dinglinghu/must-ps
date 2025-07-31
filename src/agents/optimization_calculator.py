"""
优化目标计算模块
实现GDOP跟踪精度计算、资源调度性评估、鲁棒性指标等优化目标函数
"""

import logging
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GDOPCalculationResult:
    """GDOP计算结果"""
    target_id: str
    satellite_pair: Tuple[str, str]
    time_window: Tuple[datetime, datetime]
    gdop_value: float
    tracking_accuracy: float
    geometry_angles: Dict[str, float]  # 几何角度信息
    baseline_length: float  # 基线长度


@dataclass
class SchedulabilityResult:
    """调度性评估结果"""
    satellite_id: str
    current_load: float  # 当前负载 (0-1)
    available_capacity: float  # 可用容量 (0-1)
    schedulability_score: float  # 调度性分数 (0-1)
    conflict_count: int  # 冲突任务数量
    resource_constraints: Dict[str, Any]  # 资源约束信息


@dataclass
class RobustnessResult:
    """鲁棒性评估结果"""
    plan_id: str
    robustness_score: float  # 鲁棒性分数 (0-1)
    redundancy_factor: float  # 冗余度因子
    adaptability_score: float  # 适应性分数
    failure_tolerance: float  # 故障容忍度
    disturbance_scenarios: List[Dict[str, Any]]  # 扰动场景分析


class OptimizationCalculator:
    """
    优化目标计算器
    
    实现天基低轨预警系统的三大优化目标：
    1. GDOP跟踪精度最小化
    2. 资源调度性最大化
    3. 系统鲁棒性最大化
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化优化计算器
        
        Args:
            config: 优化计算配置参数
        """
        self.config = config or {}
        
        # GDOP计算参数
        self.gdop_config = self.config.get('gdop', {})
        self.baseline_factor = self.gdop_config.get('baseline_factor', 1.0)
        self.angle_measurement_accuracy = self.gdop_config.get('angle_accuracy', 0.001)  # 弧度
        
        # 调度性计算参数
        self.schedulability_config = self.config.get('schedulability', {})
        self.max_concurrent_tasks = self.schedulability_config.get('max_concurrent_tasks', 3)
        self.resource_utilization_threshold = self.schedulability_config.get('utilization_threshold', 0.8)
        
        # 鲁棒性计算参数
        self.robustness_config = self.config.get('robustness', {})
        self.min_redundancy_level = self.robustness_config.get('min_redundancy', 2)
        self.failure_probability = self.robustness_config.get('failure_probability', 0.05)
        
        logger.info("📊 优化目标计算器初始化完成")
    
    def calculate_gdop(
        self,
        target_position: Tuple[float, float, float],
        satellite_positions: List[Tuple[str, float, float, float]],
        time_window: Tuple[datetime, datetime]
    ) -> List[GDOPCalculationResult]:
        """
        计算几何精度衰减因子(GDOP)
        
        GDOP = L*σ_θ * sqrt((sin²θ₁ + sin²θ₂) / sin⁴(θ₂ - θ₁))
        
        Args:
            target_position: 目标位置 (lat, lon, alt)
            satellite_positions: 卫星位置列表 [(sat_id, lat, lon, alt), ...]
            time_window: 时间窗口
            
        Returns:
            GDOP计算结果列表
        """
        try:
            results = []
            
            # 对所有卫星对进行GDOP计算
            for i in range(len(satellite_positions)):
                for j in range(i + 1, len(satellite_positions)):
                    sat1_id, sat1_lat, sat1_lon, sat1_alt = satellite_positions[i]
                    sat2_id, sat2_lat, sat2_lon, sat2_alt = satellite_positions[j]
                    
                    # 计算观测角度
                    angles = self._calculate_observation_angles(
                        target_position,
                        (sat1_lat, sat1_lon, sat1_alt),
                        (sat2_lat, sat2_lon, sat2_alt)
                    )
                    
                    if angles:
                        theta1, theta2, baseline_length = angles
                        
                        # 计算GDOP值
                        gdop_value = self._compute_gdop_value(theta1, theta2, baseline_length)
                        
                        # 计算跟踪精度
                        tracking_accuracy = 1.0 / max(gdop_value, 0.001)
                        
                        result = GDOPCalculationResult(
                            target_id="target",  # 简化，实际应传入目标ID
                            satellite_pair=(sat1_id, sat2_id),
                            time_window=time_window,
                            gdop_value=gdop_value,
                            tracking_accuracy=tracking_accuracy,
                            geometry_angles={
                                'theta1': math.degrees(theta1),
                                'theta2': math.degrees(theta2),
                                'angle_difference': math.degrees(abs(theta2 - theta1))
                            },
                            baseline_length=baseline_length
                        )
                        
                        results.append(result)
            
            # 按GDOP值排序（越小越好）
            results.sort(key=lambda x: x.gdop_value)
            
            logger.info(f"✅ 计算了 {len(results)} 个卫星对的GDOP值")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ GDOP计算失败: {e}")
            return []
    
    def evaluate_schedulability(
        self,
        satellite_id: str,
        current_tasks: List[Dict[str, Any]],
        new_task: Dict[str, Any],
        resource_status: Dict[str, Any]
    ) -> SchedulabilityResult:
        """
        评估卫星资源的调度性
        
        Args:
            satellite_id: 卫星ID
            current_tasks: 当前任务列表
            new_task: 新任务信息
            resource_status: 资源状态信息
            
        Returns:
            调度性评估结果
        """
        try:
            # 计算当前负载
            current_load = self._calculate_current_load(current_tasks)
            
            # 计算可用容量
            available_capacity = 1.0 - current_load
            
            # 检查时间冲突
            conflict_count = self._count_time_conflicts(current_tasks, new_task)
            
            # 检查资源约束
            resource_constraints = self._check_resource_constraints(resource_status, new_task)
            
            # 计算调度性分数
            schedulability_score = self._compute_schedulability_score(
                current_load, conflict_count, resource_constraints
            )
            
            result = SchedulabilityResult(
                satellite_id=satellite_id,
                current_load=current_load,
                available_capacity=available_capacity,
                schedulability_score=schedulability_score,
                conflict_count=conflict_count,
                resource_constraints=resource_constraints
            )
            
            logger.debug(f"📊 卫星 {satellite_id} 调度性评估: 分数 {schedulability_score:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 调度性评估失败: {e}")
            return SchedulabilityResult(
                satellite_id=satellite_id,
                current_load=1.0,
                available_capacity=0.0,
                schedulability_score=0.0,
                conflict_count=999,
                resource_constraints={'error': str(e)}
            )
    
    def calculate_robustness(
        self,
        plan_id: str,
        task_assignments: List[Dict[str, Any]],
        satellite_resources: List[Dict[str, Any]],
        disturbance_scenarios: Optional[List[Dict[str, Any]]] = None
    ) -> RobustnessResult:
        """
        计算规划方案的鲁棒性
        
        Args:
            plan_id: 规划方案ID
            task_assignments: 任务分配列表
            satellite_resources: 卫星资源列表
            disturbance_scenarios: 扰动场景列表
            
        Returns:
            鲁棒性评估结果
        """
        try:
            # 计算冗余度因子
            redundancy_factor = self._calculate_redundancy_factor(task_assignments, satellite_resources)
            
            # 计算适应性分数
            adaptability_score = self._calculate_adaptability_score(task_assignments)
            
            # 计算故障容忍度
            failure_tolerance = self._calculate_failure_tolerance(task_assignments, satellite_resources)
            
            # 分析扰动场景
            if not disturbance_scenarios:
                disturbance_scenarios = self._generate_default_disturbance_scenarios()
            
            scenario_analysis = self._analyze_disturbance_scenarios(
                task_assignments, disturbance_scenarios
            )
            
            # 计算综合鲁棒性分数
            robustness_score = self._compute_robustness_score(
                redundancy_factor, adaptability_score, failure_tolerance, scenario_analysis
            )
            
            result = RobustnessResult(
                plan_id=plan_id,
                robustness_score=robustness_score,
                redundancy_factor=redundancy_factor,
                adaptability_score=adaptability_score,
                failure_tolerance=failure_tolerance,
                disturbance_scenarios=scenario_analysis
            )
            
            logger.info(f"✅ 规划方案 {plan_id} 鲁棒性评估: 分数 {robustness_score:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 鲁棒性计算失败: {e}")
            return RobustnessResult(
                plan_id=plan_id,
                robustness_score=0.0,
                redundancy_factor=0.0,
                adaptability_score=0.0,
                failure_tolerance=0.0,
                disturbance_scenarios=[]
            )
    
    def calculate_comprehensive_optimization_score(
        self,
        gdop_results: List[GDOPCalculationResult],
        schedulability_results: List[SchedulabilityResult],
        robustness_result: RobustnessResult,
        weights: Optional[Dict[str, float]] = None
    ) -> Dict[str, float]:
        """
        计算综合优化分数
        
        Args:
            gdop_results: GDOP计算结果列表
            schedulability_results: 调度性评估结果列表
            robustness_result: 鲁棒性评估结果
            weights: 权重配置
            
        Returns:
            综合优化分数字典
        """
        try:
            # 默认权重
            if not weights:
                weights = {
                    'gdop': 0.4,        # GDOP权重40%
                    'schedulability': 0.3,  # 调度性权重30%
                    'robustness': 0.3   # 鲁棒性权重30%
                }
            
            # 计算GDOP分数（越小越好，转换为越大越好）
            if gdop_results:
                avg_gdop = sum(r.gdop_value for r in gdop_results) / len(gdop_results)
                gdop_score = 1.0 / (1.0 + avg_gdop)  # 归一化
            else:
                gdop_score = 0.0
            
            # 计算调度性分数
            if schedulability_results:
                avg_schedulability = sum(r.schedulability_score for r in schedulability_results) / len(schedulability_results)
                schedulability_score = avg_schedulability
            else:
                schedulability_score = 0.0
            
            # 鲁棒性分数
            robustness_score = robustness_result.robustness_score
            
            # 计算综合分数
            comprehensive_score = (
                weights['gdop'] * gdop_score +
                weights['schedulability'] * schedulability_score +
                weights['robustness'] * robustness_score
            )
            
            result = {
                'comprehensive_score': comprehensive_score,
                'gdop_score': gdop_score,
                'schedulability_score': schedulability_score,
                'robustness_score': robustness_score,
                'weights': weights,
                'metrics': {
                    'avg_gdop': avg_gdop if gdop_results else float('inf'),
                    'avg_schedulability': avg_schedulability if schedulability_results else 0.0,
                    'robustness': robustness_score
                }
            }
            
            logger.info(f"✅ 综合优化分数: {comprehensive_score:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 综合优化分数计算失败: {e}")
            return {'comprehensive_score': 0.0, 'error': str(e)}
    
    # 私有辅助方法
    def _calculate_observation_angles(
        self,
        target_pos: Tuple[float, float, float],
        sat1_pos: Tuple[float, float, float],
        sat2_pos: Tuple[float, float, float]
    ) -> Optional[Tuple[float, float, float]]:
        """计算观测角度"""
        try:
            # 简化的角度计算（实际应使用精确的大地测量学公式）
            target_lat, target_lon, target_alt = target_pos
            sat1_lat, sat1_lon, sat1_alt = sat1_pos
            sat2_lat, sat2_lon, sat2_alt = sat2_pos
            
            # 计算卫星到目标的方位角（简化）
            theta1 = math.atan2(
                sat1_lat - target_lat,
                sat1_lon - target_lon
            )
            
            theta2 = math.atan2(
                sat2_lat - target_lat,
                sat2_lon - target_lon
            )
            
            # 计算基线长度（简化）
            baseline_length = math.sqrt(
                (sat1_lat - sat2_lat) ** 2 +
                (sat1_lon - sat2_lon) ** 2 +
                (sat1_alt - sat2_alt) ** 2
            )
            
            return (theta1, theta2, baseline_length)
            
        except Exception as e:
            logger.error(f"角度计算失败: {e}")
            return None
    
    def _compute_gdop_value(self, theta1: float, theta2: float, baseline_length: float) -> float:
        """计算GDOP值"""
        try:
            # GDOP公式实现
            angle_diff = abs(theta2 - theta1)
            
            if angle_diff < 0.01:  # 避免除零
                return float('inf')
            
            numerator = math.sin(theta1) ** 2 + math.sin(theta2) ** 2
            denominator = math.sin(angle_diff) ** 4
            
            if denominator < 1e-10:
                return float('inf')
            
            gdop = self.baseline_factor * self.angle_measurement_accuracy * math.sqrt(numerator / denominator)
            
            return gdop
            
        except Exception:
            return float('inf')
    
    def _calculate_current_load(self, current_tasks: List[Dict[str, Any]]) -> float:
        """计算当前负载"""
        if not current_tasks:
            return 0.0
        
        # 简化：基于任务数量计算负载
        active_tasks = len([task for task in current_tasks if task.get('status') == 'executing'])
        return min(1.0, active_tasks / self.max_concurrent_tasks)
    
    def _count_time_conflicts(self, current_tasks: List[Dict[str, Any]], new_task: Dict[str, Any]) -> int:
        """计算时间冲突数量"""
        conflicts = 0
        
        new_start = new_task.get('start_time')
        new_end = new_task.get('end_time')
        
        if not new_start or not new_end:
            return 0
        
        for task in current_tasks:
            task_start = task.get('start_time')
            task_end = task.get('end_time')
            
            if task_start and task_end:
                # 检查时间重叠
                if not (new_end <= task_start or new_start >= task_end):
                    conflicts += 1
        
        return conflicts
    
    def _check_resource_constraints(self, resource_status: Dict[str, Any], new_task: Dict[str, Any]) -> Dict[str, Any]:
        """检查资源约束"""
        constraints = {}
        
        # 功率约束
        power_level = resource_status.get('power_level', 1.0)
        required_power = new_task.get('required_power', 0.3)
        constraints['power_sufficient'] = power_level >= required_power
        
        # 载荷状态约束
        payload_status = resource_status.get('payload_status', 'operational')
        constraints['payload_available'] = payload_status == 'operational'
        
        # 通信状态约束
        comm_status = resource_status.get('communication_status', 'active')
        constraints['communication_available'] = comm_status == 'active'
        
        return constraints
    
    def _compute_schedulability_score(
        self,
        current_load: float,
        conflict_count: int,
        resource_constraints: Dict[str, Any]
    ) -> float:
        """计算调度性分数"""
        # 负载因子
        load_factor = 1.0 - current_load
        
        # 冲突因子
        conflict_factor = 1.0 / (1.0 + conflict_count)
        
        # 资源因子
        resource_factor = sum(1 for constraint in resource_constraints.values() if constraint) / len(resource_constraints)
        
        # 综合分数
        score = (load_factor * 0.4 + conflict_factor * 0.4 + resource_factor * 0.2)
        
        return max(0.0, min(1.0, score))
    
    def _calculate_redundancy_factor(self, task_assignments: List[Dict[str, Any]], satellite_resources: List[Dict[str, Any]]) -> float:
        """计算冗余度因子"""
        if not task_assignments:
            return 0.0
        
        # 计算每个任务的备选卫星数量
        redundancy_scores = []
        
        for assignment in task_assignments:
            target_id = assignment.get('target_id')
            assigned_satellites = assignment.get('satellites', [])
            
            # 计算可用但未分配的卫星数量
            available_satellites = len(satellite_resources)
            redundancy = max(0, available_satellites - len(assigned_satellites))
            
            redundancy_scores.append(min(1.0, redundancy / self.min_redundancy_level))
        
        return sum(redundancy_scores) / len(redundancy_scores) if redundancy_scores else 0.0
    
    def _calculate_adaptability_score(self, task_assignments: List[Dict[str, Any]]) -> float:
        """计算适应性分数"""
        if not task_assignments:
            return 0.0
        
        # 基于任务分布的均匀性计算适应性
        satellite_loads = {}
        
        for assignment in task_assignments:
            satellites = assignment.get('satellites', [])
            for sat_id in satellites:
                satellite_loads[sat_id] = satellite_loads.get(sat_id, 0) + 1
        
        if not satellite_loads:
            return 0.0
        
        # 计算负载方差（越小越好）
        loads = list(satellite_loads.values())
        mean_load = sum(loads) / len(loads)
        variance = sum((load - mean_load) ** 2 for load in loads) / len(loads)
        
        # 转换为适应性分数（方差越小，适应性越好）
        adaptability = 1.0 / (1.0 + variance)
        
        return adaptability
    
    def _calculate_failure_tolerance(self, task_assignments: List[Dict[str, Any]], satellite_resources: List[Dict[str, Any]]) -> float:
        """计算故障容忍度"""
        if not task_assignments or not satellite_resources:
            return 0.0
        
        # 模拟单点故障对系统的影响
        total_impact = 0.0
        
        for resource in satellite_resources:
            sat_id = resource.get('satellite_id')
            
            # 计算该卫星故障时的任务完成率损失
            affected_assignments = [
                assign for assign in task_assignments 
                if sat_id in assign.get('satellites', [])
            ]
            
            impact = len(affected_assignments) / len(task_assignments) if task_assignments else 0
            total_impact += impact
        
        # 故障容忍度 = 1 - 平均影响
        failure_tolerance = 1.0 - (total_impact / len(satellite_resources)) if satellite_resources else 0.0
        
        return max(0.0, failure_tolerance)
    
    def _generate_default_disturbance_scenarios(self) -> List[Dict[str, Any]]:
        """生成默认扰动场景"""
        return [
            {
                'scenario_id': 'satellite_failure',
                'description': '卫星故障',
                'probability': 0.05,
                'impact_level': 'high'
            },
            {
                'scenario_id': 'new_target',
                'description': '新目标出现',
                'probability': 0.1,
                'impact_level': 'medium'
            },
            {
                'scenario_id': 'communication_loss',
                'description': '通信中断',
                'probability': 0.02,
                'impact_level': 'high'
            }
        ]
    
    def _analyze_disturbance_scenarios(self, task_assignments: List[Dict[str, Any]], scenarios: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """分析扰动场景"""
        analysis_results = []
        
        for scenario in scenarios:
            scenario_id = scenario.get('scenario_id')
            probability = scenario.get('probability', 0.1)
            
            # 简化的影响分析
            if scenario_id == 'satellite_failure':
                impact_score = 0.8  # 高影响
            elif scenario_id == 'new_target':
                impact_score = 0.5  # 中等影响
            else:
                impact_score = 0.3  # 低影响
            
            analysis_results.append({
                'scenario_id': scenario_id,
                'probability': probability,
                'impact_score': impact_score,
                'risk_level': probability * impact_score,
                'mitigation_available': True
            })
        
        return analysis_results
    
    def _compute_robustness_score(
        self,
        redundancy_factor: float,
        adaptability_score: float,
        failure_tolerance: float,
        scenario_analysis: List[Dict[str, Any]]
    ) -> float:
        """计算鲁棒性分数"""
        # 基础鲁棒性分数
        base_score = (redundancy_factor * 0.4 + adaptability_score * 0.3 + failure_tolerance * 0.3)
        
        # 扰动场景风险调整
        if scenario_analysis:
            avg_risk = sum(s.get('risk_level', 0) for s in scenario_analysis) / len(scenario_analysis)
            risk_adjustment = 1.0 - avg_risk
        else:
            risk_adjustment = 1.0
        
        # 综合鲁棒性分数
        robustness_score = base_score * risk_adjustment
        
        return max(0.0, min(1.0, robustness_score))
