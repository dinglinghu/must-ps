"""
智能体工具模块
提供可见窗口计算、优化目标计算等专用工具
"""

import logging
import json
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# ADK框架导入 - 强制使用真实ADK
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)


@dataclass
class VisibilityResult:
    """可见性计算结果"""
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    max_elevation: float
    min_elevation: float
    access_duration: float  # 秒
    quality_score: float  # 0-1


@dataclass
class GDOPResult:
    """GDOP计算结果"""
    target_id: str
    satellite_pair: Tuple[str, str]
    time_window: Tuple[datetime, datetime]
    gdop_value: float
    tracking_accuracy: float


class VisibilityCalculatorTool(FunctionTool):
    """可见窗口计算工具"""
    
    def __init__(self, stk_manager=None, visibility_calculator=None):
        """
        初始化可见窗口计算工具
        
        Args:
            stk_manager: STK管理器实例
            visibility_calculator: 可见性计算器实例
        """
        self.stk_manager = stk_manager
        self.visibility_calculator = visibility_calculator
        
        super().__init__(func=self.calculate_visibility_windows)
    
    async def calculate_visibility_windows(
        self,
        target_id: str,
        satellite_ids: List[str],
        start_time: str,
        end_time: str
    ) -> str:
        """
        计算目标与卫星的可见窗口
        
        Args:
            target_id: 目标ID
            satellite_ids: 卫星ID列表
            start_time: 开始时间（ISO格式）
            end_time: 结束时间（ISO格式）
            
        Returns:
            JSON格式的可见窗口结果
        """
        try:
            start_dt = datetime.fromisoformat(start_time)
            end_dt = datetime.fromisoformat(end_time)
            
            visibility_results = []
            
            for satellite_id in satellite_ids:
                # 如果有实际的可见性计算器，使用它
                if self.visibility_calculator:
                    # 调用实际的可见性计算
                    windows = await self._calculate_real_visibility(
                        satellite_id, target_id, start_dt, end_dt
                    )
                else:
                    # 使用模拟计算
                    windows = self._calculate_mock_visibility(
                        satellite_id, target_id, start_dt, end_dt
                    )
                
                visibility_results.extend(windows)
            
            # 转换为JSON格式
            result_data = []
            for result in visibility_results:
                result_data.append({
                    'satellite_id': result.satellite_id,
                    'target_id': result.target_id,
                    'start_time': result.start_time.isoformat(),
                    'end_time': result.end_time.isoformat(),
                    'max_elevation': result.max_elevation,
                    'min_elevation': result.min_elevation,
                    'access_duration': result.access_duration,
                    'quality_score': result.quality_score
                })
            
            return json.dumps({
                'status': 'success',
                'target_id': target_id,
                'total_windows': len(result_data),
                'visibility_windows': result_data
            }, indent=2)
            
        except Exception as e:
            logger.error(f"可见窗口计算失败: {e}")
            return json.dumps({
                'status': 'error',
                'error': str(e)
            })
    
    async def _calculate_real_visibility(
        self,
        satellite_id: str,
        target_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[VisibilityResult]:
        """使用实际STK接口计算可见性"""
        try:
            # 这里将集成实际的STK可见性计算
            # 目前返回空列表，待实现
            return []
        except Exception as e:
            logger.error(f"实际可见性计算失败: {e}")
            return []
    
    def _calculate_mock_visibility(
        self,
        satellite_id: str,
        target_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[VisibilityResult]:
        """模拟可见性计算"""
        try:
            results = []
            
            # 模拟生成1-3个可见窗口
            num_windows = min(3, max(1, int((end_time - start_time).total_seconds() / 1800)))  # 每30分钟一个窗口
            
            for i in range(num_windows):
                # 随机生成窗口时间
                window_start = start_time + timedelta(minutes=i*30 + np.random.randint(0, 15))
                window_duration = np.random.uniform(300, 900)  # 5-15分钟
                window_end = window_start + timedelta(seconds=window_duration)
                
                # 确保不超过结束时间
                if window_end > end_time:
                    window_end = end_time
                
                # 模拟高度角
                max_elevation = np.random.uniform(20, 80)
                min_elevation = max(10, max_elevation - np.random.uniform(10, 30))
                
                # 计算质量分数（基于最大高度角和持续时间）
                quality_score = min(1.0, (max_elevation / 90.0) * 0.7 + (window_duration / 900.0) * 0.3)
                
                result = VisibilityResult(
                    satellite_id=satellite_id,
                    target_id=target_id,
                    start_time=window_start,
                    end_time=window_end,
                    max_elevation=max_elevation,
                    min_elevation=min_elevation,
                    access_duration=window_duration,
                    quality_score=quality_score
                )
                
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"模拟可见性计算失败: {e}")
            return []


class OptimizationCalculatorTool(FunctionTool):
    """优化目标计算工具"""
    
    def __init__(self):
        """初始化优化计算工具"""
        super().__init__(func=self.calculate_optimization_metrics)
    
    async def calculate_optimization_metrics(
        self,
        allocation_data: str
    ) -> str:
        """
        计算优化指标
        
        Args:
            allocation_data: 分配方案数据（JSON格式）
            
        Returns:
            JSON格式的优化指标结果
        """
        try:
            allocation = json.loads(allocation_data)
            
            # 计算GDOP
            gdop_results = await self._calculate_gdop(allocation)
            
            # 计算调度性
            schedulability = await self._calculate_schedulability(allocation)
            
            # 计算鲁棒性
            robustness = await self._calculate_robustness(allocation)
            
            # 计算资源利用率
            resource_utilization = await self._calculate_resource_utilization(allocation)
            
            # 综合评分
            overall_score = (
                0.4 * (1.0 / max(gdop_results['average_gdop'], 0.001)) +
                0.3 * schedulability +
                0.2 * robustness +
                0.1 * resource_utilization
            )
            
            result = {
                'status': 'success',
                'target_id': allocation.get('target_id'),
                'optimization_metrics': {
                    'gdop': gdop_results,
                    'schedulability': schedulability,
                    'robustness': robustness,
                    'resource_utilization': resource_utilization,
                    'overall_score': overall_score
                }
            }
            
            return json.dumps(result, indent=2)
            
        except Exception as e:
            logger.error(f"优化指标计算失败: {e}")
            return json.dumps({
                'status': 'error',
                'error': str(e)
            })
    
    async def _calculate_gdop(self, allocation: Dict[str, Any]) -> Dict[str, float]:
        """
        计算几何精度衰减因子(GDOP)
        
        GDOP = L*σ_θ * sqrt((sin²θ₁ + sin²θ₂) / sin⁴(θ₂ - θ₁))
        """
        try:
            satellites = allocation.get('allocated_satellites', [])
            time_windows = allocation.get('time_windows', [])
            
            if len(satellites) < 2:
                return {'average_gdop': float('inf'), 'min_gdop': float('inf'), 'max_gdop': float('inf')}
            
            gdop_values = []
            
            # 对每个时间窗口计算GDOP
            for i in range(len(time_windows) - 1):
                for j in range(i + 1, len(time_windows)):
                    window1 = time_windows[i]
                    window2 = time_windows[j]
                    
                    # 模拟角度计算
                    theta1 = np.radians(window1.get('elevation_angle', 45.0))
                    theta2 = np.radians(window2.get('elevation_angle', 60.0))
                    
                    # GDOP计算
                    if abs(theta2 - theta1) > 0.01:  # 避免除零
                        L = 1.0  # 基线长度因子
                        sigma_theta = 0.001  # 角度测量精度（弧度）
                        
                        numerator = np.sin(theta1)**2 + np.sin(theta2)**2
                        denominator = np.sin(theta2 - theta1)**4
                        
                        gdop = L * sigma_theta * np.sqrt(numerator / denominator)
                        gdop_values.append(gdop)
            
            if not gdop_values:
                # 单卫星情况，使用简化计算
                gdop_values = [2.0]  # 默认GDOP值
            
            return {
                'average_gdop': float(np.mean(gdop_values)),
                'min_gdop': float(np.min(gdop_values)),
                'max_gdop': float(np.max(gdop_values)),
                'gdop_values': [float(g) for g in gdop_values]
            }
            
        except Exception as e:
            logger.error(f"GDOP计算失败: {e}")
            return {'average_gdop': 2.0, 'min_gdop': 2.0, 'max_gdop': 2.0}
    
    async def _calculate_schedulability(self, allocation: Dict[str, Any]) -> float:
        """计算调度性指标"""
        try:
            satellites = allocation.get('allocated_satellites', [])
            time_windows = allocation.get('time_windows', [])
            
            if not satellites or not time_windows:
                return 0.0
            
            # 调度性评估因子
            factors = []
            
            # 1. 卫星数量因子
            satellite_factor = min(1.0, len(satellites) / 3.0)  # 3颗卫星为最优
            factors.append(satellite_factor)
            
            # 2. 时间窗口覆盖因子
            total_duration = sum(
                (datetime.fromisoformat(tw.get('end_time', '')) - 
                 datetime.fromisoformat(tw.get('start_time', ''))).total_seconds()
                for tw in time_windows if tw.get('start_time') and tw.get('end_time')
            )
            coverage_factor = min(1.0, total_duration / 1800.0)  # 30分钟为最优
            factors.append(coverage_factor)
            
            # 3. 资源冲突因子
            conflict_factor = 1.0 - self._calculate_time_conflicts(time_windows)
            factors.append(conflict_factor)
            
            # 综合调度性
            schedulability = np.mean(factors)
            
            return float(schedulability)
            
        except Exception as e:
            logger.error(f"调度性计算失败: {e}")
            return 0.5
    
    async def _calculate_robustness(self, allocation: Dict[str, Any]) -> float:
        """计算鲁棒性指标"""
        try:
            satellites = allocation.get('allocated_satellites', [])
            time_windows = allocation.get('time_windows', [])
            
            if not satellites:
                return 0.0
            
            # 鲁棒性评估因子
            factors = []
            
            # 1. 冗余度因子
            redundancy_factor = min(1.0, (len(satellites) - 1) / 2.0)  # 额外卫星数
            factors.append(redundancy_factor)
            
            # 2. 时间分布因子
            if len(time_windows) > 1:
                time_gaps = []
                sorted_windows = sorted(time_windows, key=lambda x: x.get('start_time', ''))
                
                for i in range(len(sorted_windows) - 1):
                    end_time = datetime.fromisoformat(sorted_windows[i].get('end_time', ''))
                    start_time = datetime.fromisoformat(sorted_windows[i+1].get('start_time', ''))
                    gap = (start_time - end_time).total_seconds()
                    time_gaps.append(gap)
                
                # 时间间隔越均匀，鲁棒性越好
                if time_gaps:
                    gap_variance = np.var(time_gaps)
                    distribution_factor = 1.0 / (1.0 + gap_variance / 10000.0)  # 归一化
                else:
                    distribution_factor = 0.5
            else:
                distribution_factor = 0.3
            
            factors.append(distribution_factor)
            
            # 3. 质量多样性因子
            quality_scores = [tw.get('quality_score', 0.5) for tw in time_windows]
            if quality_scores:
                quality_diversity = 1.0 - np.std(quality_scores)  # 质量分布越均匀越好
                factors.append(max(0.0, quality_diversity))
            
            # 综合鲁棒性
            robustness = np.mean(factors)
            
            return float(robustness)
            
        except Exception as e:
            logger.error(f"鲁棒性计算失败: {e}")
            return 0.5
    
    async def _calculate_resource_utilization(self, allocation: Dict[str, Any]) -> float:
        """计算资源利用率"""
        try:
            satellites = allocation.get('allocated_satellites', [])
            time_windows = allocation.get('time_windows', [])
            
            if not satellites or not time_windows:
                return 0.0
            
            # 计算总的观测时间
            total_observation_time = sum(
                (datetime.fromisoformat(tw.get('end_time', '')) - 
                 datetime.fromisoformat(tw.get('start_time', ''))).total_seconds()
                for tw in time_windows if tw.get('start_time') and tw.get('end_time')
            )
            
            # 假设每颗卫星的可用时间为1小时
            total_available_time = len(satellites) * 3600.0
            
            # 资源利用率
            utilization = min(1.0, total_observation_time / total_available_time)
            
            return float(utilization)
            
        except Exception as e:
            logger.error(f"资源利用率计算失败: {e}")
            return 0.5
    
    def _calculate_time_conflicts(self, time_windows: List[Dict[str, Any]]) -> float:
        """计算时间冲突比例"""
        try:
            if len(time_windows) < 2:
                return 0.0
            
            conflicts = 0
            total_pairs = 0
            
            for i in range(len(time_windows)):
                for j in range(i + 1, len(time_windows)):
                    total_pairs += 1
                    
                    tw1 = time_windows[i]
                    tw2 = time_windows[j]
                    
                    start1 = datetime.fromisoformat(tw1.get('start_time', ''))
                    end1 = datetime.fromisoformat(tw1.get('end_time', ''))
                    start2 = datetime.fromisoformat(tw2.get('start_time', ''))
                    end2 = datetime.fromisoformat(tw2.get('end_time', ''))
                    
                    # 检查时间重叠
                    if not (end1 <= start2 or end2 <= start1):
                        conflicts += 1
            
            return conflicts / total_pairs if total_pairs > 0 else 0.0
            
        except Exception as e:
            logger.error(f"时间冲突计算失败: {e}")
            return 0.0
