"""
STK可见窗口计算器
通过STK COM接口计算卫星对目标的可见性时间窗口
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VisibilityWindow:
    """可见性时间窗口"""
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    elevation_angle: float  # 仰角
    azimuth_angle: float   # 方位角
    range_km: float        # 距离（公里）
    quality_score: float   # 可见性质量评分 (0-1)


@dataclass
class TargetPosition:
    """目标位置信息"""
    target_id: str
    latitude: float
    longitude: float
    altitude: float
    timestamp: datetime


class STKVisibilityCalculator:
    """
    STK可见窗口计算器
    
    通过STK COM接口实现卫星对目标的可见性时间窗口计算
    """
    
    def __init__(self, stk_manager=None):
        """
        🔧 修复：初始化STK可见窗口计算器，必须使用现有STK管理器

        Args:
            stk_manager: 现有的STK管理器实例
        """
        if stk_manager is None:
            logger.error("❌ STK可见性计算器必须传入有效的STK管理器")
            raise RuntimeError("STK可见性计算器必须使用现有的STK管理器")

        self.stk_manager = stk_manager
        self._stk_app = stk_manager.stk
        self._stk_root = stk_manager.root
        self._scenario = stk_manager.scenario

        # 验证STK连接
        if not self._stk_app or not self._stk_root or not self._scenario:
            logger.error("❌ STK管理器中缺少必要的组件")
            raise RuntimeError("STK管理器必须包含有效的STK应用、根对象和场景")

        logger.info(f"✅ STK可见窗口计算器初始化完成，使用场景: {self._scenario.InstanceName}")
    
    def _init_stk_connection(self):
        """🔧 修复：禁用独立STK连接，必须使用现有STK管理器"""
        logger.error("❌ STK可见性计算器不应该独立创建STK连接")
        logger.error("❌ 请使用 STKVisibilityCalculator(stk_manager) 传入现有的STK管理器")
        raise RuntimeError("STK可见性计算器不允许独立创建STK连接，必须使用现有的STK管理器")
    
    def _use_simulation_mode(self):
        """使用模拟模式"""
        self._stk_app = None
        self._stk_root = None
        self._scenario = None
        logger.info("🔄 STK可见窗口计算器运行在模拟模式")
    
    def _init_scenario(self):
        """🔧 修复：只能使用现有STK场景，禁止创建新场景"""
        try:
            if self._stk_root is None:
                logger.error("❌ STK根对象不存在")
                return

            # 🔧 新增：检查场景生命周期状态
            from src.stk_interface.stk_manager import STKManager
            if STKManager.is_scenario_lifecycle_locked():
                logger.info("🔒 STK可见性计算器 - 场景生命周期已锁定，只能连接现有场景")

            # 🔧 修复：只获取当前场景，禁止创建新场景
            try:
                self._scenario = self._stk_root.CurrentScenario
                if self._scenario:
                    logger.info(f"✅ STK可见性计算器连接到现有STK场景: {self._scenario.InstanceName}")
                else:
                    logger.error("❌ 没有当前STK场景")
                    logger.error("❌ STK可见性计算器不能创建新场景，必须使用现有场景")
                    raise RuntimeError("STK可见性计算器必须使用现有的STK场景")
            except Exception as e:
                logger.error(f"❌ 获取现有STK场景失败: {e}")
                logger.error("❌ STK可见性计算器不能创建新场景，必须使用现有场景")
                raise RuntimeError("STK可见性计算器必须使用现有的STK场景")

        except Exception as e:
            logger.error(f"❌ STK场景初始化失败: {e}")
            self._scenario = None
            raise
    
    def calculate_visibility_windows(
        self,
        satellite_ids: List[str],
        target_position: TargetPosition,
        start_time: datetime,
        end_time: datetime,
        min_elevation: float = 10.0
    ) -> List[VisibilityWindow]:
        """
        计算多颗卫星对目标的可见性时间窗口
        
        Args:
            satellite_ids: 卫星ID列表
            target_position: 目标位置信息
            start_time: 开始时间
            end_time: 结束时间
            min_elevation: 最小仰角（度）
            
        Returns:
            可见性时间窗口列表
        """
        try:
            logger.info(f"🔍 计算 {len(satellite_ids)} 颗卫星对目标 {target_position.target_id} 的可见窗口")
            logger.info(f"   时间范围: {start_time} - {end_time}")
            logger.info(f"   目标位置: ({target_position.latitude:.3f}, {target_position.longitude:.3f}, {target_position.altitude:.1f})")
            
            visibility_windows = []
            
            for satellite_id in satellite_ids:
                windows = self._calculate_single_satellite_visibility(
                    satellite_id, target_position, start_time, end_time, min_elevation
                )
                visibility_windows.extend(windows)
            
            # 按开始时间排序
            visibility_windows.sort(key=lambda w: w.start_time)
            
            logger.info(f"✅ 计算完成，找到 {len(visibility_windows)} 个可见窗口")
            
            return visibility_windows
            
        except Exception as e:
            logger.error(f"❌ 可见窗口计算失败: {e}")
            return []
    
    def _calculate_single_satellite_visibility(
        self,
        satellite_id: str,
        target_position: TargetPosition,
        start_time: datetime,
        end_time: datetime,
        min_elevation: float
    ) -> List[VisibilityWindow]:
        """
        计算单颗卫星对目标的可见性时间窗口
        
        Args:
            satellite_id: 卫星ID
            target_position: 目标位置信息
            start_time: 开始时间
            end_time: 结束时间
            min_elevation: 最小仰角（度）
            
        Returns:
            可见性时间窗口列表
        """
        try:
            if self._stk_root is None:
                # 模拟模式
                return self._simulate_visibility_windows(
                    satellite_id, target_position, start_time, end_time, min_elevation
                )
            
            # 真实STK计算
            return self._stk_calculate_visibility(
                satellite_id, target_position, start_time, end_time, min_elevation
            )
            
        except Exception as e:
            logger.error(f"❌ 卫星 {satellite_id} 可见窗口计算失败: {e}")
            return []
    
    def _stk_calculate_visibility(
        self,
        satellite_id: str,
        target_position: TargetPosition,
        start_time: datetime,
        end_time: datetime,
        min_elevation: float
    ) -> List[VisibilityWindow]:
        """
        使用STK COM接口计算可见性
        
        Args:
            satellite_id: 卫星ID
            target_position: 目标位置信息
            start_time: 开始时间
            end_time: 结束时间
            min_elevation: 最小仰角（度）
            
        Returns:
            可见性时间窗口列表
        """
        try:
            # TODO: 实现真实的STK COM接口调用
            # 这里需要：
            # 1. 获取或创建卫星对象
            # 2. 创建目标对象
            # 3. 设置可见性分析参数
            # 4. 执行可见性计算
            # 5. 解析结果
            
            logger.info(f"🛰️ 使用STK计算卫星 {satellite_id} 对目标的可见窗口")
            
            # 暂时返回模拟结果
            return self._simulate_visibility_windows(
                satellite_id, target_position, start_time, end_time, min_elevation
            )
            
        except Exception as e:
            logger.error(f"❌ STK可见性计算失败: {e}")
            return []
    
    def _simulate_visibility_windows(
        self,
        satellite_id: str,
        target_position: TargetPosition,
        start_time: datetime,
        end_time: datetime,
        min_elevation: float
    ) -> List[VisibilityWindow]:
        """
        模拟可见性时间窗口计算
        
        Args:
            satellite_id: 卫星ID
            target_position: 目标位置信息
            start_time: 开始时间
            end_time: 结束时间
            min_elevation: 最小仰角（度）
            
        Returns:
            模拟的可见性时间窗口列表
        """
        try:
            logger.info(f"🔄 模拟计算卫星 {satellite_id} 对目标 {target_position.target_id} 的可见窗口")
            
            visibility_windows = []
            
            # 模拟：假设每个轨道周期有1-2个可见窗口
            # 轨道周期约90-120分钟
            orbit_period = timedelta(minutes=100)
            current_time = start_time
            
            while current_time < end_time:
                # 模拟可见窗口：每个轨道周期中有一个5-15分钟的可见窗口
                window_start = current_time + timedelta(minutes=30)  # 轨道周期的1/3处开始可见
                window_duration = timedelta(minutes=8)  # 可见持续8分钟
                window_end = window_start + window_duration
                
                if window_end <= end_time:
                    # 模拟几何参数
                    elevation = min_elevation + 20.0  # 仰角
                    azimuth = 180.0  # 方位角
                    range_km = 800.0  # 距离
                    quality = 0.8  # 质量评分
                    
                    window = VisibilityWindow(
                        satellite_id=satellite_id,
                        target_id=target_position.target_id,
                        start_time=window_start,
                        end_time=window_end,
                        elevation_angle=elevation,
                        azimuth_angle=azimuth,
                        range_km=range_km,
                        quality_score=quality
                    )
                    
                    visibility_windows.append(window)
                    logger.debug(f"   模拟可见窗口: {window_start} - {window_end}")
                
                # 移动到下一个轨道周期
                current_time += orbit_period
            
            logger.info(f"✅ 模拟完成，卫星 {satellite_id} 有 {len(visibility_windows)} 个可见窗口")
            
            return visibility_windows
            
        except Exception as e:
            logger.error(f"❌ 模拟可见窗口计算失败: {e}")
            return []
    
    def find_satellites_with_visibility(
        self,
        all_satellite_ids: List[str],
        target_position: TargetPosition,
        start_time: datetime,
        end_time: datetime,
        min_elevation: float = 10.0
    ) -> List[str]:
        """
        查找对目标有可见窗口的卫星
        
        Args:
            all_satellite_ids: 所有卫星ID列表
            target_position: 目标位置信息
            start_time: 开始时间
            end_time: 结束时间
            min_elevation: 最小仰角（度）
            
        Returns:
            有可见窗口的卫星ID列表
        """
        try:
            logger.info(f"🔍 在 {len(all_satellite_ids)} 颗卫星中查找对目标 {target_position.target_id} 有可见窗口的卫星")
            
            satellites_with_visibility = []
            
            for satellite_id in all_satellite_ids:
                windows = self._calculate_single_satellite_visibility(
                    satellite_id, target_position, start_time, end_time, min_elevation
                )
                
                if windows:
                    satellites_with_visibility.append(satellite_id)
                    logger.debug(f"   卫星 {satellite_id}: {len(windows)} 个可见窗口")
            
            logger.info(f"✅ 找到 {len(satellites_with_visibility)} 颗有可见窗口的卫星")
            
            return satellites_with_visibility
            
        except Exception as e:
            logger.error(f"❌ 查找可见卫星失败: {e}")
            return []
    
    def close(self):
        """关闭STK连接"""
        try:
            if self._stk_app:
                # 可选：保存场景
                # self._stk_app.SaveAs("scenario_path")
                
                # 关闭STK应用程序
                # self._stk_app.Quit()
                pass
                
            logger.info("🔄 STK连接已关闭")
            
        except Exception as e:
            logger.error(f"❌ 关闭STK连接失败: {e}")
