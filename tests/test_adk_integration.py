"""
ADK框架集成测试
测试整个多智能体系统的ADK集成、讨论组功能、任务分发机制和UI监控功能
"""

import pytest
import pytest_asyncio
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入测试目标
from src.agents.satellite_agent_factory import SatelliteAgentFactory
from src.agents.missile_target_distributor import MissileTargetDistributor, MissileTarget
from src.agents.adk_parallel_discussion_group import ADKParallelDiscussionGroupManager
from src.agents.rolling_planning_cycle_manager import RollingPlanningCycleManager
from src.agents.satellite_agent import TaskInfo
from src.constellation.constellation_manager import ConstellationManager
from src.utils.config_manager import get_config_manager
from src.utils.time_manager import get_time_manager

logger = logging.getLogger(__name__)


class TestADKIntegration:
    """ADK框架集成测试类"""
    
    @pytest_asyncio.fixture
    async def setup_system(self):
        """设置测试系统"""
        # 获取配置管理器
        config_manager = get_config_manager()
        time_manager = get_time_manager(config_manager)
        
        # 创建星座管理器
        constellation_manager = ConstellationManager(config_manager)
        
        # 创建卫星智能体工厂
        satellite_factory = SatelliteAgentFactory(config_manager)
        
        # 创建导弹分发器
        missile_distributor = MissileTargetDistributor(config_manager)
        
        # 创建讨论组管理器
        discussion_group_manager = ADKParallelDiscussionGroupManager(config_manager)
        
        # 创建规划周期管理器
        planning_cycle_manager = RollingPlanningCycleManager(config_manager)
        planning_cycle_manager.set_satellite_factory(satellite_factory)
        
        return {
            'config_manager': config_manager,
            'time_manager': time_manager,
            'constellation_manager': constellation_manager,
            'satellite_factory': satellite_factory,
            'missile_distributor': missile_distributor,
            'discussion_group_manager': discussion_group_manager,
            'planning_cycle_manager': planning_cycle_manager
        }
    
    @pytest.mark.asyncio
    async def test_satellite_agent_factory_creation(self, setup_system):
        """测试卫星智能体工厂创建Walker星座智能体"""
        system = setup_system
        
        satellite_factory = system['satellite_factory']
        constellation_manager = system['constellation_manager']
        
        # 创建Walker星座对应的ADK智能体
        satellite_agents = await satellite_factory.create_satellite_agents_from_walker_constellation(
            constellation_manager
        )
        
        # 验证创建结果
        assert len(satellite_agents) > 0, "应该创建至少一个卫星智能体"
        
        # 验证一对一映射
        expected_count = 9  # 3个轨道面 × 3颗卫星
        assert len(satellite_agents) == expected_count, f"应该创建 {expected_count} 个卫星智能体"
        
        # 验证智能体属性
        for satellite_id, agent in satellite_agents.items():
            assert agent.satellite_id == satellite_id, "卫星ID应该匹配"
            assert hasattr(agent, 'orbital_parameters'), "应该有轨道参数"
            assert hasattr(agent, 'payload_config'), "应该有载荷配置"
        
        # 验证映射完整性
        assert satellite_factory.validate_constellation_mapping(), "星座映射应该完整"
        
        logger.info(f"✅ 卫星智能体工厂测试通过，创建了 {len(satellite_agents)} 个智能体")
    
    @pytest.mark.asyncio
    async def test_missile_target_distribution(self, setup_system):
        """测试导弹目标分发机制"""
        system = setup_system
        
        satellite_factory = system['satellite_factory']
        constellation_manager = system['constellation_manager']
        missile_distributor = system['missile_distributor']
        
        # 创建卫星智能体
        satellite_agents = await satellite_factory.create_satellite_agents_from_walker_constellation(
            constellation_manager
        )
        
        # 创建模拟导弹目标
        missile_targets = []
        for i in range(3):
            missile = MissileTarget(
                missile_id=f"missile_{i+1}",
                launch_position={'lat': 40.0 + i, 'lon': 116.0 + i, 'alt': 0.0},
                target_position={'lat': 50.0 + i, 'lon': 126.0 + i, 'alt': 0.0},
                launch_time=datetime.now(),
                flight_time=600.0,
                trajectory_points=[
                    {'position': {'lat': 40.0 + i + j*0.1, 'lon': 116.0 + i + j*0.1, 'alt': j*10}, 'time': datetime.now()}
                    for j in range(10)
                ],
                priority=0.8,
                threat_level='high',
                metadata={}
            )
            missile_targets.append(missile)
        
        # 执行分发
        distribution_result = await missile_distributor.distribute_missiles_to_satellites(
            missile_targets, satellite_agents
        )
        
        # 验证分发结果
        assert len(distribution_result) > 0, "应该有分发结果"
        
        # 验证所有导弹都被分配
        total_assigned_missiles = sum(len(missiles) for missiles in distribution_result.values())
        assert total_assigned_missiles == len(missile_targets), "所有导弹都应该被分配"
        
        # 验证分配的合理性
        for satellite_id, missile_ids in distribution_result.items():
            if missile_ids:
                assert satellite_id in satellite_agents, "分配的卫星应该存在"
        
        logger.info(f"✅ 导弹目标分发测试通过，分配了 {total_assigned_missiles} 个导弹")
    
    @pytest.mark.asyncio
    async def test_adk_parallel_discussion_group(self, setup_system):
        """测试ADK Parallel Fan-Out/Gather Pattern讨论组"""
        system = setup_system
        
        satellite_factory = system['satellite_factory']
        constellation_manager = system['constellation_manager']
        discussion_group_manager = system['discussion_group_manager']
        
        # 创建卫星智能体
        satellite_agents = await satellite_factory.create_satellite_agents_from_walker_constellation(
            constellation_manager
        )
        
        # 选择参与讨论的卫星
        agent_list = list(satellite_agents.values())
        leader_satellite = agent_list[0]
        member_satellites = agent_list[1:3]  # 选择2个组员
        
        # 创建任务
        task = TaskInfo(
            task_id="test_task_001",
            target_id="test_missile_001",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=30),
            priority=0.9,
            status='pending',
            metadata={'test': True}
        )
        
        # 创建讨论组
        discussion_group = await discussion_group_manager.create_discussion_group_for_planning_cycle(
            task=task,
            leader_satellite=leader_satellite,
            member_satellites=member_satellites
        )
        
        # 验证讨论组创建
        assert discussion_group is not None, "应该成功创建讨论组"
        assert discussion_group.leader_satellite == leader_satellite, "组长应该正确"
        assert len(discussion_group.member_satellites) == len(member_satellites), "组员数量应该正确"
        assert discussion_group.task.task_id == task.task_id, "任务应该正确关联"
        
        # 验证一次只有一个讨论组的限制
        current_group = discussion_group_manager.get_current_discussion_group()
        assert current_group == discussion_group, "当前讨论组应该是刚创建的"
        
        # 尝试创建第二个讨论组（应该关闭第一个）
        task2 = TaskInfo(
            task_id="test_task_002",
            target_id="test_missile_002",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=30),
            priority=0.8,
            status='pending',
            metadata={'test': True}
        )
        
        discussion_group2 = await discussion_group_manager.create_discussion_group_for_planning_cycle(
            task=task2,
            leader_satellite=agent_list[2],
            member_satellites=[agent_list[3]] if len(agent_list) > 3 else []
        )
        
        # 验证只有一个活跃讨论组
        current_group = discussion_group_manager.get_current_discussion_group()
        assert current_group == discussion_group2, "当前讨论组应该是新创建的"
        assert discussion_group_manager.get_active_groups_count() == 1, "应该只有一个活跃讨论组"
        
        logger.info("✅ ADK Parallel讨论组测试通过")
    
    @pytest.mark.asyncio
    async def test_rolling_planning_cycle_management(self, setup_system):
        """测试滚动任务规划周期管理"""
        system = setup_system
        
        satellite_factory = system['satellite_factory']
        constellation_manager = system['constellation_manager']
        planning_cycle_manager = system['planning_cycle_manager']
        
        # 创建卫星智能体
        satellite_agents = await satellite_factory.create_satellite_agents_from_walker_constellation(
            constellation_manager
        )
        
        # 启动滚动规划
        success = await planning_cycle_manager.start_rolling_planning()
        assert success, "应该成功启动滚动规划"
        assert planning_cycle_manager.is_running, "滚动规划应该在运行"
        
        # 创建模拟导弹目标
        missile_targets = [
            MissileTarget(
                missile_id="test_missile_001",
                launch_position={'lat': 40.0, 'lon': 116.0, 'alt': 0.0},
                target_position={'lat': 50.0, 'lon': 126.0, 'alt': 0.0},
                launch_time=datetime.now(),
                flight_time=600.0,
                trajectory_points=[
                    {'position': {'lat': 40.0 + j*0.1, 'lon': 116.0 + j*0.1, 'alt': j*10}, 'time': datetime.now()}
                    for j in range(5)
                ],
                priority=0.9,
                threat_level='high',
                metadata={}
            )
        ]
        
        # 模拟规划周期触发（通过修改下次规划时间）
        planning_cycle_manager._next_cycle_time = datetime.now() - timedelta(seconds=1)
        
        # 执行规划周期
        cycle_info = await planning_cycle_manager.check_and_execute_planning_cycle(missile_targets)
        
        # 验证规划周期执行
        if cycle_info:  # 可能因为时间条件不满足而返回None
            assert cycle_info.cycle_number > 0, "周期编号应该大于0"
            assert len(cycle_info.detected_missiles) == len(missile_targets), "检测到的导弹数量应该正确"
            assert cycle_info.state.value in ['completed', 'error'], "周期应该完成或出错"
        
        # 停止滚动规划
        await planning_cycle_manager.stop_rolling_planning()
        assert not planning_cycle_manager.is_running, "滚动规划应该停止"
        
        logger.info("✅ 滚动规划周期管理测试通过")
    
    @pytest.mark.asyncio
    async def test_system_integration(self, setup_system):
        """测试整个系统集成"""
        system = setup_system
        
        satellite_factory = system['satellite_factory']
        constellation_manager = system['constellation_manager']
        missile_distributor = system['missile_distributor']
        discussion_group_manager = system['discussion_group_manager']
        planning_cycle_manager = system['planning_cycle_manager']
        
        # 1. 创建Walker星座智能体
        satellite_agents = await satellite_factory.create_satellite_agents_from_walker_constellation(
            constellation_manager
        )
        assert len(satellite_agents) > 0, "应该创建卫星智能体"
        
        # 2. 创建导弹目标
        missile_targets = [
            MissileTarget(
                missile_id=f"integration_missile_{i}",
                launch_position={'lat': 40.0 + i, 'lon': 116.0 + i, 'alt': 0.0},
                target_position={'lat': 50.0 + i, 'lon': 126.0 + i, 'alt': 0.0},
                launch_time=datetime.now(),
                flight_time=600.0,
                trajectory_points=[
                    {'position': {'lat': 40.0 + i + j*0.1, 'lon': 116.0 + i + j*0.1, 'alt': j*10}, 'time': datetime.now()}
                    for j in range(3)
                ],
                priority=0.8,
                threat_level='medium',
                metadata={}
            )
            for i in range(2)
        ]
        
        # 3. 分发导弹目标
        distribution_result = await missile_distributor.distribute_missiles_to_satellites(
            missile_targets, satellite_agents
        )
        assert len(distribution_result) > 0, "应该有分发结果"
        
        # 4. 创建讨论组
        assigned_satellites = [sat_id for sat_id, missiles in distribution_result.items() if missiles]
        if assigned_satellites:
            leader_id = assigned_satellites[0]
            leader_satellite = satellite_agents[leader_id]
            member_satellites = [satellite_agents[sat_id] for sat_id in assigned_satellites[1:2]]
            
            task = TaskInfo(
                task_id="integration_test_task",
                target_id=missile_targets[0].missile_id,
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(minutes=30),
                priority=0.8,
                status='pending',
                metadata={'integration_test': True}
            )
            
            discussion_group = await discussion_group_manager.create_discussion_group_for_planning_cycle(
                task=task,
                leader_satellite=leader_satellite,
                member_satellites=member_satellites
            )
            
            assert discussion_group is not None, "应该成功创建讨论组"
        
        # 5. 验证系统状态
        assert satellite_factory.get_satellite_count() > 0, "应该有卫星智能体"
        assert discussion_group_manager.get_active_groups_count() <= 1, "应该最多有一个活跃讨论组"
        
        logger.info("✅ 系统集成测试通过")
    
    def test_adk_framework_compliance(self):
        """测试ADK框架合规性"""
        # 验证所有智能体都继承自ADK BaseAgent
        from src.agents.satellite_agent import SatelliteAgent
        from src.agents.missile_target_distributor import MissileTargetDistributor
        from src.agents.rolling_planning_cycle_manager import RollingPlanningCycleManager
        from google.adk.agents import BaseAgent
        
        # 检查继承关系
        assert issubclass(SatelliteAgent, BaseAgent), "SatelliteAgent应该继承自ADK BaseAgent"
        assert issubclass(MissileTargetDistributor, BaseAgent), "MissileTargetDistributor应该继承自ADK BaseAgent"
        assert issubclass(RollingPlanningCycleManager, BaseAgent), "RollingPlanningCycleManager应该继承自ADK BaseAgent"
        
        # 验证ADK导入
        try:
            from google.adk.agents import BaseAgent, LlmAgent, ParallelAgent, SequentialAgent
            from google.adk.agents.invocation_context import InvocationContext
            from google.adk.events import Event, EventActions
            from google.genai import types
            logger.info("✅ ADK框架导入验证通过")
        except ImportError as e:
            pytest.fail(f"ADK框架导入失败: {e}")
        
        logger.info("✅ ADK框架合规性测试通过")


if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行测试
    pytest.main([__file__, "-v", "-s"])
