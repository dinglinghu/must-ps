"""
航天领域专业甘特图HTML生成器
使用Plotly生成交互式HTML甘特图
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd

from .realistic_constellation_gantt import ConstellationGanttData
from .gantt_save_config_manager import get_gantt_save_config_manager

logger = logging.getLogger(__name__)

class AerospaceGanttHTMLGenerator:
    """航天领域专业甘特图HTML生成器"""
    
    def __init__(self):
        self.config_manager = get_gantt_save_config_manager()
        
        # 航天专业颜色配置
        self.threat_colors = {
            5: '#DC2626',  # 红色 - 极高威胁
            4: '#EA580C',  # 橙红色 - 高威胁
            3: '#D97706',  # 橙色 - 中等威胁
            2: '#65A30D',  # 黄绿色 - 低威胁
            1: '#059669',  # 绿色 - 极低威胁
            0: '#6B7280'   # 灰色 - 无威胁
        }
        
        self.status_colors = {
            'planned': '#6B7280',
            'ready': '#3B82F6',
            'executing': '#F59E0B',
            'completed': '#10B981',
            'failed': '#EF4444',
            'cancelled': '#8B5CF6',
            'paused': '#F97316'
        }
        
        logger.info("✅ 航天甘特图HTML生成器初始化完成")
    
    def generate_html_gantt(
        self,
        gantt_data: ConstellationGanttData,
        output_path: str,
        interactive: bool = True
    ) -> str:
        """生成交互式HTML甘特图"""
        try:
            logger.info(f"🌐 开始生成交互式HTML甘特图: {output_path}")
            
            # 准备数据
            df = self._prepare_plotly_data(gantt_data)
            
            # 创建甘特图
            fig = self._create_plotly_gantt(df, gantt_data)
            
            # 设置布局
            self._setup_plotly_layout(fig, gantt_data)
            
            # 保存HTML文件
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 配置HTML输出
            config = {
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d'],
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': f'aerospace_gantt_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                    'height': 800,
                    'width': 1400,
                    'scale': 2
                }
            }
            
            # 生成HTML
            html_content = self._generate_custom_html(fig, gantt_data, config)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"✅ HTML甘特图已生成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"❌ 生成HTML甘特图失败: {e}")
            raise
    
    def _prepare_plotly_data(self, gantt_data: ConstellationGanttData) -> pd.DataFrame:
        """准备Plotly数据"""
        data = []
        
        for task in gantt_data.tasks:
            # 获取任务属性
            threat_level = getattr(task, 'threat_level', 3)
            priority = getattr(task, 'priority', 3)
            quality_score = getattr(task, 'quality_score', 0.8)
            
            # 格式化显示文本
            hover_text = (
                f"<b>{task.task_name}</b><br>"
                f"卫星: {task.assigned_satellite}<br>"
                f"目标: {task.target_missile}<br>"
                f"威胁等级: {threat_level}<br>"
                f"优先级: {priority}<br>"
                f"状态: {task.execution_status}<br>"
                f"质量分数: {quality_score:.2f}<br>"
                f"开始: {task.start_time.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"结束: {task.end_time.strftime('%Y-%m-%d %H:%M:%S')}<br>"
                f"持续时间: {(task.end_time - task.start_time).total_seconds() / 60:.1f} 分钟"
            )
            
            data.append({
                'Task': task.task_name,
                'Start': task.start_time,
                'Finish': task.end_time,
                'Resource': task.assigned_satellite,
                'Target': task.target_missile,
                'ThreatLevel': threat_level,
                'Priority': priority,
                'Status': task.execution_status,
                'Quality': quality_score,
                'Color': self.threat_colors.get(threat_level, self.threat_colors[3]),
                'HoverText': hover_text
            })
        
        return pd.DataFrame(data)
    
    def _create_plotly_gantt(self, df: pd.DataFrame, gantt_data: ConstellationGanttData) -> go.Figure:
        """创建Plotly甘特图"""
        # 创建甘特图
        fig = px.timeline(
            df,
            x_start="Start",
            x_end="Finish",
            y="Resource",
            color="ThreatLevel",
            color_continuous_scale=[
                [0, self.threat_colors[1]],
                [0.25, self.threat_colors[2]],
                [0.5, self.threat_colors[3]],
                [0.75, self.threat_colors[4]],
                [1, self.threat_colors[5]]
            ],
            hover_data={
                'Task': True,
                'Target': True,
                'Status': True,
                'Quality': ':.2f',
                'Start': False,
                'Finish': False,
                'ThreatLevel': False
            },
            title="航天任务调度甘特图 / Aerospace Mission Scheduling Gantt Chart"
        )
        
        # 自定义悬停信息
        fig.update_traces(
            hovertemplate=df['HoverText'] + "<extra></extra>",
            textposition="inside"
        )
        
        return fig
    
    def _setup_plotly_layout(self, fig: go.Figure, gantt_data: ConstellationGanttData):
        """设置Plotly布局"""
        fig.update_layout(
            title={
                'text': f"<b>航天任务调度甘特图</b><br><sub>任务场景: {gantt_data.mission_scenario} | 图表类型: {gantt_data.chart_type}</sub>",
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 18, 'color': '#1F2937'}
            },
            xaxis_title="时间 / Time",
            yaxis_title="卫星平台 / Satellite Platform",
            font=dict(family="Arial, sans-serif", size=12, color="#374151"),
            plot_bgcolor='white',
            paper_bgcolor='#F8FAFC',
            height=max(600, len(gantt_data.satellites) * 80 + 200),
            width=1400,
            margin=dict(l=150, r=200, t=100, b=80),
            coloraxis_colorbar=dict(
                title=dict(text="威胁等级<br>Threat Level"),
                tickmode="array",
                tickvals=[1, 2, 3, 4, 5],
                ticktext=["极低", "低", "中", "高", "极高"]
            )
        )
        
        # 设置时间轴格式
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='#E5E7EB',
            tickformat='%H:%M',
            dtick=3600000  # 1小时间隔
        )
        
        # 设置Y轴
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='#E5E7EB',
            categoryorder='category ascending'
        )
    
    def _generate_custom_html(self, fig: go.Figure, gantt_data: ConstellationGanttData, config: Dict) -> str:
        """生成自定义HTML内容"""
        # 获取Plotly HTML
        plotly_html = fig.to_html(
            include_plotlyjs=True,
            config=config,
            div_id="gantt-chart"
        )
        
        # 添加自定义CSS和JavaScript
        custom_html = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>航天任务调度甘特图 - {gantt_data.mission_scenario}</title>
    <style>
        body {{
            font-family: 'Arial', 'Microsoft YaHei', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #F8FAFC;
        }}
        .header {{
            text-align: center;
            margin-bottom: 20px;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .info-panel {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .info-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .info-card h3 {{
            margin: 0 0 10px 0;
            color: #1F2937;
            font-size: 14px;
        }}
        .info-card p {{
            margin: 0;
            color: #6B7280;
            font-size: 16px;
            font-weight: bold;
        }}
        .chart-container {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        .footer {{
            text-align: center;
            margin-top: 20px;
            padding: 15px;
            background: white;
            border-radius: 8px;
            color: #6B7280;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 航天任务调度甘特图</h1>
        <p>Aerospace Mission Scheduling Gantt Chart</p>
    </div>
    
    <div class="info-panel">
        <div class="info-card">
            <h3>任务场景</h3>
            <p>{gantt_data.mission_scenario}</p>
        </div>
        <div class="info-card">
            <h3>任务数量</h3>
            <p>{len(gantt_data.tasks)} 个</p>
        </div>
        <div class="info-card">
            <h3>卫星数量</h3>
            <p>{len(gantt_data.satellites)} 颗</p>
        </div>
        <div class="info-card">
            <h3>目标数量</h3>
            <p>{len(gantt_data.missiles)} 个</p>
        </div>
        <div class="info-card">
            <h3>时间跨度</h3>
            <p>{(gantt_data.end_time - gantt_data.start_time).total_seconds() / 3600:.1f} 小时</p>
        </div>
        <div class="info-card">
            <h3>生成时间</h3>
            <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    </div>
    
    <div class="chart-container">
        {plotly_html.split('<body>')[1].split('</body>')[0]}
    </div>
    
    <div class="footer">
        <p>© 2025 星座多智能体系统 CONSTELLATION Multi-Agent System v2.0.0</p>
        <p>Powered by Plotly | Generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
        """
        
        return custom_html

# 全局HTML生成器实例
_html_gantt_generator = None

def get_gantt_html_generator() -> AerospaceGanttHTMLGenerator:
    """获取全局甘特图HTML生成器实例"""
    global _html_gantt_generator
    if _html_gantt_generator is None:
        _html_gantt_generator = AerospaceGanttHTMLGenerator()
    return _html_gantt_generator
