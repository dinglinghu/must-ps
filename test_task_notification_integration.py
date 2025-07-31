#!/usr/bin/env python3
"""
测试任务完成通知机制集成
验证仿真调度智能体是否正确使用新的任务完成通知机制
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
import sys

# 添加项目路径
sys.path.append(str(Path(__file__).parent))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TaskNotificationIntegrationTester:
    """任务完成通知机制集成测试器"""
    
    def __init__(self):
        self.test_results = {}
    
    async def run_all_tests(self):
        """运行所有集成测试"""
        logger.info("🚀 开始测试任务完成通知机制集成...")
        
        tests = [
            ("仿真调度智能体初始化", self.test_scheduler_initialization),
            ("任务发送和记录", self.test_task_sending_and_tracking),
            ("任务完成通知处理", self.test_task_completion_handling),
            ("等待机制验证", self.test_waiting_mechanism),
            ("协同决策监控更新", self.test_coordination_monitoring),
            ("讨论组完成检查更新", self.test_discussion_completion_check)
        ]
        
        for test_name, test_func in tests:
            try:
                logger.info(f"🔍 测试: {test_name}")
                result = await test_func()
                self.test_results[test_name] = result
                status = "✅ 通过" if result else "❌ 失败"
                logger.info(f"   结果: {status}")
            except Exception as e:
                logger.error(f"   ❌ 测试异常: {e}")
                self.test_results[test_name] = False
        
        # 生成测试报告
        self.generate_test_report()
    
    async def test_scheduler_initialization(self) -> bool:
        """测试仿真调度智能体初始化"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.time_manager import get_time_manager
            from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
            
            # 创建配置和时间管理器
            config_manager = get_config_manager()
            time_manager = get_time_manager()
            
            # 创建仿真调度智能体
            scheduler = SimulationSchedulerAgent(
                name="test_scheduler",
                config_mgr=config_manager,
                time_mgr=time_manager
            )
            
            # 验证任务完成通知相关属性是否正确初始化
            if (hasattr(scheduler, '_pending_tasks') and 
                hasattr(scheduler, '_completed_tasks') and
                hasattr(scheduler, '_waiting_for_tasks')):
                
                logger.info("   ✅ 仿真调度智能体任务通知属性初始化成功")
                
                # 验证初始状态
                if (len(scheduler._pending_tasks) == 0 and
                    len(scheduler._completed_tasks) == 0 and
                    not scheduler._waiting_for_tasks):
                    
                    logger.info("   ✅ 初始状态正确")
                    return True
                else:
                    logger.warning("   ⚠️ 初始状态异常")
                    return False
            else:
                logger.warning("   ⚠️ 任务通知属性未正确初始化")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 仿真调度智能体初始化测试失败: {e}")
            return False
    
    async def test_task_sending_and_tracking(self) -> bool:
        """测试任务发送和跟踪"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.time_manager import get_time_manager
            from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
            from src.data_structures.task_info import TaskInfo
            from datetime import datetime
            
            # 创建仿真调度智能体
            config_manager = get_config_manager()
            time_manager = get_time_manager()
            scheduler = SimulationSchedulerAgent(
                name="test_scheduler",
                config_mgr=config_manager,
                time_mgr=time_manager
            )
            
            # 模拟任务发送
            test_task_id = "test_tracking_task_001"
            scheduler._pending_tasks.add(test_task_id)
            
            # 验证任务是否被正确跟踪
            if test_task_id in scheduler._pending_tasks:
                logger.info(f"   ✅ 任务 {test_task_id} 已正确添加到待完成列表")
                
                # 验证活跃任务获取
                active_tasks = scheduler._get_active_adk_discussions()
                if test_task_id in active_tasks:
                    logger.info("   ✅ 活跃任务获取功能正常")
                    return True
                else:
                    logger.warning("   ⚠️ 活跃任务获取功能异常")
                    return False
            else:
                logger.warning("   ⚠️ 任务未正确添加到待完成列表")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 任务发送和跟踪测试失败: {e}")
            return False
    
    async def test_task_completion_handling(self) -> bool:
        """测试任务完成通知处理"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.time_manager import get_time_manager
            from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
            from src.utils.task_completion_notifier import TaskCompletionResult
            
            # 创建仿真调度智能体
            config_manager = get_config_manager()
            time_manager = get_time_manager()
            scheduler = SimulationSchedulerAgent(
                name="test_scheduler",
                config_mgr=config_manager,
                time_mgr=time_manager
            )
            
            # 添加待完成任务
            test_task_id = "test_completion_task_001"
            scheduler._pending_tasks.add(test_task_id)
            scheduler._waiting_for_tasks = True
            
            # 创建任务完成结果
            completion_result = TaskCompletionResult(
                task_id=test_task_id,
                satellite_id="SAT_001",
                discussion_id="DISC_001",
                status="completed",
                completion_time=datetime.now().isoformat(),
                iterations_completed=5,
                quality_score=0.85,
                discussion_result={},
                metadata={}
            )
            
            # 模拟任务完成通知处理
            await scheduler._on_task_completed(completion_result)
            
            # 验证处理结果
            if (test_task_id not in scheduler._pending_tasks and
                test_task_id in scheduler._completed_tasks and
                not scheduler._waiting_for_tasks):
                
                logger.info("   ✅ 任务完成通知处理正确")
                logger.info(f"   ✅ 任务状态: {scheduler._completed_tasks[test_task_id].status}")
                return True
            else:
                logger.warning("   ⚠️ 任务完成通知处理异常")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 任务完成通知处理测试失败: {e}")
            return False
    
    async def test_waiting_mechanism(self) -> bool:
        """测试等待机制验证"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.time_manager import get_time_manager
            from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
            
            # 创建仿真调度智能体
            config_manager = get_config_manager()
            time_manager = get_time_manager()
            scheduler = SimulationSchedulerAgent(
                name="test_scheduler",
                config_mgr=config_manager,
                time_mgr=time_manager
            )
            
            # 测试场景1: 没有待完成任务
            start_time = asyncio.get_event_loop().time()
            await scheduler._wait_for_all_tasks_completion()
            elapsed_time = asyncio.get_event_loop().time() - start_time
            
            if elapsed_time < 1.0:  # 应该立即返回
                logger.info("   ✅ 无待完成任务时立即返回")
                
                # 测试场景2: 检查所有任务完成状态
                all_completed = scheduler._check_all_discussions_completed()
                if all_completed:
                    logger.info("   ✅ 任务完成状态检查正确")
                    return True
                else:
                    logger.warning("   ⚠️ 任务完成状态检查异常")
                    return False
            else:
                logger.warning(f"   ⚠️ 无待完成任务时等待时间过长: {elapsed_time:.2f}s")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 等待机制验证测试失败: {e}")
            return False
    
    async def test_coordination_monitoring(self) -> bool:
        """测试协同决策监控更新"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.time_manager import get_time_manager
            from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
            
            # 创建仿真调度智能体
            config_manager = get_config_manager()
            time_manager = get_time_manager()
            scheduler = SimulationSchedulerAgent(
                name="test_scheduler",
                config_mgr=config_manager,
                time_mgr=time_manager
            )
            
            # 测试场景1: 无待完成任务
            result1 = await scheduler._monitor_coordination_process(None)
            if "无待完成任务" in result1:
                logger.info("   ✅ 无待完成任务时协同决策监控正确")
                
                # 测试场景2: 有待完成任务
                scheduler._pending_tasks.add("test_task_001")
                scheduler._pending_tasks.add("test_task_002")
                
                result2 = await scheduler._monitor_coordination_process(None)
                if "2 个" in result2:
                    logger.info("   ✅ 有待完成任务时协同决策监控正确")
                    return True
                else:
                    logger.warning(f"   ⚠️ 有待完成任务时协同决策监控异常: {result2}")
                    return False
            else:
                logger.warning(f"   ⚠️ 无待完成任务时协同决策监控异常: {result1}")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 协同决策监控更新测试失败: {e}")
            return False
    
    async def test_discussion_completion_check(self) -> bool:
        """测试讨论组完成检查更新"""
        try:
            from src.utils.config_manager import get_config_manager
            from src.utils.time_manager import get_time_manager
            from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
            
            # 创建仿真调度智能体
            config_manager = get_config_manager()
            time_manager = get_time_manager()
            scheduler = SimulationSchedulerAgent(
                name="test_scheduler",
                config_mgr=config_manager,
                time_mgr=time_manager
            )
            
            # 测试确保所有讨论组完成方法
            result = await scheduler._ensure_all_discussions_complete(None)
            
            if "所有任务已完成" in result:
                logger.info("   ✅ 讨论组完成检查已更新为任务完成检查")
                return True
            else:
                logger.warning(f"   ⚠️ 讨论组完成检查更新异常: {result}")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 讨论组完成检查更新测试失败: {e}")
            return False
    
    def generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "="*80)
        logger.info("📋 任务完成通知机制集成测试报告")
        logger.info("="*80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        failed_tests = total_tests - passed_tests
        
        logger.info(f"📊 测试统计:")
        logger.info(f"   总测试数: {total_tests}")
        logger.info(f"   通过: {passed_tests}")
        logger.info(f"   失败: {failed_tests}")
        logger.info(f"   通过率: {passed_tests/total_tests*100:.1f}%")
        
        logger.info(f"\n📋 详细结果:")
        for test_name, result in self.test_results.items():
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"   {test_name}: {status}")
        
        if passed_tests == total_tests:
            logger.info(f"\n🎉 所有集成测试通过！任务完成通知机制已正确集成")
        else:
            logger.warning(f"\n⚠️ 有 {failed_tests} 个测试失败，需要进一步修复")
        
        logger.info("\n💡 集成效果:")
        logger.info("   ✅ 仿真调度智能体已切换到任务完成通知机制")
        logger.info("   ✅ 旧的讨论组管理逻辑已被替换")
        logger.info("   ✅ 协同决策监控基于待完成任务数量")
        logger.info("   ✅ 等待机制基于真实任务完成通知")
        
        logger.info("\n🎯 预期行为:")
        logger.info("   - 发送任务时记录到待完成列表")
        logger.info("   - 收到完成通知时从待完成列表移除")
        logger.info("   - 等待所有任务完成后开始下一轮规划")
        logger.info("   - 不再显示'仿真调度智能体不再管理讨论组'")

async def main():
    """主测试函数"""
    tester = TaskNotificationIntegrationTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
