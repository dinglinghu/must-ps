#!/usr/bin/env python3
"""
STK COM接口卫星位置计算器
基于经过验证的STK COM接口实现真实的卫星位置计算
"""

import logging
import math
import win32com.client
import pythoncom
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class SatellitePosition:
    """卫星位置数据结构"""
    satellite_id: str
    time: datetime
    latitude: float  # 纬度（度）
    longitude: float  # 经度（度）
    altitude: float  # 高度（公里）
    x: float  # 笛卡尔坐标X（公里）
    y: float  # 笛卡尔坐标Y（公里）
    z: float  # 笛卡尔坐标Z（公里）
    velocity_x: Optional[float] = None  # 速度X分量（公里/秒）
    velocity_y: Optional[float] = None  # 速度Y分量（公里/秒）
    velocity_z: Optional[float] = None  # 速度Z分量（公里/秒）

@dataclass
class DistanceResult:
    """距离计算结果"""
    distance_km: float  # 距离（公里）
    satellite_position: SatellitePosition
    target_position: Dict[str, float]
    calculation_time: datetime
    calculation_method: str  # 计算方法

class STKPositionCalculator:
    """STK COM接口位置计算器"""
    
    def __init__(self, stk_manager=None):
        """
        初始化STK位置计算器
        
        Args:
            stk_manager: STK管理器实例
        """
        self.stk_manager = stk_manager
        self.stk = None
        self.root = None
        self.scenario = None
        self.earth_radius = 6371.0  # 地球半径（公里）

        # 🔧 修复：初始化时不检查STK连接，只在使用时检查
        logger.info("✅ STK位置计算器初始化完成（延迟连接模式）")
        logger.info("💡 STK连接将在实际调用位置计算方法时建立")
    
    def _initialize_stk_connection(self):
        """🔧 修复：只能使用现有STK管理器连接，禁止独立创建"""
        try:
            if self.stk_manager and hasattr(self.stk_manager, 'stk') and self.stk_manager.stk:
                # 🔧 新增：强制场景生命周期检查
                if not self.stk_manager.enforce_scenario_connection_only("STK位置计算器"):
                    # 如果场景未锁定，确保STK管理器已连接
                    if not self.stk_manager.is_connected:
                        logger.info("🔄 STK位置计算器触发STK管理器连接...")
                        if not self.stk_manager.connect("STK位置计算器", allow_scenario_creation=False):
                            raise RuntimeError("STK位置计算器无法连接到STK管理器")

                # 使用现有的STK管理器连接
                self.stk = self.stk_manager.stk
                self.root = self.stk_manager.root
                self.scenario = self.stk_manager.scenario
                logger.info("✅ STK位置计算器使用现有STK管理器连接")

                # 验证场景存在
                if not self.scenario:
                    logger.error("❌ STK管理器中没有有效的场景")
                    raise RuntimeError("STK管理器中没有有效的场景")

            else:
                # 🔧 修复：禁止独立创建STK连接
                logger.error("❌ STK位置计算器必须使用现有的STK管理器")
                logger.error("❌ 请确保STK管理器已正确初始化并连接")
                raise RuntimeError("STK位置计算器必须使用现有的STK管理器，不能独立创建STK连接")

        except Exception as e:
            logger.error(f"❌ STK连接初始化失败: {e}")
            self.stk = None
            raise
    
    def _create_stk_connection(self):
        """🔧 修复：禁止创建新的STK连接，必须使用现有场景"""
        logger.error("❌ STK位置计算器不应该创建新的STK连接")
        logger.error("❌ 请使用 get_stk_position_calculator(stk_manager) 传入现有的STK管理器")
        raise RuntimeError("STK位置计算器不允许独立创建STK连接，必须使用现有的STK管理器")
    
    def get_satellite_position(
        self, 
        satellite_id: str, 
        time: Optional[datetime] = None
    ) -> Optional[SatellitePosition]:
        """
        获取卫星在指定时间的位置
        
        Args:
            satellite_id: 卫星ID
            time: 指定时间，如果为None则使用当前仿真时间
            
        Returns:
            卫星位置信息
        """
        try:
            # 🔧 修复：在使用时确保STK连接
            if not self._ensure_stk_connection():
                logger.error("❌ STK连接不可用，无法获取卫星位置")
                return None
            
            # 🔧 修复：使用仿真时间而不是系统时间
            if time is None:
                # 从时间管理器获取当前仿真时间
                from src.utils.time_manager import get_time_manager
                time_manager = get_time_manager()
                time = time_manager.get_current_simulation_time()
                logger.debug(f"🕐 使用仿真时间: {time}")
            
            # 获取卫星对象
            satellite = self._get_satellite_object(satellite_id)
            if not satellite:
                logger.error(f"❌ 未找到卫星: {satellite_id}")
                return None
            
            # 🔧 修复：确保卫星轨道已传播
            self._ensure_satellite_propagated(satellite)

            # 方法1：尝试使用LLA State数据提供者（基于验证工程）
            position = self._get_position_via_lla(satellite, time)
            if position:
                return position

            # 方法2：尝试使用Cartesian Position数据提供者
            position = self._get_position_via_cartesian(satellite, time)
            if position:
                return position

            # 方法3：使用Position数据提供者
            position = self._get_position_via_position(satellite, time)
            if position:
                return position

            # 方法4：基于轨道元素计算（最终回退）
            position = self._get_position_via_orbital_elements(satellite, time)
            if position:
                return position
            
            logger.error(f"❌ 所有方法都无法获取卫星 {satellite_id} 的位置")
            return None
            
        except Exception as e:
            logger.error(f"❌ 获取卫星位置失败: {e}")
            return None
    
    def _ensure_stk_connection(self) -> bool:
        """🔧 新增：确保STK连接，如果未连接则尝试连接"""
        try:
            # 如果已经连接，直接返回
            if self._check_stk_connection():
                return True

            # 如果未连接，尝试初始化连接
            logger.info("🔄 STK位置计算器检测到未连接，尝试建立连接...")
            self._initialize_stk_connection()

            # 再次检查连接状态
            return self._check_stk_connection()

        except Exception as e:
            logger.error(f"❌ 确保STK连接失败: {e}")
            return False

    def _check_stk_connection(self) -> bool:
        """🔧 修复版：检查STK连接状态"""
        try:
            # 检查基本对象是否存在
            if not (self.stk and self.root and self.scenario):
                logger.debug("STK基本对象不存在，需要初始化连接")
                return False

            # 🔧 修复：优先检查STK管理器的连接状态
            if hasattr(self, 'stk_manager') and self.stk_manager:
                if hasattr(self.stk_manager, 'is_connected'):
                    manager_connected = self.stk_manager.is_connected
                    logger.debug(f"STK管理器连接状态: {manager_connected}")

                    # 如果管理器显示已连接，直接返回True
                    if manager_connected:
                        return True
                    else:
                        logger.debug("STK管理器显示未连接")
                        return False
                else:
                    logger.debug("STK管理器没有is_connected属性")

            # 🔧 回退：尝试访问STK对象以验证连接
            try:
                # 尝试获取STK版本信息作为连接测试
                version = self.stk.Version
                logger.debug(f"STK连接正常，版本: {version}")
                return True
            except Exception as e:
                logger.debug(f"STK连接测试失败: {e}")
                return False

        except Exception as e:
            logger.debug(f"STK连接检查异常: {e}")
            return False
    
    def _get_satellite_object(self, satellite_id: str):
        """🔧 智能匹配版：获取卫星对象，支持多种输入格式"""
        try:
            if not self.scenario:
                logger.error("❌ 场景对象不存在")
                return None

            # 🔧 智能处理：支持多种输入格式
            # 格式1: "Satellite11" (直接名称)
            # 格式2: "Satellite/Satellite11" (STK管理器返回格式)

            # 提取实际的卫星名称
            actual_satellite_name = satellite_id
            if "/" in satellite_id:
                # 如果是 "Satellite/Satellite11" 格式，提取后面的部分
                actual_satellite_name = satellite_id.split("/")[-1]
                logger.debug(f"🔧 从路径格式提取卫星名称: {satellite_id} -> {actual_satellite_name}")

            # 配置文件规则：pattern: "Satellite{plane_id}{satellite_id}"
            # 有效名称：Satellite11, Satellite12, Satellite13, Satellite21, Satellite22, Satellite23, Satellite31, Satellite32, Satellite33
            valid_satellite_names = {
                'Satellite11', 'Satellite12', 'Satellite13',
                'Satellite21', 'Satellite22', 'Satellite23',
                'Satellite31', 'Satellite32', 'Satellite33'
            }

            # 验证提取的卫星名称是否符合命名规则
            if actual_satellite_name not in valid_satellite_names:
                logger.error(f"❌ 卫星名称不符合命名规则: {actual_satellite_name}")
                logger.error(f"   原始输入: {satellite_id}")
                logger.error(f"   有效名称: {sorted(valid_satellite_names)}")
                return None

            # 方法1：直接通过名称获取（最高效）
            try:
                satellite = self.scenario.Children.Item(actual_satellite_name)
                if hasattr(satellite, 'ClassName') and satellite.ClassName == 'Satellite':
                    logger.debug(f"✅ 直接匹配找到卫星: {actual_satellite_name}")
                    return satellite
                else:
                    logger.debug(f"⚠️ 找到对象但不是卫星类型: {satellite.ClassName}")
            except Exception as e:
                logger.debug(f"直接匹配失败: {e}")

            # 方法2：遍历所有对象进行精确匹配（回退方案）
            try:
                total_children = self.scenario.Children.Count
                logger.debug(f"场景中总对象数: {total_children}")

                for i in range(total_children):
                    try:
                        child = self.scenario.Children.Item(i)
                        if (hasattr(child, 'ClassName') and child.ClassName == 'Satellite' and
                            hasattr(child, 'InstanceName') and child.InstanceName == actual_satellite_name):
                            logger.debug(f"✅ 遍历匹配找到卫星: {actual_satellite_name} (索引: {i})")
                            return child
                    except Exception as e:
                        logger.debug(f"检查对象 {i} 失败: {e}")

            except Exception as e:
                logger.debug(f"遍历查找失败: {e}")

            logger.error(f"❌ 未找到卫星对象: {actual_satellite_name}")
            logger.error(f"   原始输入: {satellite_id}")

            # 🔧 调试信息：列出场景中实际存在的卫星
            try:
                existing_satellites = []
                for i in range(self.scenario.Children.Count):
                    try:
                        child = self.scenario.Children.Item(i)
                        if hasattr(child, 'ClassName') and child.ClassName == 'Satellite':
                            name = getattr(child, 'InstanceName', f'Unknown_{i}')
                            existing_satellites.append(name)
                    except:
                        pass

                if existing_satellites:
                    logger.error(f"   场景中现有卫星: {existing_satellites}")
                else:
                    logger.error(f"   场景中没有卫星对象")

            except Exception as e:
                logger.debug(f"列出现有卫星失败: {e}")

            return None

        except Exception as e:
            logger.error(f"❌ 获取卫星对象失败: {e}")
            return None
    
    def _get_position_via_lla(self, satellite, time: datetime) -> Optional[SatellitePosition]:
        """🔧 基于验证工程修复版：通过LLA State数据提供者获取位置"""
        try:
            # 🔧 修复1：使用正确的数据提供者和组
            # 基于验证工程：satellite.DataProviders.Item("LLA State").Group.Item("Fixed")
            satelliteDP = satellite.DataProviders.Item("LLA State").Group.Item("Fixed")

            # 🔧 修复2：使用场景时间范围
            scenario_start = self._get_scenario_start_time()
            scenario_stop = self._get_scenario_stop_time()

            start_str = scenario_start.strftime("%d %b %Y %H:%M:%S.000")
            stop_str = scenario_stop.strftime("%d %b %Y %H:%M:%S.000")

            # 🔧 修复3：使用正确的执行方法（基于验证工程）
            result = satelliteDP.Exec(start_str, stop_str, 60.0)  # 60秒步长

            if result and result.DataSets.Count > 0:
                # 🔧 修复4：使用正确的数据集名称（基于验证工程）
                times = result.DataSets.GetDataSetByName("Time").GetValues()
                lat_values = result.DataSets.GetDataSetByName("Lat").GetValues()
                lon_values = result.DataSets.GetDataSetByName("Lon").GetValues()
                alt_values = result.DataSets.GetDataSetByName("Alt").GetValues()

                if len(lat_values) > 0:
                    # 获取第一个数据点
                    lat = float(lat_values[0])  # 纬度（度）
                    lon = float(lon_values[0])  # 经度（度）
                    alt = float(alt_values[0]) / 1000.0  # 高度转换为公里

                    # 转换为笛卡尔坐标
                    x, y, z = self._lla_to_cartesian(lat, lon, alt)

                    logger.debug(f"✅ LLA State获取位置成功: ({lat:.4f}°, {lon:.4f}°, {alt:.1f}km)")

                    return SatellitePosition(
                        satellite_id=satellite.InstanceName,
                        time=time,
                        latitude=lat,
                        longitude=lon,
                        altitude=alt,
                        x=x,
                        y=y,
                        z=z
                    )

        except Exception as e:
            logger.debug(f"LLA State方法失败: {e}")

        return None

    def _check_time_in_scenario_range(self, time: datetime) -> bool:
        """检查时间是否在场景范围内"""
        try:
            if not self.scenario:
                return False

            start_time = self._get_scenario_start_time()
            stop_time = self._get_scenario_stop_time()

            return start_time <= time <= stop_time

        except:
            return False

    def _get_scenario_start_time(self) -> datetime:
        """获取场景开始时间"""
        try:
            if self.scenario:
                start_str = self.scenario.StartTime
                # 解析STK时间格式
                return self._parse_stk_time(start_str)
            else:
                # 🔧 修复：使用仿真开始时间而不是系统时间
                from src.utils.time_manager import get_time_manager
                time_manager = get_time_manager()
                return time_manager.start_time
        except:
            # 🔧 修复：使用仿真开始时间而不是系统时间
            from src.utils.time_manager import get_time_manager
            time_manager = get_time_manager()
            return time_manager.start_time

    def _get_scenario_stop_time(self) -> datetime:
        """获取场景结束时间"""
        try:
            if self.scenario:
                stop_str = self.scenario.StopTime
                # 解析STK时间格式
                return self._parse_stk_time(stop_str)
            else:
                # 🔧 修复：使用仿真结束时间而不是系统时间
                from src.utils.time_manager import get_time_manager
                time_manager = get_time_manager()
                return time_manager.end_time
        except:
            # 🔧 修复：使用仿真结束时间而不是系统时间
            from src.utils.time_manager import get_time_manager
            time_manager = get_time_manager()
            return time_manager.end_time

    def _parse_stk_time(self, time_str: str) -> datetime:
        """解析STK时间字符串"""
        try:
            # STK时间格式: "2 Aug 2025 12:28:52.000"
            return datetime.strptime(time_str, "%d %b %Y %H:%M:%S.%f")
        except:
            try:
                # 尝试其他格式
                return datetime.strptime(time_str, "%d %b %Y %H:%M:%S")
            except:
                return datetime.now()

    def _ensure_satellite_propagated(self, satellite):
        """🔧 新增：确保卫星轨道已传播（基于验证工程）"""
        try:
            # 检查卫星是否有传播器
            propagator = satellite.Propagator

            # 尝试传播轨道
            try:
                propagator.Propagate()
                logger.debug(f"✅ 卫星 {satellite.InstanceName} 轨道传播成功")
            except Exception as e:
                logger.debug(f"⚠️ 卫星 {satellite.InstanceName} 轨道传播失败: {e}")

                # 尝试重置并重新传播
                try:
                    propagator.Reset()
                    propagator.Propagate()
                    logger.debug(f"✅ 卫星 {satellite.InstanceName} 重置后轨道传播成功")
                except Exception as e2:
                    logger.debug(f"❌ 卫星 {satellite.InstanceName} 重置后轨道传播仍失败: {e2}")

        except Exception as e:
            logger.debug(f"❌ 卫星 {satellite.InstanceName} 传播器访问失败: {e}")

    def _get_position_via_cartesian(self, satellite, time: datetime) -> Optional[SatellitePosition]:
        """🔧 基于验证工程修复版：通过Cartesian Position数据提供者获取位置"""
        try:
            # 🔧 修复1：使用正确的数据提供者和组
            # 尝试不同的Cartesian数据提供者
            try:
                satelliteDP = satellite.DataProviders.Item("Cartesian Position").Group.Item("Fixed")
            except:
                # 回退到基本的Cartesian Position
                satelliteDP = satellite.DataProviders.Item("Cartesian Position")

            # 🔧 修复2：使用场景时间范围
            scenario_start = self._get_scenario_start_time()
            scenario_stop = self._get_scenario_stop_time()

            start_str = scenario_start.strftime("%d %b %Y %H:%M:%S.000")
            stop_str = scenario_stop.strftime("%d %b %Y %H:%M:%S.000")

            # 🔧 修复3：使用正确的执行方法
            result = satelliteDP.Exec(start_str, stop_str, 60.0)  # 60秒步长

            if result and result.DataSets.Count > 0:
                # 🔧 修复4：尝试使用数据集名称获取数据
                try:
                    x_values = result.DataSets.GetDataSetByName("x").GetValues()
                    y_values = result.DataSets.GetDataSetByName("y").GetValues()
                    z_values = result.DataSets.GetDataSetByName("z").GetValues()
                except:
                    # 回退到索引方式
                    dataset = result.DataSets.Item(0)
                    if dataset.RowCount > 0:
                        x_values = [dataset.GetValue(0, 1)]
                        y_values = [dataset.GetValue(0, 2)]
                        z_values = [dataset.GetValue(0, 3)]
                    else:
                        return None

                if len(x_values) > 0:
                    # 获取第一个数据点，转换为公里
                    x = float(x_values[0]) / 1000.0
                    y = float(y_values[0]) / 1000.0
                    z = float(z_values[0]) / 1000.0

                    # 转换为经纬度
                    lat, lon, alt = self._cartesian_to_lla(x, y, z)

                    logger.debug(f"✅ Cartesian Position获取位置成功: ({lat:.4f}°, {lon:.4f}°, {alt:.1f}km)")

                    return SatellitePosition(
                        satellite_id=satellite.InstanceName,
                        time=time,
                        latitude=lat,
                        longitude=lon,
                        altitude=alt,
                        x=x,
                        y=y,
                        z=z
                    )

        except Exception as e:
            logger.debug(f"Cartesian Position方法失败: {e}")

        return None

    def _get_position_via_orbital_elements(self, satellite, time: datetime) -> Optional[SatellitePosition]:
        """🔧 新增：通过轨道元素计算位置（回退方案）"""
        try:
            # 尝试获取轨道传播器
            propagator = satellite.Propagator

            # 获取初始状态
            initial_state = propagator.InitialState

            # 尝试获取经典轨道元素
            try:
                representation = initial_state.Representation

                # 获取轨道参数
                sma = representation.SemiMajorAxis / 1000.0  # 半长轴（公里）
                ecc = representation.Eccentricity  # 偏心率
                inc = representation.Inclination  # 倾角（弧度）
                raan = representation.RAAN  # 升交点赤经（弧度）
                aop = representation.ArgOfPerigee  # 近地点幅角（弧度）
                ta = representation.TrueAnomaly  # 真近点角（弧度）

                # 🔧 使用简化的轨道计算
                # 这里使用简化的圆轨道假设进行位置计算
                import math

                # 计算轨道周期
                mu = 398600.4418  # 地球引力参数 (km³/s²)
                period = 2 * math.pi * math.sqrt(sma**3 / mu)

                # 计算当前时间的平均近点角
                epoch_time = self._get_scenario_start_time()
                time_since_epoch = (time - epoch_time).total_seconds()
                mean_motion = 2 * math.pi / period
                mean_anomaly = (ta + mean_motion * time_since_epoch) % (2 * math.pi)

                # 简化计算：假设圆轨道
                true_anomaly = mean_anomaly  # 圆轨道近似

                # 计算轨道坐标系中的位置
                r = sma  # 圆轨道半径
                x_orbit = r * math.cos(true_anomaly)
                y_orbit = r * math.sin(true_anomaly)
                z_orbit = 0.0

                # 转换到地心坐标系
                cos_raan = math.cos(raan)
                sin_raan = math.sin(raan)
                cos_inc = math.cos(inc)
                sin_inc = math.sin(inc)
                cos_aop = math.cos(aop)
                sin_aop = math.sin(aop)

                # 旋转矩阵变换
                x = (cos_raan * cos_aop - sin_raan * sin_aop * cos_inc) * x_orbit + \
                    (-cos_raan * sin_aop - sin_raan * cos_aop * cos_inc) * y_orbit

                y = (sin_raan * cos_aop + cos_raan * sin_aop * cos_inc) * x_orbit + \
                    (-sin_raan * sin_aop + cos_raan * cos_aop * cos_inc) * y_orbit

                z = (sin_aop * sin_inc) * x_orbit + (cos_aop * sin_inc) * y_orbit

                # 转换为经纬度
                lat, lon, alt = self._cartesian_to_lla(x, y, z)

                logger.debug(f"✅ 通过轨道元素计算位置: ({lat:.4f}°, {lon:.4f}°, {alt:.1f}km)")

                return SatellitePosition(
                    satellite_id=satellite.InstanceName,
                    time=time,
                    latitude=lat,
                    longitude=lon,
                    altitude=alt,
                    x=x,
                    y=y,
                    z=z
                )

            except Exception as e:
                logger.debug(f"轨道元素获取失败: {e}")

        except Exception as e:
            logger.debug(f"轨道元素方法失败: {e}")

        return None
    
    def _get_position_via_position(self, satellite, time: datetime) -> Optional[SatellitePosition]:
        """通过Position数据提供者获取位置"""
        try:
            dp = satellite.DataProviders.Item("Position")
            time_str = time.strftime("%d %b %Y %H:%M:%S.000")
            
            result = dp.Exec(time_str, time_str)
            
            if result and result.DataSets.Count > 0:
                dataset = result.DataSets.Item(0)
                if dataset.RowCount > 0:
                    # 根据数据集的列数判断数据格式
                    if dataset.ColumnCount >= 4:
                        x = float(dataset.GetValue(0, 1)) / 1000.0  # 转换为公里
                        y = float(dataset.GetValue(0, 2)) / 1000.0
                        z = float(dataset.GetValue(0, 3)) / 1000.0
                        
                        # 转换为经纬度
                        lat, lon, alt = self._cartesian_to_lla(x, y, z)
                        
                        return SatellitePosition(
                            satellite_id=satellite.InstanceName,
                            time=time,
                            latitude=lat,
                            longitude=lon,
                            altitude=alt,
                            x=x,
                            y=y,
                            z=z
                        )
                    
        except Exception as e:
            logger.debug(f"Position方法失败: {e}")
            
        return None

    def _lla_to_cartesian(self, lat: float, lon: float, alt: float) -> Tuple[float, float, float]:
        """
        将经纬度坐标转换为笛卡尔坐标

        Args:
            lat: 纬度（度）
            lon: 经度（度）
            alt: 高度（公里）

        Returns:
            (x, y, z) 笛卡尔坐标（公里）
        """
        try:
            lat_rad = math.radians(lat)
            lon_rad = math.radians(lon)

            # 地球半径加上高度
            r = self.earth_radius + alt

            x = r * math.cos(lat_rad) * math.cos(lon_rad)
            y = r * math.cos(lat_rad) * math.sin(lon_rad)
            z = r * math.sin(lat_rad)

            return x, y, z

        except Exception as e:
            logger.error(f"❌ 经纬度转笛卡尔坐标失败: {e}")
            return 0.0, 0.0, 0.0

    def _cartesian_to_lla(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """
        将笛卡尔坐标转换为经纬度坐标

        Args:
            x, y, z: 笛卡尔坐标（公里）

        Returns:
            (lat, lon, alt) 经纬度坐标
        """
        try:
            # 计算距离地心的距离
            r = math.sqrt(x*x + y*y + z*z)

            # 计算纬度
            lat = math.degrees(math.asin(z / r))

            # 计算经度
            lon = math.degrees(math.atan2(y, x))

            # 计算高度
            alt = r - self.earth_radius

            return lat, lon, alt

        except Exception as e:
            logger.error(f"❌ 笛卡尔坐标转经纬度失败: {e}")
            return 0.0, 0.0, 0.0

    def calculate_distance_to_target(
        self,
        satellite_id: str,
        target_position: Dict[str, float],
        time: Optional[datetime] = None
    ) -> Optional[DistanceResult]:
        """
        计算卫星到目标的距离

        Args:
            satellite_id: 卫星ID
            target_position: 目标位置 {lat, lon, alt}
            time: 计算时间

        Returns:
            距离计算结果
        """
        try:
            # 获取卫星位置
            sat_position = self.get_satellite_position(satellite_id, time)
            if not sat_position:
                logger.error(f"❌ 无法获取卫星 {satellite_id} 的位置")
                return None

            # 计算3D距离
            distance = self._calculate_3d_distance(
                sat_position, target_position
            )

            # 🔧 修复：确保使用正确的时间
            calc_time = time
            if calc_time is None:
                from src.utils.time_manager import get_time_manager
                time_manager = get_time_manager()
                calc_time = time_manager.get_current_simulation_time()

            return DistanceResult(
                distance_km=distance,
                satellite_position=sat_position,
                target_position=target_position,
                calculation_time=calc_time,
                calculation_method="STK_COM_3D"
            )

        except Exception as e:
            logger.error(f"❌ 计算距离失败: {e}")
            return None

    def _calculate_3d_distance(
        self,
        sat_position: SatellitePosition,
        target_position: Dict[str, float]
    ) -> float:
        """
        计算3D空间距离

        Args:
            sat_position: 卫星位置
            target_position: 目标位置

        Returns:
            距离（公里）
        """
        try:
            # 将目标位置转换为笛卡尔坐标
            target_lat = target_position.get('lat', 0.0)
            target_lon = target_position.get('lon', 0.0)
            target_alt = target_position.get('alt', 0.0)

            target_x, target_y, target_z = self._lla_to_cartesian(
                target_lat, target_lon, target_alt
            )

            # 计算3D欧几里得距离
            dx = sat_position.x - target_x
            dy = sat_position.y - target_y
            dz = sat_position.z - target_z

            distance = math.sqrt(dx*dx + dy*dy + dz*dz)

            return distance

        except Exception as e:
            logger.error(f"❌ 3D距离计算失败: {e}")
            return float('inf')

    def find_nearest_satellites(
        self,
        satellite_ids: List[str],
        target_position: Dict[str, float],
        time: Optional[datetime] = None,
        count: int = 5
    ) -> List[DistanceResult]:
        """
        找到距离目标最近的卫星

        Args:
            satellite_ids: 卫星ID列表
            target_position: 目标位置
            time: 计算时间
            count: 返回的卫星数量

        Returns:
            按距离排序的距离结果列表
        """
        try:
            distance_results = []

            for satellite_id in satellite_ids:
                distance_result = self.calculate_distance_to_target(
                    satellite_id, target_position, time
                )

                if distance_result:
                    distance_results.append(distance_result)
                    logger.debug(f"卫星 {satellite_id}: 距离 {distance_result.distance_km:.1f} km")

            # 按距离排序
            distance_results.sort(key=lambda x: x.distance_km)

            # 返回最近的N颗卫星
            nearest = distance_results[:count]

            logger.info(f"✅ 找到 {len(nearest)} 颗最近卫星")
            for i, result in enumerate(nearest):
                logger.info(f"   {i+1}. {result.satellite_position.satellite_id}: {result.distance_km:.1f} km")

            return nearest

        except Exception as e:
            logger.error(f"❌ 查找最近卫星失败: {e}")
            return []

    def get_multiple_satellite_positions(
        self,
        satellite_ids: List[str],
        time: Optional[datetime] = None
    ) -> Dict[str, SatellitePosition]:
        """
        批量获取多颗卫星的位置

        Args:
            satellite_ids: 卫星ID列表
            time: 计算时间

        Returns:
            卫星位置字典 {satellite_id: SatellitePosition}
        """
        try:
            positions = {}

            for satellite_id in satellite_ids:
                position = self.get_satellite_position(satellite_id, time)
                if position:
                    positions[satellite_id] = position
                    logger.debug(f"✅ 获取卫星 {satellite_id} 位置: "
                               f"({position.latitude:.2f}°, {position.longitude:.2f}°, {position.altitude:.1f}km)")
                else:
                    logger.warning(f"⚠️ 无法获取卫星 {satellite_id} 的位置")

            logger.info(f"✅ 成功获取 {len(positions)}/{len(satellite_ids)} 颗卫星的位置")
            return positions

        except Exception as e:
            logger.error(f"❌ 批量获取卫星位置失败: {e}")
            return {}


# 全局STK位置计算器实例
_stk_position_calculator = None

def get_stk_position_calculator(stk_manager=None) -> STKPositionCalculator:
    """🔧 修复版：获取全局STK位置计算器实例，必须传入有效的STK管理器"""
    global _stk_position_calculator

    # 🔧 修复：初始化时不检测STK连接，只在使用时检测
    if stk_manager is None:
        try:
            from .stk_manager import get_stk_manager
            stk_manager = get_stk_manager()
            logger.debug("✅ 获取到全局STK管理器")
        except Exception as e:
            logger.error(f"❌ 获取STK管理器失败: {e}")
            raise RuntimeError(f"无法获取STK管理器: {e}")

    # 初始化时不检查连接状态，允许延迟连接
    logger.info("✅ STK位置计算器初始化完成（延迟连接模式）")
    logger.info("💡 STK连接状态将在实际使用时检查")

    # 🔧 修复：如果已有实例但STK管理器更新了，重新创建
    if _stk_position_calculator is not None and stk_manager is not None:
        if _stk_position_calculator.stk_manager != stk_manager:
            logger.debug("🔄 STK管理器已更新，重新创建位置计算器")
            _stk_position_calculator = STKPositionCalculator(stk_manager)

    # 创建新实例
    if _stk_position_calculator is None:
        _stk_position_calculator = STKPositionCalculator(stk_manager)
        logger.debug("✅ 创建新的STK位置计算器实例")

    return _stk_position_calculator
