#!/usr/bin/env python3
"""
GDOP（几何精度衰减因子）计算器
实现航天预警领域的GDOP指标评估

GDOP定义：
- GDOP = √(q11 + q22 + q33 + q44)
- 其中 q11, q22, q33, q44 是权系数矩阵 Q = (A^T A)^(-1) 的对角线元素
- A 是设计矩阵（方向余弦矩阵）
- GDOP 值越小，几何分布越好，定位精度越高
"""

import numpy as np
import logging
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import math

logger = logging.getLogger(__name__)


class GDOPCalculator:
    """GDOP计算器"""
    
    def __init__(self):
        """初始化GDOP计算器"""
        self.earth_radius = 6371000.0  # 地球半径（米）
        logger.info("✅ GDOP计算器初始化完成")
    
    def calculate_gdop(self, satellite_positions: List[Dict[str, Any]], 
                      user_position: Dict[str, float]) -> Dict[str, Any]:
        """
        计算GDOP值
        
        Args:
            satellite_positions: 卫星位置列表，每个包含 {'x': float, 'y': float, 'z': float}
            user_position: 用户位置 {'x': float, 'y': float, 'z': float}
            
        Returns:
            GDOP计算结果字典
        """
        try:
            logger.info(f"🔄 开始计算GDOP - 卫星数量: {len(satellite_positions)}")
            
            if len(satellite_positions) < 4:
                logger.warning(f"⚠️ 卫星数量不足: {len(satellite_positions)} < 4")
                return {
                    'success': False,
                    'error': '卫星数量不足，至少需要4颗卫星',
                    'satellite_count': len(satellite_positions)
                }
            
            # 构建设计矩阵A（方向余弦矩阵）
            design_matrix = self._build_design_matrix(satellite_positions, user_position)
            
            if design_matrix is None:
                return {
                    'success': False,
                    'error': '设计矩阵构建失败',
                    'satellite_count': len(satellite_positions)
                }
            
            # 计算权系数矩阵 Q = (A^T A)^(-1)
            weight_matrix = self._calculate_weight_matrix(design_matrix)
            
            if weight_matrix is None:
                return {
                    'success': False,
                    'error': '权系数矩阵计算失败（可能是矩阵奇异）',
                    'satellite_count': len(satellite_positions)
                }
            
            # 计算各种DOP值
            gdop = self._calculate_gdop_value(weight_matrix)
            pdop = self._calculate_pdop_value(weight_matrix)
            hdop, vdop = self._calculate_hdop_vdop_values(weight_matrix, user_position)
            tdop = self._calculate_tdop_value(weight_matrix)
            
            # 评估几何分布质量
            geometry_quality = self._evaluate_geometry_quality(gdop)
            
            result = {
                'success': True,
                'gdop': gdop,
                'pdop': pdop,
                'hdop': hdop,
                'vdop': vdop,
                'tdop': tdop,
                'geometry_quality': geometry_quality,
                'satellite_count': len(satellite_positions),
                'design_matrix_condition': np.linalg.cond(design_matrix),
                'calculation_timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ GDOP计算完成 - GDOP: {gdop:.3f}, 质量: {geometry_quality}")
            return result
            
        except Exception as e:
            logger.error(f"❌ GDOP计算失败: {e}")
            return {
                'success': False,
                'error': str(e),
                'satellite_count': len(satellite_positions)
            }
    
    def _build_design_matrix(self, satellite_positions: List[Dict[str, Any]], 
                           user_position: Dict[str, float]) -> Optional[np.ndarray]:
        """构建设计矩阵A（方向余弦矩阵）"""
        try:
            n_satellites = len(satellite_positions)
            design_matrix = np.zeros((n_satellites, 4))
            
            user_x = user_position.get('x', 0.0)
            user_y = user_position.get('y', 0.0)
            user_z = user_position.get('z', 0.0)
            
            for i, sat_pos in enumerate(satellite_positions):
                sat_x = sat_pos.get('x', 0.0)
                sat_y = sat_pos.get('y', 0.0)
                sat_z = sat_pos.get('z', 0.0)
                
                # 计算用户到卫星的距离向量
                dx = sat_x - user_x
                dy = sat_y - user_y
                dz = sat_z - user_z
                
                # 计算距离
                distance = math.sqrt(dx*dx + dy*dy + dz*dz)
                
                if distance < 1e-6:  # 避免除零
                    logger.warning(f"⚠️ 卫星{i}距离用户过近: {distance}")
                    continue
                
                # 方向余弦（单位向量）
                design_matrix[i, 0] = dx / distance  # x方向余弦
                design_matrix[i, 1] = dy / distance  # y方向余弦
                design_matrix[i, 2] = dz / distance  # z方向余弦
                design_matrix[i, 3] = 1.0           # 时间项
            
            logger.debug(f"📐 设计矩阵构建完成: {design_matrix.shape}")
            return design_matrix
            
        except Exception as e:
            logger.error(f"❌ 设计矩阵构建失败: {e}")
            return None
    
    def _calculate_weight_matrix(self, design_matrix: np.ndarray) -> Optional[np.ndarray]:
        """计算权系数矩阵 Q = (A^T A)^(-1)"""
        try:
            # 计算 A^T A
            ata_matrix = np.dot(design_matrix.T, design_matrix)

            # 检查矩阵条件数
            condition_number = np.linalg.cond(ata_matrix)
            if condition_number > 1e12:
                logger.warning(f"⚠️ 矩阵条件数过大: {condition_number:.2e}")

                # 尝试使用伪逆矩阵
                try:
                    weight_matrix = np.linalg.pinv(ata_matrix)
                    logger.info(f"✅ 使用伪逆矩阵计算权系数矩阵")
                    return weight_matrix
                except Exception as pinv_e:
                    logger.error(f"❌ 伪逆矩阵计算也失败: {pinv_e}")
                    return None

            # 计算逆矩阵 Q = (A^T A)^(-1)
            weight_matrix = np.linalg.inv(ata_matrix)

            logger.debug(f"📊 权系数矩阵计算完成，条件数: {condition_number:.2e}")
            return weight_matrix

        except np.linalg.LinAlgError as e:
            logger.error(f"❌ 权系数矩阵计算失败（线性代数错误）: {e}")
            # 尝试使用伪逆矩阵作为备用方案
            try:
                ata_matrix = np.dot(design_matrix.T, design_matrix)
                weight_matrix = np.linalg.pinv(ata_matrix)
                logger.info(f"✅ 使用伪逆矩阵作为备用方案")
                return weight_matrix
            except Exception as pinv_e:
                logger.error(f"❌ 伪逆矩阵备用方案也失败: {pinv_e}")
                return None
        except Exception as e:
            logger.error(f"❌ 权系数矩阵计算失败: {e}")
            return None
    
    def _calculate_gdop_value(self, weight_matrix: np.ndarray) -> float:
        """计算GDOP值"""
        try:
            # GDOP = √(q11 + q22 + q33 + q44)
            q11 = weight_matrix[0, 0]  # x方向权系数
            q22 = weight_matrix[1, 1]  # y方向权系数
            q33 = weight_matrix[2, 2]  # z方向权系数
            q44 = weight_matrix[3, 3]  # 时间权系数

            # 检查权系数是否为负数或无穷大
            if any(not np.isfinite(q) or q < 0 for q in [q11, q22, q33, q44]):
                logger.warning(f"⚠️ 权系数异常: q11={q11:.4f}, q22={q22:.4f}, q33={q33:.4f}, q44={q44:.4f}")
                return float('inf')

            gdop_squared = q11 + q22 + q33 + q44
            if gdop_squared < 0:
                logger.warning(f"⚠️ GDOP平方值为负: {gdop_squared:.4f}")
                return float('inf')

            gdop = math.sqrt(gdop_squared)

            logger.debug(f"📊 GDOP分量 - q11:{q11:.4f}, q22:{q22:.4f}, q33:{q33:.4f}, q44:{q44:.4f}")
            return gdop

        except Exception as e:
            logger.error(f"❌ GDOP值计算失败: {e}")
            return float('inf')
    
    def _calculate_pdop_value(self, weight_matrix: np.ndarray) -> float:
        """计算PDOP值（位置精度衰减因子）"""
        try:
            # PDOP = √(q11 + q22 + q33)
            q11 = weight_matrix[0, 0]
            q22 = weight_matrix[1, 1]
            q33 = weight_matrix[2, 2]
            
            pdop = math.sqrt(q11 + q22 + q33)
            return pdop
            
        except Exception as e:
            logger.error(f"❌ PDOP值计算失败: {e}")
            return float('inf')
    
    def _calculate_hdop_vdop_values(self, weight_matrix: np.ndarray, 
                                  user_position: Dict[str, float]) -> Tuple[float, float]:
        """计算HDOP和VDOP值（水平和垂直精度衰减因子）"""
        try:
            # 简化计算：假设水平方向为x,y，垂直方向为z
            # HDOP = √(q11 + q22)
            # VDOP = √(q33)
            
            q11 = weight_matrix[0, 0]
            q22 = weight_matrix[1, 1]
            q33 = weight_matrix[2, 2]
            
            hdop = math.sqrt(q11 + q22)
            vdop = math.sqrt(q33)
            
            return hdop, vdop
            
        except Exception as e:
            logger.error(f"❌ HDOP/VDOP值计算失败: {e}")
            return float('inf'), float('inf')
    
    def _calculate_tdop_value(self, weight_matrix: np.ndarray) -> float:
        """计算TDOP值（时间精度衰减因子）"""
        try:
            # TDOP = √(q44)
            q44 = weight_matrix[3, 3]
            tdop = math.sqrt(q44)
            return tdop
            
        except Exception as e:
            logger.error(f"❌ TDOP值计算失败: {e}")
            return float('inf')
    
    def _evaluate_geometry_quality(self, gdop: float) -> str:
        """评估几何分布质量"""
        if gdop <= 1.0:
            return "优秀"
        elif gdop <= 2.0:
            return "良好"
        elif gdop <= 5.0:
            return "一般"
        elif gdop <= 10.0:
            return "较差"
        else:
            return "很差"
    
    def calculate_satellite_geometry_metrics(self, satellite_positions: List[Dict[str, Any]], 
                                           user_position: Dict[str, float]) -> Dict[str, Any]:
        """计算卫星几何分布指标"""
        try:
            logger.info(f"🔄 计算卫星几何分布指标")
            
            if len(satellite_positions) < 4:
                return {'success': False, 'error': '卫星数量不足'}
            
            # 计算卫星间的角度分布
            angles = self._calculate_satellite_angles(satellite_positions, user_position)
            
            # 计算卫星高度角分布
            elevation_angles = self._calculate_elevation_angles(satellite_positions, user_position)
            
            # 计算方位角分布
            azimuth_angles = self._calculate_azimuth_angles(satellite_positions, user_position)
            
            # 计算几何分布均匀性
            uniformity_score = self._calculate_distribution_uniformity(azimuth_angles, elevation_angles)
            
            return {
                'success': True,
                'satellite_angles': angles,
                'elevation_angles': elevation_angles,
                'azimuth_angles': azimuth_angles,
                'uniformity_score': uniformity_score,
                'min_elevation': min(elevation_angles) if elevation_angles else 0,
                'max_elevation': max(elevation_angles) if elevation_angles else 0,
                'elevation_spread': max(elevation_angles) - min(elevation_angles) if elevation_angles else 0
            }
            
        except Exception as e:
            logger.error(f"❌ 几何分布指标计算失败: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_satellite_angles(self, satellite_positions: List[Dict[str, Any]], 
                                  user_position: Dict[str, float]) -> List[float]:
        """计算卫星间夹角"""
        angles = []
        n = len(satellite_positions)
        
        for i in range(n):
            for j in range(i + 1, n):
                angle = self._calculate_angle_between_satellites(
                    satellite_positions[i], satellite_positions[j], user_position
                )
                angles.append(angle)
        
        return angles
    
    def _calculate_angle_between_satellites(self, sat1: Dict[str, Any], sat2: Dict[str, Any], 
                                         user: Dict[str, float]) -> float:
        """计算两颗卫星相对于用户的夹角"""
        try:
            # 用户到卫星1的向量
            v1 = np.array([sat1['x'] - user['x'], sat1['y'] - user['y'], sat1['z'] - user['z']])
            # 用户到卫星2的向量
            v2 = np.array([sat2['x'] - user['x'], sat2['y'] - user['y'], sat2['z'] - user['z']])
            
            # 计算夹角
            cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
            cos_angle = np.clip(cos_angle, -1.0, 1.0)  # 防止数值误差
            angle = math.acos(cos_angle) * 180.0 / math.pi
            
            return angle
            
        except Exception as e:
            logger.error(f"❌ 卫星夹角计算失败: {e}")
            return 0.0
    
    def _calculate_elevation_angles(self, satellite_positions: List[Dict[str, Any]], 
                                  user_position: Dict[str, float]) -> List[float]:
        """计算卫星高度角"""
        elevation_angles = []
        
        for sat_pos in satellite_positions:
            # 简化计算：假设用户在地面，计算相对高度角
            dx = sat_pos['x'] - user_position['x']
            dy = sat_pos['y'] - user_position['y']
            dz = sat_pos['z'] - user_position['z']
            
            horizontal_distance = math.sqrt(dx*dx + dy*dy)
            elevation = math.atan2(dz, horizontal_distance) * 180.0 / math.pi
            elevation_angles.append(elevation)
        
        return elevation_angles
    
    def _calculate_azimuth_angles(self, satellite_positions: List[Dict[str, Any]], 
                                user_position: Dict[str, float]) -> List[float]:
        """计算卫星方位角"""
        azimuth_angles = []
        
        for sat_pos in satellite_positions:
            dx = sat_pos['x'] - user_position['x']
            dy = sat_pos['y'] - user_position['y']
            
            azimuth = math.atan2(dy, dx) * 180.0 / math.pi
            if azimuth < 0:
                azimuth += 360.0
            azimuth_angles.append(azimuth)
        
        return azimuth_angles
    
    def _calculate_distribution_uniformity(self, azimuth_angles: List[float], 
                                         elevation_angles: List[float]) -> float:
        """计算分布均匀性分数"""
        try:
            if not azimuth_angles or not elevation_angles:
                return 0.0
            
            # 方位角均匀性（理想情况下应该均匀分布在0-360度）
            azimuth_std = np.std(azimuth_angles)
            azimuth_uniformity = max(0, 1.0 - azimuth_std / 180.0)
            
            # 高度角分布（理想情况下应该有一定的分散度）
            elevation_range = max(elevation_angles) - min(elevation_angles)
            elevation_uniformity = min(1.0, elevation_range / 90.0)
            
            # 综合均匀性分数
            uniformity_score = (azimuth_uniformity + elevation_uniformity) / 2.0
            
            return uniformity_score
            
        except Exception as e:
            logger.error(f"❌ 分布均匀性计算失败: {e}")
            return 0.0
