#!/usr/bin/env python3
"""
讨论组清理计划
基于系统分析结果，删除未使用的讨论组类型
"""

import os
import logging
from pathlib import Path
from typing import List, Dict

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiscussionGroupCleanup:
    """讨论组清理器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        
        # 基于分析结果的删除计划
        self.cleanup_plan = {
            # 保留的讨论组（实际使用中）
            'keep': {
                'adk_parallel': {
                    'reason': '滚动规划主要使用',
                    'files': [
                        'src/agents/adk_parallel_discussion_group.py'
                    ],
                    'classes': ['ADKParallelDiscussionGroupManager', 'ADKParallelDiscussionGroup']
                },
                'adk_official': {
                    'reason': '仿真调度智能体使用',
                    'files': [
                        'src/agents/adk_official_discussion_system.py'
                    ],
                    'classes': ['ADKOfficialDiscussionSystem']
                }
            },
            
            # 删除的讨论组（未实际使用或重复）
            'remove': {
                'traditional': {
                    'reason': '被ADK Parallel替代，未在主流程使用',
                    'files': [
                        'core/agents/discussion_group.py',
                        'core/agents/discussion_group_manager.py',
                        'src/agents/discussion_group.py',
                        'src/agents/discussion_group_manager.py'
                    ],
                    'classes': ['DiscussionGroup', 'DiscussionGroupManager']
                },
                'adk_standard': {
                    'reason': '功能与ADK Parallel重复，未在主流程使用',
                    'files': [
                        'core/agents/adk_standard_discussion_system.py',
                        'src/agents/adk_standard_discussion_system.py'
                    ],
                    'classes': ['ADKStandardDiscussionSystem', 'ADKDiscussionCoordinator', 'ADKSequentialDiscussionGroup']
                }
            }
        }
    
    def analyze_current_usage(self):
        """分析当前使用情况"""
        logger.info("📊 当前系统讨论组使用分析:")
        logger.info("="*60)
        
        logger.info("🎯 主要使用场景:")
        logger.info("  1. 滚动规划周期管理器 → ADK Parallel讨论组管理器")
        logger.info("     - 文件: demos/demo_complete_system.py:148")
        logger.info("     - 文件: test_discussion_group_dissolution.py:66")
        logger.info("     - 调用: planning_cycle_manager.set_discussion_group_manager(ADKParallelDiscussionGroupManager)")
        
        logger.info("  2. 仿真调度智能体 → ADK官方讨论系统")
        logger.info("     - 文件: src/agents/simulation_scheduler_agent.py:2782")
        logger.info("     - 调用: multi_agent_system.create_adk_official_discussion()")
        
        logger.info("\n⚠️ 未使用或重复的讨论组:")
        logger.info("  1. 传统讨论组 (DiscussionGroup/DiscussionGroupManager)")
        logger.info("     - 只在测试和导入中出现，未在主流程使用")
        logger.info("     - 功能已被ADK Parallel讨论组完全替代")
        
        logger.info("  2. ADK标准讨论组 (ADKStandardDiscussionSystem)")
        logger.info("     - 与ADK Parallel功能重复")
        logger.info("     - 未在主要业务流程中使用")
        
        logger.info("\n✅ 建议保留:")
        for keep_type, info in self.cleanup_plan['keep'].items():
            logger.info(f"  - {keep_type}: {info['reason']}")
        
        logger.info("\n🗑️ 建议删除:")
        for remove_type, info in self.cleanup_plan['remove'].items():
            logger.info(f"  - {remove_type}: {info['reason']}")
    
    def execute_cleanup(self, dry_run: bool = True):
        """执行清理操作"""
        logger.info(f"\n{'🔍 模拟' if dry_run else '🗑️ 执行'}清理操作:")
        logger.info("="*60)
        
        total_files_to_remove = 0
        total_classes_to_remove = 0
        
        for remove_type, info in self.cleanup_plan['remove'].items():
            logger.info(f"\n📁 处理 {remove_type} 讨论组:")
            
            # 删除文件
            for file_path in info['files']:
                full_path = self.project_root / file_path
                if full_path.exists():
                    if dry_run:
                        logger.info(f"  🔍 将删除文件: {file_path}")
                    else:
                        try:
                            full_path.unlink()
                            logger.info(f"  ✅ 已删除文件: {file_path}")
                        except Exception as e:
                            logger.error(f"  ❌ 删除文件失败 {file_path}: {e}")
                    total_files_to_remove += 1
                else:
                    logger.info(f"  ⚠️ 文件不存在: {file_path}")
            
            # 统计类
            total_classes_to_remove += len(info['classes'])
            logger.info(f"  📝 涉及类: {', '.join(info['classes'])}")
        
        # 清理导入引用
        self._cleanup_imports(dry_run)
        
        logger.info(f"\n📊 清理统计:")
        logger.info(f"  文件: {total_files_to_remove} 个")
        logger.info(f"  类: {total_classes_to_remove} 个")
        
        if dry_run:
            logger.info(f"\n💡 这是模拟运行，实际文件未被删除")
            logger.info(f"   要执行实际删除，请运行: python {__file__} --execute")
    
    def _cleanup_imports(self, dry_run: bool = True):
        """清理导入引用"""
        logger.info(f"\n🔧 清理导入引用:")
        
        # 需要清理导入的文件
        files_to_clean = [
            'core/agents/__init__.py',
            'src/agents/__init__.py',
            'src/ui/adk_monitoring_ui.py',
            'demos/demo_complete_system.py',
            'main.py'
        ]
        
        # 需要移除的导入
        imports_to_remove = [
            'from core.agents.discussion_group import DiscussionGroup',
            'from core.agents.discussion_group_manager import DiscussionGroupManager',
            'from src.agents.discussion_group import DiscussionGroup',
            'from src.agents.discussion_group_manager import DiscussionGroupManager',
            'from core.agents.adk_standard_discussion_system import ADKStandardDiscussionSystem',
            'from src.agents.adk_standard_discussion_system import ADKStandardDiscussionSystem',
            'import core.agents.discussion_group',
            'import src.agents.discussion_group',
            'import core.agents.adk_standard_discussion_system',
            'import src.agents.adk_standard_discussion_system'
        ]
        
        for file_path in files_to_clean:
            full_path = self.project_root / file_path
            if full_path.exists():
                if dry_run:
                    logger.info(f"  🔍 将清理导入: {file_path}")
                else:
                    self._clean_file_imports(full_path, imports_to_remove)
            else:
                logger.info(f"  ⚠️ 文件不存在: {file_path}")
    
    def _clean_file_imports(self, file_path: Path, imports_to_remove: List[str]):
        """清理单个文件的导入"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            lines = content.split('\n')
            cleaned_lines = []
            
            for line in lines:
                should_remove = False
                for import_to_remove in imports_to_remove:
                    if import_to_remove.strip() in line.strip():
                        should_remove = True
                        break
                
                if not should_remove:
                    cleaned_lines.append(line)
                else:
                    logger.info(f"    ✂️ 移除导入: {line.strip()}")
            
            if len(cleaned_lines) != len(lines):
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write('\n'.join(cleaned_lines))
                logger.info(f"  ✅ 已清理导入: {file_path}")
            else:
                logger.info(f"  ℹ️ 无需清理: {file_path}")
                
        except Exception as e:
            logger.error(f"  ❌ 清理导入失败 {file_path}: {e}")
    
    def generate_migration_guide(self):
        """生成迁移指南"""
        logger.info(f"\n📖 迁移指南:")
        logger.info("="*60)
        
        logger.info("🔄 如果代码中使用了被删除的讨论组，请按以下方式迁移:")
        
        logger.info("\n1. 传统讨论组 → ADK Parallel讨论组:")
        logger.info("   旧代码:")
        logger.info("     from src.agents.discussion_group_manager import DiscussionGroupManager")
        logger.info("     manager = DiscussionGroupManager()")
        logger.info("   新代码:")
        logger.info("     from src.agents.adk_parallel_discussion_group import ADKParallelDiscussionGroupManager")
        logger.info("     manager = ADKParallelDiscussionGroupManager()")
        
        logger.info("\n2. ADK标准讨论组 → ADK Parallel讨论组:")
        logger.info("   旧代码:")
        logger.info("     from src.agents.adk_standard_discussion_system import ADKStandardDiscussionSystem")
        logger.info("     system = ADKStandardDiscussionSystem()")
        logger.info("   新代码:")
        logger.info("     from src.agents.adk_parallel_discussion_group import ADKParallelDiscussionGroupManager")
        logger.info("     manager = ADKParallelDiscussionGroupManager()")
        
        logger.info("\n3. 方法调用迁移:")
        logger.info("   旧方法: create_discussion_group()")
        logger.info("   新方法: create_discussion_group_for_planning_cycle()")
        
        logger.info("\n✅ 保留的讨论组系统:")
        logger.info("   - ADK Parallel讨论组: 用于滚动规划")
        logger.info("   - ADK官方讨论组: 用于仿真调度")

def main():
    """主函数"""
    import sys
    
    project_root = Path(__file__).parent
    cleanup = DiscussionGroupCleanup(str(project_root))
    
    # 分析当前使用情况
    cleanup.analyze_current_usage()
    
    # 检查命令行参数
    execute_cleanup = '--execute' in sys.argv
    
    # 执行清理
    cleanup.execute_cleanup(dry_run=not execute_cleanup)
    
    # 生成迁移指南
    cleanup.generate_migration_guide()
    
    if not execute_cleanup:
        logger.info(f"\n💡 要执行实际删除，请运行:")
        logger.info(f"   python {__file__} --execute")

if __name__ == "__main__":
    main()
