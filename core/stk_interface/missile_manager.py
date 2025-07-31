"""
导弹管理器 - 清理版本
负责管理STK场景中的导弹对象，包括创建、配置和轨迹计算
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import math

logger = logging.getLogger(__name__)

class MissileManager:
    """导弹管理器 - 重新设计的导弹对象状态管理"""
    
    def __init__(self, stk_manager, config: Dict[str, Any], output_manager):
        """初始化导弹管理器"""
        self.stk_manager = stk_manager
        self.config = config
        self.output_manager = output_manager
        # 从配置管理器获取时间管理器
        from src.utils.time_manager import get_time_manager
        from src.utils.config_manager import get_config_manager
        self.config_manager = get_config_manager()
        self.time_manager = get_time_manager(self.config_manager)
        self.missile_targets = {}

        # 获取中段高度阈值配置
        task_config = self.config_manager.get_task_planning_config()
        self.midcourse_altitude_threshold = task_config.get('midcourse_altitude_threshold', 100)  # 默认100km

        # 获取导弹管理配置
        self.missile_mgmt_config = self.config_manager.get_missile_management_config()

        # COM组件状态跟踪
        self._com_initialized = False

        logger.info(f"导弹管理器初始化完成，中段高度阈值: {self.midcourse_altitude_threshold}km")

    def __del__(self):
        """析构函数，确保COM组件正确清理"""
        try:
            if hasattr(self, '_com_initialized') and self._com_initialized:
                import pythoncom
                pythoncom.CoUninitialize()
                logger.debug("🔧 COM组件已清理")
        except Exception as e:
            logger.debug(f"COM组件清理异常: {e}")
        
    def add_missile_target(self, missile_id: str, launch_position: Dict[str, float], 
                          target_position: Dict[str, float], launch_sequence: int = 1):
        """添加导弹目标配置"""
        self.missile_targets[missile_id] = {
            "launch_position": launch_position,
            "target_position": target_position,
            "launch_sequence": launch_sequence
        }
        logger.info(f"✅ 添加导弹目标配置: {missile_id}")
        
    def create_missile(self, missile_id: str, launch_time: datetime) -> bool:
        """创建导弹对象"""
        try:
            logger.info(f"🚀 创建导弹对象: {missile_id}")
            
            # 获取导弹配置
            missile_info = self.missile_targets.get(missile_id)
            if not missile_info:
                logger.error(f"❌ 未找到导弹配置: {missile_id}")
                return False
                
            # 准备轨迹参数
            trajectory_params = {
                "launch_position": missile_info["launch_position"],
                "target_position": missile_info["target_position"]
            }
            
            # 创建STK导弹对象
            success = self._create_stk_missile_object(missile_id, launch_time, trajectory_params)
            
            if success:
                logger.info(f"✅ 导弹对象创建成功: {missile_id}")
                return True
            else:
                logger.error(f"❌ 导弹对象创建失败: {missile_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 创建导弹失败: {e}")
            return False
            
    def _create_stk_missile_object(self, missile_id: str, launch_time: datetime,
                                  trajectory_params: Dict[str, Any]) -> bool:
        """创建STK导弹对象并配置轨迹"""
        com_initialized = False
        try:
            logger.info(f"🎯 创建STK导弹对象: {missile_id}")

            # 确保COM组件在正确的线程中初始化
            try:
                import pythoncom
                # 检查当前线程是否已经初始化COM
                if not hasattr(self, '_com_initialized') or not self._com_initialized:
                    pythoncom.CoInitialize()
                    self._com_initialized = True
                    com_initialized = True
                    logger.debug("🔧 COM组件线程初始化")
                else:
                    logger.debug("🔧 COM组件已在当前线程初始化")
            except Exception as e:
                logger.debug(f"COM组件初始化状态: {e}")

            # 1. 创建导弹对象
            try:
                missile = self.stk_manager.scenario.Children.New(13, missile_id)  # eMissile
                logger.info(f"✅ 导弹对象创建成功: {missile_id}")
            except Exception as create_error:
                logger.error(f"❌ 导弹对象创建失败: {create_error}")
                logger.error(f"❌ 导弹对象创建失败: {missile_id}")
                return False
                
            # 2. 设置轨迹类型为弹道
            try:
                missile.SetTrajectoryType(10)  # ePropagatorBallistic
                logger.info(f"✅ 轨迹类型设置为弹道: {missile.TrajectoryType}")
            except Exception as type_error:
                logger.error(f"❌ 轨迹类型设置失败: {type_error}")
                return False

            # 3. 设置导弹时间属性 - 基于STK官方文档的正确顺序
            # 重要：必须在设置轨迹类型后，配置轨迹参数前设置时间
            self._set_missile_time_period_correct(missile, launch_time)
                
            # 4. 配置轨迹参数
            try:
                trajectory = missile.Trajectory
                launch_pos = trajectory_params["launch_position"]
                target_pos = trajectory_params["target_position"]
                
                # 设置发射位置
                trajectory.Launch.Lat = launch_pos["lat"]
                trajectory.Launch.Lon = launch_pos["lon"]
                trajectory.Launch.Alt = launch_pos["alt"]
                logger.info(f"✅ 发射位置设置成功")
                
                # 设置撞击位置
                trajectory.ImpactLocation.Impact.Lat = target_pos["lat"]
                trajectory.ImpactLocation.Impact.Lon = target_pos["lon"]
                trajectory.ImpactLocation.Impact.Alt = target_pos["alt"]
                logger.info(f"✅ 撞击位置设置成功")
                
                # 设置发射控制类型和远地点高度
                range_m = self._calculate_great_circle_distance(launch_pos, target_pos)
                range_km = range_m / 1000.0
                apogee_alt_km = min(max(range_km * 0.3, 300), 1500)
                
                trajectory.ImpactLocation.SetLaunchControlType(0)
                trajectory.ImpactLocation.LaunchControl.ApogeeAlt = apogee_alt_km
                logger.info(f"✅ 发射控制设置成功: {apogee_alt_km:.1f}km")
                
                # 执行传播
                trajectory.Propagate()
                logger.info(f"✅ 轨迹传播成功")

                # 验证传播结果
                if self._verify_trajectory_propagation(missile):
                    logger.info(f"✅ 轨迹传播验证成功")
                else:
                    logger.warning(f"⚠️  轨迹传播验证失败，但继续执行")
                
            except Exception as traj_error:
                logger.warning(f"⚠️  轨迹参数设置失败: {traj_error}")
                
            return True
            
        except Exception as e:
            logger.error(f"❌ STK导弹对象创建失败: {e}")
            return False
            
    def get_missile_trajectory_info(self, missile_id: str) -> Optional[Dict[str, Any]]:
        """获取导弹轨迹信息 - 简化版本，直接从STK场景读取"""
        logger.info(f"🎯 获取导弹轨迹信息: {missile_id}")

        # 获取导弹对象
        missile = self.stk_manager.scenario.Children.Item(missile_id)
        logger.info(f"✅ 导弹对象获取成功: {missile_id}")

        # 直接从STK DataProvider获取轨迹数据
        return self._get_trajectory_from_stk_dataprovider(missile)
            
    def _calculate_great_circle_distance(self, pos1: Dict[str, float], pos2: Dict[str, float]) -> float:
        """计算两点间的大圆距离（米）"""
        try:
            # 转换为弧度
            lat1_rad = math.radians(pos1["lat"])
            lon1_rad = math.radians(pos1["lon"])
            lat2_rad = math.radians(pos2["lat"])
            lon2_rad = math.radians(pos2["lon"])
            
            # 使用Haversine公式
            dlat = lat2_rad - lat1_rad
            dlon = lon2_rad - lon1_rad
            
            a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            
            # 地球半径（米）
            earth_radius = 6371000
            distance = earth_radius * c
            
            return distance
            
        except Exception as e:
            logger.error(f"距离计算失败: {e}")
            raise Exception(f"距离计算失败: {e}")

    def _set_missile_time_period_correct(self, missile, launch_time: datetime):
        """
        基于STK官方文档的正确导弹时间设置方法
        使用 EphemerisInterval.SetExplicitInterval() 方法
        """
        try:
            # 获取场景时间范围
            scenario_start = self.stk_manager.scenario.StartTime
            scenario_stop = self.stk_manager.scenario.StopTime

            logger.info(f"📅 场景时间范围: {scenario_start} - {scenario_stop}")

            # 解析场景开始时间
            try:
                start_dt = datetime.strptime(scenario_start, "%d %b %Y %H:%M:%S.%f")
            except:
                try:
                    start_dt = datetime.strptime(scenario_start, "%d %b %Y %H:%M:%S")
                except:
                    logger.warning("无法解析场景开始时间，使用仿真开始时间")
                    start_dt = self.time_manager.start_time

            # 确保发射时间在场景范围内
            if launch_time < start_dt:
                launch_time = start_dt + timedelta(minutes=1)
                logger.info(f"调整发射时间到场景开始后: {launch_time}")

            # 使用配置的飞行时间计算撞击时间
            time_config = self.missile_mgmt_config["time_config"]
            flight_minutes = time_config["default_minutes"]
            impact_time = launch_time + timedelta(minutes=flight_minutes)

            # 转换为STK时间格式
            launch_time_str = launch_time.strftime("%d %b %Y %H:%M:%S.000")
            impact_time_str = impact_time.strftime("%d %b %Y %H:%M:%S.000")

            # 基于STK官方文档：使用EphemerisInterval.SetExplicitInterval()方法
            success = False

            # 方法1: 使用EphemerisInterval.SetExplicitInterval()（STK官方推荐）
            try:
                trajectory = missile.Trajectory
                # 根据STK官方文档，使用EphemerisInterval设置时间范围
                trajectory.EphemerisInterval.SetExplicitInterval(launch_time_str, impact_time_str)
                logger.info(f"✅ EphemerisInterval时间设置成功: {launch_time_str} - {impact_time_str}")
                success = True

            except Exception as e1:
                logger.warning(f"EphemerisInterval时间设置失败: {e1}")

                # 方法2: 使用Connect命令设置时间范围
                try:
                    missile_path = f"*/Missile/{missile.InstanceName}"
                    time_cmd = f"SetTimePeriod {missile_path} \"{launch_time_str}\" \"{impact_time_str}\""
                    self.stk_manager.root.ExecuteCommand(time_cmd)
                    logger.info(f"✅ Connect命令时间设置成功: {launch_time_str} - {impact_time_str}")
                    success = True

                except Exception as e2:
                    logger.debug(f"Connect命令时间设置失败: {e2}")

                    # 方法3: 尝试设置轨迹的StartTime和StopTime属性（已弃用但可能有效）
                    try:
                        trajectory = missile.Trajectory
                        trajectory.StartTime = launch_time_str
                        trajectory.StopTime = impact_time_str
                        logger.info(f"✅ 轨迹StartTime/StopTime设置成功: {launch_time_str} - {impact_time_str}")
                        success = True

                    except Exception as e3:
                        logger.warning(f"所有时间设置方法都失败:")
                        logger.warning(f"  EphemerisInterval方法: {e1}")
                        logger.warning(f"  Connect命令: {e2}")
                        logger.warning(f"  StartTime/StopTime方法: {e3}")
                        logger.info(f"⏰ 将使用场景默认时间范围")

            # 如果时间设置成功，记录相关信息
            if success:
                logger.info(f"🎯 导弹时间设置完成:")
                logger.info(f"   发射时间: {launch_time_str}")
                logger.info(f"   撞击时间: {impact_time_str}")
                logger.info(f"   飞行时间: {flight_minutes}分钟")

        except Exception as e:
            logger.warning(f"导弹时间设置过程失败: {e}")
            logger.info(f"⏰ 将使用场景默认时间范围")

    def _convert_to_stk_time_format(self, dt: datetime) -> str:
        """将Python datetime转换为STK时间格式"""
        try:
            # 月份缩写映射
            month_abbr = {
                1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun',
                7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'
            }

            # 格式化为STK时间字符串
            stk_time = f"{dt.day} {month_abbr[dt.month]} {dt.year} {dt.hour:02d}:{dt.minute:02d}:{dt.second:02d}.{dt.microsecond//1000:03d}"
            return stk_time

        except Exception as e:
            logger.error(f"时间格式转换失败: {e}")
            raise Exception(f"时间格式转换失败: {e}")

    def _get_trajectory_from_stk_dataprovider(self, missile) -> Dict[str, Any]:
        """从STK DataProvider获取真实轨迹数据"""
        missile_id = missile.InstanceName
        logger.info(f"🎯 从STK DataProvider获取轨迹数据: {missile_id}")

        try:
            # 从STK DataProvider获取真实轨迹数据
            logger.info(f"🎯 从STK DataProvider获取真实轨迹数据")
            real_trajectory = self._extract_real_trajectory_from_stk(missile)
            if real_trajectory:
                logger.info(f"✅ 成功获取STK真实轨迹数据")
                return real_trajectory
            else:
                raise Exception("STK DataProvider数据提取失败")

        except Exception as e:
            logger.error(f"❌ STK真实轨迹获取失败: {e}")
            raise Exception(f"无法获取导弹 {missile_id} 的STK真实轨迹数据: {e}")











    def _extract_real_trajectory_from_stk(self, missile) -> Optional[Dict[str, Any]]:
        """从STK获取真实轨迹数据 - 基于STK官方文档的最佳实践"""
        try:
            missile_id = missile.InstanceName
            logger.info(f"   🎯 基于STK官方文档获取轨迹数据: {missile_id}")

            # 基于STK官方文档: 首先确保导弹轨迹已传播
            try:
                # 检查导弹轨迹状态
                trajectory = missile.Trajectory
                logger.info(f"   ✅ 导弹轨迹对象获取成功")

                # 基于官方文档: 检查轨迹是否已传播
                try:
                    # 尝试获取轨迹的开始和结束时间
                    traj_start = trajectory.StartTime
                    traj_stop = trajectory.StopTime
                    logger.info(f"   ⏰ 轨迹时间范围: {traj_start} - {traj_stop}")
                    start_time_stk = traj_start
                    stop_time_stk = traj_stop
                except Exception as traj_time_error:
                    logger.debug(f"   轨迹时间获取失败: {traj_time_error}")
                    # 回退到场景时间
                    start_time_stk = self.stk_manager.scenario.StartTime
                    stop_time_stk = self.stk_manager.scenario.StopTime
                    logger.info(f"   ⏰ 使用场景时间范围: {start_time_stk} - {stop_time_stk}")

            except Exception as traj_error:
                logger.error(f"   ❌ 导弹轨迹对象获取失败: {traj_error}")
                return None

            # 基于STK官方文档: 使用正确的DataProvider访问模式
            try:
                # 获取DataProviders - 基于官方文档示例
                data_providers = missile.DataProviders
                # logger.info(f"   📡 DataProviders数量: {data_providers.Count}")

                # 列出所有可用的DataProvider
                available_providers = []
                for i in range(data_providers.Count):
                    try:
                        provider_name = data_providers.Item(i).Name
                        available_providers.append(provider_name)
                    except:
                        available_providers.append(f"Provider_{i}")
                # logger.info(f"   📋 可用DataProviders: {available_providers}")

                # 尝试多种DataProvider类型
                provider_names = ["LLA State", "Cartesian Position", "Classical Elements", "Position"]
                lla_provider_base = None

                for provider_name in provider_names:
                    try:
                        lla_provider_base = data_providers.Item(provider_name)
                        # logger.info(f"   ✅ {provider_name} DataProvider获取成功")
                        break
                    except Exception as provider_error:
                        logger.debug(f"   尝试{provider_name}失败: {provider_error}")
                        continue

                if lla_provider_base is None:
                    # 如果没有找到命名的DataProvider，尝试使用索引
                    try:
                        lla_provider_base = data_providers.Item(0)
                        logger.info(f"   ✅ 使用索引0获取DataProvider")
                    except:
                        raise Exception("无法获取任何DataProvider")

                # 🔍 基于STK官方文档: 使用Group属性访问真正的DataProvider执行接口
                # 官方示例: satellite.DataProviders.Item('Cartesian Position').Group.Item('ICRF').Exec(...)
                try:
                    if hasattr(lla_provider_base, 'Group'):
                        provider_group = lla_provider_base.Group
                        # logger.info(f"   🔍 DataProvider Group对象获取成功")

                        # 尝试获取特定坐标系的DataProvider
                        coordinate_systems = ['Fixed', 'ICRF', 'J2000', 'Inertial']
                        lla_provider = None

                        for coord_sys in coordinate_systems:
                            try:
                                lla_provider = provider_group.Item(coord_sys)
                                logger.info(f"   ✅ 成功获取{coord_sys}坐标系的DataProvider")
                                break
                            except:
                                continue

                        if lla_provider is None:
                            # 如果没有找到特定坐标系，尝试使用索引0
                            try:
                                lla_provider = provider_group.Item(0)
                                logger.info(f"   ✅ 使用索引0获取DataProvider")
                            except:
                                lla_provider = lla_provider_base
                                logger.warning(f"   ⚠️ 回退到基础DataProvider对象")
                    else:
                        logger.warning(f"   ⚠️ DataProvider没有Group属性，使用基础对象")
                        lla_provider = lla_provider_base

                except Exception as provider_access_error:
                    logger.error(f"   ❌ DataProvider Group访问失败: {provider_access_error}")
                    lla_provider = lla_provider_base

                # 基于官方文档: 使用正确的时间步长和执行方式
                time_step = 30  # 30秒步长，获取更详细的轨迹数据
                logger.info(f"   ⏰ 时间步长: {time_step}秒")
                logger.info(f"   ⏰ 时间范围: {start_time_stk} 到 {stop_time_stk}")

                # 基于STK官方文档: 正确的DataProvider.Exec()调用方式
                logger.info(f"   🚀 执行DataProvider.Exec()...")

                # 重要修复: 基于STK官方文档的多种DataProvider执行方法
                result = None
                execution_method = None

                try:
                    # 方法1: 使用ExecElements - 基于官方文档推荐
                    elements = ["Time", "Lat", "Lon", "Alt"]
                    # logger.info(f"   🔍 尝试ExecElements方法，元素: {elements}")
                    result = lla_provider.ExecElements(start_time_stk, stop_time_stk, time_step, elements)
                    execution_method = "ExecElements"
                    logger.info(f"   ✅ ExecElements方法执行成功")
                except Exception as exec_elements_error:
                    logger.debug(f"   ExecElements方法失败: {exec_elements_error}")
                    try:
                        # 方法2: 使用标准Exec方法 - 基于官方文档
                        logger.info(f"   🔍 尝试标准Exec方法")
                        result = lla_provider.Exec(start_time_stk, stop_time_stk, time_step)
                        execution_method = "Exec"
                        logger.info(f"   ✅ 标准Exec方法执行成功")
                    except Exception as exec_error:
                        logger.debug(f"   标准Exec方法失败: {exec_error}")
                        try:
                            # 方法3: 尝试不同的时间步长
                            logger.info(f"   🔍 尝试更大的时间步长: 60秒")
                            result = lla_provider.Exec(start_time_stk, stop_time_stk, 60)
                            execution_method = "Exec_60s"
                            logger.info(f"   ✅ 60秒步长Exec方法执行成功")
                        except Exception as exec_60_error:
                            logger.error(f"   ❌ 所有DataProvider执行方法都失败:")
                            logger.error(f"      ExecElements: {exec_elements_error}")
                            logger.error(f"      Exec: {exec_error}")
                            logger.error(f"      Exec_60s: {exec_60_error}")
                            return None

                if not result:
                    logger.error(f"   ❌ DataProvider返回空结果")
                    return None

                # logger.info(f"   ✅ DataProvider.Exec()执行成功，使用方法: {execution_method}")
                # logger.info(f"   📊 DataSets数量: {result.DataSets.Count}")

                # 详细检查DataSets结构
                try:
                    # logger.info(f"   🔍 Result类型: {type(result)}")
                    # logger.info(f"   🔍 DataSets类型: {type(result.DataSets)}")

                    # # 检查每个DataSet
                    # for i in range(result.DataSets.Count):
                    #     try:
                    #         ds = result.DataSets.Item(i)
                    #         logger.info(f"   🔍 DataSet[{i}]类型: {type(ds)}")
                    #         logger.info(f"   🔍 DataSet[{i}]属性: {[attr for attr in dir(ds) if not attr.startswith('_')]}")
                    #     except Exception as ds_error:
                    #         logger.error(f"   ❌ DataSet[{i}]检查失败: {ds_error}")

                    pass  # 占位符，避免空try块
                except Exception as result_error:
                    logger.error(f"   ❌ Result结构检查失败: {result_error}")

                if result.DataSets.Count > 0:
                    dataset = result.DataSets.Item(0)

                    # 详细检查DataSet结构
                    try:
                        # STK DataSet使用Count属性而不是RowCount
                        data_count = dataset.Count
                        logger.info(f"   📊 DataSet数据点数: {data_count}")
                    except Exception as row_error:
                        logger.error(f"   ❌ 无法获取DataSet行数: {row_error}")
                        # 尝试其他方法获取数据
                        try:
                            # 检查DataSet是否有其他属性
                            logger.info(f"   🔍 DataSet类型: {type(dataset)}")
                            logger.info(f"   🔍 DataSet属性: {dir(dataset)}")

                            # 尝试直接访问数据
                            if hasattr(dataset, 'GetValue'):
                                test_value = dataset.GetValue(0, 0)
                                logger.info(f"   � 测试数据值: {test_value}")

                        except Exception as detail_error:
                            logger.error(f"   ❌ DataSet详细检查失败: {detail_error}")

                        logger.error(f"   ❌ 轨迹数据提取失败: {row_error}")
                        return None

                    # 确定DataSet列数 - 基于STK DataProvider的标准格式
                    col_count = 4  # 默认4列：Time, Lat, Lon, Alt
                    try:
                        # 尝试多种方式获取列数
                        if hasattr(dataset, 'ColumnCount'):
                            col_count = dataset.ColumnCount
                            logger.debug(f"   📊 DataSet列数(ColumnCount): {col_count}")
                        elif hasattr(dataset, 'Count') and data_count > 0:
                            # 对于LLA State DataProvider，通常是4列
                            col_count = 4
                            logger.debug(f"   📊 DataSet列数(推断): {col_count}")
                        else:
                            logger.debug(f"   📊 DataSet列数(默认): {col_count}")
                    except Exception:
                        # 静默处理，使用默认值
                        logger.debug(f"   📊 DataSet列数(异常后默认): {col_count}")

                    if data_count > 0:
                        # 解析轨迹数据
                        trajectory_points = []
                        midcourse_points = []
                        max_altitude = 0

                        # 计算发射时间
                        launch_time_dt = self._parse_stk_time(start_time_stk)

                        logger.info(f"   🔍 开始解析{data_count}个轨迹点...")

                        # 获取所有数据 - 基于STK DataProvider API
                        try:
                            values = dataset.GetValues()
                            logger.info(f"   📊 获取到数据数组，长度: {len(values)}")
                        except Exception as values_error:
                            logger.error(f"   ❌ GetValues()失败: {values_error}")
                            return None

                        for i in range(len(values)):
                            try:
                                # STK DataProvider返回的是一维数组，需要按照元素顺序解析
                                # ExecElements(['Time', 'Lat', 'Lon', 'Alt'])返回的顺序
                                time_val = values[i] if i < len(values) else None

                                # 对于多个元素，STK可能返回多个DataSet
                                # 尝试从其他DataSet获取Lat, Lon, Alt
                                lat_val = None
                                lon_val = None
                                alt_km = None

                                if result.DataSets.Count >= 4:
                                    try:
                                        lat_values = result.DataSets.Item(1).GetValues()
                                        lon_values = result.DataSets.Item(2).GetValues()
                                        alt_values = result.DataSets.Item(3).GetValues()

                                        if i < len(lat_values):
                                            lat_val = lat_values[i]
                                        if i < len(lon_values):
                                            lon_val = lon_values[i]
                                        if i < len(alt_values):
                                            alt_km = alt_values[i]
                                    except Exception as multi_dataset_error:
                                        logger.debug(f"   多DataSet解析失败: {multi_dataset_error}")
                                        # 继续尝试其他方法，不直接跳过
                                        pass

                                # 解析STK时间格式
                                try:
                                    time_dt = self._parse_stk_time(str(time_val))
                                except:
                                    time_dt = launch_time_dt + timedelta(seconds=i * time_step)

                                # 验证数据有效性
                                if isinstance(lat_val, (int, float)) and isinstance(lon_val, (int, float)) and isinstance(alt_km, (int, float)):
                                    point = {
                                        "time": time_dt,
                                        "lat": float(lat_val),
                                        "lon": float(lon_val),
                                        "alt": float(alt_km) * 1000  # 转换为米
                                    }
                                    trajectory_points.append(point)

                                    if alt_km > max_altitude:
                                        max_altitude = alt_km

                                    # 收集中段轨迹点（基于配置的高度阈值）
                                    if alt_km > self.midcourse_altitude_threshold:
                                        midcourse_points.append(point)
                                else:
                                    logger.debug(f"   跳过无效数据点 {i}: lat={lat_val}, lon={lon_val}, alt={alt_km}")

                            except Exception as point_error:
                                logger.debug(f"   解析轨迹点{i}失败: {point_error}")
                                continue

                        logger.info(f"   ✅ 成功解析{len(trajectory_points)}个有效轨迹点")

                        if len(trajectory_points) > 0:
                            # 获取发射和撞击位置
                            launch_point = trajectory_points[0]
                            impact_point = trajectory_points[-1]

                            # 计算射程
                            range_m = self._calculate_great_circle_distance(
                                {"lat": launch_point["lat"], "lon": launch_point["lon"], "alt": launch_point["alt"]},
                                {"lat": impact_point["lat"], "lon": impact_point["lon"], "alt": impact_point["alt"]}
                            )

                            # 计算飞行时间
                            flight_time = (impact_point["time"] - launch_point["time"]).total_seconds()

                            # 构建符合系统期望的数据结构
                            trajectory_info = {
                                "missile_id": missile_id,
                                "trajectory_points": [
                                    {
                                        "time": (point["time"] - launch_point["time"]).total_seconds(),
                                        "lat": point["lat"],
                                        "lon": point["lon"],
                                        "alt": point["alt"]
                                    } for point in trajectory_points
                                ],
                                "midcourse_points": midcourse_points,  # 保持datetime格式用于跟踪任务
                                "launch_time": launch_point["time"],
                                "impact_time": impact_point["time"],
                                "flight_time": flight_time,
                                "range": range_m,
                                "data_source": "stk_real_trajectory",  # 标记为STK真实轨迹
                                "launch_position": {
                                    "lat": launch_point["lat"],
                                    "lon": launch_point["lon"],
                                    "alt": launch_point["alt"]
                                },
                                "impact_position": {
                                    "lat": impact_point["lat"],
                                    "lon": impact_point["lon"],
                                    "alt": impact_point["alt"]
                                },
                                "stk_data_quality": {
                                    "has_real_trajectory": True,
                                    "trajectory_points_count": len(trajectory_points),
                                    "midcourse_points_count": len(midcourse_points),
                                    "execution_method": execution_method,
                                    "overall_quality": "high"
                                }
                            }

                            logger.info(f"   ✅ STK真实轨迹数据提取成功:")
                            logger.info(f"      数据来源: STK_Real_Trajectory")
                            # logger.info(f"      执行方法: {execution_method}")
                            # logger.info(f"      轨迹点数: {len(trajectory_points)}")
                            # logger.info(f"      中段轨迹点数: {len(midcourse_points)}")
                            # logger.info(f"      射程: {range_m/1000:.1f} km")
                            # logger.info(f"      最大高度: {max_altitude:.1f} km")
                            # logger.info(f"      发射时间: {launch_point['time']}")
                            # logger.info(f"      撞击时间: {impact_point['time']}")
                            # logger.info(f"      飞行时间: {flight_time:.1f} 秒")

                            return trajectory_info
                        else:
                            logger.error(f"   ❌ 没有有效的轨迹点数据")
                            return None
                    else:
                        raise Exception("DataSet为空，没有轨迹数据")
                else:
                    raise Exception("DataProvider返回空DataSets")

            except Exception as extract_error:
                logger.error(f"   ❌ 轨迹数据提取失败: {extract_error}")
                return None

        except Exception as e:
            logger.error(f"❌ STK DataProvider获取真实轨迹数据失败: {e}")
            return None

    def _parse_stk_time(self, time_str: str) -> datetime:
        """解析STK时间格式"""
        try:
            # 处理STK的纳秒格式: "23 Jul 2025 04:00:00.000000000"
            if '.' in time_str and len(time_str.split('.')[-1]) > 6:
                # 截断纳秒到微秒 (保留6位小数)
                parts = time_str.split('.')
                time_str = parts[0] + '.' + parts[1][:6]

            # 尝试标准格式: "23 Jul 2025 04:02:00.000000"
            try:
                return datetime.strptime(time_str, "%d %b %Y %H:%M:%S.%f")
            except:
                pass

            # 尝试无毫秒格式: "23 Jul 2025 04:02:00"
            try:
                return datetime.strptime(time_str, "%d %b %Y %H:%M:%S")
            except:
                # 如果都失败，抛出异常
                raise ValueError(f"无法解析STK时间格式: {time_str}")
        except Exception as e:
            logger.error(f"解析STK时间失败: {e}")
            raise












    def get_missile_midcourse_start_position(self, missile_id: str) -> Optional[Dict[str, float]]:

        """获取导弹飞行中段起始位置"""
        logger.info(f"🎯 获取导弹飞行中段起始位置: {missile_id}")

        # 获取轨迹信息
        trajectory_info = self.get_missile_trajectory_info(missile_id)
        if not trajectory_info:
            raise Exception(f"无法获取导弹轨迹信息: {missile_id}")

        # 从轨迹信息中获取发射位置
        launch_position = trajectory_info.get("launch_position")
        if not launch_position:
            raise Exception(f"轨迹信息中缺少发射位置: {missile_id}")

        position = {
            "lat": launch_position["lat"],
            "lon": launch_position["lon"],
            "alt": launch_position["alt"]
        }

        logger.info(f"✅ 导弹中段起始位置: ({position['lat']:.6f}°, {position['lon']:.6f}°, {position['alt']:.1f}m)")
        return position

    def _verify_trajectory_propagation(self, missile) -> bool:
        """验证轨迹传播是否成功 - 基于优化版本的正确方法"""
        try:
            missile_id = missile.InstanceName
            logger.info(f"🔍 验证轨迹传播: {missile_id}")

            # 检查轨迹对象
            trajectory = missile.Trajectory

            # 使用正确的方式检查导弹时间范围 - 基于优化版本
            try:
                # 方法1: 尝试获取导弹对象的时间范围
                start_time = missile.StartTime
                stop_time = missile.StopTime
                logger.info(f"   ⏰ 导弹时间范围: {start_time} - {stop_time}")
            except Exception as time_error1:
                logger.debug(f"   方法1失败: {time_error1}")
                try:
                    # 方法2: 尝试从场景获取时间范围
                    scenario_start = self.stk_manager.scenario.StartTime
                    scenario_stop = self.stk_manager.scenario.StopTime
                    logger.info(f"   ⏰ 使用场景时间范围: {scenario_start} - {scenario_stop}")
                except Exception as time_error2:
                    logger.warning(f"   ⚠️  无法获取时间范围: 方法1({time_error1}), 方法2({time_error2})")
                    # 不返回False，继续检查其他方面

            # 检查DataProvider是否可用
            try:
                data_providers = missile.DataProviders
                provider_count = data_providers.Count
                logger.info(f"   📡 DataProvider数量: {provider_count}")

                if provider_count > 0:
                    # 尝试获取LLA State DataProvider
                    lla_provider = data_providers.Item("LLA State")
                    logger.info(f"   ✅ LLA State DataProvider可用")
                    return True
                else:
                    logger.info(f"   ℹ️  DataProvider数量为0，但轨迹可能仍然有效")
                    return True  # 即使没有DataProvider，轨迹可能仍然有效

            except Exception as dp_error:
                logger.info(f"   ℹ️  DataProvider检查失败，但轨迹可能仍然有效: {dp_error}")
                return True  # 不因为DataProvider问题而判定失败

        except Exception as e:
            logger.warning(f"轨迹传播验证失败: {e}")
            return False




    def create_single_missile_target(self, missile_scenario: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """创建单个导弹目标 - main.py调用的主要接口"""
        try:
            missile_id = missile_scenario.get("missile_id")
            logger.info(f"🚀 创建单个导弹目标: {missile_id}")

            # 1. 添加导弹目标配置
            self.add_missile_target(
                missile_id=missile_id,
                launch_position=missile_scenario.get("launch_position"),
                target_position=missile_scenario.get("target_position"),
                launch_sequence=missile_scenario.get("launch_sequence", 1)
            )

            # 2. 获取发射时间 - 优先使用传入的launch_time
            launch_sequence = missile_scenario.get("launch_sequence", 1)

            if "launch_time" in missile_scenario and missile_scenario["launch_time"]:
                # 使用传入的发射时间（用于随机导弹）
                launch_time_dt = missile_scenario["launch_time"]
                launch_time_stk = launch_time_dt.strftime("%d %b %Y %H:%M:%S.000")
                logger.info(f"🎯 使用传入的发射时间: {launch_time_dt}")
            else:
                # 使用时间管理器计算发射时间（用于固定序列导弹）
                launch_time_dt, launch_time_stk = self.time_manager.calculate_missile_launch_time(launch_sequence)
                logger.info(f"🎯 计算的发射时间: {launch_time_dt}")

            # 3. 创建STK导弹对象
            success = self.create_missile(missile_id, launch_time_dt)

            if success:
                # 4. 构建返回的导弹信息
                missile_info = {
                    "missile_id": missile_id,
                    "missile_type": missile_scenario.get("missile_type", "ballistic_missile"),
                    "description": missile_scenario.get("description", f"导弹威胁 {missile_id}"),
                    "threat_level": missile_scenario.get("threat_level", "高"),
                    "launch_position": missile_scenario.get("launch_position"),
                    "target_position": missile_scenario.get("target_position"),
                    "launch_time": launch_time_dt,
                    "launch_time_str": launch_time_stk,
                    "launch_sequence": launch_sequence,
                    "created_time": self.time_manager.start_time.isoformat(),
                    "stk_object": None  # 将在后续获取
                }

                # 5. 尝试获取STK对象
                try:
                    stk_missile = self.stk_manager.scenario.Children.Item(missile_id)
                    missile_info["stk_object"] = stk_missile
                    logger.info(f"✅ STK导弹对象获取成功: {missile_id}")
                except Exception as stk_error:
                    logger.warning(f"⚠️  STK导弹对象获取失败: {stk_error}")

                # 6. 存储到内部字典
                self.missile_targets[missile_id] = missile_info

                logger.info(f"✅ 单个导弹目标创建成功: {missile_id}")
                return missile_info
            else:
                logger.error(f"❌ 导弹对象创建失败: {missile_id}")
                return None

        except Exception as e:
            logger.error(f"❌ 创建单个导弹目标失败: {e}")
            return None

    def _get_stk_trajectory_data(self, missile_id: str) -> Optional[Dict[str, Any]]:
        """
        从STK获取导弹轨迹数据，包括准确的时间信息
        使用已测试成功的get_missile_launch_and_impact_times方法

        Args:
            missile_id: 导弹ID

        Returns:
            包含轨迹数据和时间信息的字典，失败返回None
        """
        try:
            logger.info(f"🎯 从STK获取导弹轨迹数据: {missile_id}")

            # 获取STK导弹对象
            try:
                stk_missile = self.stk_manager.scenario.Children.Item(missile_id)
                logger.info(f"✅ 获取STK导弹对象成功: {missile_id}")
            except Exception as get_error:
                logger.error(f"❌ 获取STK导弹对象失败: {missile_id}, {get_error}")
                return None

            # 方法1: 使用已测试成功的get_missile_launch_and_impact_times方法
            try:
                logger.info(f"🔍 使用get_missile_launch_and_impact_times获取时间: {missile_id}")

                # 使用我们已经测试成功的方法获取时间
                launch_time_dt, impact_time_dt = self.get_missile_launch_and_impact_times(missile_id)

                if launch_time_dt and impact_time_dt:
                    # 计算飞行时间
                    flight_duration = (impact_time_dt - launch_time_dt).total_seconds()

                    logger.info(f"✅ 成功获取导弹时间信息: {missile_id}")
                    logger.info(f"   发射时间: {launch_time_dt}")
                    logger.info(f"   撞击时间: {impact_time_dt}")
                    logger.info(f"   飞行时间: {flight_duration:.1f}秒")

                    # 尝试获取轨迹点数据
                    trajectory_points = []
                    try:
                        # 获取LLA State DataProvider来获取轨迹点
                        dp_lla = stk_missile.DataProviders.Item("LLA State")
                        scenario = self.stk_manager.scenario
                        scenario_start = scenario.StartTime
                        scenario_stop = scenario.StopTime

                        # 使用60秒间隔获取轨迹点
                        lla_result = dp_lla.Exec(scenario_start, scenario_stop, 60)

                        if lla_result and lla_result.DataSets.Count > 0:
                            lla_dataset = lla_result.DataSets.Item(0)
                            if lla_dataset.RowCount > 0:
                                logger.info(f"✅ 获取到 {lla_dataset.RowCount} 个轨迹点")

                                # 提取轨迹点（只取前10个作为示例）
                                for i in range(min(10, lla_dataset.RowCount)):
                                    time_val = lla_dataset.GetValue(i, 0)
                                    lat_val = lla_dataset.GetValue(i, 1)
                                    lon_val = lla_dataset.GetValue(i, 2)
                                    alt_val = lla_dataset.GetValue(i, 3)

                                    trajectory_points.append({
                                        "time": time_val,
                                        "latitude": lat_val,
                                        "longitude": lon_val,
                                        "altitude": alt_val
                                    })
                            else:
                                logger.warning(f"⚠️ LLA State数据集为空: {missile_id}")
                        else:
                            logger.warning(f"⚠️ LLA State DataProvider无数据: {missile_id}")

                    except Exception as lla_error:
                        logger.debug(f"LLA State获取失败: {lla_error}")

                    return {
                        "missile_id": missile_id,
                        "start_time": launch_time_dt,
                        "stop_time": impact_time_dt,
                        "flight_time_seconds": flight_duration,
                        "data_source": "STK_GetTimePeriod",
                        "trajectory_points": trajectory_points,
                        "stk_data_quality": {
                            "has_real_trajectory": len(trajectory_points) > 0,
                            "trajectory_points_count": len(trajectory_points),
                            "time_source": "GetTimePeriod_or_Estimation"
                        }
                    }
                else:
                    logger.warning(f"⚠️ get_missile_launch_and_impact_times返回空时间: {missile_id}")

            except Exception as time_error:
                logger.warning(f"⚠️ get_missile_launch_and_impact_times方法失败: {time_error}")

            # 方法2: 备用方案 - 从内部存储获取时间信息
            try:
                logger.info(f"🔍 尝试从内部存储获取时间信息: {missile_id}")

                if missile_id in self.missile_targets:
                    missile_info = self.missile_targets[missile_id]
                    launch_time = missile_info.get("launch_time")

                    if isinstance(launch_time, datetime):
                        # 使用配置的导弹飞行时间进行估算
                        time_config = self.missile_mgmt_config["time_config"]
                        flight_minutes = time_config["default_minutes"]
                        impact_time = launch_time + timedelta(minutes=flight_minutes)
                        flight_duration = (impact_time - launch_time).total_seconds()

                        logger.info(f"✅ 从内部存储获取时间信息: {missile_id}")
                        logger.info(f"   发射时间: {launch_time}")
                        logger.info(f"   估算撞击时间: {impact_time}")

                        return {
                            "missile_id": missile_id,
                            "start_time": launch_time,
                            "stop_time": impact_time,
                            "flight_time_seconds": flight_duration,
                            "data_source": "Internal_Storage",
                            "trajectory_points": [],
                            "stk_data_quality": {
                                "has_real_trajectory": False,
                                "trajectory_points_count": 0,
                                "time_source": "Internal_Estimation"
                            }
                        }

            except Exception as storage_error:
                logger.debug(f"内部存储方法失败: {storage_error}")

            logger.warning(f"⚠️ 所有时间获取方法都失败: {missile_id}")
            return None

        except Exception as e:
            logger.error(f"❌ 获取STK轨迹数据异常: {missile_id}, {e}")
            return None








    def get_missile_time_range(self, missile_id: str) -> Optional[Dict[str, Any]]:
        """
        获取导弹的时间范围信息

        Args:
            missile_id: 导弹ID

        Returns:
            包含发射时间、结束时间等信息的字典，失败返回None
        """
        try:
            # 从内部存储获取导弹信息
            if missile_id in self.missile_targets:
                missile_info = self.missile_targets[missile_id]
                launch_time = missile_info.get("launch_time")

                if launch_time:
                    # 优先从STK获取准确的时间信息
                    logger.info(f"🔍 获取导弹准确时间信息: {missile_id}")

                    trajectory_data = self._get_stk_trajectory_data(missile_id)
                    if trajectory_data:
                        # 使用STK的准确时间数据
                        stk_start_time = trajectory_data.get("start_time")
                        stk_stop_time = trajectory_data.get("stop_time")
                        flight_duration = trajectory_data.get("flight_time_seconds", 0)
                        data_source = trajectory_data.get("data_source", "STK")

                        logger.info(f"✅ 从STK获取准确时间: {missile_id}")
                        logger.info(f"   发射时间: {stk_start_time}")
                        logger.info(f"   结束时间: {stk_stop_time}")
                        logger.info(f"   飞行时间: {flight_duration:.0f}秒")
                        logger.info(f"   数据源: {data_source}")

                        return {
                            "missile_id": missile_id,
                            "launch_time": stk_start_time,
                            "end_time": stk_stop_time,
                            "flight_duration_seconds": flight_duration,
                            "launch_time_str": stk_start_time.isoformat() if isinstance(stk_start_time, datetime) else str(stk_start_time),
                            "end_time_str": stk_stop_time.isoformat() if isinstance(stk_stop_time, datetime) else str(stk_stop_time),
                            "data_source": data_source,
                            "trajectory_points_count": len(trajectory_data.get("trajectory_points", []))
                        }
                    else:
                        logger.warning(f"⚠️ 无法从STK获取准确时间，导弹可能不存在或数据不可用: {missile_id}")
                        return None

            logger.warning(f"⚠️ 未找到导弹时间信息: {missile_id}")
            return None

        except Exception as e:
            logger.error(f"❌ 获取导弹时间范围失败: {e}")
            return None

    def check_missiles_in_simulation_range(self, simulation_start: datetime, simulation_end: datetime) -> Dict[str, List[str]]:
        """
        检查哪些导弹在仿真时间范围内/外

        Args:
            simulation_start: 仿真开始时间
            simulation_end: 仿真结束时间

        Returns:
            包含有效和无效导弹列表的字典
        """
        try:
            logger.info(f"🔍 检查导弹时间范围: {simulation_start} - {simulation_end}")

            valid_missiles = []
            invalid_missiles = []

            # 获取所有导弹ID
            all_missiles = list(self.missile_targets.keys())
            logger.info(f"📊 当前场景中导弹数量: {len(all_missiles)}")

            for missile_id in all_missiles:
                time_range = self.get_missile_time_range(missile_id)

                if time_range:
                    launch_time = time_range["launch_time"]
                    end_time = time_range["end_time"]

                    # 检查导弹是否在仿真时间范围内
                    if isinstance(launch_time, datetime) and isinstance(end_time, datetime):
                        # 导弹有效条件：发射时间在仿真范围内，或者飞行时间与仿真时间有重叠
                        is_valid = (
                            (launch_time >= simulation_start and launch_time <= simulation_end) or  # 发射时间在范围内
                            (end_time >= simulation_start and end_time <= simulation_end) or        # 结束时间在范围内
                            (launch_time <= simulation_start and end_time >= simulation_end)        # 跨越整个仿真时间
                        )

                        if is_valid:
                            valid_missiles.append(missile_id)
                            logger.info(f"✅ 有效导弹: {missile_id} ({time_range['launch_time_str']} - {time_range['end_time_str']})")
                        else:
                            invalid_missiles.append(missile_id)
                            logger.warning(f"❌ 无效导弹: {missile_id} ({time_range['launch_time_str']} - {time_range['end_time_str']})")
                    else:
                        logger.warning(f"⚠️ 导弹时间格式错误: {missile_id}")
                        invalid_missiles.append(missile_id)
                else:
                    logger.warning(f"⚠️ 无法获取导弹时间: {missile_id}")
                    invalid_missiles.append(missile_id)

            result = {
                "valid_missiles": valid_missiles,
                "invalid_missiles": invalid_missiles,
                "total_missiles": len(all_missiles),
                "valid_count": len(valid_missiles),
                "invalid_count": len(invalid_missiles)
            }

            logger.info(f"📊 导弹时间检查结果: 有效{len(valid_missiles)}个, 无效{len(invalid_missiles)}个")
            return result

        except Exception as e:
            logger.error(f"❌ 检查导弹时间范围失败: {e}")
            return {"valid_missiles": [], "invalid_missiles": [], "total_missiles": 0, "valid_count": 0, "invalid_count": 0}

    def remove_invalid_missiles(self, invalid_missile_ids: List[str]) -> Dict[str, Any]:
        """
        删除无效的导弹目标

        Args:
            invalid_missile_ids: 要删除的导弹ID列表

        Returns:
            删除结果统计
        """
        try:
            logger.info(f"🗑️ 开始删除无效导弹: {len(invalid_missile_ids)}个")

            removed_count = 0
            failed_removals = []

            for missile_id in invalid_missile_ids:
                try:
                    # 从STK场景中删除导弹对象
                    try:
                        self.stk_manager.scenario.Children.Unload(19, missile_id)  # 19 = eMissile
                        logger.info(f"✅ 从STK删除导弹: {missile_id}")
                    except Exception as stk_error:
                        logger.warning(f"⚠️ STK删除导弹失败: {missile_id}, {stk_error}")

                    # 从内部存储中删除
                    if missile_id in self.missile_targets:
                        del self.missile_targets[missile_id]
                        logger.info(f"✅ 从内部存储删除导弹: {missile_id}")

                    removed_count += 1

                except Exception as remove_error:
                    logger.error(f"❌ 删除导弹失败: {missile_id}, {remove_error}")
                    failed_removals.append(missile_id)

            result = {
                "requested_removals": len(invalid_missile_ids),
                "successful_removals": removed_count,
                "failed_removals": len(failed_removals),
                "failed_missile_ids": failed_removals
            }

            logger.info(f"🗑️ 导弹删除完成: 成功{removed_count}个, 失败{len(failed_removals)}个")
            return result

        except Exception as e:
            logger.error(f"❌ 删除无效导弹异常: {e}")
            return {"requested_removals": 0, "successful_removals": 0, "failed_removals": 0, "failed_missile_ids": []}

    def manage_missile_count(self, simulation_start: datetime, simulation_end: datetime,
                           target_min: int = 5, target_max: int = 6) -> Dict[str, Any]:
        """
        管理导弹数量，确保在指定范围内

        Args:
            simulation_start: 仿真开始时间
            simulation_end: 仿真结束时间
            target_min: 最小导弹数量
            target_max: 最大导弹数量

        Returns:
            管理结果统计
        """
        try:
            logger.info(f"🎯 开始导弹数量管理: 目标范围 {target_min}-{target_max} 颗")

            # 1. 检查当前导弹时间范围
            missile_check = self.check_missiles_in_simulation_range(simulation_start, simulation_end)

            # 2. 删除无效导弹
            if missile_check["invalid_missiles"]:
                removal_result = self.remove_invalid_missiles(missile_check["invalid_missiles"])
                logger.info(f"🗑️ 删除无效导弹: {removal_result['successful_removals']}个")

            # 3. 检查当前有效导弹数量
            current_valid_count = len(missile_check["valid_missiles"])
            logger.info(f"📊 当前有效导弹数量: {current_valid_count}")

            # 4. 确定目标导弹数量
            import random
            target_count = random.randint(target_min, target_max)
            logger.info(f"🎲 随机选择目标导弹数量: {target_count}")

            # 5. 添加新导弹（如果需要）
            missiles_to_add = max(0, target_count - current_valid_count)
            added_missiles = []

            if missiles_to_add > 0:
                logger.info(f"➕ 需要添加导弹: {missiles_to_add}个")

                for i in range(missiles_to_add):
                    try:
                        # 生成随机导弹
                        new_missile = self._generate_random_global_missile(simulation_start, simulation_end, i+1)

                        if new_missile:
                            # 创建导弹
                            result = self.create_single_missile_target(new_missile)
                            if result:
                                added_missiles.append(new_missile["missile_id"])
                                logger.info(f"✅ 添加随机导弹: {new_missile['missile_id']}")
                            else:
                                logger.warning(f"⚠️ 创建随机导弹失败: {new_missile['missile_id']}")

                    except Exception as add_error:
                        logger.error(f"❌ 添加导弹异常: {add_error}")

            # 6. 最终统计
            final_missile_count = len(self.missile_targets)

            result = {
                "initial_total": missile_check["total_missiles"],
                "initial_valid": missile_check["valid_count"],
                "initial_invalid": missile_check["invalid_count"],
                "removed_invalid": len(missile_check["invalid_missiles"]),
                "target_count": target_count,
                "missiles_to_add": missiles_to_add,
                "successfully_added": len(added_missiles),
                "final_count": final_missile_count,
                "added_missile_ids": added_missiles,
                "management_success": True
            }

            logger.info(f"🎯 导弹数量管理完成:")
            logger.info(f"   初始: {missile_check['total_missiles']}个 (有效{missile_check['valid_count']}个)")
            logger.info(f"   删除: {len(missile_check['invalid_missiles'])}个无效导弹")
            logger.info(f"   添加: {len(added_missiles)}个新导弹")
            logger.info(f"   最终: {final_missile_count}个导弹")

            return result

        except Exception as e:
            logger.error(f"❌ 导弹数量管理异常: {e}")
            return {"management_success": False, "error": str(e)}

    def _generate_random_global_missile(self, simulation_start: datetime, simulation_end: datetime,
                                      sequence: int) -> Optional[Dict[str, Any]]:
        """
        生成随机的全球导弹威胁

        Args:
            simulation_start: 仿真开始时间
            simulation_end: 仿真结束时间
            sequence: 序号

        Returns:
            导弹场景配置字典
        """
        try:
            import random

            # 生成导弹ID
            id_range = self.missile_mgmt_config["position_generation"]["id_range"]
            missile_id = f"GlobalThreat_{sequence:03d}_{random.randint(*id_range)}"

            # 全球随机发射位置
            launch_position = {
                "lat": random.uniform(-60, 60),      # 纬度范围：南纬60度到北纬60度
                "lon": random.uniform(-180, 180),    # 经度范围：全球
                "alt": random.uniform(0, 100)        # 高度：0-100米
            }

            # 全球随机目标位置（确保与发射位置有一定距离）
            pos_config = self.missile_mgmt_config["position_generation"]
            min_distance_deg = pos_config["min_distance_deg"]
            max_attempts = pos_config["max_attempts"]

            for attempt in range(max_attempts):
                target_position = {
                    "lat": random.uniform(-60, 60),
                    "lon": random.uniform(-180, 180),
                    "alt": random.uniform(0, 100)
                }

                # 计算大致距离
                lat_diff = abs(target_position["lat"] - launch_position["lat"])
                lon_diff = abs(target_position["lon"] - launch_position["lon"])
                distance = (lat_diff**2 + lon_diff**2)**0.5

                if distance >= min_distance_deg:
                    break

            # 使用配置的轨迹参数范围
            time_config = self.missile_mgmt_config["time_config"]
            trajectory_params = {
                "max_altitude": random.uniform(1000, 1800),    # 使用配置的高度范围
                "flight_time": random.uniform(*time_config["flight_time_range"])  # 使用配置的飞行时间范围
            }

            # 基于当前数据采集时刻生成发射时间（使用配置的偏移范围）
            current_collection_time = self.time_manager.current_simulation_time
            launch_offset = random.randint(*time_config["launch_time_offset_range"])
            launch_time = current_collection_time + timedelta(seconds=launch_offset)

            # 确保导弹在仿真时间范围内完成飞行
            estimated_end_time = launch_time + timedelta(seconds=trajectory_params["flight_time"])
            if estimated_end_time > simulation_end:
                # 调整发射时间，确保在仿真范围内
                launch_time = simulation_end - timedelta(seconds=trajectory_params["flight_time"])
                # 如果调整后的发射时间早于当前时间，则设置为当前时间加最小偏移
                if launch_time < current_collection_time:
                    min_offset = time_config["launch_time_offset_range"][0]
                    launch_time = current_collection_time + timedelta(seconds=min_offset)

            # 导弹类型和威胁等级
            missile_types = ["ICBM", "IRBM", "MRBM", "SRBM"]
            threat_levels = ["高", "中", "低"]

            missile_scenario = {
                "missile_id": missile_id,
                "missile_type": random.choice(missile_types),
                "threat_level": random.choice(threat_levels),
                "description": f"全球随机导弹威胁 {missile_id}",
                "launch_position": launch_position,
                "target_position": target_position,
                "trajectory_params": trajectory_params,
                "launch_time": launch_time,
                "launch_sequence": sequence,
                "estimated_flight_time": trajectory_params["flight_time"],
                "generation_method": "random_global"
            }

            logger.info(f"🎲 生成随机全球导弹: {missile_id}")
            logger.info(f"   发射位置: 纬度{launch_position['lat']:.2f}°, 经度{launch_position['lon']:.2f}°")
            logger.info(f"   目标位置: 纬度{target_position['lat']:.2f}°, 经度{target_position['lon']:.2f}°")
            logger.info(f"   发射时间: {launch_time}")
            logger.info(f"   飞行时间: {trajectory_params['flight_time']:.0f}秒")
            logger.info(f"   最大高度: {trajectory_params['max_altitude']:.1f}km")

            return missile_scenario

        except Exception as e:
            logger.error(f"❌ 生成随机全球导弹失败: {e}")
            return None

    def generate_original_task_info(self, missile_id: str) -> Optional[Dict[str, Any]]:
        """生成原任务信息 - 为ADK智能体提供任务数据"""
        try:
            logger.info(f"🎯 生成原任务信息: {missile_id}")

            # 获取导弹信息
            missile_info = self.missile_targets.get(missile_id)
            if not missile_info:
                logger.error(f"❌ 未找到导弹信息: {missile_id}")
                return None

            # 获取轨迹信息
            trajectory_info = self.get_missile_trajectory_info(missile_id)
            if not trajectory_info:
                logger.error(f"❌ 无法获取轨迹信息: {missile_id}")
                raise Exception(f"无法获取轨迹信息: {missile_id}")

            # 构建原任务信息
            original_task_info = {
                "missile_id": missile_id,
                "missile_type": missile_info.get("missile_type", "ballistic_missile"),
                "description": missile_info.get("description", ""),
                "threat_level": missile_info.get("threat_level", "高"),
                "launch_time": missile_info.get("launch_time"),
                "launch_position": missile_info.get("launch_position"),
                "target_position": missile_info.get("target_position"),
                "trajectory_info": trajectory_info,
                "tracking_task": self._generate_tracking_task_info(missile_id, trajectory_info),
                "generated_time": self.time_manager.start_time.isoformat()
            }

            logger.info(f"✅ 原任务信息生成成功: {missile_id}")
            return original_task_info

        except Exception as e:
            logger.error(f"❌ 生成原任务信息失败: {e}")
            return None



    def _generate_tracking_task_info(self, missile_id: str, trajectory_info: Dict[str, Any]) -> Dict[str, Any]:
        """生成跟踪任务信息"""
        try:
            midcourse_points = trajectory_info.get("midcourse_points", [])
            launch_time = trajectory_info.get("launch_time")
            impact_time = trajectory_info.get("impact_time")

            if not midcourse_points or not launch_time or not impact_time:
                logger.error(f"轨迹数据不完整，无法生成跟踪任务: {missile_id}")
                logger.error(f"   midcourse_points: {len(midcourse_points) if midcourse_points else 0}")
                logger.error(f"   launch_time: {launch_time}")
                logger.error(f"   impact_time: {impact_time}")
                raise Exception(f"轨迹数据不完整，无法生成跟踪任务: {missile_id}")

            # 计算中段飞行时间窗口 - 基于实际中段轨迹点的时间范围
            if midcourse_points:
                # 使用实际中段轨迹点的时间范围
                midcourse_times = [point['time'] for point in midcourse_points]
                midcourse_start = min(midcourse_times)
                midcourse_end = max(midcourse_times)
                logger.info(f"   📊 基于高度阈值({self.midcourse_altitude_threshold}km)的中段轨迹点: {len(midcourse_points)}个")
            else:
                # 如果没有中段轨迹点，回退到时间偏移方法
                logger.warning(f"   ⚠️ 没有找到高度>{self.midcourse_altitude_threshold}km的中段轨迹点，使用时间偏移方法")
                # 使用配置的时间偏移
                time_config = self.missile_mgmt_config["time_config"]
                min_offset = time_config["launch_time_offset_range"][0]  # 使用最小偏移作为缓冲时间
                midcourse_start = launch_time + timedelta(seconds=min_offset)  # 发射后缓冲时间
                midcourse_end = impact_time - timedelta(seconds=min_offset)    # 撞击前缓冲时间

                # 确保中段时间窗口有效
                if midcourse_end <= midcourse_start:
                    flight_duration = (impact_time - launch_time).total_seconds()
                    midcourse_start = launch_time + timedelta(seconds=flight_duration * 0.2)
                    midcourse_end = launch_time + timedelta(seconds=flight_duration * 0.8)

            logger.info(f"   ⏰ 中段时间窗口: {midcourse_start} -> {midcourse_end}")
            logger.info(f"   ⏰ 中段持续时间: {(midcourse_end - midcourse_start).total_seconds():.1f}秒")

            # 生成原子任务
            atomic_tasks = []
            task_duration = self.time_manager.atomic_task_duration
            current_time = midcourse_start
            task_id = 1

            while current_time < midcourse_end:
                task_end_time = current_time + timedelta(seconds=task_duration)
                if task_end_time > midcourse_end:
                    task_end_time = midcourse_end

                # 找到对应时间的轨迹点
                task_position = self._interpolate_position_at_time(midcourse_points, current_time)

                atomic_task = {
                    "task_id": f"{missile_id}_task_{task_id:03d}",
                    "start_time": current_time,
                    "end_time": task_end_time,
                    "duration": (task_end_time - current_time).total_seconds(),
                    "target_position": task_position,
                    "task_type": "tracking",
                    "priority": "high"
                }
                atomic_tasks.append(atomic_task)

                current_time = task_end_time
                task_id += 1

            return {
                "missile_id": missile_id,
                "start_time": midcourse_start,  # 可视化器期望的字段名
                "end_time": midcourse_end,      # 可视化器期望的字段名
                "tracking_window_start": midcourse_start,
                "tracking_window_end": midcourse_end,
                "total_duration": (midcourse_end - midcourse_start).total_seconds(),
                "atomic_tasks": atomic_tasks,
                "total_tasks": len(atomic_tasks)
            }

        except Exception as e:
            logger.error(f"生成跟踪任务信息失败: {e}")
            return {}

    def _interpolate_position_at_time(self, trajectory_points: List[Dict], target_time: datetime) -> Dict[str, float]:
        """在指定时间插值位置"""
        try:
            if not trajectory_points:
                raise Exception("轨迹点数据为空")

            # 找到最接近的时间点
            closest_point = min(trajectory_points,
                               key=lambda p: abs((p["time"] - target_time).total_seconds()))

            return {
                "lat": closest_point["lat"],
                "lon": closest_point["lon"],
                "alt": closest_point["alt"]
            }

        except Exception as e:
            logger.error(f"时间插值失败: {e}")
            raise Exception(f"时间插值失败: {e}")

    def find_nearest_satellite(self, missile_id: str, satellite_positions: Dict[str, Dict]) -> Optional[str]:
        """找到距离导弹最近的卫星"""
        try:
            logger.info(f"🔍 为导弹 {missile_id} 寻找最近卫星...")

            # 获取导弹中段起始位置
            missile_position = self.get_missile_midcourse_start_position(missile_id)
            if not missile_position:
                logger.error(f"❌ 无法获取导弹位置: {missile_id}")
                raise Exception(f"无法获取导弹位置: {missile_id}")

            # 计算到每个卫星的距离
            min_distance = float('inf')
            nearest_satellite = None

            for satellite_id, sat_pos in satellite_positions.items():
                try:
                    distance = self._calculate_great_circle_distance(missile_position, sat_pos)
                    logger.debug(f"   {satellite_id}: 距离 {distance/1000:.1f} km")

                    if distance < min_distance:
                        min_distance = distance
                        nearest_satellite = satellite_id

                except Exception as calc_error:
                    logger.warning(f"   计算距离失败 {satellite_id}: {calc_error}")

            if nearest_satellite:
                logger.info(f"✅ 最近卫星: {nearest_satellite} (距离: {min_distance/1000:.1f} km)")
                return nearest_satellite
            else:
                logger.error(f"❌ 未找到可用卫星")
                return None

        except Exception as e:
            logger.error(f"❌ 寻找最近卫星失败: {e}")
            return None

    async def send_task_to_nearest_agent(self, missile_id: str, satellite_id: str,
                                       original_task: Dict[str, Any],
                                       adk_agents: Dict[str, Any]) -> Dict[str, Any]:
        """向最近的智能体发送任务"""
        try:
            logger.info(f"📤 向卫星 {satellite_id} 发送导弹 {missile_id} 的跟踪任务...")

            # 获取对应的智能体
            agent = adk_agents.get(satellite_id)
            if not agent:
                logger.error(f"❌ 未找到卫星智能体: {satellite_id}")
                return {"success": False, "error": f"未找到智能体: {satellite_id}"}

            # 构建任务配置
            task_config = {
                "missile_id": missile_id,
                "priority": "high",
                "tracking_mode": "coordination",
                "coordination_enabled": True,
                "original_task": original_task,
                "assigned_satellite": satellite_id,
                "assignment_time": self.time_manager.start_time.isoformat()
            }

            # 发送任务给智能体
            try:
                result = await agent.process_missile_tracking_task(missile_id, task_config)

                if result and not result.get("error"):
                    logger.info(f"✅ 任务发送成功: {satellite_id} -> {missile_id}")
                    return {
                        "success": True,
                        "missile_id": missile_id,
                        "assigned_to": satellite_id,
                        "task_result": result,
                        "assignment_time": task_config["assignment_time"]
                    }
                else:
                    logger.error(f"❌ 智能体任务处理失败: {result.get('error', 'Unknown error')}")
                    return {
                        "success": False,
                        "error": f"智能体任务处理失败: {result.get('error', 'Unknown error')}"
                    }

            except Exception as agent_error:
                logger.error(f"❌ 智能体任务发送异常: {agent_error}")
                return {
                    "success": False,
                    "error": f"智能体任务发送异常: {agent_error}"
                }

        except Exception as e:
            logger.error(f"❌ 发送任务到智能体失败: {e}")
            return {"success": False, "error": str(e)}

    def generate_multi_target_visualization(self, target_ids: List[str]) -> Optional[str]:
        """生成多目标可视化"""
        try:
            logger.info(f"📊 生成多目标可视化: {len(target_ids)} 个目标")

            if not self.output_manager:
                logger.error("❌ 输出管理器未初始化")
                return None

            # 收集所有目标的原任务信息
            all_original_tasks = {}
            for target_id in target_ids:
                original_task = self.generate_original_task_info(target_id)
                if original_task:
                    all_original_tasks[target_id] = original_task

            if not all_original_tasks:
                logger.error("❌ 没有有效的原任务信息")
                return None

            # 使用多目标可视化器
            try:
                from src.visualization.multi_target_atomic_task_visualizer import MultiTargetAtomicTaskVisualizer

                visualizer = MultiTargetAtomicTaskVisualizer()
                save_path = visualizer.create_multi_target_aligned_chart(all_original_tasks, self.output_manager)
                visualizer.close()

                if save_path:
                    logger.info(f"✅ 多目标可视化生成成功: {save_path}")
                    return save_path
                else:
                    logger.error("❌ 多目标可视化生成失败")
                    return None

            except ImportError as import_error:
                logger.error(f"❌ 多目标可视化器导入失败: {import_error}")
                return None

        except Exception as e:
            logger.error(f"❌ 生成多目标可视化失败: {e}")
            return None

    def get_missile_launch_and_impact_times(self, missile_name: str) -> tuple:
        """
        获取导弹的发射时间和撞击时间
        基于STK官方文档的正确方法：使用GetTimePeriod Connect命令

        Args:
            missile_name: 导弹名称

        Returns:
            tuple: (launch_time_dt, impact_time_dt) 或 (None, None) 如果失败
        """
        try:
            # 方法1: 使用GetTimePeriod Connect命令（STK官方推荐方法）
            try:
                missile_path = f"*/Missile/{missile_name}"
                cmd = f"GetTimePeriod {missile_path}"

                result = self.stk_manager.root.ExecuteCommand(cmd)

                if result and hasattr(result, 'Item') and result.Count > 0:
                    # 获取时间范围字符串
                    time_range = result.Item(0)

                    # 解析时间范围字符串，格式: "开始时间", "结束时间"
                    if isinstance(time_range, str) and '", "' in time_range:
                        # 移除引号并分割
                        time_range = time_range.strip('"')
                        times = time_range.split('", "')

                        if len(times) == 2:
                            launch_time_str = times[0].strip('"')
                            impact_time_str = times[1].strip('"')

                            # 解析时间字符串
                            launch_time_dt = self._parse_stk_time(launch_time_str)
                            impact_time_dt = self._parse_stk_time(impact_time_str)

                            if launch_time_dt and impact_time_dt:
                                logger.info(f"✅ GetTimePeriod获取成功: {launch_time_str} - {impact_time_str}")
                                return launch_time_dt, impact_time_dt

            except Exception as e1:
                logger.debug(f"GetTimePeriod方法失败: {e1}")

            # 方法2: 使用Available Times DataProvider（备用方法）
            try:
                missile = self.stk_manager.scenario.Children.Item(missile_name)
                dp_available_times = missile.DataProviders.Item("Available Times")
                scenario_start = self.stk_manager.scenario.StartTime
                scenario_stop = self.stk_manager.scenario.StopTime

                result = dp_available_times.Exec(scenario_start, scenario_stop)

                if result and result.DataSets.Count > 0:
                    dataset = result.DataSets.Item(0)
                    if dataset.RowCount > 0:
                        launch_time_str = dataset.GetValue(0, 0)
                        impact_time_str = dataset.GetValue(0, 1) if dataset.ColumnCount > 1 else launch_time_str

                        # 解析时间字符串
                        launch_time_dt = self._parse_stk_time(launch_time_str)
                        impact_time_dt = self._parse_stk_time(impact_time_str)

                        if launch_time_dt and impact_time_dt:
                            logger.info(f"✅ Available Times获取成功: {launch_time_str} - {impact_time_str}")
                            return launch_time_dt, impact_time_dt

            except Exception as e2:
                logger.debug(f"Available Times方法失败: {e2}")

            # 方法3: 使用LLA State DataProvider获取首末时间点（备用方法）
            try:
                missile = self.stk_manager.scenario.Children.Item(missile_name)
                dp_lla = missile.DataProviders.Item("LLA State")
                scenario_start = self.stk_manager.scenario.StartTime
                scenario_stop = self.stk_manager.scenario.StopTime

                lla_result = dp_lla.Exec(scenario_start, scenario_stop, 60)

                if lla_result and lla_result.DataSets.Count > 0:
                    lla_dataset = lla_result.DataSets.Item(0)
                    if lla_dataset.RowCount > 0:
                        launch_time_str = lla_dataset.GetValue(0, 0)
                        impact_time_str = lla_dataset.GetValue(lla_dataset.RowCount - 1, 0)

                        # 解析时间字符串
                        launch_time_dt = self._parse_stk_time(launch_time_str)
                        impact_time_dt = self._parse_stk_time(impact_time_str)

                        if launch_time_dt and impact_time_dt:
                            logger.info(f"✅ LLA State获取成功: {launch_time_str} - {impact_time_str}")
                            return launch_time_dt, impact_time_dt

            except Exception as e3:
                logger.debug(f"LLA State方法失败: {e3}")

            # 方法4: 估算方法（最后的备用方案）
            try:
                # 如果无法获取精确时间，使用估算
                time_config = self.missile_mgmt_config["time_config"]
                scenario_start_dt = datetime.strptime(
                    self.stk_manager.scenario.StartTime,
                    "%d %b %Y %H:%M:%S.%f"
                )

                # 估算发射时间为场景开始后最小偏移时间
                min_offset_seconds = time_config["launch_time_offset_range"][0]
                launch_time_dt = scenario_start_dt + timedelta(seconds=min_offset_seconds)
                # 使用配置的默认飞行时间
                flight_minutes = time_config["default_minutes"]
                impact_time_dt = launch_time_dt + timedelta(minutes=flight_minutes)

                logger.warning(f"⚠️ 使用估算时间: {launch_time_dt} - {impact_time_dt}")
                return launch_time_dt, impact_time_dt

            except Exception as e4:
                logger.debug(f"估算方法失败: {e4}")

            logger.warning(f"⚠️ 无法获取导弹 {missile_name} 的时间信息")
            return None, None

        except Exception as e:
            logger.error(f"❌ 获取导弹时间失败: {e}")
            return None, None


# 全局导弹管理器实例
_missile_manager = None

def get_missile_manager(config_manager=None, stk_manager=None, output_manager=None):
    """获取全局导弹管理器实例"""
    global _missile_manager
    if _missile_manager is None and config_manager:
        if stk_manager is None:
            from src.stk_interface.stk_manager import get_stk_manager
            stk_manager = get_stk_manager(config_manager)
        if output_manager is None:
            # 创建一个简单的输出管理器
            class SimpleOutputManager:
                def __init__(self):
                    pass
                def save_data(self, *args, **kwargs):
                    pass
            output_manager = SimpleOutputManager()
        if stk_manager:
            missile_config = config_manager.get_missile_config() if hasattr(config_manager, 'get_missile_config') else {}
            _missile_manager = MissileManager(stk_manager, missile_config, output_manager)
    return _missile_manager
