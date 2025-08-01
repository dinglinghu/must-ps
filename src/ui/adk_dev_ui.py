"""
ADK Development UI - 严格基于Google ADK官方设计的多智能体系统管理界面
Official ADK Design Reference: https://github.com/google/adk-java
Documentation: https://google.github.io/adk-docs/

This UI follows the exact design patterns and conventions from the official ADK framework,
providing a professional development environment for multi-agent systems.
"""

import logging
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import sys
import uuid
import concurrent.futures
import functools

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Web框架导入
try:
    from flask import Flask, render_template, request, jsonify, send_from_directory
    from flask_socketio import SocketIO, emit
    import threading
    WEB_AVAILABLE = True
except ImportError:
    print("⚠️ Flask未安装，请运行: pip install flask flask-socketio")
    WEB_AVAILABLE = False
    sys.exit(1)

# ADK和多智能体系统导入
from src.agents.multi_agent_system import MultiAgentSystem
from src.agents.simulation_scheduler_agent import SimulationSchedulerAgent
from src.agents.satellite_agent import SatelliteAgent
from src.agents.leader_agent import LeaderAgent
from src.utils.llm_config_manager import get_llm_config_manager

logger = logging.getLogger(__name__)


class ADKDevUI:
    """ADK开发UI管理器"""
    
    def __init__(self, host: str = "localhost", port: int = 8080):
        """
        初始化ADK开发UI
        
        Args:
            host: 服务器主机
            port: 服务器端口
        """
        self.host = host
        self.port = port
        self.app = Flask(__name__, 
                        template_folder=str(Path(__file__).parent / "templates"),
                        static_folder=str(Path(__file__).parent / "static"))
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")
        
        # 多智能体系统实例
        self.multi_agent_system: Optional[MultiAgentSystem] = None
        self.system_status = {
            'is_running': False,
            'agents': {},
            'sessions': {},
            'logs': []
        }

        # 线程池执行器，用于处理可能的异步操作
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        
        # 设置路由
        self._setup_routes()
        self._setup_socketio_events()
        
        logger.info(f"🌐 ADK开发UI初始化完成: http://{host}:{port}")
    
    def _setup_routes(self):
        """设置Web路由"""
        
        @self.app.route('/')
        def index():
            """主页"""
            return render_template('index.html')
        
        @self.app.route('/agents')
        def agents_page():
            """智能体管理页面"""
            return render_template('agents.html')
        
        @self.app.route('/sessions')
        def sessions_page():
            """会话管理页面"""
            return render_template('sessions.html')

        @self.app.route('/discussion-groups')
        def discussion_groups_page():
            """讨论组监控页面"""
            return render_template('discussion_groups.html')
        
        @self.app.route('/tools')
        def tools_page():
            """工具管理页面"""
            return render_template('tools.html')

        @self.app.route('/config')
        def config_page():
            """配置管理页面"""
            return render_template('config.html')

        @self.app.route('/gantt_charts')
        def gantt_charts_page():
            """甘特图展示页面"""
            return render_template('gantt_charts.html')

        @self.app.route('/logs')
        def logs_page():
            """日志查看页面"""
            return render_template('logs.html')
        
        @self.app.route('/api/system/status')
        def get_system_status():
            """获取系统状态API"""
            if self.multi_agent_system:
                status = self.multi_agent_system.get_system_status()
                return jsonify(status)
            return jsonify({'error': '系统未初始化'})
        
        @self.app.route('/api/system/start', methods=['POST'])
        def start_system():
            """启动系统API"""
            try:
                config_path = request.json.get('config_path', 'config/config.yaml')
                output_dir = request.json.get('output_dir', 'output')

                # 在线程池中创建多智能体系统，避免事件循环冲突
                def create_system_safe():
                    """在独立线程中安全创建系统"""
                    try:
                        # 确保在新线程中没有事件循环冲突
                        return MultiAgentSystem(
                            config_path=config_path,
                            output_dir=output_dir
                        )
                    except Exception as e:
                        logger.error(f"线程中创建系统失败: {e}")
                        raise

                # 使用线程池执行器
                future = self.executor.submit(create_system_safe)
                self.multi_agent_system = future.result(timeout=30)  # 30秒超时

                self.system_status['is_running'] = True
                self._log_message("系统启动成功")

                return jsonify({'success': True, 'message': '系统启动成功'})
            except concurrent.futures.TimeoutError:
                self._log_message("系统启动超时", level='error')
                return jsonify({'success': False, 'error': '系统启动超时'})
            except Exception as e:
                self._log_message(f"系统启动失败: {e}", level='error')
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/system/stop', methods=['POST'])
        def stop_system():
            """停止系统API"""
            try:
                if self.multi_agent_system:
                    # 这里可以添加系统清理逻辑
                    self.multi_agent_system = None
                
                self.system_status['is_running'] = False
                self._log_message("系统已停止")
                
                return jsonify({'success': True, 'message': '系统已停止'})
            except Exception as e:
                self._log_message(f"系统停止失败: {e}", level='error')
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/agents/list')
        def list_agents():
            """获取智能体列表API"""
            if not self.multi_agent_system:
                return jsonify({'agents': []})
            
            agents = []
            
            # 仿真调度智能体
            if self.multi_agent_system.simulation_scheduler:
                agents.append({
                    'id': 'simulation_scheduler',
                    'name': 'SimulationScheduler',
                    'type': 'LlmAgent',
                    'status': 'active' if self.multi_agent_system.simulation_scheduler.is_running else 'idle',
                    'description': '仿真调度智能体'
                })
            
            # 卫星智能体
            for sat_id, agent in self.multi_agent_system.satellite_agents.items():
                agents.append({
                    'id': sat_id,
                    'name': agent.name,
                    'type': 'SatelliteAgent',
                    'status': 'active',
                    'description': f'卫星智能体 - {sat_id}'
                })
            
            # 组长智能体
            for leader_id, agent in self.multi_agent_system.leader_agents.items():
                agents.append({
                    'id': leader_id,
                    'name': agent.name,
                    'type': 'LeaderAgent',
                    'status': 'active',
                    'description': f'组长智能体 - {leader_id}'
                })
            
            return jsonify({'agents': agents})
        
        @self.app.route('/api/agents/<agent_id>/details')
        def get_agent_details(agent_id):
            """获取智能体详细信息API"""
            if not self.multi_agent_system:
                return jsonify({'error': '系统未初始化'})
            
            # 查找智能体
            agent = None
            if agent_id == 'simulation_scheduler':
                agent = self.multi_agent_system.simulation_scheduler
            elif agent_id in self.multi_agent_system.satellite_agents:
                agent = self.multi_agent_system.satellite_agents[agent_id]
            elif agent_id in self.multi_agent_system.leader_agents:
                agent = self.multi_agent_system.leader_agents[agent_id]
            
            if not agent:
                return jsonify({'error': '智能体未找到'})
            
            details = {
                'id': agent_id,
                'name': agent.name,
                'type': type(agent).__name__,
                'description': getattr(agent, 'description', ''),
                'tools': [tool.__class__.__name__ for tool in getattr(agent, 'tools', [])],
                'status': 'active'
            }
            
            return jsonify(details)

        @self.app.route('/api/discussion-groups')
        def get_discussion_groups():
            """获取讨论组列表API - 仅支持ADK标准讨论系统"""
            try:
                if not self.multi_agent_system:
                    return jsonify({'error': '多智能体系统未启动', 'groups': []})

                # 只从ADK标准讨论系统获取讨论组信息
                groups = []

                try:
                    if hasattr(self.multi_agent_system, '_adk_standard_discussion_system'):
                        # 使用全局Session管理器获取ADK标准讨论组
                        from src.utils.adk_session_manager import get_adk_session_manager

                        session_manager = get_adk_session_manager()
                        adk_standard_discussions = session_manager.get_adk_discussions()

                        for discussion_id, discussion_info in adk_standard_discussions.items():
                            groups.append({
                                'group_id': discussion_id,
                                'target_id': discussion_info.get('task_description', 'ADK_Standard_Discussion')[:50],
                                'missile_id': 'N/A',
                                'status': discussion_info.get('status', 'active'),
                                'participants': discussion_info.get('participants', []),
                                'leader': discussion_info.get('participants', ['N/A'])[0] if discussion_info.get('participants') else 'N/A',
                                'created_time': discussion_info.get('created_time', ''),
                                'coordination_rounds': 0,
                                'max_rounds': 1,
                                'timeout': 600,
                                'session_type': f"ADK_Standard_{discussion_info.get('type', 'Unknown').title()}",
                                'source': 'adk_standard_discussion_system',
                                'discussion_type': discussion_info.get('type', 'unknown'),
                                'agent_class': discussion_info.get('agent_class', 'Unknown')
                            })

                        logger.info("✅ 成功检查ADK标准讨论系统")
                except Exception as e:
                    logger.warning(f"获取ADK标准讨论组信息失败: {e}")

                return jsonify({'groups': groups})

            except Exception as e:
                logger.error(f"获取讨论组列表失败: {e}")
                return jsonify({'error': str(e), 'groups': []})

        @self.app.route('/api/discussion-groups/debug')
        def debug_discussion_groups():
            """调试API - ADK标准讨论系统状态诊断"""
            try:
                debug_info = {
                    'multi_agent_system_status': 'not_initialized',
                    'adk_standard_discussion_system_status': 'not_found',
                    'discussion_groups_total': 0,
                    'detailed_sources': {},
                    'system_diagnostics': {}
                }

                if not self.multi_agent_system:
                    return jsonify(debug_info)

                debug_info['multi_agent_system_status'] = 'initialized'

                # 只检查ADK标准讨论系统
                if hasattr(self.multi_agent_system, '_adk_standard_discussion_system'):
                    debug_info['adk_standard_discussion_system_status'] = 'found'
                    try:
                        # 使用全局Session管理器检查ADK标准讨论组
                        from src.utils.adk_session_manager import get_adk_session_manager

                        session_manager = get_adk_session_manager()
                        standard_discussions = session_manager.get_adk_discussions()
                        session_stats = session_manager.get_statistics()

                        debug_info['detailed_sources']['adk_standard_discussions_count'] = len(standard_discussions)
                        debug_info['discussion_groups_total'] = len(standard_discussions)

                        # 详细的ADK标准讨论组信息
                        debug_info['detailed_sources']['adk_standard_discussions_detail'] = {}
                        for discussion_id, discussion_info in standard_discussions.items():
                            debug_info['detailed_sources']['adk_standard_discussions_detail'][discussion_id] = {
                                'type': discussion_info.get('type', 'unknown'),
                                'participants_count': len(discussion_info.get('participants', [])),
                                'status': discussion_info.get('status', 'unknown'),
                                'agent_class': discussion_info.get('agent_class', 'Unknown')
                            }

                        # 添加Session管理器统计信息
                        debug_info['detailed_sources']['session_manager_stats'] = session_stats

                    except Exception as e:
                        debug_info['detailed_sources']['adk_standard_discussions_error'] = str(e)

                return jsonify(debug_info)

            except Exception as e:
                logger.error(f"调试讨论组状态失败: {e}")
                return jsonify({'error': str(e), 'debug_info': debug_info})

        @self.app.route('/api/discussion-groups/list')
        def list_discussion_groups():
            """列出ADK标准讨论组的简要信息"""
            try:
                if not self.multi_agent_system:
                    return jsonify({'groups': []})

                groups = []

                # 只从ADK标准讨论系统获取
                try:
                    if hasattr(self.multi_agent_system, '_adk_standard_discussion_system'):
                        from src.utils.adk_session_manager import get_adk_session_manager

                        session_manager = get_adk_session_manager()
                        adk_standard_discussions = session_manager.get_adk_discussions()

                        for discussion_id, discussion_info in adk_standard_discussions.items():
                            groups.append({
                                'id': discussion_id,
                                'name': f"adk_standard_{discussion_info.get('type', 'unknown')}",
                                'type': f"ADK_Standard_{discussion_info.get('type', 'Unknown').title()}",
                                'status': discussion_info.get('status', 'active'),
                                'participants_count': len(discussion_info.get('participants', []))
                            })
                except Exception as e:
                    logger.warning(f"获取ADK标准讨论组列表失败: {e}")

                return jsonify({'groups': groups})

            except Exception as e:
                logger.error(f"列出讨论组失败: {e}")
                return jsonify({'error': str(e), 'groups': []})

        @self.app.route('/api/discussion-groups/<group_id>/details')
        def get_discussion_group_details(group_id):
            """获取ADK标准讨论组详细信息API"""
            try:
                if not self.multi_agent_system:
                    return jsonify({'error': '多智能体系统未启动'})

                # 从ADK标准讨论系统获取讨论组详细信息
                try:
                    if hasattr(self.multi_agent_system, '_adk_standard_discussion_system'):
                        from src.utils.adk_session_manager import get_adk_session_manager

                        session_manager = get_adk_session_manager()
                        adk_standard_discussions = session_manager.get_adk_discussions()

                        group_info = adk_standard_discussions.get(group_id)
                        if not group_info:
                            return jsonify({'error': f'ADK标准讨论组 {group_id} 不存在'})

                        details = {
                            'group_id': group_id,
                            'target_id': group_info.get('task_description', 'ADK_Standard_Discussion')[:50],
                            'missile_id': 'N/A',
                            'status': group_info.get('status', 'active'),
                            'participants': group_info.get('participants', []),
                            'leader': group_info.get('participants', ['N/A'])[0] if group_info.get('participants') else 'N/A',
                            'created_time': group_info.get('created_time', ''),
                            'coordination_rounds': 0,
                            'max_rounds': 1,
                            'timeout': 600,
                            'discussion_type': group_info.get('type', 'unknown'),
                            'agent_class': group_info.get('agent_class', 'Unknown'),
                            'task_description': group_info.get('task_description', ''),
                            'session_type': f"ADK_Standard_{group_info.get('type', 'Unknown').title()}",
                            'source': 'adk_standard_discussion_system'
                        }

                        return jsonify(details)
                    else:
                        return jsonify({'error': 'ADK标准讨论系统未初始化'})

                except Exception as e:
                    return jsonify({'error': f'获取ADK标准讨论组详情失败: {str(e)}'})

            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/logs')
        def get_logs():
            """获取日志API"""
            return jsonify({'logs': self.system_status['logs']})

        @self.app.route('/api/config/llm')
        def get_llm_config():
            """获取大模型配置API"""
            try:
                llm_config_mgr = get_llm_config_manager()

                # 获取主要配置
                primary_config = llm_config_mgr.get_llm_config()

                # 获取智能体特定配置
                agent_configs = {}
                for agent_type in ['simulation_scheduler', 'satellite_agents', 'leader_agents']:
                    config = llm_config_mgr.get_llm_config(agent_type)
                    agent_configs[agent_type] = {
                        'provider': config.provider,
                        'model': config.model,
                        'max_tokens': config.max_tokens,
                        'temperature': config.temperature
                    }

                # 获取备用配置
                fallback_configs = []
                for config in llm_config_mgr.get_fallback_configs():
                    fallback_configs.append({
                        'provider': config.provider,
                        'model': config.model,
                        'api_key_configured': bool(config.api_key)
                    })

                return jsonify({
                    'primary': {
                        'provider': primary_config.provider,
                        'model': primary_config.model,
                        'max_tokens': primary_config.max_tokens,
                        'temperature': primary_config.temperature,
                        'api_key_configured': bool(primary_config.api_key)
                    },
                    'agent_specific': agent_configs,
                    'fallback': fallback_configs,
                    'performance': llm_config_mgr.get_performance_config(),
                    'security': llm_config_mgr.get_security_config()
                })

            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/config/prompts')
        def get_prompts_config():
            """获取提示词配置API"""
            try:
                llm_config_mgr = get_llm_config_manager()

                prompts = {}
                for agent_type in ['simulation_scheduler', 'satellite_agents', 'leader_agents']:
                    prompt_config = llm_config_mgr.get_agent_prompt_config(agent_type)
                    prompts[agent_type] = {
                        'system_prompt_length': len(prompt_config.system_prompt),
                        'user_template_length': len(prompt_config.user_prompt_template),
                        'examples_count': len(prompt_config.few_shot_examples)
                    }

                common_instructions = llm_config_mgr.get_common_instructions()

                return jsonify({
                    'agent_prompts': prompts,
                    'common_instructions': {
                        'global_instructions_length': len(common_instructions.get('global_instructions', '')),
                        'error_handling_length': len(common_instructions.get('error_handling', '')),
                        'collaboration_length': len(common_instructions.get('collaboration', '')),
                        'security_length': len(common_instructions.get('security', ''))
                    }
                })

            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/logs/stream')
        def stream_logs():
            """获取实时日志流API"""
            return jsonify({
                'logs': self.system_status['logs'][-100:],  # 返回最近100条日志
                'total_count': len(self.system_status['logs'])
            })

        @self.app.route('/api/simulation/sessions')
        def get_simulation_sessions():
            """获取仿真会话列表API"""
            try:
                from src.utils.simulation_result_manager import get_simulation_result_manager
                result_manager = get_simulation_result_manager()

                # 扫描仿真结果目录
                sessions = []
                base_dir = Path(result_manager.base_output_dir)

                if base_dir.exists():
                    for session_dir in base_dir.iterdir():
                        if session_dir.is_dir():
                            session_info_file = session_dir / "session_info.json"
                            if session_info_file.exists():
                                try:
                                    with open(session_info_file, 'r', encoding='utf-8') as f:
                                        session_info = json.load(f)
                                    sessions.append(session_info)
                                except Exception as e:
                                    logger.warning(f"读取会话信息失败: {session_dir.name}, {e}")

                return jsonify({'sessions': sessions})

            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/simulation/sessions/<session_id>/gantt_files')
        def get_gantt_files(session_id):
            """获取指定会话的甘特图文件列表API"""
            try:
                from src.utils.simulation_result_manager import get_simulation_result_manager
                result_manager = get_simulation_result_manager()

                chart_type = request.args.get('type', 'all')

                # 查找会话目录
                base_dir = Path(result_manager.base_output_dir)
                session_dir = None

                for dir_path in base_dir.iterdir():
                    if dir_path.is_dir() and session_id in dir_path.name:
                        session_dir = dir_path
                        break

                if not session_dir:
                    return jsonify({'error': '会话未找到'})

                gantt_dir = session_dir / "gantt_charts"
                files = []

                if gantt_dir.exists():
                    for file_path in gantt_dir.iterdir():
                        if file_path.suffix == '.json':
                            # 根据文件名判断类型
                            if chart_type == 'all' or chart_type in file_path.name:
                                files.append({
                                    'filename': file_path.name,
                                    'display_name': file_path.stem.replace('_', ' ').title(),
                                    'created_time': datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                                    'size': file_path.stat().st_size
                                })

                return jsonify({'files': files})

            except Exception as e:
                return jsonify({'error': str(e)})

        # 注册甘特图API蓝图
        try:
            from src.api.gantt_api import gantt_api
            self.app.register_blueprint(gantt_api)
            logger.info("✅ 甘特图API已注册")
        except ImportError as e:
            logger.warning(f"⚠️ 甘特图API注册失败: {e}")

        @self.app.route('/api/simulation/sessions/<session_id>/gantt_data/<filename>')
        def get_gantt_data(session_id, filename):
            """获取甘特图数据API"""
            try:
                from src.utils.simulation_result_manager import get_simulation_result_manager
                result_manager = get_simulation_result_manager()

                # 查找会话目录
                base_dir = Path(result_manager.base_output_dir)
                session_dir = None

                for dir_path in base_dir.iterdir():
                    if dir_path.is_dir() and session_id in dir_path.name:
                        session_dir = dir_path
                        break

                if not session_dir:
                    return jsonify({'error': '会话未找到'})

                gantt_file = session_dir / "gantt_charts" / filename

                if not gantt_file.exists():
                    return jsonify({'error': '甘特图文件未找到'})

                with open(gantt_file, 'r', encoding='utf-8') as f:
                    gantt_data = json.load(f)

                return jsonify(gantt_data)

            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/agents/<agent_id>/send_message', methods=['POST'])
        def send_agent_message(agent_id):
            """发送消息给智能体API"""
            try:
                data = request.get_json()
                message = data.get('message', '')

                if not message:
                    return jsonify({'success': False, 'error': '消息不能为空'})

                # 记录用户发送的消息
                self._log_message(f"👤 用户 → 智能体 {agent_id}: {message}")

                # 通过SocketIO发送消息
                self.socketio.emit('run_agent', {
                    'agent_id': agent_id,
                    'message': message
                })

                return jsonify({'success': True, 'message': '消息已发送'})

            except Exception as e:
                self._log_message(f"❌ 发送消息失败: {e}", level='error')
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/static/<path:filename>')
        def static_files(filename):
            """静态文件服务"""
            return send_from_directory(self.app.static_folder, filename)
    
    def _setup_socketio_events(self):
        """设置SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客户端连接事件"""
            self.socketio.emit('status', {'message': '已连接到ADK开发UI'})
            logger.info("客户端已连接")
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开连接事件"""
            logger.info("客户端已断开连接")
        
        @self.socketio.on('run_agent')
        def handle_run_agent(data):
            """运行智能体事件"""
            agent_id = data.get('agent_id')
            message = data.get('message', '')

            if not self.multi_agent_system:
                self.socketio.emit('agent_response', {'error': '系统未初始化'})
                return

            try:
                self._log_message(f"🤖 运行智能体 {agent_id}: {message}")

                # 根据智能体ID调用相应的智能体
                if agent_id == 'simulation_scheduler':
                    if self.multi_agent_system.simulation_scheduler:
                        # 启动仿真调度流程
                        import asyncio

                        async def run_scheduler():
                            try:
                                # 记录开始执行
                                self._log_planning_status("Initialization", "Starting", "开始仿真调度流程")
                                self._log_message(f"🚀 启动仿真调度智能体 {agent_id}")

                                # 设置UI回调函数
                                if hasattr(self.multi_agent_system.simulation_scheduler, 'set_ui_callbacks'):
                                    self.multi_agent_system.simulation_scheduler.set_ui_callbacks(
                                        log_callback=self._log_message,
                                        planning_callback=self._log_planning_status,
                                        llm_callback=self._log_llm_response
                                    )
                                    self._log_message("✅ UI回调函数已设置到仿真调度智能体")

                                # 创建一个简单的上下文
                                from google.genai import types

                                # 发送消息给仿真调度智能体
                                self._log_planning_status("Execution", "Running", "执行仿真调度智能体")
                                self._log_message(f"📋 开始执行滚动规划任务")

                                response_stream = self.multi_agent_system.simulation_scheduler.run_simulation_scheduling()

                                full_response = ""
                                response_count = 0

                                async for event in response_stream:
                                    if hasattr(event, 'content') and event.content:
                                        for part in event.content.parts:
                                            if hasattr(part, 'text'):
                                                response_count += 1
                                                full_response += part.text + "\n"

                                                # 记录LLM响应片段
                                                self._log_llm_response("DeepSeek", "deepseek-chat", part.text,
                                                                     tokens=len(part.text.split()),
                                                                     agent_id=agent_id)

                                                # 记录响应片段到日志
                                                self._log_message(f"📝 LLM响应片段 #{response_count}: {len(part.text)} 字符")

                                                # 确保LLM响应内容也显示在日志中
                                                if len(part.text) > 100:
                                                    preview = part.text[:100] + "..."
                                                else:
                                                    preview = part.text
                                                self._log_message(f"💬 LLM内容预览: {preview}")

                                                # 使用socketio在应用上下文中发送响应
                                                self.socketio.emit('agent_response', {
                                                    'agent_id': agent_id,
                                                    'response': part.text,
                                                    'timestamp': datetime.now().isoformat(),
                                                    'partial': True,
                                                    'response_count': response_count
                                                })

                                # 记录完成状态
                                self._log_planning_status("Completion", "Finished", f"仿真调度完成，生成响应 {len(full_response)} 字符")
                                self._log_message(f"✅ 仿真调度智能体执行完成，共生成 {response_count} 个响应片段，总计 {len(full_response)} 字符")

                                # 发送最终响应
                                self.socketio.emit('agent_response', {
                                    'agent_id': agent_id,
                                    'response': full_response,
                                    'timestamp': datetime.now().isoformat(),
                                    'partial': False,
                                    'total_responses': response_count,
                                    'total_length': len(full_response)
                                })

                            except Exception as e:
                                self._log_message(f"❌ 仿真调度智能体运行失败: {e}", level='error')
                                self._log_planning_status("Error", "Failed", f"执行失败: {str(e)}")
                                self.socketio.emit('agent_response', {
                                    'agent_id': agent_id,
                                    'error': f"运行失败: {e}",
                                    'timestamp': datetime.now().isoformat()
                                })

                        # 在新线程中运行异步函数
                        import threading
                        def run_async():
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(run_scheduler())
                            loop.close()

                        thread = threading.Thread(target=run_async)
                        thread.start()

                    else:
                        self.socketio.emit('agent_response', {'error': '仿真调度智能体未初始化'})

                else:
                    # 其他智能体的处理逻辑
                    self._log_message(f"智能体 {agent_id} 暂不支持直接运行")
                    self.socketio.emit('agent_response', {
                        'agent_id': agent_id,
                        'response': f"智能体 {agent_id} 收到消息: {message}",
                        'timestamp': datetime.now().isoformat()
                    })

            except Exception as e:
                self._log_message(f"❌ 运行智能体失败: {e}", level='error')
                self.socketio.emit('agent_response', {
                    'agent_id': agent_id,
                    'error': f"运行失败: {e}",
                    'timestamp': datetime.now().isoformat()
                })
    
    def _log_message(self, message: str, level: str = 'info'):
        """记录日志消息"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message
        }

        self.system_status['logs'].append(log_entry)

        # 限制日志数量
        if len(self.system_status['logs']) > 1000:
            self.system_status['logs'] = self.system_status['logs'][-500:]

        # 通过SocketIO广播日志
        self.socketio.emit('new_log', log_entry)

        # 记录到Python日志
        getattr(logger, level)(message)

    def _log_llm_response(self, provider: str, model: str, response: str, tokens: int = 0, agent_id: str = None):
        """记录LLM响应"""
        llm_log = {
            'timestamp': datetime.now().isoformat(),
            'provider': provider,
            'model': model,
            'response': response,
            'tokens': tokens,
            'agent_id': agent_id or 'unknown'
        }

        # 通过SocketIO广播LLM响应
        self.socketio.emit('llm_response', llm_log)

        # 记录到系统日志
        agent_info = f" (Agent: {agent_id})" if agent_id else ""
        self._log_message(f"🤖 LLM响应 [{provider}/{model}]{agent_info} - {len(response)} 字符, {tokens} tokens")

    def _log_planning_status(self, phase: str, step: str, description: str):
        """记录任务规划状态"""
        planning_log = {
            'timestamp': datetime.now().isoformat(),
            'phase': phase,
            'step': step,
            'description': description
        }

        # 通过SocketIO广播规划状态
        self.socketio.emit('planning_status', planning_log)

        # 记录到系统日志
        self._log_message(f"📋 任务规划 [{phase}] {step}: {description}")

    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self, 'executor'):
                self.executor.shutdown(wait=True)
                logger.info("✅ 线程池执行器已关闭")
        except Exception as e:
            logger.error(f"❌ 清理资源失败: {e}")

    def run(self, debug: bool = False):
        """运行开发UI服务器"""
        logger.info(f"🚀 启动ADK开发UI服务器: http://{self.host}:{self.port}")
        try:
            self.socketio.run(self.app, host=self.host, port=self.port, debug=debug)
        finally:
            self.cleanup()


def main():
    """主函数"""
    if not WEB_AVAILABLE:
        print("❌ Web框架不可用")
        return False
    
    print("🌐 ADK开发UI - 多智能体系统管理界面")
    print("=" * 60)
    print("功能:")
    print("- 智能体管理和监控")
    print("- 会话管理和调试")
    print("- 实时日志查看")
    print("- 系统状态监控")
    print("=" * 60)
    
    # 创建UI实例
    ui = ADKDevUI(host="localhost", port=8080)
    
    try:
        ui.run(debug=True)
    except KeyboardInterrupt:
        print("\n⏹️ 服务器已停止")
    except Exception as e:
        print(f"\n❌ 服务器错误: {e}")
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
