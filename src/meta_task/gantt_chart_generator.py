"""
航天领域专业甘特图生成器
用于生成元任务和可见性的甘特图
采用航天领域专业的配色方案和样式设计
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.collections import PatchCollection
import matplotlib.patches as mpatches
import numpy as np
import json

logger = logging.getLogger(__name__)


class GanttChartGenerator:
    """航天领域专业甘特图生成器"""

    def __init__(self, config_manager):
        """
        初始化甘特图生成器

        Args:
            config_manager: 配置管理器
        """
        self.config_manager = config_manager
        self.gantt_config = self.config_manager.get_meta_task_config()["gantt_chart"]

        # 获取可视化配置
        visualization_config = self.config_manager.config.get("visualization", {})
        self.colors = visualization_config.get("colors", {})
        self.style = visualization_config.get("style", {})

        # 设置matplotlib样式
        self._setup_matplotlib_style()

        logger.info("📊 航天领域专业甘特图生成器初始化完成")

    def _setup_matplotlib_style(self):
        """设置matplotlib专业样式"""
        # 字体设置
        plt.rcParams['font.family'] = self.style["font_family"]
        plt.rcParams['font.size'] = self.style["tick_font_size"]
        plt.rcParams['axes.titlesize'] = self.style["title_font_size"]
        plt.rcParams['axes.labelsize'] = self.style["label_font_size"]
        plt.rcParams['xtick.labelsize'] = self.style["tick_font_size"]
        plt.rcParams['ytick.labelsize'] = self.style["tick_font_size"]
        plt.rcParams['legend.fontsize'] = self.style["legend_font_size"]

        # 线条和网格设置
        plt.rcParams['axes.linewidth'] = self.style["border_width"]
        plt.rcParams['grid.linewidth'] = self.style["grid_line_width"]
        plt.rcParams['lines.linewidth'] = self.style["line_width"]

        # 颜色设置
        plt.rcParams['axes.facecolor'] = self.colors["background"]
        plt.rcParams['figure.facecolor'] = self.colors["background"]
        plt.rcParams['text.color'] = self.colors["text_primary"]
        plt.rcParams['axes.labelcolor'] = self.colors["text_primary"]
        plt.rcParams['xtick.color'] = self.colors["text_secondary"]
        plt.rcParams['ytick.color'] = self.colors["text_secondary"]

        # 网格设置
        plt.rcParams['axes.grid'] = True
        plt.rcParams['grid.color'] = self.colors["grid_major"]
        plt.rcParams['grid.alpha'] = self.style["grid_alpha"]

        # 字体设置（优先使用英文，避免中文字体问题）
        plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans', 'Liberation Sans']
        plt.rcParams['axes.unicode_minus'] = False
    
    def generate_meta_task_gantt(self, meta_task_set, output_path: str) -> bool:
        """
        生成航天领域专业的元任务甘特图

        Args:
            meta_task_set: 元任务信息集
            output_path: 输出文件路径

        Returns:
            是否生成成功
        """
        try:
            logger.info(f"📊 生成航天领域专业元任务甘特图: {output_path}")

            # 创建图形
            fig_size = self.gantt_config["figure_size"]
            fig, ax = plt.subplots(figsize=fig_size, dpi=self.gantt_config["dpi"])

            # 设置专业背景
            fig.patch.set_facecolor(self.colors["background"])
            ax.set_facecolor(self.colors["background"])

            # 准备数据
            y_pos = 0
            y_labels = []
            y_positions = []

            # 1. 为每个导弹目标绘制元任务甘特图
            logger.debug("为每个导弹目标绘制元任务甘特图...")

            # 获取完整时间范围
            start_time, end_time = meta_task_set.time_range
            total_duration_days = (end_time - start_time).total_seconds() / (24 * 3600)

            # 为每个导弹目标创建一行
            for missile_id in meta_task_set.total_missiles:
                # 简化导弹ID显示
                missile_display_name = missile_id.replace("GlobalThreat_001_", "TGT-")
                y_labels.append(f"Target {missile_display_name}")
                y_positions.append(y_pos)

                # 绘制该目标的元任务时间轴背景
                background_rect = FancyBboxPatch(
                    (mdates.date2num(start_time), y_pos - self.style["bar_height"]/2),
                    total_duration_days, self.style["bar_height"],
                    boxstyle="round,pad=0.01",
                    facecolor=self.colors["visibility_none"],
                    alpha=0.2,
                    edgecolor=self.colors["text_secondary"],
                    linewidth=self.style["border_width"]/2
                )
                ax.add_patch(background_rect)

                # 在时间轴上绘制该目标的元任务窗口
                self._draw_target_meta_task_windows(ax, meta_task_set, missile_id, y_pos)

                y_pos += 1

            # 2. 绘制元任务窗口分割线
            logger.debug("绘制元任务窗口分割线...")
            self._draw_meta_task_window_dividers(ax, meta_task_set)

            # 3. 简化处理，只关注时间维度
            logger.debug("简化甘特图，只体现时间维度...")

            # 3. 设置专业坐标轴
            logger.debug("设置坐标轴和样式...")

            # Y轴设置
            ax.set_ylim(-0.5, y_pos - 0.5)
            ax.set_yticks(y_positions)
            ax.set_yticklabels(y_labels, fontsize=self.style["label_font_size"])

            # X轴时间设置
            start_time, end_time = meta_task_set.time_range
            ax.set_xlim(mdates.date2num(start_time), mdates.date2num(end_time))

            # 智能时间轴格式化
            total_duration_hours = (end_time - start_time).total_seconds() / 3600
            if total_duration_hours <= 2:
                # 短时间：每10分钟一个主刻度
                ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
                ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=2))
            elif total_duration_hours <= 6:
                # 中等时间：每30分钟一个主刻度
                ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
                ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=10))
            else:
                # 长时间：每小时一个主刻度
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
                ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=30))

            time_format = self.gantt_config["time_format"]
            ax.xaxis.set_major_formatter(mdates.DateFormatter(time_format))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            # 4. 设置简洁的时间维度标题和标签
            start_time_str = meta_task_set.time_range[0].strftime('%H:%M:%S')
            end_time_str = meta_task_set.time_range[1].strftime('%H:%M:%S')
            duration_str = f"{total_duration_hours:.1f}h"

            title = f"Meta-Task Timeline\n{start_time_str} - {end_time_str} ({duration_str})"
            ax.set_title(title, fontsize=self.style["title_font_size"],
                        fontweight='bold', color=self.colors["text_primary"], pad=20)

            ax.set_xlabel("Time (UTC)", fontsize=self.style["label_font_size"],
                         color=self.colors["text_primary"])
            ax.set_ylabel("Targets", fontsize=self.style["label_font_size"],
                         color=self.colors["text_primary"])

            # 5. 设置专业网格
            ax.grid(True, which='major', color=self.colors["grid_major"],
                   alpha=self.style["grid_alpha"], linewidth=self.style["grid_line_width"])
            ax.grid(True, which='minor', color=self.colors["grid_minor"],
                   alpha=self.style["grid_alpha"]/2, linewidth=self.style["grid_line_width"]/2)

            # 6. 创建丰富的时间维度图例
            legend_elements = []

            # 为每个目标添加颜色图例
            for i, missile_id in enumerate(meta_task_set.total_missiles):
                target_display_name = missile_id.replace("GlobalThreat_001_", "TGT-")

                # 选择目标专属颜色
                color_keys = [f"meta_task_{j+1}" for j in range(6)]
                if i < len(color_keys):
                    color_key = color_keys[i]
                    color = self.colors.get(color_key, self.colors["meta_task_active"])
                else:
                    accent_colors = ["accent_blue", "accent_teal", "accent_purple", "accent_pink"]
                    color_key = accent_colors[i % len(accent_colors)]
                    color = self.colors.get(color_key, self.colors["meta_task_active"])

                legend_elements.append(
                    mpatches.Patch(facecolor=color, alpha=0.8, label=f"{target_display_name} Active Time")
                )

            legend = ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1),
                             fontsize=self.style["legend_font_size"], frameon=True,
                             fancybox=True, shadow=True)
            legend.get_frame().set_facecolor(self.colors["background"])
            legend.get_frame().set_alpha(0.9)

            # 7. 设置边距和布局
            plt.subplots_adjust(
                left=self.style["margin_left"],
                right=1-self.style["margin_right"],
                top=1-self.style["margin_top"],
                bottom=self.style["margin_bottom"]
            )

            # 保存图形
            output_format = self.gantt_config["output_format"]
            plt.savefig(f"{output_path}.{output_format}",
                       dpi=self.gantt_config["dpi"],
                       bbox_inches='tight',
                       facecolor=self.colors["background"],
                       edgecolor='none')
            plt.close()

            logger.info(f"✅ 航天领域专业元任务甘特图生成成功: {output_path}.{output_format}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 生成元任务甘特图失败: {e}")
            return False
    
    def generate_visibility_gantt(self, meta_task_set, missile_id: str, output_path: str) -> bool:
        """
        生成航天领域专业的单个导弹目标可见性甘特图

        Args:
            meta_task_set: 元任务信息集
            missile_id: 导弹ID
            output_path: 输出文件路径

        Returns:
            是否生成成功
        """
        try:
            logger.info(f"📊 生成导弹 {missile_id} 航天领域专业可见性甘特图: {output_path}")

            # 创建图形
            fig_size = self.gantt_config["figure_size"]
            fig, ax = plt.subplots(figsize=fig_size, dpi=self.gantt_config["dpi"])

            # 设置专业背景
            fig.patch.set_facecolor(self.colors["background"])
            ax.set_facecolor(self.colors["background"])

            # 准备数据
            y_pos = 0
            y_labels = []
            y_positions = []

            # 获取所有卫星列表（从元任务数据中推断）
            satellite_list = []
            for window in meta_task_set.meta_windows:
                if missile_id in window.visibility_windows:
                    satellite_list.extend(window.visibility_windows[missile_id].keys())

            # 去重并排序
            satellite_list = sorted(list(set(satellite_list)))

            if not satellite_list:
                logger.warning(f"⚠️ 导弹 {missile_id} 没有可见性数据")
                return False

            # 1. 绘制每颗卫星的可见性窗口（按可见性质量分级）
            logger.debug("绘制卫星可见性窗口...")
            for satellite_index, satellite_id in enumerate(satellite_list):
                # 美化卫星名称显示
                satellite_display_name = satellite_id.replace("Satellite", "SAT-")
                y_labels.append(f"Satellite {satellite_display_name}")
                y_positions.append(y_pos)

                # 为每颗卫星选择专属颜色
                visibility_color_keys = [f"visibility_{i+1}" for i in range(8)]
                if satellite_index < len(visibility_color_keys):
                    color_key = visibility_color_keys[satellite_index]
                    color = self.colors.get(color_key, self.colors["visibility_high"])
                else:
                    # 如果卫星数量超过预定义颜色，使用循环颜色
                    accent_colors = ["accent_green", "accent_teal", "accent_blue", "accent_purple"]
                    color_key = accent_colors[satellite_index % len(accent_colors)]
                    color = self.colors.get(color_key, self.colors["visibility_high"])

                # 收集该卫星对该导弹的所有可见性窗口
                visibility_windows = []
                for window in meta_task_set.meta_windows:
                    if missile_id in window.visibility_windows:
                        satellite_visibility = window.visibility_windows[missile_id].get(satellite_id, [])
                        visibility_windows.extend(satellite_visibility)

                # 绘制可见性时间段
                for vis_window in visibility_windows:
                    start_time = vis_window["start"]
                    end_time = vis_window["end"]
                    duration_seconds = (end_time - start_time).total_seconds()
                    duration_hours = duration_seconds / 3600
                    duration_days = duration_hours / 24

                    # 使用卫星专属颜色
                    alpha = 0.7

                    # 创建丰富颜色的可见性时间段
                    rect = Rectangle(
                        (mdates.date2num(start_time), y_pos - self.style["bar_height"]/2),
                        duration_days, self.style["bar_height"],
                        facecolor=color,
                        alpha=alpha,
                        edgecolor=self.colors["text_primary"],
                        linewidth=0.5
                    )
                    ax.add_patch(rect)

                y_pos += 1

            # 2. 绘制导弹飞行时间线（作为参考基准）
            logger.debug("绘制导弹飞行参考时间线...")
            try:
                from src.stk_interface.missile_manager import get_missile_manager
                missile_manager = get_missile_manager()
                launch_time, impact_time = missile_manager.get_missile_launch_and_impact_times(missile_id)

                if launch_time and impact_time:
                    # 简化导弹ID显示
                    missile_display_name = missile_id.replace("GlobalThreat_001_", "TGT-")
                    y_labels.append(f"Target {missile_display_name} Flight Trajectory")
                    y_positions.append(y_pos)

                    flight_duration_seconds = (impact_time - launch_time).total_seconds()
                    flight_duration_hours = flight_duration_seconds / 3600
                    flight_duration_days = flight_duration_hours / 24

                    # 绘制整体飞行时间线（半透明背景）
                    flight_rect = FancyBboxPatch(
                        (mdates.date2num(launch_time), y_pos - self.style["bar_height"]/2),
                        flight_duration_days, self.style["bar_height"],
                        boxstyle="round,pad=0.01",
                        facecolor=self.colors["missile_flight"],
                        alpha=0.4,
                        edgecolor=self.colors["text_primary"],
                        linewidth=self.style["border_width"],
                        linestyle='--'
                    )
                    ax.add_patch(flight_rect)

                    # 简化处理，只保留时间维度

                    y_pos += 1

            except Exception as e:
                logger.debug(f"绘制导弹飞行时间线失败: {e}")

            # 3. 设置专业坐标轴和样式
            logger.debug("设置可见性甘特图坐标轴和样式...")

            # Y轴设置
            ax.set_ylim(-0.5, y_pos - 0.5)
            ax.set_yticks(y_positions)
            ax.set_yticklabels(y_labels, fontsize=self.style["label_font_size"])

            # X轴时间设置
            start_time, end_time = meta_task_set.time_range
            ax.set_xlim(mdates.date2num(start_time), mdates.date2num(end_time))

            # 智能时间轴格式化
            total_duration_hours = (end_time - start_time).total_seconds() / 3600
            if total_duration_hours <= 2:
                ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
                ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=2))
            elif total_duration_hours <= 6:
                ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
                ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=10))
            else:
                ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
                ax.xaxis.set_minor_locator(mdates.MinuteLocator(interval=30))

            time_format = self.gantt_config["time_format"]
            ax.xaxis.set_major_formatter(mdates.DateFormatter(time_format))
            plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

            # 4. 设置简洁的时间维度标题和标签
            missile_display_name = missile_id.replace("GlobalThreat_001_", "TGT-")
            start_time_str = meta_task_set.time_range[0].strftime('%H:%M:%S')
            end_time_str = meta_task_set.time_range[1].strftime('%H:%M:%S')

            title = f"Target {missile_display_name} Visibility Timeline\n{start_time_str} - {end_time_str} ({total_duration_hours:.1f}h)"
            ax.set_title(title, fontsize=self.style["title_font_size"],
                        fontweight='bold', color=self.colors["text_primary"], pad=20)

            ax.set_xlabel("Time (UTC)", fontsize=self.style["label_font_size"],
                         color=self.colors["text_primary"])
            ax.set_ylabel("Satellites", fontsize=self.style["label_font_size"],
                         color=self.colors["text_primary"])

            # 5. 设置专业网格
            ax.grid(True, which='major', color=self.colors["grid_major"],
                   alpha=self.style["grid_alpha"], linewidth=self.style["grid_line_width"])
            ax.grid(True, which='minor', color=self.colors["grid_minor"],
                   alpha=self.style["grid_alpha"]/2, linewidth=self.style["grid_line_width"]/2)

            # 6. 创建丰富的卫星颜色图例
            legend_elements = []

            # 为每颗卫星添加颜色图例（最多显示前6颗）
            display_satellites = satellite_list[:6] if len(satellite_list) > 6 else satellite_list
            for satellite_index, satellite_id in enumerate(display_satellites):
                satellite_display_name = satellite_id.replace("Satellite", "SAT-")

                # 选择卫星专属颜色
                visibility_color_keys = [f"visibility_{j+1}" for j in range(8)]
                if satellite_index < len(visibility_color_keys):
                    color_key = visibility_color_keys[satellite_index]
                    color = self.colors.get(color_key, self.colors["visibility_high"])
                else:
                    accent_colors = ["accent_green", "accent_teal", "accent_blue", "accent_purple"]
                    color_key = accent_colors[satellite_index % len(accent_colors)]
                    color = self.colors.get(color_key, self.colors["visibility_high"])

                legend_elements.append(
                    mpatches.Patch(facecolor=color, alpha=0.7, label=f"{satellite_display_name} Visibility")
                )

            # 如果卫星数量超过6颗，添加省略说明
            if len(satellite_list) > 6:
                legend_elements.append(
                    mpatches.Patch(facecolor=self.colors["text_secondary"], alpha=0.5,
                                 label=f"... and {len(satellite_list)-6} more satellites")
                )

            # 添加飞行时间图例
            legend_elements.append(
                mpatches.Patch(facecolor=self.colors["missile_flight"], alpha=0.4, label="Flight Time")
            )

            legend = ax.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.02, 1),
                             fontsize=self.style["legend_font_size"], frameon=True,
                             fancybox=True, shadow=True)
            legend.get_frame().set_facecolor(self.colors["background"])
            legend.get_frame().set_alpha(0.9)

            # 7. 设置边距和布局
            plt.subplots_adjust(
                left=self.style["margin_left"],
                right=1-self.style["margin_right"],
                top=1-self.style["margin_top"],
                bottom=self.style["margin_bottom"]
            )

            # 保存图形
            output_format = self.gantt_config["output_format"]
            plt.savefig(f"{output_path}.{output_format}",
                       dpi=self.gantt_config["dpi"],
                       bbox_inches='tight',
                       facecolor=self.colors["background"],
                       edgecolor='none')
            plt.close()

            logger.info(f"✅ 导弹 {missile_id} 航天领域专业可见性甘特图生成成功: {output_path}.{output_format}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 生成可见性甘特图失败: {e}")
            return False

    def _draw_target_meta_task_windows(self, ax, meta_task_set, missile_id: str, y_pos: int):
        """
        为指定目标绘制元任务窗口（使用丰富颜色，避免重叠）

        Args:
            ax: matplotlib轴对象
            meta_task_set: 元任务信息集
            missile_id: 导弹ID
            y_pos: Y轴位置
        """
        try:
            # 获取目标索引，用于选择颜色
            target_index = meta_task_set.total_missiles.index(missile_id) if missile_id in meta_task_set.total_missiles else 0

            # 选择目标专属颜色
            color_keys = [f"meta_task_{i+1}" for i in range(6)]
            if target_index < len(color_keys):
                color_key = color_keys[target_index]
                color = self.colors.get(color_key, self.colors["meta_task_active"])
            else:
                # 如果目标数量超过预定义颜色，使用循环颜色
                accent_colors = ["accent_blue", "accent_teal", "accent_purple", "accent_pink"]
                color_key = accent_colors[target_index % len(accent_colors)]
                color = self.colors.get(color_key, self.colors["meta_task_active"])

            # 遍历所有元任务窗口
            for i, window in enumerate(meta_task_set.meta_windows):
                # 计算窗口时间参数
                window_start = window.start_time
                window_duration_days = window.duration / (24 * 3600)

                # 检查该目标是否在此窗口内
                is_target_in_window = missile_id in window.missiles

                if is_target_in_window:
                    # 目标在窗口内 - 使用目标专属颜色，避免重叠加深
                    alpha = 0.8

                    # 创建简洁的时间段矩形（无重叠效果）
                    window_rect = Rectangle(
                        (mdates.date2num(window_start), y_pos - self.style["bar_height"]/2),
                        window_duration_days, self.style["bar_height"],
                        facecolor=color,
                        alpha=alpha,
                        edgecolor=self.colors["text_primary"],
                        linewidth=0.5
                    )
                    ax.add_patch(window_rect)

        except Exception as e:
            logger.debug(f"绘制目标 {missile_id} 元任务窗口失败: {e}")

    def _draw_meta_task_window_dividers(self, ax, meta_task_set):
        """
        绘制元任务窗口分割线

        Args:
            ax: matplotlib轴对象
            meta_task_set: 元任务信息集
        """
        try:
            # 只绘制简洁的时间分割线
            for i, window in enumerate(meta_task_set.meta_windows):
                window_start = window.start_time

                # 绘制简洁的时间分割线
                ax.axvline(
                    x=mdates.date2num(window_start),
                    color=self.colors["text_secondary"],
                    linewidth=1,
                    linestyle='-',
                    alpha=0.3,
                    zorder=5
                )

            # 为最后一个窗口添加结束分割线
            if meta_task_set.meta_windows:
                last_window = meta_task_set.meta_windows[-1]
                window_end = last_window.start_time + timedelta(seconds=last_window.duration)
                ax.axvline(
                    x=mdates.date2num(window_end),
                    color=self.colors["text_secondary"],
                    linewidth=1,
                    linestyle='-',
                    alpha=0.3,
                    zorder=5
                )

        except Exception as e:
            logger.debug(f"绘制时间分割线失败: {e}")
