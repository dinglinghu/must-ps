"""
多智能体系统测试用例
验证协同决策、任务规划、结果输出等功能
"""

import unittest
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import sys

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.multi_agent_system import MultiAgentSystem
from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
from src.agents.satellite_agent import SatelliteAgent
from src.agents.leader_agent import LeaderAgent
from src.agents.coordination_manager import CoordinationManager
from src.agents.optimization_calculator import OptimizationCalculator
from google.adk.agents.invocation_context import InvocationContext
from google.genai import types


class TestMultiAgentSystem(unittest.TestCase):
    """多智能体系统测试类"""
    
    def setUp(self):
        """测试前准备"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = "config/config.yaml"
        
    def tearDown(self):
        """测试后清理"""
        if Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
    
    def test_multi_agent_system_initialization(self):
        """测试多智能体系统初始化"""
        try:
            system = MultiAgentSystem(
                config_path=self.config_path,
                output_dir=self.temp_dir
            )
            
            # 验证系统组件
            self.assertIsNotNone(system.simulation_scheduler)
            self.assertIsNotNone(system.coordination_manager)
            self.assertIsNotNone(system.optimization_calculator)
            self.assertIsNotNone(system.meta_task_integration)
            
            # 验证系统状态
            status = system.get_system_status()
            self.assertFalse(status['is_running'])
            self.assertEqual(status['satellite_agents_count'], 0)
            self.assertEqual(status['leader_agents_count'], 0)
            
            print("✅ 多智能体系统初始化测试通过")
            
        except Exception as e:
            self.fail(f"多智能体系统初始化失败: {e}")
    
    def test_simulation_scheduler_agent(self):
        """测试仿真调度智能体"""
        try:
            agent = SimulationSchedulerAgent(
                name="TestScheduler",
                model="mock-model"
            )
            
            # 验证智能体属性
            self.assertEqual(agent.name, "TestScheduler")
            self.assertEqual(agent.model, "mock-model")
            self.assertFalse(agent.is_running)
            self.assertEqual(agent.current_planning_cycle, 0)
            
            print("✅ 仿真调度智能体测试通过")
            
        except Exception as e:
            self.fail(f"仿真调度智能体测试失败: {e}")
    
    def test_satellite_agent(self):
        """测试卫星智能体"""
        try:
            agent = SatelliteAgent(
                satellite_id="TestSat_01",
                name="TestSatelliteAgent"
            )
            
            # 验证智能体属性
            self.assertEqual(agent.satellite_id, "TestSat_01")
            self.assertEqual(agent.name, "TestSatelliteAgent")
            self.assertIsNotNone(agent.memory_module)
            self.assertIsNotNone(agent.task_manager)
            self.assertIsNone(agent.current_leader)
            
            print("✅ 卫星智能体测试通过")
            
        except Exception as e:
            self.fail(f"卫星智能体测试失败: {e}")
    
    def test_leader_agent(self):
        """测试组长智能体"""
        try:
            agent = LeaderAgent(
                name="TestLeader",
                target_id="TestTarget_01",
                model="mock-model"
            )
            
            # 验证智能体属性
            self.assertEqual(agent.name, "TestLeader")
            self.assertEqual(agent.target_id, "TestTarget_01")
            self.assertIsNone(agent.discussion_group)
            self.assertEqual(len(agent.member_agents), 0)
            self.assertEqual(len(agent.visibility_windows), 0)
            
            print("✅ 组长智能体测试通过")
            
        except Exception as e:
            self.fail(f"组长智能体测试失败: {e}")
    
    def test_coordination_manager(self):
        """测试协调管理器"""
        try:
            manager = CoordinationManager()
            
            # 验证管理器属性
            self.assertEqual(len(manager.registered_agents), 0)
            self.assertEqual(len(manager.active_sessions), 0)
            self.assertEqual(len(manager.message_queue), 0)
            
            # 测试智能体注册
            agent = SatelliteAgent("TestSat_01")
            manager.register_agent(agent)
            self.assertEqual(len(manager.registered_agents), 1)
            self.assertIn("Agent_TestSat_01", manager.registered_agents)
            
            # 测试智能体注销
            manager.unregister_agent("Agent_TestSat_01")
            self.assertEqual(len(manager.registered_agents), 0)
            
            print("✅ 协调管理器测试通过")
            
        except Exception as e:
            self.fail(f"协调管理器测试失败: {e}")
    
    def test_optimization_calculator(self):
        """测试优化计算器"""
        try:
            calculator = OptimizationCalculator()
            
            # 测试GDOP计算
            target_pos = (40.0, 116.0, 200000)  # 北京上空200km
            satellite_positions = [
                ("Sat1", 41.0, 117.0, 1800000),  # 1800km轨道
                ("Sat2", 39.0, 115.0, 1800000)
            ]
            time_window = (datetime.now(), datetime.now() + timedelta(minutes=10))
            
            gdop_results = calculator.calculate_gdop(
                target_pos, satellite_positions, time_window
            )
            
            self.assertIsInstance(gdop_results, list)
            if gdop_results:
                result = gdop_results[0]
                self.assertIsNotNone(result.gdop_value)
                self.assertIsNotNone(result.tracking_accuracy)
            
            # 测试调度性评估
            current_tasks = [
                {'task_id': 'task1', 'status': 'executing', 'start_time': datetime.now()}
            ]
            new_task = {
                'task_id': 'task2',
                'start_time': datetime.now() + timedelta(minutes=5),
                'end_time': datetime.now() + timedelta(minutes=15),
                'required_power': 0.3
            }
            resource_status = {
                'power_level': 0.8,
                'payload_status': 'operational',
                'communication_status': 'active'
            }
            
            schedulability_result = calculator.evaluate_schedulability(
                "TestSat_01", current_tasks, new_task, resource_status
            )
            
            self.assertIsNotNone(schedulability_result.schedulability_score)
            self.assertGreaterEqual(schedulability_result.schedulability_score, 0.0)
            self.assertLessEqual(schedulability_result.schedulability_score, 1.0)
            
            print("✅ 优化计算器测试通过")
            
        except Exception as e:
            self.fail(f"优化计算器测试失败: {e}")
    
    async def test_agent_coordination_flow(self):
        """测试智能体协调流程"""
        try:
            # 创建协调管理器
            coord_manager = CoordinationManager()
            
            # 创建智能体
            leader = LeaderAgent("Leader_Target01", "Target01")
            satellite1 = SatelliteAgent("Sat01")
            satellite2 = SatelliteAgent("Sat02")
            
            # 注册智能体
            coord_manager.register_agent(leader)
            coord_manager.register_agent(satellite1)
            coord_manager.register_agent(satellite2)
            
            # 创建协调会话
            ctx = InvocationContext()
            success = await coord_manager.create_coordination_session(
                session_id="test_session",
                participants=["Agent_Sat01", "Agent_Sat02"],
                coordinator="Leader_Target01",
                topic="测试协调",
                ctx=ctx
            )
            
            self.assertTrue(success)
            self.assertEqual(len(coord_manager.active_sessions), 1)
            
            # 发送测试消息
            from src.agents.coordination_manager import MessageType
            
            message_id = await coord_manager.send_message(
                sender_id="Leader_Target01",
                receiver_id="Agent_Sat01",
                message_type=MessageType.COORDINATION_REQUEST,
                content={'request_type': 'resource_check'},
                priority=2
            )
            
            self.assertIsNotNone(message_id)
            self.assertEqual(len(coord_manager.message_queue), 1)
            
            # 处理消息
            events = await coord_manager.process_messages(ctx)
            self.assertIsInstance(events, list)
            
            # 结束协调会话
            success = await coord_manager.end_coordination_session(
                session_id="test_session",
                results={'status': 'completed'},
                ctx=ctx
            )
            
            self.assertTrue(success)
            self.assertEqual(len(coord_manager.active_sessions), 0)
            
            print("✅ 智能体协调流程测试通过")
            
        except Exception as e:
            self.fail(f"智能体协调流程测试失败: {e}")
    
    async def test_system_integration(self):
        """测试系统集成"""
        try:
            # 创建多智能体系统
            system = MultiAgentSystem(
                config_path=self.config_path,
                output_dir=self.temp_dir
            )
            
            # 创建调用上下文
            ctx = InvocationContext()
            
            # 模拟运行一个简短的仿真周期
            event_count = 0
            max_events = 5  # 限制事件数量以避免长时间运行
            
            async for event in system.run_async(ctx):
                event_count += 1
                
                # 验证事件结构
                self.assertIsNotNone(event.author)
                
                if event.content and event.content.parts:
                    content_text = event.content.parts[0].text
                    self.assertIsInstance(content_text, str)
                
                # 限制事件数量
                if event_count >= max_events or event.is_final_response():
                    break
            
            # 验证系统状态
            status = system.get_system_status()
            self.assertIsNotNone(status['current_simulation_id'])
            self.assertIsNotNone(status['output_directory'])
            
            print("✅ 系统集成测试通过")
            
        except Exception as e:
            self.fail(f"系统集成测试失败: {e}")


class TestAsyncMethods(unittest.IsolatedAsyncioTestCase):
    """异步方法测试类"""
    
    async def test_agent_coordination_flow(self):
        """测试智能体协调流程（异步）"""
        test_case = TestMultiAgentSystem()
        test_case.setUp()
        try:
            await test_case.test_agent_coordination_flow()
        finally:
            test_case.tearDown()
    
    async def test_system_integration(self):
        """测试系统集成（异步）"""
        test_case = TestMultiAgentSystem()
        test_case.setUp()
        try:
            await test_case.test_system_integration()
        finally:
            test_case.tearDown()


def run_tests():
    """运行所有测试"""
    print("🧪 开始多智能体系统测试")
    print("=" * 50)
    
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加同步测试
    suite.addTests(loader.loadTestsFromTestCase(TestMultiAgentSystem))
    
    # 运行同步测试
    runner = unittest.TextTestRunner(verbosity=2)
    sync_result = runner.run(suite)
    
    # 运行异步测试
    print("\n🔄 运行异步测试...")
    async_test_case = TestAsyncMethods()
    
    try:
        asyncio.run(async_test_case.test_agent_coordination_flow())
        print("✅ 异步协调流程测试通过")
    except Exception as e:
        print(f"❌ 异步协调流程测试失败: {e}")
    
    try:
        asyncio.run(async_test_case.test_system_integration())
        print("✅ 异步系统集成测试通过")
    except Exception as e:
        print(f"❌ 异步系统集成测试失败: {e}")
    
    print("\n" + "=" * 50)
    print(f"🧪 测试完成")
    print(f"   - 运行测试: {sync_result.testsRun}")
    print(f"   - 失败: {len(sync_result.failures)}")
    print(f"   - 错误: {len(sync_result.errors)}")
    
    return sync_result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
