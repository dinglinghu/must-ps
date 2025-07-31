"""
甘特图保存配置管理器
负责管理甘特图保存的各种配置选项和策略
"""

import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class GanttSaveFormat(Enum):
    """甘特图保存格式枚举"""
    PNG = "png"
    SVG = "svg"
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    EXCEL = "xlsx"

class GanttSaveQuality(Enum):
    """甘特图保存质量枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ULTRA = "ultra"

@dataclass
class GanttSaveSettings:
    """甘特图保存设置"""
    # 基本设置
    base_path: str = "reports/gantt"
    auto_save: bool = True
    create_backup: bool = True
    
    # 格式设置
    default_formats: List[str] = None
    image_quality: str = "high"
    image_dpi: int = 300
    image_width: int = 1600
    image_height: int = 1000
    
    # 文件管理
    max_files_per_type: int = 100
    auto_cleanup_days: int = 30
    archive_old_files: bool = True
    compress_archives: bool = True
    
    # 命名规则
    filename_template: str = "{chart_type}_{timestamp}_{mission_id}"
    timestamp_format: str = "%Y%m%d_%H%M%S"
    include_metadata: bool = True
    
    # 性能设置
    async_save: bool = True
    batch_save: bool = True
    max_concurrent_saves: int = 3
    
    def __post_init__(self):
        if self.default_formats is None:
            self.default_formats = ["png", "svg", "json"]

@dataclass
class GanttSaveResult:
    """甘特图保存结果"""
    success: bool
    file_path: str = ""
    file_size: int = 0
    format: str = ""
    save_time: datetime = None
    error_message: str = ""
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.save_time is None:
            self.save_time = datetime.now()
        if self.metadata is None:
            self.metadata = {}

class GanttSaveConfigManager:
    """甘特图保存配置管理器"""
    
    def __init__(self, config_file: str = "config/gantt_save_config.json"):
        self.config_file = Path(config_file)
        self.settings = GanttSaveSettings()
        self.save_history: List[GanttSaveResult] = []
        
        # 加载配置
        self.load_config()
        
        # 确保目录存在
        self._ensure_directories()
        
        logger.info("✅ 甘特图保存配置管理器初始化完成")
    
    def load_config(self) -> bool:
        """加载配置文件"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
                
                # 更新设置
                for key, value in config_data.items():
                    if hasattr(self.settings, key):
                        setattr(self.settings, key, value)
                
                logger.info(f"✅ 甘特图保存配置已加载: {self.config_file}")
                return True
            else:
                logger.info("📝 使用默认甘特图保存配置")
                self.save_config()  # 保存默认配置
                return True
                
        except Exception as e:
            logger.error(f"❌ 加载甘特图保存配置失败: {e}")
            return False
    
    def save_config(self) -> bool:
        """保存配置文件"""
        try:
            # 确保配置目录存在
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 保存配置
            config_data = asdict(self.settings)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ 甘特图保存配置已保存: {self.config_file}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存甘特图保存配置失败: {e}")
            return False
    
    def _ensure_directories(self):
        """确保必要的目录存在"""
        directories = [
            self.settings.base_path,
            f"{self.settings.base_path}/strategic",
            f"{self.settings.base_path}/tactical",
            f"{self.settings.base_path}/execution",
            f"{self.settings.base_path}/analysis",
            f"{self.settings.base_path}/archives",
            f"{self.settings.base_path}/temp",
            "reports/data",
            "reports/exports"
        ]
        
        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)
    
    def get_save_path(
        self,
        chart_type: str,
        format: str,
        mission_id: str = None,
        category: str = "tactical"
    ) -> str:
        """生成保存路径"""
        try:
            # 生成时间戳
            timestamp = datetime.now().strftime(self.settings.timestamp_format)
            
            # 生成文件名
            filename_vars = {
                'chart_type': chart_type,
                'timestamp': timestamp,
                'mission_id': mission_id or 'UNKNOWN',
                'category': category,
                'format': format
            }
            
            filename = self.settings.filename_template.format(**filename_vars)
            filename = f"{filename}.{format}"
            
            # 生成完整路径
            full_path = Path(self.settings.base_path) / category / filename
            
            return str(full_path)
            
        except Exception as e:
            logger.error(f"❌ 生成保存路径失败: {e}")
            # 返回默认路径
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"{self.settings.base_path}/{category}/{chart_type}_{timestamp}.{format}"
    
    def get_image_settings(self, quality: str = None) -> Dict[str, Any]:
        """获取图像保存设置"""
        quality = quality or self.settings.image_quality
        
        quality_settings = {
            "low": {"dpi": 150, "width": 800, "height": 600},
            "medium": {"dpi": 200, "width": 1200, "height": 800},
            "high": {"dpi": 300, "width": 1600, "height": 1000},
            "ultra": {"dpi": 600, "width": 2400, "height": 1500}
        }
        
        settings = quality_settings.get(quality, quality_settings["high"])
        
        return {
            "dpi": settings["dpi"],
            "width": settings["width"],
            "height": settings["height"],
            "bbox_inches": "tight",
            "facecolor": "white",
            "edgecolor": "none"
        }
    
    def record_save_result(self, result: GanttSaveResult):
        """记录保存结果"""
        self.save_history.append(result)
        
        # 限制历史记录数量
        if len(self.save_history) > 1000:
            self.save_history = self.save_history[-500:]
    
    def get_save_statistics(self) -> Dict[str, Any]:
        """获取保存统计信息"""
        if not self.save_history:
            return {"total_saves": 0}
        
        total_saves = len(self.save_history)
        successful_saves = sum(1 for r in self.save_history if r.success)
        failed_saves = total_saves - successful_saves
        
        # 按格式统计
        format_stats = {}
        for result in self.save_history:
            format_stats[result.format] = format_stats.get(result.format, 0) + 1
        
        # 计算总文件大小
        total_size = sum(r.file_size for r in self.save_history if r.success)
        
        return {
            "total_saves": total_saves,
            "successful_saves": successful_saves,
            "failed_saves": failed_saves,
            "success_rate": successful_saves / total_saves if total_saves > 0 else 0,
            "format_distribution": format_stats,
            "total_file_size_mb": total_size / (1024 * 1024),
            "average_file_size_mb": (total_size / successful_saves / (1024 * 1024)) if successful_saves > 0 else 0
        }

    def cleanup_old_files(self, days_to_keep: int = None) -> Dict[str, int]:
        """清理旧文件"""
        days_to_keep = days_to_keep or self.settings.auto_cleanup_days
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)

        cleanup_stats = {
            "files_checked": 0,
            "files_archived": 0,
            "files_deleted": 0,
            "space_freed_mb": 0
        }

        try:
            base_path = Path(self.settings.base_path)

            for root, dirs, files in os.walk(base_path):
                # 跳过归档目录
                if "archives" in root:
                    continue

                for file in files:
                    file_path = Path(root) / file
                    cleanup_stats["files_checked"] += 1

                    # 检查文件修改时间
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        file_size = file_path.stat().st_size

                        if self.settings.archive_old_files:
                            # 归档文件
                            archive_path = self._get_archive_path(file_path)
                            archive_path.parent.mkdir(parents=True, exist_ok=True)
                            file_path.rename(archive_path)
                            cleanup_stats["files_archived"] += 1
                        else:
                            # 删除文件
                            file_path.unlink()
                            cleanup_stats["files_deleted"] += 1
                            cleanup_stats["space_freed_mb"] += file_size / (1024 * 1024)

            logger.info(f"✅ 甘特图文件清理完成: {cleanup_stats}")
            return cleanup_stats

        except Exception as e:
            logger.error(f"❌ 清理甘特图文件失败: {e}")
            return cleanup_stats

    def _get_archive_path(self, file_path: Path) -> Path:
        """获取归档路径"""
        base_path = Path(self.settings.base_path)
        relative_path = file_path.relative_to(base_path)

        # 按年月组织归档
        archive_date = datetime.fromtimestamp(file_path.stat().st_mtime)
        archive_subdir = archive_date.strftime("%Y/%m")

        return base_path / "archives" / archive_subdir / relative_path

    def validate_format(self, format: str) -> bool:
        """验证保存格式是否支持"""
        supported_formats = [f.value for f in GanttSaveFormat]
        return format.lower() in supported_formats

    def get_format_settings(self, format: str) -> Dict[str, Any]:
        """获取特定格式的保存设置"""
        format = format.lower()

        if format == "png":
            return {
                **self.get_image_settings(),
                "format": "png",
                "transparent": False
            }
        elif format == "svg":
            return {
                **self.get_image_settings(),
                "format": "svg",
                "transparent": True
            }
        elif format == "pdf":
            return {
                **self.get_image_settings(),
                "format": "pdf",
                "orientation": "landscape"
            }
        elif format == "html":
            return {
                "include_plotlyjs": True,
                "div_id": "gantt-chart",
                "config": {"displayModeBar": True}
            }
        elif format == "json":
            return {
                "indent": 2,
                "ensure_ascii": False,
                "default": str
            }
        else:
            return {}

    def update_settings(self, **kwargs) -> bool:
        """更新配置设置"""
        try:
            for key, value in kwargs.items():
                if hasattr(self.settings, key):
                    setattr(self.settings, key, value)
                    logger.info(f"📝 更新甘特图保存设置: {key} = {value}")
                else:
                    logger.warning(f"⚠️ 未知的配置项: {key}")

            # 保存更新后的配置
            return self.save_config()

        except Exception as e:
            logger.error(f"❌ 更新甘特图保存设置失败: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """重置为默认配置"""
        try:
            self.settings = GanttSaveSettings()
            self._ensure_directories()
            return self.save_config()
        except Exception as e:
            logger.error(f"❌ 重置甘特图保存配置失败: {e}")
            return False

    def export_config(self, export_path: str) -> bool:
        """导出配置到文件"""
        try:
            export_data = {
                "settings": asdict(self.settings),
                "statistics": self.get_save_statistics(),
                "export_time": datetime.now().isoformat()
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"✅ 甘特图保存配置已导出: {export_path}")
            return True

        except Exception as e:
            logger.error(f"❌ 导出甘特图保存配置失败: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """从文件导入配置"""
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            if "settings" in import_data:
                settings_data = import_data["settings"]
                for key, value in settings_data.items():
                    if hasattr(self.settings, key):
                        setattr(self.settings, key, value)

                self._ensure_directories()
                self.save_config()

                logger.info(f"✅ 甘特图保存配置已导入: {import_path}")
                return True
            else:
                logger.error("❌ 导入文件格式不正确")
                return False

        except Exception as e:
            logger.error(f"❌ 导入甘特图保存配置失败: {e}")
            return False

# 全局配置管理器实例
_gantt_save_config_manager = None

def get_gantt_save_config_manager() -> GanttSaveConfigManager:
    """获取全局甘特图保存配置管理器实例"""
    global _gantt_save_config_manager
    if _gantt_save_config_manager is None:
        _gantt_save_config_manager = GanttSaveConfigManager()
    return _gantt_save_config_manager
