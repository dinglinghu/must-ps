"""
甘特图数据持久化管理器
负责甘特图数据的序列化、反序列化、版本控制和兼容性处理
"""

import json
import logging
import gzip
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
import uuid

from .realistic_constellation_gantt import ConstellationGanttData, ConstellationGanttTask
from .gantt_save_config_manager import get_gantt_save_config_manager
from .gantt_file_manager import get_gantt_file_manager

logger = logging.getLogger(__name__)

@dataclass
class GanttDataVersion:
    """甘特图数据版本信息"""
    version: str = "2.0.0"
    schema_version: str = "1.0"
    created_by: str = "CONSTELLATION_MULTI_AGENT_SYSTEM"
    created_at: datetime = None
    compatibility: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.compatibility is None:
            self.compatibility = ["2.0.0", "1.9.0", "1.8.0"]

@dataclass
class GanttDataContainer:
    """甘特图数据容器"""
    container_id: str
    version_info: GanttDataVersion
    gantt_data: ConstellationGanttData
    metadata: Dict[str, Any]
    checksum: str = ""
    
    def __post_init__(self):
        if not self.container_id:
            self.container_id = str(uuid.uuid4())

class GanttDataPersistenceManager:
    """甘特图数据持久化管理器"""
    
    def __init__(self):
        self.config_manager = get_gantt_save_config_manager()
        self.file_manager = get_gantt_file_manager()
        
        # 支持的序列化格式
        self.serializers = {
            'json': self._serialize_json,
            'json_compressed': self._serialize_json_compressed,
            'pickle': self._serialize_pickle,
            'pickle_compressed': self._serialize_pickle_compressed
        }
        
        self.deserializers = {
            'json': self._deserialize_json,
            'json_compressed': self._deserialize_json_compressed,
            'pickle': self._deserialize_pickle,
            'pickle_compressed': self._deserialize_pickle_compressed
        }
        
        logger.info("✅ 甘特图数据持久化管理器初始化完成")
    
    def save_gantt_data(
        self,
        gantt_data: ConstellationGanttData,
        save_path: str,
        format: str = "json",
        compress: bool = False,
        include_metadata: bool = True
    ) -> str:
        """保存甘特图数据"""
        try:
            # 创建数据容器
            container = self._create_data_container(gantt_data, include_metadata)
            
            # 选择序列化格式
            serializer_key = format
            if compress and format in ['json', 'pickle']:
                serializer_key = f"{format}_compressed"
            
            if serializer_key not in self.serializers:
                raise ValueError(f"不支持的序列化格式: {serializer_key}")
            
            # 序列化数据
            serialized_data = self.serializers[serializer_key](container)
            
            # 保存到文件
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == 'pickle' or serializer_key.endswith('_compressed'):
                with open(save_path, 'wb') as f:
                    f.write(serialized_data)
            else:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(serialized_data)
            
            # 注册文件
            self.file_manager.register_file(
                str(save_path),
                gantt_data.chart_type,
                getattr(gantt_data, 'mission_scenario', 'UNKNOWN'),
                'data'
            )
            
            logger.info(f"✅ 甘特图数据已保存: {save_path}")
            return str(save_path)
            
        except Exception as e:
            logger.error(f"❌ 保存甘特图数据失败: {e}")
            raise
    
    def load_gantt_data(self, file_path: str) -> Optional[ConstellationGanttData]:
        """加载甘特图数据"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 检测文件格式
            format = self._detect_file_format(file_path)
            
            if format not in self.deserializers:
                raise ValueError(f"不支持的文件格式: {format}")
            
            # 读取文件
            if format in ['pickle', 'pickle_compressed', 'json_compressed']:
                with open(file_path, 'rb') as f:
                    file_data = f.read()
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = f.read()
            
            # 反序列化数据
            container = self.deserializers[format](file_data)
            
            # 验证版本兼容性
            if not self._check_version_compatibility(container.version_info):
                logger.warning(f"⚠️ 版本兼容性警告: {container.version_info.version}")
            
            logger.info(f"✅ 甘特图数据已加载: {file_path}")
            return container.gantt_data
            
        except Exception as e:
            logger.error(f"❌ 加载甘特图数据失败: {e}")
            return None
    
    def _create_data_container(
        self,
        gantt_data: ConstellationGanttData,
        include_metadata: bool = True
    ) -> GanttDataContainer:
        """创建数据容器"""
        version_info = GanttDataVersion()
        
        metadata = {}
        if include_metadata:
            metadata = {
                'total_tasks': len(gantt_data.tasks),
                'total_satellites': len(gantt_data.satellites),
                'total_missiles': len(gantt_data.missiles),
                'time_span_hours': (gantt_data.end_time - gantt_data.start_time).total_seconds() / 3600,
                'performance_metrics': gantt_data.performance_metrics,
                'export_settings': asdict(self.config_manager.settings)
            }
        
        container = GanttDataContainer(
            container_id=str(uuid.uuid4()),
            version_info=version_info,
            gantt_data=gantt_data,
            metadata=metadata
        )
        
        # 计算校验和
        container.checksum = self._calculate_checksum(container)
        
        return container
    
    def _calculate_checksum(self, container: GanttDataContainer) -> str:
        """计算数据校验和"""
        import hashlib
        
        # 创建用于校验和计算的数据
        checksum_data = {
            'container_id': container.container_id,
            'gantt_data_id': container.gantt_data.chart_id,
            'task_count': len(container.gantt_data.tasks),
            'creation_time': container.gantt_data.creation_time.isoformat()
        }
        
        data_str = json.dumps(checksum_data, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _serialize_json(self, container: GanttDataContainer) -> str:
        """JSON序列化"""
        data = {
            'container_id': container.container_id,
            'version_info': asdict(container.version_info),
            'gantt_data': self._gantt_data_to_dict(container.gantt_data),
            'metadata': container.metadata,
            'checksum': container.checksum
        }
        
        # 处理datetime对象
        return json.dumps(data, indent=2, ensure_ascii=False, default=self._json_serializer)
    
    def _serialize_json_compressed(self, container: GanttDataContainer) -> bytes:
        """压缩JSON序列化"""
        json_data = self._serialize_json(container)
        return gzip.compress(json_data.encode('utf-8'))
    
    def _serialize_pickle(self, container: GanttDataContainer) -> bytes:
        """Pickle序列化"""
        return pickle.dumps(container)
    
    def _serialize_pickle_compressed(self, container: GanttDataContainer) -> bytes:
        """压缩Pickle序列化"""
        pickle_data = pickle.dumps(container)
        return gzip.compress(pickle_data)
    
    def _deserialize_json(self, data: str) -> GanttDataContainer:
        """JSON反序列化"""
        json_data = json.loads(data)
        return self._dict_to_container(json_data)
    
    def _deserialize_json_compressed(self, data: bytes) -> GanttDataContainer:
        """压缩JSON反序列化"""
        decompressed_data = gzip.decompress(data).decode('utf-8')
        return self._deserialize_json(decompressed_data)
    
    def _deserialize_pickle(self, data: bytes) -> GanttDataContainer:
        """Pickle反序列化"""
        return pickle.loads(data)
    
    def _deserialize_pickle_compressed(self, data: bytes) -> GanttDataContainer:
        """压缩Pickle反序列化"""
        decompressed_data = gzip.decompress(data)
        return pickle.loads(decompressed_data)
    
    def _detect_file_format(self, file_path: Path) -> str:
        """检测文件格式"""
        # 首先尝试从扩展名判断
        suffix = file_path.suffix.lower()
        
        if suffix == '.json':
            return 'json'
        elif suffix == '.pkl' or suffix == '.pickle':
            return 'pickle'
        elif suffix == '.gz':
            # 检查是否是压缩文件
            try:
                with open(file_path, 'rb') as f:
                    header = f.read(2)
                    if header == b'\x1f\x8b':  # gzip magic number
                        # 尝试解压缩并检查内容
                        f.seek(0)
                        try:
                            decompressed = gzip.decompress(f.read())
                            if decompressed.startswith(b'{'):
                                return 'json_compressed'
                            else:
                                return 'pickle_compressed'
                        except:
                            return 'pickle_compressed'
            except:
                pass
        
        # 尝试读取文件内容判断
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read(100)
                if content.strip().startswith('{'):
                    return 'json'
        except:
            pass
        
        # 默认尝试pickle
        return 'pickle'

    def _gantt_data_to_dict(self, gantt_data: ConstellationGanttData) -> Dict[str, Any]:
        """将甘特图数据转换为字典"""
        tasks_data = []
        for task in gantt_data.tasks:
            task_dict = {
                'task_id': task.task_id,
                'task_name': task.task_name,
                'start_time': task.start_time.isoformat(),
                'end_time': task.end_time.isoformat(),
                'category': task.category,
                'priority': task.priority,
                'threat_level': task.threat_level,
                'assigned_satellite': task.assigned_satellite,
                'target_missile': task.target_missile,
                'execution_status': task.execution_status,
                'quality_score': task.quality_score,
                'resource_utilization': task.resource_utilization
            }
            tasks_data.append(task_dict)

        return {
            'chart_id': gantt_data.chart_id,
            'chart_type': gantt_data.chart_type,
            'creation_time': gantt_data.creation_time.isoformat(),
            'mission_scenario': gantt_data.mission_scenario,
            'start_time': gantt_data.start_time.isoformat(),
            'end_time': gantt_data.end_time.isoformat(),
            'tasks': tasks_data,
            'satellites': gantt_data.satellites,
            'missiles': gantt_data.missiles,
            'metadata': gantt_data.metadata,
            'performance_metrics': gantt_data.performance_metrics
        }

    def _dict_to_container(self, data: Dict[str, Any]) -> GanttDataContainer:
        """将字典转换为数据容器"""
        # 重建版本信息
        version_data = data['version_info']
        version_info = GanttDataVersion(
            version=version_data['version'],
            schema_version=version_data['schema_version'],
            created_by=version_data['created_by'],
            created_at=datetime.fromisoformat(version_data['created_at']),
            compatibility=version_data['compatibility']
        )

        # 重建甘特图数据
        gantt_dict = data['gantt_data']
        tasks = []
        for task_data in gantt_dict['tasks']:
            task = ConstellationGanttTask(
                task_id=task_data['task_id'],
                task_name=task_data['task_name'],
                start_time=datetime.fromisoformat(task_data['start_time']),
                end_time=datetime.fromisoformat(task_data['end_time']),
                category=task_data['category'],
                priority=task_data['priority'],
                threat_level=task_data['threat_level'],
                assigned_satellite=task_data['assigned_satellite'],
                target_missile=task_data['target_missile'],
                execution_status=task_data['execution_status'],
                quality_score=task_data['quality_score'],
                resource_utilization=task_data['resource_utilization']
            )
            tasks.append(task)

        gantt_data = ConstellationGanttData(
            chart_id=gantt_dict['chart_id'],
            chart_type=gantt_dict['chart_type'],
            creation_time=datetime.fromisoformat(gantt_dict['creation_time']),
            mission_scenario=gantt_dict['mission_scenario'],
            start_time=datetime.fromisoformat(gantt_dict['start_time']),
            end_time=datetime.fromisoformat(gantt_dict['end_time']),
            tasks=tasks,
            satellites=gantt_dict['satellites'],
            missiles=gantt_dict['missiles'],
            metadata=gantt_dict['metadata'],
            performance_metrics=gantt_dict['performance_metrics']
        )

        return GanttDataContainer(
            container_id=data['container_id'],
            version_info=version_info,
            gantt_data=gantt_data,
            metadata=data['metadata'],
            checksum=data['checksum']
        )

    def _json_serializer(self, obj):
        """JSON序列化辅助函数"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    def _check_version_compatibility(self, version_info: GanttDataVersion) -> bool:
        """检查版本兼容性"""
        current_version = "2.0.0"
        return current_version in version_info.compatibility

    def migrate_data(self, old_data: Dict[str, Any], target_version: str = "2.0.0") -> Dict[str, Any]:
        """数据迁移"""
        try:
            # 检查当前版本
            current_version = old_data.get('version_info', {}).get('version', '1.0.0')

            if current_version == target_version:
                return old_data

            logger.info(f"🔄 开始数据迁移: {current_version} -> {target_version}")

            # 执行迁移
            migrated_data = self._perform_migration(old_data, current_version, target_version)

            logger.info(f"✅ 数据迁移完成: {current_version} -> {target_version}")
            return migrated_data

        except Exception as e:
            logger.error(f"❌ 数据迁移失败: {e}")
            raise

    def _perform_migration(self, data: Dict[str, Any], from_version: str, to_version: str) -> Dict[str, Any]:
        """执行具体的迁移操作"""
        # 这里可以根据版本差异实现具体的迁移逻辑
        if from_version.startswith('1.') and to_version.startswith('2.'):
            # 1.x -> 2.x 迁移
            return self._migrate_v1_to_v2(data)

        return data

    def _migrate_v1_to_v2(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """从v1.x迁移到v2.x"""
        # 添加新的字段和结构
        if 'version_info' not in data:
            data['version_info'] = asdict(GanttDataVersion())

        if 'container_id' not in data:
            data['container_id'] = str(uuid.uuid4())

        if 'checksum' not in data:
            data['checksum'] = ""

        # 更新任务结构
        if 'gantt_data' in data and 'tasks' in data['gantt_data']:
            for task in data['gantt_data']['tasks']:
                if 'quality_score' not in task:
                    task['quality_score'] = 0.8
                if 'resource_utilization' not in task:
                    task['resource_utilization'] = {}

        return data

    def backup_data(self, source_path: str, backup_dir: str = None) -> str:
        """备份数据文件"""
        try:
            source_path = Path(source_path)

            if backup_dir is None:
                backup_dir = self.config_manager.settings.base_path + "/backups"

            backup_dir = Path(backup_dir)
            backup_dir.mkdir(parents=True, exist_ok=True)

            # 生成备份文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source_path.stem}_backup_{timestamp}{source_path.suffix}"
            backup_path = backup_dir / backup_name

            # 复制文件
            import shutil
            shutil.copy2(source_path, backup_path)

            logger.info(f"✅ 数据已备份: {backup_path}")
            return str(backup_path)

        except Exception as e:
            logger.error(f"❌ 数据备份失败: {e}")
            raise

    def validate_data_integrity(self, file_path: str) -> bool:
        """验证数据完整性"""
        try:
            container = self.load_gantt_data(file_path)
            if container is None:
                return False

            # 验证校验和
            calculated_checksum = self._calculate_checksum(container)
            stored_checksum = container.checksum

            if calculated_checksum != stored_checksum:
                logger.warning(f"⚠️ 数据校验和不匹配: {file_path}")
                return False

            # 验证数据结构
            if not self._validate_data_structure(container.gantt_data):
                return False

            logger.info(f"✅ 数据完整性验证通过: {file_path}")
            return True

        except Exception as e:
            logger.error(f"❌ 数据完整性验证失败: {e}")
            return False

    def _validate_data_structure(self, gantt_data: ConstellationGanttData) -> bool:
        """验证数据结构"""
        try:
            # 检查必要字段
            if not gantt_data.chart_id or not gantt_data.chart_type:
                return False

            # 检查时间逻辑
            if gantt_data.start_time >= gantt_data.end_time:
                return False

            # 检查任务数据
            for task in gantt_data.tasks:
                if task.start_time >= task.end_time:
                    return False
                if not task.task_id or not task.assigned_satellite:
                    return False

            return True

        except Exception:
            return False

# 全局持久化管理器实例
_gantt_persistence_manager = None

def get_gantt_persistence_manager() -> GanttDataPersistenceManager:
    """获取全局甘特图数据持久化管理器实例"""
    global _gantt_persistence_manager
    if _gantt_persistence_manager is None:
        _gantt_persistence_manager = GanttDataPersistenceManager()
    return _gantt_persistence_manager
