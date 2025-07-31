"""
数据采集器
负责采集卫星位置姿态、载荷参数、导弹轨迹、可见性时间窗口等数据
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from ..utils.time_manager import get_time_manager
from ..utils.config_manager import get_config_manager

logger = logging.getLogger(__name__)

class DataCollector:
    """数据采集器"""
    
    def __init__(self, stk_manager, missile_manager, visibility_calculator, 
                 constellation_manager, config_manager=None, time_manager=None):
        """
        初始化数据采集器
        
        Args:
            stk_manager: STK管理器
            missile_manager: 导弹管理器
            visibility_calculator: 可见性计算器
            constellation_manager: 星座管理器
            config_manager: 配置管理器
            time_manager: 时间管理器
        """
        self.stk_manager = stk_manager
        self.missile_manager = missile_manager
        self.visibility_calculator = visibility_calculator
        self.constellation_manager = constellation_manager
        self.config_manager = config_manager or get_config_manager()
        self.time_manager = time_manager or get_time_manager()
        
        # 数据存储
        self.collected_data = []
        self.output_dir = Path("output/data")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化元任务管理器
        from src.meta_task import get_meta_task_manager
        self.meta_task_manager = get_meta_task_manager(
            self.config_manager, self.time_manager, self.missile_manager, self.visibility_calculator
        )

        logger.info("📊 数据采集器初始化完成")
    
    def collect_data_at_time(self, collection_time: datetime) -> Dict[str, Any]:
        """
        在指定时间采集数据 - 使用固定的仿真场景时间范围

        Args:
            collection_time: 采集时间

        Returns:
            采集的数据
        """
        try:
            # 获取采集进度信息
            progress = self.time_manager.get_collection_progress()

            # 输出明显特征的采集周期开始日志
            logger.info("=" * 80)
            logger.info(f"🚀 【数据采集周期 #{progress['current_count'] + 1}】开始")
            logger.info(f"📊 采集进度: {progress['current_count']}/{progress['total_count']} ({progress['progress_percentage']}%)")
            logger.info(f"⏰ 采集时间: {collection_time}")
            logger.info(f"📈 剩余采集: {progress['remaining_count']}次")
            logger.info("=" * 80)

            # 推进仿真时间到采集时间点
            self.time_manager.advance_simulation_time(collection_time)

            # 采集数据（使用固定的场景时间范围，不再动态设置）
            satellite_data = self._collect_satellite_data()
            missile_data = self._collect_missile_data()
            visibility_data = self._collect_visibility_data()

            # 创建元任务信息集
            meta_task_set = None
            meta_task_files = {}
            active_missiles = [missile["missile_id"] for missile in missile_data if missile.get("is_active", False)]

            if active_missiles and self.meta_task_manager:
                logger.info("🎯 创建元任务信息集...")
                meta_task_set = self.meta_task_manager.create_meta_task_set(collection_time, active_missiles)

                if meta_task_set:
                    # 保存元任务信息集
                    meta_task_file = self.meta_task_manager.save_meta_task_set(meta_task_set)
                    if meta_task_file:
                        meta_task_files["meta_task_data"] = meta_task_file

                    # 生成甘特图
                    gantt_files = self.meta_task_manager.generate_gantt_charts(meta_task_set)
                    meta_task_files.update(gantt_files)

                    logger.info(f"✅ 元任务处理完成: {len(meta_task_files)} 个文件生成")
                else:
                    logger.warning("⚠️ 元任务信息集创建失败")

            data_snapshot = {
                "collection_time": collection_time.isoformat(),
                "simulation_progress": self.time_manager.get_simulation_progress(),
                "satellites": satellite_data,
                "missiles": missile_data,
                "visibility": visibility_data,
                "meta_task_set": {
                    "window_count": len(meta_task_set.meta_windows) if meta_task_set else 0,
                    "total_missiles": len(active_missiles),
                    "time_range": [
                        meta_task_set.time_range[0].isoformat(),
                        meta_task_set.time_range[1].isoformat()
                    ] if meta_task_set else None,
                    "files": meta_task_files
                },
                "metadata": {
                    "collection_count": self.time_manager.collection_count,
                    "stk_connected": self.stk_manager.is_connected,
                    "constellation_info": self.constellation_manager.get_constellation_info(),
                    "scenario_time_fixed": True  # 标记使用固定场景时间
                }
            }

            # 添加到数据列表
            self.collected_data.append(data_snapshot)

            # 获取更新后的进度信息
            progress = self.time_manager.get_collection_progress()

            logger.info(f"✅ 【数据采集周期 #{progress['current_count']}】完成")
            logger.info(f"📊 本次采集: {len(data_snapshot['satellites'])}颗卫星, "
                       f"{len(data_snapshot['missiles'])}个导弹目标")
            logger.info(f"📈 总体进度: {progress['current_count']}/{progress['total_count']} ({progress['progress_percentage']}%)")
            logger.info("=" * 80)

            return data_snapshot

        except Exception as e:
            logger.error(f"❌ 数据采集失败: {e}")
            return {}



    def _collect_satellite_data(self) -> List[Dict[str, Any]]:
        """采集所有卫星的数据"""
        satellite_data = []
        
        try:
            satellite_list = self.constellation_manager.get_satellite_list()
            
            for satellite_id in satellite_list:
                try:
                    # 获取卫星位置
                    position_data = self.stk_manager.get_satellite_position(satellite_id)
                    
                    if position_data:
                        satellite_info = {
                            "satellite_id": satellite_id,
                            "position": position_data,
                            "payload_status": self._get_payload_status(satellite_id),
                            "data_quality": "good" if position_data else "poor"
                        }
                        satellite_data.append(satellite_info)
                        logger.debug(f"✅ 卫星数据采集成功: {satellite_id}")
                    else:
                        logger.warning(f"⚠️ 卫星位置数据获取失败: {satellite_id}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 卫星数据采集异常 {satellite_id}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ 卫星数据采集失败: {e}")
            
        return satellite_data
    
    def _collect_missile_data(self) -> List[Dict[str, Any]]:
        """采集当前时刻在飞行的导弹数据"""
        missile_data = []
        
        try:
            # 获取当前时刻在飞行的导弹
            current_time = self.time_manager.current_simulation_time
            active_missiles = self._get_active_missiles(current_time)
            
            for missile_id in active_missiles:
                try:
                    # 获取导弹轨迹信息
                    trajectory_info = self.missile_manager.get_missile_trajectory_info(missile_id)
                    
                    if trajectory_info:
                        missile_info = {
                            "missile_id": missile_id,
                            "trajectory": trajectory_info,
                            "flight_status": self._get_missile_flight_status(missile_id, current_time),
                            "data_quality": "high" if trajectory_info.get("stk_data_quality", {}).get("has_real_trajectory") else "medium",
                            "is_active": True  # 标记为活跃导弹
                        }
                        missile_data.append(missile_info)
                        logger.debug(f"✅ 导弹数据采集成功: {missile_id}")
                    else:
                        logger.warning(f"⚠️ 导弹轨迹数据获取失败: {missile_id}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ 导弹数据采集异常 {missile_id}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ 导弹数据采集失败: {e}")
            
        return missile_data
    
    def _collect_visibility_data(self) -> List[Dict[str, Any]]:
        """采集可见性数据"""
        visibility_data = []
        
        try:
            satellite_list = self.constellation_manager.get_satellite_list()
            current_time = self.time_manager.current_simulation_time
            active_missiles = self._get_active_missiles(current_time)
            
            # 计算每颗卫星对每个导弹的可见性
            for satellite_id in satellite_list:
                for missile_id in active_missiles:
                    try:
                        visibility_result = self.visibility_calculator.calculate_satellite_to_missile_access(
                            satellite_id, missile_id
                        )
                        
                        if visibility_result and visibility_result.get("success"):
                            visibility_info = {
                                "satellite_id": satellite_id,
                                "missile_id": missile_id,
                                "has_visibility": visibility_result.get("has_access", False),
                                "access_intervals": visibility_result.get("access_intervals", []),
                                "total_intervals": visibility_result.get("total_intervals", 0),
                                "calculation_time": current_time.isoformat()
                            }
                            visibility_data.append(visibility_info)
                            
                    except Exception as e:
                        logger.debug(f"可见性计算异常 {satellite_id}->{missile_id}: {e}")
                        
        except Exception as e:
            logger.error(f"❌ 可见性数据采集失败: {e}")
            
        return visibility_data
    
    def _get_payload_status(self, satellite_id: str) -> Dict[str, Any]:
        """获取载荷状态"""
        try:
            payload_config = self.config_manager.get_payload_config()
            data_sim_config = self.config_manager.get_data_simulation_config()
            payload_sim = data_sim_config["payload_status"]

            # 基本载荷状态信息
            payload_status = {
                "type": payload_config.get("type", "Optical_Sensor"),
                "mounting": payload_config.get("mounting", "Nadir"),
                "sensor_pattern": payload_config.get("sensor_pattern", "Conic"),
                "operational": payload_sim.get("operational_default", True),
                "power_consumption": payload_sim.get("power_consumption", 80.0),
                "temperature": payload_sim.get("temperature", 25.0),
                "pointing": payload_config.get("pointing", {}),
                "constraints": payload_config.get("constraints_range", {})
            }
            
            return payload_status
            
        except Exception as e:
            logger.debug(f"获取载荷状态失败 {satellite_id}: {e}")
            return {"operational": False, "error": str(e)}
    
    def _get_active_missiles(self, current_time: datetime) -> List[str]:
        """获取当前时刻在飞行的导弹列表"""
        active_missiles = []
        
        try:
            # 从导弹管理器获取所有导弹
            for missile_id, missile_info in self.missile_manager.missile_targets.items():
                if isinstance(missile_info, dict) and "launch_time" in missile_info:
                    launch_time = missile_info.get("launch_time")
                    
                    if isinstance(launch_time, datetime):
                        # 使用配置的导弹飞行时间
                        missile_mgmt_config = self.config_manager.get_missile_management_config()
                        time_config = missile_mgmt_config["time_config"]
                        flight_minutes = time_config["default_minutes"]
                        impact_time = launch_time + timedelta(minutes=flight_minutes)

                        # 检查导弹是否在飞行中
                        if launch_time <= current_time <= impact_time:
                            active_missiles.append(missile_id)
                            
        except Exception as e:
            logger.debug(f"获取活跃导弹列表失败: {e}")
            
        return active_missiles
    
    def _get_missile_flight_status(self, missile_id: str, current_time: datetime) -> Dict[str, Any]:
        """获取导弹飞行状态"""
        try:
            missile_info = self.missile_manager.missile_targets.get(missile_id, {})
            launch_time = missile_info.get("launch_time")
            
            if isinstance(launch_time, datetime):
                flight_duration = (current_time - launch_time).total_seconds()
                
                return {
                    "status": "in_flight",
                    "launch_time": launch_time.isoformat(),
                    "flight_duration": flight_duration,
                    "estimated_impact_time": (launch_time + timedelta(minutes=30)).isoformat()
                }
            else:
                return {"status": "unknown", "error": "Invalid launch time"}
                
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def save_collected_data(self) -> Optional[str]:
        """
        保存采集的数据到文件
        
        Returns:
            保存的文件路径
        """
        try:
            if not self.collected_data:
                logger.warning("⚠️ 没有数据需要保存")
                return None
            
            # 生成文件名
            filename = self.time_manager.get_data_filename()
            file_path = self.output_dir / filename
            
            # 准备保存的数据
            save_data = {
                "metadata": {
                    "collection_start_time": self.time_manager.start_time.isoformat(),
                    "collection_end_time": self.time_manager.current_simulation_time.isoformat(),
                    "total_collections": len(self.collected_data),
                    "constellation_info": self.constellation_manager.get_constellation_info(),
                    "simulation_config": self.config_manager.get_simulation_config()
                },
                "data_snapshots": self.collected_data
            }
            
            # 保存到JSON文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
            
            logger.info(f"💾 数据保存成功: {file_path}")
            logger.info(f"   数据快照数量: {len(self.collected_data)}")
            
            # 清空已保存的数据
            self.collected_data.clear()
            
            return str(file_path)
            
        except Exception as e:
            logger.error(f"❌ 数据保存失败: {e}")
            return None
    
    def get_collection_summary(self) -> Dict[str, Any]:
        """获取数据采集摘要"""
        try:
            total_satellites = 0
            total_missiles = 0
            total_visibility_records = 0
            
            for snapshot in self.collected_data:
                total_satellites += len(snapshot.get("satellites", []))
                total_missiles += len(snapshot.get("missiles", []))
                total_visibility_records += len(snapshot.get("visibility", []))
            
            return {
                "total_snapshots": len(self.collected_data),
                "total_satellite_records": total_satellites,
                "total_missile_records": total_missiles,
                "total_visibility_records": total_visibility_records,
                "collection_period": {
                    "start": self.time_manager.start_time.isoformat(),
                    "current": self.time_manager.current_simulation_time.isoformat(),
                    "progress": f"{self.time_manager.get_simulation_progress():.1f}%"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 获取采集摘要失败: {e}")
            return {}
