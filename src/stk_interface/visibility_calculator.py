#!/usr/bin/env python3
"""
可见性计算器模块
负责卫星-导弹可见性计算
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class VisibilityCalculator:
    """可见性计算器"""
    
    def __init__(self, stk_manager):
        """初始化可见性计算器"""
        self.stk_manager = stk_manager

        # 获取配置
        from src.utils.config_manager import get_config_manager
        config_manager = get_config_manager()
        self.visibility_config = config_manager.get_visibility_config()

        logger.info("🔍 可见性计算器初始化")
    
    def calculate_satellite_to_missile_access(self, satellite_id: str, missile_id: str) -> Dict[str, Any]:
        """计算卫星到导弹的访问"""
        try:
            logger.info(f"🔍 计算可见性: {satellite_id} -> {missile_id}")
            
            # 使用STK计算访问
            access_result = self._compute_stk_access(satellite_id, missile_id)
            
            if access_result:
                logger.info(f"   ✅ 可见性计算成功: {satellite_id}")
                return {
                    "satellite_id": satellite_id,
                    "missile_id": missile_id,
                    "success": True,
                    "has_access": access_result["has_access"],
                    "access_intervals": access_result["intervals"],
                    "total_intervals": len(access_result["intervals"])
                }
            else:
                logger.warning(f"   ❌ 可见性计算失败: {satellite_id}")
                return {
                    "satellite_id": satellite_id,
                    "missile_id": missile_id,
                    "success": False,
                    "has_access": False,
                    "access_intervals": [],
                    "total_intervals": 0
                }
                
        except Exception as e:
            logger.error(f"❌ 可见性计算异常 {satellite_id}: {e}")
            return {
                "satellite_id": satellite_id,
                "missile_id": missile_id,
                "success": False,
                "error": str(e),
                "has_access": False,
                "access_intervals": [],
                "total_intervals": 0
            }
    
    def compute_constellation_visibility(self, satellite_paths: List[str], target_path: str) -> Dict[str, Any]:
        """
        计算星座对目标的可见性 - 兼容元任务可见性分析器

        Args:
            satellite_paths: 卫星路径列表，如 ["Satellite/Satellite11", ...]
            target_path: 目标路径，如 "Missile/ICBM_Threat_01"

        Returns:
            包含所有卫星可见性信息的字典
        """
        # 提取卫星ID
        satellite_ids = []
        for path in satellite_paths:
            if "/" in path:
                satellite_ids.append(path.split("/")[-1])
            else:
                satellite_ids.append(path)

        # 提取目标ID
        if "/" in target_path:
            missile_id = target_path.split("/")[-1]
        else:
            missile_id = target_path

        # 调用原有的星座访问计算方法
        return self.calculate_constellation_access(satellite_ids, missile_id)

    def analyze_meta_task_visibility(self, meta_tasks: List[Dict[str, Any]], satellite_paths: List[str]) -> Dict[str, Any]:
        """
        分析元任务可见性 - 为元任务协调器提供接口

        Args:
            meta_tasks: 元任务列表，每个包含target_id和atomic_tasks
            satellite_paths: 卫星路径列表

        Returns:
            包含卫星分配建议的字典
        """
        try:
            logger.info(f"🔍 开始元任务可见性分析: {len(meta_tasks)}个目标, {len(satellite_paths)}颗卫星")
            logger.info(f"   📋 元任务详情: {[task.get('target_id', 'Unknown') for task in meta_tasks]}")
            logger.info(f"   🛰️ 卫星路径: {satellite_paths}")

            satellite_assignment = {}

            for meta_task in meta_tasks:
                target_id = meta_task.get("target_id", "Unknown")
                atomic_tasks = meta_task.get("atomic_tasks", [])

                logger.info(f"   🎯 分析目标: {target_id}, 原子任务数: {len(atomic_tasks)}")
                logger.info(f"   📋 原子任务详情: {[task.get('task_id', 'Unknown') for task in atomic_tasks]}")

                # 提取卫星ID
                satellite_ids = []
                for path in satellite_paths:
                    if "/" in path:
                        satellite_ids.append(path.split("/")[-1])
                    else:
                        satellite_ids.append(path)

                # 计算优化的星座可见性
                # 注意：使用target_id作为missile_id，因为在ICBM系统中它们是相同的
                visibility_result = self.calculate_optimized_constellation_visibility(
                    satellite_ids, target_id, atomic_tasks
                )

                logger.info(f"   🔍 可见性计算结果键: {list(visibility_result.keys())}")
                if visibility_result.get("constellation_visibility"):
                    logger.info(f"   🛰️ 星座可见性键: {list(visibility_result['constellation_visibility'].keys())}")
                else:
                    logger.warning(f"   ❌ 星座可见性为空: {visibility_result.get('constellation_visibility')}")

                # 找到最佳卫星
                best_satellite = None
                best_score = 0

                if visibility_result.get("constellation_visibility"):
                    for sat_id, sat_result in visibility_result["constellation_visibility"].items():
                        if sat_result.get("has_access"):
                            # 计算可见性得分
                            intervals = sat_result.get("access_intervals", [])

                            # 获取元任务分析结果
                            meta_analysis = visibility_result.get("meta_task_analysis", {}).get(sat_id, {})
                            visible_tasks = meta_analysis.get("visible_tasks", 0)
                            total_tasks = meta_analysis.get("total_tasks", 1)

                            # 综合得分：可见窗口数 + 可见任务比例
                            score = len(intervals) + (visible_tasks / total_tasks)

                            logger.info(f"   🔍 卫星 {sat_id}: 访问间隔={len(intervals)}, 可见任务={visible_tasks}/{total_tasks}, 得分={score:.2f}")

                            if score > best_score:
                                best_score = score
                                best_satellite = sat_id

                if best_satellite:
                    satellite_assignment[target_id] = {
                        "satellite_id": best_satellite,
                        "score": best_score,
                        "visibility_result": visibility_result["constellation_visibility"][best_satellite],
                        "meta_task_analysis": visibility_result.get("meta_task_analysis", {}).get(best_satellite, {})
                    }
                    logger.info(f"   ✅ 目标 {target_id} 最佳卫星: {best_satellite} (得分: {best_score:.2f})")
                else:
                    logger.warning(f"   ❌ 目标 {target_id} 未找到可见卫星")

            result = {
                "success": True,
                "satellite_assignment": satellite_assignment,
                "total_targets": len(meta_tasks),
                "assigned_targets": len(satellite_assignment)
            }

            logger.info(f"✅ 元任务可见性分析完成: {len(satellite_assignment)}/{len(meta_tasks)} 目标已分配")
            return result

        except Exception as e:
            logger.error(f"❌ 元任务可见性分析失败: {e}")
            return {"success": False, "error": str(e)}

    def calculate_constellation_access(self, satellite_ids: List[str], missile_id: str) -> Dict[str, Any]:
        """计算星座访问"""
        try:
            logger.info(f"🌟 计算星座可见性: {len(satellite_ids)} 颗卫星 -> {missile_id}")
            
            constellation_result = {
                "missile_id": missile_id,
                "satellites_count": len(satellite_ids),
                "successful_calculations": 0,
                "satellites_with_access": [],
                "total_access_intervals": 0,
                "satellite_results": {}
            }
            
            # 计算每颗卫星的访问
            for satellite_id in satellite_ids:
                result = self.calculate_satellite_to_missile_access(satellite_id, missile_id)
                
                constellation_result["satellite_results"][satellite_id] = result
                
                if result["success"]:
                    constellation_result["successful_calculations"] += 1
                    
                    if result["has_access"]:
                        constellation_result["satellites_with_access"].append(satellite_id)
                        constellation_result["total_access_intervals"] += result["total_intervals"]
            
            logger.info(f"🌟 星座可见性计算完成:")
            logger.info(f"   成功计算: {constellation_result['successful_calculations']}")
            logger.info(f"   有访问的卫星: {len(constellation_result['satellites_with_access'])}")
            logger.info(f"   总访问间隔: {constellation_result['total_access_intervals']}")
            
            return constellation_result

        except Exception as e:
            logger.error(f"❌ 星座可见性计算失败: {e}")
            return {"error": str(e)}

    def calculate_optimized_constellation_visibility(self, satellite_ids: List[str], missile_id: str,
                                                   atomic_tasks: List[Dict] = None) -> Dict[str, Any]:
        """
        优化的星座可见性计算 - 基于STK官方文档
        一次性计算整个星座的可见窗口，然后与元任务时间段比较

        Args:
            satellite_ids: 卫星ID列表
            missile_id: 导弹ID
            atomic_tasks: 原子任务列表，包含start_time和end_time

        Returns:
            Dict: 优化的可见性结果
        """
        try:
            logger.info(f"🌟 优化计算星座可见性: {len(satellite_ids)} 颗卫星 -> {missile_id}")

            # 1. 一次性计算所有卫星的可见窗口
            constellation_visibility = {}
            total_visible_satellites = 0
            total_access_intervals = 0

            for satellite_id in satellite_ids:
                # 计算该卫星对导弹的可见窗口
                visibility_result = self.calculate_satellite_to_missile_access(satellite_id, missile_id)

                if visibility_result and visibility_result.get("success"):
                    access_intervals = visibility_result.get("access_intervals", [])

                    constellation_visibility[satellite_id] = {
                        "satellite_id": satellite_id,
                        "has_access": len(access_intervals) > 0,
                        "access_intervals": access_intervals,
                        "total_intervals": len(access_intervals)
                    }

                    if len(access_intervals) > 0:
                        total_visible_satellites += 1
                        total_access_intervals += len(access_intervals)
                else:
                    constellation_visibility[satellite_id] = {
                        "satellite_id": satellite_id,
                        "has_access": False,
                        "access_intervals": [],
                        "total_intervals": 0
                    }

            # 2. 如果提供了原子任务，进行元任务级别的可见性分析
            meta_task_analysis = {}
            if atomic_tasks:
                logger.info(f"📊 进行元任务级别可见性分析: {len(atomic_tasks)} 个原子任务")

                for satellite_id in satellite_ids:
                    satellite_visibility = constellation_visibility[satellite_id]
                    access_intervals = satellite_visibility["access_intervals"]

                    # 分析每个原子任务的可见性
                    task_visibility = []
                    visible_task_count = 0

                    for i, atomic_task in enumerate(atomic_tasks):
                        task_start = atomic_task.get("start_time")
                        task_end = atomic_task.get("end_time")

                        if task_start and task_end:
                            # 判断该原子任务是否与可见窗口重叠
                            is_visible = self._is_task_visible_in_windows(task_start, task_end, access_intervals)
                            overlapping_windows = self._get_overlapping_windows(task_start, task_end, access_intervals) if is_visible else []

                            task_visibility.append({
                                "task_index": i + 1,
                                "task_id": atomic_task.get("task_id", f"atomic_task_{i+1}"),
                                "start_time": task_start,
                                "end_time": task_end,
                                "is_visible": is_visible,
                                "overlapping_windows": overlapping_windows,
                                "visibility_duration": self._calculate_visibility_duration(overlapping_windows)
                            })

                            if is_visible:
                                visible_task_count += 1

                    meta_task_analysis[satellite_id] = {
                        "satellite_id": satellite_id,
                        "total_tasks": len(atomic_tasks),
                        "visible_tasks": visible_task_count,
                        "visibility_rate": (visible_task_count / len(atomic_tasks) * 100) if atomic_tasks else 0,
                        "task_visibility": task_visibility
                    }

            # 3. 构建优化的结果
            optimized_result = {
                "missile_id": missile_id,
                "constellation_size": len(satellite_ids),
                "total_visible_satellites": total_visible_satellites,
                "total_access_intervals": total_access_intervals,
                "constellation_visibility": constellation_visibility,
                "meta_task_analysis": meta_task_analysis,
                "optimization_stats": {
                    "stk_api_calls": len(satellite_ids),  # 只调用了卫星数量次STK API
                    "atomic_tasks_analyzed": len(atomic_tasks) if atomic_tasks else 0,
                    "computation_efficiency": f"1 STK call per satellite vs {len(atomic_tasks) if atomic_tasks else 0} calls per task"
                }
            }

            logger.info(f"🌟 优化星座可见性计算完成:")
            logger.info(f"   STK API调用次数: {len(satellite_ids)}")
            logger.info(f"   可见卫星数: {total_visible_satellites}")
            logger.info(f"   总访问间隔: {total_access_intervals}")
            if atomic_tasks:
                logger.info(f"   原子任务分析: {len(atomic_tasks)} 个任务")

            return optimized_result

        except Exception as e:
            logger.error(f"❌ 优化星座可见性计算失败: {e}")
            return {"error": str(e)}
    
    def _compute_stk_access(self, satellite_id: str, missile_id: str) -> Optional[Dict[str, Any]]:
        """使用STK真正的Access计算 - 基于STK官方文档"""
        try:
            logger.info(f"   🔍 使用STK API计算访问: {satellite_id} -> {missile_id}")

            if not self.stk_manager or not self.stk_manager.scenario:
                logger.warning("STK管理器或场景不可用")
                return {"has_access": False, "intervals": []}

            # 1. 获取STK根对象和场景
            root = self.stk_manager.root
            scenario = self.stk_manager.scenario

            # 2. 基于STK官方文档: 使用对象路径获取访问
            satellite_path = f"Satellite/{satellite_id}"
            missile_path = f"Missile/{missile_id}"

            try:
                # 基于STK官方代码: Get access by object path
                satellite = root.GetObjectFromPath(satellite_path)
                access = satellite.GetAccess(missile_path)
                logger.debug(f"   ✅ 创建访问对象成功: {satellite_path} -> {missile_path}")
            except Exception as e:
                logger.warning(f"   ❌ 创建访问对象失败: {e}")
                return {"has_access": False, "intervals": []}

            # 3. 基于STK官方文档: 配置访问约束
            self._configure_stk_access_constraints(access)

            # 4. 基于STK官方文档: Compute access
            try:
                access.ComputeAccess()
                logger.debug(f"   ✅ 访问计算完成")
            except Exception as e:
                logger.warning(f"   ❌ 访问计算失败: {e}")
                return {"has_access": False, "intervals": []}

            # 5. 基于STK官方文档: Get and display the Computed Access Intervals
            access_intervals = self._extract_stk_access_intervals(access)

            # 添加调试信息
            logger.debug(f"   🔍 调试信息: 访问间隔提取结果 = {len(access_intervals)}")
            if len(access_intervals) > 0:
                logger.debug(f"   🔍 第一个间隔: {access_intervals[0]}")

            # 尝试直接检查访问对象
            try:
                interval_collection = access.ComputedAccessIntervalTimes
                logger.debug(f"   🔍 直接检查: interval_collection = {interval_collection}")
                if interval_collection:
                    logger.debug(f"   🔍 直接检查: Count = {interval_collection.Count}")
                    if interval_collection.Count > 0:
                        logger.debug(f"   🔍 直接检查: 有访问间隔！")
                        # 尝试获取原始数据
                        try:
                            raw_data = interval_collection.ToArray(0, -1)
                            logger.debug(f"   🔍 原始数据长度: {len(raw_data)}")
                            if len(raw_data) > 0:
                                logger.debug(f"   🔍 原始数据前几个: {raw_data[:min(4, len(raw_data))]}")
                        except Exception as e:
                            logger.debug(f"   🔍 获取原始数据失败: {e}")
                else:
                    logger.debug(f"   🔍 直接检查: interval_collection 为 None")
            except Exception as e:
                logger.debug(f"   🔍 直接检查失败: {e}")

            # 6. 构建返回数据
            access_data = {
                "has_access": len(access_intervals) > 0,
                "intervals": access_intervals
            }

            logger.info(f"   ✅ STK访问计算完成: {satellite_id}, 有访问: {access_data['has_access']}, 间隔数: {len(access_intervals)}")
            return access_data

        except Exception as e:
            logger.error(f"❌ STK访问计算异常: {e}")
            return {"has_access": False, "intervals": []}

    def _configure_stk_access_constraints(self, access):
        """
        配置STK访问约束 - 基于STK官方文档
        """
        try:
            # 基于STK官方代码: Get handle to the object access constraints
            access_constraints = access.AccessConstraints

            # 基于STK官方代码: Add and configure an altitude access constraint
            altitude_constraint = access_constraints.AddConstraint(2)  # eCstrAltitude
            altitude_constraint.EnableMin = True
            altitude_constraint.Min = self.visibility_config["access_constraints"]["min_altitude"]  # km - 最小高度约束

            # 基于STK官方代码: Add and configure a sun elevation angle access constraint
            sun_elevation = access_constraints.AddConstraint(58)  # eCstrSunElevationAngle
            sun_elevation.EnableMin = True
            sun_elevation.Min = self.visibility_config["access_constraints"]["sun_elevation_min"]  # 度 - 避免太阳干扰

            logger.debug("   ✅ STK访问约束配置完成")

        except Exception as e:
            logger.debug(f"   ⚠️ STK访问约束配置失败: {e}")

    def _extract_stk_access_intervals(self, access) -> List[Dict[str, str]]:
        """
        提取STK访问间隔 - 基于STK官方文档
        """
        try:
            intervals = []

            # 基于STK官方代码: Compute and extract access interval times
            interval_collection = access.ComputedAccessIntervalTimes

            if interval_collection and interval_collection.Count > 0:
                logger.debug(f"   📊 找到 {interval_collection.Count} 个访问间隔")

                # 基于STK官方代码: Set the intervals to use to the Computed Access Intervals
                computed_intervals = interval_collection.ToArray(0, -1)

                # 解析间隔数据 - STK返回的是元组的元组格式
                for interval_tuple in computed_intervals:
                    if isinstance(interval_tuple, tuple) and len(interval_tuple) >= 2:
                        start_time = interval_tuple[0]
                        end_time = interval_tuple[1]

                        intervals.append({
                            "start": str(start_time),
                            "stop": str(end_time)
                        })
                    elif len(computed_intervals) >= 2:
                        # 备用解析方式：如果是平坦数组
                        for i in range(0, len(computed_intervals), 2):
                            if i + 1 < len(computed_intervals):
                                start_time = computed_intervals[i]
                                end_time = computed_intervals[i + 1]

                                intervals.append({
                                    "start": str(start_time),
                                    "stop": str(end_time)
                                })
                        break

                logger.debug(f"   ✅ 成功提取 {len(intervals)} 个访问间隔")
            else:
                logger.debug("   📊 没有找到访问间隔")

            return intervals

        except Exception as e:
            logger.debug(f"   ❌ STK访问间隔提取失败: {e}")
            return []

    def _parse_stk_time(self, stk_time_str: str):
        """
        解析STK时间字符串 - 基于STK官方时间格式

        Args:
            stk_time_str: STK时间字符串，如 "23 Jul 2025 04:00:00.000"

        Returns:
            datetime对象或None
        """
        try:
            from datetime import datetime

            # 移除毫秒部分以简化解析
            time_str = stk_time_str.strip()
            if '.' in time_str:
                time_str = time_str.split('.')[0]

            # STK标准时间格式: "23 Jul 2025 04:00:00"
            dt = datetime.strptime(time_str, "%d %b %Y %H:%M:%S")
            return dt

        except Exception as e:
            logger.debug(f"STK时间解析失败: {stk_time_str}, 错误: {e}")
            return None

    def _get_access_object(self, satellite):
        """获取访问对象（优先使用传感器）- 基于项目成功经验"""
        try:
            # 优先使用传感器进行访问计算
            if satellite.Children.Count > 0:
                for i in range(satellite.Children.Count):
                    child = satellite.Children.Item(i)
                    if child.ClassName == "Sensor":
                        logger.debug(f"   🔍 使用传感器进行访问计算: {child.InstanceName}")
                        return child

            # 如果没有传感器，使用卫星本身
            logger.debug(f"   🛰️ 使用卫星本身进行访问计算: {satellite.InstanceName}")
            return satellite

        except Exception as e:
            logger.debug(f"获取访问对象失败: {e}")
            return satellite

    def _extract_access_intervals(self, access) -> List[Dict[str, str]]:
        """提取访问间隔 - 基于项目成功经验"""
        try:
            intervals = []

            # 方法1: 使用ComputedAccessIntervalTimes（推荐）
            try:
                access_intervals = access.ComputedAccessIntervalTimes
                if access_intervals and access_intervals.Count > 0:
                    logger.debug(f"   📊 找到 {access_intervals.Count} 个访问间隔")

                    for i in range(access_intervals.Count):
                        interval = access_intervals.Item(i)
                        start_time = str(interval.Start)
                        stop_time = str(interval.Stop)

                        intervals.append({
                            "start": start_time,
                            "stop": stop_time
                        })

                    return intervals

            except Exception as e:
                logger.debug(f"ComputedAccessIntervalTimes方法失败: {e}")

            # 方法2: 使用DataProviders（备用）
            try:
                logger.debug("   🔄 尝试使用DataProviders方法")

                accessDP = access.DataProviders.Item('Access Data').Exec(
                    self.stk_manager.scenario.StartTime,
                    self.stk_manager.scenario.StopTime
                )

                if accessDP and accessDP.DataSets.Count > 0:
                    dataset = accessDP.DataSets.Item(0)
                    for row in range(dataset.RowCount):
                        start_time = dataset.GetValue(row, 0)  # 开始时间
                        stop_time = dataset.GetValue(row, 1)   # 结束时间

                        intervals.append({
                            "start": str(start_time),
                            "stop": str(stop_time)
                        })

                    return intervals

            except Exception as e:
                logger.debug(f"DataProviders方法失败: {e}")

            return intervals

        except Exception as e:
            logger.debug(f"提取访问间隔失败: {e}")
            return []




    def _is_task_visible_in_windows(self, task_start: str, task_end: str, access_intervals: List[Dict]) -> bool:
        """
        判断原子任务是否在可见窗口内

        Args:
            task_start: 任务开始时间（ISO格式字符串）
            task_end: 任务结束时间（ISO格式字符串）
            access_intervals: 访问间隔列表

        Returns:
            bool: 是否可见
        """
        try:
            from datetime import datetime

            # 转换任务时间
            if isinstance(task_start, str):
                task_start_dt = datetime.fromisoformat(task_start.replace('Z', '+00:00'))
            else:
                task_start_dt = task_start

            if isinstance(task_end, str):
                task_end_dt = datetime.fromisoformat(task_end.replace('Z', '+00:00'))
            else:
                task_end_dt = task_end

            logger.debug(f"[可见性判断] 任务时间: start={task_start}({task_start_dt}), end={task_end}({task_end_dt})")

            # 检查是否与任何访问间隔重叠
            for idx, interval in enumerate(access_intervals):
                interval_start_str = interval.get("start")
                interval_end_str = interval.get("stop") or interval.get("end")

                if interval_start_str and interval_end_str:
                    try:
                        # 解析STK时间格式
                        interval_start_dt = self._parse_stk_time(interval_start_str)
                        interval_end_dt = self._parse_stk_time(interval_end_str)

                        logger.debug(f"[可见性判断] 窗口{idx+1}: start={interval_start_str}({interval_start_dt}), end={interval_end_str}({interval_end_dt})")

                        if interval_start_dt and interval_end_dt:
                            # 检查时间重叠：任务开始时间 < 间隔结束时间 且 任务结束时间 > 间隔开始时间
                            overlap = task_start_dt < interval_end_dt and task_end_dt > interval_start_dt
                            logger.debug(f"[可见性判断] 任务与窗口{idx+1}重叠: {overlap}")
                            if overlap:
                                return True
                    except Exception as parse_error:
                        logger.debug(f"[可见性判断] 时间解析失败: {parse_error}")
                        continue

            logger.debug(f"[可见性判断] 任务与所有窗口均无重叠")
            return False

        except Exception as e:
            logger.error(f"判断任务可见性失败: {e}")
            return False

    def _get_overlapping_windows(self, task_start: str, task_end: str, access_intervals: List[Dict]) -> List[Dict]:
        """
        获取与任务时间重叠的可见窗口

        Args:
            task_start: 任务开始时间
            task_end: 任务结束时间
            access_intervals: 访问间隔列表

        Returns:
            List[Dict]: 重叠的窗口列表
        """
        try:
            from datetime import datetime

            overlapping_windows = []

            # 转换任务时间
            if isinstance(task_start, str):
                task_start_dt = datetime.fromisoformat(task_start.replace('Z', '+00:00'))
            else:
                task_start_dt = task_start

            if isinstance(task_end, str):
                task_end_dt = datetime.fromisoformat(task_end.replace('Z', '+00:00'))
            else:
                task_end_dt = task_end

            logger.debug(f"[重叠窗口] 任务时间: start={task_start}({task_start_dt}), end={task_end}({task_end_dt})")

            # 找到所有重叠的窗口
            for idx, interval in enumerate(access_intervals):
                interval_start_str = interval.get("start")
                interval_end_str = interval.get("stop") or interval.get("end")

                if interval_start_str and interval_end_str:
                    try:
                        interval_start_dt = self._parse_stk_time(interval_start_str)
                        interval_end_dt = self._parse_stk_time(interval_end_str)

                        logger.debug(f"[重叠窗口] 窗口{idx+1}: start={interval_start_str}({interval_start_dt}), end={interval_end_str}({interval_end_dt})")

                        if interval_start_dt and interval_end_dt:
                            # 检查时间重叠
                            overlap = task_start_dt < interval_end_dt and task_end_dt > interval_start_dt
                            logger.debug(f"[重叠窗口] 任务与窗口{idx+1}重叠: {overlap}")
                            if overlap:
                                # 计算重叠部分
                                overlap_start = max(task_start_dt, interval_start_dt)
                                overlap_end = min(task_end_dt, interval_end_dt)

                                overlapping_windows.append({
                                    "original_window": interval,
                                    "overlap_start": overlap_start.isoformat(),
                                    "overlap_end": overlap_end.isoformat(),
                                    "overlap_duration": (overlap_end - overlap_start).total_seconds()
                                })
                    except Exception as parse_error:
                        logger.debug(f"[重叠窗口] 解析失败: {parse_error}")
                        continue

            logger.debug(f"[重叠窗口] 共找到 {len(overlapping_windows)} 个重叠窗口")
            return overlapping_windows

        except Exception as e:
            logger.error(f"获取重叠窗口失败: {e}")
            return []

    def _calculate_visibility_duration(self, overlapping_windows: List[Dict]) -> float:
        """
        计算总可见时长

        Args:
            overlapping_windows: 重叠窗口列表

        Returns:
            float: 总可见时长（秒）
        """
        try:
            total_duration = 0.0
            for window in overlapping_windows:
                duration = window.get("overlap_duration", 0)
                total_duration += duration
            return total_duration
        except Exception as e:
            logger.error(f"计算可见时长失败: {e}")
            return 0.0


# 全局可见性计算器实例
_visibility_calculator = None

def get_visibility_calculator(config_manager=None):
    """获取全局可见性计算器实例"""
    global _visibility_calculator
    if _visibility_calculator is None and config_manager:
        from src.stk_interface.stk_manager import get_stk_manager
        stk_manager = get_stk_manager(config_manager)
        if stk_manager:
            _visibility_calculator = VisibilityCalculator(stk_manager)
    return _visibility_calculator
