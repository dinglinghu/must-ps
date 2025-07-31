"""
分层甘特图管理器
按照战略、战术、执行、分析四个层次组织甘特图的生成和保存
"""

import os
import json
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging

from src.visualization.advanced_gantt_generator import AdvancedGanttGenerator

logger = logging.getLogger(__name__)

class HierarchicalGanttManager:
    """分层甘特图管理器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.gantt_generator = AdvancedGanttGenerator(config_manager)
        
        # 基础目录结构
        self.base_dir = "reports"
        self.gantt_dir = os.path.join(self.base_dir, "gantt")
        
        # 分层目录结构
        self.layer_dirs = {
            'strategic': os.path.join(self.gantt_dir, "strategic"),
            'tactical': os.path.join(self.gantt_dir, "tactical"),
            'execution': os.path.join(self.gantt_dir, "execution"),
            'analysis': os.path.join(self.gantt_dir, "analysis"),
            'archives': os.path.join(self.gantt_dir, "archives")
        }
        
        # 数据和模板目录
        self.data_dir = os.path.join(self.base_dir, "data")
        self.templates_dir = os.path.join(self.base_dir, "templates")
        
        # 确保所有目录存在
        self._ensure_directories()
        
        # 初始化模板
        self._initialize_templates()
        
        logger.info("✅ 分层甘特图管理器初始化完成")
    
    def _ensure_directories(self):
        """确保所有目录存在"""
        # 创建基础目录
        os.makedirs(self.base_dir, exist_ok=True)
        os.makedirs(self.gantt_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.templates_dir, exist_ok=True)
        
        # 创建分层目录
        for layer_dir in self.layer_dirs.values():
            os.makedirs(layer_dir, exist_ok=True)
        
        # 创建归档目录结构
        current_date = datetime.now()
        archive_path = os.path.join(
            self.layer_dirs['archives'],
            str(current_date.year),
            f"{current_date.month:02d}",
            f"{current_date.day:02d}"
        )
        os.makedirs(archive_path, exist_ok=True)
    
    def _initialize_templates(self):
        """初始化图表模板"""
        templates = {
            'strategic_template.json': {
                'name': '战略层甘特图模板',
                'description': '全局任务规划和威胁态势演进',
                'chart_types': [
                    'mission_overview',
                    'threat_evolution',
                    'global_timeline'
                ],
                'default_settings': {
                    'time_scale': 'hours',
                    'color_scheme': 'threat_based',
                    'show_statistics': True,
                    'include_legend': True
                }
            },
            'tactical_template.json': {
                'name': '战术层甘特图模板',
                'description': '任务分配、可见性窗口和资源利用',
                'chart_types': [
                    'task_allocation',
                    'visibility_windows',
                    'resource_utilization'
                ],
                'default_settings': {
                    'time_scale': 'minutes',
                    'color_scheme': 'satellite_based',
                    'show_resource_bars': True,
                    'include_workload_balance': True
                }
            },
            'execution_template.json': {
                'name': '执行层甘特图模板',
                'description': '单卫星详细任务和协商过程',
                'chart_types': [
                    'satellite_detailed',
                    'negotiation_process',
                    'real_time_status'
                ],
                'default_settings': {
                    'time_scale': 'seconds',
                    'color_scheme': 'status_based',
                    'show_detailed_timeline': True,
                    'include_communication': True
                }
            },
            'analysis_template.json': {
                'name': '分析层甘特图模板',
                'description': '性能对比和瓶颈分析',
                'chart_types': [
                    'performance_comparison',
                    'bottleneck_analysis',
                    'optimization_suggestions'
                ],
                'default_settings': {
                    'time_scale': 'adaptive',
                    'color_scheme': 'performance_based',
                    'show_metrics': True,
                    'include_recommendations': True
                }
            }
        }
        
        # 保存模板文件
        for template_name, template_data in templates.items():
            template_path = os.path.join(self.templates_dir, template_name)
            if not os.path.exists(template_path):
                with open(template_path, 'w', encoding='utf-8') as f:
                    json.dump(template_data, f, indent=2, ensure_ascii=False)
    
    def create_simulation_session(self, mission_id: str = None) -> str:
        """创建仿真会话目录"""
        if mission_id is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            mission_id = f"SIMULATION_{timestamp}"
        
        # 创建会话目录
        session_dir = os.path.join(self.gantt_dir, f"session_{mission_id}")
        os.makedirs(session_dir, exist_ok=True)
        
        # 在会话目录下创建分层子目录
        session_layers = {}
        for layer_name in ['strategic', 'tactical', 'execution', 'analysis']:
            layer_path = os.path.join(session_dir, layer_name)
            os.makedirs(layer_path, exist_ok=True)
            session_layers[layer_name] = layer_path
        
        # 创建数据目录
        session_data_dir = os.path.join(session_dir, "data")
        os.makedirs(session_data_dir, exist_ok=True)
        session_layers['data'] = session_data_dir
        
        # 创建会话元数据
        session_metadata = {
            'session_id': mission_id,
            'creation_time': datetime.now().isoformat(),
            'session_dir': session_dir,
            'layer_dirs': session_layers,
            'status': 'initialized'
        }
        
        metadata_path = os.path.join(session_dir, "session_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(session_metadata, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ 仿真会话已创建: {session_dir}")
        return session_dir
    
    def generate_strategic_layer_gantts(
        self,
        session_dir: str,
        gantt_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """生成战略层甘特图"""
        try:
            logger.info("🎨 生成战略层甘特图...")
            
            strategic_dir = os.path.join(session_dir, "strategic")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            generated_charts = {}
            
            # 1. 任务概览甘特图
            mission_overview_path = os.path.join(strategic_dir, f"mission_overview_{timestamp}")
            overview_chart = self.gantt_generator.generate_matplotlib_gantt(
                gantt_data, f"{mission_overview_path}.png", "timeline_overview"
            )
            generated_charts['mission_overview'] = overview_chart
            
            # 2. 威胁态势演进图（使用plotly热力图）
            threat_evolution_path = os.path.join(strategic_dir, f"threat_evolution_{timestamp}")
            threat_chart = self.gantt_generator.generate_plotly_gantt(
                gantt_data, f"{threat_evolution_path}.html", "resource_heatmap"
            )
            generated_charts['threat_evolution'] = threat_chart
            
            # 3. 全局时间线（使用plotly交互式）
            global_timeline_path = os.path.join(strategic_dir, f"global_timeline_{timestamp}")
            timeline_chart = self.gantt_generator.generate_plotly_gantt(
                gantt_data, f"{global_timeline_path}.html", "interactive_timeline"
            )
            generated_charts['global_timeline'] = timeline_chart
            
            # 保存战略层数据
            strategic_data = {
                'layer': 'strategic',
                'generation_time': datetime.now().isoformat(),
                'charts': generated_charts,
                'mission_summary': {
                    'total_threats': len(gantt_data.get('missiles', [])),
                    'high_priority_threats': sum(1 for task in gantt_data.get('tasks', []) 
                                               if task.get('threat_level', 0) >= 4),
                    'mission_duration_hours': 2.0,
                    'coverage_satellites': len(gantt_data.get('satellites', []))
                }
            }
            
            strategic_data_path = os.path.join(strategic_dir, f"strategic_data_{timestamp}.json")
            with open(strategic_data_path, 'w', encoding='utf-8') as f:
                json.dump(strategic_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 战略层甘特图生成完成: {len(generated_charts)} 个图表")
            return generated_charts
            
        except Exception as e:
            logger.error(f"❌ 生成战略层甘特图失败: {e}")
            return {}
    
    def generate_tactical_layer_gantts(
        self,
        session_dir: str,
        gantt_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """生成战术层甘特图"""
        try:
            logger.info("🎨 生成战术层甘特图...")
            
            tactical_dir = os.path.join(session_dir, "tactical")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            generated_charts = {}
            
            # 1. 任务分配甘特图
            task_allocation_path = os.path.join(tactical_dir, f"task_allocation_{timestamp}")
            allocation_chart = self.gantt_generator.generate_matplotlib_gantt(
                gantt_data, f"{task_allocation_path}.png", "task_allocation"
            )
            generated_charts['task_allocation'] = allocation_chart
            
            # 2. 可见性窗口图（使用3D甘特图表示）
            visibility_path = os.path.join(tactical_dir, f"visibility_windows_{timestamp}")
            visibility_chart = self.gantt_generator.generate_plotly_gantt(
                gantt_data, f"{visibility_path}.html", "3d_gantt"
            )
            generated_charts['visibility_windows'] = visibility_chart
            
            # 3. 资源利用率甘特图
            resource_path = os.path.join(tactical_dir, f"resource_utilization_{timestamp}")
            resource_chart = self.gantt_generator.generate_matplotlib_gantt(
                gantt_data, f"{resource_path}.png", "resource_utilization"
            )
            generated_charts['resource_utilization'] = resource_chart
            
            # 保存战术层数据
            tactical_data = {
                'layer': 'tactical',
                'generation_time': datetime.now().isoformat(),
                'charts': generated_charts,
                'tactical_metrics': {
                    'task_distribution': self._calculate_task_distribution(gantt_data),
                    'resource_efficiency': self._calculate_resource_efficiency(gantt_data),
                    'coverage_redundancy': self._calculate_coverage_redundancy(gantt_data)
                }
            }
            
            tactical_data_path = os.path.join(tactical_dir, f"tactical_data_{timestamp}.json")
            with open(tactical_data_path, 'w', encoding='utf-8') as f:
                json.dump(tactical_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 战术层甘特图生成完成: {len(generated_charts)} 个图表")
            return generated_charts
            
        except Exception as e:
            logger.error(f"❌ 生成战术层甘特图失败: {e}")
            return {}

    def generate_execution_layer_gantts(
        self,
        session_dir: str,
        gantt_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """生成执行层甘特图"""
        try:
            logger.info("🎨 生成执行层甘特图...")

            execution_dir = os.path.join(session_dir, "execution")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            generated_charts = {}

            # 1. 单卫星详细任务甘特图
            satellite_detailed_path = os.path.join(execution_dir, f"satellite_detailed_{timestamp}")
            detailed_chart = self.gantt_generator.generate_matplotlib_gantt(
                gantt_data, f"{satellite_detailed_path}.png", "task_allocation"
            )
            generated_charts['satellite_detailed'] = detailed_chart

            # 2. 协商过程甘特图（使用交互式时间线）
            negotiation_path = os.path.join(execution_dir, f"negotiation_process_{timestamp}")
            negotiation_chart = self.gantt_generator.generate_plotly_gantt(
                gantt_data, f"{negotiation_path}.html", "interactive_timeline"
            )
            generated_charts['negotiation_process'] = negotiation_chart

            # 3. 实时状态监控图（使用资源热力图）
            realtime_path = os.path.join(execution_dir, f"realtime_status_{timestamp}")
            realtime_chart = self.gantt_generator.generate_plotly_gantt(
                gantt_data, f"{realtime_path}.html", "resource_heatmap"
            )
            generated_charts['realtime_status'] = realtime_chart

            # 保存执行层数据
            execution_data = {
                'layer': 'execution',
                'generation_time': datetime.now().isoformat(),
                'charts': generated_charts,
                'execution_metrics': {
                    'task_completion_rate': self._calculate_completion_rate(gantt_data),
                    'communication_efficiency': self._calculate_communication_efficiency(gantt_data),
                    'real_time_performance': self._calculate_realtime_performance(gantt_data)
                }
            }

            execution_data_path = os.path.join(execution_dir, f"execution_data_{timestamp}.json")
            with open(execution_data_path, 'w', encoding='utf-8') as f:
                json.dump(execution_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ 执行层甘特图生成完成: {len(generated_charts)} 个图表")
            return generated_charts

        except Exception as e:
            logger.error(f"❌ 生成执行层甘特图失败: {e}")
            return {}

    def generate_analysis_layer_gantts(
        self,
        session_dir: str,
        gantt_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """生成分析层甘特图"""
        try:
            logger.info("🎨 生成分析层甘特图...")

            analysis_dir = os.path.join(session_dir, "analysis")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            generated_charts = {}

            # 1. 性能对比分析图
            performance_path = os.path.join(analysis_dir, f"performance_comparison_{timestamp}")
            performance_chart = self.gantt_generator.generate_seaborn_gantt(
                gantt_data, f"{performance_path}.png", "statistical_analysis"
            )
            generated_charts['performance_comparison'] = performance_chart

            # 2. 瓶颈分析图
            bottleneck_path = os.path.join(analysis_dir, f"bottleneck_analysis_{timestamp}")
            bottleneck_chart = self.gantt_generator.generate_seaborn_gantt(
                gantt_data, f"{bottleneck_path}.png", "correlation_matrix"
            )
            generated_charts['bottleneck_analysis'] = bottleneck_chart

            # 3. 优化建议图（使用3D甘特图）
            optimization_path = os.path.join(analysis_dir, f"optimization_suggestions_{timestamp}")
            optimization_chart = self.gantt_generator.generate_plotly_gantt(
                gantt_data, f"{optimization_path}.html", "3d_gantt"
            )
            generated_charts['optimization_suggestions'] = optimization_chart

            # 保存分析层数据
            analysis_data = {
                'layer': 'analysis',
                'generation_time': datetime.now().isoformat(),
                'charts': generated_charts,
                'analysis_results': {
                    'performance_score': self._calculate_performance_score(gantt_data),
                    'bottlenecks_identified': self._identify_bottlenecks(gantt_data),
                    'optimization_recommendations': self._generate_optimization_recommendations(gantt_data)
                }
            }

            analysis_data_path = os.path.join(analysis_dir, f"analysis_data_{timestamp}.json")
            with open(analysis_data_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ 分析层甘特图生成完成: {len(generated_charts)} 个图表")
            return generated_charts

        except Exception as e:
            logger.error(f"❌ 生成分析层甘特图失败: {e}")
            return {}

    def generate_complete_hierarchical_gantts(
        self,
        gantt_data: Dict[str, Any],
        mission_id: str = None
    ) -> Dict[str, Any]:
        """生成完整的分层甘特图"""
        try:
            logger.info("🎨 开始生成完整分层甘特图...")

            # 创建仿真会话
            session_dir = self.create_simulation_session(mission_id)

            # 生成各层甘特图
            results = {
                'session_dir': session_dir,
                'mission_id': mission_id or f"SIMULATION_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'generation_time': datetime.now().isoformat(),
                'layers': {}
            }

            # 战略层
            strategic_charts = self.generate_strategic_layer_gantts(session_dir, gantt_data)
            results['layers']['strategic'] = strategic_charts

            # 战术层
            tactical_charts = self.generate_tactical_layer_gantts(session_dir, gantt_data)
            results['layers']['tactical'] = tactical_charts

            # 执行层
            execution_charts = self.generate_execution_layer_gantts(session_dir, gantt_data)
            results['layers']['execution'] = execution_charts

            # 分析层
            analysis_charts = self.generate_analysis_layer_gantts(session_dir, gantt_data)
            results['layers']['analysis'] = analysis_charts

            # 保存原始任务数据
            data_dir = os.path.join(session_dir, "data")
            mission_data_path = os.path.join(data_dir, f"mission_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(mission_data_path, 'w', encoding='utf-8') as f:
                json.dump(gantt_data, f, indent=2, ensure_ascii=False)

            # 生成性能指标
            performance_metrics = self._generate_performance_metrics(gantt_data, results)
            performance_path = os.path.join(data_dir, f"performance_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            with open(performance_path, 'w', encoding='utf-8') as f:
                json.dump(performance_metrics, f, indent=2, ensure_ascii=False)

            # 生成会话总结报告
            session_summary = self._generate_session_summary(results, performance_metrics)
            summary_path = os.path.join(session_dir, "session_summary.json")
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(session_summary, f, indent=2, ensure_ascii=False)

            # 生成HTML索引页面
            index_path = self._generate_hierarchical_index(session_dir, results)
            results['index_page'] = index_path

            # 更新会话元数据
            self._update_session_metadata(session_dir, results)

            total_charts = sum(len(layer_charts) for layer_charts in results['layers'].values())
            logger.info(f"✅ 完整分层甘特图生成完成: {total_charts} 个图表，4个层次")

            return results

        except Exception as e:
            logger.error(f"❌ 生成完整分层甘特图失败: {e}")
            return {}

    def _calculate_task_distribution(self, gantt_data: Dict[str, Any]) -> Dict[str, Any]:
        """计算任务分布"""
        tasks = gantt_data.get('tasks', [])
        satellites = gantt_data.get('satellites', [])

        distribution = {}
        for satellite in satellites:
            satellite_tasks = [t for t in tasks if t.get('assigned_satellite') == satellite]
            distribution[satellite] = {
                'task_count': len(satellite_tasks),
                'avg_threat_level': sum(t.get('threat_level', 0) for t in satellite_tasks) / len(satellite_tasks) if satellite_tasks else 0,
                'total_duration': sum(t.get('duration_minutes', 0) for t in satellite_tasks)
            }

        return distribution

    def _calculate_resource_efficiency(self, gantt_data: Dict[str, Any]) -> Dict[str, float]:
        """计算资源效率"""
        tasks = gantt_data.get('tasks', [])

        if not tasks:
            return {'power': 0.0, 'storage': 0.0, 'communication': 0.0}

        total_resources = {'power': 0.0, 'storage': 0.0, 'communication': 0.0}
        for task in tasks:
            resources = task.get('resource_requirements', {})
            for resource_type in total_resources:
                total_resources[resource_type] += resources.get(resource_type, 0.0)

        # 计算平均效率
        task_count = len(tasks)
        return {k: v / task_count for k, v in total_resources.items()}

    def _calculate_coverage_redundancy(self, gantt_data: Dict[str, Any]) -> Dict[str, int]:
        """计算覆盖冗余度"""
        tasks = gantt_data.get('tasks', [])
        missiles = gantt_data.get('missiles', [])

        coverage = {}
        for missile in missiles:
            missile_tasks = [t for t in tasks if t.get('target_missile') == missile]
            coverage[missile] = len(missile_tasks)

        return coverage

    def _calculate_completion_rate(self, gantt_data: Dict[str, Any]) -> float:
        """计算任务完成率"""
        tasks = gantt_data.get('tasks', [])
        if not tasks:
            return 0.0

        completed_tasks = sum(1 for t in tasks if t.get('status') == 'completed')
        return completed_tasks / len(tasks)

    def _calculate_communication_efficiency(self, gantt_data: Dict[str, Any]) -> float:
        """计算通信效率"""
        tasks = gantt_data.get('tasks', [])
        if not tasks:
            return 0.0

        total_comm = sum(t.get('resource_requirements', {}).get('communication', 0.0) for t in tasks)
        return total_comm / len(tasks)

    def _calculate_realtime_performance(self, gantt_data: Dict[str, Any]) -> Dict[str, float]:
        """计算实时性能"""
        tasks = gantt_data.get('tasks', [])

        if not tasks:
            return {'response_time': 0.0, 'processing_speed': 0.0, 'data_throughput': 0.0}

        # 模拟实时性能指标
        avg_duration = sum(t.get('duration_minutes', 0) for t in tasks) / len(tasks)
        avg_threat = sum(t.get('threat_level', 0) for t in tasks) / len(tasks)

        return {
            'response_time': max(0.1, 1.0 / avg_threat),  # 威胁越高响应越快
            'processing_speed': min(1.0, avg_threat / 5.0),  # 基于威胁等级
            'data_throughput': min(1.0, 30.0 / avg_duration)  # 基于任务持续时间
        }

    def _calculate_performance_score(self, gantt_data: Dict[str, Any]) -> float:
        """计算综合性能评分"""
        tasks = gantt_data.get('tasks', [])
        if not tasks:
            return 0.0

        # 基于多个因素计算综合评分
        completion_rate = self._calculate_completion_rate(gantt_data)
        resource_efficiency = self._calculate_resource_efficiency(gantt_data)
        coverage_redundancy = self._calculate_coverage_redundancy(gantt_data)

        # 加权计算
        efficiency_score = sum(resource_efficiency.values()) / len(resource_efficiency)
        redundancy_score = min(1.0, sum(coverage_redundancy.values()) / len(coverage_redundancy) / 2.0)

        performance_score = (completion_rate * 0.4 + efficiency_score * 0.4 + redundancy_score * 0.2)
        return min(1.0, performance_score)

    def _identify_bottlenecks(self, gantt_data: Dict[str, Any]) -> List[str]:
        """识别系统瓶颈"""
        bottlenecks = []

        # 检查资源瓶颈
        resource_efficiency = self._calculate_resource_efficiency(gantt_data)
        for resource, efficiency in resource_efficiency.items():
            if efficiency > 0.8:
                bottlenecks.append(f"高{resource}资源使用率 ({efficiency:.2f})")

        # 检查任务分布瓶颈
        task_distribution = self._calculate_task_distribution(gantt_data)
        task_counts = [dist['task_count'] for dist in task_distribution.values()]
        if task_counts and max(task_counts) - min(task_counts) > 2:
            bottlenecks.append("任务分配不均衡")

        # 检查覆盖瓶颈
        coverage_redundancy = self._calculate_coverage_redundancy(gantt_data)
        single_coverage = sum(1 for count in coverage_redundancy.values() if count == 1)
        if single_coverage > len(coverage_redundancy) * 0.3:
            bottlenecks.append("覆盖冗余度不足")

        return bottlenecks if bottlenecks else ["未发现明显瓶颈"]

    def _generate_optimization_recommendations(self, gantt_data: Dict[str, Any]) -> List[str]:
        """生成优化建议"""
        recommendations = []

        # 基于瓶颈分析生成建议
        bottlenecks = self._identify_bottlenecks(gantt_data)

        for bottleneck in bottlenecks:
            if "资源使用率" in bottleneck:
                recommendations.append("建议优化资源分配策略，降低峰值使用率")
            elif "任务分配不均衡" in bottleneck:
                recommendations.append("建议重新平衡卫星任务分配")
            elif "覆盖冗余度不足" in bottleneck:
                recommendations.append("建议为高威胁目标增加观测卫星")

        # 基于性能评分生成建议
        performance_score = self._calculate_performance_score(gantt_data)
        if performance_score < 0.7:
            recommendations.append("建议全面优化系统配置以提升整体性能")
        elif performance_score < 0.85:
            recommendations.append("建议针对性优化关键性能指标")

        return recommendations if recommendations else ["当前配置已较为优化"]

    def _generate_performance_metrics(self, gantt_data: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """生成性能指标"""
        return {
            'generation_time': datetime.now().isoformat(),
            'mission_metrics': {
                'total_tasks': len(gantt_data.get('tasks', [])),
                'total_satellites': len(gantt_data.get('satellites', [])),
                'total_missiles': len(gantt_data.get('missiles', [])),
                'mission_duration_minutes': max([t.get('duration_minutes', 0) for t in gantt_data.get('tasks', [])], default=0)
            },
            'performance_scores': {
                'overall_performance': self._calculate_performance_score(gantt_data),
                'resource_efficiency': self._calculate_resource_efficiency(gantt_data),
                'completion_rate': self._calculate_completion_rate(gantt_data),
                'communication_efficiency': self._calculate_communication_efficiency(gantt_data)
            },
            'system_analysis': {
                'bottlenecks': self._identify_bottlenecks(gantt_data),
                'recommendations': self._generate_optimization_recommendations(gantt_data),
                'coverage_redundancy': self._calculate_coverage_redundancy(gantt_data)
            },
            'chart_statistics': {
                'total_charts_generated': sum(len(layer) for layer in results['layers'].values()),
                'layers_completed': len(results['layers']),
                'generation_success_rate': 1.0  # 假设全部成功
            }
        }

    def _generate_session_summary(self, results: Dict[str, Any], performance_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """生成会话总结"""
        return {
            'session_info': {
                'session_id': results['mission_id'],
                'generation_time': results['generation_time'],
                'session_directory': results['session_dir']
            },
            'layer_summary': {
                layer: {
                    'charts_generated': len(charts),
                    'chart_types': list(charts.keys())
                }
                for layer, charts in results['layers'].items()
            },
            'performance_summary': performance_metrics['performance_scores'],
            'key_insights': {
                'primary_bottlenecks': performance_metrics['system_analysis']['bottlenecks'][:3],
                'top_recommendations': performance_metrics['system_analysis']['recommendations'][:3],
                'overall_assessment': self._generate_overall_assessment(performance_metrics)
            }
        }

    def _generate_overall_assessment(self, performance_metrics: Dict[str, Any]) -> str:
        """生成总体评估"""
        overall_score = performance_metrics['performance_scores']['overall_performance']

        if overall_score >= 0.9:
            return "系统性能优秀，配置高度优化"
        elif overall_score >= 0.8:
            return "系统性能良好，存在小幅优化空间"
        elif overall_score >= 0.7:
            return "系统性能中等，建议进行针对性优化"
        elif overall_score >= 0.6:
            return "系统性能偏低，需要重点优化"
        else:
            return "系统性能较差，需要全面重新设计"

    def _generate_hierarchical_index(self, session_dir: str, results: Dict[str, Any]) -> str:
        """生成分层甘特图HTML索引页面"""
        try:
            mission_id = results['mission_id']
            generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>分层甘特图分析报告 - {mission_id}</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
        }}
        .header p {{
            margin: 10px 0 0 0;
            opacity: 0.9;
            font-size: 1.1em;
        }}
        .nav-tabs {{
            display: flex;
            background-color: #ecf0f1;
            border-bottom: 3px solid #3498db;
        }}
        .nav-tab {{
            flex: 1;
            padding: 15px;
            text-align: center;
            background-color: #bdc3c7;
            color: #2c3e50;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: bold;
            border: none;
            font-size: 1em;
        }}
        .nav-tab:hover {{
            background-color: #95a5a6;
        }}
        .nav-tab.active {{
            background-color: #3498db;
            color: white;
        }}
        .layer-content {{
            display: none;
            padding: 30px;
        }}
        .layer-content.active {{
            display: block;
        }}
        .layer-header {{
            border-bottom: 2px solid #3498db;
            padding-bottom: 15px;
            margin-bottom: 25px;
        }}
        .layer-title {{
            color: #2c3e50;
            font-size: 2em;
            margin: 0;
        }}
        .layer-description {{
            color: #7f8c8d;
            margin: 5px 0 0 0;
            font-size: 1.1em;
        }}
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 25px;
            margin: 25px 0;
        }}
        .chart-card {{
            background: white;
            border: 1px solid #ddd;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}
        .chart-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.15);
        }}
        .chart-title {{
            font-size: 1.3em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }}
        .chart-links {{
            margin-top: 15px;
        }}
        .chart-link {{
            display: inline-block;
            margin: 5px 10px 5px 0;
            padding: 8px 15px;
            background-color: #3498db;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 0.9em;
            transition: background-color 0.3s ease;
        }}
        .chart-link:hover {{
            background-color: #2980b9;
        }}
        .chart-link.html {{
            background-color: #e74c3c;
        }}
        .chart-link.html:hover {{
            background-color: #c0392b;
        }}
        .summary-section {{
            background-color: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin: 25px 0;
        }}
        .summary-title {{
            color: #2c3e50;
            font-size: 1.4em;
            margin-bottom: 15px;
            font-weight: bold;
        }}
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        .metric-item {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border-left: 4px solid #3498db;
        }}
        .metric-value {{
            font-size: 1.8em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .metric-label {{
            color: #7f8c8d;
            font-size: 0.9em;
            margin-top: 5px;
        }}
        .footer {{
            background-color: #34495e;
            color: white;
            text-align: center;
            padding: 20px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>现实预警星座分层甘特图分析</h1>
            <p>任务ID: {mission_id} | 生成时间: {generation_time}</p>
        </div>

        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showLayer('strategic')">战略层</button>
            <button class="nav-tab" onclick="showLayer('tactical')">战术层</button>
            <button class="nav-tab" onclick="showLayer('execution')">执行层</button>
            <button class="nav-tab" onclick="showLayer('analysis')">分析层</button>
        </div>
"""

            # 添加各层内容
            layer_descriptions = {
                'strategic': {
                    'title': '战略层甘特图',
                    'description': '全局任务规划和威胁态势演进分析',
                    'charts': {
                        'mission_overview': '任务概览甘特图',
                        'threat_evolution': '威胁态势演进图',
                        'global_timeline': '全局时间线图'
                    }
                },
                'tactical': {
                    'title': '战术层甘特图',
                    'description': '任务分配、可见性窗口和资源利用分析',
                    'charts': {
                        'task_allocation': '任务分配甘特图',
                        'visibility_windows': '可见性窗口图',
                        'resource_utilization': '资源利用率图'
                    }
                },
                'execution': {
                    'title': '执行层甘特图',
                    'description': '单卫星详细任务和协商过程分析',
                    'charts': {
                        'satellite_detailed': '单卫星详细任务图',
                        'negotiation_process': '协商过程图',
                        'realtime_status': '实时状态监控图'
                    }
                },
                'analysis': {
                    'title': '分析层甘特图',
                    'description': '性能对比和瓶颈分析',
                    'charts': {
                        'performance_comparison': '性能对比分析图',
                        'bottleneck_analysis': '瓶颈分析图',
                        'optimization_suggestions': '优化建议图'
                    }
                }
            }

            for layer_name, layer_info in layer_descriptions.items():
                is_active = "active" if layer_name == 'strategic' else ""
                html_content += f"""
        <div id="{layer_name}" class="layer-content {is_active}">
            <div class="layer-header">
                <h2 class="layer-title">{layer_info['title']}</h2>
                <p class="layer-description">{layer_info['description']}</p>
            </div>

            <div class="charts-grid">
"""

                # 添加该层的图表卡片
                layer_charts = results['layers'].get(layer_name, {})
                for chart_type, chart_name in layer_info['charts'].items():
                    chart_path = layer_charts.get(chart_type, '')
                    if chart_path:
                        chart_filename = os.path.basename(chart_path)
                        chart_base = chart_filename.rsplit('.', 1)[0]

                        html_content += f"""
                <div class="chart-card">
                    <div class="chart-title">{chart_name}</div>
                    <p>文件: {chart_filename}</p>
                    <div class="chart-links">
"""

                        # 添加不同格式的链接
                        possible_extensions = ['.png', '.svg', '.pdf', '.html', '.json']
                        for ext in possible_extensions:
                            possible_file = f"{chart_base}{ext}"
                            possible_path = os.path.join(os.path.dirname(chart_path), possible_file)
                            if os.path.exists(possible_path):
                                link_class = "html" if ext == '.html' else ""
                                html_content += f'<a href="{possible_file}" class="chart-link {link_class}" target="_blank">{ext.upper()[1:]}</a>'

                        html_content += """
                    </div>
                </div>
"""

                html_content += """
            </div>
        </div>
"""

            # 添加JavaScript和结束标签
            html_content += """
        <div class="footer">
            <p>现实预警星座分层甘特图分析系统 © 2025</p>
        </div>
    </div>

    <script>
        function showLayer(layerName) {
            // 隐藏所有层内容
            const contents = document.querySelectorAll('.layer-content');
            contents.forEach(content => content.classList.remove('active'));

            // 移除所有标签的active状态
            const tabs = document.querySelectorAll('.nav-tab');
            tabs.forEach(tab => tab.classList.remove('active'));

            // 显示选中的层
            document.getElementById(layerName).classList.add('active');

            // 激活对应的标签
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
"""

            index_path = os.path.join(session_dir, "hierarchical_index.html")
            with open(index_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"✅ 分层甘特图HTML索引页面已生成: {index_path}")
            return index_path

        except Exception as e:
            logger.error(f"❌ 生成分层甘特图HTML索引页面失败: {e}")
            return ""

    def _update_session_metadata(self, session_dir: str, results: Dict[str, Any]):
        """更新会话元数据"""
        try:
            metadata_path = os.path.join(session_dir, "session_metadata.json")

            # 读取现有元数据
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 更新元数据
            metadata.update({
                'completion_time': datetime.now().isoformat(),
                'status': 'completed',
                'total_charts_generated': sum(len(layer) for layer in results['layers'].values()),
                'layers_completed': list(results['layers'].keys()),
                'index_page': results.get('index_page', ''),
                'generation_success': True
            })

            # 保存更新的元数据
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ 更新会话元数据失败: {e}")

    def archive_session(self, session_dir: str):
        """归档会话到历史目录"""
        try:
            current_date = datetime.now()
            archive_base = os.path.join(
                self.layer_dirs['archives'],
                str(current_date.year),
                f"{current_date.month:02d}",
                f"{current_date.day:02d}"
            )
            os.makedirs(archive_base, exist_ok=True)

            session_name = os.path.basename(session_dir)
            archive_path = os.path.join(archive_base, session_name)

            # 复制会话目录到归档位置
            shutil.copytree(session_dir, archive_path, dirs_exist_ok=True)

            logger.info(f"✅ 会话已归档: {archive_path}")
            return archive_path

        except Exception as e:
            logger.error(f"❌ 归档会话失败: {e}")
            return ""
