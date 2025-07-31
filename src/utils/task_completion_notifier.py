#!/usr/bin/env python3
"""
任务完成通知系统
负责管理讨论组任务完成后向仿真调度智能体发送完成信号
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass
import threading

logger = logging.getLogger(__name__)

@dataclass
class TaskCompletionResult:
    """任务完成结果"""
    task_id: str
    satellite_id: str
    discussion_id: str
    status: str  # 'completed', 'failed', 'timeout'
    completion_time: str
    iterations_completed: int
    quality_score: float
    discussion_result: Dict[str, Any]
    metadata: Dict[str, Any]

class TaskCompletionNotifier:
    """任务完成通知系统"""
    
    def __init__(self):
        self._completion_callbacks: Dict[str, Callable] = {}
        self._task_results: Dict[str, TaskCompletionResult] = {}
        self._scheduler_callbacks: List[Callable] = []
        self._pending_notifications: List[TaskCompletionResult] = []
        self._lock = threading.Lock()
        
        logger.info("📢 任务完成通知系统初始化完成")
    
    def register_scheduler_callback(self, callback: Callable):
        """注册仿真调度智能体的回调函数"""
        with self._lock:
            self._scheduler_callbacks.append(callback)
            logger.info(f"✅ 仿真调度智能体回调已注册，总数: {len(self._scheduler_callbacks)}")
    
    def register_task_callback(self, task_id: str, callback: Callable):
        """注册特定任务的完成回调"""
        with self._lock:
            self._completion_callbacks[task_id] = callback
            logger.info(f"✅ 任务 {task_id} 完成回调已注册")
    
    async def notify_task_completion(self, result: TaskCompletionResult):
        """通知任务完成"""
        try:
            logger.info(f"📢 收到任务完成通知: {result.task_id} (状态: {result.status})")
            
            with self._lock:
                # 存储结果
                self._task_results[result.task_id] = result
                
                # 添加到待通知列表
                self._pending_notifications.append(result)
            
            # 通知特定任务回调
            await self._notify_task_specific_callbacks(result)
            
            # 通知仿真调度智能体
            await self._notify_scheduler_callbacks(result)
            
            logger.info(f"✅ 任务完成通知处理完成: {result.task_id}")
            
        except Exception as e:
            logger.error(f"❌ 任务完成通知处理失败: {e}")
    
    async def _notify_task_specific_callbacks(self, result: TaskCompletionResult):
        """通知特定任务的回调"""
        try:
            task_id = result.task_id
            
            with self._lock:
                callback = self._completion_callbacks.get(task_id)
            
            if callback:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(result)
                    else:
                        callback(result)
                    
                    logger.info(f"✅ 任务 {task_id} 特定回调执行成功")
                    
                    # 清理已执行的回调
                    with self._lock:
                        if task_id in self._completion_callbacks:
                            del self._completion_callbacks[task_id]
                            
                except Exception as e:
                    logger.error(f"❌ 任务 {task_id} 特定回调执行失败: {e}")
            
        except Exception as e:
            logger.error(f"❌ 通知任务特定回调失败: {e}")
    
    async def _notify_scheduler_callbacks(self, result: TaskCompletionResult):
        """通知仿真调度智能体回调"""
        try:
            with self._lock:
                callbacks = self._scheduler_callbacks.copy()
            
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(result)
                    else:
                        callback(result)
                    
                    logger.info(f"✅ 仿真调度智能体回调执行成功")
                    
                except Exception as e:
                    logger.error(f"❌ 仿真调度智能体回调执行失败: {e}")
            
        except Exception as e:
            logger.error(f"❌ 通知仿真调度智能体回调失败: {e}")
    
    def get_task_result(self, task_id: str) -> Optional[TaskCompletionResult]:
        """获取任务完成结果"""
        with self._lock:
            return self._task_results.get(task_id)
    
    def get_all_completed_tasks(self) -> List[TaskCompletionResult]:
        """获取所有已完成的任务"""
        with self._lock:
            return list(self._task_results.values())
    
    def get_pending_notifications(self) -> List[TaskCompletionResult]:
        """获取待处理的通知"""
        with self._lock:
            return self._pending_notifications.copy()
    
    def clear_pending_notifications(self):
        """清理待处理的通知"""
        with self._lock:
            cleared_count = len(self._pending_notifications)
            self._pending_notifications.clear()
            logger.info(f"🧹 清理了 {cleared_count} 个待处理通知")
    
    def get_completion_statistics(self) -> Dict[str, Any]:
        """获取完成统计信息"""
        with self._lock:
            total_tasks = len(self._task_results)
            completed_tasks = len([r for r in self._task_results.values() if r.status == 'completed'])
            failed_tasks = len([r for r in self._task_results.values() if r.status == 'failed'])
            timeout_tasks = len([r for r in self._task_results.values() if r.status == 'timeout'])
            
            avg_quality = 0.0
            if total_tasks > 0:
                avg_quality = sum(r.quality_score for r in self._task_results.values()) / total_tasks
            
            avg_iterations = 0.0
            if total_tasks > 0:
                avg_iterations = sum(r.iterations_completed for r in self._task_results.values()) / total_tasks
            
            return {
                'total_tasks': total_tasks,
                'completed_tasks': completed_tasks,
                'failed_tasks': failed_tasks,
                'timeout_tasks': timeout_tasks,
                'success_rate': completed_tasks / total_tasks if total_tasks > 0 else 0.0,
                'average_quality_score': avg_quality,
                'average_iterations': avg_iterations,
                'pending_notifications': len(self._pending_notifications)
            }
    
    def cleanup_old_results(self, max_age_hours: int = 24):
        """清理旧的任务结果"""
        try:
            current_time = datetime.now()
            cleaned_count = 0
            
            with self._lock:
                task_ids_to_remove = []
                
                for task_id, result in self._task_results.items():
                    try:
                        completion_time = datetime.fromisoformat(result.completion_time.replace('Z', '+00:00'))
                        age_hours = (current_time - completion_time).total_seconds() / 3600
                        
                        if age_hours > max_age_hours:
                            task_ids_to_remove.append(task_id)
                    except Exception:
                        # 如果时间解析失败，也清理掉
                        task_ids_to_remove.append(task_id)
                
                for task_id in task_ids_to_remove:
                    del self._task_results[task_id]
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"🧹 清理了 {cleaned_count} 个超过 {max_age_hours} 小时的旧任务结果")
            
        except Exception as e:
            logger.error(f"❌ 清理旧任务结果失败: {e}")

# 全局单例实例
_task_completion_notifier = None
_notifier_lock = threading.Lock()

def get_task_completion_notifier() -> TaskCompletionNotifier:
    """获取任务完成通知系统的全局单例"""
    global _task_completion_notifier
    
    with _notifier_lock:
        if _task_completion_notifier is None:
            _task_completion_notifier = TaskCompletionNotifier()
        
        return _task_completion_notifier

def reset_task_completion_notifier():
    """重置任务完成通知系统（主要用于测试）"""
    global _task_completion_notifier
    
    with _notifier_lock:
        _task_completion_notifier = None
        logger.info("🔄 任务完成通知系统已重置")

# 便捷函数
async def notify_task_completed(
    task_id: str,
    satellite_id: str,
    discussion_id: str,
    status: str = 'completed',
    iterations_completed: int = 0,
    quality_score: float = 0.0,
    discussion_result: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None
):
    """便捷的任务完成通知函数"""
    notifier = get_task_completion_notifier()
    
    result = TaskCompletionResult(
        task_id=task_id,
        satellite_id=satellite_id,
        discussion_id=discussion_id,
        status=status,
        completion_time=datetime.now().isoformat(),
        iterations_completed=iterations_completed,
        quality_score=quality_score,
        discussion_result=discussion_result or {},
        metadata=metadata or {}
    )
    
    await notifier.notify_task_completion(result)

def register_scheduler_for_task_notifications(callback: Callable):
    """注册仿真调度智能体接收任务完成通知"""
    notifier = get_task_completion_notifier()
    notifier.register_scheduler_callback(callback)
