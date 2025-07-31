"""
甘特图集成管理器
负责在现实预警星座系统中自动生成和管理甘特图
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import json

from .realistic_constellation_gantt import (
    RealisticConstellationGanttGenerator,
    ConstellationGanttData,
    ConstellationGanttTask
)

logger = logging.getLogger(__name__)

class ConstellationGanttIntegrationManager:
    """星座甘特图集成管理器"""
    
    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self.gantt_generator = RealisticConstellationGanttGenerator(config_manager)
        
        # 甘特图保存配置
        self.save_config = {
            'base_path': 'reports/gantt',
            'formats': ['png', 'svg', 'json'],
            'auto_save': True,
            'archive_old': True
        }
        
        # 确保目录存在
        self._ensure_directories()
        
        logger.info("✅ 星座甘特图集成管理器初始化完成")
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            'reports/gantt/strategic',
            'reports/gantt/tactical', 
            'reports/gantt/execution',
            'reports/gantt/analysis',
            'reports/gantt/archives',
            'reports/data'
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    async def generate_mission_gantts(
        self,
        mission_data: Dict[str, Any],
        gantt_types: List[str] = None
    ) -> Dict[str, str]:
        """为任务生成所有相关的甘特图"""
        try:
            logger.info("🎨 开始生成任务甘特图集合...")
            
            if gantt_types is None:
                gantt_types = ['task_allocation', 'resource_utilization', 'mission_overview']
            
            # 准备甘特图数据
            gantt_data = self.gantt_generator.prepare_gantt_data_from_mission(mission_data)
            
            generated_charts = {}
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # 1. 生成任务分配甘特图
            if 'task_allocation' in gantt_types:
                task_path = f"reports/gantt/tactical/task_allocation_{timestamp}.png"
                generated_charts['task_allocation'] = await self._generate_task_allocation_chart(
                    gantt_data, task_path
                )
            
            # 2. 生成资源利用率甘特图
            if 'resource_utilization' in gantt_types:
                resource_path = f"reports/gantt/tactical/resource_utilization_{timestamp}.png"
                generated_charts['resource_utilization'] = await self._generate_resource_chart(
                    gantt_data, resource_path
                )
            
            # 3. 生成任务概览甘特图
            if 'mission_overview' in gantt_types:
                overview_path = f"reports/gantt/strategic/mission_overview_{timestamp}.png"
                generated_charts['mission_overview'] = await self._generate_overview_chart(
                    gantt_data, overview_path
                )
            
            # 4. 保存原始数据
            data_path = f"reports/data/mission_data_{timestamp}.json"
            generated_charts['data'] = self.gantt_generator.save_gantt_data_json(gantt_data, data_path)
            
            # 5. 生成甘特图索引
            index_data = {
                'mission_id': mission_data.get('mission_id', f'MISSION_{timestamp}'),
                'generation_time': datetime.now().isoformat(),
                'charts': generated_charts,
                'metadata': {
                    'total_tasks': len(gantt_data.tasks),
                    'total_satellites': len(gantt_data.satellites),
                    'total_missiles': len(gantt_data.missiles),
                    'mission_duration': gantt_data.performance_metrics.get('mission_duration', 0)
                }
            }
            
            index_path = f"reports/gantt/mission_gantt_index_{timestamp}.json"
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, indent=2, ensure_ascii=False, default=str)
            
            generated_charts['index'] = index_path
            
            logger.info(f"✅ 任务甘特图生成完成，共生成 {len(generated_charts)} 个文件")
            return generated_charts
            
        except Exception as e:
            logger.error(f"❌ 生成任务甘特图失败: {e}")
            raise
    
    async def _generate_task_allocation_chart(self, gantt_data: ConstellationGanttData, save_path: str) -> str:
        """生成任务分配甘特图"""
        try:
            return self.gantt_generator.generate_constellation_task_gantt(gantt_data, save_path)
        except Exception as e:
            logger.error(f"❌ 生成任务分配甘特图失败: {e}")
            raise
    
    async def _generate_resource_chart(self, gantt_data: ConstellationGanttData, save_path: str) -> str:
        """生成资源利用率甘特图"""
        try:
            return self.gantt_generator.generate_resource_utilization_gantt(gantt_data, save_path)
        except Exception as e:
            logger.error(f"❌ 生成资源利用率甘特图失败: {e}")
            raise
    
    async def _generate_overview_chart(self, gantt_data: ConstellationGanttData, save_path: str) -> str:
        """生成任务概览甘特图"""
        try:
            # 这里可以实现一个简化版的概览图
            # 暂时使用任务分配图作为概览
            return self.gantt_generator.generate_constellation_task_gantt(gantt_data, save_path)
        except Exception as e:
            logger.error(f"❌ 生成任务概览甘特图失败: {e}")
            raise
    
    def create_mission_data_from_realistic_scenario(
        self,
        missile_scenario: List[Dict[str, Any]],
        task_assignments: Dict[str, List[str]],
        satellite_list: List[str]
    ) -> Dict[str, Any]:
        """从现实场景数据创建任务数据"""
        try:
            mission_data = {
                'mission_id': f'REALISTIC_MISSION_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'scenario_name': '现实预警星座导弹跟踪任务',
                'missiles': missile_scenario,
                'satellites': [{'satellite_id': sat_id} for sat_id in satellite_list],
                'task_assignments': task_assignments,
                'metadata': {
                    'generation_time': datetime.now().isoformat(),
                    'scenario_type': 'realistic_constellation',
                    'total_missiles': len(missile_scenario),
                    'total_satellites': len(satellite_list),
                    'total_assignments': sum(len(assignments) for assignments in task_assignments.values())
                }
            }
            
            return mission_data
            
        except Exception as e:
            logger.error(f"❌ 创建任务数据失败: {e}")
            raise
    
    async def auto_generate_from_scheduler_result(
        self,
        scheduler_result: str,
        missile_scenario: List[Dict[str, Any]],
        satellite_list: List[str]
    ) -> Optional[Dict[str, str]]:
        """从调度器结果自动生成甘特图"""
        try:
            logger.info("🎨 从调度器结果自动生成甘特图...")
            
            # 解析调度器结果，提取任务分配信息
            task_assignments = self._parse_scheduler_result(scheduler_result, satellite_list)
            
            if not task_assignments:
                logger.warning("⚠️ 未能从调度器结果中提取任务分配信息")
                return None
            
            # 创建任务数据
            mission_data = self.create_mission_data_from_realistic_scenario(
                missile_scenario, task_assignments, satellite_list
            )
            
            # 生成甘特图
            generated_charts = await self.generate_mission_gantts(mission_data)
            
            logger.info(f"✅ 自动甘特图生成完成: {len(generated_charts)} 个文件")
            return generated_charts
            
        except Exception as e:
            logger.error(f"❌ 自动生成甘特图失败: {e}")
            return None
    
    def _parse_scheduler_result(
        self,
        scheduler_result: str,
        satellite_list: List[str]
    ) -> Dict[str, List[str]]:
        """解析调度器结果，提取任务分配信息"""
        try:
            # 简化的解析逻辑 - 实际实现需要根据具体的结果格式调整
            task_assignments = {}
            
            # 如果调度成功，为每颗卫星分配一些任务（模拟）
            if "成功" in scheduler_result or "Success" in scheduler_result:
                # 模拟任务分配 - 实际应该从真实的调度结果中解析
                for i, satellite_id in enumerate(satellite_list[:4]):  # 只使用前4颗卫星
                    task_assignments[satellite_id] = [f'DEMO_MISSILE_{(i % 3) + 1:03d}']
            
            return task_assignments
            
        except Exception as e:
            logger.error(f"❌ 解析调度器结果失败: {e}")
            return {}
    
    def get_latest_gantt_charts(self) -> Dict[str, str]:
        """获取最新生成的甘特图文件路径"""
        try:
            gantt_files = {}
            
            # 查找最新的甘特图文件
            for chart_type in ['task_allocation', 'resource_utilization', 'mission_overview']:
                pattern_path = f"reports/gantt/tactical/{chart_type}_*.png"
                # 这里应该实现文件查找逻辑，返回最新的文件
                # 简化实现
                gantt_files[chart_type] = pattern_path
            
            return gantt_files
            
        except Exception as e:
            logger.error(f"❌ 获取最新甘特图失败: {e}")
            return {}
    
    def cleanup_old_charts(self, days_to_keep: int = 7):
        """清理旧的甘特图文件"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # 遍历甘特图目录
            for root, dirs, files in os.walk('reports/gantt'):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # 检查文件修改时间
                    if os.path.getmtime(file_path) < cutoff_date.timestamp():
                        # 移动到归档目录而不是删除
                        archive_path = file_path.replace('reports/gantt', 'reports/gantt/archives')
                        os.makedirs(os.path.dirname(archive_path), exist_ok=True)
                        os.rename(file_path, archive_path)
                        logger.info(f"📁 归档旧甘特图: {file}")
            
            logger.info(f"✅ 甘特图清理完成，保留 {days_to_keep} 天内的文件")
            
        except Exception as e:
            logger.error(f"❌ 清理甘特图失败: {e}")
    
    def generate_gantt_summary_report(self) -> Dict[str, Any]:
        """生成甘特图汇总报告"""
        try:
            summary = {
                'total_charts_generated': 0,
                'chart_types': {},
                'latest_generation_time': None,
                'storage_usage': 0
            }
            
            # 统计甘特图文件
            for root, dirs, files in os.walk('reports/gantt'):
                for file in files:
                    if file.endswith(('.png', '.svg', '.json')):
                        summary['total_charts_generated'] += 1
                        
                        # 统计文件大小
                        file_path = os.path.join(root, file)
                        summary['storage_usage'] += os.path.getsize(file_path)
                        
                        # 提取图表类型
                        if 'task_allocation' in file:
                            summary['chart_types']['task_allocation'] = summary['chart_types'].get('task_allocation', 0) + 1
                        elif 'resource_utilization' in file:
                            summary['chart_types']['resource_utilization'] = summary['chart_types'].get('resource_utilization', 0) + 1
                        elif 'mission_overview' in file:
                            summary['chart_types']['mission_overview'] = summary['chart_types'].get('mission_overview', 0) + 1
            
            # 转换存储大小为MB
            summary['storage_usage_mb'] = summary['storage_usage'] / (1024 * 1024)
            
            logger.info(f"📊 甘特图汇总: {summary['total_charts_generated']} 个文件，{summary['storage_usage_mb']:.2f} MB")
            return summary
            
        except Exception as e:
            logger.error(f"❌ 生成甘特图汇总报告失败: {e}")
            return {}

# 甘特图集成管理器的使用示例
async def demo_gantt_integration():
    """演示甘特图集成功能"""
    try:
        logger.info("🎨 开始甘特图集成演示...")

        # 创建管理器
        gantt_manager = ConstellationGanttIntegrationManager()

        # 模拟任务数据
        demo_mission_data = {
            'mission_id': 'DEMO_GANTT_MISSION',
            'scenario_name': '甘特图演示场景',
            'missiles': [
                {
                    'missile_id': 'DEMO_MISSILE_001',
                    'threat_level': 5,
                    'priority_level': 5,
                    'launch_time': datetime.now().isoformat()
                },
                {
                    'missile_id': 'DEMO_MISSILE_002',
                    'threat_level': 4,
                    'priority_level': 4,
                    'launch_time': (datetime.now() + timedelta(minutes=5)).isoformat()
                }
            ],
            'satellites': [
                {'satellite_id': 'SAT_001'},
                {'satellite_id': 'SAT_002'},
                {'satellite_id': 'SAT_003'}
            ],
            'task_assignments': {
                'SAT_001': ['DEMO_MISSILE_001'],
                'SAT_002': ['DEMO_MISSILE_002'],
                'SAT_003': ['DEMO_MISSILE_001', 'DEMO_MISSILE_002']
            }
        }

        # 生成甘特图
        generated_charts = await gantt_manager.generate_mission_gantts(demo_mission_data)

        logger.info("✅ 甘特图集成演示完成")
        logger.info(f"生成的图表: {list(generated_charts.keys())}")

        return generated_charts

    except Exception as e:
        logger.error(f"❌ 甘特图集成演示失败: {e}")
        return None
