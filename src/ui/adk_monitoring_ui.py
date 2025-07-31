"""
ADK监控UI - 基于ADK官方设计的多智能体系统监控界面
严格参考ADK Java项目实现，提供专业的智能体状态和讨论组活动监控
"""

import logging
import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import deque
import sys
import uuid
import threading
import time

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Web框架导入
try:
    from flask import Flask, render_template, request, jsonify, send_from_directory, Response
    from flask_socketio import SocketIO, emit
    WEB_AVAILABLE = True
except ImportError:
    print("⚠️ Flask未安装，请运行: pip install flask flask-socketio")
    WEB_AVAILABLE = False
    sys.exit(1)

# ADK和多智能体系统导入
from src.agents.multi_agent_system import MultiAgentSystem
from src.agents.satellite_agent_factory import SatelliteAgentFactory
from src.agents.adk_parallel_discussion_group import ADKParallelDiscussionGroupManager
from src.agents.rolling_planning_cycle_manager import RollingPlanningCycleManager
from src.agents.missile_target_distributor import MissileTargetDistributor
from src.utils.config_manager import get_config_manager
from src.utils.time_manager import get_time_manager

logger = logging.getLogger(__name__)


class ADKMonitoringUI:
    """
    ADK监控UI管理器
    
    基于ADK官方设计模式，提供：
    1. 智能体状态实时监控
    2. 讨论组活动跟踪
    3. 任务规划周期可视化
    4. 系统性能指标展示
    """
    
    def __init__(self, host: str = "localhost", port: int = 8081):
        """
        初始化ADK监控UI
        
        Args:
            host: 服务器主机
            port: 服务器端口
        """
        self.host = host
        self.port = port
        
        # 创建Flask应用
        self.app = Flask(__name__, 
                        template_folder=str(Path(__file__).parent / "templates"),
                        static_folder=str(Path(__file__).parent / "static"))
        self.app.config['SECRET_KEY'] = 'adk_monitoring_ui_secret_key'
        
        # 创建SocketIO实例
        self.socketio = SocketIO(self.app, cors_allowed_origins="*", async_mode='threading')
        
        # 系统组件引用
        self.multi_agent_system: Optional[MultiAgentSystem] = None
        self.satellite_factory: Optional[SatelliteAgentFactory] = None
        self.discussion_group_manager: Optional[ADKParallelDiscussionGroupManager] = None
        self.planning_cycle_manager: Optional[RollingPlanningCycleManager] = None
        self.missile_distributor: Optional[MissileTargetDistributor] = None
        
        # 监控状态
        self.monitoring_active = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.last_update_time: Optional[datetime] = None
        
        # 缓存的监控数据
        self.cached_data = {
            'system_status': {},
            'agents_status': {},
            'discussion_groups': {},
            'planning_cycles': {},
            'performance_metrics': {},
            'real_time_events': []
        }

        # 日志管理
        self.system_logs = deque(maxlen=1000)  # 保存最近1000条系统日志
        self.llm_api_logs = deque(maxlen=500)  # 保存最近500条大模型API日志
        self.log_file_path = "adk_system.log"
        self.last_log_position = 0

        # 设置路由和事件
        self._setup_routes()
        self._setup_socketio_events()

        # 启动日志监控
        self._start_log_monitoring()

        logger.info(f"🖥️ ADK监控UI初始化完成: http://{host}:{port}")
    
    def set_system_components(
        self,
        multi_agent_system: MultiAgentSystem,
        satellite_factory: SatelliteAgentFactory,
        discussion_group_manager: ADKParallelDiscussionGroupManager,
        planning_cycle_manager: RollingPlanningCycleManager,
        missile_distributor: MissileTargetDistributor
    ):
        """
        设置系统组件引用
        
        Args:
            multi_agent_system: 多智能体系统
            satellite_factory: 卫星智能体工厂
            discussion_group_manager: 讨论组管理器
            planning_cycle_manager: 规划周期管理器
            missile_distributor: 导弹分发器
        """
        self.multi_agent_system = multi_agent_system
        self.satellite_factory = satellite_factory
        self.discussion_group_manager = discussion_group_manager
        self.planning_cycle_manager = planning_cycle_manager
        self.missile_distributor = missile_distributor
        
        logger.info("🔗 系统组件引用设置完成")
    
    def _setup_routes(self):
        """设置Web路由"""
        
        @self.app.route('/')
        def index():
            """主监控页面"""
            return render_template('monitoring_dashboard.html')
        
        @self.app.route('/agents')
        def agents_monitor():
            """智能体监控页面"""
            return render_template('agents_monitor.html')
        
        @self.app.route('/discussion_groups')
        def discussion_groups_monitor():
            """讨论组监控页面"""
            return render_template('discussion_groups_monitor.html')
        
        @self.app.route('/planning_cycles')
        def planning_cycles_monitor():
            """规划周期监控页面"""
            return render_template('planning_cycles_monitor.html')
        
        @self.app.route('/api/system_status')
        def api_system_status():
            """系统状态API"""
            return jsonify(self._get_system_status())
        
        @self.app.route('/api/agents_status')
        def api_agents_status():
            """智能体状态API"""
            return jsonify(self._get_agents_status())
        
        @self.app.route('/api/discussion_groups')
        def api_discussion_groups():
            """讨论组状态API"""
            return jsonify(self._get_discussion_groups_status())
        
        @self.app.route('/api/planning_cycles')
        def api_planning_cycles():
            """规划周期状态API"""
            return jsonify(self._get_planning_cycles_status())
        
        @self.app.route('/api/performance_metrics')
        def api_performance_metrics():
            """性能指标API"""
            return jsonify(self._get_performance_metrics())

        @self.app.route('/api/logs')
        def api_logs():
            """日志API"""
            log_type = request.args.get('type', 'all')  # all, system, llm_api
            limit = int(request.args.get('limit', 100))
            return jsonify({
                'logs': self.get_recent_logs(log_type, limit),
                'total_system_logs': len(self.system_logs),
                'total_llm_api_logs': len(self.llm_api_logs)
            })

        @self.app.route('/api/logs/stream')
        def api_logs_stream():
            """日志流API（Server-Sent Events）"""
            def generate():
                while True:
                    try:
                        # 获取最新日志
                        recent_logs = self.get_recent_logs('all', 10)
                        if recent_logs:
                            yield f"data: {json.dumps(recent_logs)}\n\n"
                        time.sleep(2)
                    except Exception as e:
                        yield f"data: {json.dumps({'error': str(e)})}\n\n"
                        break

            return Response(generate(), mimetype='text/plain')
    
    def _setup_socketio_events(self):
        """设置SocketIO事件"""
        
        @self.socketio.on('connect')
        def handle_connect():
            """客户端连接事件"""
            logger.info("🔌 客户端连接到监控UI")
            emit('connected', {'status': 'success', 'message': 'Connected to ADK Monitoring UI'})
            
            # 发送初始数据
            emit('system_status_update', self._get_system_status())
            emit('agents_status_update', self._get_agents_status())
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """客户端断开连接事件"""
            logger.info("🔌 客户端断开监控UI连接")
        
        @self.socketio.on('start_monitoring')
        def handle_start_monitoring():
            """开始监控事件"""
            self.start_monitoring()
            emit('monitoring_started', {'status': 'success'})
        
        @self.socketio.on('stop_monitoring')
        def handle_stop_monitoring():
            """停止监控事件"""
            self.stop_monitoring()
            emit('monitoring_stopped', {'status': 'success'})
        
        @self.socketio.on('request_update')
        def handle_request_update():
            """请求更新事件"""
            self._broadcast_all_updates()
    
    def _get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        try:
            if not self.multi_agent_system:
                return {'status': 'not_initialized', 'message': '多智能体系统未初始化'}
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'is_running': self.multi_agent_system.is_running,
                'current_simulation_id': self.multi_agent_system.current_simulation_id,
                'monitoring_active': self.monitoring_active,
                'components': {
                    'satellite_factory': self.satellite_factory is not None,
                    'discussion_group_manager': self.discussion_group_manager is not None,
                    'planning_cycle_manager': self.planning_cycle_manager is not None,
                    'missile_distributor': self.missile_distributor is not None
                }
            }
            
            if self.planning_cycle_manager:
                status['planning_status'] = {
                    'is_running': self.planning_cycle_manager.is_running,
                    'cycle_counter': self.planning_cycle_manager.cycle_counter,
                    'current_cycle': self.planning_cycle_manager.current_cycle.cycle_id if self.planning_cycle_manager.current_cycle else None
                }
            
            return status
            
        except Exception as e:
            logger.error(f"❌ 获取系统状态失败: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _get_agents_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        try:
            if not self.multi_agent_system:
                return {'agents': {}, 'total_count': 0}

            agents_status = {}
            # 从多智能体系统获取已注册的卫星智能体
            satellite_agents = self.multi_agent_system.get_all_satellite_agents()

            for satellite_id, agent in satellite_agents.items():
                # 获取资源状态
                resource_status = getattr(agent, '_resource_status', None)
                if resource_status and hasattr(resource_status, 'power_level'):
                    power_level = resource_status.power_level
                    thermal_status = resource_status.thermal_status
                    payload_status = resource_status.payload_status
                else:
                    power_level = 1.0
                    thermal_status = 'normal'
                    payload_status = 'operational'

                agents_status[satellite_id] = {
                    'satellite_id': satellite_id,
                    'agent_type': 'SatelliteAgent',
                    'status': 'active',  # 简化状态
                    'resource_status': {
                        'power_level': power_level,
                        'thermal_status': thermal_status,
                        'payload_status': payload_status
                    },
                    'task_count': self._get_agent_task_count(agent),
                    'last_update': datetime.now().isoformat()
                }
            
            return {
                'agents': agents_status,
                'total_count': len(agents_status),
                'active_count': len([a for a in agents_status.values() if a['status'] == 'active'])
            }
            
        except Exception as e:
            logger.error(f"❌ 获取智能体状态失败: {e}")
            return {'agents': {}, 'total_count': 0, 'error': str(e)}

    def _get_agent_task_count(self, agent) -> int:
        """获取智能体任务数量"""
        try:
            # 尝试从TaskManager获取任务数量
            task_manager = getattr(agent, '_task_manager', None)
            if task_manager:
                # 检查TaskManager的类型，避免将其当作字典处理
                if hasattr(task_manager, '_pending_tasks') and isinstance(getattr(task_manager, '_pending_tasks', None), (list, dict)):
                    pending_tasks = task_manager._pending_tasks
                    return len(pending_tasks) if pending_tasks else 0
                # 如果TaskManager有其他任务列表属性
                elif hasattr(task_manager, 'tasks') and isinstance(getattr(task_manager, 'tasks', None), (list, dict)):
                    tasks = task_manager.tasks
                    return len(tasks) if tasks else 0
                # 如果TaskManager有get_task_count方法
                elif hasattr(task_manager, 'get_task_count') and callable(getattr(task_manager, 'get_task_count', None)):
                    return task_manager.get_task_count()

            # 备用方案：从智能体直接获取任务信息
            if hasattr(agent, 'get_task_count') and callable(getattr(agent, 'get_task_count', None)):
                return agent.get_task_count()
            elif hasattr(agent, '_current_tasks') and isinstance(getattr(agent, '_current_tasks', None), (list, dict)):
                current_tasks = agent._current_tasks
                return len(current_tasks) if current_tasks else 0

            return 0
        except Exception as e:
            logger.debug(f"获取智能体 {getattr(agent, 'satellite_id', 'unknown')} 任务数量失败: {e}")
            return 0
    
    def _get_discussion_groups_status(self) -> Dict[str, Any]:
        """获取讨论组状态"""
        try:
            if not self.discussion_group_manager:
                return {'groups': {}, 'total_count': 0}
            
            current_group = self.discussion_group_manager.get_current_discussion_group()
            completed_groups = self.discussion_group_manager.get_completed_groups_summary()
            
            groups_status = {}
            
            # 当前活跃讨论组
            if current_group:
                groups_status[current_group.group_id] = {
                    'group_id': current_group.group_id,
                    'task_id': current_group.task.task_id,
                    'leader_satellite': current_group.leader_satellite.satellite_id,
                    'member_satellites': [sat.satellite_id for sat in current_group.member_satellites],
                    'status': 'active',
                    'consensus_reached': current_group.consensus_reached,
                    'created_at': datetime.now().isoformat()  # 简化
                }
            
            # 已完成的讨论组摘要
            for summary in completed_groups[-5:]:  # 只显示最近5个
                # 确保summary是字典类型
                if not isinstance(summary, dict):
                    logger.warning(f"⚠️ 讨论组摘要不是字典类型: {type(summary)}")
                    continue

                groups_status[summary.get('group_id', 'unknown')] = {
                    'group_id': summary.get('group_id', 'unknown'),
                    'task_id': summary.get('task_id', 'unknown'),
                    'leader_satellite': summary.get('leader_satellite', 'unknown'),
                    'member_satellites': summary.get('member_satellites', []),
                    'status': 'completed',
                    'consensus_reached': summary.get('consensus_reached', False),
                    'created_at': summary.get('created_at', ''),
                    'closed_at': summary.get('closed_at', '')
                }
            
            return {
                'groups': groups_status,
                'total_count': len(groups_status),
                'active_count': 1 if current_group else 0,
                'completed_count': len(completed_groups)
            }
            
        except Exception as e:
            logger.error(f"❌ 获取讨论组状态失败: {e}")
            return {'groups': {}, 'total_count': 0, 'error': str(e)}
    
    def _get_planning_cycles_status(self) -> Dict[str, Any]:
        """获取规划周期状态"""
        try:
            if not self.planning_cycle_manager:
                return {'cycles': {}, 'total_count': 0}
            
            current_cycle = self.planning_cycle_manager.current_cycle
            cycle_history = self.planning_cycle_manager.cycle_history
            
            cycles_status = {}
            
            # 当前规划周期
            if current_cycle:
                cycles_status[current_cycle.cycle_id] = {
                    'cycle_id': current_cycle.cycle_id,
                    'cycle_number': current_cycle.cycle_number,
                    'state': current_cycle.state.value,
                    'start_time': current_cycle.start_time.isoformat(),
                    'end_time': current_cycle.end_time.isoformat() if current_cycle.end_time else None,
                    'detected_missiles_count': len(current_cycle.detected_missiles),
                    'assigned_satellites_count': len(current_cycle.task_distribution),
                    'has_discussion_group': current_cycle.discussion_group is not None,
                    'error_message': current_cycle.error_message
                }
            
            # 历史规划周期（最近10个）
            for cycle in cycle_history[-10:]:
                cycles_status[cycle.cycle_id] = {
                    'cycle_id': cycle.cycle_id,
                    'cycle_number': cycle.cycle_number,
                    'state': cycle.state.value,
                    'start_time': cycle.start_time.isoformat(),
                    'end_time': cycle.end_time.isoformat() if cycle.end_time else None,
                    'detected_missiles_count': len(cycle.detected_missiles),
                    'assigned_satellites_count': len(cycle.task_distribution),
                    'has_discussion_group': cycle.discussion_group is not None,
                    'error_message': cycle.error_message
                }
            
            return {
                'cycles': cycles_status,
                'total_count': len(cycle_history) + (1 if current_cycle else 0),
                'current_cycle_id': current_cycle.cycle_id if current_cycle else None,
                'is_running': self.planning_cycle_manager.is_running
            }
            
        except Exception as e:
            logger.error(f"❌ 获取规划周期状态失败: {e}")
            return {'cycles': {}, 'total_count': 0, 'error': str(e)}
    
    def _get_performance_metrics(self) -> Dict[str, Any]:
        """获取性能指标"""
        try:
            metrics = {
                'timestamp': datetime.now().isoformat(),
                'system_uptime': 0,  # 简化实现
                'memory_usage': 0,   # 简化实现
                'cpu_usage': 0,      # 简化实现
                'agent_response_time': 0,  # 简化实现
                'discussion_completion_rate': 0,  # 简化实现
                'planning_cycle_success_rate': 0   # 简化实现
            }
            
            # 计算规划周期成功率
            if self.planning_cycle_manager:
                history = self.planning_cycle_manager.cycle_history
                if history:
                    completed_cycles = len([c for c in history if c.state.value == 'completed'])
                    metrics['planning_cycle_success_rate'] = completed_cycles / len(history)
            
            return metrics
            
        except Exception as e:
            logger.error(f"❌ 获取性能指标失败: {e}")
            return {'error': str(e)}
    
    def _broadcast_all_updates(self):
        """广播所有更新"""
        try:
            self.socketio.emit('system_status_update', self._get_system_status())
            self.socketio.emit('agents_status_update', self._get_agents_status())
            self.socketio.emit('discussion_groups_update', self._get_discussion_groups_status())
            self.socketio.emit('planning_cycles_update', self._get_planning_cycles_status())
            self.socketio.emit('performance_metrics_update', self._get_performance_metrics())
            
        except Exception as e:
            logger.error(f"❌ 广播更新失败: {e}")
    
    def start_monitoring(self):
        """开始监控"""
        if self.monitoring_active:
            logger.warning("⚠️ 监控已在运行中")
            return
        
        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitoring_thread.start()
        
        logger.info("🔍 开始ADK系统监控")
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        
        logger.info("🛑 停止ADK系统监控")
    
    def _monitoring_loop(self):
        """监控循环"""
        while self.monitoring_active:
            try:
                # 更新缓存数据
                self.cached_data['system_status'] = self._get_system_status()
                self.cached_data['agents_status'] = self._get_agents_status()
                self.cached_data['discussion_groups'] = self._get_discussion_groups_status()
                self.cached_data['planning_cycles'] = self._get_planning_cycles_status()
                self.cached_data['performance_metrics'] = self._get_performance_metrics()
                
                # 广播更新
                self._broadcast_all_updates()
                
                self.last_update_time = datetime.now()
                
                # 等待下次更新
                time.sleep(2)  # 每2秒更新一次
                
            except Exception as e:
                logger.error(f"❌ 监控循环异常: {e}")
                time.sleep(5)  # 出错时等待更长时间
    
    def run(self, debug: bool = False):
        """运行监控UI"""
        try:
            logger.info(f"🚀 启动ADK监控UI: http://{self.host}:{self.port}")
            self.socketio.run(self.app, host=self.host, port=self.port, debug=debug)
            
        except Exception as e:
            logger.error(f"❌ 运行监控UI失败: {e}")
            raise

    def _start_log_monitoring(self):
        """启动日志监控"""
        try:
            # 启动日志文件监控线程
            log_thread = threading.Thread(target=self._monitor_log_file, daemon=True)
            log_thread.start()
            logger.info("📝 启动日志文件监控")
        except Exception as e:
            logger.error(f"❌ 启动日志监控失败: {e}")

    def _monitor_log_file(self):
        """监控日志文件变化"""
        while True:
            try:
                if os.path.exists(self.log_file_path):
                    # 读取新的日志内容
                    new_logs = self._read_new_logs()
                    if new_logs:
                        # 处理新日志
                        self._process_new_logs(new_logs)
                        # 广播日志更新
                        self.socketio.emit('logs_update', {
                            'system_logs': list(self.system_logs)[-50:],  # 最近50条系统日志
                            'llm_api_logs': list(self.llm_api_logs)[-20:]  # 最近20条API日志
                        })

                time.sleep(1)  # 每秒检查一次

            except Exception as e:
                logger.error(f"❌ 监控日志文件异常: {e}")
                time.sleep(5)

    def _read_new_logs(self) -> List[str]:
        """读取新的日志内容"""
        try:
            with open(self.log_file_path, 'r', encoding='utf-8') as f:
                f.seek(self.last_log_position)
                new_content = f.read()
                self.last_log_position = f.tell()

                if new_content.strip():
                    return new_content.strip().split('\n')
                return []

        except Exception as e:
            logger.debug(f"读取日志文件失败: {e}")
            return []

    def _process_new_logs(self, logs: List[str]):
        """处理新的日志条目"""
        for log_line in logs:
            if not log_line.strip():
                continue

            # 解析日志条目
            log_entry = self._parse_log_entry(log_line)

            # 分类存储日志
            if self._is_llm_api_log(log_line):
                self.llm_api_logs.append(log_entry)
            else:
                self.system_logs.append(log_entry)

    def _parse_log_entry(self, log_line: str) -> Dict[str, Any]:
        """解析日志条目"""
        try:
            # 尝试解析标准日志格式：时间戳 - 模块 - 级别 - 消息
            parts = log_line.split(' - ', 3)
            if len(parts) >= 4:
                timestamp_str, module, level, message = parts
                return {
                    'timestamp': timestamp_str,
                    'module': module,
                    'level': level,
                    'message': message,
                    'raw': log_line
                }
            else:
                # 如果解析失败，返回原始日志
                return {
                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'module': 'unknown',
                    'level': 'INFO',
                    'message': log_line,
                    'raw': log_line
                }
        except Exception:
            return {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'module': 'unknown',
                'level': 'INFO',
                'message': log_line,
                'raw': log_line
            }

    def _is_llm_api_log(self, log_line: str) -> bool:
        """判断是否为大模型API相关日志"""
        llm_keywords = [
            'LiteLLM', 'deepseek', 'API', 'HTTP Request', 'completion',
            '大模型', 'LLM', 'litellm', 'openai', 'chat', 'response'
        ]
        return any(keyword in log_line for keyword in llm_keywords)

    def get_recent_logs(self, log_type: str = 'all', limit: int = 100) -> List[Dict[str, Any]]:
        """获取最近的日志"""
        try:
            if log_type == 'system':
                return list(self.system_logs)[-limit:]
            elif log_type == 'llm_api':
                return list(self.llm_api_logs)[-limit:]
            else:
                # 合并所有日志并按时间排序
                all_logs = list(self.system_logs) + list(self.llm_api_logs)
                all_logs.sort(key=lambda x: x.get('timestamp', ''))
                return all_logs[-limit:]
        except Exception as e:
            logger.error(f"❌ 获取日志失败: {e}")
            return []
