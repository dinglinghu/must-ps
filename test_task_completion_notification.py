#!/usr/bin/env python3
"""
测试任务完成通知机制
验证讨论组任务完成后能够正确通知仿真调度智能体
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

class TaskCompletionNotificationTester:
    """任务完成通知机制测试器"""
    
    def __init__(self):
        self.test_results = {}
        self.received_notifications = []
    
    async def run_all_tests(self):
        """运行所有测试"""
        logger.info("🚀 开始测试任务完成通知机制...")
        
        tests = [
            ("任务完成通知系统初始化", self.test_notifier_initialization),
            ("任务完成通知发送", self.test_task_completion_notification),
            ("仿真调度智能体回调注册", self.test_scheduler_callback_registration),
            ("多任务完成通知处理", self.test_multiple_task_notifications),
            ("任务完成统计功能", self.test_completion_statistics),
            ("超时任务处理", self.test_timeout_handling)
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
    
    async def test_notifier_initialization(self) -> bool:
        """测试任务完成通知系统初始化"""
        try:
            from src.utils.task_completion_notifier import get_task_completion_notifier, reset_task_completion_notifier
            
            # 重置通知系统
            reset_task_completion_notifier()
            
            # 获取通知系统实例
            notifier = get_task_completion_notifier()
            
            # 验证初始化
            if notifier is not None:
                logger.info("   ✅ 任务完成通知系统初始化成功")
                
                # 验证统计信息
                stats = notifier.get_completion_statistics()
                if stats['total_tasks'] == 0:
                    logger.info("   ✅ 初始统计信息正确")
                    return True
                else:
                    logger.warning("   ⚠️ 初始统计信息异常")
                    return False
            else:
                logger.warning("   ⚠️ 任务完成通知系统初始化失败")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 任务完成通知系统初始化测试失败: {e}")
            return False
    
    async def test_task_completion_notification(self) -> bool:
        """测试任务完成通知发送"""
        try:
            from src.utils.task_completion_notifier import notify_task_completed, get_task_completion_notifier
            
            # 发送任务完成通知
            test_task_id = "test_task_001"
            await notify_task_completed(
                task_id=test_task_id,
                satellite_id="SAT_001",
                discussion_id="DISC_001",
                status="completed",
                iterations_completed=5,
                quality_score=0.85,
                discussion_result={"success": True, "final_result": "optimal_solution"},
                metadata={"test": True}
            )
            
            # 验证通知是否被记录
            notifier = get_task_completion_notifier()
            result = notifier.get_task_result(test_task_id)
            
            if result and result.task_id == test_task_id:
                logger.info(f"   ✅ 任务完成通知发送成功: {test_task_id}")
                logger.info(f"   ✅ 任务状态: {result.status}, 质量分数: {result.quality_score}")
                return True
            else:
                logger.warning("   ⚠️ 任务完成通知未正确记录")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 任务完成通知发送测试失败: {e}")
            return False
    
    async def test_scheduler_callback_registration(self) -> bool:
        """测试仿真调度智能体回调注册"""
        try:
            from src.utils.task_completion_notifier import get_task_completion_notifier
            
            # 创建模拟回调函数
            async def mock_scheduler_callback(completion_result):
                self.received_notifications.append(completion_result)
                logger.info(f"   📢 模拟仿真调度智能体收到通知: {completion_result.task_id}")
            
            # 注册回调
            notifier = get_task_completion_notifier()
            notifier.register_scheduler_callback(mock_scheduler_callback)
            
            # 发送测试通知
            from src.utils.task_completion_notifier import TaskCompletionResult
            test_result = TaskCompletionResult(
                task_id="test_callback_task",
                satellite_id="SAT_002",
                discussion_id="DISC_002",
                status="completed",
                completion_time=datetime.now().isoformat(),
                iterations_completed=3,
                quality_score=0.75,
                discussion_result={},
                metadata={}
            )
            
            await notifier.notify_task_completion(test_result)
            
            # 等待回调执行
            await asyncio.sleep(0.1)
            
            # 验证回调是否被调用
            if len(self.received_notifications) > 0:
                received = self.received_notifications[-1]
                if received.task_id == "test_callback_task":
                    logger.info("   ✅ 仿真调度智能体回调注册和执行成功")
                    return True
                else:
                    logger.warning("   ⚠️ 回调接收到错误的任务ID")
                    return False
            else:
                logger.warning("   ⚠️ 仿真调度智能体回调未被调用")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 仿真调度智能体回调注册测试失败: {e}")
            return False
    
    async def test_multiple_task_notifications(self) -> bool:
        """测试多任务完成通知处理"""
        try:
            from src.utils.task_completion_notifier import notify_task_completed, get_task_completion_notifier
            
            # 发送多个任务完成通知
            task_ids = ["multi_task_001", "multi_task_002", "multi_task_003"]
            
            for i, task_id in enumerate(task_ids):
                await notify_task_completed(
                    task_id=task_id,
                    satellite_id=f"SAT_{i+1:03d}",
                    discussion_id=f"DISC_{i+1:03d}",
                    status="completed" if i < 2 else "failed",
                    iterations_completed=i + 3,
                    quality_score=0.7 + i * 0.1,
                    metadata={"batch": "multi_test"}
                )
            
            # 验证所有通知都被处理
            notifier = get_task_completion_notifier()
            all_results = notifier.get_all_completed_tasks()
            
            multi_test_results = [r for r in all_results if r.metadata.get("batch") == "multi_test"]
            
            if len(multi_test_results) == 3:
                logger.info(f"   ✅ 多任务完成通知处理成功: {len(multi_test_results)} 个任务")
                
                # 验证统计信息
                stats = notifier.get_completion_statistics()
                logger.info(f"   📊 统计信息: 总任务={stats['total_tasks']}, 成功率={stats['success_rate']:.2f}")
                
                return True
            else:
                logger.warning(f"   ⚠️ 多任务通知处理异常: 期望3个，实际{len(multi_test_results)}个")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 多任务完成通知处理测试失败: {e}")
            return False
    
    async def test_completion_statistics(self) -> bool:
        """测试任务完成统计功能"""
        try:
            from src.utils.task_completion_notifier import get_task_completion_notifier
            
            notifier = get_task_completion_notifier()
            stats = notifier.get_completion_statistics()
            
            # 验证统计信息结构
            required_keys = ['total_tasks', 'completed_tasks', 'failed_tasks', 'success_rate', 'average_quality_score']
            
            if all(key in stats for key in required_keys):
                logger.info("   ✅ 统计信息结构正确")
                logger.info(f"   📊 当前统计: {stats}")
                
                # 验证数值合理性
                if (stats['total_tasks'] >= 0 and 
                    0 <= stats['success_rate'] <= 1 and
                    0 <= stats['average_quality_score'] <= 1):
                    logger.info("   ✅ 统计数值合理")
                    return True
                else:
                    logger.warning("   ⚠️ 统计数值异常")
                    return False
            else:
                logger.warning("   ⚠️ 统计信息结构不完整")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 任务完成统计功能测试失败: {e}")
            return False
    
    async def test_timeout_handling(self) -> bool:
        """测试超时任务处理"""
        try:
            from src.utils.task_completion_notifier import get_task_completion_notifier
            
            notifier = get_task_completion_notifier()
            
            # 测试清理功能
            initial_count = notifier.get_completion_statistics()['total_tasks']
            
            # 执行清理（使用0小时阈值来清理所有任务）
            notifier.cleanup_old_results(max_age_hours=0)
            
            # 验证清理效果
            after_cleanup_count = notifier.get_completion_statistics()['total_tasks']
            
            if after_cleanup_count < initial_count:
                logger.info(f"   ✅ 超时任务清理成功: {initial_count} -> {after_cleanup_count}")
                return True
            elif initial_count == 0:
                logger.info("   ✅ 没有需要清理的任务")
                return True
            else:
                logger.warning("   ⚠️ 超时任务清理未生效")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ 超时任务处理测试失败: {e}")
            return False
    
    def generate_test_report(self):
        """生成测试报告"""
        logger.info("\n" + "="*80)
        logger.info("📋 任务完成通知机制测试报告")
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
            logger.info(f"\n🎉 所有测试通过！任务完成通知机制工作正常")
        else:
            logger.warning(f"\n⚠️ 有 {failed_tests} 个测试失败，需要进一步修复")
        
        logger.info("\n💡 机制特点:")
        logger.info("   ✅ 卫星智能体任务完成后自动发送通知")
        logger.info("   ✅ 仿真调度智能体接收通知并更新状态")
        logger.info("   ✅ 支持多任务并发完成通知")
        logger.info("   ✅ 提供详细的完成统计信息")
        logger.info("   ✅ 具备超时和清理机制")
        
        logger.info("\n🎯 预期效果:")
        logger.info("   - 仿真调度智能体等待所有任务完成通知")
        logger.info("   - 收到所有通知后才开始下一轮规划")
        logger.info("   - 避免基于时间的盲目等待")
        logger.info("   - 提供实时的任务完成进度")

async def main():
    """主测试函数"""
    tester = TaskCompletionNotificationTester()
    await tester.run_all_tests()

if __name__ == "__main__":
    asyncio.run(main())
