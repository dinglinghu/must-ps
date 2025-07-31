"""
增强的任务管理器
基于现有TaskManager扩展，支持增强任务信息处理
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from .enhanced_task_info import EnhancedTaskInfo, ConflictInfo, VisibilityWindow
from .satellite_agent import TaskManager, TaskInfo
from google.adk.agents.invocation_context import InvocationContext

logger = logging.getLogger(__name__)

class EnhancedTaskManager(TaskManager):
    """增强的任务管理器"""
    
    def __init__(self, satellite_id: str, satellite_agent=None):
        super().__init__(satellite_id, satellite_agent)
        
        # 增强功能标志
        self.enhanced_capabilities = True
        self.enhancement_version = "1.0"
        
        # 增强任务存储
        self._enhanced_tasks: Dict[str, EnhancedTaskInfo] = {}
        
        # 冲突检测配置
        self.conflict_detection_enabled = True
        self.auto_conflict_resolution = True
        
        # 资源监控
        self.resource_monitoring_enabled = True
        self.resource_thresholds = {
            'power': 0.8,  # 80%功率阈值
            'storage': 0.9,  # 90%存储阈值
            'communication': 0.7  # 70%通信阈值
        }
        
        logger.info(f"✅ 增强任务管理器初始化完成: {satellite_id}")
    
    def add_enhanced_task(self, enhanced_task: EnhancedTaskInfo) -> bool:
        """添加增强任务"""
        try:
            logger.info(f"📋 添加增强任务: {enhanced_task.task_id}")
            
            # 1. 基础验证
            if not self._validate_enhanced_task(enhanced_task):
                logger.error(f"❌ 增强任务验证失败: {enhanced_task.task_id}")
                return False
            
            # 2. 冲突检测
            if self.conflict_detection_enabled:
                conflicts = self._detect_task_conflicts(enhanced_task)
                if conflicts:
                    logger.warning(f"⚠️ 检测到任务冲突: {len(conflicts)}个")
                    enhanced_task.potential_conflicts.extend(conflicts)
                    
                    # 自动冲突解决
                    if self.auto_conflict_resolution:
                        resolved = self._resolve_conflicts(enhanced_task, conflicts)
                        if not resolved:
                            logger.error(f"❌ 冲突解决失败: {enhanced_task.task_id}")
                            return False
            
            # 3. 资源检查
            resource_check = self._check_enhanced_resources(enhanced_task)
            if not resource_check['can_accept']:
                logger.error(f"❌ 资源检查失败: {resource_check['reason']}")
                return False
            
            # 4. 存储增强任务
            self._enhanced_tasks[enhanced_task.task_id] = enhanced_task
            
            # 5. 同时添加到基础任务管理器（向后兼容）
            basic_task = enhanced_task.to_basic_task_info()
            success = self.add_task(basic_task)
            
            if success:
                logger.info(f"✅ 增强任务添加成功: {enhanced_task.task_id}")
                return True
            else:
                # 回滚
                del self._enhanced_tasks[enhanced_task.task_id]
                logger.error(f"❌ 基础任务添加失败: {enhanced_task.task_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 添加增强任务异常: {e}")
            return False
    
    def get_enhanced_task(self, task_id: str) -> Optional[EnhancedTaskInfo]:
        """获取增强任务"""
        return self._enhanced_tasks.get(task_id)
    
    def get_all_enhanced_tasks(self) -> List[EnhancedTaskInfo]:
        """获取所有增强任务"""
        return list(self._enhanced_tasks.values())
    
    def _validate_enhanced_task(self, enhanced_task: EnhancedTaskInfo) -> bool:
        """验证增强任务"""
        try:
            # 基础验证
            if not enhanced_task.task_id or not enhanced_task.target_id:
                return False
            
            if enhanced_task.start_time >= enhanced_task.end_time:
                return False
            
            if not (0 <= enhanced_task.priority <= 1):
                return False
            
            # 增强验证
            if enhanced_task.observation_requirements:
                if enhanced_task.observation_requirements.min_observation_duration <= 0:
                    return False
                
                if enhanced_task.observation_requirements.min_elevation_angle < 0:
                    return False
            
            if enhanced_task.resource_requirements:
                if enhanced_task.resource_requirements.power_consumption < 0:
                    return False
                
                if enhanced_task.resource_requirements.storage_requirement < 0:
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ 任务验证异常: {e}")
            return False
    
    def _detect_task_conflicts(self, new_task: EnhancedTaskInfo) -> List[ConflictInfo]:
        """检测任务冲突"""
        conflicts = []
        
        try:
            # 与现有增强任务检查冲突
            for existing_task in self._enhanced_tasks.values():
                if existing_task.status in ['pending', 'executing']:
                    # 时间冲突检测
                    time_conflict = self._check_time_conflict(new_task, existing_task)
                    if time_conflict:
                        conflicts.append(time_conflict)
                    
                    # 资源冲突检测
                    resource_conflict = self._check_resource_conflict(new_task, existing_task)
                    if resource_conflict:
                        conflicts.append(resource_conflict)
                    
                    # 几何冲突检测
                    geometric_conflict = self._check_geometric_conflict(new_task, existing_task)
                    if geometric_conflict:
                        conflicts.append(geometric_conflict)
            
            return conflicts
            
        except Exception as e:
            logger.error(f"❌ 冲突检测异常: {e}")
            return []
    
    def _check_time_conflict(self, task1: EnhancedTaskInfo, task2: EnhancedTaskInfo) -> Optional[ConflictInfo]:
        """检查时间冲突"""
        try:
            # 检查时间重叠
            if not (task1.end_time <= task2.start_time or task1.start_time >= task2.end_time):
                # 计算重叠时间
                overlap_start = max(task1.start_time, task2.start_time)
                overlap_end = min(task1.end_time, task2.end_time)
                overlap_duration = (overlap_end - overlap_start).total_seconds()
                
                # 计算冲突严重性
                task1_duration = (task1.end_time - task1.start_time).total_seconds()
                task2_duration = (task2.end_time - task2.start_time).total_seconds()
                severity = overlap_duration / min(task1_duration, task2_duration)
                
                return ConflictInfo(
                    conflict_id=f"TIME_CONFLICT_{task1.task_id}_{task2.task_id}",
                    conflict_type="time",
                    severity=min(severity, 1.0),
                    conflicting_tasks=[task1.task_id, task2.task_id],
                    resolution_suggestions=[
                        {
                            'type': 'reschedule',
                            'description': f'重新调度任务 {task1.task_id} 或 {task2.task_id}',
                            'cost': severity * 0.5
                        },
                        {
                            'type': 'priority_override',
                            'description': f'基于优先级覆盖 (P1:{task1.priority}, P2:{task2.priority})',
                            'cost': abs(task1.priority - task2.priority) * 0.3
                        }
                    ]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 时间冲突检查异常: {e}")
            return None
    
    def _check_resource_conflict(self, task1: EnhancedTaskInfo, task2: EnhancedTaskInfo) -> Optional[ConflictInfo]:
        """检查资源冲突"""
        try:
            if not (task1.resource_requirements and task2.resource_requirements):
                return None
            
            # 检查功率冲突
            total_power = (task1.resource_requirements.power_consumption + 
                          task2.resource_requirements.power_consumption)
            
            # 假设卫星最大功率为1000W
            max_power = 1000.0
            if total_power > max_power:
                severity = (total_power - max_power) / max_power
                
                return ConflictInfo(
                    conflict_id=f"RESOURCE_CONFLICT_{task1.task_id}_{task2.task_id}",
                    conflict_type="resource",
                    severity=min(severity, 1.0),
                    conflicting_tasks=[task1.task_id, task2.task_id],
                    resolution_suggestions=[
                        {
                            'type': 'power_management',
                            'description': '降低功率消耗或错开执行时间',
                            'cost': severity * 0.4
                        },
                        {
                            'type': 'task_splitting',
                            'description': '将任务分解为更小的子任务',
                            'cost': severity * 0.6
                        }
                    ]
                )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 资源冲突检查异常: {e}")
            return None
    
    def _check_geometric_conflict(self, task1: EnhancedTaskInfo, task2: EnhancedTaskInfo) -> Optional[ConflictInfo]:
        """检查几何冲突"""
        try:
            # 简化的几何冲突检测
            # 检查是否需要同时指向不同方向
            
            # 如果两个任务的目标ID不同，可能存在指向冲突
            if task1.target_id != task2.target_id:
                # 检查时间重叠
                if not (task1.end_time <= task2.start_time or task1.start_time >= task2.end_time):
                    # 简化：假设不同目标需要不同指向，存在几何冲突
                    severity = 0.5  # 中等严重性
                    
                    return ConflictInfo(
                        conflict_id=f"GEOMETRIC_CONFLICT_{task1.task_id}_{task2.task_id}",
                        conflict_type="geometric",
                        severity=severity,
                        conflicting_tasks=[task1.task_id, task2.task_id],
                        resolution_suggestions=[
                            {
                                'type': 'sequential_execution',
                                'description': '顺序执行任务，避免同时指向',
                                'cost': severity * 0.3
                            },
                            {
                                'type': 'satellite_reassignment',
                                'description': '将其中一个任务分配给其他卫星',
                                'cost': severity * 0.7
                            }
                        ]
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ 几何冲突检查异常: {e}")
            return None
    
    def _resolve_conflicts(self, task: EnhancedTaskInfo, conflicts: List[ConflictInfo]) -> bool:
        """解决冲突"""
        try:
            logger.info(f"🔧 尝试解决 {len(conflicts)} 个冲突")
            
            for conflict in conflicts:
                # 选择成本最低的解决方案
                best_solution = min(conflict.resolution_suggestions, 
                                  key=lambda s: s.get('cost', 1.0))
                
                logger.info(f"   应用解决方案: {best_solution['type']} - {best_solution['description']}")
                
                # 这里可以实现具体的冲突解决逻辑
                # 目前只是记录，实际实现需要根据具体解决方案类型来处理
                
            return True
            
        except Exception as e:
            logger.error(f"❌ 冲突解决异常: {e}")
            return False
    
    def _check_enhanced_resources(self, task: EnhancedTaskInfo) -> Dict[str, Any]:
        """检查增强资源需求"""
        try:
            if not task.resource_requirements:
                return {'can_accept': True, 'reason': 'no_resource_requirements'}
            
            # 获取当前资源状态
            current_power_usage = self._calculate_current_power_usage()
            current_storage_usage = self._calculate_current_storage_usage()
            current_comm_usage = self._calculate_current_communication_usage()
            
            # 检查功率
            required_power = task.resource_requirements.power_consumption
            available_power = 1000.0 - current_power_usage  # 假设1000W总功率
            
            if required_power > available_power:
                return {
                    'can_accept': False,
                    'reason': 'insufficient_power',
                    'details': {
                        'required': required_power,
                        'available': available_power,
                        'current_usage': current_power_usage
                    }
                }
            
            # 检查存储
            required_storage = task.resource_requirements.storage_requirement
            available_storage = 10000.0 - current_storage_usage  # 假设10GB总存储
            
            if required_storage > available_storage:
                return {
                    'can_accept': False,
                    'reason': 'insufficient_storage',
                    'details': {
                        'required': required_storage,
                        'available': available_storage,
                        'current_usage': current_storage_usage
                    }
                }
            
            # 检查通信
            required_comm = task.resource_requirements.communication_requirement
            available_comm = 100.0 - current_comm_usage  # 假设100Mbps总带宽
            
            if required_comm > available_comm:
                return {
                    'can_accept': False,
                    'reason': 'insufficient_communication',
                    'details': {
                        'required': required_comm,
                        'available': available_comm,
                        'current_usage': current_comm_usage
                    }
                }
            
            return {
                'can_accept': True,
                'reason': 'sufficient_resources',
                'resource_impact': {
                    'power_usage_after': current_power_usage + required_power,
                    'storage_usage_after': current_storage_usage + required_storage,
                    'comm_usage_after': current_comm_usage + required_comm
                }
            }
            
        except Exception as e:
            logger.error(f"❌ 资源检查异常: {e}")
            return {'can_accept': False, 'reason': 'check_error', 'error': str(e)}
    
    def _calculate_current_power_usage(self) -> float:
        """计算当前功率使用"""
        total_power = 0.0
        for task in self._enhanced_tasks.values():
            if task.status == 'executing' and task.resource_requirements:
                total_power += task.resource_requirements.power_consumption
        return total_power
    
    def _calculate_current_storage_usage(self) -> float:
        """计算当前存储使用"""
        total_storage = 0.0
        for task in self._enhanced_tasks.values():
            if task.status in ['executing', 'completed'] and task.resource_requirements:
                total_storage += task.resource_requirements.storage_requirement
        return total_storage
    
    def _calculate_current_communication_usage(self) -> float:
        """计算当前通信使用"""
        total_comm = 0.0
        for task in self._enhanced_tasks.values():
            if task.status == 'executing' and task.resource_requirements:
                total_comm += task.resource_requirements.communication_requirement
        return total_comm
    
    def get_resource_utilization_report(self) -> Dict[str, Any]:
        """获取资源利用率报告"""
        try:
            current_power = self._calculate_current_power_usage()
            current_storage = self._calculate_current_storage_usage()
            current_comm = self._calculate_current_communication_usage()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'satellite_id': self.satellite_id,
                'power': {
                    'current_usage': current_power,
                    'max_capacity': 1000.0,
                    'utilization_rate': current_power / 1000.0,
                    'available': 1000.0 - current_power
                },
                'storage': {
                    'current_usage': current_storage,
                    'max_capacity': 10000.0,
                    'utilization_rate': current_storage / 10000.0,
                    'available': 10000.0 - current_storage
                },
                'communication': {
                    'current_usage': current_comm,
                    'max_capacity': 100.0,
                    'utilization_rate': current_comm / 100.0,
                    'available': 100.0 - current_comm
                },
                'active_enhanced_tasks': len([t for t in self._enhanced_tasks.values() 
                                            if t.status == 'executing']),
                'total_enhanced_tasks': len(self._enhanced_tasks)
            }
            
        except Exception as e:
            logger.error(f"❌ 资源利用率报告生成异常: {e}")
            return {'error': str(e)}
