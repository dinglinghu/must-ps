"""
航天领域专业甘特图图像生成器
负责生成PNG、SVG、PDF等图像格式的专业航天甘特图
"""

import logging
import os
import platform
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle, FancyBboxPatch
import matplotlib.font_manager as fm
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import numpy as np

from .realistic_constellation_gantt import ConstellationGanttData
from .gantt_save_config_manager import get_gantt_save_config_manager

logger = logging.getLogger(__name__)

class AerospaceGanttImageGenerator:
    """航天领域专业甘特图图像生成器"""

    def __init__(self):
        self.config_manager = get_gantt_save_config_manager()

        # 设置字体
        self._setup_fonts()

        # 航天领域专业颜色配置
        self.colors = {
            'observation': '#1E3A8A',      # 深蓝色 - 观测任务
            'tracking': '#0F766E',         # 青绿色 - 跟踪任务
            'communication': '#DC2626',    # 红色 - 通信任务
            'processing': '#7C2D12',       # 棕色 - 数据处理
            'maintenance': '#6B7280',      # 灰色 - 维护任务
            'planning': '#7C3AED',         # 紫色 - 规划任务
            'coordination': '#059669',     # 绿色 - 协调任务
            'emergency': '#EF4444',        # 亮红色 - 紧急任务
            'default': '#374151'           # 深灰色 - 默认
        }

        # 威胁等级颜色（航天标准）
        self.threat_colors = {
            5: '#DC2626',  # 红色 - 极高威胁
            4: '#EA580C',  # 橙红色 - 高威胁
            3: '#D97706',  # 橙色 - 中等威胁
            2: '#65A30D',  # 黄绿色 - 低威胁
            1: '#059669',  # 绿色 - 极低威胁
            0: '#6B7280'   # 灰色 - 无威胁
        }

        # 执行状态颜色
        self.status_colors = {
            'planned': '#6B7280',      # 灰色 - 计划中
            'ready': '#3B82F6',        # 蓝色 - 就绪
            'executing': '#F59E0B',    # 黄色 - 执行中
            'completed': '#10B981',    # 绿色 - 已完成
            'failed': '#EF4444',       # 红色 - 失败
            'cancelled': '#8B5CF6',    # 紫色 - 已取消
            'paused': '#F97316'        # 橙色 - 暂停
        }

        # 优先级样式
        self.priority_styles = {
            5: {'pattern': '///', 'linewidth': 3},  # 最高优先级
            4: {'pattern': '\\\\\\', 'linewidth': 2.5},
            3: {'pattern': '|||', 'linewidth': 2},
            2: {'pattern': '---', 'linewidth': 1.5},
            1: {'pattern': '...', 'linewidth': 1}
        }

        logger.info("✅ 航天领域专业甘特图图像生成器初始化完成")

    def _setup_fonts(self):
        """设置字体配置"""
        try:
            # 检测系统并设置合适的字体
            system = platform.system()

            if system == "Windows":
                # Windows系统字体
                font_candidates = [
                    'Microsoft YaHei',     # 微软雅黑
                    'SimHei',              # 黑体
                    'SimSun',              # 宋体
                    'Arial Unicode MS',    # Arial Unicode
                    'Calibri',             # Calibri
                    'Arial'                # Arial
                ]
            elif system == "Darwin":  # macOS
                font_candidates = [
                    'PingFang SC',         # 苹方
                    'Helvetica Neue',      # Helvetica Neue
                    'Arial Unicode MS',    # Arial Unicode
                    'STHeiti',             # 华文黑体
                    'Arial'                # Arial
                ]
            else:  # Linux
                font_candidates = [
                    'Noto Sans CJK SC',    # Noto Sans 中文
                    'WenQuanYi Micro Hei', # 文泉驿微米黑
                    'DejaVu Sans',         # DejaVu Sans
                    'Liberation Sans',     # Liberation Sans
                    'Arial'                # Arial
                ]

            # 查找可用字体
            available_fonts = [f.name for f in fm.fontManager.ttflist]
            selected_font = None

            for font in font_candidates:
                if font in available_fonts:
                    selected_font = font
                    break

            if selected_font:
                logger.info(f"🔤 使用字体: {selected_font}")
                plt.rcParams['font.sans-serif'] = [selected_font] + font_candidates
            else:
                logger.warning("⚠️ 未找到合适的中文字体，使用默认字体")
                plt.rcParams['font.sans-serif'] = font_candidates

            # 设置字体属性
            plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题
            plt.rcParams['font.size'] = 10
            plt.rcParams['axes.titlesize'] = 14
            plt.rcParams['axes.labelsize'] = 12
            plt.rcParams['xtick.labelsize'] = 10
            plt.rcParams['ytick.labelsize'] = 10
            plt.rcParams['legend.fontsize'] = 10

        except Exception as e:
            logger.error(f"❌ 字体设置失败: {e}")
            # 使用默认字体配置
            plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
            plt.rcParams['axes.unicode_minus'] = False
    
    def generate_gantt_image(
        self,
        gantt_data: ConstellationGanttData,
        output_path: str,
        format: str = "png",
        quality: str = "high"
    ) -> str:
        """生成航天领域专业甘特图图像"""
        try:
            logger.info(f"🚀 开始生成航天领域专业甘特图: {format.upper()}")

            # 获取图像设置
            image_settings = self.config_manager.get_image_settings(quality)

            # 创建专业航天甘特图
            fig, ax = self._create_aerospace_gantt_chart(gantt_data, image_settings)

            # 保存图像
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 设置保存参数
            save_params = {
                'bbox_inches': 'tight',
                'facecolor': 'white',
                'edgecolor': 'none',
                'pad_inches': 0.2
            }

            if format.lower() == 'png':
                save_params.update({
                    'format': 'png',
                    'dpi': image_settings['dpi'],
                    'transparent': False
                })
                fig.savefig(output_path, **save_params)

            elif format.lower() == 'svg':
                save_params.update({
                    'format': 'svg',
                    'transparent': True
                })
                fig.savefig(output_path, **save_params)

            elif format.lower() == 'pdf':
                save_params.update({
                    'format': 'pdf',
                    'orientation': 'landscape'
                })
                fig.savefig(output_path, **save_params)

            elif format.lower() == 'eps':
                save_params.update({
                    'format': 'eps',
                    'dpi': image_settings['dpi']
                })
                fig.savefig(output_path, **save_params)

            else:
                raise ValueError(f"不支持的图像格式: {format}")

            plt.close(fig)

            logger.info(f"✅ 航天甘特图已生成: {output_path}")
            return str(output_path)

        except Exception as e:
            logger.error(f"❌ 生成航天甘特图失败: {e}")
            raise
    
    def _create_aerospace_gantt_chart(self, gantt_data: ConstellationGanttData, image_settings: Dict) -> tuple:
        """创建航天领域专业甘特图"""
        # 设置图表大小（航天标准比例）
        fig_width = image_settings['width'] / 100
        fig_height = max(image_settings['height'] / 100, len(gantt_data.satellites) * 1.2)

        # 创建图形和子图
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        # 设置专业航天背景
        fig.patch.set_facecolor('#F8FAFC')  # 浅灰蓝色背景
        ax.set_facecolor('#FFFFFF')         # 白色绘图区

        # 准备数据
        tasks = gantt_data.tasks
        if not tasks:
            raise ValueError("没有任务数据可以绘制")

        # 按卫星分组并排序任务
        satellite_tasks = {}
        for task in tasks:
            satellite = task.assigned_satellite
            if satellite not in satellite_tasks:
                satellite_tasks[satellite] = []
            satellite_tasks[satellite].append(task)

        # 按任务开始时间排序
        for satellite in satellite_tasks:
            satellite_tasks[satellite].sort(key=lambda t: t.start_time)

        # 绘制任务条和卫星轨道
        y_pos = 0
        y_labels = []
        y_positions = []

        for satellite, sat_tasks in satellite_tasks.items():
            y_labels.append(self._format_satellite_label(satellite))
            y_positions.append(y_pos)

            # 绘制卫星轨道背景
            self._draw_satellite_track(ax, y_pos, gantt_data.start_time, gantt_data.end_time)

            # 绘制任务条
            for task in sat_tasks:
                self._draw_aerospace_task_bar(ax, task, y_pos)

            y_pos += 1

        # 设置Y轴（卫星列表）
        ax.set_yticks(y_positions)
        ax.set_yticklabels(y_labels, fontsize=11, fontweight='bold')
        ax.set_ylabel('卫星平台 / Satellite Platform', fontsize=13, fontweight='bold', color='#1F2937')

        # 设置X轴（时间轴）
        self._setup_aerospace_time_axis(ax, gantt_data.start_time, gantt_data.end_time)

        # 设置专业标题和样式
        self._setup_aerospace_chart_style(ax, gantt_data)

        # 添加专业图例
        self._add_aerospace_legend(ax)

        # 添加网格和边框
        self._add_professional_grid(ax)

        # 调整布局
        plt.tight_layout(pad=2.0)

        return fig, ax

    def _format_satellite_label(self, satellite: str) -> str:
        """格式化卫星标签"""
        # 将卫星ID格式化为更专业的显示
        if satellite.startswith('SAT_'):
            sat_num = satellite.replace('SAT_', '')
            return f"卫星-{sat_num}\nSAT-{sat_num}"
        elif satellite.startswith('SATELLITE_'):
            sat_num = satellite.replace('SATELLITE_', '')
            return f"卫星-{sat_num}\nSAT-{sat_num}"
        else:
            return satellite

    def _draw_satellite_track(self, ax, y_pos: float, start_time: datetime, end_time: datetime):
        """绘制卫星轨道背景"""
        # 绘制轨道背景条
        track_rect = Rectangle(
            (mdates.date2num(start_time), y_pos - 0.4),
            mdates.date2num(end_time) - mdates.date2num(start_time),
            0.8,
            facecolor='#F1F5F9',
            edgecolor='#CBD5E1',
            linewidth=1,
            alpha=0.3
        )
        ax.add_patch(track_rect)

    def _draw_aerospace_task_bar(self, ax, task, y_pos: float):
        """绘制航天专业任务条"""
        # 转换时间为matplotlib数值
        start_num = mdates.date2num(task.start_time)
        end_num = mdates.date2num(task.end_time)
        duration_num = end_num - start_num

        # 根据威胁等级选择主色调
        threat_level = getattr(task, 'threat_level', 3)
        base_color = self.threat_colors.get(threat_level, self.threat_colors[3])

        # 根据任务类别调整色调
        category_color = self.colors.get(task.category, self.colors['default'])

        # 根据执行状态选择边框
        status_color = self.status_colors.get(task.execution_status, self.status_colors['planned'])

        # 任务条高度和位置
        bar_height = 0.5
        bar_y = y_pos - bar_height/2

        # 绘制主任务条（使用FancyBboxPatch实现圆角）
        task_rect = FancyBboxPatch(
            (start_num, bar_y),
            duration_num,
            bar_height,
            boxstyle="round,pad=0.02",
            facecolor=base_color,
            edgecolor=status_color,
            linewidth=2.5,
            alpha=0.85
        )
        ax.add_patch(task_rect)

        # 添加威胁等级指示条
        if threat_level >= 4:
            threat_indicator = Rectangle(
                (start_num, bar_y + bar_height - 0.08),
                duration_num,
                0.08,
                facecolor='#DC2626',
                alpha=0.9
            )
            ax.add_patch(threat_indicator)

        # 添加优先级纹理
        priority = getattr(task, 'priority', 3)
        if priority >= 4:
            self._add_priority_pattern(ax, start_num, bar_y, duration_num, bar_height, priority)

        # 添加任务标签
        self._add_task_label(ax, task, start_num, duration_num, y_pos, base_color)

        # 添加进度指示器（如果有质量分数）
        quality_score = getattr(task, 'quality_score', None)
        if quality_score is not None:
            self._add_quality_indicator(ax, start_num, bar_y, duration_num, quality_score)

    def _add_priority_pattern(self, ax, start_x: float, start_y: float, width: float, height: float, priority: int):
        """添加优先级图案"""
        if priority >= 5:
            # 最高优先级：斜线图案
            for i in range(int(width * 50)):
                line_x = start_x + i * 0.02
                if line_x < start_x + width:
                    ax.plot([line_x, line_x + 0.01], [start_y, start_y + height],
                           color='white', linewidth=1, alpha=0.6)

    def _add_task_label(self, ax, task, start_x: float, width: float, y_pos: float, bg_color: str):
        """添加任务标签"""
        # 计算标签位置
        label_x = start_x + width / 2

        # 格式化任务名称
        task_name = task.task_name
        if len(task_name) > 15:
            task_name = task_name[:12] + "..."

        # 目标信息
        target = getattr(task, 'target_missile', 'Unknown')
        if target.startswith('MISSILE_'):
            target = target.replace('MISSILE_', 'M-')

        # 组合标签文本
        label_text = f"{task_name}\n目标: {target}"

        # 选择文字颜色
        text_color = 'white' if self._is_dark_color(bg_color) else 'black'

        # 绘制文本
        ax.text(
            label_x, y_pos,
            label_text,
            ha='center', va='center',
            fontsize=9,
            fontweight='bold',
            color=text_color,
            bbox=dict(boxstyle="round,pad=0.3", facecolor=bg_color, alpha=0.8, edgecolor='none')
        )

    def _add_quality_indicator(self, ax, start_x: float, start_y: float, width: float, quality: float):
        """添加质量指示器"""
        # 质量条的宽度基于质量分数
        quality_width = width * quality

        # 质量指示条
        quality_rect = Rectangle(
            (start_x, start_y - 0.05),
            quality_width,
            0.03,
            facecolor='#10B981' if quality >= 0.8 else '#F59E0B' if quality >= 0.6 else '#EF4444',
            alpha=0.9
        )
        ax.add_patch(quality_rect)

    def _setup_aerospace_time_axis(self, ax, start_time: datetime, end_time: datetime):
        """设置航天专业时间轴"""
        # 设置时间范围
        ax.set_xlim(mdates.date2num(start_time), mdates.date2num(end_time))

        # 计算时间跨度
        duration_hours = (end_time - start_time).total_seconds() / 3600

        # 根据时间跨度设置合适的时间格式
        if duration_hours <= 2:
            # 小于2小时，每15分钟一个刻度
            ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=15))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=5))
            time_label = "时间 / Time (HH:MM)"
        elif duration_hours <= 12:
            # 小于12小时，每小时一个刻度
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
            ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=30))
            time_label = "时间 / Time (HH:MM)"
        elif duration_hours <= 48:
            # 小于48小时，每4小时一个刻度
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            ax.xaxis.set_minor_locator(mdates.HourLocator(interval=1))
            time_label = "时间 / Time (MM-DD HH:MM)"
        else:
            # 大于48小时，每12小时一个刻度
            ax.xaxis.set_major_locator(mdates.HourLocator(interval=12))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d %H:%M'))
            ax.xaxis.set_minor_locator(mdates.HourLocator(interval=6))
            time_label = "时间 / Time (MM-DD HH:MM)"

        # 设置X轴标签
        ax.set_xlabel(time_label, fontsize=13, fontweight='bold', color='#1F2937')

        # 设置时间标签样式
        plt.setp(ax.xaxis.get_majorticklabels(),
                rotation=30, ha='right', fontsize=10, color='#374151')

        # 设置刻度样式
        ax.tick_params(axis='x', which='major', length=6, width=1.5, color='#6B7280')
        ax.tick_params(axis='x', which='minor', length=3, width=1, color='#9CA3AF')

    def _setup_aerospace_chart_style(self, ax, gantt_data: ConstellationGanttData):
        """设置航天专业图表样式"""
        # 设置专业标题
        main_title = f"航天任务调度甘特图 / Aerospace Mission Scheduling Gantt Chart"
        sub_title = f"任务场景: {gantt_data.mission_scenario} | 图表类型: {gantt_data.chart_type}"

        ax.set_title(main_title, fontsize=16, fontweight='bold', color='#1F2937', pad=25)
        ax.text(0.5, 1.02, sub_title, transform=ax.transAxes, ha='center',
               fontsize=12, color='#6B7280', style='italic')

        # 添加时间戳和版本信息
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        version_info = f"生成时间: {timestamp} | 系统版本: CONSTELLATION v2.0"
        ax.text(0.99, -0.08, version_info, transform=ax.transAxes, ha='right',
               fontsize=8, color='#9CA3AF')

        # 设置Y轴样式
        ax.tick_params(axis='y', which='major', length=6, width=1.5, color='#6B7280')
        plt.setp(ax.yaxis.get_majorticklabels(), fontsize=11, color='#374151')

        # 设置边框样式
        for spine_name, spine in ax.spines.items():
            if spine_name in ['top', 'right']:
                spine.set_visible(False)
            else:
                spine.set_linewidth(2)
                spine.set_color('#374151')

    def _add_professional_grid(self, ax):
        """添加专业网格"""
        # 主网格
        ax.grid(True, which='major', axis='x', color='#E5E7EB', linewidth=1, alpha=0.8)
        ax.grid(True, which='minor', axis='x', color='#F3F4F6', linewidth=0.5, alpha=0.6)
        ax.grid(True, which='major', axis='y', color='#E5E7EB', linewidth=0.8, alpha=0.5)

        # 设置网格在背景
        ax.set_axisbelow(True)

    def _add_aerospace_legend(self, ax):
        """添加航天专业图例"""
        from matplotlib.patches import Patch

        # 威胁等级图例
        threat_elements = []
        threat_labels = []
        for level, color in self.threat_colors.items():
            if level > 0:  # 跳过无威胁级别
                threat_elements.append(Patch(facecolor=color, alpha=0.85))
                threat_labels.append(f"威胁等级 {level}")

        # 执行状态图例
        status_elements = []
        status_labels = []
        status_names = {
            'planned': '计划中',
            'ready': '就绪',
            'executing': '执行中',
            'completed': '已完成',
            'failed': '失败',
            'cancelled': '已取消'
        }

        for status, color in self.status_colors.items():
            if status in status_names:
                status_elements.append(Patch(facecolor='white', edgecolor=color, linewidth=3))
                status_labels.append(status_names[status])

        # 任务类型图例
        category_elements = []
        category_labels = []
        category_names = {
            'observation': '观测任务',
            'tracking': '跟踪任务',
            'communication': '通信任务',
            'processing': '数据处理',
            'coordination': '协调任务'
        }

        for category, color in self.colors.items():
            if category in category_names:
                category_elements.append(Patch(facecolor=color, alpha=0.85))
                category_labels.append(category_names[category])

        # 创建威胁等级图例
        if threat_elements:
            legend1 = ax.legend(
                threat_elements, threat_labels,
                title='威胁等级 / Threat Level',
                loc='upper left',
                bbox_to_anchor=(1.02, 1.0),
                frameon=True,
                fancybox=True,
                shadow=True,
                fontsize=10,
                title_fontsize=11
            )
            legend1.get_frame().set_facecolor('#F8FAFC')
            legend1.get_frame().set_edgecolor('#E5E7EB')
            ax.add_artist(legend1)

        # 创建执行状态图例
        if status_elements:
            legend2 = ax.legend(
                status_elements, status_labels,
                title='执行状态 / Execution Status',
                loc='upper left',
                bbox_to_anchor=(1.02, 0.65),
                frameon=True,
                fancybox=True,
                shadow=True,
                fontsize=10,
                title_fontsize=11
            )
            legend2.get_frame().set_facecolor('#F8FAFC')
            legend2.get_frame().set_edgecolor('#E5E7EB')
            ax.add_artist(legend2)

        # 创建任务类型图例
        if category_elements:
            legend3 = ax.legend(
                category_elements, category_labels,
                title='任务类型 / Task Category',
                loc='upper left',
                bbox_to_anchor=(1.02, 0.3),
                frameon=True,
                fancybox=True,
                shadow=True,
                fontsize=10,
                title_fontsize=11
            )
            legend3.get_frame().set_facecolor('#F8FAFC')
            legend3.get_frame().set_edgecolor('#E5E7EB')
    
    def _is_dark_color(self, color: str) -> bool:
        """判断颜色是否为深色"""
        # 简单的颜色亮度判断
        if color.startswith('#'):
            hex_color = color[1:]
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            brightness = (r * 299 + g * 587 + b * 114) / 1000
            return brightness < 128
        return False

# 全局图像生成器实例
_aerospace_gantt_generator = None

def get_gantt_image_generator() -> AerospaceGanttImageGenerator:
    """获取全局航天甘特图图像生成器实例"""
    global _aerospace_gantt_generator
    if _aerospace_gantt_generator is None:
        _aerospace_gantt_generator = AerospaceGanttImageGenerator()
    return _aerospace_gantt_generator

# 向后兼容的别名
def get_aerospace_gantt_generator() -> AerospaceGanttImageGenerator:
    """获取航天甘特图生成器（专用接口）"""
    return get_gantt_image_generator()
