"""
甘特图文件管理器
负责甘特图文件的索引、搜索、归档、清理等管理功能
"""

import os
import json
import shutil
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

from .gantt_save_config_manager import get_gantt_save_config_manager, GanttSaveResult

logger = logging.getLogger(__name__)

@dataclass
class GanttFileInfo:
    """甘特图文件信息"""
    file_id: str
    file_path: str
    file_name: str
    file_size: int
    format: str
    chart_type: str
    mission_id: str
    category: str
    creation_time: datetime
    last_modified: datetime
    checksum: str
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class GanttSearchFilter:
    """甘特图搜索过滤器"""
    chart_type: Optional[str] = None
    format: Optional[str] = None
    mission_id: Optional[str] = None
    category: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    keywords: Optional[List[str]] = None

class GanttFileManager:
    """甘特图文件管理器"""
    
    def __init__(self, db_path: str = "data/gantt_files.db"):
        self.db_path = Path(db_path)
        self.config_manager = get_gantt_save_config_manager()
        
        # 确保数据库目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
        
        logger.info("✅ 甘特图文件管理器初始化完成")
    
    def _init_database(self):
        """初始化数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 创建文件信息表
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS gantt_files (
                        file_id TEXT PRIMARY KEY,
                        file_path TEXT UNIQUE NOT NULL,
                        file_name TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        format TEXT NOT NULL,
                        chart_type TEXT NOT NULL,
                        mission_id TEXT,
                        category TEXT NOT NULL,
                        creation_time TEXT NOT NULL,
                        last_modified TEXT NOT NULL,
                        checksum TEXT NOT NULL,
                        metadata TEXT
                    )
                ''')
                
                # 创建索引
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_chart_type ON gantt_files(chart_type)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_format ON gantt_files(format)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_mission_id ON gantt_files(mission_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_category ON gantt_files(category)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_creation_time ON gantt_files(creation_time)')
                
                conn.commit()
                logger.info("✅ 甘特图文件数据库初始化完成")
                
        except Exception as e:
            logger.error(f"❌ 初始化甘特图文件数据库失败: {e}")
            raise
    
    def register_file(self, file_path: str, chart_type: str, mission_id: str = None, 
                     category: str = "tactical", metadata: Dict[str, Any] = None) -> str:
        """注册甘特图文件"""
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 生成文件ID
            file_id = self._generate_file_id(file_path)
            
            # 计算文件校验和
            checksum = self._calculate_checksum(file_path)
            
            # 获取文件信息
            stat = file_path.stat()
            
            file_info = GanttFileInfo(
                file_id=file_id,
                file_path=str(file_path),
                file_name=file_path.name,
                file_size=stat.st_size,
                format=file_path.suffix[1:].lower(),
                chart_type=chart_type,
                mission_id=mission_id or "UNKNOWN",
                category=category,
                creation_time=datetime.fromtimestamp(stat.st_ctime),
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                checksum=checksum,
                metadata=metadata or {}
            )
            
            # 保存到数据库
            self._save_file_info(file_info)
            
            logger.info(f"✅ 甘特图文件已注册: {file_path.name}")
            return file_id
            
        except Exception as e:
            logger.error(f"❌ 注册甘特图文件失败: {e}")
            raise
    
    def _generate_file_id(self, file_path: Path) -> str:
        """生成文件ID"""
        # 使用文件路径和创建时间生成唯一ID
        content = f"{file_path}_{file_path.stat().st_ctime}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """计算文件校验和"""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _save_file_info(self, file_info: GanttFileInfo):
        """保存文件信息到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT OR REPLACE INTO gantt_files 
                    (file_id, file_path, file_name, file_size, format, chart_type, 
                     mission_id, category, creation_time, last_modified, checksum, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    file_info.file_id,
                    file_info.file_path,
                    file_info.file_name,
                    file_info.file_size,
                    file_info.format,
                    file_info.chart_type,
                    file_info.mission_id,
                    file_info.category,
                    file_info.creation_time.isoformat(),
                    file_info.last_modified.isoformat(),
                    file_info.checksum,
                    json.dumps(file_info.metadata, ensure_ascii=False)
                ))
                
                conn.commit()
                
        except Exception as e:
            logger.error(f"❌ 保存文件信息失败: {e}")
            raise
    
    def search_files(self, filter: GanttSearchFilter) -> List[GanttFileInfo]:
        """搜索甘特图文件"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                conditions = []
                params = []
                
                if filter.chart_type:
                    conditions.append("chart_type = ?")
                    params.append(filter.chart_type)
                
                if filter.format:
                    conditions.append("format = ?")
                    params.append(filter.format)
                
                if filter.mission_id:
                    conditions.append("mission_id = ?")
                    params.append(filter.mission_id)
                
                if filter.category:
                    conditions.append("category = ?")
                    params.append(filter.category)
                
                if filter.date_from:
                    conditions.append("creation_time >= ?")
                    params.append(filter.date_from.isoformat())
                
                if filter.date_to:
                    conditions.append("creation_time <= ?")
                    params.append(filter.date_to.isoformat())
                
                if filter.min_size:
                    conditions.append("file_size >= ?")
                    params.append(filter.min_size)
                
                if filter.max_size:
                    conditions.append("file_size <= ?")
                    params.append(filter.max_size)
                
                # 构建SQL查询
                sql = "SELECT * FROM gantt_files"
                if conditions:
                    sql += " WHERE " + " AND ".join(conditions)
                sql += " ORDER BY creation_time DESC"
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                
                # 转换为GanttFileInfo对象
                files = []
                for row in rows:
                    file_info = GanttFileInfo(
                        file_id=row[0],
                        file_path=row[1],
                        file_name=row[2],
                        file_size=row[3],
                        format=row[4],
                        chart_type=row[5],
                        mission_id=row[6],
                        category=row[7],
                        creation_time=datetime.fromisoformat(row[8]),
                        last_modified=datetime.fromisoformat(row[9]),
                        checksum=row[10],
                        metadata=json.loads(row[11]) if row[11] else {}
                    )
                    
                    # 关键词过滤
                    if filter.keywords:
                        if self._match_keywords(file_info, filter.keywords):
                            files.append(file_info)
                    else:
                        files.append(file_info)
                
                return files
                
        except Exception as e:
            logger.error(f"❌ 搜索甘特图文件失败: {e}")
            return []
    
    def _match_keywords(self, file_info: GanttFileInfo, keywords: List[str]) -> bool:
        """检查文件是否匹配关键词"""
        search_text = f"{file_info.file_name} {file_info.chart_type} {file_info.mission_id}".lower()
        return any(keyword.lower() in search_text for keyword in keywords)

    def get_file_info(self, file_id: str) -> Optional[GanttFileInfo]:
        """获取文件信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM gantt_files WHERE file_id = ?", (file_id,))
                row = cursor.fetchone()

                if row:
                    return GanttFileInfo(
                        file_id=row[0],
                        file_path=row[1],
                        file_name=row[2],
                        file_size=row[3],
                        format=row[4],
                        chart_type=row[5],
                        mission_id=row[6],
                        category=row[7],
                        creation_time=datetime.fromisoformat(row[8]),
                        last_modified=datetime.fromisoformat(row[9]),
                        checksum=row[10],
                        metadata=json.loads(row[11]) if row[11] else {}
                    )
                return None

        except Exception as e:
            logger.error(f"❌ 获取文件信息失败: {e}")
            return None

    def delete_file(self, file_id: str, remove_physical: bool = True) -> bool:
        """删除文件"""
        try:
            file_info = self.get_file_info(file_id)
            if not file_info:
                logger.warning(f"⚠️ 文件不存在: {file_id}")
                return False

            # 删除物理文件
            if remove_physical:
                file_path = Path(file_info.file_path)
                if file_path.exists():
                    file_path.unlink()
                    logger.info(f"🗑️ 已删除物理文件: {file_path}")

            # 从数据库删除记录
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM gantt_files WHERE file_id = ?", (file_id,))
                conn.commit()

            logger.info(f"✅ 文件已删除: {file_info.file_name}")
            return True

        except Exception as e:
            logger.error(f"❌ 删除文件失败: {e}")
            return False

    def archive_file(self, file_id: str) -> bool:
        """归档文件"""
        try:
            file_info = self.get_file_info(file_id)
            if not file_info:
                return False

            source_path = Path(file_info.file_path)
            if not source_path.exists():
                logger.warning(f"⚠️ 源文件不存在: {source_path}")
                return False

            # 生成归档路径
            archive_date = datetime.now()
            archive_subdir = archive_date.strftime("%Y/%m")
            archive_path = Path(self.config_manager.settings.base_path) / "archives" / archive_subdir / source_path.name

            # 确保归档目录存在
            archive_path.parent.mkdir(parents=True, exist_ok=True)

            # 移动文件
            shutil.move(str(source_path), str(archive_path))

            # 更新数据库中的路径
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE gantt_files SET file_path = ?, category = ? WHERE file_id = ?",
                    (str(archive_path), "archived", file_id)
                )
                conn.commit()

            logger.info(f"📁 文件已归档: {source_path.name} -> {archive_path}")
            return True

        except Exception as e:
            logger.error(f"❌ 归档文件失败: {e}")
            return False

    def get_statistics(self) -> Dict[str, Any]:
        """获取文件统计信息"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # 总文件数
                cursor.execute("SELECT COUNT(*) FROM gantt_files")
                total_files = cursor.fetchone()[0]

                # 按格式统计
                cursor.execute("SELECT format, COUNT(*) FROM gantt_files GROUP BY format")
                format_stats = dict(cursor.fetchall())

                # 按图表类型统计
                cursor.execute("SELECT chart_type, COUNT(*) FROM gantt_files GROUP BY chart_type")
                chart_type_stats = dict(cursor.fetchall())

                # 按类别统计
                cursor.execute("SELECT category, COUNT(*) FROM gantt_files GROUP BY category")
                category_stats = dict(cursor.fetchall())

                # 总文件大小
                cursor.execute("SELECT SUM(file_size) FROM gantt_files")
                total_size = cursor.fetchone()[0] or 0

                # 最近文件
                cursor.execute(
                    "SELECT file_name, creation_time FROM gantt_files ORDER BY creation_time DESC LIMIT 5"
                )
                recent_files = [{"name": row[0], "time": row[1]} for row in cursor.fetchall()]

                return {
                    "total_files": total_files,
                    "total_size_mb": total_size / (1024 * 1024),
                    "format_distribution": format_stats,
                    "chart_type_distribution": chart_type_stats,
                    "category_distribution": category_stats,
                    "recent_files": recent_files
                }

        except Exception as e:
            logger.error(f"❌ 获取统计信息失败: {e}")
            return {}

    def cleanup_orphaned_records(self) -> int:
        """清理孤立记录（文件已删除但数据库记录仍存在）"""
        try:
            orphaned_count = 0

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_id, file_path FROM gantt_files")

                for file_id, file_path in cursor.fetchall():
                    if not Path(file_path).exists():
                        cursor.execute("DELETE FROM gantt_files WHERE file_id = ?", (file_id,))
                        orphaned_count += 1
                        logger.info(f"🧹 清理孤立记录: {file_path}")

                conn.commit()

            logger.info(f"✅ 清理完成，删除 {orphaned_count} 条孤立记录")
            return orphaned_count

        except Exception as e:
            logger.error(f"❌ 清理孤立记录失败: {e}")
            return 0

    def sync_filesystem(self, base_path: str = None) -> Dict[str, int]:
        """同步文件系统，发现新文件并注册"""
        base_path = base_path or self.config_manager.settings.base_path
        sync_stats = {"discovered": 0, "registered": 0, "errors": 0}

        try:
            base_path = Path(base_path)

            # 获取已注册的文件路径
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT file_path FROM gantt_files")
                registered_paths = {row[0] for row in cursor.fetchall()}

            # 扫描文件系统
            for file_path in base_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in ['.png', '.svg', '.pdf', '.html', '.json']:
                    sync_stats["discovered"] += 1

                    if str(file_path) not in registered_paths:
                        try:
                            # 尝试从文件名推断信息
                            chart_type, mission_id, category = self._infer_file_info(file_path)
                            self.register_file(str(file_path), chart_type, mission_id, category)
                            sync_stats["registered"] += 1
                        except Exception as e:
                            logger.warning(f"⚠️ 注册文件失败: {file_path} - {e}")
                            sync_stats["errors"] += 1

            logger.info(f"✅ 文件系统同步完成: {sync_stats}")
            return sync_stats

        except Exception as e:
            logger.error(f"❌ 文件系统同步失败: {e}")
            return sync_stats

    def _infer_file_info(self, file_path: Path) -> Tuple[str, str, str]:
        """从文件路径推断文件信息"""
        # 从文件名推断图表类型
        name_lower = file_path.name.lower()
        if "task_allocation" in name_lower:
            chart_type = "task_allocation"
        elif "resource_utilization" in name_lower:
            chart_type = "resource_utilization"
        elif "mission_overview" in name_lower:
            chart_type = "mission_overview"
        elif "planning" in name_lower:
            chart_type = "planning"
        elif "meta_task" in name_lower:
            chart_type = "meta_task"
        else:
            chart_type = "unknown"

        # 从路径推断类别
        path_parts = file_path.parts
        if "strategic" in path_parts:
            category = "strategic"
        elif "tactical" in path_parts:
            category = "tactical"
        elif "execution" in path_parts:
            category = "execution"
        elif "analysis" in path_parts:
            category = "analysis"
        elif "archives" in path_parts:
            category = "archived"
        else:
            category = "unknown"

        # 尝试从文件名提取任务ID
        mission_id = "UNKNOWN"
        parts = file_path.stem.split("_")
        for part in parts:
            if part.startswith("MISSION") or part.startswith("DEMO"):
                mission_id = part
                break

        return chart_type, mission_id, category

# 全局文件管理器实例
_gantt_file_manager = None

def get_gantt_file_manager() -> GanttFileManager:
    """获取全局甘特图文件管理器实例"""
    global _gantt_file_manager
    if _gantt_file_manager is None:
        _gantt_file_manager = GanttFileManager()
    return _gantt_file_manager
