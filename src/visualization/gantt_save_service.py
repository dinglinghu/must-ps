"""
甘特图保存服务
整合所有甘特图保存相关功能的高级服务接口
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import asyncio

from .gantt_save_config_manager import get_gantt_save_config_manager, GanttSaveResult
from .gantt_file_manager import get_gantt_file_manager, GanttSearchFilter
from .gantt_data_persistence import get_gantt_persistence_manager
from .gantt_save_state_manager import get_gantt_save_state_manager, SaveStatus
from .realistic_constellation_gantt import ConstellationGanttData

logger = logging.getLogger(__name__)

class GanttSaveService:
    """甘特图保存服务"""
    
    def __init__(self):
        self.config_manager = get_gantt_save_config_manager()
        self.file_manager = get_gantt_file_manager()
        self.persistence_manager = get_gantt_persistence_manager()
        self.state_manager = get_gantt_save_state_manager()
        
        logger.info("✅ 甘特图保存服务初始化完成")
    
    async def save_gantt_chart(
        self,
        gantt_data: ConstellationGanttData,
        chart_type: str,
        mission_id: str = None,
        formats: List[str] = None,
        category: str = "tactical",
        options: Dict[str, Any] = None,
        on_progress: Callable = None,
        on_complete: Callable = None,
        on_error: Callable = None
    ) -> Dict[str, Any]:
        """保存甘特图（支持多种格式）"""
        try:
            formats = formats or self.config_manager.settings.default_formats
            options = options or {}
            
            save_results = {}
            task_ids = []
            
            # 为每种格式创建保存任务
            for format in formats:
                save_path = self.config_manager.get_save_path(
                    chart_type, format, mission_id, category
                )
                
                # 提交异步保存任务
                task_id = self.state_manager.submit_save_task(
                    gantt_data=gantt_data,
                    save_path=save_path,
                    format=format,
                    options=options,
                    on_progress=on_progress,
                    on_complete=on_complete,
                    on_error=on_error
                )
                
                task_ids.append(task_id)
                save_results[format] = {
                    'task_id': task_id,
                    'save_path': save_path,
                    'status': 'pending'
                }
            
            logger.info(f"📝 提交甘特图保存任务: {len(task_ids)} 个格式")
            
            return {
                'success': True,
                'task_ids': task_ids,
                'save_results': save_results,
                'message': f'已提交 {len(task_ids)} 个保存任务'
            }
            
        except Exception as e:
            logger.error(f"❌ 提交甘特图保存任务失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_save_progress(self, task_ids: List[str]) -> Dict[str, Any]:
        """获取保存进度"""
        try:
            progress_info = {}
            overall_progress = 0.0
            completed_count = 0
            
            for task_id in task_ids:
                task = self.state_manager.get_task_status(task_id)
                if task:
                    progress_info[task_id] = {
                        'status': task.status.value,
                        'progress': task.progress,
                        'error_message': task.error_message,
                        'save_path': task.save_path,
                        'format': task.format
                    }
                    
                    overall_progress += task.progress
                    if task.status == SaveStatus.COMPLETED:
                        completed_count += 1
                else:
                    progress_info[task_id] = {
                        'status': 'not_found',
                        'progress': 0.0,
                        'error_message': '任务未找到'
                    }
            
            overall_progress = overall_progress / len(task_ids) if task_ids else 0.0
            
            return {
                'success': True,
                'overall_progress': overall_progress,
                'completed_count': completed_count,
                'total_count': len(task_ids),
                'tasks': progress_info
            }
            
        except Exception as e:
            logger.error(f"❌ 获取保存进度失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def search_gantt_charts(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """搜索甘特图"""
        try:
            # 构建搜索过滤器
            filter = GanttSearchFilter(
                chart_type=search_params.get('chart_type'),
                format=search_params.get('format'),
                mission_id=search_params.get('mission_id'),
                category=search_params.get('category'),
                keywords=search_params.get('keywords')
            )
            
            # 处理日期范围
            if search_params.get('date_from'):
                filter.date_from = datetime.fromisoformat(search_params['date_from'])
            if search_params.get('date_to'):
                filter.date_to = datetime.fromisoformat(search_params['date_to'])
            
            # 执行搜索
            files = self.file_manager.search_files(filter)
            
            # 转换结果
            results = []
            for file_info in files:
                results.append({
                    'file_id': file_info.file_id,
                    'file_name': file_info.file_name,
                    'file_path': file_info.file_path,
                    'file_size': file_info.file_size,
                    'format': file_info.format,
                    'chart_type': file_info.chart_type,
                    'mission_id': file_info.mission_id,
                    'category': file_info.category,
                    'creation_time': file_info.creation_time.isoformat(),
                    'last_modified': file_info.last_modified.isoformat(),
                    'checksum': file_info.checksum
                })
            
            return {
                'success': True,
                'total_count': len(results),
                'files': results
            }
            
        except Exception as e:
            logger.error(f"❌ 搜索甘特图失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def load_gantt_chart(self, file_id: str) -> Dict[str, Any]:
        """加载甘特图"""
        try:
            # 获取文件信息
            file_info = self.file_manager.get_file_info(file_id)
            if not file_info:
                return {
                    'success': False,
                    'error': '文件不存在'
                }
            
            # 加载数据
            gantt_data = self.persistence_manager.load_gantt_data(file_info.file_path)
            if not gantt_data:
                return {
                    'success': False,
                    'error': '加载数据失败'
                }
            
            return {
                'success': True,
                'gantt_data': gantt_data,
                'file_info': {
                    'file_id': file_info.file_id,
                    'file_name': file_info.file_name,
                    'file_size': file_info.file_size,
                    'format': file_info.format,
                    'chart_type': file_info.chart_type,
                    'mission_id': file_info.mission_id,
                    'creation_time': file_info.creation_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 加载甘特图失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def export_gantt_chart(self, file_id: str) -> Dict[str, Any]:
        """导出甘特图文件"""
        try:
            file_info = self.file_manager.get_file_info(file_id)
            if not file_info:
                return {
                    'success': False,
                    'error': '文件不存在'
                }
            
            file_path = Path(file_info.file_path)
            if not file_path.exists():
                return {
                    'success': False,
                    'error': '物理文件不存在'
                }
            
            return {
                'success': True,
                'file_path': str(file_path),
                'file_name': file_info.file_name,
                'file_size': file_info.file_size,
                'format': file_info.format
            }
            
        except Exception as e:
            logger.error(f"❌ 导出甘特图失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_gantt_chart(self, file_id: str, remove_physical: bool = True) -> Dict[str, Any]:
        """删除甘特图"""
        try:
            success = self.file_manager.delete_file(file_id, remove_physical)
            
            if success:
                return {
                    'success': True,
                    'message': '文件已删除'
                }
            else:
                return {
                    'success': False,
                    'error': '删除失败'
                }
                
        except Exception as e:
            logger.error(f"❌ 删除甘特图失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            file_stats = self.file_manager.get_statistics()
            save_stats = self.config_manager.get_save_statistics()
            state_stats = self.state_manager.get_statistics()
            
            return {
                'success': True,
                'file_statistics': file_stats,
                'save_statistics': save_stats,
                'state_statistics': {
                    'total_tasks': state_stats.total_tasks,
                    'completed_tasks': state_stats.completed_tasks,
                    'failed_tasks': state_stats.failed_tasks,
                    'success_rate': state_stats.success_rate,
                    'average_save_time': state_stats.average_save_time
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def cleanup_old_files(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """清理旧文件"""
        try:
            cleanup_stats = self.config_manager.cleanup_old_files(days_to_keep)
            self.state_manager.cleanup_old_tasks(days_to_keep)
            
            return {
                'success': True,
                'cleanup_statistics': cleanup_stats
            }
            
        except Exception as e:
            logger.error(f"❌ 清理旧文件失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def sync_filesystem(self) -> Dict[str, Any]:
        """同步文件系统"""
        try:
            sync_stats = self.file_manager.sync_filesystem()
            
            return {
                'success': True,
                'sync_statistics': sync_stats
            }
            
        except Exception as e:
            logger.error(f"❌ 同步文件系统失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# 全局服务实例
_gantt_save_service = None

def get_gantt_save_service() -> GanttSaveService:
    """获取全局甘特图保存服务实例"""
    global _gantt_save_service
    if _gantt_save_service is None:
        _gantt_save_service = GanttSaveService()
    return _gantt_save_service
