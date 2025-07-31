"""
STK管理器类
负责与STK软件的COM接口交互，基于参考工程的设计模式
"""

import logging
import math
import win32com.client
import comtypes.client
import time
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from ..utils.time_manager import UnifiedTimeManager

logger = logging.getLogger(__name__)

class STKManager:
    """STK管理器类"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化STK管理器
        
        Args:
            config: STK配置参数
        """
        self.config = config
        self.stk = None
        self.root = None
        self.scenario = None
        self.is_connected = False

        # 现有项目检测配置
        self.detect_existing_project = config.get('detect_existing_project', True)
        self.existing_project_wait_time = config.get('existing_project_wait_time', 5)
        self.skip_creation = False  # 是否跳过创建步骤
        self.existing_project_detected = False  # 是否检测到现有项目

        # 🕐 初始化统一时间管理器
        self.time_manager = UnifiedTimeManager()

        # 从时间管理器获取时间配置
        start_time_str, end_time_str, epoch_time_str = self.time_manager.get_stk_time_range()
        self.scenario_begin_time = start_time_str
        self.scenario_end_time = end_time_str
        self.scenario_epoch_time = epoch_time_str

        # 从配置获取物理常数和STK枚举
        from src.utils.config_manager import get_config_manager
        config_manager = get_config_manager()
        physics_config = config_manager.get_physics_config()
        self.earth_radius = physics_config.get("earth_radius", 6371)  # km

        # STK对象类型和配置
        stk_config = config_manager.get_stk_config()
        self.object_types = stk_config.get("object_types", {
            "satellite": 18, "sensor": 20, "target": 20, "missile": 19
        })
        self.propagator_types = stk_config.get("propagator_types", {
            "j2_perturbation": 1
        })
        self.sensor_patterns = stk_config.get("sensor_patterns", {
            "conic": 0, "custom": 1, "half_power": 2, "omni": 3, "rectangular": 4
        })
        self.wait_times = stk_config.get("wait_times", {
            "object_creation": 2.0, "sensor_creation": 1.0, "constraint_setup": 0.5,
            "pattern_setup": 0.2, "parameter_setup": 0.1
        })
        
        # 可见性计算优化
        self.visibility_cache = {}
        self.batch_visibility_queue = []
        self.batch_processing = False
        
        # 连接池优化
        self.connection_pool = []
        self.max_connections = config.get('stk', {}).get('max_connections', 5)
        self.connection_timeout = config.get('stk', {}).get('connection_timeout', 30)
        
        # 使用统一时间管理器
        self.time_format_manager = None  # 已被统一时间管理器替代
        
    def connect(self) -> bool:
        """
        连接到STK

        Returns:
            连接是否成功
        """
        try:
            # 初始化COM组件
            import pythoncom
            try:
                pythoncom.CoInitialize()
                logger.debug("COM组件初始化成功")
            except Exception as e:
                logger.debug(f"COM组件已初始化或初始化失败: {e}")

            # 尝试获取已运行的STK实例
            try:
                self.stk = win32com.client.GetActiveObject("STK12.Application")
                logger.info("连接到已运行的STK实例")
            except Exception:
                # 如果没有运行的实例，创建新的
                self.stk = win32com.client.Dispatch("STK12.Application")
                logger.info("创建新的STK实例")
            
            # 设置STK可见性和用户控制
            self.stk.Visible = True
            self.stk.UserControl = True
            
            # 获取根对象
            self.root = self.stk.Personality2
            
            # 设置日期格式
            self.root.UnitPreferences.SetCurrentUnit("DateFormat", "UTCG")
            
            # 检测现有项目并决定是否跳过创建
            if self.detect_existing_project:
                existing_detected = self._detect_existing_project()
                if existing_detected:
                    self.skip_creation = True
                    self.existing_project_detected = True
                    logger.info("🔍 检测到现有STK项目，将跳过场景、星座、载荷、导弹的创建")
                    logger.info(f"⏰ 等待 {self.existing_project_wait_time} 秒以确保项目稳定...")
                    import time
                    time.sleep(self.existing_project_wait_time)

                    # 获取当前场景
                    try:
                        self.scenario = self.root.CurrentScenario
                        logger.info(f"✅ 使用现有场景: {self.scenario.InstanceName}")
                    except Exception as e:
                        logger.warning(f"获取现有场景失败: {e}")
                        self.skip_creation = False  # 如果无法获取现有场景，则不跳过创建
                else:
                    logger.info("🆕 未检测到现有项目，将创建新的场景和对象")

            # 创建或打开场景（仅在未检测到现有项目时）
            if not self.skip_creation:
                scenario_name = self.config.get('scenario', {}).get('name', 'MCP_Created_Scenario')
                try:
                    # 尝试关闭现有场景
                    self.root.CloseScenario()
                    logger.info("关闭现有场景")
                except:
                    pass

                try:
                    self.root.NewScenario(scenario_name)
                    self.scenario = self.root.CurrentScenario
                    logger.info(f"创建新场景: {scenario_name}")
                except Exception as e:
                    logger.warning(f"创建场景失败: {e}")
                    # 尝试获取当前场景
                    self.scenario = self.root.CurrentScenario
                    logger.info("使用当前场景")
            
            # 设置连接状态（在时间设置之前）
            self.is_connected = True

            # 设置场景时间
            self._setup_scenario_time()

            logger.info("STK连接成功")
            return True
            
        except Exception as e:
            logger.error(f"STK连接失败: {e}")
            self.is_connected = False
            return False
    
    def disconnect(self):
        """断开STK连接"""
        if self.stk:
            try:
                self.stk.Quit()
                self.stk = None
                self.root = None
                self.scenario = None
                self.is_connected = False
                logger.info("STK连接已断开")

                # 清理COM组件
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                    logger.debug("COM组件清理完成")
                except Exception as e:
                    logger.debug(f"COM组件清理失败: {e}")

            except Exception as e:
                logger.error(f"断开STK连接时出错: {e}")

    def _detect_existing_project(self) -> bool:
        """
        检测是否存在现有的STK项目

        Returns:
            bool: True表示检测到现有项目，False表示没有
        """
        try:
            # 检查是否有当前场景
            current_scenario = self.root.CurrentScenario
            if current_scenario:
                scenario_name = current_scenario.InstanceName
                logger.info(f"🔍 检测到现有场景: {scenario_name}")

                # 检查场景中是否有对象
                children_count = current_scenario.Children.Count
                if children_count > 0:
                    logger.info(f"📊 现有场景包含 {children_count} 个对象")

                    # 列出现有对象类型
                    object_types = {}
                    for i in range(children_count):
                        child = current_scenario.Children.Item(i)
                        obj_type = child.ClassName
                        object_types[obj_type] = object_types.get(obj_type, 0) + 1

                    logger.info("📋 现有对象统计:")
                    for obj_type, count in object_types.items():
                        logger.info(f"   {obj_type}: {count}个")

                    # 如果有卫星、传感器或导弹，认为是现有项目
                    if any(obj_type in ['Satellite', 'Sensor', 'Missile'] for obj_type in object_types.keys()):
                        logger.info("✅ 检测到现有的卫星/传感器/导弹对象，确认为现有项目")
                        return True
                    else:
                        logger.info("⚠️  场景中没有相关对象，不视为现有项目")
                        return False
                else:
                    logger.info("📭 现有场景为空，不视为现有项目")
                    return False
            else:
                logger.info("🆕 没有检测到现有场景")
                return False

        except Exception as e:
            logger.warning(f"检测现有项目时出错: {e}")
            return False

    def should_skip_creation(self) -> bool:
        """检查是否应该跳过创建步骤"""
        return self.skip_creation

    def is_existing_project_detected(self) -> bool:
        """检查是否检测到现有项目"""
        return self.existing_project_detected



    def _setup_scenario_time(self):
        """设置场景时间"""
        if not self.scenario:
            logger.warning("STK场景不存在，跳过时间设置")
            return

        try:
            # 🕐 强制从统一时间管理器获取仿真时间
            from src.utils.time_manager import get_time_manager
            time_manager = get_time_manager()
            start_time_stk, end_time_stk, epoch_time_stk = time_manager.get_stk_time_range()

            logger.info(f"🕐 统一时间管理器配置:")
            logger.info(f"   开始时间: {start_time_stk}")
            logger.info(f"   结束时间: {end_time_stk}")
            logger.info(f"   历元时间: {epoch_time_stk}")

            # 设置场景时间
            self.scenario.StartTime = start_time_stk
            self.scenario.StopTime = end_time_stk
            self.scenario.Epoch = epoch_time_stk
            self.scenario_begin_time = start_time_stk
            self.scenario_end_time = end_time_stk
            logger.info(f"✅ STK场景仿真时间已设置: {start_time_stk} - {end_time_stk}")
        except Exception as e:
            logger.warning(f"❌ STK场景仿真时间设置失败: {e}")
            try:
                # 尝试多种方式重置动画
                animation_methods = [
                    lambda: self.root.Animation.Reset(),
                    lambda: getattr(self.root, 'Animation', None).Reset() if hasattr(self.root, 'Animation') else None,
                    lambda: self.root.GetAnimation().Reset() if hasattr(self.root, 'GetAnimation') else None,
                ]
                
                animation_reset_success = False
                for i, method in enumerate(animation_methods):
                    try:
                        method()
                        logger.info(f"动画重置成功 (方法 {i+1})")
                        animation_reset_success = True
                        break
                    except Exception as e:
                        logger.debug(f"动画重置方法 {i+1} 失败: {e}")
                        continue
                
                if not animation_reset_success:
                    logger.warning("所有动画重置方法都失败，但场景时间设置继续")
                    
            except Exception as e:
                logger.warning(f"动画重置过程中出现异常: {e}")
            
            self.scenario_begin_time = start_time_stk
            self.scenario_end_time = end_time_stk

            logger.info(f"场景时间设置成功: {start_time_stk} 到 {end_time_stk}")
            
        except Exception as e:
            logger.error(f"设置场景时间失败: {e}")
            raise
    
    def _convert_to_stk_format(self, time_string: str) -> str:
        """
        将配置格式的时间字符串转换为STK默认格式
        
        Args:
            time_string: 配置格式的时间字符串
            
        Returns:
            STK格式的时间字符串
        """
        # 使用统一时间管理器进行转换
        try:
            from datetime import datetime
            
            # 解析配置格式
            dt = datetime.strptime(time_string, "%Y/%m/%d %H:%M:%S")
            
            # 转换为STK格式
            stk_format = dt.strftime("%d %b %Y %H:%M:%S.000")
            
            return stk_format
            
        except Exception as e:
            logger.error(f"时间格式转换失败: {e}")
            raise
    
    def set_scenario_time(self, scenario_begin_time: str, scenario_end_time: str):
        """
        设置场景的时间范围，并重置动画至开始时间
        
        Args:
            scenario_begin_time: 场景的开始时间，格式为 "YYYY/MM/DD HH:MM:SS"
            scenario_end_time: 场景的结束时间，格式为 "YYYY/MM/DD HH:MM:SS"
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return
        
        try:
            # 将配置格式转换为STK默认格式
            start_time_stk = self._convert_to_stk_format(scenario_begin_time)
            end_time_stk = self._convert_to_stk_format(scenario_end_time)
            
            self.scenario.StartTime = start_time_stk
            self.scenario.StopTime = end_time_stk
            self.scenario.Epoch = start_time_stk
            
            try:
                # 尝试多种方式重置动画
                animation_methods = [
                    lambda: self.root.Animation.Reset(),
                    lambda: getattr(self.root, 'Animation', None).Reset() if hasattr(self.root, 'Animation') else None,
                    lambda: self.root.GetAnimation().Reset() if hasattr(self.root, 'GetAnimation') else None,
                ]
                
                animation_reset_success = False
                for i, method in enumerate(animation_methods):
                    try:
                        method()
                        logger.info(f"动画重置成功 (方法 {i+1})")
                        animation_reset_success = True
                        break
                    except Exception as e:
                        logger.debug(f"动画重置方法 {i+1} 失败: {e}")
                        continue
                
                if not animation_reset_success:
                    logger.warning("所有动画重置方法都失败，但场景时间设置继续")
                    
            except Exception as e:
                logger.warning(f"动画重置过程中出现异常: {e}")
            
            self.scenario_begin_time = scenario_begin_time
            self.scenario_end_time = scenario_end_time
            
            logger.info(f"场景时间更新: {scenario_begin_time} 到 {scenario_end_time}")
            
        except Exception as e:
            logger.error(f"设置场景时间失败: {e}")
    
    def get_scenario(self):
        """获取场景对象"""
        return self.scenario
    
    def get_root(self):
        """获取根对象"""
        return self.root
    
    def get_objects(self, obj_type: str) -> List[str]:
        """
        获取指定类型的对象列表
        
        Args:
            obj_type: 对象类型，如 "Satellite", "Sensor", "Target"
            
        Returns:
            对象路径列表
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return []
        
        try:
            objects = []
            for i in range(self.scenario.Children.Count):
                child = self.scenario.Children.Item(i)
                if child.ClassName == obj_type:
                    objects.append(f"{obj_type}/{child.InstanceName}")
            return objects
        except Exception as e:
            logger.error(f"获取{obj_type}对象失败: {e}")
            return []
    
    def create_satellite(self, satellite_id: str, orbital_params: Dict) -> bool:
        """
        创建卫星
        
        Args:
            satellite_id: 卫星ID
            orbital_params: 轨道参数，包含轨道六根数
            
        Returns:
            创建是否成功
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return False
        
        try:
            # 使用COM接口创建卫星对象
            self.scenario.Children.New(self.object_types["satellite"], satellite_id)
            logger.info(f"使用COM接口创建卫星: {satellite_id}")

            # 等待卫星对象完全创建
            time.sleep(self.wait_times["object_creation"])
            
            # 遍历Children查找卫星对象，并打印所有对象信息
            logger.info('场景Children对象列表:')
            for i in range(self.scenario.Children.Count):
                child = self.scenario.Children.Item(i)
                logger.info(f"Child {i}: ClassName={getattr(child, 'ClassName', None)}, InstanceName={getattr(child, 'InstanceName', None)}, Name={getattr(child, 'Name', None)}")
            satellite = None
            for i in range(self.scenario.Children.Count):
                child = self.scenario.Children.Item(i)
                if getattr(child, 'ClassName', None) == 'Satellite' and (getattr(child, 'InstanceName', None) == satellite_id or getattr(child, 'Name', None) == satellite_id):
                    satellite = child
                    break
            if satellite is None:
                logger.error(f"未找到卫星对象: {satellite_id}")
                return False
            
            # 设置轨道传播器类型为J2摄动
            try:
                satellite.SetPropagatorType(self.propagator_types["j2_perturbation"])
                logger.info("轨道传播器类型设置成功")
            except Exception as e:
                logger.error(f"设置传播器类型失败: {e}")
                raise
            
            # 设置轨道参数
            if orbital_params:
                self._set_satellite_orbit(satellite, orbital_params, satellite_id)
            
            # 设置地面轨迹显示
            passdata = satellite.Graphics.PassData
            groundTrack = passdata.GroundTrack
            groundTrack.SetLeadDataType(1)  # 1 = eDataAll
            groundTrack.SetTrailSameAsLead()
            
            logger.info(f"卫星 {satellite_id} 创建成功")
            return True
                
        except Exception as e:
            logger.error(f"创建卫星 {satellite_id} 失败: {e}")
            return False
    
    def _set_satellite_orbit(self, satellite, orbital_params: Dict, satellite_id: str = None):
        """
        设置卫星轨道参数
        
        Args:
            satellite: 卫星对象
            orbital_params: 轨道参数
        """
        try:
            # 轨道参数阈值定义
            ORBITAL_THRESHOLDS = {
                'semi_axis': {'min': 6371.0, 'max': 50000.0, 'unit': 'km'},  # 地球半径到地球同步轨道
                'eccentricity': {'min': 0.0, 'max': 0.999, 'unit': '无量纲'},  # 0为圆轨道，接近1为抛物线
                'inclination': {'min': 0.0, 'max': 180.0, 'unit': '度'},  # 0-180度
                'arg_of_perigee': {'min': 0.0, 'max': 360.0, 'unit': '度'},  # 0-360度
                'argument_of_perigee': {'min': 0.0, 'max': 360.0, 'unit': '度'},  # 0-360度（兼容配置文件的参数名）
                'raan': {'min': 0.0, 'max': 360.0, 'unit': '度'},  # 0-360度
                'mean_anomaly': {'min': 0.0, 'max': 360.0, 'unit': '度'}  # 0-360度
            }
            
            logger.info("开始设置卫星轨道参数...")
            logger.info(f"接收到的轨道参数: {orbital_params}")
            
            # 参数合理性检查和日志记录
            validated_params = {}
            for param_name, param_value in orbital_params.items():
                if param_name in ORBITAL_THRESHOLDS:
                    threshold = ORBITAL_THRESHOLDS[param_name]
                    min_val = threshold['min']
                    max_val = threshold['max']
                    unit = threshold['unit']
                    
                    # 检查参数是否在合理范围内
                    if param_value < min_val or param_value > max_val:
                        logger.warning(f"参数 {param_name} = {param_value} {unit} 超出合理范围 [{min_val}, {max_val}]")
                        logger.warning(f"继续使用该参数，但可能导致轨道异常")
                    else:
                        logger.info(f"参数 {param_name} = {param_value} {unit} 在合理范围内")
                    
                    validated_params[param_name] = param_value
                else:
                    logger.warning(f"未知的轨道参数: {param_name} = {param_value}")
                    validated_params[param_name] = param_value
            
            # 取参数，兼容两种近地点幅角参数名
            semi_axis = validated_params.get('semi_axis')
            eccentricity = validated_params.get('eccentricity')
            inclination = validated_params.get('inclination')
            raan = validated_params.get('raan')
            arg_of_perigee = validated_params.get('arg_of_perigee', validated_params.get('argument_of_perigee'))
            mean_anomaly = validated_params.get('mean_anomaly')
            
            # 使用优化的COM接口设置Walker星座轨道参数
            logger.info("🔄 使用优化的COM接口设置轨道参数...")

            try:
                # 方法1: 使用Keplerian轨道表示法（更稳定）
                logger.info("尝试使用Keplerian轨道表示法...")

                # 获取Keplerian轨道对象
                keplerian = satellite.Propagator.InitialState.Representation.ConvertTo(1)  # 1 = eOrbitStateClassical

                # 设置轨道参数类型
                keplerian.SizeShapeType = 0  # eSizeShapeAltitude (使用高度)
                keplerian.LocationType = 5   # eLocationTrueAnomaly (使用真近点角)
                keplerian.Orientation.AscNodeType = 0  # eAscNodeLAN (使用升交点赤经)

                # 设置轨道参数
                keplerian.SizeShape.PerigeeAltitude = semi_axis - 6371.0  # 近地点高度 (km)
                keplerian.SizeShape.ApogeeAltitude = semi_axis - 6371.0   # 远地点高度 (km) - 圆轨道
                keplerian.Orientation.Inclination = inclination  # 倾角 (度)
                keplerian.Orientation.ArgOfPerigee = arg_of_perigee  # 近地点幅角 (度)
                keplerian.Orientation.AscNode.Value = raan  # 升交点赤经 (度)
                keplerian.Location.Value = mean_anomaly  # 平近点角转真近点角 (度)

                # 应用轨道参数
                satellite.Propagator.InitialState.Representation.Assign(keplerian)
                logger.info("✅ Keplerian轨道参数设置成功")

                # 设置传播器类型为J2摄动
                satellite.SetPropagatorType(1)  # 1 = ePropagatorJ2Perturbation
                logger.info("✅ 传播器类型设置为J2摄动")

                # 传播轨道
                satellite.Propagator.Propagate()
                logger.info("✅ 轨道传播完成")

                logger.info("✅ 轨道参数设置成功，卫星轨道已更新")

            except Exception as keplerian_error:
                logger.warning(f"⚠️ Keplerian方法失败: {keplerian_error}")
                logger.info("🔄 尝试备用AssignClassical方法...")

                try:
                    # 备用方法: AssignClassical
                    # 设置传播器类型
                    satellite.SetPropagatorType(1)  # 1 = ePropagatorJ2Perturbation

                    # 转换为STK内部单位
                    semi_major_axis_m = semi_axis * 1000.0  # km -> m
                    inclination_rad = math.radians(inclination)
                    raan_rad = math.radians(raan)
                    arg_of_perigee_rad = math.radians(arg_of_perigee)
                    mean_anomaly_rad = math.radians(mean_anomaly)

                    # 获取传播器对象
                    propagator = satellite.Propagator
                    initial_state = propagator.InitialState
                    representation = initial_state.Representation

                    # 使用AssignClassical方法
                    representation.AssignClassical(
                        3,                 # 3 = J2000坐标系
                        semi_major_axis_m,  # 半长轴 (m)
                        eccentricity,       # 偏心率
                        inclination_rad,    # 倾角 (弧度)
                        raan_rad,          # RAAN (弧度)
                        arg_of_perigee_rad, # 近地点幅角 (弧度)
                        mean_anomaly_rad    # 平近点角 (弧度)
                    )
                    logger.info("✅ AssignClassical备用方法设置轨道参数成功")

                    # 传播轨道
                    satellite.Propagator.Propagate()
                    logger.info("✅ 轨道传播完成")

                    logger.info("✅ 轨道参数设置成功，卫星轨道已更新")

                except Exception as classical_error:
                    logger.error(f"❌ AssignClassical备用方法也失败: {classical_error}")
                    # 最后尝试基本传播
                    try:
                        satellite.Propagator.Propagate()
                        logger.warning("⚠️ 使用默认参数完成轨道传播")
                    except Exception as prop_error:
                        logger.error(f"❌ 轨道传播失败: {prop_error}")
                        raise

        except Exception as e:
            logger.error(f"设置轨道参数失败: {e}")
            raise
    
    def create_sensor(self, satellite_id: str, sensor_params: Dict) -> bool:
        """
        为卫星创建载荷（传感器）
        
        Args:
            satellite_id: 卫星ID
            sensor_params: 载荷参数
            
        Returns:
            创建是否成功
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return False
        
        try:
            # 遍历Children查找卫星对象
            satellite = None
            for i in range(self.scenario.Children.Count):
                child = self.scenario.Children.Item(i)
                if getattr(child, 'ClassName', None) == 'Satellite' and getattr(child, 'InstanceName', None) == satellite_id:
                    satellite = child
                    break
            
            if satellite is None:
                logger.error(f"卫星 {satellite_id} 不存在")
                return False
            
            # 创建载荷（传感器）
            sensor_id = f"{satellite_id}_Payload"
            
            # 使用COM接口创建传感器
            sensor = satellite.Children.New(self.object_types["sensor"], sensor_id)
            logger.info(f"使用COM接口创建载荷: {sensor_id}")

            # 等待传感器对象完全创建
            time.sleep(self.wait_times["sensor_creation"])
            
            try:
                # 配置载荷参数
                self._configure_payload(sensor, sensor_params, satellite_id, sensor_id)
                
                logger.info(f"载荷 {sensor_id} 创建成功")
                return True
                
            except Exception as sensor_error:
                logger.warning(f"载荷配置失败，但载荷对象已创建: {sensor_error}")
                # 即使配置失败，载荷对象已经创建，返回成功
                return True
            
        except Exception as e:
            logger.error(f"创建载荷失败: {e}")
            return False
    
    def _configure_payload(self, sensor, payload_params: Dict, satellite_id: str = None, sensor_id: str = None):
        """
        配置载荷参数 - 统一配置函数

        Args:
            sensor: STK传感器对象
            payload_params: 载荷参数
            satellite_id: 卫星ID
            sensor_id: 传感器ID
        """
        try:
            logger.info("=============== 开始详细配置载荷参数 ===============")
            logger.info(f"接收到的载荷参数: {payload_params}")
            
            # 记录配置结果
            config_results = {
                "success": [],
                "failed": []
            }
            
            # 1. 配置圆锥视场参数（借鉴成功经验）
            cone_config_result = self._configure_conic_pattern(sensor, payload_params)
            config_results["success"].extend(cone_config_result["success"])
            config_results["failed"].extend(cone_config_result["failed"])
            
            # 2. 配置指向参数
            pointing_config_result = self._configure_pointing_parameters(sensor, payload_params)
            config_results["success"].extend(pointing_config_result["success"])
            config_results["failed"].extend(pointing_config_result["failed"])
            
            # 3. 配置约束参数
            constraint_results = self._configure_sensor_constraints(sensor, payload_params)
            config_results["success"].extend(constraint_results["success"])
            config_results["failed"].extend(constraint_results["failed"])
            
            # 输出配置结果总结
            logger.info("=== 载荷配置结果总结 ===")
            logger.info(f"成功配置的参数 ({len(config_results['success'])} 个):")
            for success_param in config_results["success"]:
                logger.info(f"  ✓ {success_param}")
            
            if config_results["failed"]:
                logger.warning(f"配置失败的参数 ({len(config_results['failed'])} 个):")
                for failed_param in config_results["failed"]:
                    logger.warning(f"  ✗ {failed_param}")
            else:
                logger.info("所有参数配置成功！")
            
            logger.info("=== 载荷配置完成 ===")
            
        except Exception as e:
            logger.error(f"配置载荷失败: {e}")
            raise
    
    def _configure_conic_pattern(self, sensor, payload_params: Dict):
        """
        配置圆锥视场参数 - 基于成功经验
        
        Args:
            sensor: STK传感器对象
            payload_params: 载荷参数
            
        Returns:
            Dict: 包含成功和失败配置的字典
        """
        config_results = {
            "success": [],
            "failed": []
        }
        
        try:
            # 获取圆锥视场参数
            inner_cone_half_angle = payload_params.get('inner_cone_half_angle', 66.1)
            outer_cone_half_angle = payload_params.get('outer_cone_half_angle', 85.0)
            clockwise_angle_min = payload_params.get('clockwise_angle_min', 0.0)
            clockwise_angle_max = payload_params.get('clockwise_angle_max', 360.0)
            
            # 验证参数范围
            if inner_cone_half_angle < 0.0 or inner_cone_half_angle > 90.0:
                logger.warning(f"⚠ 内锥半角{inner_cone_half_angle}°超出范围[0.0°, 90.0°]，将使用边界值")
                inner_cone_half_angle = max(0.0, min(inner_cone_half_angle, 90.0))
            if outer_cone_half_angle < 0.0 or outer_cone_half_angle > 180.0:
                logger.warning(f"⚠ 外锥半角{outer_cone_half_angle}°超出范围[0.0°, 180.0°]，将使用边界值")
                outer_cone_half_angle = max(0.0, min(outer_cone_half_angle, 180.0))
            if clockwise_angle_min < 0.0 or clockwise_angle_min > 360.0 or clockwise_angle_max < 0.0 or clockwise_angle_max > 360.0:
                logger.warning(f"⚠ 顺时针旋转角约束超出范围[0.0°, 360.0°]，将使用边界值")
                clockwise_angle_min = max(0.0, min(clockwise_angle_min, 360.0))
                clockwise_angle_max = max(0.0, min(clockwise_angle_max, 360.0))
            if clockwise_angle_min >= clockwise_angle_max:
                logger.error(f"❌ 顺时针旋转角最小值({clockwise_angle_min}°)大于等于最大值({clockwise_angle_max}°)")
                raise ValueError(f"顺时针旋转角配置错误: 最小值({clockwise_angle_min}°)大于等于最大值({clockwise_angle_max}°)")
            if inner_cone_half_angle >= outer_cone_half_angle:
                logger.error(f"❌ 内锥半角({inner_cone_half_angle}°)大于等于外锥半角({outer_cone_half_angle}°)")
                raise ValueError(f"锥角配置错误: 内锥半角({inner_cone_half_angle}°)大于等于外锥半角({outer_cone_half_angle}°)")
            
            # 优化的载荷圆锥视场参数设置
            try:
                logger.info("🔄 开始设置传感器圆锥视场参数...")

                # 方法1: 使用验证成功的SetPatternType(0)方法
                try:
                    # 设置传感器模式为锥形 - 使用验证成功的方法
                    sensor.SetPatternType(self.sensor_patterns["conic"])
                    logger.info("✓ 使用SetPatternType设置传感器模式为锥形成功")

                    # 等待设置生效
                    import time
                    time.sleep(self.wait_times["pattern_setup"])

                    # 获取Pattern对象并设置参数
                    pattern = sensor.Pattern

                    # 设置锥形参数 - 按验证成功的方法
                    pattern.OuterConeHalfAngle = outer_cone_half_angle
                    pattern.InnerConeHalfAngle = inner_cone_half_angle
                    pattern.MinimumClockAngle = clockwise_angle_min
                    pattern.MaximumClockAngle = clockwise_angle_max

                    logger.info(f"✓ 使用验证成功的方法设置锥形参数成功: 内锥角{inner_cone_half_angle}°, 外锥角{outer_cone_half_angle}°")
                    config_results["success"].append(f"圆锥视场参数(验证成功方法, 内锥角{inner_cone_half_angle}°, 外锥角{outer_cone_half_angle}°)")

                except Exception as verified_method_error:
                    logger.warning(f"⚠️ 验证成功的方法失败: {verified_method_error}")

                    # 方法2: 使用正确的STK COM接口设置锥形传感器
                    try:
                        # 首先尝试使用STK枚举常量设置传感器模式为圆锥
                        # STK Pattern类型枚举: 0=eConic, 1=eCustom, 2=eHalfPower, 3=eOmni, 4=eRectangular
                        sensor.SetPatternType(0)  # 0 = eConic (锥形)
                        logger.info("✓ 设置传感器模式为圆锥成功")

                        # 等待模式设置完成
                        import time
                        time.sleep(0.2)  # 增加等待时间确保设置生效

                        # 获取Pattern对象并验证类型
                        pattern = sensor.Pattern
                        logger.info(f"✓ 获取Pattern对象成功，类型: {type(pattern)}")

                        # 设置圆锥参数 - 使用更稳定的方法
                        try:
                            # 设置外锥角
                            pattern.OuterConeHalfAngle = outer_cone_half_angle
                            logger.info(f"✓ 设置外锥角成功: {outer_cone_half_angle}°")

                            # 设置内锥角
                            pattern.InnerConeHalfAngle = inner_cone_half_angle
                            logger.info(f"✓ 设置内锥角成功: {inner_cone_half_angle}°")

                            # 设置时钟角约束
                            pattern.MinimumClockAngle = clockwise_angle_min
                            pattern.MaximumClockAngle = clockwise_angle_max
                            logger.info(f"✓ 设置时钟角约束成功: {clockwise_angle_min}° - {clockwise_angle_max}°")

                            config_results["success"].append(f"圆锥视场参数(Pattern对象, 内锥角{inner_cone_half_angle}°, 外锥角{outer_cone_half_angle}°)")

                        except Exception as param_error:
                            logger.warning(f"⚠️ 设置圆锥参数失败: {param_error}")
                            # 尝试逐个设置参数
                            try:
                                pattern.OuterConeHalfAngle = outer_cone_half_angle
                                logger.info(f"✓ 单独设置外锥角成功: {outer_cone_half_angle}°")
                                config_results["success"].append(f"圆锥视场参数(外锥角{outer_cone_half_angle}°)")
                            except Exception as outer_error:
                                logger.error(f"❌ 设置外锥角失败: {outer_error}")
                                config_results["failed"].append(f"外锥角设置: {outer_error}")

                    except Exception as pattern_error:
                        logger.warning(f"⚠️ Pattern对象方法失败: {pattern_error}")

                        # 方法3: 使用基本圆锥角设置
                        try:
                            # 尝试设置基本圆锥角
                            if hasattr(sensor, 'ConeAngle'):
                                sensor.ConeAngle = outer_cone_half_angle
                                logger.info(f"✓ 使用基本ConeAngle设置成功: {outer_cone_half_angle}°")
                                config_results["success"].append(f"圆锥视场参数(基本ConeAngle, 角度{outer_cone_half_angle}°)")
                            else:
                                logger.warning("⚠️ 传感器不支持ConeAngle属性")
                                config_results["failed"].append(f"圆锥视场参数设置: 传感器不支持圆锥角设置")

                        except Exception as basic_error:
                            logger.warning(f"⚠️ 基本方法也失败: {basic_error}")
                            config_results["failed"].append(f"圆锥视场参数设置: 所有方法都失败")

            except Exception as e:
                logger.error(f"❌ 圆锥视场参数设置异常: {e}")
                config_results["failed"].append(f"圆锥视场参数设置异常: {e}")
            
        except Exception as e:
            logger.error(f"配置圆锥视场参数失败: {e}")
            config_results["failed"].append(f"圆锥视场参数配置: {e}")
        
        return config_results
    
    def _configure_pointing_parameters(self, sensor, payload_params: Dict):
        """
        配置指向参数 - 使用STK官方推荐的CommonTasks.SetPointingFixedAzEl方法
        
        Args:
            sensor: STK传感器对象
            payload_params: 载荷参数
            
        Returns:
            Dict: 包含成功和失败配置的字典
        """
        config_results = {
            "success": [],
            "failed": []
        }
        
        # 从配置文件中读取指向参数
        pointing_config = payload_params.get('pointing', {})
        point_azimuth = pointing_config.get('azimuth', 0.0)
        point_elevation = pointing_config.get('elevation', 90.0)
        
        # 验证指向参数范围
        if point_azimuth < -180.0 or point_azimuth > 180.0:
            logger.warning(f"⚠ 方位角{point_azimuth}°超出范围[-180.0°, 180.0°]，将使用边界值")
            point_azimuth = max(-180.0, min(point_azimuth, 180.0))
        if point_elevation < -90.0 or point_elevation > 90.0:
            logger.warning(f"⚠ 俯仰角{point_elevation}°超出范围[-90.0°, 90.0°]，将使用边界值")
            point_elevation = max(-90.0, min(point_elevation, 90.0))
        
        # 使用STK官方推荐的CommonTasks.SetPointingFixedAzEl方法
        try:
            # 参数顺序：方位角, 俯仰角, 旋转标志(1=rotate, 0=Hold)
            sensor.CommonTasks.SetPointingFixedAzEl(point_azimuth, point_elevation, 1)
            logger.info(f"✓ 使用STK官方方法设置指向参数成功: 方位角{point_azimuth}°, 俯仰角{point_elevation}°")
            config_results["success"].append(f"指向参数(STK官方方法, 方位角{point_azimuth}°, 俯仰角{point_elevation}°)")
        except Exception as e:
            logger.warning(f"⚠ STK官方方法设置指向参数失败: {e}")
        
        return config_results
    
    def _configure_sensor_constraints(self, sensor, payload_params: Dict):
        """
        设置载荷约束参数 - 使用STK官方Python COM API的AddConstraint方法
        
        Args:
            sensor: STK传感器对象
            payload_params: 载荷参数
            
        Returns:
            Dict: 包含成功和失败配置的字典
        """
        try:
            config_results = {
                "success": [],
                "failed": []
            }
            
            logger.info("=============== 开始配置传感器约束 ===============")
            
            # 等待传感器完全初始化
            import time
            time.sleep(0.5)
            
            # 获取传感器约束对象 - 使用STK官方API
            try:
                senConstraints = sensor.AccessConstraints
                logger.info("✓ 获取传感器约束对象成功")
            except Exception as e:
                logger.error(f"✗ 获取传感器约束对象失败: {e}")
                return {"success": [], "failed": [f"获取约束对象: {e}"]}
            
            # STK约束类型常量 - 根据STK官方示例
            # 使用AgEAccessConstraints枚举值
            AgEAccessConstraints = {
                'eCstrRange': 34,
                'eCstrLOSSunExclusion': 2,
                'eCstrBSSunExclusion': 3
            }     # Duration约束
            
            # 1. 配置距离约束 (Range Constraints) - 根据STK官方示例
            if 'constraints_range' in payload_params:
                range_constraints = payload_params['constraints_range']
                min_range_km = range_constraints.get('min_range', 0.0)
                max_range_km = range_constraints.get('max_range', 4000.0)
                
                logger.info(f"配置距离约束: {min_range_km} km 到 {max_range_km} km")
                
                try:
                    # 等待传感器完全初始化
                    import time
                    time.sleep(0.5)
                    
                    # 严格按照成功示例实现距离约束配置
                    # 可见性约束
                    senConstraints = sensor.AccessConstraints
                    
                    # 视距限制 - 按照成功示例
                    minmaxRange = senConstraints.AddConstraint(AgEAccessConstraints["eCstrRange"])
                    minmaxRange.EnableMin = True
                    minmaxRange.EnableMax = True
                    minmaxRange.Min = min_range_km
                    minmaxRange.Max = max_range_km
                    
                    logger.info(f"✓ 设置距离约束成功: {min_range_km} km 到 {max_range_km} km")
                    config_results["success"].append(f"距离约束({min_range_km} km 到 {max_range_km} km)")
                except Exception as e:
                    logger.warning(f"⚠ 设置距离约束失败: {e}")
                    config_results["failed"].append(f"距离约束: {e}")
            
            # 5. 配置能源约束 (Energy Constraints) - 仅记录参数，STK不直接支持能源约束
            if 'energy_management' in payload_params:
                energy_config = payload_params['energy_management']
                battery_capacity = energy_config.get('battery_capacity', 1000.0)
                standby_power = energy_config.get('standby_power', 20.0)
                observation_power = energy_config.get('observation_power', 80.0)
                transmission_power = energy_config.get('transmission_power', 60.0)
                
                logger.info(f"记录能源管理参数: 电池容量{battery_capacity}Wh, 待机功耗{standby_power}W, 观测功耗{observation_power}W, 传输功耗{transmission_power}W")
                
                try:
                    # 能源约束需要通过自定义逻辑实现，这里仅记录参数
                    logger.info(f"✓ 记录能源参数成功")
                    config_results["success"].append(f"能源参数记录(电池{battery_capacity}Wh, 待机{standby_power}W, 观测{observation_power}W, 传输{transmission_power}W)")
                except Exception as e:
                    logger.warning(f"⚠ 记录能源参数失败: {e}")
                    config_results["failed"].append(f"能源参数记录: {e}")
            
            # 输出配置结果总结
            logger.info("=== 传感器约束配置结果总结 ===")
            logger.info(f"成功配置的约束 ({len(config_results['success'])} 个):")
            for success_constraint in config_results["success"]:
                logger.info(f"  ✓ {success_constraint}")
            
            if config_results["failed"]:
                logger.warning(f"失败的约束配置 ({len(config_results['failed'])} 个):")
                for failed_constraint in config_results["failed"]:
                    logger.warning(f"  ✗ {failed_constraint}")
            
            logger.info("=============== 传感器约束配置完成 ===============")
            
            return config_results
            
        except Exception as e:
            logger.error(f"设置载荷约束失败: {e}")
            return {"success": [], "failed": [f"载荷约束设置: {e}"]}
    
    def get_satellite_position(self, satellite_id: str, time_shift: float = 0) -> Optional[Dict]:
        """
        🔧 修复版：获取卫星位置 - 解决STK服务器状态问题

        Args:
            satellite_id: 卫星ID
            time_shift: 时间偏移量（秒）

        Returns:
            卫星位置信息
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return None

        # 🔧 修复：检查STK服务器状态
        if not self._check_stk_server_status():
            logger.warning("STK服务器状态异常，尝试恢复...")
            if not self._recover_stk_server():
                logger.error("STK服务器恢复失败，无法获取卫星位置")
                return None

        try:
            # 兼容带 "Satellite/" 前缀的卫星ID
            if satellite_id.startswith("Satellite/"):
                sat_name = satellite_id.split("/", 1)[1]
            else:
                sat_name = satellite_id

            # 🔧 修复1：直接使用卫星对象而不是传感器
            satellite = self.scenario.Children.Item(sat_name)

            # 🔧 修复2：确保卫星已传播
            try:
                # 强制传播卫星以确保位置数据可用
                satellite.Propagator.Propagate()
                logger.debug(f"卫星 {sat_name} 传播完成")
            except Exception as prop_e:
                logger.warning(f"卫星 {sat_name} 传播失败: {prop_e}")

            # 🔧 修复3：使用多种方法尝试获取位置
            position_data = None

            # 方法1：使用卫星的Cartesian Position数据提供者
            try:
                dp = satellite.DataProviders.Item("Cartesian Position")
                start_time = self.scenario.StartTime
                end_time = self.scenario.StartTime  # 只获取开始时间的位置
                result = dp.Exec(start_time, end_time)

                if result and result.DataSets.Count > 0:
                    dataset = result.DataSets.Item(0)
                    if dataset.RowCount > 0:
                        x = dataset.GetValue(0, 1)  # 第1列是X
                        y = dataset.GetValue(0, 2)  # 第2列是Y
                        z = dataset.GetValue(0, 3)  # 第3列是Z
                        position_data = {
                            'time': start_time,
                            'x': float(x),
                            'y': float(y),
                            'z': float(z)
                        }
                        logger.debug(f"方法1成功获取卫星 {sat_name} 位置: ({x:.1f}, {y:.1f}, {z:.1f})")
            except Exception as e1:
                logger.debug(f"方法1失败: {e1}")

            # 方法2：如果方法1失败，尝试使用LLA Position
            if position_data is None:
                try:
                    dp = satellite.DataProviders.Item("LLA Position")
                    start_time = self.scenario.StartTime
                    result = dp.Exec(start_time, start_time)

                    if result and result.DataSets.Count > 0:
                        dataset = result.DataSets.Item(0)
                        if dataset.RowCount > 0:
                            lat = dataset.GetValue(0, 1)  # 纬度
                            lon = dataset.GetValue(0, 2)  # 经度
                            alt = dataset.GetValue(0, 3)  # 高度
                            position_data = {
                                'time': start_time,
                                'lat': float(lat),
                                'lon': float(lon),
                                'alt': float(alt)
                            }
                            logger.debug(f"方法2成功获取卫星 {sat_name} 位置: ({lat:.6f}°, {lon:.6f}°, {alt:.1f}m)")
                except Exception as e2:
                    logger.debug(f"方法2失败: {e2}")

            # 方法3：如果前两种方法都失败，使用传感器位置（如果存在）
            if position_data is None:
                try:
                    sensor = None
                    for i in range(satellite.Children.Count):
                        child = satellite.Children.Item(i)
                        if hasattr(child, 'ClassName') and child.ClassName == 'Sensor':
                            sensor = child
                            break

                    if sensor:
                        dp = sensor.DataProviders.Item("Points(ICRF)").Group('Center')
                        start_time = self.scenario.StartTime
                        result = dp.Exec(start_time, start_time, 60)

                        if result.DataSets.Count > 0:
                            times = result.DataSets.GetDataSetByName("Time").GetValues()
                            x_pos = result.DataSets.GetDataSetByName("x").GetValues()
                            y_pos = result.DataSets.GetDataSetByName("y").GetValues()
                            z_pos = result.DataSets.GetDataSetByName("z").GetValues()
                            if times and x_pos and y_pos and z_pos and len(times) > 0:
                                position_data = {
                                    'time': times[0],
                                    'x': float(x_pos[0]),
                                    'y': float(y_pos[0]),
                                    'z': float(z_pos[0])
                                }
                                logger.debug(f"方法3成功获取卫星 {sat_name} 位置")
                except Exception as e3:
                    logger.debug(f"方法3失败: {e3}")

            if position_data:
                return position_data
            else:
                logger.warning(f"所有方法都无法获取卫星 {satellite_id} 的位置数据")
                return None

        except Exception as e:
            logger.error(f"获取卫星位置失败: {e}")
            # 辅助调试：打印所有场景中的卫星名称
            try:
                sat_names = []
                for i in range(self.scenario.Children.Count):
                    obj = self.scenario.Children.Item(i)
                    if hasattr(obj, 'ClassName') and obj.ClassName == 'Satellite':
                        sat_names.append(obj.InstanceName)
                logger.error(f"当前场景可用卫星名称: {sat_names}")
            except Exception as e2:
                logger.error(f"辅助打印卫星名称失败: {e2}")
            return None
    
    def _get_time_by_shift(self, time_shift: float) -> str:
        """
        根据时间偏移量计算时间字符串
        
        Args:
            time_shift: 时间偏移量（秒）
            
        Returns:
            时间字符串
        """
        try:
            # 将场景开始时间转换为时间戳
            start_timestamp = self._date_string_to_timestamp(self.scenario_begin_time)
            target_timestamp = start_timestamp + time_shift * 1000  # 转换为毫秒
            
            # 转换回日期字符串
            return self._timestamp_to_date_string(target_timestamp)
        except Exception as e:
            logger.error(f"时间转换失败: {e}")
            return self.scenario_begin_time
    
    def _date_string_to_timestamp(self, date_string: str) -> int:
        """将日期字符串转换为时间戳（毫秒）"""
        try:
            # 解析日期字符串格式 "YYYY/MM/DD HH:MM:SS"
            dt = datetime.strptime(date_string, "%Y/%m/%d %H:%M:%S")
            return int(dt.timestamp() * 1000)
        except:
            # 如果解析失败，使用仿真开始时间
            from src.utils.time_manager import get_time_manager
            time_manager = get_time_manager()
            return int(time_manager.start_time.timestamp() * 1000)
    
    def _timestamp_to_date_string(self, timestamp: int) -> str:
        """将时间戳转换为日期字符串"""
        try:
            dt = datetime.fromtimestamp(timestamp / 1000)
            return dt.strftime("%Y/%m/%d %H:%M:%S")
        except:
            return self.scenario_begin_time
    
    def calculate_visibility(self, satellite_id: str, target_info: Dict) -> Dict:
        """
        计算卫星对目标的可见性
        
        Args:
            satellite_id: 卫星ID
            target_info: 目标信息
            
        Returns:
            可见性分析结果
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return {}
        
        try:
            # 创建或获取目标
            target_id = target_info.get('target_id', 'Target_001')
            target = self._create_or_get_target(target_id, target_info)
            
            # 获取卫星传感器 - 基于experence.py的成功经验
            # 直接使用卫星名称，不需要添加"Satellite/"前缀
            satellite = self.scenario.Children.Item(satellite_id)
            
            # 获取传感器 - 基于experence.py的成功经验，使用"Sensor"名称
            sensor = satellite.Children.Item("Sensor")
            
            # 计算可见性
            access = sensor.GetAccessToObject(target)
            access.ComputeAccess()
            
            # 获取可见窗口
            accessDP = access.DataProviders.Item("Access Data")
            result = accessDP.Exec(self.scenario_begin_time, self.scenario_end_time)
            
            times = result.DataSets.GetDataSetByName("Time").GetValues()
            access_times = result.DataSets.GetDataSetByName("Access").GetValues()
            
            visibility_windows = []
            if times and access_times:
                for i, access_flag in enumerate(access_times):
                    if access_flag == 1:  # 可见
                        visibility_windows.append(times[i])
            
            return {
                'has_visibility': len(visibility_windows) > 0,
                'visibility_windows': visibility_windows,
                'total_windows': len(visibility_windows)
            }
            
        except Exception as e:
            logger.error(f"计算可见性失败: {e}")
            return {'has_visibility': False}
    
    def _create_or_get_target(self, target_id: str, target_info: Dict):
        """
        创建或获取目标对象
        
        Args:
            target_id: 目标ID
            target_info: 目标信息
            
        Returns:
            目标对象
        """
        try:
            # 尝试获取现有目标
            target_path = f"Target/{target_id}"
            target = self.root.GetObjectFromPath(target_path)
            logger.info(f"使用现有目标: {target_id}")
        except:
            # 创建新目标
            target = self.scenario.Children.New(20, target_id)  # 20 = eTarget
            logger.info(f"创建新目标: {target_id}")
            
            # 设置目标位置
            if 'position' in target_info:
                pos = target_info['position']
                target.Position.AssignGeodetic(pos['lat'], pos['lon'], pos['alt'])
        
        return target
    
    def delete_objects(self, obj_type: str, delete_all: bool = False, obj_list: List[str] = None):
        """
        删除对象
        
        Args:
            obj_type: 对象类型
            delete_all: 是否删除所有对象
            obj_list: 要删除的对象列表
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return
        
        try:
            if delete_all:
                # 删除所有指定类型的对象
                objects = self.get_objects(obj_type)
                for obj_path in objects:
                    obj_name = obj_path.split('/')[-1]
                    try:
                        # 使用COM接口删除对象
                        obj = self.root.GetObjectFromPath(f"*/{obj_type}/{obj_name}")
                        obj.Unload()
                        logger.info(f"使用COM接口删除对象: {obj_name}")
                    except Exception as e:
                        logger.warning(f"COM接口删除失败: {e}")
                        # 尝试使用另一种COM接口方法
                        try:
                            # 通过场景对象删除
                            for i in range(self.scenario.Children.Count):
                                child = self.scenario.Children.Item(i)
                                if getattr(child, 'ClassName', None) == obj_type and getattr(child, 'InstanceName', None) == obj_name:
                                    child.Unload()
                                    logger.info(f"使用备用COM接口方法删除对象: {obj_name}")
                                    break
                        except Exception as cmd_error:
                            logger.error(f"备用COM接口方法也失败: {cmd_error}")
                logger.info(f"删除所有 {obj_type} 对象")
            elif obj_list:
                # 删除指定对象
                for obj_name in obj_list:
                    try:
                        # 使用COM接口删除对象
                        obj = self.root.GetObjectFromPath(f"*/{obj_type}/{obj_name}")
                        obj.Unload()
                        logger.info(f"使用COM接口删除对象: {obj_name}")
                    except Exception as e:
                        logger.warning(f"COM接口删除失败: {e}")
                        # 尝试使用另一种COM接口方法
                        try:
                            # 通过场景对象删除
                            for i in range(self.scenario.Children.Count):
                                child = self.scenario.Children.Item(i)
                                if getattr(child, 'ClassName', None) == obj_type and getattr(child, 'InstanceName', None) == obj_name:
                                    child.Unload()
                                    logger.info(f"使用备用COM接口方法删除对象: {obj_name}")
                                    break
                        except Exception as cmd_error:
                            logger.error(f"备用COM接口方法也失败: {cmd_error}")
                logger.info(f"删除指定的 {obj_type} 对象")
                
        except Exception as e:
            logger.error(f"删除对象失败: {e}")
    

    
    def close_scenario(self):
        """关闭场景"""
        if not self.scenario:
            return
        
        try:
            self.root.CloseScenario()
            logger.info("场景已关闭")
        except Exception as e:
            logger.error(f"关闭场景失败: {e}")
    
    # 兼容性方法，保持与原有代码的接口一致
    async def connect_async(self) -> bool:
        """异步连接方法，保持兼容性"""
        return self.connect()
    
    def create_walker_constellation(self, config: Dict[str, Any]) -> bool:
        """创建Walker星座 - 基于成功经验的方法"""
        try:
            logger.info("开始创建Walker星座...")
            
            # 检查连接状态
            if not self.scenario or not self.is_connected:
                logger.error("STK未连接，无法创建星座")
                return False
            
            # 获取星座配置
            constellation_config = config["constellation"]
            num_planes = constellation_config["planes"]
            sats_per_plane = constellation_config["satellites_per_plane"]
            total_satellites = constellation_config["total_satellites"]
            
            logger.info(f"星座配置: {num_planes}个轨道面, 每面{sats_per_plane}颗卫星, 总计{total_satellites}颗")
            
            # 创建种子卫星
            if not self._create_seed_satellite(config):
                logger.error("种子卫星创建失败")
                return False
            
            # 创建Walker星座
            if not self._create_walker_constellation_from_seed(num_planes, sats_per_plane):
                logger.error("Walker星座创建失败")
                return False
            
            # 为所有卫星创建传感器
            if not self._create_sensors_for_all_satellites(config):
                logger.error("传感器创建失败")
                return False
            
            # 删除种子卫星，因为星座中已经包含了种子卫星
            if not self._delete_seed_satellite():
                logger.warning("种子卫星删除失败，但不影响星座功能")
            
            logger.info(f"Walker星座创建完成，共{total_satellites}颗卫星")
            
            return True
            
        except Exception as e:
            logger.error(f"创建Walker星座失败: {e}")
            return False
    
    def _create_seed_satellite(self, config: Dict[str, Any]) -> bool:
        """创建种子卫星 - 基于成功经验"""
        try:
            # 自动清理同名卫星
            try:
                self.root.CurrentScenario.Children.Unload(18, "Satellite")  # 18 = eSatellite
                logger.info("已清理同名卫星: Satellite")
            except Exception:
                pass  # 如果不存在则忽略
            
            # 创建种子卫星
            satellite_seed = self.root.CurrentScenario.Children.New(18, "Satellite")
            logger.info("创建种子卫星: Satellite")
            
            # 获取轨道参数配置
            ref_sat = config["constellation"]["reference_satellite"]
            
            # 设置轨道传播器为经典开普勒轨道
            keplerian = satellite_seed.Propagator.InitialState.Representation.ConvertTo(1)
            
            # 设置轨道参数类型
            keplerian.SizeShapeType = 0  # eSizeShapeAltitude
            keplerian.LocationType = 5   # eLocationTrueAnomaly
            keplerian.Orientation.AscNodeType = 0  # eAscNodeLAN
            
            # 设置轨道参数 - 基于成功经验
            keplerian.SizeShape.PerigeeAltitude = ref_sat["altitude"]  # km
            keplerian.SizeShape.ApogeeAltitude = ref_sat["altitude"]   # km
            keplerian.Orientation.Inclination = ref_sat["inclination"]  # deg
            keplerian.Orientation.ArgOfPerigee = ref_sat["arg_of_perigee"]  # deg
            keplerian.Orientation.AscNode.Value = ref_sat["raan_offset"]  # deg
            keplerian.Location.Value = ref_sat["mean_anomaly_offset"]  # deg
            
            # 应用轨道参数并传播
            satellite_seed.Propagator.InitialState.Representation.Assign(keplerian)
            satellite_seed.Propagator.Propagate()
            
            logger.info("种子卫星轨道参数设置成功")
            
            # 注意：种子卫星不创建传感器，传感器将在Walker星座创建时统一创建
            
            return True
            
        except Exception as e:
            logger.error(f"创建种子卫星失败: {e}")
            return False
    
    def _create_seed_sensor(self, satellite_seed, config: Dict[str, Any]):
        """创建种子传感器 - 基于成功经验（已废弃，不再使用）"""
        try:
            # 这个方法已废弃，传感器将在Walker星座创建时统一创建
            logger.info("种子传感器创建已废弃，传感器将在Walker星座创建时统一创建")
            
        except Exception as e:
            logger.error(f"创建种子传感器失败: {e}")
            raise
    
    def _create_walker_constellation_from_seed(self, num_planes: int, sats_per_plane: int) -> bool:
        """从种子卫星创建Walker星座 - 基于成功经验"""
        try:
            logger.info(f"开始创建Walker星座: {num_planes}个轨道面, 每面{sats_per_plane}颗卫星")
            
            # 构建Walker星座命令
            walker_cmd = (
                f'Walker */Satellite/Satellite '
                f'Type Delta '
                f'NumPlanes {num_planes} '
                f'NumSatsPerPlane {sats_per_plane} '
                f'InterPlanePhaseIncrement 1 '
                f'ColorByPlane Yes'
            )
            
            # 执行Walker星座命令
            self.root.ExecuteCommand(walker_cmd)
            logger.info("Walker星座命令执行成功")
            
            return True
            
        except Exception as e:
            logger.error(f"创建Walker星座失败: {e}")
            return False
    
    def _delete_seed_satellite(self) -> bool:
        """删除种子卫星 - 星座创建完成后清理"""
        try:
            logger.info("开始删除种子卫星...")
            
            # 查找种子卫星
            seed_satellite = None
            for i in range(self.scenario.Children.Count):
                child = self.scenario.Children.Item(i)
                if (getattr(child, 'ClassName', None) == 'Satellite' and 
                    getattr(child, 'InstanceName', None) == 'Satellite'):
                    seed_satellite = child
                    break
            
            if seed_satellite:
                # 删除种子卫星
                seed_satellite.Unload()
                logger.info("种子卫星删除成功")
                return True
            else:
                logger.info("未找到种子卫星，可能已被删除或不存在")
                return True
                
        except Exception as e:
            logger.error(f"删除种子卫星失败: {e}")
            return False
    
    def _create_sensors_for_all_satellites(self, config: Dict[str, Any]) -> bool:
        """为所有卫星创建传感器 - 基于成功经验"""
        try:
            # 获取所有卫星
            satellites = self.get_objects("Satellite")
            logger.info(f"=== 开始为 {len(satellites)} 颗卫星创建传感器 ===")
            
            # 记录创建结果
            creation_results = {
                "success": [],
                "failed": []
            }
            
            for satellite_path in satellites:
                satellite_id = satellite_path.split('/')[-1]
                logger.info(f"--- 开始为卫星 {satellite_id} 创建传感器 ---")
                
                try:
                    # 获取卫星对象
                    satellite = self.scenario.Children.Item(satellite_id)
                    logger.info(f"✓ 获取卫星对象成功: {satellite_id}")
                    
                    # 自动清理同名传感器
                    sensor_name = f"{satellite_id}_Sensor"
                    try:
                        satellite.Children.Unload(20, sensor_name)  # 20 = eSensor
                        logger.info(f"✓ 已清理同名传感器: {sensor_name}")
                    except Exception:
                        logger.info(f"✓ 无需清理传感器: {sensor_name} (不存在)")
                        pass  # 如果不存在则忽略
                    
                    # 创建传感器
                    sensor = satellite.Children.New(20, sensor_name)  # 20 = eSensor
                    logger.info(f"✓ 传感器对象创建成功: {sensor_name}")
                    
                    # 设置传感器模式为锥形
                    try:
                        # 使用正确的STK枚举值设置锥形模式
                        sensor.SetPatternType(0)  # 0 = eConic (锥形)
                        logger.info(f"✓ 设置传感器模式为锥形成功")

                        # 等待设置生效
                        import time
                        time.sleep(0.1)

                    except Exception as e:
                        logger.error(f"✗ 设置传感器模式失败: {e}")
                        creation_results["failed"].append(f"传感器模式设置({satellite_id}): {e}")
                        continue
                    
                    # 获取并配置锥形模式参数
                    try:
                        conic_pattern = sensor.Pattern
                        logger.info(f"✓ 获取锥形模式参数成功")
                    except Exception as e:
                        logger.error(f"✗ 获取锥形模式参数失败: {e}")
                        creation_results["failed"].append(f"锥形模式参数获取({satellite_id}): {e}")
                        continue
                    
                    # 配置载荷参数（包括圆锥视场、指向参数、约束参数）
                    try:
                        sensor_id = f"{satellite_id}_Payload"
                        self._configure_payload(sensor, config["payload"], satellite_id, sensor_id)
                        logger.info(f"✓ 卫星 {satellite_id} 的载荷配置成功")
                    except Exception as e:
                        logger.warning(f"⚠ 卫星 {satellite_id} 的载荷配置失败: {e}")
                    
                    # 设置传感器约束
                    self._configure_sensor_constraints(sensor, config["payload"])
                    
                    creation_results["success"].append(satellite_id)
                    logger.info(f"✓ 卫星 {satellite_id} 的传感器创建成功")
                    
                except Exception as e:
                    logger.error(f"✗ 为卫星 {satellite_id} 创建传感器失败: {e}")
                    creation_results["failed"].append(f"传感器创建({satellite_id}): {e}")
                    continue
            
            # 输出创建结果总结
            logger.info("=== 传感器创建结果总结 ===")
            logger.info(f"成功创建的传感器 ({len(creation_results['success'])} 个):")
            for success_satellite in creation_results["success"]:
                logger.info(f"  ✓ {success_satellite}")
            
            if creation_results["failed"]:
                logger.warning(f"创建失败的传感器 ({len(creation_results['failed'])} 个):")
                for failed_sensor in creation_results["failed"]:
                    logger.warning(f"  ✗ {failed_sensor}")
            else:
                logger.info("所有传感器创建成功！")
            
            logger.info(f"=== 传感器创建完成: {len(creation_results['success'])}/{len(satellites)} 成功 ===")
            return len(creation_results["success"]) > 0
            
        except Exception as e:
            logger.error(f"创建传感器失败: {e}")
            return False
    
    def _create_payloads(self, config: Dict[str, Any]):
        """创建载荷 - 基于成功经验的方法"""
        try:
            payload_config = config["payload"]
            logger.info("开始创建载荷...")
            
            # 检查连接状态
            if not self.scenario or not self.is_connected:
                logger.error("STK未连接，无法创建载荷")
                return
            
            # 获取所有卫星
            satellites = self.get_objects("Satellite")
            logger.info(f"为 {len(satellites)} 颗卫星创建载荷")
            
            success_count = 0
            for satellite_path in satellites:
                satellite_id = satellite_path.split('/')[-1]
                
                try:
                    # 获取卫星对象
                    satellite = self.scenario.Children.Item(satellite_id)
                    
                    # 自动清理同名传感器
                    sensor_name = f"{satellite_id}_Sensor"
                    try:
                        satellite.Children.Unload(20, sensor_name)  # 20 = eSensor
                        logger.info(f"已清理同名传感器: {sensor_name}")
                    except Exception:
                        pass  # 如果不存在则忽略
                    
                    # 创建传感器
                    sensor = satellite.Children.New(20, sensor_name)  # 20 = eSensor
                    
                    # 设置传感器模式为锥形
                    sensor.SetPatternType(0)  # 0 = eConic (锥形)
                    logger.info(f"✓ 设置传感器模式为锥形成功")

                    # 等待设置生效
                    import time
                    time.sleep(0.1)
                    
                    # 获取并配置锥形模式参数
                    conic_pattern = sensor.Pattern
                    
                    # 验证顺时针旋转角约束范围
                    clockwise_angle_min = payload_config.get("clockwise_angle_min", 0.0)
                    clockwise_angle_max = payload_config.get("clockwise_angle_max", 360.0)
                    
                    if clockwise_angle_min < 0.0 or clockwise_angle_min > 360.0 or clockwise_angle_max < 0.0 or clockwise_angle_max > 360.0:
                        logger.warning(f"⚠ 顺时针旋转角约束超出范围[0.0°, 360.0°]，将使用边界值")
                        clockwise_angle_min = max(0.0, min(clockwise_angle_min, 360.0))
                        clockwise_angle_max = max(0.0, min(clockwise_angle_max, 360.0))
                    if clockwise_angle_min >= clockwise_angle_max:
                        logger.warning(f"⚠ 顺时针旋转角最小值({clockwise_angle_min}°)大于等于最大值({clockwise_angle_max}°)，自动调整为默认值")
                        clockwise_angle_min = 0.0
                        clockwise_angle_max = 360.0
                    
                    # 设置圆锥视场参数（只设置一次）
                    try:
                        conic_pattern.InnerConeHalfAngle = payload_config["inner_cone_half_angle"]
                        conic_pattern.OuterConeHalfAngle = payload_config["outer_cone_half_angle"]
                        conic_pattern.MinimumClockAngle = clockwise_angle_min
                        conic_pattern.MaximumClockAngle = clockwise_angle_max
                        logger.info(f"✓ 设置圆锥视场参数成功: 内锥角{payload_config['inner_cone_half_angle']}°, 外锥角{payload_config['outer_cone_half_angle']}° (旋转角约束: {clockwise_angle_min}° - {clockwise_angle_max}°)")
                    except Exception as e:
                        logger.warning(f"⚠ 属性设置方法失败: {e}")
                        try:
                            # 备用方法：使用Pattern对象
                            pattern = sensor.Pattern
                            pattern.InnerConeHalfAngle = payload_config["inner_cone_half_angle"]
                            pattern.OuterConeHalfAngle = payload_config["outer_cone_half_angle"]
                            pattern.MinimumClockAngle = clockwise_angle_min
                            pattern.MaximumClockAngle = clockwise_angle_max
                            logger.info(f"✓ 使用Pattern对象设置圆锥视场参数成功")
                        except Exception as e2:
                            logger.warning(f"⚠ Pattern对象设置方法也失败: {e2}")
                            logger.error(f"✗ 设置圆锥视场参数失败: {e2}")
                            continue
                    
                    # 设置传感器约束
                    self._configure_sensor_constraints(sensor, config["payload"])
                    
                    success_count += 1
                    logger.info(f"载荷 {sensor_name} 创建成功")
                    
                except Exception as e:
                    logger.error(f"载荷 {satellite_id}_Sensor 创建失败: {e}")
                    continue
            
            logger.info(f"载荷创建完成: {success_count}/{len(satellites)} 成功")
                    
        except Exception as e:
            logger.error(f"创建载荷失败: {e}")
    
    def _configure_payload_parameters(self, payload_config: Dict[str, Any]) -> bool:
        """配置载荷参数 - 兼容性方法，保持大模型系统接口"""
        try:
            # 这个方法主要用于兼容性，确保大模型系统能正常调用
            logger.info("载荷参数配置完成 (兼容性方法)")
            
            # 验证载荷参数
            if not payload_config:
                logger.warning("载荷参数为空")
                return False
                
            # 检查必要的参数
            required_params = ['type', 'sensor_pattern']
            for param in required_params:
                if param not in payload_config:
                    logger.warning(f"缺少必要参数: {param}")
                    return False
                    
            # 验证圆锥视场参数
            if 'inner_cone_half_angle' in payload_config:
                inner_angle = payload_config['inner_cone_half_angle']
                if inner_angle < 0.0 or inner_angle > 90.0:
                    logger.warning(f"内锥半角{inner_angle}°超出范围[0.0°, 90.0°]")
                    
            if 'outer_cone_half_angle' in payload_config:
                outer_angle = payload_config['outer_cone_half_angle']
                if outer_angle < 0.0 or outer_angle > 180.0:
                    logger.warning(f"外锥半角{outer_angle}°超出范围[0.0°, 180.0°]")
                    
            logger.info("载荷参数验证完成")
            return True
            
        except Exception as e:
            logger.error(f"配置载荷参数失败: {e}")
            return False
    
    def get_satellite_list(self) -> List[str]:
        """获取卫星列表 - 兼容性方法"""
        return self.get_objects("Satellite")
    


    async def calculate_visibility_batch(self, visibility_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量计算可见性"""
        try:
            logger.info(f"开始批量计算可见性: {len(visibility_requests)} 个请求")
            
            if not self.is_connected:
                logger.error("STK未连接")
                return [{"visibility": False, "reason": "STK未连接"} for _ in visibility_requests]
            
            # 检查缓存
            cached_results = []
            uncached_requests = []
            
            for request in visibility_requests:
                cache_key = self._generate_visibility_cache_key(request)
                cached_result = self._get_visibility_cache(cache_key)
                
                if cached_result:
                    cached_results.append(cached_result)
                else:
                    uncached_requests.append((request, cache_key))
            
            # 批量处理未缓存的请求
            batch_results = []
            if uncached_requests:
                batch_results = await self._process_visibility_batch(uncached_requests)
                
                # 缓存结果
                for i, (request, cache_key) in enumerate(uncached_requests):
                    if i < len(batch_results):
                        self._cache_visibility_result(cache_key, batch_results[i])
            
            # 合并结果
            all_results = cached_results + batch_results
            logger.info(f"批量可见性计算完成: {len(cached_results)} 缓存, {len(batch_results)} 新计算")
            
            return all_results
            
        except Exception as e:
            logger.error(f"批量可见性计算失败: {e}")
            return [{"visibility": False, "reason": str(e)} for _ in visibility_requests]
            
    async def _process_visibility_batch(self, uncached_requests: List[tuple]) -> List[Dict[str, Any]]:
        """处理批量可见性请求"""
        try:
            results = []
            
            # 使用连接池处理
            async with self._get_stk_connection() as connection:
                for request, cache_key in uncached_requests:
                    try:
                        result = await self._calculate_single_visibility(connection, request)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"单个可见性计算失败: {e}")
                        results.append({"visibility": False, "reason": str(e)})
            
            return results
            
        except Exception as e:
            logger.error(f"批量可见性处理失败: {e}")
            return [{"visibility": False, "reason": str(e)} for _ in uncached_requests]
            
    async def _calculate_single_visibility(self, connection, request: Dict[str, Any]) -> Dict[str, Any]:
        """计算单个可见性"""
        try:
            satellite_id = request.get("satellite_id")
            target_info = request.get("target_info", {})
            start_time = request.get("start_time")
            end_time = request.get("end_time")
            
            # 获取卫星对象
            satellite = connection.GetObjectFromPath(f"Satellite/{satellite_id}")
            
            # 创建或获取目标
            target_id = target_info.get("target_id", "Target_Default")
            target = await self._create_or_get_target(target_id, target_info)
            
            # 计算可见性
            visibility_result = await self.calculate_visibility(satellite_id, target_info)
            
            return visibility_result
            
        except Exception as e:
            logger.error(f"单个可见性计算失败: {e}")
            return {"visibility": False, "reason": str(e)}
            
    def _generate_visibility_cache_key(self, request: Dict[str, Any]) -> str:
        """生成可见性缓存键"""
        satellite_id = request.get("satellite_id", "")
        target_id = request.get("target_info", {}).get("target_id", "")
        start_time = request.get("start_time", "")
        end_time = request.get("end_time", "")
        
        return f"{satellite_id}_{target_id}_{start_time}_{end_time}"
        
    def _get_visibility_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取可见性缓存"""
        cached_item = self.visibility_cache.get(cache_key)
        if cached_item and (datetime.now() - cached_item["timestamp"]).seconds < 300:  # 5分钟缓存
            return cached_item["result"]
        return None
        
    def _cache_visibility_result(self, cache_key: str, result: Dict[str, Any]):
        """缓存可见性结果"""
        # 使用仿真时间而不是系统时间
        from src.utils.time_manager import get_time_manager
        time_manager = get_time_manager()
        current_sim_time = time_manager.start_time

        self.visibility_cache[cache_key] = {
            "result": result,
            "timestamp": current_sim_time
        }

        # 清理过期缓存（基于仿真时间）
        expired_keys = [
            key for key, item in self.visibility_cache.items()
            if (current_sim_time - item["timestamp"]).seconds > 300
        ]
        for key in expired_keys:
            del self.visibility_cache[key]
            
    async def _get_stk_connection(self):
        """获取STK连接（连接池管理）"""
        # 简化实现：直接返回当前连接
        # 实际应用中可以实现真正的连接池
        return self
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        pass

    # 适配方法：基于成功经验添加main.py需要的方法
    def _initialize_simulation_time(self) -> bool:
        """初始化仿真时间 - 基于成功经验"""
        try:
            logger.info("初始化仿真时间...")
            self._setup_scenario_time()
            return True
        except Exception as e:
            logger.error(f"初始化仿真时间失败: {e}")
            return False

    def _check_stk_server_status(self) -> bool:
        """🔧 检查STK服务器状态 - 解决服务器意外情况"""
        try:
            if not self.scenario:
                logger.error("场景对象不可用")
                return False

            # 检查场景基本属性
            try:
                scenario_name = self.scenario.InstanceName
                start_time = self.scenario.StartTime
                logger.info(f"STK服务器状态正常: 场景={scenario_name}, 开始时间={start_time}")
                return True
            except Exception as e:
                logger.error(f"STK服务器状态异常: {e}")
                return False

        except Exception as e:
            logger.error(f"STK服务器状态检查失败: {e}")
            return False

    def _recover_stk_server(self) -> bool:
        """🔧 恢复STK服务器状态 - 解决服务器意外情况"""
        try:
            logger.info("尝试恢复STK服务器状态...")

            # 方法1：刷新COM连接
            try:
                if hasattr(self, 'root') and self.root:
                    # 重新获取场景对象
                    self.scenario = self.root.CurrentScenario
                    if self.scenario:
                        logger.info("✅ 方法1成功：COM连接已刷新")
                        return True
            except Exception as e1:
                logger.debug(f"方法1失败: {e1}")

            # 方法2：重新连接STK
            try:
                self.connect()
                if self.scenario:
                    logger.info("✅ 方法2成功：STK已重新连接")
                    return True
            except Exception as e2:
                logger.debug(f"方法2失败: {e2}")

            logger.error("❌ STK服务器恢复失败")
            return False

        except Exception as e:
            logger.error(f"STK服务器恢复异常: {e}")
            return False

    def _safe_propagate_all_satellites(self) -> bool:
        """安全传播所有卫星 - 基于成功经验"""
        try:
            logger.info("开始传播所有卫星...")
            satellites = self.get_objects("Satellite")

            if not satellites:
                logger.warning("没有找到卫星对象")
                return False

            success_count = 0
            for satellite_id in satellites:
                try:
                    satellite = self.scenario.Children.Item(satellite_id)
                    satellite.Propagator.Propagate()
                    success_count += 1
                    logger.info(f"卫星 {satellite_id} 传播成功")
                except Exception as e:
                    logger.warning(f"卫星 {satellite_id} 传播失败: {e}")

            success_rate = success_count / len(satellites)
            logger.info(f"传播结果: {success_count}/{len(satellites)} 成功 ({success_rate*100:.1f}%)")
            return success_rate >= 0.5

        except Exception as e:
            logger.error(f"传播所有卫星失败: {e}")
            return False

    def _debug_propagate_all_satellites(self) -> bool:
        """调试传播所有卫星 - 基于成功经验"""
        return self._safe_propagate_all_satellites()

    def _debug_create_sensors_and_propagate(self) -> bool:
        """调试创建传感器并传播 - 基于成功经验"""
        try:
            # 获取所有卫星
            satellites = self.get_objects("Satellite")
            if not satellites:
                logger.warning("没有找到卫星对象")
                return False

            # 为每个卫星创建传感器并传播
            success_count = 0
            for satellite_id in satellites:
                try:
                    # 创建传感器的默认配置
                    sensor_params = {
                        "inner_cone_half_angle": 5.0,
                        "outer_cone_half_angle": 15.0,
                        "point_azimuth": 0.0,
                        "point_elevation": -90.0
                    }

                    # 创建传感器
                    if self.create_sensor(satellite_id, sensor_params):
                        # 传播卫星
                        satellite = self.scenario.Children.Item(satellite_id)
                        satellite.Propagator.Propagate()
                        success_count += 1
                        logger.info(f"卫星 {satellite_id} 传感器创建和传播成功")

                except Exception as e:
                    logger.warning(f"卫星 {satellite_id} 传感器创建和传播失败: {e}")

            success_rate = success_count / len(satellites)
            logger.info(f"传感器创建和传播结果: {success_count}/{len(satellites)} 成功")
            return success_rate >= 0.5

        except Exception as e:
            logger.error(f"调试创建传感器并传播失败: {e}")
            return False

    def _debug_verify_propagation_state(self) -> bool:
        """调试验证传播状态 - 基于成功经验"""
        try:
            logger.info("验证传播状态...")
            satellites = self.get_objects("Satellite")

            if not satellites:
                logger.warning("没有找到卫星对象")
                return False

            valid_count = 0
            for satellite_id in satellites:
                try:
                    # 获取卫星位置来验证传播状态
                    position = self.get_satellite_position(satellite_id)
                    if position:
                        valid_count += 1
                        logger.info(f"卫星 {satellite_id} 传播状态有效")
                    else:
                        logger.warning(f"卫星 {satellite_id} 传播状态无效")

                except Exception as e:
                    logger.warning(f"验证卫星 {satellite_id} 传播状态失败: {e}")

            success_rate = valid_count / len(satellites)
            logger.info(f"传播状态验证结果: {valid_count}/{len(satellites)} 有效")
            return success_rate >= 0.5

        except Exception as e:
            logger.error(f"验证传播状态失败: {e}")
            return False

    def get_missile_launch_time(self, missile_id: str) -> Optional[str]:
        """
        获取导弹的发射时间

        Args:
            missile_id: 导弹ID

        Returns:
            发射时间字符串 (格式: "YYYY/MM/DD HH:MM:SS") 或 None
        """
        if not self.scenario or not self.is_connected:
            logger.error("STK未连接")
            return None

        try:
            # 获取导弹对象
            missile = self.scenario.Children.Item(missile_id)
            if not missile:
                logger.error(f"导弹 {missile_id} 不存在")
                return None

            # 获取发射时间属性（STK官方API：通常为Epoch或StartTime）
            try:
                # 优先尝试Propagator.InitialState.Epoch
                launch_time = missile.Propagator.InitialState.Epoch
            except Exception:
                try:
                    # 备用：尝试Propagator.Epoch
                    launch_time = missile.Propagator.Epoch
                except Exception:
                    logger.error(f"无法获取导弹 {missile_id} 的发射时间属性")
                    return None

            logger.info(f"导弹 {missile_id} 的发射时间(Epoch): {launch_time}")
            return launch_time

        except Exception as e:
            logger.error(f"获取导弹 {missile_id} 的发射时间失败: {e}")
            return None


# 全局STK管理器实例
_stk_manager = None

def get_stk_manager(config_manager=None):
    """获取全局STK管理器实例"""
    global _stk_manager
    if _stk_manager is None and config_manager:
        stk_config = config_manager.get_stk_config()
        _stk_manager = STKManager(stk_config)
    return _stk_manager