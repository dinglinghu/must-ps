"""
元任务与智能体集成模块
扩展现有的元任务管理器以支持多智能体协同
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict

from ..meta_task.meta_task_manager import MetaTaskManager, MetaTaskSet, MetaTaskWindow
# 🧹 已清理：from ..meta_task.gantt_chart_generator import GanttChartGenerator

logger = logging.getLogger(__name__)


@dataclass
class AgentTaskAssignment:
    """智能体任务分配数据结构"""
    assignment_id: str
    target_id: str
    satellite_id: str
    meta_windows: List[str]  # 分配的元任务窗口ID列表
    visibility_windows: List[Dict[str, Any]]  # 对应的可见窗口
    optimization_score: float
    assignment_time: datetime
    status: str  # 'assigned', 'accepted', 'rejected', 'completed'


@dataclass
class CoordinationResult:
    """协调结果数据结构"""
    result_id: str
    target_id: str
    discussion_group_id: str
    assignments: List[AgentTaskAssignment]
    total_coverage: float  # 总覆盖率
    average_gdop: float  # 平均GDOP
    resource_utilization: float  # 资源利用率
    coordination_time: datetime
    gantt_chart_path: Optional[str] = None


class MetaTaskAgentIntegration:
    """
    元任务与智能体集成管理器
    
    负责将元任务信息转换为智能体可处理的格式，
    以及收集智能体协调结果并生成最终规划方案
    """
    
    def __init__(
        self,
        meta_task_manager: MetaTaskManager,
        gantt_generator: Optional[object] = None  # 🧹 已清理：GanttChartGenerator类型
    ):
        """
        初始化集成管理器

        Args:
            meta_task_manager: 元任务管理器实例
            gantt_generator: 甘特图生成器实例（已清理，保留参数兼容性）
        """
        self.meta_task_manager = meta_task_manager
        self.gantt_generator = None  # 🧹 已清理：甘特图生成器功能已删除
        
        # 存储分配和结果
        self.task_assignments: Dict[str, List[AgentTaskAssignment]] = {}
        self.coordination_results: Dict[str, CoordinationResult] = {}
        
        logger.info("🔗 元任务智能体集成管理器初始化完成")
    
    def prepare_meta_tasks_for_agents(
        self,
        meta_task_set: MetaTaskSet,
        target_id: str
    ) -> Dict[str, Any]:
        """
        为智能体准备元任务信息
        
        Args:
            meta_task_set: 元任务集合
            target_id: 目标ID
            
        Returns:
            格式化的元任务信息
        """
        try:
            # 筛选指定目标的元任务窗口
            target_windows = []
            for window in meta_task_set.meta_windows:
                if target_id in window.missiles:
                    target_windows.append(window)
            
            if not target_windows:
                logger.warning(f"目标 {target_id} 没有对应的元任务窗口")
                return {}
            
            # 转换为智能体可理解的格式
            agent_meta_tasks = {
                'target_id': target_id,
                'collection_time': meta_task_set.collection_time.isoformat(),
                'time_range': {
                    'start': meta_task_set.time_range[0].isoformat(),
                    'end': meta_task_set.time_range[1].isoformat()
                },
                'meta_windows': [],
                'total_windows': len(target_windows),
                'alignment_resolution': meta_task_set.alignment_resolution
            }
            
            # 处理每个元任务窗口
            for window in target_windows:
                window_data = {
                    'window_id': window.window_id,
                    'start_time': window.start_time.isoformat(),
                    'end_time': window.end_time.isoformat(),
                    'duration': window.duration,
                    'trajectory_segment': window.trajectory_segments.get(target_id, []),
                    'visibility_info': window.visibility_windows.get(target_id, {}),
                    'priority': self._calculate_window_priority(window, target_id),
                    'metadata': {
                        'window_index': len(agent_meta_tasks['meta_windows']),
                        'missiles_in_window': window.missiles,
                        'has_trajectory': target_id in window.trajectory_segments,
                        'has_visibility': target_id in window.visibility_windows
                    }
                }
                
                agent_meta_tasks['meta_windows'].append(window_data)
            
            logger.info(f"✅ 为目标 {target_id} 准备了 {len(target_windows)} 个元任务窗口")
            
            return agent_meta_tasks
            
        except Exception as e:
            logger.error(f"❌ 准备智能体元任务信息失败: {e}")
            return {}
    
    def create_visibility_based_meta_tasks(
        self,
        meta_task_set: MetaTaskSet,
        visibility_windows: Dict[str, Dict[str, List[Dict[str, Any]]]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        基于可见窗口创建可见性元任务
        
        Args:
            meta_task_set: 元任务集合
            visibility_windows: 可见窗口信息 {target_id: {satellite_id: [windows]}}
            
        Returns:
            按目标分组的可见性元任务
        """
        try:
            visibility_meta_tasks = {}
            
            for target_id, satellite_windows in visibility_windows.items():
                visibility_meta_tasks[target_id] = []
                
                # 获取目标的元任务窗口
                target_meta_windows = [
                    mw for mw in meta_task_set.meta_windows 
                    if target_id in mw.missiles
                ]
                
                # 为每个卫星的可见窗口创建可见性元任务
                for satellite_id, vis_windows in satellite_windows.items():
                    for vis_window in vis_windows:
                        # 找到与可见窗口重叠的元任务窗口
                        overlapping_windows = self._find_overlapping_meta_windows(
                            vis_window, target_meta_windows
                        )
                        
                        for meta_window in overlapping_windows:
                            vis_meta_task = {
                                'meta_task_id': f"vis_{target_id}_{satellite_id}_{meta_window.window_id}",
                                'target_id': target_id,
                                'satellite_id': satellite_id,
                                'meta_window_id': meta_window.window_id,
                                'visibility_window': vis_window,
                                'meta_window_info': {
                                    'start_time': meta_window.start_time.isoformat(),
                                    'end_time': meta_window.end_time.isoformat(),
                                    'duration': meta_window.duration,
                                    'trajectory_segment': meta_window.trajectory_segments.get(target_id, [])
                                },
                                'quality_score': self._calculate_visibility_quality(vis_window, meta_window),
                                'overlap_info': self._calculate_overlap_info(vis_window, meta_window)
                            }
                            
                            visibility_meta_tasks[target_id].append(vis_meta_task)
            
            total_vis_tasks = sum(len(tasks) for tasks in visibility_meta_tasks.values())
            logger.info(f"✅ 创建了 {total_vis_tasks} 个可见性元任务")
            
            return visibility_meta_tasks
            
        except Exception as e:
            logger.error(f"❌ 创建可见性元任务失败: {e}")
            return {}
    
    def process_coordination_result(
        self,
        target_id: str,
        discussion_group_id: str,
        agent_decisions: List[Dict[str, Any]],
        coordination_time: datetime
    ) -> CoordinationResult:
        """
        处理智能体协调结果
        
        Args:
            target_id: 目标ID
            discussion_group_id: 讨论组ID
            agent_decisions: 智能体决策列表
            coordination_time: 协调时间
            
        Returns:
            协调结果
        """
        try:
            assignments = []
            
            # 处理每个智能体的决策
            for decision in agent_decisions:
                satellite_id = decision.get('satellite_id')
                assigned_windows = decision.get('assigned_windows', [])
                visibility_windows = decision.get('visibility_windows', [])
                optimization_score = decision.get('optimization_score', 0.0)
                
                if satellite_id and assigned_windows:
                    assignment = AgentTaskAssignment(
                        assignment_id=f"assign_{target_id}_{satellite_id}_{coordination_time.strftime('%H%M%S')}",
                        target_id=target_id,
                        satellite_id=satellite_id,
                        meta_windows=assigned_windows,
                        visibility_windows=visibility_windows,
                        optimization_score=optimization_score,
                        assignment_time=coordination_time,
                        status='assigned'
                    )
                    
                    assignments.append(assignment)
            
            # 计算总体指标
            total_coverage = self._calculate_total_coverage(assignments)
            average_gdop = self._calculate_average_gdop(assignments)
            resource_utilization = self._calculate_resource_utilization(assignments)
            
            # 🧹 已清理：甘特图生成功能已删除
            gantt_chart_path = None
            
            # 创建协调结果
            result = CoordinationResult(
                result_id=f"coord_{target_id}_{coordination_time.strftime('%Y%m%d_%H%M%S')}",
                target_id=target_id,
                discussion_group_id=discussion_group_id,
                assignments=assignments,
                total_coverage=total_coverage,
                average_gdop=average_gdop,
                resource_utilization=resource_utilization,
                coordination_time=coordination_time,
                gantt_chart_path=gantt_chart_path
            )
            
            # 保存结果
            self.coordination_results[result.result_id] = result
            self.task_assignments[target_id] = assignments
            
            logger.info(f"✅ 处理协调结果完成: {len(assignments)} 个分配，覆盖率 {total_coverage:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 处理协调结果失败: {e}")
            return None
    
    def export_coordination_results(self, output_dir: str = "output/coordination_results") -> Dict[str, str]:
        """
        导出协调结果
        
        Args:
            output_dir: 输出目录
            
        Returns:
            导出文件路径字典
        """
        try:
            from pathlib import Path
            
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)
            
            exported_files = {}
            
            for result_id, result in self.coordination_results.items():
                # 导出JSON格式结果
                json_file = output_path / f"{result_id}.json"
                
                result_data = {
                    'result_id': result.result_id,
                    'target_id': result.target_id,
                    'discussion_group_id': result.discussion_group_id,
                    'coordination_time': result.coordination_time.isoformat(),
                    'total_coverage': result.total_coverage,
                    'average_gdop': result.average_gdop,
                    'resource_utilization': result.resource_utilization,
                    'gantt_chart_path': result.gantt_chart_path,
                    'assignments': [
                        {
                            'assignment_id': assign.assignment_id,
                            'satellite_id': assign.satellite_id,
                            'meta_windows': assign.meta_windows,
                            'optimization_score': assign.optimization_score,
                            'assignment_time': assign.assignment_time.isoformat(),
                            'status': assign.status,
                            'visibility_windows_count': len(assign.visibility_windows)
                        }
                        for assign in result.assignments
                    ]
                }
                
                with open(json_file, 'w', encoding='utf-8') as f:
                    json.dump(result_data, f, indent=2, ensure_ascii=False)
                
                exported_files[result_id] = str(json_file)
            
            logger.info(f"✅ 导出了 {len(exported_files)} 个协调结果文件")
            
            return exported_files
            
        except Exception as e:
            logger.error(f"❌ 导出协调结果失败: {e}")
            return {}
    
    # 辅助方法
    def _calculate_window_priority(self, window: MetaTaskWindow, target_id: str) -> float:
        """计算窗口优先级"""
        try:
            # 基于轨迹数据质量和可见性信息计算优先级
            priority = 0.5  # 基础优先级
            
            # 轨迹数据质量因子
            if target_id in window.trajectory_segments:
                trajectory_points = len(window.trajectory_segments[target_id])
                priority += min(0.3, trajectory_points / 100.0)  # 最多加0.3
            
            # 可见性因子
            if target_id in window.visibility_windows:
                visibility_count = sum(
                    len(windows) for windows in window.visibility_windows[target_id].values()
                )
                priority += min(0.2, visibility_count / 10.0)  # 最多加0.2
            
            return min(1.0, priority)
            
        except Exception:
            return 0.5
    
    def _find_overlapping_meta_windows(
        self,
        vis_window: Dict[str, Any],
        meta_windows: List[MetaTaskWindow]
    ) -> List[MetaTaskWindow]:
        """找到与可见窗口重叠的元任务窗口"""
        try:
            overlapping = []
            
            vis_start = datetime.fromisoformat(vis_window['start'])
            vis_end = datetime.fromisoformat(vis_window['end'])
            
            for meta_window in meta_windows:
                # 检查时间重叠
                if not (meta_window.end_time <= vis_start or meta_window.start_time >= vis_end):
                    overlapping.append(meta_window)
            
            return overlapping
            
        except Exception as e:
            logger.error(f"查找重叠窗口失败: {e}")
            return []
    
    def _calculate_visibility_quality(self, vis_window: Dict[str, Any], meta_window: MetaTaskWindow) -> float:
        """计算可见性质量分数"""
        try:
            # 基于持续时间、高度角等计算质量分数
            duration = vis_window.get('duration', 0)
            max_elevation = vis_window.get('max_elevation', 0)
            
            # 持续时间因子 (0-0.5)
            duration_factor = min(0.5, duration / 600.0)  # 10分钟为满分
            
            # 高度角因子 (0-0.5)
            elevation_factor = min(0.5, max_elevation / 90.0)
            
            return duration_factor + elevation_factor
            
        except Exception:
            return 0.5
    
    def _calculate_overlap_info(self, vis_window: Dict[str, Any], meta_window: MetaTaskWindow) -> Dict[str, Any]:
        """计算重叠信息"""
        try:
            vis_start = datetime.fromisoformat(vis_window['start'])
            vis_end = datetime.fromisoformat(vis_window['end'])
            
            # 计算重叠时间段
            overlap_start = max(vis_start, meta_window.start_time)
            overlap_end = min(vis_end, meta_window.end_time)
            
            overlap_duration = (overlap_end - overlap_start).total_seconds()
            
            return {
                'overlap_start': overlap_start.isoformat(),
                'overlap_end': overlap_end.isoformat(),
                'overlap_duration': overlap_duration,
                'overlap_ratio': overlap_duration / meta_window.duration
            }
            
        except Exception:
            return {'overlap_duration': 0, 'overlap_ratio': 0}
    
    def _calculate_total_coverage(self, assignments: List[AgentTaskAssignment]) -> float:
        """计算总覆盖率"""
        # 简化实现，基于分配的窗口数量
        if not assignments:
            return 0.0
        
        total_windows = sum(len(assign.meta_windows) for assign in assignments)
        return min(1.0, total_windows / 10.0)  # 假设10个窗口为满覆盖
    
    def _calculate_average_gdop(self, assignments: List[AgentTaskAssignment]) -> float:
        """计算平均GDOP"""
        # 简化实现，基于优化分数
        if not assignments:
            return float('inf')
        
        scores = [assign.optimization_score for assign in assignments]
        return 1.0 / max(0.001, sum(scores) / len(scores))  # 转换为GDOP值
    
    def _calculate_resource_utilization(self, assignments: List[AgentTaskAssignment]) -> float:
        """计算资源利用率"""
        # 简化实现，基于分配的卫星数量
        if not assignments:
            return 0.0
        
        unique_satellites = len(set(assign.satellite_id for assign in assignments))
        return min(1.0, unique_satellites / 5.0)  # 假设5颗卫星为满利用
    
    # 🧹 已清理：_generate_coordination_gantt_chart 方法已删除
    # 原因：甘特图功能在当前GDOP分析流程中未被使用
