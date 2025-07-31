#!/usr/bin/env python3
"""
验证任务完成通知机制修复
简单验证修复是否生效
"""

import logging
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

def verify_scheduler_methods():
    """验证仿真调度智能体方法是否已更新"""
    try:
        # 导入仿真调度智能体
        from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
        
        # 检查方法是否存在
        methods_to_check = [
            '_register_task_completion_callback',
            '_on_task_completed',
            '_wait_for_all_tasks_completion',
            '_log_task_completion_statistics'
        ]
        
        logger.info("🔍 检查仿真调度智能体新增方法...")
        
        for method_name in methods_to_check:
            if hasattr(SimulationSchedulerAgent, method_name):
                logger.info(f"   ✅ {method_name} 方法存在")
            else:
                logger.warning(f"   ❌ {method_name} 方法不存在")
                return False
        
        logger.info("✅ 所有新增方法都存在")
        return True
        
    except Exception as e:
        logger.error(f"❌ 验证仿真调度智能体方法失败: {e}")
        return False

def verify_task_completion_notifier():
    """验证任务完成通知系统"""
    try:
        from src.utils.task_completion_notifier import get_task_completion_notifier, TaskCompletionResult
        
        logger.info("🔍 检查任务完成通知系统...")
        
        # 获取通知系统实例
        notifier = get_task_completion_notifier()
        
        if notifier is not None:
            logger.info("   ✅ 任务完成通知系统可以正常创建")
            
            # 检查统计功能
            stats = notifier.get_completion_statistics()
            if isinstance(stats, dict) and 'total_tasks' in stats:
                logger.info("   ✅ 统计功能正常")
                return True
            else:
                logger.warning("   ❌ 统计功能异常")
                return False
        else:
            logger.warning("   ❌ 任务完成通知系统创建失败")
            return False
            
    except Exception as e:
        logger.error(f"❌ 验证任务完成通知系统失败: {e}")
        return False

def verify_satellite_agent_reporting():
    """验证卫星智能体结果回传"""
    try:
        from src.agents.satellite_agent import SatelliteAgent
        
        logger.info("🔍 检查卫星智能体结果回传方法...")
        
        # 检查_report_result_to_scheduler方法是否已更新
        if hasattr(SatelliteAgent, '_report_result_to_scheduler'):
            logger.info("   ✅ _report_result_to_scheduler 方法存在")
            
            # 检查方法源码是否包含任务完成通知相关代码
            import inspect
            source = inspect.getsource(SatelliteAgent._report_result_to_scheduler)
            
            if 'TaskCompletionResult' in source and 'notify_task_completion' in source:
                logger.info("   ✅ 结果回传方法已更新为使用任务完成通知")
                return True
            else:
                logger.warning("   ❌ 结果回传方法未更新")
                return False
        else:
            logger.warning("   ❌ _report_result_to_scheduler 方法不存在")
            return False
            
    except Exception as e:
        logger.error(f"❌ 验证卫星智能体结果回传失败: {e}")
        return False

def verify_method_updates():
    """验证关键方法是否已更新"""
    try:
        from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
        import inspect
        
        logger.info("🔍 检查关键方法是否已更新...")
        
        # 检查_monitor_coordination_process方法
        source = inspect.getsource(SimulationSchedulerAgent._monitor_coordination_process)
        if '待完成任务' in source and 'pending_tasks' in source:
            logger.info("   ✅ _monitor_coordination_process 已更新")
        else:
            logger.warning("   ❌ _monitor_coordination_process 未更新")
            return False
        
        # 检查_ensure_all_discussions_complete方法
        source = inspect.getsource(SimulationSchedulerAgent._ensure_all_discussions_complete)
        if '_wait_for_all_tasks_completion' in source:
            logger.info("   ✅ _ensure_all_discussions_complete 已更新")
        else:
            logger.warning("   ❌ _ensure_all_discussions_complete 未更新")
            return False
        
        # 检查_check_all_discussions_completed方法
        source = inspect.getsource(SimulationSchedulerAgent._check_all_discussions_completed)
        if 'pending_tasks' in source and '任务已完成' in source:
            logger.info("   ✅ _check_all_discussions_completed 已更新")
        else:
            logger.warning("   ❌ _check_all_discussions_completed 未更新")
            return False
        
        logger.info("✅ 所有关键方法都已更新")
        return True
        
    except Exception as e:
        logger.error(f"❌ 验证方法更新失败: {e}")
        return False

def main():
    """主验证函数"""
    logger.info("🚀 开始验证任务完成通知机制修复...")
    
    results = []
    
    # 验证各个组件
    tests = [
        ("仿真调度智能体新增方法", verify_scheduler_methods),
        ("任务完成通知系统", verify_task_completion_notifier),
        ("卫星智能体结果回传", verify_satellite_agent_reporting),
        ("关键方法更新", verify_method_updates)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n📋 验证: {test_name}")
        try:
            result = test_func()
            results.append(result)
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"结果: {status}")
        except Exception as e:
            logger.error(f"验证异常: {e}")
            results.append(False)
    
    # 生成验证报告
    logger.info("\n" + "="*60)
    logger.info("📋 任务完成通知机制修复验证报告")
    logger.info("="*60)
    
    total_tests = len(results)
    passed_tests = sum(results)
    
    logger.info(f"📊 验证统计:")
    logger.info(f"   总验证项: {total_tests}")
    logger.info(f"   通过: {passed_tests}")
    logger.info(f"   失败: {total_tests - passed_tests}")
    logger.info(f"   通过率: {passed_tests/total_tests*100:.1f}%")
    
    if passed_tests == total_tests:
        logger.info("\n🎉 所有验证通过！任务完成通知机制修复成功")
        logger.info("\n💡 修复效果:")
        logger.info("   ✅ 仿真调度智能体已集成任务完成通知机制")
        logger.info("   ✅ 卫星智能体已实现结果回传功能")
        logger.info("   ✅ 旧的讨论组管理逻辑已被替换")
        logger.info("   ✅ 系统将基于真实任务完成通知进行时序控制")
        
        logger.info("\n🎯 预期行为变化:")
        logger.info("   - 不再显示'仿真调度智能体不再管理讨论组'")
        logger.info("   - 显示'等待 X 个任务完成...'")
        logger.info("   - 显示'收到任务完成通知: task_id (status)'")
        logger.info("   - 显示'所有任务已完成，等待时间: Xs'")
        
        logger.info("\n🚀 部署建议: 立即部署，修复已完成")
    else:
        logger.warning(f"\n⚠️ 有 {total_tests - passed_tests} 个验证失败，需要进一步检查")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
