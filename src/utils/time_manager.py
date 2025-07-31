"""
统一时间管理器
管理仿真时间、数据采集时间间隔、导弹随机添加时间等
严格禁止使用系统时间，必须使用配置的仿真时间
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Tuple, Optional
from .config_manager import get_config_manager

logger = logging.getLogger(__name__)

class UnifiedTimeManager:
    """统一时间管理器"""
    
    def __init__(self, config_manager=None):
        """
        初始化时间管理器
        
        Args:
            config_manager: 配置管理器实例
        """
        self.config_manager = config_manager or get_config_manager()
        self._load_time_config()
        
    def _load_time_config(self):
        """加载时间配置"""
        sim_config = self.config_manager.get_simulation_config()
        
        # 解析仿真时间
        start_time_str = sim_config.get("start_time", "2025/07/26 04:00:00")
        end_time_str = sim_config.get("end_time", "2025/07/26 08:00:00")
        epoch_time_str = sim_config.get("epoch_time", "2025/07/26 04:00:00")
        
        try:
            self.start_time = datetime.strptime(start_time_str, "%Y/%m/%d %H:%M:%S")
            self.end_time = datetime.strptime(end_time_str, "%Y/%m/%d %H:%M:%S")
            self.epoch_time = datetime.strptime(epoch_time_str, "%Y/%m/%d %H:%M:%S")
        except ValueError as e:
            logger.error(f"❌ 时间格式解析失败: {e}")
            # 使用默认时间
            self.start_time = datetime(2025, 7, 26, 4, 0, 0)
            self.end_time = datetime(2025, 7, 26, 8, 0, 0)
            self.epoch_time = datetime(2025, 7, 26, 4, 0, 0)
        
        # 数据采集配置
        data_config = self.config_manager.get_data_collection_config()
        self.collection_interval_range = data_config.get("interval_range", [60, 300])
        self.save_frequency = data_config.get("save_frequency", 10)
        self.total_collections = data_config.get("total_collections", 50)  # 总采集次数目标
        
        # 导弹配置
        missile_config = self.config_manager.get_missile_config()
        self.missile_launch_interval_range = missile_config.get("launch_interval_range", [300, 1800])
        self.max_concurrent_missiles = missile_config.get("max_concurrent_missiles", 5)
        
        # 任务规划配置
        task_config = self.config_manager.get_task_planning_config()
        self.atomic_task_duration = task_config.get("atomic_task_duration", 300)
        
        # 当前仿真时间（从开始时间开始）
        self.current_simulation_time = self.start_time
        
        # 数据采集计数器
        self.collection_count = 0
        
        logger.info(f"🕐 时间管理器初始化完成:")
        logger.info(f"   仿真时间范围: {self.start_time} - {self.end_time}")
        logger.info(f"   历元时间: {self.epoch_time}")
        logger.info(f"   数据采集间隔: {self.collection_interval_range}秒")
        logger.info(f"   保存频率: 每{self.save_frequency}次采集保存一次")
        logger.info(f"   总采集次数目标: {self.total_collections}次")
        logger.info(f"   导弹发射间隔: {self.missile_launch_interval_range}秒")
        
    def get_stk_time_range(self) -> Tuple[str, str, str]:
        """
        获取STK格式的时间范围
        
        Returns:
            (start_time_stk, end_time_stk, epoch_time_stk)
        """
        start_time_stk = self._convert_to_stk_format(self.start_time)
        end_time_stk = self._convert_to_stk_format(self.end_time)
        epoch_time_stk = self._convert_to_stk_format(self.epoch_time)
        
        return start_time_stk, end_time_stk, epoch_time_stk
    
    def _convert_to_stk_format(self, dt: datetime) -> str:
        """
        将datetime转换为STK格式
        
        Args:
            dt: datetime对象
            
        Returns:
            STK格式的时间字符串
        """
        # STK格式: "26 Jul 2025 04:00:00.000"
        month_names = [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
        ]
        
        month_name = month_names[dt.month - 1]
        return f"{dt.day} {month_name} {dt.year} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.000"
    
    def get_next_collection_time(self) -> datetime:
        """
        获取下一次数据采集时间
        
        Returns:
            下一次采集的仿真时间
        """
        # 随机生成时间间隔
        interval = random.randint(*self.collection_interval_range)
        next_time = self.current_simulation_time + timedelta(seconds=interval)
        
        # 确保不超过仿真结束时间
        if next_time > self.end_time:
            next_time = self.end_time
            
        logger.debug(f"🕐 下一次数据采集时间: {next_time} (间隔: {interval}秒)")
        return next_time
    
    def get_current_simulation_time(self) -> datetime:
        """
        获取当前仿真时间

        Returns:
            当前仿真时间
        """
        return self.current_simulation_time

    def advance_simulation_time(self, target_time: datetime):
        """
        推进仿真时间到指定时间

        Args:
            target_time: 目标时间
        """
        if target_time <= self.end_time:
            self.current_simulation_time = target_time
            logger.debug(f"🕐 仿真时间推进到: {self.current_simulation_time}")
        else:
            logger.warning(f"⚠️ 目标时间超出仿真范围: {target_time}")

    def is_simulation_finished(self) -> bool:
        """
        检查仿真是否结束

        Returns:
            是否结束
        """
        return self.current_simulation_time >= self.end_time

    def is_collection_finished(self) -> bool:
        """
        检查数据采集是否完成

        Returns:
            是否完成
        """
        return self.collection_count >= self.total_collections

    def get_collection_progress(self) -> dict:
        """
        获取数据采集进度信息

        Returns:
            包含进度信息的字典
        """
        progress_percentage = (self.collection_count / self.total_collections) * 100 if self.total_collections > 0 else 0
        return {
            "current_count": self.collection_count,
            "total_count": self.total_collections,
            "remaining_count": max(0, self.total_collections - self.collection_count),
            "progress_percentage": round(progress_percentage, 1)
        }
    
    def should_save_data(self) -> bool:
        """
        检查是否应该保存数据
        
        Returns:
            是否应该保存
        """
        self.collection_count += 1
        should_save = (self.collection_count % self.save_frequency) == 0
        
        if should_save:
            logger.info(f"💾 达到保存频率: 第{self.collection_count}次采集，准备保存数据")
            
        return should_save
    
    def get_data_filename(self) -> str:
        """
        生成数据文件名
        
        Returns:
            文件名字符串
        """
        # 使用当前仿真时间生成文件名
        time_str = self.current_simulation_time.strftime("%Y%m%d_%H%M%S")
        return f"satellite_data_{time_str}_collection_{self.collection_count:04d}.json"
    
    def calculate_missile_launch_time(self, launch_sequence: int) -> Tuple[datetime, str]:
        """
        计算导弹发射时间
        
        Args:
            launch_sequence: 发射序号
            
        Returns:
            (发射时间datetime, 发射时间STK格式)
        """
        # 基于发射序号和随机间隔计算发射时间
        base_interval = random.randint(*self.missile_launch_interval_range)
        launch_offset = (launch_sequence - 1) * base_interval + random.randint(0, 300)
        
        launch_time = self.start_time + timedelta(seconds=launch_offset)
        
        # 确保在仿真时间范围内
        if launch_time > self.end_time:
            # 使用配置的默认飞行时间作为缓冲
            missile_config = self.config_manager.get_missile_management_config()
            default_flight_minutes = missile_config["time_config"]["default_minutes"]
            launch_time = self.end_time - timedelta(minutes=default_flight_minutes)
            
        launch_time_stk = self._convert_to_stk_format(launch_time)
        
        logger.info(f"🚀 计算导弹发射时间: 序号{launch_sequence}, 时间{launch_time}")
        return launch_time, launch_time_stk
    
    def get_simulation_progress(self) -> float:
        """
        获取仿真进度百分比
        
        Returns:
            进度百分比 (0-100)
        """
        total_duration = (self.end_time - self.start_time).total_seconds()
        elapsed_duration = (self.current_simulation_time - self.start_time).total_seconds()
        
        progress = (elapsed_duration / total_duration) * 100
        return min(100.0, max(0.0, progress))

# 全局时间管理器实例
_time_manager = None

def get_time_manager(config_manager=None) -> UnifiedTimeManager:
    """获取全局时间管理器实例"""
    global _time_manager
    if _time_manager is None:
        _time_manager = UnifiedTimeManager(config_manager)
    return _time_manager
