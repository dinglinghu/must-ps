"""
现实预警星座系统甘特图可视化模块
支持多层次、多维度的任务规划可视化分析
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json
import os
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ConstellationGanttTask:
    """星座甘特图任务项"""
    task_id: str
    task_name: str
    start_time: datetime
    end_time: datetime
    
    # 分类信息
    category: str  # observation/communication/processing/coordination
    priority: int  # 1-5
    threat_level: int  # 1-5
    
    # 执行信息
    assigned_satellite: str
    target_missile: str
    execution_status: str  # planned/executing/completed/failed
    
    # 质量信息
    quality_score: float = 0.8  # 0-1
    resource_utilization: Dict[str, float] = field(default_factory=dict)
    
    @property
    def duration(self) -> float:
        """任务持续时间（秒）"""
        return (self.end_time - self.start_time).total_seconds()

@dataclass
class ConstellationGanttData:
    """星座甘特图数据结构"""
    chart_id: str
    chart_type: str
    creation_time: datetime
    mission_scenario: str
    
    # 时间轴信息
    start_time: datetime
    end_time: datetime
    
    # 任务和资源信息
    tasks: List[ConstellationGanttTask] = field(default_factory=list)
    satellites: List[str] = field(default_factory=list)
    missiles: List[str] = field(default_factory=list)
    
    # 元数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)

class RealisticConstellationGanttGenerator:
    """现实星座甘特图生成器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 颜色方案
        self.threat_colors = {
            5: '#FF0000',  # 红色 - 最高威胁
            4: '#FF6600',  # 橙色 - 高威胁
            3: '#FFCC00',  # 黄色 - 中等威胁
            2: '#66CC00',  # 绿色 - 低威胁
            1: '#0066CC'   # 蓝色 - 最低威胁
        }
        
        self.category_colors = {
            'observation': '#1f77b4',
            'communication': '#ff7f0e', 
            'processing': '#2ca02c',
            'coordination': '#d62728'
        }
        
        self.status_colors = {
            'planned': '#87CEEB',
            'executing': '#32CD32',
            'completed': '#228B22',
            'failed': '#DC143C'
        }
        
        logger.info("✅ 现实星座甘特图生成器初始化完成")
    
    def prepare_gantt_data_from_mission(self, mission_data: Dict[str, Any]) -> ConstellationGanttData:
        """从任务数据准备甘特图数据"""
        try:
            # 提取基础信息
            mission_id = mission_data.get('mission_id', f'MISSION_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
            
            # 创建甘特图数据结构
            gantt_data = ConstellationGanttData(
                chart_id=f"GANTT_{mission_id}",
                chart_type="constellation_mission",
                creation_time=datetime.now(),
                mission_scenario=mission_data.get('scenario_name', 'Unknown Scenario'),
                start_time=datetime.now(),
                end_time=datetime.now() + timedelta(hours=2)  # 默认2小时任务窗口
            )
            
            # 处理导弹信息
            missiles = mission_data.get('missiles', [])
            for missile in missiles:
                gantt_data.missiles.append(missile.get('missile_id', 'Unknown'))
            
            # 处理卫星信息
            satellites = mission_data.get('satellites', [])
            for satellite in satellites:
                gantt_data.satellites.append(satellite.get('satellite_id', 'Unknown'))
            
            # 处理任务分配信息
            task_assignments = mission_data.get('task_assignments', {})
            task_counter = 1
            
            for satellite_id, assigned_missiles in task_assignments.items():
                for missile_id in assigned_missiles:
                    # 查找对应的导弹信息
                    missile_info = next((m for m in missiles if m.get('missile_id') == missile_id), {})
                    
                    # 创建观测任务
                    task = ConstellationGanttTask(
                        task_id=f"TASK_{task_counter:03d}",
                        task_name=f"观测{missile_id}",
                        start_time=gantt_data.start_time + timedelta(minutes=task_counter * 5),
                        end_time=gantt_data.start_time + timedelta(minutes=task_counter * 5 + 30),
                        category='observation',
                        priority=missile_info.get('priority_level', 3),
                        threat_level=missile_info.get('threat_level', 3),
                        assigned_satellite=satellite_id,
                        target_missile=missile_id,
                        execution_status='planned',
                        quality_score=0.85,
                        resource_utilization={'power': 0.7, 'storage': 0.5, 'communication': 0.6}
                    )
                    
                    gantt_data.tasks.append(task)
                    task_counter += 1
            
            # 更新时间范围
            if gantt_data.tasks:
                gantt_data.start_time = min(task.start_time for task in gantt_data.tasks)
                gantt_data.end_time = max(task.end_time for task in gantt_data.tasks)
            
            # 添加性能指标
            gantt_data.performance_metrics = {
                'total_tasks': len(gantt_data.tasks),
                'total_satellites': len(gantt_data.satellites),
                'total_missiles': len(gantt_data.missiles),
                'avg_task_duration': np.mean([task.duration for task in gantt_data.tasks]) if gantt_data.tasks else 0,
                'mission_duration': (gantt_data.end_time - gantt_data.start_time).total_seconds()
            }
            
            logger.info(f"✅ 甘特图数据准备完成: {len(gantt_data.tasks)} 个任务")
            return gantt_data
            
        except Exception as e:
            logger.error(f"❌ 准备甘特图数据失败: {e}")
            raise
    
    def generate_constellation_task_gantt(
        self, 
        gantt_data: ConstellationGanttData,
        save_path: str = None
    ) -> str:
        """生成星座任务甘特图"""
        try:
            logger.info("🎨 开始生成星座任务甘特图...")
            
            # 创建图表
            fig, ax = plt.subplots(figsize=(16, 10))
            
            # 按卫星分组任务
            satellite_tasks = {}
            for task in gantt_data.tasks:
                if task.assigned_satellite not in satellite_tasks:
                    satellite_tasks[task.assigned_satellite] = []
                satellite_tasks[task.assigned_satellite].append(task)
            
            # 绘制任务条
            y_positions = {}
            y_pos = 0
            
            for satellite_id, tasks in satellite_tasks.items():
                y_positions[satellite_id] = y_pos
                
                for task in tasks:
                    # 根据威胁等级选择颜色
                    color = self.threat_colors.get(task.threat_level, '#808080')
                    
                    # 根据执行状态调整透明度
                    alpha = 0.9 if task.execution_status == 'completed' else 0.7
                    
                    # 绘制任务条
                    ax.barh(
                        y_pos, 
                        task.duration / 60,  # 转换为分钟
                        left=mdates.date2num(task.start_time),
                        height=0.6,
                        color=color,
                        alpha=alpha,
                        edgecolor='black',
                        linewidth=0.5
                    )
                    
                    # 添加任务标签
                    task_center = task.start_time + timedelta(seconds=task.duration/2)
                    ax.text(
                        mdates.date2num(task_center),
                        y_pos,
                        f"{task.target_missile}\n威胁:{task.threat_level}",
                        ha='center',
                        va='center',
                        fontsize=8,
                        fontweight='bold',
                        color='white' if task.threat_level >= 4 else 'black'
                    )
                
                y_pos += 1
            
            # 设置Y轴
            ax.set_yticks(list(y_positions.values()))
            ax.set_yticklabels(list(y_positions.keys()))
            ax.set_ylabel('卫星智能体', fontsize=12, fontweight='bold')
            
            # 设置X轴（时间轴）
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
            ax.set_xlabel('时间', fontsize=12, fontweight='bold')
            
            # 设置标题
            ax.set_title(
                f'现实预警星座任务分配甘特图\n{gantt_data.mission_scenario}',
                fontsize=16,
                fontweight='bold',
                pad=20
            )
            
            # 添加网格
            ax.grid(True, alpha=0.3, axis='x')
            
            # 添加图例
            threat_legend = []
            for level, color in self.threat_colors.items():
                threat_legend.append(plt.Rectangle((0,0),1,1, facecolor=color, label=f'威胁等级 {level}'))
            
            ax.legend(handles=threat_legend, loc='upper right', bbox_to_anchor=(1.15, 1))
            
            # 添加统计信息
            stats_text = f"""任务统计:
总任务数: {gantt_data.performance_metrics['total_tasks']}
参与卫星: {gantt_data.performance_metrics['total_satellites']}
目标导弹: {gantt_data.performance_metrics['total_missiles']}
任务时长: {gantt_data.performance_metrics['mission_duration']/3600:.1f}小时"""
            
            ax.text(
                0.02, 0.98, stats_text,
                transform=ax.transAxes,
                verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8),
                fontsize=10
            )
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"reports/gantt/constellation_task_gantt_{timestamp}.png"
            
            # 确保目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 保存为高分辨率PNG
            plt.savefig(save_path, dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            
            # 同时保存为SVG矢量格式
            svg_path = save_path.replace('.png', '.svg')
            plt.savefig(svg_path, format='svg', bbox_inches='tight')
            
            plt.close(fig)
            
            logger.info(f"✅ 星座任务甘特图已保存: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"❌ 生成星座任务甘特图失败: {e}")
            raise
    
    def generate_resource_utilization_gantt(
        self,
        gantt_data: ConstellationGanttData,
        save_path: str = None
    ) -> str:
        """生成资源利用率甘特图"""
        try:
            logger.info("🎨 开始生成资源利用率甘特图...")
            
            # 创建子图布局
            fig, axes = plt.subplots(3, 1, figsize=(16, 12))
            
            # 资源类型
            resource_types = ['power', 'storage', 'communication']
            resource_names = ['功率利用率', '存储利用率', '通信利用率']
            
            for idx, (resource_type, resource_name) in enumerate(zip(resource_types, resource_names)):
                ax = axes[idx]
                
                # 按卫星分组
                satellite_resources = {}
                for task in gantt_data.tasks:
                    satellite_id = task.assigned_satellite
                    if satellite_id not in satellite_resources:
                        satellite_resources[satellite_id] = []
                    
                    utilization = task.resource_utilization.get(resource_type, 0.5)
                    satellite_resources[satellite_id].append({
                        'start': task.start_time,
                        'end': task.end_time,
                        'utilization': utilization
                    })
                
                # 绘制资源利用率
                y_pos = 0
                for satellite_id, resources in satellite_resources.items():
                    for resource in resources:
                        # 颜色根据利用率确定
                        if resource['utilization'] > 0.8:
                            color = '#FF4444'  # 高利用率 - 红色
                        elif resource['utilization'] > 0.6:
                            color = '#FFAA00'  # 中等利用率 - 橙色
                        else:
                            color = '#44AA44'  # 低利用率 - 绿色
                        
                        duration = (resource['end'] - resource['start']).total_seconds() / 60
                        
                        ax.barh(
                            y_pos,
                            duration,
                            left=mdates.date2num(resource['start']),
                            height=0.6,
                            color=color,
                            alpha=0.7,
                            edgecolor='black',
                            linewidth=0.5
                        )
                        
                        # 添加利用率标签
                        center_time = resource['start'] + timedelta(seconds=(resource['end'] - resource['start']).total_seconds()/2)
                        ax.text(
                            mdates.date2num(center_time),
                            y_pos,
                            f"{resource['utilization']:.1%}",
                            ha='center',
                            va='center',
                            fontsize=8,
                            fontweight='bold',
                            color='white'
                        )
                    
                    y_pos += 1
                
                # 设置轴标签
                ax.set_yticks(range(len(satellite_resources)))
                ax.set_yticklabels(list(satellite_resources.keys()))
                ax.set_ylabel('卫星', fontsize=10)
                ax.set_title(resource_name, fontsize=12, fontweight='bold')
                
                # 设置时间轴
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
                
                # 添加网格
                ax.grid(True, alpha=0.3, axis='x')
            
            # 设置总标题
            fig.suptitle(
                f'现实预警星座资源利用率甘特图\n{gantt_data.mission_scenario}',
                fontsize=16,
                fontweight='bold'
            )
            
            # 添加图例
            legend_elements = [
                plt.Rectangle((0,0),1,1, facecolor='#FF4444', alpha=0.7, label='高利用率 (>80%)'),
                plt.Rectangle((0,0),1,1, facecolor='#FFAA00', alpha=0.7, label='中等利用率 (60-80%)'),
                plt.Rectangle((0,0),1,1, facecolor='#44AA44', alpha=0.7, label='低利用率 (<60%)')
            ]
            
            axes[0].legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"reports/gantt/resource_utilization_gantt_{timestamp}.png"
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            plt.savefig(save_path, dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            
            # 保存SVG版本
            svg_path = save_path.replace('.png', '.svg')
            plt.savefig(svg_path, format='svg', bbox_inches='tight')
            
            plt.close(fig)
            
            logger.info(f"✅ 资源利用率甘特图已保存: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"❌ 生成资源利用率甘特图失败: {e}")
            raise
    
    def save_gantt_data_json(self, gantt_data: ConstellationGanttData, save_path: str = None) -> str:
        """保存甘特图数据为JSON格式"""
        try:
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"reports/gantt/gantt_data_{timestamp}.json"
            
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            # 转换数据为可序列化格式
            data_dict = {
                'chart_id': gantt_data.chart_id,
                'chart_type': gantt_data.chart_type,
                'creation_time': gantt_data.creation_time.isoformat(),
                'mission_scenario': gantt_data.mission_scenario,
                'start_time': gantt_data.start_time.isoformat(),
                'end_time': gantt_data.end_time.isoformat(),
                'satellites': gantt_data.satellites,
                'missiles': gantt_data.missiles,
                'performance_metrics': gantt_data.performance_metrics,
                'metadata': gantt_data.metadata,
                'tasks': []
            }
            
            for task in gantt_data.tasks:
                task_dict = {
                    'task_id': task.task_id,
                    'task_name': task.task_name,
                    'start_time': task.start_time.isoformat(),
                    'end_time': task.end_time.isoformat(),
                    'duration': task.duration,
                    'category': task.category,
                    'priority': task.priority,
                    'threat_level': task.threat_level,
                    'assigned_satellite': task.assigned_satellite,
                    'target_missile': task.target_missile,
                    'execution_status': task.execution_status,
                    'quality_score': task.quality_score,
                    'resource_utilization': task.resource_utilization
                }
                data_dict['tasks'].append(task_dict)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(data_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 甘特图数据已保存为JSON: {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"❌ 保存甘特图数据失败: {e}")
            raise
