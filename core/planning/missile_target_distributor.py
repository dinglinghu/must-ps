"""
导弹目标分发器
基于ADK框架实现导弹目标到最近卫星的智能分发机制
严格按照ADK官方文档要求实现
"""

import logging
import math
import asyncio
from typing import Dict, List, Any, Optional, Tuple, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from .satellite_agent import SatelliteAgent, TaskInfo
from ..utils.config_manager import get_config_manager
from ..utils.time_manager import get_time_manager

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于导弹目标分发器")


@dataclass
class MissileTarget:
    """导弹目标数据结构"""
    missile_id: str
    launch_position: Dict[str, float]  # {lat, lon, alt}
    target_position: Dict[str, float]  # {lat, lon, alt}
    launch_time: datetime
    flight_time: float  # 飞行时间（秒）
    trajectory_points: List[Dict[str, Any]]  # 轨迹点列表
    priority: float
    threat_level: str
    metadata: Dict[str, Any]


@dataclass
class DistanceCalculationResult:
    """距离计算结果"""
    missile_id: str
    satellite_id: str
    min_distance: float  # 最小距离（公里）
    avg_distance: float  # 平均距离（公里）
    closest_time: datetime  # 最近距离时刻
    visibility_windows: List[Dict[str, Any]]  # 可见窗口列表
    calculation_confidence: float  # 计算置信度


class MissileTargetDistributor(BaseAgent):
    """
    导弹目标分发器
    
    基于ADK的BaseAgent实现，负责：
    1. 收集仿真调度智能体检测到的导弹目标
    2. 计算所有导弹到所有卫星的距离
    3. 基于距离优势将导弹分发给最近的卫星智能体
    """
    
    def __init__(self, config_manager=None):
        """
        初始化导弹目标分发器
        
        Args:
            config_manager: 配置管理器实例
        """
        # 初始化ADK BaseAgent
        super().__init__(
            name="MissileTargetDistributor",
            description="基于ADK框架的导弹目标智能分发器"
        )
        
        self._config_manager = config_manager or get_config_manager()
        self._time_manager = get_time_manager(self._config_manager)
        
        # 获取配置
        self._system_config = self._config_manager.config.get('multi_agent_system', {})
        self._physics_config = self._config_manager.config.get('physics', {})
        
        # 地球半径（公里）
        self._earth_radius = self._physics_config.get('earth_radius', 6371)
        
        # 分发策略配置
        self._distribution_strategy = self._system_config.get('simulation_scheduler', {}).get(
            'task_distribution_strategy', 'nearest_satellite'
        )
        
        # 缓存
        self._distance_cache: Dict[str, DistanceCalculationResult] = {}
        self._last_calculation_time: Optional[datetime] = None
        
        logger.info("🎯 导弹目标分发器初始化完成")
    
    async def distribute_missiles_to_satellites(
        self,
        missile_targets: List[MissileTarget],
        satellite_agents: Dict[str, SatelliteAgent]
    ) -> Dict[str, List[str]]:
        """
        将导弹目标分发给最近的卫星智能体
        
        Args:
            missile_targets: 导弹目标列表
            satellite_agents: 卫星智能体字典
            
        Returns:
            分发结果 {satellite_id: [missile_ids]}
        """
        try:
            if not missile_targets or not satellite_agents:
                logger.warning("⚠️ 导弹目标或卫星智能体为空，跳过分发")
                return {}
            
            logger.info(f"🎯 开始分发 {len(missile_targets)} 个导弹目标到 {len(satellite_agents)} 个卫星")
            
            # 计算所有导弹到所有卫星的距离
            distance_matrix = await self._calculate_distance_matrix(missile_targets, satellite_agents)
            
            # 基于距离优势进行分发
            distribution_result = await self._perform_distance_based_distribution(
                missile_targets, satellite_agents, distance_matrix
            )
            
            # 记录分发结果
            await self._log_distribution_results(distribution_result, distance_matrix)

            # 实际将任务发送给卫星智能体
            await self._send_tasks_to_satellites(distribution_result, missile_targets, satellite_agents)

            return distribution_result
            
        except Exception as e:
            logger.error(f"❌ 导弹目标分发失败: {e}")
            return {}
    
    async def _calculate_distance_matrix(
        self,
        missile_targets: List[MissileTarget],
        satellite_agents: Dict[str, SatelliteAgent]
    ) -> Dict[str, Dict[str, DistanceCalculationResult]]:
        """
        计算导弹到卫星的距离矩阵
        
        Args:
            missile_targets: 导弹目标列表
            satellite_agents: 卫星智能体字典
            
        Returns:
            距离矩阵 {missile_id: {satellite_id: DistanceCalculationResult}}
        """
        try:
            distance_matrix = {}
            current_time = self._time_manager.get_current_simulation_time()
            
            for missile in missile_targets:
                distance_matrix[missile.missile_id] = {}
                
                for satellite_id, satellite_agent in satellite_agents.items():
                    # 计算导弹轨迹与卫星轨道的距离
                    distance_result = await self._calculate_missile_satellite_distance(
                        missile, satellite_agent, current_time
                    )
                    
                    distance_matrix[missile.missile_id][satellite_id] = distance_result
            
            logger.info(f"📊 完成距离矩阵计算: {len(missile_targets)}×{len(satellite_agents)}")
            return distance_matrix
            
        except Exception as e:
            logger.error(f"❌ 距离矩阵计算失败: {e}")
            return {}
    
    async def _calculate_missile_satellite_distance(
        self,
        missile: MissileTarget,
        satellite_agent: SatelliteAgent,
        current_time: datetime
    ) -> DistanceCalculationResult:
        """
        计算单个导弹与卫星的距离
        
        Args:
            missile: 导弹目标
            satellite_agent: 卫星智能体
            current_time: 当前时间
            
        Returns:
            距离计算结果
        """
        try:
            # 获取卫星当前位置（简化计算，实际应该获取轨道预测位置）
            satellite_position = await self._get_satellite_position(satellite_agent, current_time)
            
            # 计算导弹轨迹上各点到卫星的距离
            distances = []
            closest_distance = float('inf')
            closest_time = current_time
            
            for trajectory_point in missile.trajectory_points:
                # 计算球面距离
                distance = self._calculate_spherical_distance(
                    trajectory_point['position'],
                    satellite_position
                )
                distances.append(distance)
                
                if distance < closest_distance:
                    closest_distance = distance
                    closest_time = trajectory_point.get('time', current_time)
            
            # 计算平均距离
            avg_distance = sum(distances) / len(distances) if distances else float('inf')
            
            # 计算可见窗口（简化版本）
            visibility_windows = await self._calculate_visibility_windows(
                missile, satellite_agent, current_time
            )
            
            # 计算置信度
            confidence = self._calculate_distance_confidence(distances, visibility_windows)
            
            return DistanceCalculationResult(
                missile_id=missile.missile_id,
                satellite_id=satellite_agent.satellite_id,
                min_distance=closest_distance,
                avg_distance=avg_distance,
                closest_time=closest_time,
                visibility_windows=visibility_windows,
                calculation_confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"❌ 计算导弹 {missile.missile_id} 与卫星 {satellite_agent.satellite_id} 距离失败: {e}")
            return DistanceCalculationResult(
                missile_id=missile.missile_id,
                satellite_id=satellite_agent.satellite_id,
                min_distance=float('inf'),
                avg_distance=float('inf'),
                closest_time=current_time,
                visibility_windows=[],
                calculation_confidence=0.0
            )
    
    def _calculate_spherical_distance(
        self,
        pos1: Dict[str, float],
        pos2: Dict[str, float]
    ) -> float:
        """
        计算球面距离（Haversine公式）
        
        Args:
            pos1: 位置1 {lat, lon, alt}
            pos2: 位置2 {lat, lon, alt}
            
        Returns:
            距离（公里）
        """
        try:
            lat1, lon1, alt1 = pos1['lat'], pos1['lon'], pos1.get('alt', 0)
            lat2, lon2, alt2 = pos2['lat'], pos2['lon'], pos2.get('alt', 0)
            
            # 转换为弧度
            lat1_rad = math.radians(lat1)
            lon1_rad = math.radians(lon1)
            lat2_rad = math.radians(lat2)
            lon2_rad = math.radians(lon2)
            
            # Haversine公式
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            a = (math.sin(dlat/2)**2 + 
                 math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2)
            c = 2 * math.asin(math.sqrt(a))
            
            # 地面距离
            ground_distance = self._earth_radius * c
            
            # 考虑高度差
            height_diff = abs(alt2 - alt1)
            total_distance = math.sqrt(ground_distance**2 + height_diff**2)
            
            return total_distance
            
        except Exception as e:
            logger.error(f"❌ 球面距离计算失败: {e}")
            return float('inf')
    
    async def _get_satellite_position(
        self,
        satellite_agent: SatelliteAgent,
        time: datetime
    ) -> Dict[str, float]:
        """
        获取卫星在指定时间的位置
        
        Args:
            satellite_agent: 卫星智能体
            time: 指定时间
            
        Returns:
            位置信息 {lat, lon, alt}
        """
        try:
            # 简化实现：返回模拟位置
            # 实际应该从STK或轨道预测模块获取精确位置
            return {
                'lat': 0.0,  # 纬度
                'lon': 0.0,  # 经度
                'alt': 1800.0  # 高度（公里）
            }
            
        except Exception as e:
            logger.error(f"❌ 获取卫星位置失败: {e}")
            return {'lat': 0.0, 'lon': 0.0, 'alt': 0.0}
    
    async def _calculate_visibility_windows(
        self,
        missile: MissileTarget,
        satellite_agent: SatelliteAgent,
        current_time: datetime
    ) -> List[Dict[str, Any]]:
        """
        计算可见窗口
        
        Args:
            missile: 导弹目标
            satellite_agent: 卫星智能体
            current_time: 当前时间
            
        Returns:
            可见窗口列表
        """
        try:
            # 简化实现：基于距离阈值判断可见性
            visibility_threshold = 2000.0  # 2000公里可见阈值
            
            windows = []
            window_start = None
            
            for i, trajectory_point in enumerate(missile.trajectory_points):
                satellite_pos = await self._get_satellite_position(satellite_agent, current_time)
                distance = self._calculate_spherical_distance(
                    trajectory_point['position'],
                    satellite_pos
                )
                
                if distance <= visibility_threshold:
                    if window_start is None:
                        window_start = i
                else:
                    if window_start is not None:
                        windows.append({
                            'start_index': window_start,
                            'end_index': i - 1,
                            'duration': (i - window_start) * 10,  # 假设10秒间隔
                            'min_distance': visibility_threshold
                        })
                        window_start = None
            
            # 处理最后一个窗口
            if window_start is not None:
                windows.append({
                    'start_index': window_start,
                    'end_index': len(missile.trajectory_points) - 1,
                    'duration': (len(missile.trajectory_points) - window_start) * 10,
                    'min_distance': visibility_threshold
                })
            
            return windows
            
        except Exception as e:
            logger.error(f"❌ 可见窗口计算失败: {e}")
            return []
    
    def _calculate_distance_confidence(
        self,
        distances: List[float],
        visibility_windows: List[Dict[str, Any]]
    ) -> float:
        """
        计算距离计算的置信度

        Args:
            distances: 距离列表
            visibility_windows: 可见窗口列表

        Returns:
            置信度 (0.0-1.0)
        """
        try:
            if not distances:
                return 0.0

            # 基于距离变化的稳定性和可见窗口数量计算置信度
            distance_variance = sum((d - sum(distances)/len(distances))**2 for d in distances) / len(distances)
            stability_score = max(0.0, 1.0 - distance_variance / 1000000)  # 归一化

            visibility_score = min(1.0, len(visibility_windows) / 3.0)  # 最多3个窗口得满分

            confidence = (stability_score + visibility_score) / 2.0
            return max(0.0, min(1.0, confidence))

        except Exception as e:
            logger.error(f"❌ 置信度计算失败: {e}")
            return 0.0

    async def _perform_distance_based_distribution(
        self,
        missile_targets: List[MissileTarget],
        satellite_agents: Dict[str, SatelliteAgent],
        distance_matrix: Dict[str, Dict[str, DistanceCalculationResult]]
    ) -> Dict[str, List[str]]:
        """
        基于距离优势执行分发

        Args:
            missile_targets: 导弹目标列表
            satellite_agents: 卫星智能体字典
            distance_matrix: 距离矩阵

        Returns:
            分发结果 {satellite_id: [missile_ids]}
        """
        try:
            distribution_result = {sat_id: [] for sat_id in satellite_agents.keys()}

            # 为每个导弹找到最近的卫星
            for missile in missile_targets:
                missile_id = missile.missile_id

                if missile_id not in distance_matrix:
                    logger.warning(f"⚠️ 导弹 {missile_id} 未找到距离计算结果")
                    continue

                # 找到距离最近的卫星
                best_satellite_id = None
                best_distance = float('inf')
                best_confidence = 0.0

                for satellite_id, distance_result in distance_matrix[missile_id].items():
                    # 综合考虑距离和置信度
                    weighted_score = (distance_result.min_distance *
                                    (2.0 - distance_result.calculation_confidence))

                    if weighted_score < best_distance:
                        best_distance = weighted_score
                        best_satellite_id = satellite_id
                        best_confidence = distance_result.calculation_confidence

                # 分配给最佳卫星
                if best_satellite_id:
                    distribution_result[best_satellite_id].append(missile_id)
                    logger.info(f"🎯 导弹 {missile_id} 分配给卫星 {best_satellite_id} "
                              f"(距离: {best_distance:.2f}km, 置信度: {best_confidence:.2f})")

            return distribution_result

        except Exception as e:
            logger.error(f"❌ 基于距离的分发失败: {e}")
            return {}

    async def _log_distribution_results(
        self,
        distribution_result: Dict[str, List[str]],
        distance_matrix: Dict[str, Dict[str, DistanceCalculationResult]]
    ):
        """
        记录分发结果

        Args:
            distribution_result: 分发结果
            distance_matrix: 距离矩阵
        """
        try:
            total_missiles = sum(len(missiles) for missiles in distribution_result.values())
            active_satellites = sum(1 for missiles in distribution_result.values() if missiles)

            logger.info(f"📊 分发结果统计:")
            logger.info(f"   总导弹数: {total_missiles}")
            logger.info(f"   参与卫星数: {active_satellites}")

            for satellite_id, missile_ids in distribution_result.items():
                if missile_ids:
                    logger.info(f"   卫星 {satellite_id}: {len(missile_ids)} 个导弹 {missile_ids}")

        except Exception as e:
            logger.error(f"❌ 记录分发结果失败: {e}")

    async def run(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        ADK BaseAgent运行方法

        Args:
            ctx: 调用上下文

        Yields:
            ADK事件流
        """
        try:
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="导弹目标分发器已启动，等待分发任务...")])
            )

            # 这里可以添加定期检查和分发逻辑
            # 实际使用时会被外部调用 distribute_missiles_to_satellites 方法

        except Exception as e:
            logger.error(f"❌ 导弹目标分发器运行异常: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"运行异常: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def _send_tasks_to_satellites(
        self,
        distribution_result: Dict[str, List[str]],
        missile_targets: List[MissileTarget],
        satellite_agents: Dict[str, SatelliteAgent]
    ):
        """
        将任务实际发送给卫星智能体

        Args:
            distribution_result: 分发结果
            missile_targets: 导弹目标列表
            satellite_agents: 卫星智能体字典
        """
        try:
            # 创建导弹ID到导弹对象的映射
            missile_dict = {missile.missile_id: missile for missile in missile_targets}

            for satellite_id, missile_ids in distribution_result.items():
                if not missile_ids:
                    continue

                satellite_agent = satellite_agents.get(satellite_id)
                if not satellite_agent:
                    logger.warning(f"⚠️ 未找到卫星智能体: {satellite_id}")
                    continue

                # 为每个分配的导弹创建任务
                for missile_id in missile_ids:
                    missile = missile_dict.get(missile_id)
                    if not missile:
                        logger.warning(f"⚠️ 未找到导弹目标: {missile_id}")
                        continue

                    # 创建任务信息
                    from .satellite_agent import TaskInfo
                    task = TaskInfo(
                        task_id=f"track_{missile_id}_{satellite_id}",
                        target_id=missile_id,
                        priority=missile.priority,
                        start_time=missile.launch_time,
                        end_time=missile.launch_time + timedelta(seconds=missile.flight_time),
                        status='assigned'
                    )

                    # 发送任务给卫星智能体
                    await self._send_task_to_satellite(satellite_agent, task, missile)

        except Exception as e:
            logger.error(f"❌ 发送任务给卫星智能体失败: {e}")

    async def _send_task_to_satellite(self, satellite_agent: SatelliteAgent, task: TaskInfo, missile: MissileTarget):
        """
        发送单个任务给卫星智能体

        Args:
            satellite_agent: 卫星智能体
            task: 任务信息
            missile: 导弹目标
        """
        try:
            logger.info(f"📤 发送任务 {task.task_id} 给卫星 {satellite_agent.satellite_id}")

            # 调用卫星智能体的接收任务方法
            # 这将触发卫星智能体创建讨论组
            await satellite_agent.receive_task(task, missile)

        except Exception as e:
            logger.error(f"❌ 发送任务给卫星 {satellite_agent.satellite_id} 失败: {e}")
