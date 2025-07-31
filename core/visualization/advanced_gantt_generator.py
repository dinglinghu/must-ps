"""
高级甘特图生成器
支持完整的图形化甘特图生成和保存功能
"""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
import seaborn as sns
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

# 设置matplotlib中文支持
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 设置seaborn样式
sns.set_style("whitegrid")
sns.set_palette("husl")

logger = logging.getLogger(__name__)

class AdvancedGanttGenerator:
    """高级甘特图生成器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        
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
            'coordination': '#d62728',
            'stk_calculation': '#9467bd',
            'data_downlink': '#8c564b'
        }
        
        self.status_colors = {
            'planned': '#87CEEB',
            'executing': '#32CD32',
            'completed': '#228B22',
            'failed': '#DC143C',
            'cancelled': '#808080'
        }
        
        # 确保输出目录存在
        self.output_dirs = {
            'matplotlib': 'reports/gantt/matplotlib',
            'plotly': 'reports/gantt/plotly',
            'seaborn': 'reports/gantt/seaborn',
            'combined': 'reports/gantt/combined'
        }
        
        for dir_path in self.output_dirs.values():
            os.makedirs(dir_path, exist_ok=True)
        
        logger.info("✅ 高级甘特图生成器初始化完成")
    
    def generate_matplotlib_gantt(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None,
        chart_type: str = "task_allocation"
    ) -> str:
        """使用matplotlib生成甘特图"""
        try:
            logger.info(f"🎨 使用matplotlib生成{chart_type}甘特图...")
            
            # 创建图表
            fig, ax = plt.subplots(figsize=(16, 10))
            
            if chart_type == "task_allocation":
                return self._generate_matplotlib_task_allocation(gantt_data, ax, fig, save_path)
            elif chart_type == "resource_utilization":
                return self._generate_matplotlib_resource_utilization(gantt_data, ax, fig, save_path)
            elif chart_type == "timeline_overview":
                return self._generate_matplotlib_timeline_overview(gantt_data, ax, fig, save_path)
            else:
                raise ValueError(f"不支持的图表类型: {chart_type}")
                
        except Exception as e:
            logger.error(f"❌ matplotlib甘特图生成失败: {e}")
            raise
    
    def _generate_matplotlib_task_allocation(
        self,
        gantt_data: Dict[str, Any],
        ax,
        fig,
        save_path: str = None
    ) -> str:
        """生成任务分配甘特图"""
        try:
            tasks = gantt_data.get('tasks', [])
            satellites = gantt_data.get('satellites', [])
            
            # 按卫星分组任务
            satellite_tasks = {}
            for task in tasks:
                satellite_id = task.get('assigned_satellite', 'Unknown')
                if satellite_id not in satellite_tasks:
                    satellite_tasks[satellite_id] = []
                satellite_tasks[satellite_id].append(task)
            
            # 创建Y轴位置映射
            y_positions = {sat: i for i, sat in enumerate(satellites)}
            
            # 绘制任务条
            for satellite_id, sat_tasks in satellite_tasks.items():
                y_pos = y_positions.get(satellite_id, 0)
                
                for task in sat_tasks:
                    # 解析时间
                    start_time = datetime.fromisoformat(task['start_time'])
                    duration_hours = task.get('duration_minutes', 30) / 60.0
                    
                    # 选择颜色
                    threat_level = task.get('threat_level', 3)
                    color = self.threat_colors.get(threat_level, '#808080')
                    
                    # 绘制任务条
                    rect = patches.Rectangle(
                        (mdates.date2num(start_time), y_pos - 0.4),
                        duration_hours / 24,  # 转换为天数单位
                        0.8,
                        facecolor=color,
                        edgecolor='black',
                        linewidth=1,
                        alpha=0.8
                    )
                    ax.add_patch(rect)
                    
                    # 添加任务标签
                    task_center = start_time + timedelta(minutes=task.get('duration_minutes', 30)/2)
                    ax.text(
                        mdates.date2num(task_center),
                        y_pos,
                        f"{task.get('target_missile', 'Unknown')}\n威胁:{threat_level}",
                        ha='center',
                        va='center',
                        fontsize=8,
                        fontweight='bold',
                        color='white' if threat_level >= 4 else 'black'
                    )
            
            # 设置坐标轴
            ax.set_yticks(list(y_positions.values()))
            ax.set_yticklabels(list(y_positions.keys()))
            ax.set_ylabel('卫星智能体', fontsize=12, fontweight='bold')
            
            # 设置时间轴
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
            ax.set_xlabel('时间', fontsize=12, fontweight='bold')
            
            # 设置标题
            mission_id = gantt_data.get('mission_id', 'Unknown')
            ax.set_title(
                f'现实预警星座任务分配甘特图\n任务ID: {mission_id}',
                fontsize=16,
                fontweight='bold',
                pad=20
            )
            
            # 添加网格
            ax.grid(True, alpha=0.3, axis='x')
            
            # 添加图例
            threat_legend = []
            for level, color in self.threat_colors.items():
                threat_legend.append(
                    patches.Patch(facecolor=color, label=f'威胁等级 {level}')
                )
            
            ax.legend(handles=threat_legend, loc='upper right', bbox_to_anchor=(1.15, 1))
            
            # 添加统计信息
            stats = gantt_data.get('statistics', {})
            stats_text = f"""任务统计:
总任务数: {stats.get('total_tasks', 0)}
参与卫星: {stats.get('total_satellites', 0)}
目标导弹: {stats.get('total_missiles', 0)}"""
            
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
                save_path = f"{self.output_dirs['matplotlib']}/task_allocation_{timestamp}.png"
            
            # 保存为多种格式
            base_path = save_path.rsplit('.', 1)[0]
            
            # PNG格式（高分辨率）
            plt.savefig(f"{base_path}.png", dpi=300, bbox_inches='tight', 
                       facecolor='white', edgecolor='none')
            
            # SVG格式（矢量）
            plt.savefig(f"{base_path}.svg", format='svg', bbox_inches='tight')
            
            # PDF格式（打印）
            plt.savefig(f"{base_path}.pdf", format='pdf', bbox_inches='tight')
            
            plt.close(fig)
            
            logger.info(f"✅ matplotlib任务分配甘特图已保存: {base_path}")
            return f"{base_path}.png"
            
        except Exception as e:
            logger.error(f"❌ 生成matplotlib任务分配甘特图失败: {e}")
            raise
    
    def _generate_matplotlib_resource_utilization(
        self,
        gantt_data: Dict[str, Any],
        ax,
        fig,
        save_path: str = None
    ) -> str:
        """生成资源利用率甘特图"""
        try:
            tasks = gantt_data.get('tasks', [])
            satellites = gantt_data.get('satellites', [])
            
            # 创建子图布局
            fig.clear()
            axes = fig.subplots(3, 1, figsize=(16, 12))
            
            resource_types = ['power', 'storage', 'communication']
            resource_names = ['功率利用率 (%)', '存储利用率 (%)', '通信利用率 (%)']
            
            for idx, (resource_type, resource_name) in enumerate(zip(resource_types, resource_names)):
                ax = axes[idx]
                
                # 按卫星分组资源数据
                satellite_resources = {}
                for task in tasks:
                    satellite_id = task.get('assigned_satellite', 'Unknown')
                    if satellite_id not in satellite_resources:
                        satellite_resources[satellite_id] = []
                    
                    start_time = datetime.fromisoformat(task['start_time'])
                    duration_minutes = task.get('duration_minutes', 30)
                    end_time = start_time + timedelta(minutes=duration_minutes)
                    
                    resource_req = task.get('resource_requirements', {})
                    utilization = resource_req.get(resource_type, 0.5) * 100  # 转换为百分比
                    
                    satellite_resources[satellite_id].append({
                        'start': start_time,
                        'end': end_time,
                        'utilization': utilization
                    })
                
                # 绘制资源利用率条
                y_positions = {sat: i for i, sat in enumerate(satellites)}
                
                for satellite_id, resources in satellite_resources.items():
                    y_pos = y_positions.get(satellite_id, 0)
                    
                    for resource in resources:
                        # 根据利用率选择颜色
                        if resource['utilization'] > 80:
                            color = '#FF4444'  # 高利用率 - 红色
                        elif resource['utilization'] > 60:
                            color = '#FFAA00'  # 中等利用率 - 橙色
                        else:
                            color = '#44AA44'  # 低利用率 - 绿色
                        
                        duration_hours = (resource['end'] - resource['start']).total_seconds() / 3600
                        
                        rect = patches.Rectangle(
                            (mdates.date2num(resource['start']), y_pos - 0.4),
                            duration_hours / 24,  # 转换为天数单位
                            0.8,
                            facecolor=color,
                            edgecolor='black',
                            linewidth=0.5,
                            alpha=0.7
                        )
                        ax.add_patch(rect)
                        
                        # 添加利用率标签
                        center_time = resource['start'] + timedelta(
                            seconds=(resource['end'] - resource['start']).total_seconds()/2
                        )
                        ax.text(
                            mdates.date2num(center_time),
                            y_pos,
                            f"{resource['utilization']:.0f}%",
                            ha='center',
                            va='center',
                            fontsize=8,
                            fontweight='bold',
                            color='white'
                        )
                
                # 设置轴标签
                ax.set_yticks(list(y_positions.values()))
                ax.set_yticklabels(list(y_positions.keys()))
                ax.set_ylabel('卫星', fontsize=10)
                ax.set_title(resource_name, fontsize=12, fontweight='bold')
                
                # 设置时间轴
                ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
                
                # 添加网格
                ax.grid(True, alpha=0.3, axis='x')
            
            # 设置总标题
            mission_id = gantt_data.get('mission_id', 'Unknown')
            fig.suptitle(
                f'现实预警星座资源利用率甘特图\n任务ID: {mission_id}',
                fontsize=16,
                fontweight='bold'
            )
            
            # 添加图例
            legend_elements = [
                patches.Patch(facecolor='#FF4444', alpha=0.7, label='高利用率 (>80%)'),
                patches.Patch(facecolor='#FFAA00', alpha=0.7, label='中等利用率 (60-80%)'),
                patches.Patch(facecolor='#44AA44', alpha=0.7, label='低利用率 (<60%)')
            ]
            
            axes[0].legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))
            
            # 调整布局
            plt.tight_layout()
            
            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['matplotlib']}/resource_utilization_{timestamp}.png"
            
            base_path = save_path.rsplit('.', 1)[0]
            
            plt.savefig(f"{base_path}.png", dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.savefig(f"{base_path}.svg", format='svg', bbox_inches='tight')
            plt.savefig(f"{base_path}.pdf", format='pdf', bbox_inches='tight')
            
            plt.close(fig)
            
            logger.info(f"✅ matplotlib资源利用率甘特图已保存: {base_path}")
            return f"{base_path}.png"
            
        except Exception as e:
            logger.error(f"❌ 生成matplotlib资源利用率甘特图失败: {e}")
            raise

    def _generate_matplotlib_timeline_overview(
        self,
        gantt_data: Dict[str, Any],
        ax,
        fig,
        save_path: str = None
    ) -> str:
        """生成时间线概览甘特图"""
        try:
            tasks = gantt_data.get('tasks', [])
            missiles = gantt_data.get('missiles', [])

            if not tasks or not missiles:
                raise ValueError("缺少任务或导弹数据")

            # 创建导弹时间线视图
            missile_positions = {missile: i for i, missile in enumerate(missiles)}

            # 获取所有卫星用于颜色分配
            satellites = list(set(task.get('assigned_satellite', 'Unknown') for task in tasks))
            satellite_colors = {sat: sns.color_palette("husl", len(satellites))[i]
                              for i, sat in enumerate(satellites)}

            # 绘制每个导弹的观测时间线
            for task in tasks:
                missile_id = task.get('target_missile', 'Unknown')
                if missile_id in missile_positions:
                    y_pos = missile_positions[missile_id]

                    start_time = datetime.fromisoformat(task['start_time'])
                    duration_hours = task.get('duration_minutes', 30) / 60.0

                    # 根据卫星选择颜色
                    satellite_id = task.get('assigned_satellite', 'Unknown')
                    color = satellite_colors.get(satellite_id, '#808080')

                    # 绘制观测时间段
                    rect = patches.Rectangle(
                        (mdates.date2num(start_time), y_pos - 0.3),
                        duration_hours / 24,
                        0.6,
                        facecolor=color,
                        edgecolor='black',
                        linewidth=1,
                        alpha=0.7
                    )
                    ax.add_patch(rect)

                    # 添加卫星标签
                    ax.text(
                        mdates.date2num(start_time + timedelta(minutes=task.get('duration_minutes', 30)/2)),
                        y_pos,
                        satellite_id.split('_')[-1] if '_' in satellite_id else satellite_id[-1:],
                        ha='center',
                        va='center',
                        fontsize=8,
                        fontweight='bold',
                        color='white'
                    )

            # 设置坐标轴
            ax.set_yticks(list(missile_positions.values()))
            ax.set_yticklabels(list(missile_positions.keys()))
            ax.set_ylabel('目标导弹', fontsize=12, fontweight='bold')

            # 设置时间轴
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
            ax.set_xlabel('时间', fontsize=12, fontweight='bold')

            # 设置标题
            mission_id = gantt_data.get('mission_id', 'Unknown')
            ax.set_title(
                f'导弹观测时间线概览\n任务ID: {mission_id}',
                fontsize=16,
                fontweight='bold',
                pad=20
            )

            # 添加网格
            ax.grid(True, alpha=0.3, axis='x')

            # 添加图例（显示卫星）
            legend_elements = [patches.Patch(facecolor=color, label=sat)
                             for sat, color in satellite_colors.items()]
            ax.legend(handles=legend_elements, loc='upper right', bbox_to_anchor=(1.15, 1))

            # 调整布局
            plt.tight_layout()

            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['matplotlib']}/timeline_overview_{timestamp}.png"

            base_path = save_path.rsplit('.', 1)[0]

            plt.savefig(f"{base_path}.png", dpi=300, bbox_inches='tight',
                       facecolor='white', edgecolor='none')
            plt.savefig(f"{base_path}.svg", format='svg', bbox_inches='tight')
            plt.savefig(f"{base_path}.pdf", format='pdf', bbox_inches='tight')

            plt.close(fig)

            logger.info(f"✅ matplotlib时间线概览甘特图已保存: {base_path}")
            return f"{base_path}.png"

        except Exception as e:
            logger.error(f"❌ 生成matplotlib时间线概览甘特图失败: {e}")
            raise

    def generate_plotly_gantt(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None,
        chart_type: str = "interactive_timeline"
    ) -> str:
        """使用Plotly生成交互式甘特图"""
        try:
            logger.info(f"🎨 使用Plotly生成{chart_type}甘特图...")

            if chart_type == "interactive_timeline":
                return self._generate_plotly_interactive_timeline(gantt_data, save_path)
            elif chart_type == "resource_heatmap":
                return self._generate_plotly_resource_heatmap(gantt_data, save_path)
            elif chart_type == "3d_gantt":
                return self._generate_plotly_3d_gantt(gantt_data, save_path)
            else:
                raise ValueError(f"不支持的Plotly图表类型: {chart_type}")

        except Exception as e:
            logger.error(f"❌ Plotly甘特图生成失败: {e}")
            raise

    def _generate_plotly_interactive_timeline(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None
    ) -> str:
        """生成交互式时间线甘特图"""
        try:
            tasks = gantt_data.get('tasks', [])

            # 准备数据
            df_data = []
            for task in tasks:
                start_time = datetime.fromisoformat(task['start_time'])
                duration_minutes = task.get('duration_minutes', 30)
                end_time = start_time + timedelta(minutes=duration_minutes)

                df_data.append({
                    'Task': task.get('task_name', 'Unknown Task'),
                    'Start': start_time,
                    'Finish': end_time,
                    'Resource': task.get('assigned_satellite', 'Unknown'),
                    'Threat_Level': task.get('threat_level', 3),
                    'Target': task.get('target_missile', 'Unknown'),
                    'Status': task.get('status', 'planned'),
                    'Duration': duration_minutes
                })

            df = pd.DataFrame(df_data)

            # 创建甘特图
            fig = px.timeline(
                df,
                x_start="Start",
                x_end="Finish",
                y="Resource",
                color="Threat_Level",
                hover_data=["Target", "Status", "Duration"],
                title=f"交互式任务时间线甘特图 - {gantt_data.get('mission_id', 'Unknown')}",
                color_continuous_scale="RdYlBu_r",
                range_color=[1, 5]
            )

            # 更新布局
            fig.update_layout(
                title_font_size=16,
                xaxis_title="时间",
                yaxis_title="卫星智能体",
                height=600,
                showlegend=True,
                hovermode='closest'
            )

            # 更新颜色条
            fig.update_coloraxes(
                colorbar_title="威胁等级",
                colorbar_tickvals=[1, 2, 3, 4, 5],
                colorbar_ticktext=["低", "较低", "中等", "高", "极高"]
            )

            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['plotly']}/interactive_timeline_{timestamp}.html"

            base_path = save_path.rsplit('.', 1)[0]

            # 保存为HTML（交互式）
            fig.write_html(f"{base_path}.html")

            # 保存为PNG（静态）
            fig.write_image(f"{base_path}.png", width=1600, height=800, scale=2)

            # 保存为JSON（数据）
            fig.write_json(f"{base_path}.json")

            logger.info(f"✅ Plotly交互式甘特图已保存: {base_path}")
            return f"{base_path}.html"

        except Exception as e:
            logger.error(f"❌ 生成Plotly交互式甘特图失败: {e}")
            raise

    def _generate_plotly_resource_heatmap(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None
    ) -> str:
        """生成资源利用率热力图"""
        try:
            tasks = gantt_data.get('tasks', [])
            satellites = gantt_data.get('satellites', [])

            # 创建时间网格
            if not tasks:
                raise ValueError("没有任务数据")

            start_times = [datetime.fromisoformat(task['start_time']) for task in tasks]
            min_time = min(start_times)
            max_time = max(start_times) + timedelta(hours=2)

            # 创建15分钟间隔的时间网格
            time_grid = []
            current_time = min_time
            while current_time <= max_time:
                time_grid.append(current_time)
                current_time += timedelta(minutes=15)

            # 创建资源利用率矩阵
            resource_matrix = np.zeros((len(satellites), len(time_grid)))

            for i, satellite in enumerate(satellites):
                for j, time_point in enumerate(time_grid):
                    # 计算该时间点该卫星的资源利用率
                    total_utilization = 0
                    active_tasks = 0

                    for task in tasks:
                        if task.get('assigned_satellite') == satellite:
                            task_start = datetime.fromisoformat(task['start_time'])
                            task_end = task_start + timedelta(minutes=task.get('duration_minutes', 30))

                            if task_start <= time_point <= task_end:
                                resource_req = task.get('resource_requirements', {})
                                avg_utilization = np.mean(list(resource_req.values()))
                                total_utilization += avg_utilization
                                active_tasks += 1

                    resource_matrix[i, j] = total_utilization

            # 创建热力图
            fig = go.Figure(data=go.Heatmap(
                z=resource_matrix,
                x=[t.strftime('%H:%M') for t in time_grid],
                y=satellites,
                colorscale='RdYlGn_r',
                hoverongaps=False,
                hovertemplate='卫星: %{y}<br>时间: %{x}<br>资源利用率: %{z:.2f}<extra></extra>'
            ))

            fig.update_layout(
                title=f"资源利用率热力图 - {gantt_data.get('mission_id', 'Unknown')}",
                xaxis_title="时间",
                yaxis_title="卫星",
                height=600
            )

            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['plotly']}/resource_heatmap_{timestamp}.html"

            base_path = save_path.rsplit('.', 1)[0]

            fig.write_html(f"{base_path}.html")
            fig.write_image(f"{base_path}.png", width=1600, height=800, scale=2)
            fig.write_json(f"{base_path}.json")

            logger.info(f"✅ Plotly资源热力图已保存: {base_path}")
            return f"{base_path}.html"

        except Exception as e:
            logger.error(f"❌ 生成Plotly资源热力图失败: {e}")
            raise

    def _generate_plotly_3d_gantt(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None
    ) -> str:
        """生成3D甘特图"""
        try:
            tasks = gantt_data.get('tasks', [])
            satellites = gantt_data.get('satellites', [])
            missiles = gantt_data.get('missiles', [])

            if not tasks:
                raise ValueError("没有任务数据")

            # 准备3D数据
            x_data = []  # 时间
            y_data = []  # 卫星
            z_data = []  # 导弹
            colors = []  # 威胁等级
            sizes = []   # 任务持续时间
            hover_text = []

            for task in tasks:
                start_time = datetime.fromisoformat(task['start_time'])
                satellite_id = task.get('assigned_satellite', 'Unknown')
                missile_id = task.get('target_missile', 'Unknown')
                threat_level = task.get('threat_level', 3)
                duration = task.get('duration_minutes', 30)

                # 时间轴（小时）
                time_hours = start_time.hour + start_time.minute / 60.0

                # 卫星轴（索引）
                sat_index = satellites.index(satellite_id) if satellite_id in satellites else 0

                # 导弹轴（索引）
                missile_index = missiles.index(missile_id) if missile_id in missiles else 0

                x_data.append(time_hours)
                y_data.append(sat_index)
                z_data.append(missile_index)
                colors.append(threat_level)
                sizes.append(duration)

                hover_text.append(
                    f"任务: {task.get('task_name', 'Unknown')}<br>"
                    f"卫星: {satellite_id}<br>"
                    f"导弹: {missile_id}<br>"
                    f"威胁等级: {threat_level}<br>"
                    f"持续时间: {duration}分钟<br>"
                    f"开始时间: {start_time.strftime('%H:%M')}"
                )

            # 创建3D散点图
            fig = go.Figure(data=go.Scatter3d(
                x=x_data,
                y=y_data,
                z=z_data,
                mode='markers',
                marker=dict(
                    size=[s/3 for s in sizes],  # 缩放尺寸
                    color=colors,
                    colorscale='RdYlBu_r',
                    colorbar=dict(
                        title="威胁等级",
                        tickvals=[1, 2, 3, 4, 5],
                        ticktext=["低", "较低", "中等", "高", "极高"]
                    ),
                    opacity=0.8,
                    line=dict(width=2, color='black')
                ),
                text=hover_text,
                hovertemplate='%{text}<extra></extra>'
            ))

            # 更新布局
            fig.update_layout(
                title=f"3D任务甘特图 - {gantt_data.get('mission_id', 'Unknown')}",
                scene=dict(
                    xaxis_title="时间 (小时)",
                    yaxis_title="卫星",
                    zaxis_title="导弹目标",
                    xaxis=dict(tickmode='linear', tick0=0, dtick=1),
                    yaxis=dict(
                        tickmode='array',
                        tickvals=list(range(len(satellites))),
                        ticktext=satellites
                    ),
                    zaxis=dict(
                        tickmode='array',
                        tickvals=list(range(len(missiles))),
                        ticktext=missiles
                    )
                ),
                height=800,
                margin=dict(l=0, r=0, b=0, t=50)
            )

            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['plotly']}/3d_gantt_{timestamp}.html"

            base_path = save_path.rsplit('.', 1)[0]

            fig.write_html(f"{base_path}.html")
            fig.write_image(f"{base_path}.png", width=1600, height=1200, scale=2)
            fig.write_json(f"{base_path}.json")

            logger.info(f"✅ Plotly 3D甘特图已保存: {base_path}")
            return f"{base_path}.html"

        except Exception as e:
            logger.error(f"❌ 生成Plotly 3D甘特图失败: {e}")
            raise

    def generate_seaborn_gantt(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None,
        chart_type: str = "statistical_analysis"
    ) -> str:
        """使用Seaborn生成统计分析甘特图"""
        try:
            logger.info(f"🎨 使用Seaborn生成{chart_type}甘特图...")

            if chart_type == "statistical_analysis":
                return self._generate_seaborn_statistical_analysis(gantt_data, save_path)
            elif chart_type == "correlation_matrix":
                return self._generate_seaborn_correlation_matrix(gantt_data, save_path)
            else:
                raise ValueError(f"不支持的Seaborn图表类型: {chart_type}")

        except Exception as e:
            logger.error(f"❌ Seaborn甘特图生成失败: {e}")
            raise

    def _generate_seaborn_statistical_analysis(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None
    ) -> str:
        """生成统计分析图表"""
        try:
            tasks = gantt_data.get('tasks', [])

            # 准备数据
            df_data = []
            for task in tasks:
                resource_req = task.get('resource_requirements', {})
                df_data.append({
                    'satellite': task.get('assigned_satellite', 'Unknown'),
                    'threat_level': task.get('threat_level', 3),
                    'duration': task.get('duration_minutes', 30),
                    'power': resource_req.get('power', 0.5),
                    'storage': resource_req.get('storage', 0.5),
                    'communication': resource_req.get('communication', 0.5),
                    'missile_type': task.get('missile_type', 'Unknown')
                })

            df = pd.DataFrame(df_data)

            # 创建多子图
            fig, axes = plt.subplots(2, 2, figsize=(16, 12))

            # 1. 威胁等级分布
            sns.countplot(data=df, x='threat_level', ax=axes[0,0], palette='RdYlBu_r')
            axes[0,0].set_title('威胁等级分布', fontsize=14, fontweight='bold')
            axes[0,0].set_xlabel('威胁等级')
            axes[0,0].set_ylabel('任务数量')

            # 2. 卫星任务负载
            sns.countplot(data=df, x='satellite', ax=axes[0,1], palette='Set2')
            axes[0,1].set_title('卫星任务负载分布', fontsize=14, fontweight='bold')
            axes[0,1].set_xlabel('卫星')
            axes[0,1].set_ylabel('任务数量')
            axes[0,1].tick_params(axis='x', rotation=45)

            # 3. 资源利用率箱线图
            resource_data = df[['power', 'storage', 'communication']].melt(
                var_name='resource_type', value_name='utilization'
            )
            sns.boxplot(data=resource_data, x='resource_type', y='utilization', ax=axes[1,0])
            axes[1,0].set_title('资源利用率分布', fontsize=14, fontweight='bold')
            axes[1,0].set_xlabel('资源类型')
            axes[1,0].set_ylabel('利用率')

            # 4. 威胁等级与任务持续时间关系
            sns.scatterplot(data=df, x='threat_level', y='duration',
                           hue='satellite', size='power', ax=axes[1,1])
            axes[1,1].set_title('威胁等级与任务持续时间关系', fontsize=14, fontweight='bold')
            axes[1,1].set_xlabel('威胁等级')
            axes[1,1].set_ylabel('任务持续时间 (分钟)')

            # 设置总标题
            mission_id = gantt_data.get('mission_id', 'Unknown')
            fig.suptitle(f'任务统计分析 - {mission_id}', fontsize=16, fontweight='bold')

            plt.tight_layout()

            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['seaborn']}/statistical_analysis_{timestamp}.png"

            base_path = save_path.rsplit('.', 1)[0]

            plt.savefig(f"{base_path}.png", dpi=300, bbox_inches='tight')
            plt.savefig(f"{base_path}.svg", format='svg', bbox_inches='tight')
            plt.savefig(f"{base_path}.pdf", format='pdf', bbox_inches='tight')

            plt.close(fig)

            logger.info(f"✅ Seaborn统计分析图已保存: {base_path}")
            return f"{base_path}.png"

        except Exception as e:
            logger.error(f"❌ 生成Seaborn统计分析图失败: {e}")
            raise

    def _generate_seaborn_correlation_matrix(
        self,
        gantt_data: Dict[str, Any],
        save_path: str = None
    ) -> str:
        """生成相关性矩阵图"""
        try:
            tasks = gantt_data.get('tasks', [])

            if not tasks:
                raise ValueError("没有任务数据")

            # 准备数据
            df_data = []
            for task in tasks:
                resource_req = task.get('resource_requirements', {})
                df_data.append({
                    'threat_level': task.get('threat_level', 3),
                    'duration': task.get('duration_minutes', 30),
                    'power': resource_req.get('power', 0.5),
                    'storage': resource_req.get('storage', 0.5),
                    'communication': resource_req.get('communication', 0.5),
                    'satellite_index': hash(task.get('assigned_satellite', '')) % 100,
                    'missile_index': hash(task.get('target_missile', '')) % 100
                })

            df = pd.DataFrame(df_data)

            # 计算相关性矩阵
            correlation_matrix = df.corr()

            # 创建热力图
            fig, ax = plt.subplots(figsize=(10, 8))

            # 生成相关性热力图
            mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
            sns.heatmap(
                correlation_matrix,
                mask=mask,
                annot=True,
                cmap='RdBu_r',
                center=0,
                square=True,
                fmt='.2f',
                cbar_kws={"shrink": .8},
                ax=ax
            )

            # 设置标题
            mission_id = gantt_data.get('mission_id', 'Unknown')
            ax.set_title(f'任务参数相关性矩阵 - {mission_id}', fontsize=16, fontweight='bold', pad=20)

            # 设置标签
            labels = ['威胁等级', '持续时间', '功率需求', '存储需求', '通信需求', '卫星索引', '导弹索引']
            ax.set_xticklabels(labels, rotation=45, ha='right')
            ax.set_yticklabels(labels, rotation=0)

            plt.tight_layout()

            # 保存图表
            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = f"{self.output_dirs['seaborn']}/correlation_matrix_{timestamp}.png"

            base_path = save_path.rsplit('.', 1)[0]

            plt.savefig(f"{base_path}.png", dpi=300, bbox_inches='tight')
            plt.savefig(f"{base_path}.svg", format='svg', bbox_inches='tight')
            plt.savefig(f"{base_path}.pdf", format='pdf', bbox_inches='tight')

            plt.close(fig)

            logger.info(f"✅ Seaborn相关性矩阵图已保存: {base_path}")
            return f"{base_path}.png"

        except Exception as e:
            logger.error(f"❌ 生成Seaborn相关性矩阵图失败: {e}")
            raise

    def generate_comprehensive_gantt_suite(
        self,
        gantt_data: Dict[str, Any],
        output_dir: str = None
    ) -> Dict[str, str]:
        """生成完整的甘特图套件"""
        try:
            logger.info("🎨 开始生成完整甘特图套件...")

            if output_dir is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = f"{self.output_dirs['combined']}/suite_{timestamp}"

            os.makedirs(output_dir, exist_ok=True)

            generated_charts = {}

            # 1. Matplotlib甘特图
            try:
                matplotlib_task = self.generate_matplotlib_gantt(
                    gantt_data, f"{output_dir}/matplotlib_task_allocation.png", "task_allocation"
                )
                generated_charts['matplotlib_task_allocation'] = matplotlib_task

                matplotlib_resource = self.generate_matplotlib_gantt(
                    gantt_data, f"{output_dir}/matplotlib_resource_utilization.png", "resource_utilization"
                )
                generated_charts['matplotlib_resource_utilization'] = matplotlib_resource

                matplotlib_timeline = self.generate_matplotlib_gantt(
                    gantt_data, f"{output_dir}/matplotlib_timeline_overview.png", "timeline_overview"
                )
                generated_charts['matplotlib_timeline_overview'] = matplotlib_timeline

            except Exception as e:
                logger.warning(f"⚠️ Matplotlib甘特图生成失败: {e}")

            # 2. Plotly交互式甘特图
            try:
                plotly_interactive = self.generate_plotly_gantt(
                    gantt_data, f"{output_dir}/plotly_interactive_timeline.html", "interactive_timeline"
                )
                generated_charts['plotly_interactive_timeline'] = plotly_interactive

                plotly_heatmap = self.generate_plotly_gantt(
                    gantt_data, f"{output_dir}/plotly_resource_heatmap.html", "resource_heatmap"
                )
                generated_charts['plotly_resource_heatmap'] = plotly_heatmap

                plotly_3d = self.generate_plotly_gantt(
                    gantt_data, f"{output_dir}/plotly_3d_gantt.html", "3d_gantt"
                )
                generated_charts['plotly_3d_gantt'] = plotly_3d

            except Exception as e:
                logger.warning(f"⚠️ Plotly甘特图生成失败: {e}")

            # 3. Seaborn统计分析图
            try:
                seaborn_stats = self.generate_seaborn_gantt(
                    gantt_data, f"{output_dir}/seaborn_statistical_analysis.png", "statistical_analysis"
                )
                generated_charts['seaborn_statistical_analysis'] = seaborn_stats

                seaborn_correlation = self.generate_seaborn_gantt(
                    gantt_data, f"{output_dir}/seaborn_correlation_matrix.png", "correlation_matrix"
                )
                generated_charts['seaborn_correlation_matrix'] = seaborn_correlation

            except Exception as e:
                logger.warning(f"⚠️ Seaborn甘特图生成失败: {e}")

            # 4. 生成综合报告
            report_data = self._generate_comprehensive_report(gantt_data, generated_charts)
            report_path = f"{output_dir}/comprehensive_report.json"
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
            generated_charts['comprehensive_report'] = report_path

            # 5. 生成HTML索引页面
            index_path = self._generate_html_index(gantt_data, generated_charts, output_dir)
            generated_charts['html_index'] = index_path

            logger.info(f"✅ 完整甘特图套件生成完成: {len(generated_charts)} 个文件")
            return generated_charts

        except Exception as e:
            logger.error(f"❌ 生成完整甘特图套件失败: {e}")
            raise

    def _generate_comprehensive_report(
        self,
        gantt_data: Dict[str, Any],
        generated_charts: Dict[str, str]
    ) -> Dict[str, Any]:
        """生成综合报告"""
        try:
            tasks = gantt_data.get('tasks', [])
            satellites = gantt_data.get('satellites', [])

            # 计算统计指标
            threat_distribution = {}
            satellite_workload = {}
            resource_utilization = {'power': [], 'storage': [], 'communication': []}

            for task in tasks:
                # 威胁等级分布
                threat_level = task.get('threat_level', 3)
                threat_distribution[threat_level] = threat_distribution.get(threat_level, 0) + 1

                # 卫星工作负载
                satellite = task.get('assigned_satellite', 'Unknown')
                satellite_workload[satellite] = satellite_workload.get(satellite, 0) + 1

                # 资源利用率
                resource_req = task.get('resource_requirements', {})
                for resource_type in resource_utilization:
                    resource_utilization[resource_type].append(resource_req.get(resource_type, 0.5))

            # 计算平均资源利用率
            avg_resource_utilization = {}
            for resource_type, values in resource_utilization.items():
                if values:
                    avg_resource_utilization[resource_type] = {
                        'mean': np.mean(values),
                        'std': np.std(values),
                        'min': np.min(values),
                        'max': np.max(values)
                    }

            report = {
                'mission_info': {
                    'mission_id': gantt_data.get('mission_id', 'Unknown'),
                    'generation_time': datetime.now().isoformat(),
                    'total_tasks': len(tasks),
                    'total_satellites': len(satellites),
                    'total_missiles': len(gantt_data.get('missiles', []))
                },
                'statistics': {
                    'threat_distribution': threat_distribution,
                    'satellite_workload': satellite_workload,
                    'avg_resource_utilization': avg_resource_utilization,
                    'workload_balance': {
                        'max_tasks_per_satellite': max(satellite_workload.values()) if satellite_workload else 0,
                        'min_tasks_per_satellite': min(satellite_workload.values()) if satellite_workload else 0,
                        'avg_tasks_per_satellite': np.mean(list(satellite_workload.values())) if satellite_workload else 0
                    }
                },
                'generated_charts': generated_charts,
                'recommendations': self._generate_recommendations(gantt_data, threat_distribution, satellite_workload)
            }

            return report

        except Exception as e:
            logger.error(f"❌ 生成综合报告失败: {e}")
            return {}

    def _generate_recommendations(
        self,
        gantt_data: Dict[str, Any],
        threat_distribution: Dict[int, int],
        satellite_workload: Dict[str, int]
    ) -> List[str]:
        """生成优化建议"""
        recommendations = []

        try:
            # 威胁等级分析
            high_threat_count = threat_distribution.get(5, 0) + threat_distribution.get(4, 0)
            total_tasks = sum(threat_distribution.values())

            if high_threat_count / total_tasks > 0.6:
                recommendations.append("高威胁目标占比较高，建议增加冗余观测卫星")

            # 工作负载平衡分析
            if satellite_workload:
                max_workload = max(satellite_workload.values())
                min_workload = min(satellite_workload.values())

                if max_workload - min_workload > 2:
                    recommendations.append("卫星工作负载不均衡，建议重新分配任务")

            # 资源利用率分析
            tasks = gantt_data.get('tasks', [])
            high_power_tasks = sum(1 for task in tasks
                                 if task.get('resource_requirements', {}).get('power', 0) > 0.8)

            if high_power_tasks / len(tasks) > 0.5:
                recommendations.append("功率需求较高，建议优化观测策略或增加充电时间")

            if not recommendations:
                recommendations.append("当前任务分配较为合理，无明显优化建议")

            return recommendations

        except Exception as e:
            logger.error(f"❌ 生成优化建议失败: {e}")
            return ["无法生成优化建议"]

    def _generate_html_index(
        self,
        gantt_data: Dict[str, Any],
        generated_charts: Dict[str, str],
        output_dir: str
    ) -> str:
        """生成HTML索引页面"""
        try:
            mission_id = gantt_data.get('mission_id', 'Unknown')
            generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>甘特图分析报告 - {mission_id}</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
        }}
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .info-card {{
            background-color: #ecf0f1;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .chart-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .chart-card {{
            background-color: #ffffff;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
        }}
        .chart-card img {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
        }}
        .chart-link {{
            display: inline-block;
            margin: 10px 5px;
            padding: 8px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 14px;
        }}
        .chart-link:hover {{
            background-color: #2980b9;
        }}
        .interactive-link {{
            background-color: #e74c3c;
        }}
        .interactive-link:hover {{
            background-color: #c0392b;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>现实预警星座甘特图分析报告</h1>

        <div class="info-grid">
            <div class="info-card">
                <h3>任务信息</h3>
                <p><strong>任务ID:</strong> {mission_id}</p>
                <p><strong>生成时间:</strong> {generation_time}</p>
            </div>
            <div class="info-card">
                <h3>统计数据</h3>
                <p><strong>总任务数:</strong> {len(gantt_data.get('tasks', []))}</p>
                <p><strong>参与卫星:</strong> {len(gantt_data.get('satellites', []))}</p>
                <p><strong>目标导弹:</strong> {len(gantt_data.get('missiles', []))}</p>
            </div>
        </div>

        <h2>📊 甘特图集合</h2>
        <div class="chart-grid">
"""

            # 添加图表卡片
            chart_descriptions = {
                'matplotlib_task_allocation': '任务分配甘特图 (Matplotlib)',
                'matplotlib_resource_utilization': '资源利用率甘特图 (Matplotlib)',
                'matplotlib_timeline_overview': '时间线概览图 (Matplotlib)',
                'plotly_interactive_timeline': '交互式时间线 (Plotly)',
                'plotly_resource_heatmap': '资源热力图 (Plotly)',
                'plotly_3d_gantt': '3D甘特图 (Plotly)',
                'seaborn_statistical_analysis': '统计分析图 (Seaborn)',
                'seaborn_correlation_matrix': '相关性矩阵图 (Seaborn)'
            }

            for chart_type, chart_path in generated_charts.items():
                if chart_type in chart_descriptions:
                    chart_name = chart_descriptions[chart_type]
                    file_name = os.path.basename(chart_path)

                    html_content += f"""
            <div class="chart-card">
                <h3>{chart_name}</h3>
                <p>文件: {file_name}</p>
"""

                    # 如果是图片文件，显示预览
                    if chart_path.endswith(('.png', '.jpg', '.jpeg')):
                        html_content += f'<img src="{file_name}" alt="{chart_name}">'

                    # 添加下载链接
                    if chart_path.endswith('.html'):
                        html_content += f'<br><a href="{file_name}" class="chart-link interactive-link" target="_blank">查看交互式图表</a>'
                    else:
                        html_content += f'<br><a href="{file_name}" class="chart-link" download>下载图表</a>'

                    html_content += '</div>'

            html_content += """
        </div>

        <h2>📋 文件列表</h2>
        <ul>
"""

            # 添加文件列表
            for chart_type, chart_path in generated_charts.items():
                file_name = os.path.basename(chart_path)
                html_content += f'<li><strong>{chart_type}:</strong> <a href="{file_name}">{file_name}</a></li>'

            html_content += """
        </ul>

        <div style="text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd;">
            <p style="color: #7f8c8d;">现实预警星座甘特图分析系统 © 2025</p>
        </div>
    </div>
</body>
</html>
"""

            index_path = f"{output_dir}/index.html"
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"✅ HTML索引页面已生成: {index_path}")
            return index_path

        except Exception as e:
            logger.error(f"❌ 生成HTML索引页面失败: {e}")
            return ""
