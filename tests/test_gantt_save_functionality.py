"""
甘特图保存功能测试
测试甘特图保存系统的各个组件和功能
"""

import pytest
import tempfile
import shutil
import json
from datetime import datetime, timedelta
from pathlib import Path
import asyncio

# 导入要测试的模块
from src.visualization.gantt_save_config_manager import (
    GanttSaveConfigManager, GanttSaveSettings, GanttSaveResult
)
from src.visualization.gantt_file_manager import (
    GanttFileManager, GanttFileInfo, GanttSearchFilter
)
from src.visualization.gantt_data_persistence import (
    GanttDataPersistenceManager, GanttDataContainer, GanttDataVersion
)
from src.visualization.gantt_save_state_manager import (
    GanttSaveStateManager, SaveTask, SaveStatus
)
from src.visualization.gantt_save_service import GanttSaveService
from src.visualization.realistic_constellation_gantt import (
    ConstellationGanttData, ConstellationGanttTask
)

class TestGanttSaveConfigManager:
    """测试甘特图保存配置管理器"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.json"
        self.manager = GanttSaveConfigManager(str(self.config_file))
    
    def teardown_method(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_config_initialization(self):
        """测试配置初始化"""
        assert self.manager.settings.base_path == "reports/gantt"
        assert self.manager.settings.auto_save is True
        assert "png" in self.manager.settings.default_formats
    
    def test_save_and_load_config(self):
        """测试配置保存和加载"""
        # 修改配置
        self.manager.update_settings(
            base_path="test/gantt",
            auto_save=False,
            image_quality="ultra"
        )
        
        # 创建新的管理器实例
        new_manager = GanttSaveConfigManager(str(self.config_file))
        
        # 验证配置已保存
        assert new_manager.settings.base_path == "test/gantt"
        assert new_manager.settings.auto_save is False
        assert new_manager.settings.image_quality == "ultra"
    
    def test_path_generation(self):
        """测试路径生成"""
        path = self.manager.get_save_path(
            chart_type="test_chart",
            format="png",
            mission_id="TEST_001",
            category="tactical"
        )
        
        assert "test_chart" in path
        assert "TEST_001" in path
        assert path.endswith(".png")
        assert "tactical" in path
    
    def test_image_settings(self):
        """测试图像设置"""
        settings = self.manager.get_image_settings("high")
        
        assert settings["dpi"] == 300
        assert settings["width"] == 1600
        assert settings["height"] == 1000
    
    def test_format_validation(self):
        """测试格式验证"""
        assert self.manager.validate_format("png") is True
        assert self.manager.validate_format("svg") is True
        assert self.manager.validate_format("invalid") is False

class TestGanttFileManager:
    """测试甘特图文件管理器"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test_files.db"
        self.manager = GanttFileManager(str(self.db_path))
    
    def teardown_method(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_file_registration(self):
        """测试文件注册"""
        # 创建测试文件
        test_file = Path(self.temp_dir) / "test_chart.png"
        test_file.write_text("test content")
        
        # 注册文件
        file_id = self.manager.register_file(
            str(test_file),
            chart_type="test_chart",
            mission_id="TEST_001",
            category="tactical"
        )
        
        assert file_id is not None
        
        # 获取文件信息
        file_info = self.manager.get_file_info(file_id)
        assert file_info is not None
        assert file_info.chart_type == "test_chart"
        assert file_info.mission_id == "TEST_001"
    
    def test_file_search(self):
        """测试文件搜索"""
        # 创建并注册多个测试文件
        for i in range(3):
            test_file = Path(self.temp_dir) / f"test_chart_{i}.png"
            test_file.write_text(f"test content {i}")
            
            self.manager.register_file(
                str(test_file),
                chart_type=f"chart_type_{i}",
                mission_id=f"MISSION_{i:03d}",
                category="tactical"
            )
        
        # 搜索所有文件
        filter = GanttSearchFilter()
        files = self.manager.search_files(filter)
        assert len(files) == 3
        
        # 按图表类型搜索
        filter = GanttSearchFilter(chart_type="chart_type_1")
        files = self.manager.search_files(filter)
        assert len(files) == 1
        assert files[0].chart_type == "chart_type_1"
    
    def test_file_deletion(self):
        """测试文件删除"""
        # 创建测试文件
        test_file = Path(self.temp_dir) / "test_delete.png"
        test_file.write_text("test content")
        
        # 注册文件
        file_id = self.manager.register_file(
            str(test_file),
            chart_type="test_chart",
            mission_id="TEST_001"
        )
        
        # 删除文件
        success = self.manager.delete_file(file_id, remove_physical=True)
        assert success is True
        
        # 验证文件已删除
        assert not test_file.exists()
        assert self.manager.get_file_info(file_id) is None

class TestGanttDataPersistence:
    """测试甘特图数据持久化"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = GanttDataPersistenceManager()
    
    def teardown_method(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_test_gantt_data(self) -> ConstellationGanttData:
        """创建测试甘特图数据"""
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=2)
        
        task = ConstellationGanttTask(
            task_id="TEST_TASK_001",
            task_name="测试任务",
            start_time=start_time,
            end_time=end_time,
            category="observation",
            priority=5,
            threat_level=3,
            assigned_satellite="SAT_001",
            target_missile="MISSILE_001",
            execution_status="planned"
        )
        
        gantt_data = ConstellationGanttData(
            chart_id="TEST_CHART_001",
            chart_type="test_chart",
            creation_time=datetime.now(),
            mission_scenario="测试场景",
            start_time=start_time,
            end_time=end_time,
            tasks=[task],
            satellites=["SAT_001"],
            missiles=["MISSILE_001"]
        )
        
        return gantt_data
    
    def test_json_serialization(self):
        """测试JSON序列化"""
        gantt_data = self.create_test_gantt_data()
        save_path = Path(self.temp_dir) / "test_gantt.json"
        
        # 保存数据
        saved_path = self.manager.save_gantt_data(
            gantt_data, str(save_path), format="json"
        )
        
        assert Path(saved_path).exists()
        
        # 加载数据
        loaded_data = self.manager.load_gantt_data(saved_path)
        
        assert loaded_data is not None
        assert loaded_data.chart_id == gantt_data.chart_id
        assert len(loaded_data.tasks) == 1
        assert loaded_data.tasks[0].task_id == "TEST_TASK_001"
    
    def test_compressed_serialization(self):
        """测试压缩序列化"""
        gantt_data = self.create_test_gantt_data()
        save_path = Path(self.temp_dir) / "test_gantt_compressed.json.gz"
        
        # 保存压缩数据
        saved_path = self.manager.save_gantt_data(
            gantt_data, str(save_path), format="json", compress=True
        )
        
        assert Path(saved_path).exists()
        
        # 加载压缩数据
        loaded_data = self.manager.load_gantt_data(saved_path)
        
        assert loaded_data is not None
        assert loaded_data.chart_id == gantt_data.chart_id

class TestGanttSaveStateManager:
    """测试甘特图保存状态管理器"""
    
    def setup_method(self):
        """测试前设置"""
        self.manager = GanttSaveStateManager(max_concurrent_saves=2)
    
    def teardown_method(self):
        """测试后清理"""
        self.manager.stop_workers()
    
    def test_task_submission(self):
        """测试任务提交"""
        gantt_data = {"test": "data"}
        
        task_id = self.manager.submit_save_task(
            gantt_data=gantt_data,
            save_path="/tmp/test.json",
            format="json"
        )
        
        assert task_id is not None
        
        # 获取任务状态
        task = self.manager.get_task_status(task_id)
        assert task is not None
        assert task.gantt_data == gantt_data
    
    def test_task_cancellation(self):
        """测试任务取消"""
        task_id = self.manager.submit_save_task(
            gantt_data={"test": "data"},
            save_path="/tmp/test.json",
            format="json"
        )
        
        # 取消任务
        success = self.manager.cancel_task(task_id)
        assert success is True
        
        # 验证任务状态
        task = self.manager.get_task_status(task_id)
        assert task.status == SaveStatus.CANCELLED

class TestGanttSaveService:
    """测试甘特图保存服务"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = tempfile.mkdtemp()
        self.service = GanttSaveService()
    
    def teardown_method(self):
        """测试后清理"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_save_gantt_chart(self):
        """测试保存甘特图"""
        # 创建测试数据
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=1)
        
        task = ConstellationGanttTask(
            task_id="TEST_TASK",
            task_name="测试任务",
            start_time=start_time,
            end_time=end_time,
            category="observation",
            priority=5,
            threat_level=3,
            assigned_satellite="SAT_001",
            target_missile="MISSILE_001",
            execution_status="planned"
        )
        
        gantt_data = ConstellationGanttData(
            chart_id="TEST_CHART",
            chart_type="test_chart",
            creation_time=datetime.now(),
            mission_scenario="测试场景",
            start_time=start_time,
            end_time=end_time,
            tasks=[task],
            satellites=["SAT_001"],
            missiles=["MISSILE_001"]
        )
        
        # 保存甘特图
        result = await self.service.save_gantt_chart(
            gantt_data=gantt_data,
            chart_type="test_chart",
            mission_id="TEST_MISSION",
            formats=["json"]
        )
        
        assert result['success'] is True
        assert len(result['task_ids']) == 1
    
    def test_search_functionality(self):
        """测试搜索功能"""
        search_params = {
            'chart_type': 'test_chart',
            'format': 'json'
        }
        
        result = self.service.search_gantt_charts(search_params)
        
        assert result['success'] is True
        assert 'files' in result
        assert 'total_count' in result

def run_gantt_save_tests():
    """运行甘特图保存功能测试"""
    print("🧪 开始甘特图保存功能测试...")
    
    # 运行测试
    pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])
    
    print("✅ 甘特图保存功能测试完成")

if __name__ == "__main__":
    run_gantt_save_tests()
