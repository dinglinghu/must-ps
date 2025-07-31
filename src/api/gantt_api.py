"""
甘特图Web API接口
提供甘特图的保存、加载、导出、分享等Web API功能
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from flask import Blueprint, request, jsonify, send_file, abort
import zipfile
import tempfile

from ..visualization.gantt_save_config_manager import get_gantt_save_config_manager
from ..visualization.gantt_file_manager import get_gantt_file_manager, GanttSearchFilter
from ..visualization.gantt_data_persistence import get_gantt_persistence_manager
from ..visualization.gantt_integration_manager import ConstellationGanttIntegrationManager

logger = logging.getLogger(__name__)

# 创建蓝图
gantt_api = Blueprint('gantt_api', __name__, url_prefix='/api/gantt')

@gantt_api.route('/save', methods=['POST'])
def save_gantt_chart():
    """保存甘特图"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': '缺少请求数据'}), 400
        
        # 获取参数
        gantt_data = data.get('gantt_data')
        chart_type = data.get('chart_type', 'unknown')
        mission_id = data.get('mission_id', 'UNKNOWN')
        format = data.get('format', 'json')
        compress = data.get('compress', False)
        
        if not gantt_data:
            return jsonify({'error': '缺少甘特图数据'}), 400
        
        # 获取管理器
        config_manager = get_gantt_save_config_manager()
        persistence_manager = get_gantt_persistence_manager()
        
        # 生成保存路径
        save_path = config_manager.get_save_path(chart_type, format, mission_id)
        
        # 保存数据
        saved_path = persistence_manager.save_gantt_data(
            gantt_data, save_path, format, compress
        )
        
        return jsonify({
            'success': True,
            'file_path': saved_path,
            'file_size': os.path.getsize(saved_path),
            'format': format,
            'save_time': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"❌ 保存甘特图失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/load/<file_id>', methods=['GET'])
def load_gantt_chart(file_id: str):
    """加载甘特图"""
    try:
        file_manager = get_gantt_file_manager()
        persistence_manager = get_gantt_persistence_manager()
        
        # 获取文件信息
        file_info = file_manager.get_file_info(file_id)
        if not file_info:
            return jsonify({'error': '文件不存在'}), 404
        
        # 加载数据
        gantt_data = persistence_manager.load_gantt_data(file_info.file_path)
        if not gantt_data:
            return jsonify({'error': '加载数据失败'}), 500
        
        return jsonify({
            'success': True,
            'gantt_data': gantt_data,
            'file_info': {
                'file_id': file_info.file_id,
                'file_name': file_info.file_name,
                'file_size': file_info.file_size,
                'format': file_info.format,
                'chart_type': file_info.chart_type,
                'mission_id': file_info.mission_id,
                'creation_time': file_info.creation_time.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"❌ 加载甘特图失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/search', methods=['POST'])
def search_gantt_charts():
    """搜索甘特图"""
    try:
        data = request.get_json() or {}
        
        # 构建搜索过滤器
        filter = GanttSearchFilter(
            chart_type=data.get('chart_type'),
            format=data.get('format'),
            mission_id=data.get('mission_id'),
            category=data.get('category'),
            keywords=data.get('keywords')
        )
        
        # 处理日期范围
        if data.get('date_from'):
            filter.date_from = datetime.fromisoformat(data['date_from'])
        if data.get('date_to'):
            filter.date_to = datetime.fromisoformat(data['date_to'])
        
        # 处理文件大小范围
        if data.get('min_size'):
            filter.min_size = int(data['min_size'])
        if data.get('max_size'):
            filter.max_size = int(data['max_size'])
        
        # 执行搜索
        file_manager = get_gantt_file_manager()
        files = file_manager.search_files(filter)
        
        # 转换结果
        results = []
        for file_info in files:
            results.append({
                'file_id': file_info.file_id,
                'file_name': file_info.file_name,
                'file_size': file_info.file_size,
                'format': file_info.format,
                'chart_type': file_info.chart_type,
                'mission_id': file_info.mission_id,
                'category': file_info.category,
                'creation_time': file_info.creation_time.isoformat(),
                'last_modified': file_info.last_modified.isoformat()
            })
        
        return jsonify({
            'success': True,
            'total_count': len(results),
            'files': results
        })
        
    except Exception as e:
        logger.error(f"❌ 搜索甘特图失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/export/<file_id>', methods=['GET'])
def export_gantt_chart(file_id: str):
    """导出甘特图文件"""
    try:
        file_manager = get_gantt_file_manager()
        
        # 获取文件信息
        file_info = file_manager.get_file_info(file_id)
        if not file_info:
            abort(404)
        
        file_path = Path(file_info.file_path)
        if not file_path.exists():
            abort(404)
        
        # 返回文件
        return send_file(
            file_path,
            as_attachment=True,
            download_name=file_info.file_name,
            mimetype=_get_mimetype(file_info.format)
        )
        
    except Exception as e:
        logger.error(f"❌ 导出甘特图失败: {e}")
        abort(500)

@gantt_api.route('/export/batch', methods=['POST'])
def export_gantt_charts_batch():
    """批量导出甘特图"""
    try:
        data = request.get_json()
        file_ids = data.get('file_ids', [])
        
        if not file_ids:
            return jsonify({'error': '缺少文件ID列表'}), 400
        
        file_manager = get_gantt_file_manager()
        
        # 创建临时ZIP文件
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as temp_file:
            with zipfile.ZipFile(temp_file.name, 'w') as zip_file:
                for file_id in file_ids:
                    file_info = file_manager.get_file_info(file_id)
                    if file_info and Path(file_info.file_path).exists():
                        zip_file.write(file_info.file_path, file_info.file_name)
            
            # 返回ZIP文件
            return send_file(
                temp_file.name,
                as_attachment=True,
                download_name=f'gantt_charts_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
                mimetype='application/zip'
            )
        
    except Exception as e:
        logger.error(f"❌ 批量导出甘特图失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/delete/<file_id>', methods=['DELETE'])
def delete_gantt_chart(file_id: str):
    """删除甘特图"""
    try:
        file_manager = get_gantt_file_manager()
        
        # 获取删除选项
        remove_physical = request.args.get('remove_physical', 'true').lower() == 'true'
        
        # 删除文件
        success = file_manager.delete_file(file_id, remove_physical)
        
        if success:
            return jsonify({'success': True, 'message': '文件已删除'})
        else:
            return jsonify({'error': '删除失败'}), 500
        
    except Exception as e:
        logger.error(f"❌ 删除甘特图失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/archive/<file_id>', methods=['POST'])
def archive_gantt_chart(file_id: str):
    """归档甘特图"""
    try:
        file_manager = get_gantt_file_manager()
        
        # 归档文件
        success = file_manager.archive_file(file_id)
        
        if success:
            return jsonify({'success': True, 'message': '文件已归档'})
        else:
            return jsonify({'error': '归档失败'}), 500
        
    except Exception as e:
        logger.error(f"❌ 归档甘特图失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/statistics', methods=['GET'])
def get_gantt_statistics():
    """获取甘特图统计信息"""
    try:
        file_manager = get_gantt_file_manager()
        config_manager = get_gantt_save_config_manager()
        
        # 获取统计信息
        file_stats = file_manager.get_statistics()
        save_stats = config_manager.get_save_statistics()
        
        return jsonify({
            'success': True,
            'file_statistics': file_stats,
            'save_statistics': save_stats
        })
        
    except Exception as e:
        logger.error(f"❌ 获取统计信息失败: {e}")
        return jsonify({'error': str(e)}), 500

@gantt_api.route('/config', methods=['GET', 'POST'])
def manage_gantt_config():
    """管理甘特图配置"""
    try:
        config_manager = get_gantt_save_config_manager()
        
        if request.method == 'GET':
            # 获取配置
            from dataclasses import asdict
            return jsonify({
                'success': True,
                'config': asdict(config_manager.settings)
            })
        
        elif request.method == 'POST':
            # 更新配置
            data = request.get_json()
            if not data:
                return jsonify({'error': '缺少配置数据'}), 400
            
            success = config_manager.update_settings(**data)
            
            if success:
                return jsonify({'success': True, 'message': '配置已更新'})
            else:
                return jsonify({'error': '配置更新失败'}), 500
        
    except Exception as e:
        logger.error(f"❌ 管理配置失败: {e}")
        return jsonify({'error': str(e)}), 500

def _get_mimetype(format: str) -> str:
    """获取MIME类型"""
    mimetypes = {
        'png': 'image/png',
        'svg': 'image/svg+xml',
        'pdf': 'application/pdf',
        'html': 'text/html',
        'json': 'application/json',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    }
    return mimetypes.get(format.lower(), 'application/octet-stream')
