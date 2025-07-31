"""
甘特图保存状态管理器
负责跟踪和管理甘特图保存操作的状态、进度、错误处理和重试机制
"""

import asyncio
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import uuid
import queue

logger = logging.getLogger(__name__)

class SaveStatus(Enum):
    """保存状态枚举"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"

@dataclass
class SaveTask:
    """保存任务"""
    task_id: str
    gantt_data: Any
    save_path: str
    format: str
    options: Dict[str, Any] = field(default_factory=dict)
    
    # 状态信息
    status: SaveStatus = SaveStatus.PENDING
    progress: float = 0.0
    error_message: str = ""
    
    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # 重试信息
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 回调函数
    on_progress: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None

@dataclass
class SaveStatistics:
    """保存统计信息"""
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    cancelled_tasks: int = 0
    average_save_time: float = 0.0
    total_save_time: float = 0.0
    success_rate: float = 0.0

class GanttSaveStateManager:
    """甘特图保存状态管理器"""
    
    def __init__(self, max_concurrent_saves: int = 3):
        self.max_concurrent_saves = max_concurrent_saves
        self.active_tasks: Dict[str, SaveTask] = {}
        self.completed_tasks: List[SaveTask] = []
        self.task_queue = queue.Queue()
        self.worker_threads: List[threading.Thread] = []
        self.is_running = False
        self.lock = threading.Lock()
        
        # 统计信息
        self.statistics = SaveStatistics()
        
        # 启动工作线程
        self.start_workers()
        
        logger.info("✅ 甘特图保存状态管理器初始化完成")
    
    def start_workers(self):
        """启动工作线程"""
        self.is_running = True
        
        for i in range(self.max_concurrent_saves):
            worker = threading.Thread(target=self._worker_loop, name=f"GanttSaveWorker-{i}")
            worker.daemon = True
            worker.start()
            self.worker_threads.append(worker)
        
        logger.info(f"✅ 启动了 {self.max_concurrent_saves} 个保存工作线程")
    
    def stop_workers(self):
        """停止工作线程"""
        self.is_running = False
        
        # 向队列添加停止信号
        for _ in range(self.max_concurrent_saves):
            self.task_queue.put(None)
        
        # 等待线程结束
        for worker in self.worker_threads:
            worker.join(timeout=5.0)
        
        logger.info("✅ 保存工作线程已停止")
    
    def submit_save_task(
        self,
        gantt_data: Any,
        save_path: str,
        format: str,
        options: Dict[str, Any] = None,
        on_progress: Callable = None,
        on_complete: Callable = None,
        on_error: Callable = None
    ) -> str:
        """提交保存任务"""
        task_id = str(uuid.uuid4())
        
        task = SaveTask(
            task_id=task_id,
            gantt_data=gantt_data,
            save_path=save_path,
            format=format,
            options=options or {},
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error
        )
        
        with self.lock:
            self.active_tasks[task_id] = task
            self.statistics.total_tasks += 1
        
        # 添加到队列
        self.task_queue.put(task)
        
        logger.info(f"📝 提交保存任务: {task_id}")
        return task_id
    
    def get_task_status(self, task_id: str) -> Optional[SaveTask]:
        """获取任务状态"""
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id]
            
            # 在已完成任务中查找
            for task in self.completed_tasks:
                if task.task_id == task_id:
                    return task
        
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                if task.status in [SaveStatus.PENDING, SaveStatus.IN_PROGRESS]:
                    task.status = SaveStatus.CANCELLED
                    task.completed_at = datetime.now()
                    self._move_to_completed(task)
                    logger.info(f"❌ 取消保存任务: {task_id}")
                    return True
        
        return False
    
    def get_active_tasks(self) -> List[SaveTask]:
        """获取活动任务列表"""
        with self.lock:
            return list(self.active_tasks.values())
    
    def get_completed_tasks(self, limit: int = 100) -> List[SaveTask]:
        """获取已完成任务列表"""
        with self.lock:
            return self.completed_tasks[-limit:]
    
    def get_statistics(self) -> SaveStatistics:
        """获取统计信息"""
        with self.lock:
            # 更新统计信息
            completed_count = len([t for t in self.completed_tasks if t.status == SaveStatus.COMPLETED])
            failed_count = len([t for t in self.completed_tasks if t.status == SaveStatus.FAILED])
            cancelled_count = len([t for t in self.completed_tasks if t.status == SaveStatus.CANCELLED])
            
            self.statistics.completed_tasks = completed_count
            self.statistics.failed_tasks = failed_count
            self.statistics.cancelled_tasks = cancelled_count
            
            if self.statistics.total_tasks > 0:
                self.statistics.success_rate = completed_count / self.statistics.total_tasks
            
            # 计算平均保存时间
            completed_tasks_with_time = [
                t for t in self.completed_tasks 
                if t.status == SaveStatus.COMPLETED and t.started_at and t.completed_at
            ]
            
            if completed_tasks_with_time:
                total_time = sum(
                    (t.completed_at - t.started_at).total_seconds() 
                    for t in completed_tasks_with_time
                )
                self.statistics.total_save_time = total_time
                self.statistics.average_save_time = total_time / len(completed_tasks_with_time)
            
            return self.statistics
    
    def _worker_loop(self):
        """工作线程主循环"""
        while self.is_running:
            try:
                # 从队列获取任务
                task = self.task_queue.get(timeout=1.0)
                
                if task is None:  # 停止信号
                    break
                
                # 执行任务
                self._execute_task(task)
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"❌ 工作线程异常: {e}")
    
    def _execute_task(self, task: SaveTask):
        """执行保存任务"""
        try:
            # 更新任务状态
            task.status = SaveStatus.IN_PROGRESS
            task.started_at = datetime.now()
            task.progress = 0.0
            
            if task.on_progress:
                task.on_progress(task.task_id, 0.0, "开始保存...")
            
            # 执行实际的保存操作
            self._perform_save(task)
            
            # 保存成功
            task.status = SaveStatus.COMPLETED
            task.progress = 100.0
            task.completed_at = datetime.now()
            
            if task.on_complete:
                task.on_complete(task.task_id, task.save_path)
            
            if task.on_progress:
                task.on_progress(task.task_id, 100.0, "保存完成")
            
            logger.info(f"✅ 保存任务完成: {task.task_id}")
            
        except Exception as e:
            # 保存失败
            task.status = SaveStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            
            # 检查是否需要重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = SaveStatus.RETRYING
                
                logger.warning(f"⚠️ 保存任务失败，准备重试 ({task.retry_count}/{task.max_retries}): {task.task_id}")
                
                # 延迟后重新加入队列
                threading.Timer(task.retry_delay, lambda: self.task_queue.put(task)).start()
                return
            
            if task.on_error:
                task.on_error(task.task_id, str(e))
            
            logger.error(f"❌ 保存任务失败: {task.task_id} - {e}")
        
        finally:
            # 移动到已完成列表
            with self.lock:
                self._move_to_completed(task)
    
    def _perform_save(self, task: SaveTask):
        """执行实际的保存操作"""
        # 更新进度
        if task.on_progress:
            task.on_progress(task.task_id, 25.0, "准备数据...")

        # 根据格式选择不同的保存方式
        if task.format.lower() in ['json', 'pickle']:
            # 数据格式使用持久化管理器
            from .gantt_data_persistence import get_gantt_persistence_manager
            persistence_manager = get_gantt_persistence_manager()

            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 50.0, "序列化数据...")

            # 执行保存
            saved_path = persistence_manager.save_gantt_data(
                task.gantt_data,
                task.save_path,
                task.format,
                task.options.get('compress', False),
                task.options.get('include_metadata', True)
            )

        elif task.format.lower() in ['png', 'svg', 'pdf', 'eps']:
            # 图像格式使用图表生成器
            saved_path = self._save_chart_image(task)

        elif task.format.lower() == 'html':
            # HTML格式使用专门的HTML生成器
            saved_path = self._save_html_chart(task)

        elif task.format.lower() in ['xlsx', 'excel']:
            # Excel格式使用专门的Excel生成器
            saved_path = self._save_excel_chart(task)

        else:
            raise Exception(f"不支持的保存格式: {task.format}")

        # 更新进度
        if task.on_progress:
            task.on_progress(task.task_id, 75.0, "写入文件...")

        # 验证保存结果
        if not saved_path:
            raise Exception("保存操作返回空路径")

        task.save_path = saved_path

        # 更新进度
        if task.on_progress:
            task.on_progress(task.task_id, 90.0, "验证文件...")

    def _save_chart_image(self, task: SaveTask) -> str:
        """保存图表图像"""
        try:
            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 50.0, "生成图表...")

            # 使用图像生成器
            from .gantt_image_generator import get_gantt_image_generator
            image_generator = get_gantt_image_generator()

            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 60.0, f"渲染{task.format.upper()}图像...")

            # 生成图像
            saved_path = image_generator.generate_gantt_image(
                gantt_data=task.gantt_data,
                output_path=task.save_path,
                format=task.format,
                quality=task.options.get('quality', 'high')
            )

            # 注册文件到文件管理器
            from .gantt_file_manager import get_gantt_file_manager
            file_manager = get_gantt_file_manager()

            file_manager.register_file(
                saved_path,
                chart_type=task.gantt_data.chart_type,
                mission_id=getattr(task.gantt_data, 'mission_scenario', 'UNKNOWN'),
                category='image'
            )

            return saved_path

        except Exception as e:
            logger.error(f"❌ 保存图表图像失败: {e}")
            # 如果图像生成失败，回退到JSON格式
            logger.info(f"🔄 图像生成失败，回退到JSON格式: {task.save_path}")

            from .gantt_data_persistence import get_gantt_persistence_manager
            persistence_manager = get_gantt_persistence_manager()

            json_path = task.save_path.replace(f'.{task.format}', '.json')
            return persistence_manager.save_gantt_data(
                task.gantt_data,
                json_path,
                'json',
                task.options.get('compress', False),
                task.options.get('include_metadata', True)
            )

    def _save_html_chart(self, task: SaveTask) -> str:
        """保存HTML格式甘特图"""
        try:
            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 50.0, "生成HTML图表...")

            # 使用HTML生成器
            from .gantt_html_generator import get_gantt_html_generator
            html_generator = get_gantt_html_generator()

            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 60.0, "渲染交互式HTML...")

            # 生成HTML
            saved_path = html_generator.generate_html_gantt(
                gantt_data=task.gantt_data,
                output_path=task.save_path,
                interactive=task.options.get('interactive', True)
            )

            # 注册文件到文件管理器
            from .gantt_file_manager import get_gantt_file_manager
            file_manager = get_gantt_file_manager()

            file_manager.register_file(
                saved_path,
                chart_type=task.gantt_data.chart_type,
                mission_id=getattr(task.gantt_data, 'mission_scenario', 'UNKNOWN'),
                category='html'
            )

            return saved_path

        except Exception as e:
            logger.error(f"❌ 保存HTML图表失败: {e}")
            # 如果HTML生成失败，回退到JSON格式
            logger.info(f"🔄 HTML生成失败，回退到JSON格式: {task.save_path}")

            from .gantt_data_persistence import get_gantt_persistence_manager
            persistence_manager = get_gantt_persistence_manager()

            json_path = task.save_path.replace('.html', '.json')
            return persistence_manager.save_gantt_data(
                task.gantt_data,
                json_path,
                'json',
                task.options.get('compress', False),
                task.options.get('include_metadata', True)
            )

    def _save_excel_chart(self, task: SaveTask) -> str:
        """保存Excel格式甘特图"""
        try:
            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 50.0, "生成Excel图表...")

            # 使用Excel生成器
            from .gantt_excel_generator import get_gantt_excel_generator
            excel_generator = get_gantt_excel_generator()

            # 更新进度
            if task.on_progress:
                task.on_progress(task.task_id, 60.0, "创建Excel工作表...")

            # 生成Excel
            saved_path = excel_generator.generate_excel_gantt(
                gantt_data=task.gantt_data,
                output_path=task.save_path
            )

            # 注册文件到文件管理器
            from .gantt_file_manager import get_gantt_file_manager
            file_manager = get_gantt_file_manager()

            file_manager.register_file(
                saved_path,
                chart_type=task.gantt_data.chart_type,
                mission_id=getattr(task.gantt_data, 'mission_scenario', 'UNKNOWN'),
                category='excel'
            )

            return saved_path

        except Exception as e:
            logger.error(f"❌ 保存Excel图表失败: {e}")
            # 如果Excel生成失败，回退到JSON格式
            logger.info(f"🔄 Excel生成失败，回退到JSON格式: {task.save_path}")

            from .gantt_data_persistence import get_gantt_persistence_manager
            persistence_manager = get_gantt_persistence_manager()

            json_path = task.save_path.replace('.xlsx', '.json').replace('.excel', '.json')
            return persistence_manager.save_gantt_data(
                task.gantt_data,
                json_path,
                'json',
                task.options.get('compress', False),
                task.options.get('include_metadata', True)
            )

    def _move_to_completed(self, task: SaveTask):
        """将任务移动到已完成列表"""
        if task.task_id in self.active_tasks:
            del self.active_tasks[task.task_id]
        
        self.completed_tasks.append(task)
        
        # 限制已完成任务列表大小
        if len(self.completed_tasks) > 1000:
            self.completed_tasks = self.completed_tasks[-500:]
    
    def cleanup_old_tasks(self, days_to_keep: int = 7):
        """清理旧的已完成任务"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        with self.lock:
            old_count = len(self.completed_tasks)
            self.completed_tasks = [
                task for task in self.completed_tasks
                if task.completed_at and task.completed_at > cutoff_date
            ]
            new_count = len(self.completed_tasks)
            
            logger.info(f"🧹 清理旧任务: 删除 {old_count - new_count} 个任务")

# 全局状态管理器实例
_gantt_save_state_manager = None

def get_gantt_save_state_manager() -> GanttSaveStateManager:
    """获取全局甘特图保存状态管理器实例"""
    global _gantt_save_state_manager
    if _gantt_save_state_manager is None:
        _gantt_save_state_manager = GanttSaveStateManager()
    return _gantt_save_state_manager
