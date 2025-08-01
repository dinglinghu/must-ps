"""
卫星智能体工厂
基于ADK框架实现Walker星座卫星到ADK智能体的一对一映射
严格按照ADK官方文档要求实现
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from .satellite_agent import SatelliteAgent
from ..constellation.constellation_manager import ConstellationManager
from ..utils.config_manager import get_config_manager
from ..utils.time_manager import get_time_manager
from ..utils.llm_config_manager import get_llm_config_manager

logger = logging.getLogger(__name__)
logger.info("使用真实ADK框架于卫星智能体工厂")


class SatelliteAgentFactory:
    """
    卫星智能体工厂
    
    负责创建和管理Walker星座中每颗卫星对应的ADK智能体实例，
    确保一对一的映射关系，严格按照ADK框架设计模式实现。
    """
    
    def __init__(self, config_manager=None):
        """
        初始化卫星智能体工厂

        Args:
            config_manager: 配置管理器实例
        """
        self._config_manager = config_manager or get_config_manager()
        self._time_manager = get_time_manager(self._config_manager)
        self._llm_config_manager = get_llm_config_manager()

        # 获取星座配置
        self._constellation_config = self._config_manager.config.get('constellation', {})
        self._satellite_config = self._config_manager.config.get('multi_agent_system', {}).get('satellite_agents', {})

        # STK管理器（可由外部设置以确保连接一致性）
        self._stk_manager = None

        # 多智能体系统引用（用于卫星智能体间通信）
        self._multi_agent_system = None

        # 卫星智能体注册表 - 确保一对一映射
        self._satellite_agents: Dict[str, SatelliteAgent] = {}
        self._stk_satellite_mapping: Dict[str, str] = {}  # STK卫星ID -> 智能体ID映射

        # 星座管理器
        self._constellation_manager = None

        logger.info("卫星智能体工厂初始化完成")

    def set_stk_manager(self, stk_manager):
        """
        设置STK管理器实例

        Args:
            stk_manager: STK管理器实例
        """
        self._stk_manager = stk_manager
        logger.info("✅ 卫星智能体工厂已设置STK管理器")

    def set_multi_agent_system(self, multi_agent_system):
        """
        设置多智能体系统引用

        Args:
            multi_agent_system: 多智能体系统实例
        """
        self._multi_agent_system = multi_agent_system
        logger.info("✅ 卫星智能体工厂已设置多智能体系统引用")

    def get_satellite_agent(self, satellite_id: str) -> Optional[SatelliteAgent]:
        """
        获取已创建的卫星智能体

        Args:
            satellite_id: 卫星ID

        Returns:
            卫星智能体实例，如果不存在则返回None
        """
        return self._satellite_agents.get(satellite_id)

    def get_all_satellite_agents(self) -> Dict[str, SatelliteAgent]:
        """
        获取所有已创建的卫星智能体

        Returns:
            卫星智能体字典
        """
        return self._satellite_agents.copy()

    def get_satellite_count(self) -> int:
        """
        获取已创建的卫星智能体数量

        Returns:
            卫星智能体数量
        """
        return len(self._satellite_agents)

    async def create_satellite_agents_from_walker_constellation(
        self,
        constellation_manager: ConstellationManager,
        stk_manager=None
    ) -> Dict[str, SatelliteAgent]:
        """
        从Walker星座创建对应的ADK卫星智能体

        Args:
            constellation_manager: 星座管理器实例
            stk_manager: STK管理器实例（可选，用于确保连接一致性）

        Returns:
            卫星智能体字典 {satellite_id: SatelliteAgent}
        """
        try:
            self._constellation_manager = constellation_manager

            # 设置STK管理器（如果提供）
            if stk_manager:
                self._stk_manager = stk_manager
                logger.info("✅ 使用传入的STK管理器实例")

            # 获取Walker星座信息
            constellation_info = await self._get_walker_constellation_info()
            if not constellation_info:
                logger.error("❌ 无法获取Walker星座信息")
                return {}
            
            logger.info(f"🛰️ 开始为Walker星座创建ADK智能体，总卫星数: {len(constellation_info)}")
            
            # 为每颗卫星创建对应的ADK智能体
            created_agents = {}
            for satellite_info in constellation_info:
                agent = await self._create_single_satellite_agent(satellite_info)
                if agent:
                    created_agents[agent.satellite_id] = agent
                    self._satellite_agents[agent.satellite_id] = agent
                    self._stk_satellite_mapping[satellite_info['stk_id']] = agent.satellite_id
            
            logger.info(f"✅ 成功创建 {len(created_agents)} 个卫星智能体")
            return created_agents
            
        except Exception as e:
            logger.error(f"❌ 创建卫星智能体失败: {e}")
            return {}
    
    async def _get_walker_constellation_info(self) -> List[Dict[str, Any]]:
        """
        获取Walker星座信息
        
        Returns:
            星座信息列表
        """
        try:
            if not self._constellation_manager:
                logger.error("❌ 星座管理器未初始化")
                return []
            
            # 从星座管理器获取卫星信息
            satellites_info = []
            
            # 根据配置生成Walker星座卫星信息
            planes = self._constellation_config.get('planes', 3)
            satellites_per_plane = self._constellation_config.get('satellites_per_plane', 3)
            
            satellite_index = 1
            for plane_idx in range(planes):
                for sat_idx in range(satellites_per_plane):
                    # 使用与STK一致的命名格式：Satellite{轨道面编号}{卫星编号}
                    satellite_id = f"Satellite{plane_idx+1}{sat_idx+1}"

                    satellite_info = {
                        'satellite_id': satellite_id,
                        'stk_id': satellite_id,  # 确保与STK中的命名一致
                        'plane_index': plane_idx,
                        'satellite_index_in_plane': sat_idx,
                        'global_index': satellite_index,
                        'orbital_parameters': self._calculate_orbital_parameters(plane_idx, sat_idx),
                        'payload_config': self._get_payload_config(),
                        'created_at': self._time_manager.get_current_simulation_time()
                    }
                    satellites_info.append(satellite_info)
                    satellite_index += 1
            
            logger.info(f"📡 生成Walker星座信息: {len(satellites_info)} 颗卫星")
            return satellites_info
            
        except Exception as e:
            logger.error(f"❌ 获取Walker星座信息失败: {e}")
            return []
    
    def _calculate_orbital_parameters(self, plane_idx: int, sat_idx: int) -> Dict[str, float]:
        """
        计算Walker星座轨道参数
        
        Args:
            plane_idx: 轨道面索引
            sat_idx: 轨道面内卫星索引
            
        Returns:
            轨道参数字典
        """
        ref_params = self._constellation_config.get('reference_satellite', {})
        planes = self._constellation_config.get('planes', 3)
        satellites_per_plane = self._constellation_config.get('satellites_per_plane', 3)
        
        # Walker星座参数计算
        raan_offset = ref_params.get('raan_offset', 24)
        mean_anomaly_offset = ref_params.get('mean_anomaly_offset', 180)
        
        # 升交点赤经 (RAAN)
        raan = (plane_idx * 360.0 / planes) % 360.0
        
        # 平近点角 (Mean Anomaly)
        mean_anomaly = (sat_idx * 360.0 / satellites_per_plane + 
                       plane_idx * mean_anomaly_offset / planes) % 360.0
        
        return {
            'altitude': ref_params.get('altitude', 1800),
            'inclination': ref_params.get('inclination', 51.856),
            'eccentricity': ref_params.get('eccentricity', 0.0),
            'arg_of_perigee': ref_params.get('arg_of_perigee', 12),
            'raan': raan,
            'mean_anomaly': mean_anomaly
        }
    
    def _get_payload_config(self) -> Dict[str, Any]:
        """
        获取载荷配置
        
        Returns:
            载荷配置字典
        """
        return self._config_manager.config.get('payload', {})
    
    async def _create_single_satellite_agent(self, satellite_info: Dict[str, Any]) -> Optional[SatelliteAgent]:
        """
        创建单个卫星智能体
        
        Args:
            satellite_info: 卫星信息
            
        Returns:
            创建的卫星智能体实例
        """
        try:
            satellite_id = satellite_info['satellite_id']
            
            # 检查是否已存在
            if satellite_id in self._satellite_agents:
                logger.warning(f"⚠️ 卫星智能体 {satellite_id} 已存在，跳过创建")
                return self._satellite_agents[satellite_id]
            
            # 获取LLM配置
            llm_config = self._llm_config_manager.get_llm_config('satellite_agents')
            
            # 创建卫星智能体实例，传递STK管理器和多智能体系统引用以确保连接一致性
            agent = SatelliteAgent(
                satellite_id=satellite_id,
                name=satellite_id,  # 统一名称格式：直接使用satellite_id
                config={
                    'orbital_parameters': satellite_info['orbital_parameters'],
                    'payload_config': satellite_info['payload_config']
                },
                stk_manager=self._stk_manager,  # 关键修复：传递共享的STK管理器
                multi_agent_system=self._multi_agent_system  # 传递多智能体系统引用
            )
            
            logger.info(f"✅ 成功创建卫星智能体: {satellite_id}")
            return agent
            
        except Exception as e:
            logger.error(f"❌ 创建卫星智能体 {satellite_info.get('satellite_id', 'Unknown')} 失败: {e}")
            return None
    
    def get_satellite_agent(self, satellite_id: str) -> Optional[SatelliteAgent]:
        """
        获取指定的卫星智能体
        
        Args:
            satellite_id: 卫星ID
            
        Returns:
            卫星智能体实例
        """
        return self._satellite_agents.get(satellite_id)
    
    def get_all_satellite_agents(self) -> Dict[str, SatelliteAgent]:
        """
        获取所有卫星智能体
        
        Returns:
            所有卫星智能体字典
        """
        return self._satellite_agents.copy()
    
    def get_stk_satellite_mapping(self) -> Dict[str, str]:
        """
        获取STK卫星ID到智能体ID的映射

        Returns:
            映射字典
        """
        return self._stk_satellite_mapping.copy()

    async def delegate_discussion_group_creation(
        self,
        missile_info: Dict[str, Any],
        participant_list: List[str]
    ) -> str:
        """
        委托卫星智能体创建讨论组

        Args:
            missile_info: 导弹信息
            participant_list: 参与者列表

        Returns:
            创建结果描述
        """
        try:
            if not participant_list:
                return "❌ 参与者列表为空"

            # 选择第一颗卫星作为组长
            leader_satellite_id = participant_list[0]
            leader_satellite = self.get_satellite_agent(leader_satellite_id)

            if not leader_satellite:
                return f"❌ 无法找到组长卫星智能体: {leader_satellite_id}"

            logger.info(f"🎯 委托卫星 {leader_satellite_id} 创建讨论组，参与者: {participant_list}")

            # 创建任务信息
            from .satellite_agent import TaskInfo
            from ..utils.time_manager import get_time_manager
            from datetime import timedelta

            time_manager = get_time_manager(self._config_manager)
            missile_id = missile_info['missile_id']

            task_info = TaskInfo(
                task_id=f"TRACK_{missile_id}",
                target_id=missile_id,
                priority=0.9,
                start_time=time_manager.get_current_simulation_time(),
                end_time=time_manager.get_current_simulation_time() + timedelta(hours=2),
                status="pending",
                metadata={
                    "task_type": "collaborative_tracking",
                    "description": f"协同跟踪导弹 {missile_id}",
                    "missile_info": missile_info,
                    "requires_discussion": True,
                    "coordination_level": "high",
                    "participant_list": participant_list,
                    "created_by": "satellite_factory"
                }
            )

            # 委托给组长卫星智能体
            await leader_satellite.receive_task(task_info, missile_info)

            return f"✅ 已委托卫星 {leader_satellite_id} 创建讨论组"

        except Exception as e:
            logger.error(f"❌ 委托创建讨论组失败: {e}")
            return f"❌ 委托创建讨论组失败: {e}"
    
    async def update_satellite_positions(self, positions_data: Dict[str, Any]):
        """
        更新所有卫星的位置信息
        
        Args:
            positions_data: 位置数据
        """
        try:
            for satellite_id, agent in self._satellite_agents.items():
                if satellite_id in positions_data:
                    await agent.update_position(positions_data[satellite_id])
                    
        except Exception as e:
            logger.error(f"❌ 更新卫星位置失败: {e}")
    
    def get_satellite_count(self) -> int:
        """
        获取卫星智能体数量
        
        Returns:
            卫星数量
        """
        return len(self._satellite_agents)
    
    def validate_constellation_mapping(self) -> bool:
        """
        验证星座映射的完整性
        
        Returns:
            映射是否完整
        """
        expected_count = (self._constellation_config.get('planes', 3) * 
                         self._constellation_config.get('satellites_per_plane', 3))
        actual_count = len(self._satellite_agents)
        
        is_valid = expected_count == actual_count
        
        if is_valid:
            logger.info(f"✅ 星座映射验证通过: {actual_count}/{expected_count}")
        else:
            logger.error(f"❌ 星座映射验证失败: {actual_count}/{expected_count}")
        
        return is_valid
