#!/usr/bin/env python3
"""
讨论组系统分析脚本
分析当前系统实际使用的讨论组类型，确定保留哪种讨论组
"""

import os
import re
import logging
from pathlib import Path
from typing import Dict, List, Set
from collections import defaultdict

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DiscussionGroupAnalyzer:
    """讨论组使用情况分析器"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        
        # 讨论组类型和相关方法
        self.discussion_types = {
            'traditional': {
                'classes': ['DiscussionGroup', 'DiscussionGroupManager'],
                'methods': ['create_discussion_group', 'get_current_discussion_group'],
                'files': []
            },
            'adk_standard': {
                'classes': ['ADKStandardDiscussionSystem', 'ADKDiscussionCoordinator', 'ADKSequentialDiscussionGroup'],
                'methods': ['create_adk_standard_discussion', 'create_discussion'],
                'files': []
            },
            'adk_official': {
                'classes': ['ADKOfficialDiscussionSystem'],
                'methods': ['create_adk_official_discussion'],
                'files': []
            },
            'adk_parallel': {
                'classes': ['ADKParallelDiscussionGroupManager', 'ADKParallelDiscussionGroup'],
                'methods': ['create_discussion_group'],
                'files': []
            }
        }
        
        # 使用统计
        self.usage_stats = defaultdict(lambda: {
            'class_definitions': 0,
            'method_calls': 0,
            'imports': 0,
            'files_using': set(),
            'actual_calls': []
        })
    
    def analyze_project(self):
        """分析整个项目的讨论组使用情况"""
        logger.info("🔍 开始分析项目讨论组使用情况...")
        
        # 扫描所有Python文件
        python_files = list(self.project_root.rglob("*.py"))
        logger.info(f"📁 找到 {len(python_files)} 个Python文件")
        
        for file_path in python_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                self._analyze_file(file_path)
            except Exception as e:
                logger.warning(f"⚠️ 分析文件失败 {file_path}: {e}")
        
        # 生成分析报告
        self._generate_analysis_report()
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """判断是否应该跳过文件"""
        skip_patterns = [
            '__pycache__',
            '.git',
            'venv',
            'env',
            '.pytest_cache',
            'node_modules'
        ]
        
        return any(pattern in str(file_path) for pattern in skip_patterns)
    
    def _analyze_file(self, file_path: Path):
        """分析单个文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            relative_path = file_path.relative_to(self.project_root)
            
            # 分析每种讨论组类型
            for discussion_type, config in self.discussion_types.items():
                self._analyze_discussion_type_in_file(
                    content, str(relative_path), discussion_type, config
                )
                
        except Exception as e:
            logger.debug(f"读取文件失败 {file_path}: {e}")
    
    def _analyze_discussion_type_in_file(self, content: str, file_path: str, discussion_type: str, config: Dict):
        """分析文件中特定讨论组类型的使用"""
        stats = self.usage_stats[discussion_type]
        
        # 检查类定义
        for class_name in config['classes']:
            if re.search(rf'class\s+{class_name}\b', content):
                stats['class_definitions'] += 1
                stats['files_using'].add(file_path)
                logger.debug(f"📝 {file_path}: 定义了类 {class_name}")
        
        # 检查方法调用
        for method_name in config['methods']:
            # 查找方法调用
            method_calls = re.findall(rf'(\w+\.)?{method_name}\s*\(', content)
            if method_calls:
                stats['method_calls'] += len(method_calls)
                stats['files_using'].add(file_path)
                stats['actual_calls'].extend([f"{file_path}:{method_name}" for _ in method_calls])
                logger.debug(f"🔧 {file_path}: 调用了方法 {method_name} ({len(method_calls)}次)")
        
        # 检查导入
        for class_name in config['classes']:
            if re.search(rf'from\s+.*import\s+.*{class_name}', content) or \
               re.search(rf'import\s+.*{class_name}', content):
                stats['imports'] += 1
                stats['files_using'].add(file_path)
                logger.debug(f"📦 {file_path}: 导入了 {class_name}")
    
    def _generate_analysis_report(self):
        """生成分析报告"""
        logger.info("\n" + "="*80)
        logger.info("📊 讨论组使用情况分析报告")
        logger.info("="*80)
        
        # 按使用频率排序
        sorted_types = sorted(
            self.usage_stats.items(),
            key=lambda x: x[1]['method_calls'] + x[1]['class_definitions'] + x[1]['imports'],
            reverse=True
        )
        
        total_usage = 0
        for discussion_type, stats in sorted_types:
            usage_score = stats['method_calls'] + stats['class_definitions'] + stats['imports']
            total_usage += usage_score
            
            logger.info(f"\n🔍 {discussion_type.upper()} 讨论组:")
            logger.info(f"   类定义: {stats['class_definitions']} 个")
            logger.info(f"   方法调用: {stats['method_calls']} 次")
            logger.info(f"   导入语句: {stats['imports']} 次")
            logger.info(f"   使用文件: {len(stats['files_using'])} 个")
            logger.info(f"   总使用分数: {usage_score}")
            
            if stats['files_using']:
                logger.info(f"   主要使用文件:")
                for file_path in sorted(stats['files_using'])[:5]:  # 显示前5个
                    logger.info(f"     - {file_path}")
            
            if stats['actual_calls']:
                logger.info(f"   实际调用示例:")
                for call in stats['actual_calls'][:3]:  # 显示前3个
                    logger.info(f"     - {call}")
        
        # 生成建议
        logger.info("\n" + "="*80)
        logger.info("💡 分析结论和建议")
        logger.info("="*80)
        
        if total_usage == 0:
            logger.info("⚠️ 未检测到任何讨论组的使用")
            return
        
        # 找出主要使用的讨论组类型
        primary_type = sorted_types[0][0] if sorted_types else None
        primary_stats = sorted_types[0][1] if sorted_types else {}
        
        if primary_type and primary_stats['method_calls'] > 0:
            logger.info(f"🎯 主要使用的讨论组类型: {primary_type.upper()}")
            logger.info(f"   使用频率: {primary_stats['method_calls']} 次方法调用")
            logger.info(f"   涉及文件: {len(primary_stats['files_using'])} 个")
            
            # 检查是否有其他显著使用的类型
            significant_types = [
                (t, s) for t, s in sorted_types 
                if s['method_calls'] > 0 and t != primary_type
            ]
            
            if significant_types:
                logger.info(f"\n📋 其他使用的讨论组类型:")
                for disc_type, stats in significant_types:
                    logger.info(f"   - {disc_type}: {stats['method_calls']} 次调用")
            
            # 生成删除建议
            logger.info(f"\n🗑️ 删除建议:")
            unused_types = [t for t, s in sorted_types if s['method_calls'] == 0]
            if unused_types:
                logger.info(f"   可以安全删除的讨论组类型:")
                for unused_type in unused_types:
                    logger.info(f"     - {unused_type}")
            
            # 生成保留建议
            used_types = [t for t, s in sorted_types if s['method_calls'] > 0]
            if used_types:
                logger.info(f"   建议保留的讨论组类型:")
                for used_type in used_types:
                    stats = dict(sorted_types)[used_type]
                    logger.info(f"     - {used_type} (调用 {stats['method_calls']} 次)")
        
        else:
            logger.info("⚠️ 未检测到活跃的讨论组方法调用")
            logger.info("   可能所有讨论组都是定义但未使用的")
    
    def get_deletion_plan(self) -> Dict[str, List[str]]:
        """获取删除计划"""
        deletion_plan = {
            'files_to_delete': [],
            'classes_to_remove': [],
            'methods_to_remove': [],
            'imports_to_clean': []
        }
        
        # 找出未使用的讨论组类型
        for discussion_type, stats in self.usage_stats.items():
            if stats['method_calls'] == 0:  # 没有实际方法调用
                config = self.discussion_types[discussion_type]
                deletion_plan['classes_to_remove'].extend(config['classes'])
                deletion_plan['methods_to_remove'].extend(config['methods'])
        
        return deletion_plan

def main():
    """主函数"""
    project_root = Path(__file__).parent
    
    analyzer = DiscussionGroupAnalyzer(str(project_root))
    analyzer.analyze_project()
    
    # 获取删除计划
    deletion_plan = analyzer.get_deletion_plan()
    
    if deletion_plan['classes_to_remove']:
        logger.info(f"\n🗑️ 删除计划:")
        logger.info(f"   待删除的类: {deletion_plan['classes_to_remove']}")
        logger.info(f"   待删除的方法: {deletion_plan['methods_to_remove']}")
    else:
        logger.info(f"\n✅ 所有讨论组类型都在使用中，无需删除")

if __name__ == "__main__":
    main()
