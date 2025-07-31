"""
元任务管理器
负责建立元任务区间、轨迹填充、多目标时间段对齐和可见性分析
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from dataclasses import dataclass
import json

logger = logging.getLogger(__name__)


@dataclass
class MetaTaskWindow:
    """元任务窗口数据结构"""
    window_id: str
    start_time: datetime
    end_time: datetime
    duration: float  # 秒
    missiles: List[str]  # 该窗口内的导弹ID列表
    trajectory_segments: Dict[str, List[Dict]]  # 每个导弹在该窗口的轨迹段
    visibility_windows: Dict[str, Dict[str, List[Dict]]]  # 可见性窗口 {missile_id: {satellite_id: [windows]}}


@dataclass
class MetaTaskSet:
    """元任务信息集"""
    collection_time: datetime
    time_range: Tuple[datetime, datetime]  # (start, end)
    meta_windows: List[MetaTaskWindow]
    total_missiles: List[str]
    alignment_resolution: float  # 对齐时间分辨率(秒)
    metadata: Dict[str, Any]


class MetaTaskManager:
    """元任务管理器"""
    
    def __init__(self, config_manager, time_manager, missile_manager, visibility_calculator):
        """
        初始化元任务管理器
        
        Args:
            config_manager: 配置管理器
            time_manager: 时间管理器
            missile_manager: 导弹管理器
            visibility_calculator: 可见性计算器
        """
        self.config_manager = config_manager
        self.time_manager = time_manager
        self.missile_manager = missile_manager
        self.visibility_calculator = visibility_calculator
        
        # 获取元任务配置
        self.meta_task_config = self.config_manager.get_meta_task_config()
        
        # 输出目录
        self.output_dir = Path("output/meta_tasks")
        self.gantt_dir = Path("output/gantt_charts")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.gantt_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("🎯 元任务管理器初始化完成")
    
    def create_meta_task_set(self, collection_time: datetime, active_missiles: List[str]) -> Optional[MetaTaskSet]:
        """
        创建元任务信息集
        
        Args:
            collection_time: 当前数据采集时刻
            active_missiles: 当前在飞行的导弹列表
            
        Returns:
            元任务信息集
        """
        try:
            logger.info(f"🎯 创建元任务信息集: 采集时间={collection_time}, 导弹数量={len(active_missiles)}")
            
            if not active_missiles:
                logger.warning("⚠️ 没有在飞行的导弹，无法创建元任务集")
                return None
            
            # 1. 建立元任务区间
            time_range = self._establish_meta_task_interval(collection_time, active_missiles)
            if not time_range:
                logger.error("❌ 无法建立元任务区间")
                return None
            
            logger.info(f"✅ 元任务区间: {time_range[0]} - {time_range[1]}")
            
            # 2. 切分元任务窗口
            meta_windows = self._split_meta_task_windows(time_range, active_missiles)
            if not meta_windows:
                logger.error("❌ 无法切分元任务窗口")
                return None
            
            logger.info(f"✅ 切分出 {len(meta_windows)} 个元任务窗口")
            
            # 3. 填充轨迹数据并对齐
            self._fill_trajectory_data(meta_windows, active_missiles)
            
            # 4. 计算可见性窗口
            self._calculate_visibility_windows(meta_windows)
            
            # 5. 创建元任务信息集
            meta_task_set = MetaTaskSet(
                collection_time=collection_time,
                time_range=time_range,
                meta_windows=meta_windows,
                total_missiles=active_missiles.copy(),
                alignment_resolution=self.meta_task_config["trajectory_alignment"]["time_resolution"],
                metadata={
                    "window_count": len(meta_windows),
                    "total_duration": (time_range[1] - time_range[0]).total_seconds(),
                    "config": self.meta_task_config
                }
            )
            
            logger.info(f"✅ 元任务信息集创建完成")
            return meta_task_set
            
        except Exception as e:
            logger.error(f"❌ 创建元任务信息集失败: {e}")
            return None
    
    def _establish_meta_task_interval(self, collection_time: datetime, active_missiles: List[str]) -> Optional[Tuple[datetime, datetime]]:
        """
        建立元任务区间
        以当前数据采集时刻为起点，所有在飞导弹结束最晚时刻为终点
        
        Args:
            collection_time: 当前数据采集时刻
            active_missiles: 在飞行的导弹列表
            
        Returns:
            (start_time, end_time) 或 None
        """
        try:
            start_time = collection_time
            latest_end_time = collection_time
            
            # 找到所有导弹中结束最晚的时刻
            for missile_id in active_missiles:
                try:
                    # 获取导弹的撞击时间
                    launch_time, impact_time = self.missile_manager.get_missile_launch_and_impact_times(missile_id)
                    
                    if impact_time and impact_time > latest_end_time:
                        latest_end_time = impact_time
                        
                except Exception as e:
                    logger.warning(f"⚠️ 获取导弹 {missile_id} 时间信息失败: {e}")
                    continue
            
            # 如果没有有效的结束时间，使用默认扩展
            if latest_end_time == collection_time:
                max_extension = self.meta_task_config["time_window"]["max_extension"]
                latest_end_time = collection_time + timedelta(seconds=max_extension)
                logger.warning(f"⚠️ 使用默认扩展时间: {max_extension}秒")
            
            return (start_time, latest_end_time)
            
        except Exception as e:
            logger.error(f"❌ 建立元任务区间失败: {e}")
            return None
    
    def _split_meta_task_windows(self, time_range: Tuple[datetime, datetime], active_missiles: List[str]) -> List[MetaTaskWindow]:
        """
        按照固定的元任务时间窗口进行切分
        
        Args:
            time_range: 总时间范围
            active_missiles: 导弹列表
            
        Returns:
            元任务窗口列表
        """
        try:
            windows = []
            start_time, end_time = time_range
            
            window_duration = self.meta_task_config["time_window"]["fixed_duration"]
            overlap_duration = self.meta_task_config["time_window"]["overlap_duration"]
            
            current_start = start_time
            window_index = 0
            
            while current_start < end_time:
                # 计算当前窗口的结束时间
                current_end = current_start + timedelta(seconds=window_duration)
                
                # 如果超出总范围，调整到总范围结束时间
                if current_end > end_time:
                    current_end = end_time
                
                # 创建窗口
                window = MetaTaskWindow(
                    window_id=f"MetaWindow_{window_index:03d}",
                    start_time=current_start,
                    end_time=current_end,
                    duration=(current_end - current_start).total_seconds(),
                    missiles=[],
                    trajectory_segments={},
                    visibility_windows={}
                )
                
                # 确定该窗口内的导弹
                window.missiles = self._get_missiles_in_window(active_missiles, current_start, current_end)
                
                windows.append(window)
                
                # 计算下一个窗口的开始时间（考虑重叠）
                current_start = current_start + timedelta(seconds=window_duration - overlap_duration)
                window_index += 1
                
                # 防止无限循环
                if window_index > 100:
                    logger.warning("⚠️ 窗口数量超过限制，停止切分")
                    break
            
            return windows
            
        except Exception as e:
            logger.error(f"❌ 切分元任务窗口失败: {e}")
            return []
    
    def _get_missiles_in_window(self, active_missiles: List[str], window_start: datetime, window_end: datetime) -> List[str]:
        """
        获取在指定时间窗口内飞行的导弹
        
        Args:
            active_missiles: 所有在飞导弹
            window_start: 窗口开始时间
            window_end: 窗口结束时间
            
        Returns:
            在该窗口内飞行的导弹列表
        """
        missiles_in_window = []
        
        for missile_id in active_missiles:
            try:
                launch_time, impact_time = self.missile_manager.get_missile_launch_and_impact_times(missile_id)
                
                if launch_time and impact_time:
                    # 检查导弹飞行时间是否与窗口时间有重叠
                    if (launch_time < window_end and impact_time > window_start):
                        missiles_in_window.append(missile_id)
                        
            except Exception as e:
                logger.debug(f"检查导弹 {missile_id} 窗口重叠失败: {e}")
                continue
        
        return missiles_in_window

    def _fill_trajectory_data(self, meta_windows: List[MetaTaskWindow], active_missiles: List[str]):
        """
        填充轨迹数据并进行多目标时间段对齐

        Args:
            meta_windows: 元任务窗口列表
            active_missiles: 导弹列表
        """
        try:
            logger.info("🎯 开始填充轨迹数据并进行时间段对齐")

            time_resolution = self.meta_task_config["trajectory_alignment"]["time_resolution"]

            for window in meta_windows:
                logger.debug(f"处理窗口: {window.window_id}")

                for missile_id in window.missiles:
                    try:
                        # 获取导弹轨迹信息
                        trajectory_info = self.missile_manager.get_missile_trajectory_info(missile_id)

                        if trajectory_info and trajectory_info.get("trajectory_points"):
                            # 提取该窗口时间范围内的轨迹段
                            window_trajectory = self._extract_window_trajectory(
                                trajectory_info, window.start_time, window.end_time, time_resolution
                            )

                            if window_trajectory:
                                window.trajectory_segments[missile_id] = window_trajectory
                                logger.debug(f"✅ 导弹 {missile_id} 轨迹数据填充完成: {len(window_trajectory)} 个点")
                            else:
                                logger.debug(f"⚠️ 导弹 {missile_id} 在窗口 {window.window_id} 内无轨迹数据")
                        else:
                            logger.warning(f"⚠️ 无法获取导弹 {missile_id} 的轨迹信息")

                    except Exception as e:
                        logger.warning(f"⚠️ 处理导弹 {missile_id} 轨迹数据失败: {e}")
                        continue

            logger.info("✅ 轨迹数据填充和对齐完成")

        except Exception as e:
            logger.error(f"❌ 填充轨迹数据失败: {e}")

    def _extract_window_trajectory(self, trajectory_info: Dict, window_start: datetime,
                                 window_end: datetime, time_resolution: float) -> List[Dict]:
        """
        提取指定时间窗口内的轨迹段并进行时间对齐

        Args:
            trajectory_info: 导弹轨迹信息
            window_start: 窗口开始时间
            window_end: 窗口结束时间
            time_resolution: 时间分辨率(秒)

        Returns:
            对齐后的轨迹点列表
        """
        try:
            trajectory_points = trajectory_info.get("trajectory_points", [])
            launch_time = trajectory_info.get("launch_time")

            if not trajectory_points or not launch_time:
                return []

            window_trajectory = []

            # 计算窗口相对于发射时间的时间范围
            window_start_rel = (window_start - launch_time).total_seconds()
            window_end_rel = (window_end - launch_time).total_seconds()

            # 按时间分辨率生成对齐的时间点
            current_time = max(0, window_start_rel)  # 不能早于发射时间

            while current_time <= window_end_rel:
                # 在轨迹点中插值获取该时间点的位置
                interpolated_point = self._interpolate_trajectory_point(trajectory_points, current_time)

                if interpolated_point:
                    # 添加绝对时间信息
                    interpolated_point["absolute_time"] = launch_time + timedelta(seconds=current_time)
                    interpolated_point["relative_time"] = current_time
                    window_trajectory.append(interpolated_point)

                current_time += time_resolution

            return window_trajectory

        except Exception as e:
            logger.error(f"❌ 提取窗口轨迹失败: {e}")
            return []

    def _interpolate_trajectory_point(self, trajectory_points: List[Dict], target_time: float) -> Optional[Dict]:
        """
        在轨迹点中插值获取指定时间的位置

        Args:
            trajectory_points: 轨迹点列表
            target_time: 目标时间(相对于发射时间的秒数)

        Returns:
            插值后的轨迹点
        """
        try:
            if not trajectory_points:
                return None

            # 找到目标时间前后的轨迹点
            before_point = None
            after_point = None

            for point in trajectory_points:
                point_time = point.get("time", 0)

                if point_time <= target_time:
                    before_point = point
                elif point_time > target_time and after_point is None:
                    after_point = point
                    break

            # 如果目标时间在轨迹范围外
            if before_point is None:
                return trajectory_points[0] if trajectory_points else None
            if after_point is None:
                return before_point

            # 线性插值
            t1, t2 = before_point["time"], after_point["time"]
            if t2 == t1:
                return before_point

            ratio = (target_time - t1) / (t2 - t1)

            interpolated = {
                "time": target_time,
                "lat": before_point["lat"] + ratio * (after_point["lat"] - before_point["lat"]),
                "lon": before_point["lon"] + ratio * (after_point["lon"] - before_point["lon"]),
                "alt": before_point["alt"] + ratio * (after_point["alt"] - before_point["alt"])
            }

            return interpolated

        except Exception as e:
            logger.error(f"❌ 轨迹点插值失败: {e}")
            return None

    def _calculate_visibility_windows(self, meta_windows: List[MetaTaskWindow]):
        """
        计算基于元任务的可见性窗口

        Args:
            meta_windows: 元任务窗口列表
        """
        try:
            logger.info("🎯 开始计算元任务可见性窗口")

            for window in meta_windows:
                logger.debug(f"计算窗口 {window.window_id} 的可见性")

                for missile_id in window.missiles:
                    window.visibility_windows[missile_id] = {}

                    try:
                        # 获取所有卫星列表
                        from src.constellation.constellation_manager import get_constellation_manager
                        constellation_manager = get_constellation_manager()
                        satellite_list = constellation_manager.get_satellite_list()

                        for satellite_id in satellite_list:
                            try:
                                # 计算卫星对导弹的可见性
                                visibility_result = self.visibility_calculator.calculate_satellite_to_missile_access(
                                    satellite_id, missile_id
                                )

                                if visibility_result and visibility_result.get("success"):
                                    # 提取该窗口时间范围内的可见性窗口
                                    window_visibility = self._extract_window_visibility(
                                        visibility_result, window.start_time, window.end_time
                                    )

                                    window.visibility_windows[missile_id][satellite_id] = window_visibility

                                    if window_visibility:
                                        logger.debug(f"✅ {satellite_id}->{missile_id} 可见性: {len(window_visibility)} 个窗口")
                                else:
                                    window.visibility_windows[missile_id][satellite_id] = []

                            except Exception as e:
                                logger.debug(f"计算 {satellite_id}->{missile_id} 可见性失败: {e}")
                                window.visibility_windows[missile_id][satellite_id] = []
                                continue

                    except Exception as e:
                        logger.warning(f"⚠️ 处理导弹 {missile_id} 可见性失败: {e}")
                        continue

            logger.info("✅ 元任务可见性窗口计算完成")

        except Exception as e:
            logger.error(f"❌ 计算可见性窗口失败: {e}")

    def _extract_window_visibility(self, visibility_result: Dict, window_start: datetime,
                                 window_end: datetime) -> List[Dict]:
        """
        提取指定时间窗口内的可见性窗口

        Args:
            visibility_result: 可见性计算结果
            window_start: 窗口开始时间
            window_end: 窗口结束时间

        Returns:
            窗口内的可见性时间段列表
        """
        try:
            access_intervals = visibility_result.get("access_intervals", [])
            window_visibility = []

            for interval in access_intervals:
                try:
                    # 解析时间字符串
                    start_str = interval.get("start", "")
                    stop_str = interval.get("stop", "")

                    if not start_str or not stop_str:
                        continue

                    # 转换为datetime对象
                    interval_start = datetime.strptime(start_str, "%d %b %Y %H:%M:%S.%f")
                    interval_end = datetime.strptime(stop_str, "%d %b %Y %H:%M:%S.%f")

                    # 检查是否与窗口时间有重叠
                    if interval_start < window_end and interval_end > window_start:
                        # 计算重叠部分
                        overlap_start = max(interval_start, window_start)
                        overlap_end = min(interval_end, window_end)

                        window_visibility.append({
                            "start": overlap_start,
                            "end": overlap_end,
                            "duration": (overlap_end - overlap_start).total_seconds(),
                            "original_start": interval_start,
                            "original_end": interval_end
                        })

                except Exception as e:
                    logger.debug(f"解析可见性时间间隔失败: {e}")
                    continue

            return window_visibility

        except Exception as e:
            logger.error(f"❌ 提取窗口可见性失败: {e}")
            return []

    def save_meta_task_set(self, meta_task_set: MetaTaskSet) -> Optional[str]:
        """
        保存元任务信息集到文件

        Args:
            meta_task_set: 元任务信息集

        Returns:
            保存的文件路径
        """
        try:
            # 生成文件名
            timestamp = meta_task_set.collection_time.strftime("%Y%m%d_%H%M%S")
            filename = f"meta_task_set_{timestamp}.json"
            filepath = self.output_dir / filename

            # 转换为可序列化的格式
            serializable_data = self._convert_to_serializable(meta_task_set)

            # 保存到文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(serializable_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ 元任务信息集保存成功: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"❌ 保存元任务信息集失败: {e}")
            return None

    def generate_gantt_charts(self, meta_task_set: MetaTaskSet) -> Dict[str, str]:
        """
        生成甘特图

        Args:
            meta_task_set: 元任务信息集

        Returns:
            生成的甘特图文件路径字典
        """
        try:
            from .gantt_chart_generator import GanttChartGenerator

            gantt_generator = GanttChartGenerator(self.config_manager)
            generated_files = {}

            # 生成元任务甘特图
            timestamp = meta_task_set.collection_time.strftime("%Y%m%d_%H%M%S")
            meta_task_path = self.gantt_dir / f"meta_task_gantt_{timestamp}"

            if gantt_generator.generate_meta_task_gantt(meta_task_set, str(meta_task_path)):
                generated_files["meta_task"] = f"{meta_task_path}.{self.meta_task_config['gantt_chart']['output_format']}"

            # 为每个导弹生成可见性甘特图
            for missile_id in meta_task_set.total_missiles:
                visibility_path = self.gantt_dir / f"visibility_gantt_{missile_id}_{timestamp}"

                if gantt_generator.generate_visibility_gantt(meta_task_set, missile_id, str(visibility_path)):
                    generated_files[f"visibility_{missile_id}"] = f"{visibility_path}.{self.meta_task_config['gantt_chart']['output_format']}"

            logger.info(f"✅ 甘特图生成完成: {len(generated_files)} 个文件")
            return generated_files

        except Exception as e:
            logger.error(f"❌ 生成甘特图失败: {e}")
            return {}

    def _convert_to_serializable(self, meta_task_set: MetaTaskSet) -> Dict[str, Any]:
        """
        将元任务信息集转换为可序列化的格式

        Args:
            meta_task_set: 元任务信息集

        Returns:
            可序列化的字典
        """
        try:
            serializable_windows = []

            for window in meta_task_set.meta_windows:
                # 转换轨迹段
                serializable_trajectory = {}
                for missile_id, trajectory in window.trajectory_segments.items():
                    serializable_trajectory[missile_id] = [
                        {
                            "time": point.get("time", 0),
                            "lat": point.get("lat", 0),
                            "lon": point.get("lon", 0),
                            "alt": point.get("alt", 0),
                            "absolute_time": point.get("absolute_time").isoformat() if point.get("absolute_time") else None,
                            "relative_time": point.get("relative_time", 0)
                        } for point in trajectory
                    ]

                # 转换可见性窗口
                serializable_visibility = {}
                for missile_id, satellite_dict in window.visibility_windows.items():
                    serializable_visibility[missile_id] = {}
                    for satellite_id, vis_windows in satellite_dict.items():
                        serializable_visibility[missile_id][satellite_id] = [
                            {
                                "start": vis_window["start"].isoformat(),
                                "end": vis_window["end"].isoformat(),
                                "duration": vis_window["duration"],
                                "original_start": vis_window["original_start"].isoformat(),
                                "original_end": vis_window["original_end"].isoformat()
                            } for vis_window in vis_windows
                        ]

                serializable_windows.append({
                    "window_id": window.window_id,
                    "start_time": window.start_time.isoformat(),
                    "end_time": window.end_time.isoformat(),
                    "duration": window.duration,
                    "missiles": window.missiles,
                    "trajectory_segments": serializable_trajectory,
                    "visibility_windows": serializable_visibility
                })

            return {
                "collection_time": meta_task_set.collection_time.isoformat(),
                "time_range": [
                    meta_task_set.time_range[0].isoformat(),
                    meta_task_set.time_range[1].isoformat()
                ],
                "meta_windows": serializable_windows,
                "total_missiles": meta_task_set.total_missiles,
                "alignment_resolution": meta_task_set.alignment_resolution,
                "metadata": meta_task_set.metadata
            }

        except Exception as e:
            logger.error(f"❌ 转换为可序列化格式失败: {e}")
            return {}


# 全局元任务管理器实例
_meta_task_manager = None

def get_meta_task_manager(config_manager=None, time_manager=None, missile_manager=None, visibility_calculator=None):
    """获取全局元任务管理器实例"""
    global _meta_task_manager
    if _meta_task_manager is None and all([config_manager, time_manager, missile_manager, visibility_calculator]):
        _meta_task_manager = MetaTaskManager(config_manager, time_manager, missile_manager, visibility_calculator)
    return _meta_task_manager
