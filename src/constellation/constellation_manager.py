"""
星座管理器
负责Walker星座的创建与参数配置，包括卫星轨道参数设置和载荷配置
"""

import logging
import math
from typing import Dict, List, Any, Optional
from ..utils.config_manager import get_config_manager

logger = logging.getLogger(__name__)

class ConstellationManager:
    """Walker星座管理器"""
    
    def __init__(self, stk_manager, config_manager=None):
        """
        初始化星座管理器
        
        Args:
            stk_manager: STK管理器实例
            config_manager: 配置管理器实例
        """
        self.stk_manager = stk_manager
        self.config_manager = config_manager or get_config_manager()
        self.constellation_config = self.config_manager.get_constellation_config()
        self.payload_config = self.config_manager.get_payload_config()
        
        logger.info("🌟 星座管理器初始化完成")
        
    def create_walker_constellation(self) -> bool:
        """
        创建Walker星座
        
        Returns:
            创建是否成功
        """
        try:
            logger.info("🌟 开始创建Walker星座...")

            # 检查STK连接
            if not self.stk_manager.is_connected:
                logger.error("❌ STK未连接，无法创建星座")
                return False

            # 🔧 修复：检查现有卫星，避免重复创建
            existing_satellites = self.stk_manager.get_objects("Satellite")
            if existing_satellites and len(existing_satellites) > 0:
                logger.info(f"🔍 检测到现有卫星 {len(existing_satellites)} 颗，跳过Walker星座创建")
                logger.info(f"📡 现有卫星: {[sat.split('/')[-1] for sat in existing_satellites]}")
                return True

            # 检查是否跳过创建（现有项目检测）
            if self.stk_manager.should_skip_stk_creation():
                logger.info("🔍 检测到现有项目，跳过星座创建")
                return True
            
            # 获取星座参数
            constellation_type = self.constellation_config.get("type", "Walker")
            planes = self.constellation_config.get("planes", 3)
            sats_per_plane = self.constellation_config.get("satellites_per_plane", 3)
            total_satellites = self.constellation_config.get("total_satellites", 9)
            
            logger.info(f"📊 星座配置: {constellation_type}, {planes}个轨道面, 每面{sats_per_plane}颗卫星")
            
            # 创建Walker星座
            success = self._create_walker_satellites(planes, sats_per_plane)
            
            if success:
                logger.info(f"✅ Walker星座创建成功，共{total_satellites}颗卫星")
                return True
            else:
                logger.error("❌ Walker星座创建失败")
                return False
                
        except Exception as e:
            logger.error(f"❌ 创建Walker星座异常: {e}")
            return False
    
    def _create_walker_satellites(self, planes: int, sats_per_plane: int) -> bool:
        """
        创建Walker星座中的所有卫星
        
        Args:
            planes: 轨道面数量
            sats_per_plane: 每个轨道面的卫星数量
            
        Returns:
            创建是否成功
        """
        try:
            reference_params = self.constellation_config.get("reference_satellite", {})
            
            # 基础轨道参数
            base_altitude = reference_params.get("altitude", 1800)  # km
            base_inclination = reference_params.get("inclination", 51.856)  # 度
            base_eccentricity = reference_params.get("eccentricity", 0.0)
            base_arg_perigee = reference_params.get("arg_of_perigee", 12)  # 度
            raan_offset = reference_params.get("raan_offset", 24)  # 度
            mean_anomaly_offset = reference_params.get("mean_anomaly_offset", 180)  # 度
            
            # 计算Walker星座参数
            raan_spacing = 360.0 / planes  # 轨道面间的RAAN间隔
            mean_anomaly_spacing = 360.0 / sats_per_plane  # 同轨道面内卫星的平近点角间隔
            
            satellite_count = 0
            
            for plane_idx in range(planes):
                for sat_idx in range(sats_per_plane):
                    satellite_count += 1
                    # 新的命名规则：Satellite{轨道面编号}{卫星编号}
                    # 例如：Satellite11, Satellite12, Satellite13 (第1轨道面的3颗卫星)
                    #       Satellite21, Satellite22, Satellite23 (第2轨道面的3颗卫星)
                    satellite_id = f"Satellite{plane_idx+1}{sat_idx+1}"
                    
                    # 计算该卫星的轨道参数
                    orbital_params = self._calculate_satellite_orbital_params(
                        base_altitude, base_inclination, base_eccentricity, base_arg_perigee,
                        plane_idx, sat_idx, raan_spacing, mean_anomaly_spacing,
                        raan_offset, mean_anomaly_offset
                    )
                    
                    # 创建卫星
                    success = self.stk_manager.create_satellite(satellite_id, orbital_params)
                    if not success:
                        logger.error(f"❌ 卫星创建失败: {satellite_id}")
                        return False
                    
                    # 为卫星创建载荷
                    payload_success = self.stk_manager.create_sensor(satellite_id, self.payload_config)
                    if not payload_success:
                        logger.warning(f"⚠️ 载荷创建失败: {satellite_id}")
                    
                    logger.info(f"✅ 卫星创建成功: {satellite_id} (轨道面{plane_idx+1}, 位置{sat_idx+1})")
            
            logger.info(f"🌟 Walker星座创建完成，共创建{satellite_count}颗卫星")
            return True
            
        except Exception as e:
            logger.error(f"❌ 创建Walker卫星失败: {e}")
            return False
    
    def _calculate_satellite_orbital_params(self, base_altitude: float, base_inclination: float,
                                          base_eccentricity: float, base_arg_perigee: float,
                                          plane_idx: int, sat_idx: int,
                                          raan_spacing: float, mean_anomaly_spacing: float,
                                          raan_offset: float, mean_anomaly_offset: float) -> Dict[str, float]:
        """
        计算单颗卫星的轨道参数
        
        Args:
            base_altitude: 基础高度 (km)
            base_inclination: 基础倾角 (度)
            base_eccentricity: 基础偏心率
            base_arg_perigee: 基础近地点幅角 (度)
            plane_idx: 轨道面索引 (0开始)
            sat_idx: 卫星在轨道面内的索引 (0开始)
            raan_spacing: 轨道面间RAAN间隔 (度)
            mean_anomaly_spacing: 同轨道面内卫星平近点角间隔 (度)
            raan_offset: RAAN偏移 (度)
            mean_anomaly_offset: 平近点角偏移 (度)
            
        Returns:
            轨道参数字典
        """
        # 地球半径 (km)
        earth_radius = 6371.0
        
        # 计算半长轴 (km)
        semi_major_axis = earth_radius + base_altitude
        
        # 计算该卫星的RAAN (升交点赤经)
        raan = (plane_idx * raan_spacing + raan_offset) % 360.0
        
        # 计算该卫星的平近点角
        mean_anomaly = (sat_idx * mean_anomaly_spacing + mean_anomaly_offset) % 360.0
        
        orbital_params = {
            "semi_axis": semi_major_axis,
            "eccentricity": base_eccentricity,
            "inclination": base_inclination,
            "raan": raan,
            "arg_of_perigee": base_arg_perigee,
            "mean_anomaly": mean_anomaly
        }
        
        logger.debug(f"🛰️ 轨道参数计算: 轨道面{plane_idx+1}, 卫星{sat_idx+1} (ID: Satellite{plane_idx+1}{sat_idx+1})")
        logger.debug(f"   半长轴: {semi_major_axis:.1f} km")
        logger.debug(f"   倾角: {base_inclination:.3f}°")
        logger.debug(f"   RAAN: {raan:.1f}°")
        logger.debug(f"   平近点角: {mean_anomaly:.1f}°")
        
        return orbital_params

    def get_satellite_info_from_id(self, satellite_id: str) -> Dict[str, Any]:
        """
        从卫星ID解析轨道面和卫星编号信息

        Args:
            satellite_id: 卫星ID (格式: SatelliteXY, X=轨道面编号, Y=卫星编号)

        Returns:
            包含轨道面和卫星编号的字典
        """
        try:
            # 解析卫星ID格式：SatelliteXY
            if satellite_id.startswith("Satellite") and len(satellite_id) >= 11:
                plane_num = int(satellite_id[9])  # 轨道面编号
                sat_num = int(satellite_id[10])   # 卫星编号

                return {
                    "satellite_id": satellite_id,
                    "plane_number": plane_num,
                    "satellite_number": sat_num,
                    "plane_index": plane_num - 1,  # 0-based索引
                    "satellite_index": sat_num - 1  # 0-based索引
                }
            else:
                logger.warning(f"无法解析卫星ID格式: {satellite_id}")
                return {}

        except Exception as e:
            logger.error(f"解析卫星ID失败: {satellite_id}, 错误: {e}")
            return {}

    def get_satellites_by_plane(self, plane_number: int) -> List[str]:
        """
        获取指定轨道面的所有卫星ID

        Args:
            plane_number: 轨道面编号 (1-based)

        Returns:
            该轨道面的卫星ID列表
        """
        try:
            sats_per_plane = self.constellation_config.get("satellites_per_plane", 3)
            satellites = []

            for sat_idx in range(1, sats_per_plane + 1):
                satellite_id = f"Satellite{plane_number}{sat_idx}"
                satellites.append(satellite_id)

            return satellites

        except Exception as e:
            logger.error(f"获取轨道面{plane_number}卫星列表失败: {e}")
            return []
    
    def get_satellite_list(self) -> List[str]:
        """
        获取星座中的卫星列表
        
        Returns:
            卫星ID列表
        """
        try:
            total_satellites = self.constellation_config.get("total_satellites", 9)
            satellite_list = []
            
            for i in range(1, total_satellites + 1):
                satellite_id = f"Satellite{i:02d}"
                satellite_list.append(satellite_id)
            
            return satellite_list
            
        except Exception as e:
            logger.error(f"❌ 获取卫星列表失败: {e}")
            return []
    
    def get_constellation_info(self) -> Dict[str, Any]:
        """
        获取星座信息
        
        Returns:
            星座信息字典
        """
        return {
            "type": self.constellation_config.get("type", "Walker"),
            "planes": self.constellation_config.get("planes", 3),
            "satellites_per_plane": self.constellation_config.get("satellites_per_plane", 3),
            "total_satellites": self.constellation_config.get("total_satellites", 9),
            "satellite_list": self.get_satellite_list(),
            "reference_satellite": self.constellation_config.get("reference_satellite", {}),
            "payload_config": self.payload_config
        }
    

