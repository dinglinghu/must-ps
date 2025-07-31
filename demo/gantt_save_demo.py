"""
甘特图保存功能演示
展示甘特图保存系统的各种功能和用法
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.visualization.gantt_save_service import get_gantt_save_service
from src.visualization.realistic_constellation_gantt import (
    ConstellationGanttData, ConstellationGanttTask
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_demo_gantt_data() -> ConstellationGanttData:
    """创建演示甘特图数据"""
    logger.info("🎨 创建演示甘特图数据...")
    
    start_time = datetime.now()
    
    # 创建任务列表
    tasks = []
    
    # 任务1: 卫星SAT_001跟踪导弹MISSILE_001
    task1 = ConstellationGanttTask(
        task_id="TASK_001",
        task_name="SAT_001跟踪MISSILE_001",
        start_time=start_time,
        end_time=start_time + timedelta(minutes=30),
        category="observation",
        priority=5,
        threat_level=4,
        assigned_satellite="SAT_001",
        target_missile="MISSILE_001",
        execution_status="planned",
        quality_score=0.9,
        resource_utilization={"cpu": 0.8, "memory": 0.6, "power": 0.7}
    )
    tasks.append(task1)
    
    # 任务2: 卫星SAT_002跟踪导弹MISSILE_002
    task2 = ConstellationGanttTask(
        task_id="TASK_002",
        task_name="SAT_002跟踪MISSILE_002",
        start_time=start_time + timedelta(minutes=10),
        end_time=start_time + timedelta(minutes=45),
        category="observation",
        priority=4,
        threat_level=3,
        assigned_satellite="SAT_002",
        target_missile="MISSILE_002",
        execution_status="planned",
        quality_score=0.85,
        resource_utilization={"cpu": 0.7, "memory": 0.5, "power": 0.6}
    )
    tasks.append(task2)
    
    # 任务3: 数据处理任务
    task3 = ConstellationGanttTask(
        task_id="TASK_003",
        task_name="数据处理与分析",
        start_time=start_time + timedelta(minutes=20),
        end_time=start_time + timedelta(minutes=50),
        category="processing",
        priority=3,
        threat_level=2,
        assigned_satellite="GROUND_STATION",
        target_missile="ALL",
        execution_status="planned",
        quality_score=0.95,
        resource_utilization={"cpu": 0.9, "memory": 0.8, "power": 0.4}
    )
    tasks.append(task3)
    
    # 创建甘特图数据
    gantt_data = ConstellationGanttData(
        chart_id="DEMO_CHART_001",
        chart_type="mission_overview",
        creation_time=datetime.now(),
        mission_scenario="演示导弹跟踪任务",
        start_time=start_time,
        end_time=start_time + timedelta(hours=1),
        tasks=tasks,
        satellites=["SAT_001", "SAT_002", "GROUND_STATION"],
        missiles=["MISSILE_001", "MISSILE_002"],
        metadata={
            "demo_version": "1.0",
            "created_by": "甘特图保存演示",
            "scenario_type": "multi_target_tracking"
        },
        performance_metrics={
            "total_coverage": 0.85,
            "resource_efficiency": 0.78,
            "mission_success_rate": 0.92
        }
    )
    
    logger.info(f"✅ 创建了包含 {len(tasks)} 个任务的甘特图数据")
    return gantt_data

async def demo_save_functionality():
    """演示保存功能"""
    logger.info("💾 演示甘特图保存功能...")
    
    # 获取保存服务
    save_service = get_gantt_save_service()
    
    # 创建演示数据
    gantt_data = create_demo_gantt_data()
    
    # 定义进度回调函数
    def on_progress(task_id: str, progress: float, message: str):
        logger.info(f"📊 任务 {task_id[:8]}... 进度: {progress:.1f}% - {message}")
    
    def on_complete(task_id: str, save_path: str):
        logger.info(f"✅ 任务 {task_id[:8]}... 完成: {save_path}")
    
    def on_error(task_id: str, error_message: str):
        logger.error(f"❌ 任务 {task_id[:8]}... 失败: {error_message}")
    
    # 保存多种格式（包括所有支持的格式）
    result = await save_service.save_gantt_chart(
        gantt_data=gantt_data,
        chart_type="mission_overview",
        mission_id="DEMO_MISSION_001",
        formats=["json", "png", "svg", "html", "xlsx"],  # 测试所有格式
        category="demo",
        options={"quality": "high", "interactive": True},
        on_progress=on_progress,
        on_complete=on_complete,
        on_error=on_error
    )
    
    if result['success']:
        logger.info(f"📝 提交了 {len(result['task_ids'])} 个保存任务")
        
        # 等待保存完成
        task_ids = result['task_ids']
        max_wait_time = 30  # 最大等待30秒
        wait_time = 0
        
        while wait_time < max_wait_time:
            progress_info = save_service.get_save_progress(task_ids)
            
            if progress_info['success']:
                logger.info(f"📊 总体进度: {progress_info['overall_progress']:.1f}% "
                          f"({progress_info['completed_count']}/{progress_info['total_count']})")
                
                if progress_info['completed_count'] == progress_info['total_count']:
                    logger.info("✅ 所有保存任务已完成")
                    break
            
            await asyncio.sleep(1)
            wait_time += 1
        
        return result['task_ids']
    else:
        logger.error(f"❌ 保存任务提交失败: {result.get('error')}")
        return []

async def demo_search_functionality():
    """演示搜索功能"""
    logger.info("🔍 演示甘特图搜索功能...")
    
    save_service = get_gantt_save_service()
    
    # 搜索所有甘特图
    search_params = {}
    result = save_service.search_gantt_charts(search_params)
    
    if result['success']:
        logger.info(f"📋 找到 {result['total_count']} 个甘特图文件")
        
        for file_info in result['files'][:5]:  # 只显示前5个
            logger.info(f"  📄 {file_info['file_name']} "
                       f"({file_info['format']}, {file_info['file_size']} bytes)")
    
    # 按类型搜索
    search_params = {'chart_type': 'mission_overview'}
    result = save_service.search_gantt_charts(search_params)
    
    if result['success']:
        logger.info(f"🎯 找到 {result['total_count']} 个任务概览甘特图")

async def demo_load_functionality():
    """演示加载功能"""
    logger.info("📂 演示甘特图加载功能...")
    
    save_service = get_gantt_save_service()
    
    # 搜索JSON格式的文件（只有JSON格式可以加载数据）
    search_params = {'chart_type': 'mission_overview', 'format': 'json'}
    result = save_service.search_gantt_charts(search_params)

    if result['success'] and result['files']:
        # 加载第一个JSON文件
        file_info = result['files'][0]
        file_id = file_info['file_id']

        logger.info(f"📖 加载文件: {file_info['file_name']}")

        load_result = save_service.load_gantt_chart(file_id)

        if load_result['success']:
            gantt_data = load_result['gantt_data']
            logger.info(f"✅ 成功加载甘特图: {gantt_data.chart_id}")
            logger.info(f"  📊 包含 {len(gantt_data.tasks)} 个任务")
            logger.info(f"  🛰️ 涉及 {len(gantt_data.satellites)} 颗卫星")
            logger.info(f"  🚀 跟踪 {len(gantt_data.missiles)} 枚导弹")
        else:
            logger.error(f"❌ 加载失败: {load_result.get('error')}")
    else:
        logger.warning("⚠️ 没有找到可加载的JSON文件")

async def demo_statistics():
    """演示统计功能"""
    logger.info("📊 演示统计信息功能...")
    
    save_service = get_gantt_save_service()
    
    result = save_service.get_statistics()
    
    if result['success']:
        file_stats = result['file_statistics']
        save_stats = result['save_statistics']
        state_stats = result['state_statistics']
        
        logger.info("📈 文件统计:")
        logger.info(f"  总文件数: {file_stats.get('total_files', 0)}")
        logger.info(f"  总大小: {file_stats.get('total_size_mb', 0):.2f} MB")
        
        logger.info("💾 保存统计:")
        logger.info(f"  总保存次数: {save_stats.get('total_saves', 0)}")
        logger.info(f"  成功率: {save_stats.get('success_rate', 0):.2%}")
        
        logger.info("⚡ 状态统计:")
        logger.info(f"  总任务数: {state_stats.get('total_tasks', 0)}")
        logger.info(f"  完成任务数: {state_stats.get('completed_tasks', 0)}")
        logger.info(f"  平均保存时间: {state_stats.get('average_save_time', 0):.2f} 秒")

async def main():
    """主演示函数"""
    logger.info("🚀 开始甘特图保存功能演示")
    
    try:
        # 1. 演示保存功能
        task_ids = await demo_save_functionality()
        
        # 2. 演示搜索功能
        await demo_search_functionality()
        
        # 3. 演示加载功能
        await demo_load_functionality()
        
        # 4. 演示统计功能
        await demo_statistics()
        
        logger.info("🎉 甘特图保存功能演示完成")
        
    except Exception as e:
        logger.error(f"❌ 演示过程中发生错误: {e}")
        raise

if __name__ == "__main__":
    # 确保输出目录存在
    Path("reports/gantt/demo").mkdir(parents=True, exist_ok=True)
    
    # 运行演示
    asyncio.run(main())
