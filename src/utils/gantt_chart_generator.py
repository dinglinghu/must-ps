#!/usr/bin/env python3
"""
航天领域专业甘特图生成器
使用Plotly生成高质量的任务规划甘特图
"""

import json
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class AerospaceGanttGenerator:
    """航天领域专业甘特图生成器"""
    
    # 航天任务专业配色方案
    AEROSPACE_COLORS = {
        # 主要任务类型
        "observation": "#2E8B57",        # 海绿色 - 观测任务
        "communication": "#4169E1",      # 皇家蓝 - 通信任务
        "data_transmission": "#FF6347",  # 番茄红 - 数据传输
        "maintenance": "#9370DB",        # 中紫色 - 维护任务
        "maneuver": "#FF8C00",          # 深橙色 - 机动任务
        "standby": "#708090",           # 石板灰 - 待机状态
        
        # 元任务类型
        "meta_task": "#1f77b4",         # 蓝色 - 元任务
        "flight_phase": "#ff7f0e",      # 橙色 - 飞行阶段
        "observation_window": "#2ca02c", # 绿色 - 观测窗口
        
        # 优先级颜色
        "priority_high": "#DC143C",      # 深红色 - 高优先级
        "priority_medium": "#FFD700",    # 金色 - 中优先级
        "priority_low": "#32CD32",       # 酸橙绿 - 低优先级
        
        # 状态颜色
        "completed": "#228B22",          # 森林绿 - 已完成
        "in_progress": "#FF8C00",        # 深橙色 - 进行中
        "planned": "#4682B4",            # 钢蓝色 - 已规划
        "cancelled": "#696969"           # 暗灰色 - 已取消
    }
    
    def __init__(self):
        """初始化甘特图生成器"""
        self.fig = None
        
    def create_meta_task_gantt(self, gantt_data: Dict[str, Any]) -> go.Figure:
        """
        创建天基预警元任务甘特图
        横轴：时间轴，纵轴：预警目标，长方形块：探测跟踪时间窗口

        Args:
            gantt_data: 甘特图数据

        Returns:
            Plotly图表对象
        """
        tasks = gantt_data.get("tasks", [])
        if not tasks:
            logger.warning("没有任务数据，无法生成甘特图")
            return None

        # 创建自定义甘特图
        fig = go.Figure()

        # 获取所有目标并排序
        targets = sorted(list(set(task["category"] for task in tasks)))
        target_positions = {target: i for i, target in enumerate(targets)}

        # 计算整体时间范围
        all_start_times = [pd.to_datetime(task["start"]) for task in tasks]
        all_end_times = [pd.to_datetime(task["end"]) for task in tasks]
        overall_start = min(all_start_times)
        overall_end = max(all_end_times)

        # 扩展时间范围以显示更多上下文（前后各加30分钟）
        from datetime import timedelta
        extended_start = overall_start - timedelta(minutes=30)
        extended_end = overall_end + timedelta(minutes=30)

        # 首先为每个目标添加灰色背景（非轨迹时间）
        for target in targets:
            y_pos = target_positions[target]

            # 添加整个扩展时间范围的灰色背景
            fig.add_trace(go.Scatter(
                x=[extended_start, extended_end, extended_end, extended_start, extended_start],
                y=[y_pos-0.4, y_pos-0.4, y_pos+0.4, y_pos+0.4, y_pos-0.4],
                fill="toself",
                fillcolor="#E8E8E8",  # 浅灰色背景
                line=dict(color="#CCCCCC", width=1),
                mode="lines",
                name="非轨迹时间" if y_pos == 0 else "",
                hovertemplate=f"<b>非轨迹时间</b><br>目标: {target}<br>状态: 无导弹轨迹数据<extra></extra>",
                showlegend=True if y_pos == 0 else False,
                legendgroup="background"
            ))

        # 然后为每个任务添加有色矩形块（导弹轨迹时间）
        for task in tasks:
            target = task["category"]
            y_pos = target_positions[target]

            # 计算时间
            start_time = pd.to_datetime(task["start"])
            end_time = pd.to_datetime(task["end"])
            duration_minutes = (end_time - start_time).total_seconds() / 60

            # 添加矩形块表示导弹轨迹时间窗口
            fig.add_trace(go.Scatter(
                x=[start_time, end_time, end_time, start_time, start_time],
                y=[y_pos-0.3, y_pos-0.3, y_pos+0.3, y_pos+0.3, y_pos-0.3],
                fill="toself",
                fillcolor=self.AEROSPACE_COLORS.get(task.get("type", "meta_task"), "#1f77b4"),
                line=dict(color="black", width=2),
                mode="lines",
                name=f"导弹中段飞行" if y_pos == 0 else "",
                hovertemplate=f"<b>导弹中段飞行</b><br>" +
                             f"目标: {target}<br>" +
                             f"飞行时长: {duration_minutes:.1f}分钟<br>" +
                             f"开始: {start_time.strftime('%H:%M:%S')}<br>" +
                             f"结束: {end_time.strftime('%H:%M:%S')}<br>" +
                             f"描述: {task.get('description', '')}<extra></extra>",
                showlegend=True if y_pos == 0 else False,
                legendgroup="trajectory"
            ))

            # 添加任务标签
            fig.add_annotation(
                x=start_time + (end_time - start_time) / 2,
                y=y_pos,
                text=f"Task{target_positions[target]+1}",
                showarrow=False,
                font=dict(color="white", size=10, family="Arial", weight="bold"),
                bgcolor="rgba(0,0,0,0.8)",
                bordercolor="white",
                borderwidth=1
            )

        # 设置布局
        fig.update_layout(
            title={
                'text': "天基预警元任务分解甘特图",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'family': 'Arial, sans-serif', 'color': '#2c3e50'}
            },
            xaxis=dict(
                title="时间轴 (st_m → end_t)",
                showgrid=True,
                gridwidth=1,
                gridcolor='#e0e0e0',
                tickformat='%H:%M:%S',
                title_font=dict(size=12, color='#2c3e50')
            ),
            yaxis=dict(
                title="预警目标",
                tickmode='array',
                tickvals=list(range(len(targets))),
                ticktext=[f"Target{i+1}" for i in range(len(targets))],
                showgrid=True,
                gridwidth=1,
                gridcolor='#e0e0e0',
                title_font=dict(size=12, color='#2c3e50')
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Arial, sans-serif", size=11),
            margin=dict(l=80, r=50, t=80, b=120),
            height=max(400, len(targets) * 80 + 200),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.1,
                xanchor="center",
                x=0.5,
                title="时间窗口类型"
            )
        )

        # 添加时间刻度线
        if tasks:
            start_time = min(pd.to_datetime(task["start"]) for task in tasks)
            end_time = max(pd.to_datetime(task["end"]) for task in tasks)

            # 添加时间序号标注
            time_range = end_time - start_time
            num_ticks = min(20, max(5, int(time_range.total_seconds() / 300)))  # 每5分钟一个刻度

            for i in range(num_ticks + 1):
                tick_time = start_time + (time_range * i / num_ticks)
                fig.add_vline(
                    x=tick_time,
                    line_dash="dot",
                    line_color="#cccccc",
                    line_width=1
                )

        # 添加专业注释
        fig.add_annotation(
            text="注：横轴为时间轴，纵轴为预警目标，蓝色块代表导弹中段飞行时间窗口，灰色区域为非轨迹时间",
            xref="paper", yref="paper",
            x=0.5, y=-0.2,
            showarrow=False,
            font=dict(size=10, color="#7f8c8d")
        )

        self.fig = fig
        return fig
    
    def create_planning_gantt(self, gantt_data: Dict[str, Any]) -> go.Figure:
        """
        创建协同调度方案甘特图
        横轴：时间轴，纵轴：预警目标，不同颜色块：不同预警卫星节点资源

        Args:
            gantt_data: 甘特图数据

        Returns:
            Plotly图表对象
        """
        tasks = gantt_data.get("tasks", [])
        if not tasks:
            logger.warning("没有任务数据，无法生成甘特图")
            return None

        # 创建自定义甘特图
        fig = go.Figure()

        # 按目标分组任务
        targets_tasks = {}
        for task in tasks:
            target_id = task.get("target_id", task["category"])
            if target_id not in targets_tasks:
                targets_tasks[target_id] = []
            targets_tasks[target_id].append(task)

        # 为每个目标分配Y轴位置
        targets = sorted(targets_tasks.keys())
        target_positions = {target: i for i, target in enumerate(targets)}

        # 卫星颜色映射
        satellite_colors = {
            "Satellite13": "#FF6B6B",  # 红色
            "Satellite32": "#4ECDC4",  # 青色
            "Satellite33": "#45B7D1",  # 蓝色
            "Satellite21": "#96CEB4",  # 绿色
            "Satellite11": "#FFEAA7",  # 黄色
            "Satellite22": "#DDA0DD",  # 紫色
            "Satellite31": "#F4A460",  # 橙色
            "Satellite12": "#98D8C8",  # 薄荷绿
            "Satellite23": "#F7DC6F"   # 金黄色
        }

        # 为每个目标的每个任务添加矩形块
        for target_id, target_tasks in targets_tasks.items():
            y_pos = target_positions[target_id]

            # 按卫星分组同一目标的任务
            satellite_tasks = {}
            for task in target_tasks:
                satellite = task["category"]
                if satellite not in satellite_tasks:
                    satellite_tasks[satellite] = []
                satellite_tasks[satellite].append(task)

            # 为每个卫星的任务创建子轨道
            sub_track = 0
            for satellite, sat_tasks in satellite_tasks.items():
                for task in sat_tasks:
                    start_time = pd.to_datetime(task["start"])
                    end_time = pd.to_datetime(task["end"])
                    duration_minutes = (end_time - start_time).total_seconds() / 60

                    # 计算子轨道位置
                    y_bottom = y_pos - 0.4 + sub_track * 0.2
                    y_top = y_pos - 0.2 + sub_track * 0.2

                    # 获取卫星颜色
                    color = satellite_colors.get(satellite, "#95A5A6")

                    # 添加矩形块
                    fig.add_trace(go.Scatter(
                        x=[start_time, end_time, end_time, start_time, start_time],
                        y=[y_bottom, y_bottom, y_top, y_top, y_bottom],
                        fill="toself",
                        fillcolor=color,
                        line=dict(color="black", width=1),
                        mode="lines",
                        name=f"{satellite}",
                        hovertemplate=f"<b>{satellite}</b><br>" +
                                     f"目标: {target_id}<br>" +
                                     f"探测时长: {duration_minutes:.1f}分钟<br>" +
                                     f"开始: {start_time.strftime('%H:%M:%S')}<br>" +
                                     f"结束: {end_time.strftime('%H:%M:%S')}<br>" +
                                     f"任务: {task.get('description', '')}<extra></extra>",
                        showlegend=True if sub_track == 0 else False
                    ))

                    # 添加卫星编号标签
                    satellite_num = satellite.replace("Satellite", "")
                    fig.add_annotation(
                        x=start_time + (end_time - start_time) / 2,
                        y=(y_bottom + y_top) / 2,
                        text=satellite_num,
                        showarrow=False,
                        font=dict(color="white", size=9, family="Arial", weight="bold"),
                        bgcolor="rgba(0,0,0,0.7)",
                        bordercolor="white",
                        borderwidth=1
                    )

                sub_track += 1

        # 设置布局
        fig.update_layout(
            title={
                'text': "协同调度方案甘特图",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'family': 'Arial, sans-serif', 'color': '#2c3e50'}
            },
            xaxis=dict(
                title="时间轴",
                showgrid=True,
                gridwidth=1,
                gridcolor='#e0e0e0',
                tickformat='%H:%M:%S',
                title_font=dict(size=12, color='#2c3e50')
            ),
            yaxis=dict(
                title="预警目标",
                tickmode='array',
                tickvals=list(range(len(targets))),
                ticktext=[f"目标{i+1}" for i in range(len(targets))],
                showgrid=True,
                gridwidth=1,
                gridcolor='#e0e0e0',
                title_font=dict(size=12, color='#2c3e50')
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Arial, sans-serif", size=11),
            margin=dict(l=80, r=50, t=80, b=100),
            height=max(400, len(targets) * 80 + 200),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.1,
                xanchor="center",
                x=0.5,
                title="预警卫星节点"
            )
        )

        # 添加时间序号标注
        if tasks:
            start_time = min(pd.to_datetime(task["start"]) for task in tasks)
            end_time = max(pd.to_datetime(task["end"]) for task in tasks)

            time_range = end_time - start_time
            num_ticks = min(20, max(5, int(time_range.total_seconds() / 300)))

            for i in range(num_ticks + 1):
                tick_time = start_time + (time_range * i / num_ticks)
                fig.add_vline(
                    x=tick_time,
                    line_dash="dot",
                    line_color="#cccccc",
                    line_width=1
                )

                # 添加序号标注
                fig.add_annotation(
                    x=tick_time,
                    y=-0.8,
                    text=str(i+1),
                    showarrow=False,
                    font=dict(size=8, color="#7f8c8d"),
                    bgcolor="white",
                    bordercolor="#cccccc",
                    borderwidth=1
                )

        # 添加专业注释
        fig.add_annotation(
            text="注：横轴为时间轴，纵轴为预警目标，不同颜色块代表不同预警卫星节点资源，编号对应卫星标识",
            xref="paper", yref="paper",
            x=0.5, y=-0.2,
            showarrow=False,
            font=dict(size=10, color="#7f8c8d")
        )

        self.fig = fig
        return fig

    def generate_gantt_chart(self, chart_type: str, gantt_data: Dict[str, Any]) -> go.Figure:
        """
        生成甘特图

        Args:
            chart_type: 图表类型 ('meta_task', 'planning', 'collaborative')
            gantt_data: 甘特图数据

        Returns:
            Plotly图表对象
        """
        if chart_type == "meta_task":
            return self.create_meta_task_gantt(gantt_data)
        elif chart_type == "planning":
            return self.create_planning_gantt(gantt_data)
        elif chart_type == "collaborative":
            return self.create_collaborative_gantt(gantt_data)
        else:
            raise ValueError(f"不支持的图表类型: {chart_type}")

    def create_collaborative_gantt(self, gantt_data: Dict[str, Any]) -> go.Figure:
        """
        创建多目标协同调度甘特图
        支持多个目标的协同调度展示

        Args:
            gantt_data: 甘特图数据

        Returns:
            Plotly图表对象
        """
        tasks = gantt_data.get("tasks", [])
        if not tasks:
            logger.warning("没有任务数据，无法生成甘特图")
            return None

        # 创建子图
        targets = sorted(list(set(task.get("target_id", task["category"]) for task in tasks)))
        num_targets = len(targets)

        fig = make_subplots(
            rows=num_targets,
            cols=1,
            subplot_titles=[f"目标{i+1}: {target}" for i, target in enumerate(targets)],
            shared_xaxes=True,
            vertical_spacing=0.05
        )

        # 卫星颜色映射
        satellite_colors = {
            "Satellite13": "#FF6B6B",  # 红色
            "Satellite32": "#4ECDC4",  # 青色
            "Satellite33": "#45B7D1",  # 蓝色
            "Satellite21": "#96CEB4",  # 绿色
            "Satellite11": "#FFEAA7",  # 黄色
            "Satellite22": "#DDA0DD",  # 紫色
            "Satellite31": "#F4A460",  # 橙色
            "Satellite12": "#98D8C8",  # 薄荷绿
            "Satellite23": "#F7DC6F"   # 金黄色
        }

        # 为每个目标创建甘特图
        for target_idx, target in enumerate(targets):
            target_tasks = [task for task in tasks if task.get("target_id", task["category"]) == target]

            for task in target_tasks:
                satellite = task["category"]
                start_time = pd.to_datetime(task["start"])
                end_time = pd.to_datetime(task["end"])
                duration_minutes = (end_time - start_time).total_seconds() / 60

                color = satellite_colors.get(satellite, "#95A5A6")

                # 添加甘特条
                fig.add_trace(
                    go.Scatter(
                        x=[start_time, end_time, end_time, start_time, start_time],
                        y=[0.2, 0.2, 0.8, 0.8, 0.2],
                        fill="toself",
                        fillcolor=color,
                        line=dict(color="black", width=1),
                        mode="lines",
                        name=satellite,
                        hovertemplate=f"<b>{satellite}</b><br>" +
                                     f"目标: {target}<br>" +
                                     f"探测时长: {duration_minutes:.1f}分钟<br>" +
                                     f"开始: {start_time.strftime('%H:%M:%S')}<br>" +
                                     f"结束: {end_time.strftime('%H:%M:%S')}<extra></extra>",
                        showlegend=target_idx == 0  # 只在第一个子图显示图例
                    ),
                    row=target_idx + 1,
                    col=1
                )

                # 添加卫星编号
                satellite_num = satellite.replace("Satellite", "")
                fig.add_annotation(
                    x=start_time + (end_time - start_time) / 2,
                    y=0.5,
                    text=satellite_num,
                    showarrow=False,
                    font=dict(color="white", size=10, family="Arial", weight="bold"),
                    bgcolor="rgba(0,0,0,0.7)",
                    bordercolor="white",
                    borderwidth=1,
                    row=target_idx + 1,
                    col=1
                )

        # 更新布局
        fig.update_layout(
            title={
                'text': "多目标协同调度甘特图",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 16, 'family': 'Arial, sans-serif', 'color': '#2c3e50'}
            },
            height=max(400, num_targets * 150 + 100),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.1,
                xanchor="center",
                x=0.5
            ),
            plot_bgcolor='white',
            paper_bgcolor='white'
        )

        # 更新x轴
        fig.update_xaxes(
            title_text="时间轴",
            showgrid=True,
            gridwidth=1,
            gridcolor='#e0e0e0',
            tickformat='%H:%M:%S',
            row=num_targets,
            col=1
        )

        # 更新y轴
        for i in range(num_targets):
            fig.update_yaxes(
                showticklabels=False,
                showgrid=False,
                range=[0, 1],
                row=i + 1,
                col=1
            )

        self.fig = fig
        return fig

    def save_chart(self, filepath: str, format: str = "html") -> str:
        """
        保存甘特图
        
        Args:
            filepath: 保存路径
            format: 保存格式 (html, png, pdf, svg)
            
        Returns:
            保存的文件路径
        """
        if self.fig is None:
            raise ValueError("没有可保存的图表，请先生成甘特图")
        
        if format.lower() == "html":
            self.fig.write_html(filepath)
        elif format.lower() == "png":
            self.fig.write_image(filepath, format="png", width=1200, height=800)
        elif format.lower() == "pdf":
            self.fig.write_image(filepath, format="pdf", width=1200, height=800)
        elif format.lower() == "svg":
            self.fig.write_image(filepath, format="svg", width=1200, height=800)
        else:
            raise ValueError(f"不支持的格式: {format}")
        
        logger.info(f"甘特图已保存到: {filepath}")
        return filepath
    
    def get_chart_html(self) -> str:
        """
        获取图表的HTML代码
        
        Returns:
            HTML代码字符串
        """
        if self.fig is None:
            raise ValueError("没有可用的图表，请先生成甘特图")
        
        return self.fig.to_html(include_plotlyjs=True, div_id="gantt-chart")
    
    def add_milestone(self, date: str, label: str, color: str = "#FF0000"):
        """
        添加里程碑标记
        
        Args:
            date: 里程碑日期
            label: 里程碑标签
            color: 标记颜色
        """
        if self.fig is None:
            raise ValueError("请先生成甘特图")
        
        self.fig.add_vline(
            x=pd.to_datetime(date),
            line_dash="dash",
            line_color=color,
            annotation_text=label,
            annotation_position="top"
        )
    
    def add_critical_path(self, tasks: List[str]):
        """
        高亮关键路径
        
        Args:
            tasks: 关键路径任务列表
        """
        if self.fig is None:
            raise ValueError("请先生成甘特图")
        
        # 这里可以添加关键路径高亮逻辑
        # 例如改变特定任务的颜色或添加边框
        pass


def create_aerospace_gantt_chart(gantt_data: Dict[str, Any], chart_type: str = "planning") -> go.Figure:
    """
    创建航天专业甘特图的便捷函数
    
    Args:
        gantt_data: 甘特图数据
        chart_type: 图表类型 ("meta_task" 或 "planning")
        
    Returns:
        Plotly图表对象
    """
    generator = AerospaceGanttGenerator()
    
    if chart_type == "meta_task":
        return generator.create_meta_task_gantt(gantt_data)
    elif chart_type == "planning":
        return generator.create_planning_gantt(gantt_data)
    else:
        raise ValueError(f"不支持的图表类型: {chart_type}")
