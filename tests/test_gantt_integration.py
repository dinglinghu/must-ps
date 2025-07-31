"""
甘特图集成测试
测试甘特图保存系统与整个系统的集成
"""

import pytest
import asyncio
import tempfile
import shutil
import json
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
from src.api.gantt_api import gantt_api
from flask import Flask

class TestGanttIntegration:
    """甘特图集成测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.save_service = get_gantt_save_service()
        
        # 创建测试甘特图数据
        self.test_gantt_data = self.create_test_gantt_data()
    
    def teardown_method(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_gantt_data(self) -> ConstellationGanttData:
        """创建测试甘特图数据"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)
        
        # 创建测试任务
        tasks = []
        for i in range(3):
            task = ConstellationGanttTask(
                task_id=f"INTEGRATION_TASK_{i:03d}",
                task_name=f"集成测试任务 {i+1}",
                start_time=start_time + timedelta(minutes=i*10),
                end_time=start_time + timedelta(minutes=(i+1)*15),
                category="observation",
                priority=5-i,
                threat_level=3,
                assigned_satellite=f"SAT_{i:03d}",
                target_missile=f"MISSILE_{i:03d}",
                execution_status="planned",
                quality_score=0.9 - i*0.1,
                resource_utilization={"cpu": 0.8-i*0.1, "memory": 0.6-i*0.05}
            )
            tasks.append(task)
        
        gantt_data = ConstellationGanttData(
            chart_id="INTEGRATION_TEST_CHART",
            chart_type="integration_test",
            creation_time=datetime.now(),
            mission_scenario="集成测试场景",
            start_time=start_time,
            end_time=end_time,
            tasks=tasks,
            satellites=[f"SAT_{i:03d}" for i in range(3)],
            missiles=[f"MISSILE_{i:03d}" for i in range(3)],
            metadata={"test_type": "integration", "version": "1.0"},
            performance_metrics={"coverage": 0.85, "efficiency": 0.78}
        )
        
        return gantt_data
    
    @pytest.mark.asyncio
    async def test_end_to_end_save_and_load(self):
        """测试端到端的保存和加载流程"""
        print("🧪 测试端到端保存和加载流程...")
        
        # 1. 保存甘特图
        save_result = await self.save_service.save_gantt_chart(
            gantt_data=self.test_gantt_data,
            chart_type="integration_test",
            mission_id="INTEGRATION_TEST_001",
            formats=["json"],
            category="test"
        )
        
        assert save_result['success'] is True
        assert len(save_result['task_ids']) == 1
        
        # 2. 等待保存完成
        task_ids = save_result['task_ids']
        max_wait = 10
        wait_time = 0
        
        while wait_time < max_wait:
            progress = self.save_service.get_save_progress(task_ids)
            if progress['completed_count'] == progress['total_count']:
                break
            await asyncio.sleep(0.5)
            wait_time += 0.5
        
        assert progress['completed_count'] == 1
        
        # 3. 搜索保存的文件
        search_result = self.save_service.search_gantt_charts({
            'chart_type': 'integration_test'
        })
        
        assert search_result['success'] is True
        assert search_result['total_count'] > 0
        
        # 4. 加载文件
        file_id = search_result['files'][0]['file_id']
        load_result = self.save_service.load_gantt_chart(file_id)
        
        assert load_result['success'] is True
        loaded_data = load_result['gantt_data']
        assert loaded_data.chart_id == self.test_gantt_data.chart_id
        assert len(loaded_data.tasks) == len(self.test_gantt_data.tasks)
        
        print("✅ 端到端测试通过")
    
    def test_api_integration(self):
        """测试API集成"""
        print("🧪 测试API集成...")
        
        # 创建Flask应用
        app = Flask(__name__)
        app.register_blueprint(gantt_api)
        
        with app.test_client() as client:
            # 测试搜索API
            response = client.post('/api/gantt/search', 
                                 json={'chart_type': 'integration_test'})
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            
            print("✅ API集成测试通过")
    
    def test_configuration_management(self):
        """测试配置管理"""
        print("🧪 测试配置管理...")
        
        from src.visualization.gantt_save_config_manager import get_gantt_save_config_manager
        
        config_manager = get_gantt_save_config_manager()
        
        # 测试配置更新
        original_quality = config_manager.settings.image_quality
        config_manager.update_settings(image_quality="ultra")
        assert config_manager.settings.image_quality == "ultra"
        
        # 恢复原始配置
        config_manager.update_settings(image_quality=original_quality)
        
        print("✅ 配置管理测试通过")
    
    def test_file_management(self):
        """测试文件管理"""
        print("🧪 测试文件管理...")
        
        from src.visualization.gantt_file_manager import get_gantt_file_manager
        
        file_manager = get_gantt_file_manager()
        
        # 获取统计信息
        stats = file_manager.get_statistics()
        assert 'total_files' in stats
        assert 'total_size_mb' in stats
        
        # 测试清理功能
        orphaned_count = file_manager.cleanup_orphaned_records()
        assert isinstance(orphaned_count, int)
        
        print("✅ 文件管理测试通过")
    
    def test_state_management(self):
        """测试状态管理"""
        print("🧪 测试状态管理...")
        
        from src.visualization.gantt_save_state_manager import get_gantt_save_state_manager
        
        state_manager = get_gantt_save_state_manager()
        
        # 获取统计信息
        stats = state_manager.get_statistics()
        assert hasattr(stats, 'total_tasks')
        assert hasattr(stats, 'completed_tasks')
        
        # 获取活动任务
        active_tasks = state_manager.get_active_tasks()
        assert isinstance(active_tasks, list)
        
        print("✅ 状态管理测试通过")
    
    def test_data_persistence(self):
        """测试数据持久化"""
        print("🧪 测试数据持久化...")
        
        from src.visualization.gantt_data_persistence import get_gantt_persistence_manager
        
        persistence_manager = get_gantt_persistence_manager()
        
        # 测试JSON保存和加载
        test_file = Path(self.temp_dir) / "test_persistence.json"
        
        saved_path = persistence_manager.save_gantt_data(
            self.test_gantt_data, str(test_file), "json"
        )
        
        assert Path(saved_path).exists()
        
        loaded_data = persistence_manager.load_gantt_data(saved_path)
        assert loaded_data is not None
        assert loaded_data.chart_id == self.test_gantt_data.chart_id
        
        print("✅ 数据持久化测试通过")
    
    def test_error_handling(self):
        """测试错误处理"""
        print("🧪 测试错误处理...")
        
        # 测试加载不存在的文件
        load_result = self.save_service.load_gantt_chart("non_existent_id")
        assert load_result['success'] is False
        assert 'error' in load_result
        
        # 测试删除不存在的文件
        delete_result = self.save_service.delete_gantt_chart("non_existent_id")
        assert delete_result['success'] is False
        
        print("✅ 错误处理测试通过")

def run_integration_tests():
    """运行集成测试"""
    print("🚀 开始甘特图集成测试...")
    
    # 确保测试目录存在
    Path("reports/gantt/test").mkdir(parents=True, exist_ok=True)
    
    # 运行测试
    pytest.main([
        __file__,
        "-v",
        "--tb=short",
        "-s"  # 显示print输出
    ])
    
    print("🎉 甘特图集成测试完成")

if __name__ == "__main__":
    run_integration_tests()
