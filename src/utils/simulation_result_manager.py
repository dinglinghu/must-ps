#!/usr/bin/env python3
"""
仿真结果管理器
负责保存仿真结果、生成甘特图等功能
"""

import os
import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class SimulationResultManager:
    """仿真结果管理器"""
    
    def __init__(self, base_output_dir: str = "simulation_results"):
        """
        初始化仿真结果管理器
        
        Args:
            base_output_dir: 基础输出目录
        """
        self.base_output_dir = Path(base_output_dir)
        self.base_output_dir.mkdir(exist_ok=True)
        
        # 当前仿真会话
        self.current_session_id = None
        self.current_session_dir = None
        
    def create_simulation_session(self, session_name: str = None) -> str:
        """
        创建新的仿真会话
        
        Args:
            session_name: 会话名称，如果为None则自动生成
            
        Returns:
            会话ID
        """
        # 生成会话ID和目录名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_id = str(uuid.uuid4())[:8]
        
        if session_name:
            dir_name = f"{timestamp}_{session_name}_{session_id}"
        else:
            dir_name = f"{timestamp}_simulation_{session_id}"
        
        # 创建会话目录
        self.current_session_dir = self.base_output_dir / dir_name
        self.current_session_dir.mkdir(exist_ok=True)
        
        # 创建子目录
        (self.current_session_dir / "meta_tasks").mkdir(exist_ok=True)
        (self.current_session_dir / "planning_results").mkdir(exist_ok=True)
        (self.current_session_dir / "gantt_charts").mkdir(exist_ok=True)
        (self.current_session_dir / "logs").mkdir(exist_ok=True)
        
        self.current_session_id = session_id
        
        # 保存会话信息
        session_info = {
            "session_id": session_id,
            "session_name": session_name or "simulation",
            "created_time": datetime.now().isoformat(),
            "directory": str(self.current_session_dir),
            "status": "active"
        }
        
        with open(self.current_session_dir / "session_info.json", 'w', encoding='utf-8') as f:
            json.dump(session_info, f, ensure_ascii=False, indent=2)
        
        logger.info(f"创建仿真会话: {session_id}, 目录: {self.current_session_dir}")
        return session_id
    
    def save_meta_tasks(self, meta_tasks: List[Dict[str, Any]], filename: str = None) -> str:
        """
        保存元任务为JSON格式
        
        Args:
            meta_tasks: 元任务列表
            filename: 文件名，如果为None则自动生成
            
        Returns:
            保存的文件路径
        """
        if not self.current_session_dir:
            raise ValueError("没有活动的仿真会话")
        
        if filename is None:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"meta_tasks_{timestamp}.json"
        
        filepath = self.current_session_dir / "meta_tasks" / filename
        
        # 添加元数据
        meta_tasks_data = {
            "metadata": {
                "session_id": self.current_session_id,
                "created_time": datetime.now().isoformat(),
                "total_tasks": len(meta_tasks),
                "version": "1.0"
            },
            "meta_tasks": meta_tasks
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(meta_tasks_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存元任务到: {filepath}")
        return str(filepath)
    
    def save_planning_results(self, planning_results: Dict[str, Any], filename: str = None) -> str:
        """
        保存规划结果
        
        Args:
            planning_results: 规划结果
            filename: 文件名，如果为None则自动生成
            
        Returns:
            保存的文件路径
        """
        if not self.current_session_dir:
            raise ValueError("没有活动的仿真会话")
        
        if filename is None:
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"planning_results_{timestamp}.json"
        
        filepath = self.current_session_dir / "planning_results" / filename
        
        # 添加元数据
        results_data = {
            "metadata": {
                "session_id": self.current_session_id,
                "created_time": datetime.now().isoformat(),
                "version": "1.0"
            },
            "planning_results": planning_results
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存规划结果到: {filepath}")
        return str(filepath)
    
    def generate_meta_task_gantt_data(self, meta_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        生成元任务甘特图数据
        
        Args:
            meta_tasks: 元任务列表
            
        Returns:
            甘特图数据
        """
        gantt_data = {
            "chart_type": "meta_task_gantt",
            "title": "天基预警元任务分解甘特图",
            "x_axis": {
                "label": "时间轴",
                "type": "datetime"
            },
            "y_axis": {
                "label": "预警目标",
                "categories": []
            },
            "tasks": [],
            "colors": {
                "meta_task": "#1f77b4",
                "flight_phase": "#ff7f0e",
                "observation_window": "#2ca02c"
            }
        }
        
        # 提取所有导弹目标ID
        target_ids = set()
        for task in meta_tasks:
            if 'target_id' in task:
                target_ids.add(task['target_id'])
        
        gantt_data["y_axis"]["categories"] = sorted(list(target_ids))
        
        # 生成任务条目
        for task in meta_tasks:
            if 'target_id' in task and 'start_time' in task and 'end_time' in task:
                gantt_task = {
                    "id": task.get('task_id', str(uuid.uuid4())),
                    "name": f"元任务-{task['target_id']}",
                    "category": task['target_id'],
                    "start": task['start_time'],
                    "end": task['end_time'],
                    "type": "meta_task",
                    "description": task.get('description', ''),
                    "priority": task.get('priority', 1)
                }
                gantt_data["tasks"].append(gantt_task)
        
        return gantt_data
    
    def generate_planning_gantt_data(self, planning_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成任务规划调度甘特图数据
        
        Args:
            planning_results: 规划结果
            
        Returns:
            甘特图数据
        """
        gantt_data = {
            "chart_type": "planning_gantt",
            "title": "协同调度方案甘特图",
            "x_axis": {
                "label": "时间轴",
                "type": "datetime"
            },
            "y_axis": {
                "label": "预警目标",
                "categories": []
            },
            "tasks": [],
            "colors": {
                "observation": "#2E8B57",      # 海绿色 - 观测任务
                "communication": "#4169E1",    # 皇家蓝 - 通信任务
                "data_transmission": "#FF6347", # 番茄红 - 数据传输
                "maintenance": "#9370DB",       # 中紫色 - 维护任务
                "maneuver": "#FF8C00",         # 深橙色 - 机动任务
                "standby": "#708090"           # 石板灰 - 待机状态
            }
        }
        
        # 提取目标列表（用于纵轴分组）
        targets = set()
        if 'satellite_assignments' in planning_results:
            for assignment in planning_results['satellite_assignments']:
                target_id = assignment.get('target_id', assignment.get('satellite_id', 'Unknown'))
                targets.add(target_id)

        gantt_data["y_axis"]["categories"] = sorted(list(targets))
        
        # 生成任务条目
        if 'satellite_assignments' in planning_results:
            for assignment in planning_results['satellite_assignments']:
                if all(key in assignment for key in ['satellite_id', 'start_time', 'end_time']):
                    gantt_task = {
                        "id": assignment.get('assignment_id', str(uuid.uuid4())),
                        "name": assignment.get('task_name', '未知任务'),
                        "category": assignment['satellite_id'],
                        "start": assignment['start_time'],
                        "end": assignment['end_time'],
                        "type": assignment.get('task_type', 'observation'),
                        "description": assignment.get('description', ''),
                        "priority": assignment.get('priority', 1),
                        "target_id": assignment.get('target_id', '')
                    }
                    gantt_data["tasks"].append(gantt_task)
        
        return gantt_data
    
    def save_gantt_chart_data(self, gantt_data: Dict[str, Any], chart_type: str = "gantt") -> str:
        """
        保存甘特图数据
        
        Args:
            gantt_data: 甘特图数据
            chart_type: 图表类型
            
        Returns:
            保存的文件路径
        """
        if not self.current_session_dir:
            raise ValueError("没有活动的仿真会话")
        
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"{chart_type}_{timestamp}.json"
        filepath = self.current_session_dir / "gantt_charts" / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(gantt_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"保存甘特图数据到: {filepath}")
        return str(filepath)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        获取当前会话摘要
        
        Returns:
            会话摘要信息
        """
        if not self.current_session_dir:
            return {"error": "没有活动的仿真会话"}
        
        summary = {
            "session_id": self.current_session_id,
            "session_dir": str(self.current_session_dir),
            "files": {
                "meta_tasks": [],
                "planning_results": [],
                "gantt_charts": [],
                "logs": []
            }
        }
        
        # 统计各类文件
        for subdir in ["meta_tasks", "planning_results", "gantt_charts", "logs"]:
            subdir_path = self.current_session_dir / subdir
            if subdir_path.exists():
                files = [f.name for f in subdir_path.iterdir() if f.is_file()]
                summary["files"][subdir] = files
        
        return summary


# 全局实例
_simulation_result_manager = None

def get_simulation_result_manager() -> SimulationResultManager:
    """获取仿真结果管理器实例"""
    global _simulation_result_manager
    if _simulation_result_manager is None:
        _simulation_result_manager = SimulationResultManager()
    return _simulation_result_manager
