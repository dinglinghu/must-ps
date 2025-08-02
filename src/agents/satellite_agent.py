"""
卫星智能体
基于ADK的BaseAgent实现，每颗卫星对应一个智能体实例
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator, Tuple
from dataclasses import dataclass, asdict

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.tools import FunctionTool
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from ..utils.llm_config_manager import get_llm_config_manager

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于卫星智能体")


@dataclass
class TaskInfo:
    """任务信息数据结构"""
    task_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    priority: float
    status: str  # 'pending', 'executing', 'completed', 'failed'
    metadata: Dict[str, Any]


@dataclass
class ResourceStatus:
    """资源状态数据结构"""
    satellite_id: str
    power_level: float  # 功率水平 (0-1)
    thermal_status: str  # 热状态
    payload_status: str  # 载荷状态
    communication_status: str  # 通信状态
    last_update: datetime


@dataclass
class OptimizationMetrics:
    """优化指标数据结构"""
    gdop_value: float  # 几何精度衰减因子
    schedulability: float  # 调度性指标
    robustness: float  # 鲁棒性指标
    resource_utilization: float  # 资源利用率


class MemoryModule:
    """记忆模块 - 基于ADK Session State实现"""

    def __init__(self, satellite_id: str, timeout: int = 3600):
        self.satellite_id = satellite_id
        self.timeout = timeout  # 记忆超时时间（秒）
        self._memory_key = f"satellite_{satellite_id}_memory"

        # 初始化时间管理器
        from ..utils.time_manager import get_time_manager
        self._time_manager = get_time_manager()

        # 在测试环境中使用本地内存存储
        self._local_memory = {
            'satellite_id': satellite_id,
            'tasks': {},
            'resource_status': {},
            'last_update': self._time_manager.get_current_simulation_time().isoformat()
        }
    
    def store_task(self, ctx: Optional[InvocationContext], task: TaskInfo):
        """存储任务信息"""
        memory = self._get_memory(ctx)
        task_dict = asdict(task)
        # 确保时间字段是字符串格式
        task_dict['start_time'] = task.start_time.isoformat()
        task_dict['end_time'] = task.end_time.isoformat()
        memory['tasks'][task.task_id] = task_dict
        memory['last_update'] = self._time_manager.get_current_simulation_time().isoformat()
        self._save_memory(ctx, memory)

    def get_executing_tasks(self, ctx: Optional[InvocationContext]) -> List[TaskInfo]:
        """获取正在执行的任务"""
        memory = self._get_memory(ctx)
        executing_tasks = []

        for task_data in memory['tasks'].values():
            if task_data['status'] == 'executing':
                task = TaskInfo(**task_data)
                task.start_time = datetime.fromisoformat(task_data['start_time'])
                task.end_time = datetime.fromisoformat(task_data['end_time'])
                executing_tasks.append(task)

        return executing_tasks

    def get_pending_tasks(self, ctx: Optional[InvocationContext]) -> List[TaskInfo]:
        """获取待执行任务"""
        memory = self._get_memory(ctx)
        pending_tasks = []

        for task_data in memory['tasks'].values():
            if task_data['status'] == 'pending':
                task = TaskInfo(**task_data)
                task.start_time = datetime.fromisoformat(task_data['start_time'])
                task.end_time = datetime.fromisoformat(task_data['end_time'])
                pending_tasks.append(task)

        return pending_tasks

    def get_completed_tasks(self, ctx: Optional[InvocationContext]) -> List[TaskInfo]:
        """获取已完成任务"""
        memory = self._get_memory(ctx)
        completed_tasks = []

        for task_data in memory['tasks'].values():
            if task_data['status'] == 'completed':
                task = TaskInfo(**task_data)
                task.start_time = datetime.fromisoformat(task_data['start_time'])
                task.end_time = datetime.fromisoformat(task_data['end_time'])
                completed_tasks.append(task)

        return completed_tasks

    def update_task_status(self, ctx: Optional[InvocationContext], task_id: str, status: str):
        """更新任务状态"""
        memory = self._get_memory(ctx)
        if task_id in memory['tasks']:
            memory['tasks'][task_id]['status'] = status
            memory['last_update'] = self._time_manager.get_current_simulation_time().isoformat()
            self._save_memory(ctx, memory)
    
    def _get_memory(self, ctx: Optional[InvocationContext]) -> Dict[str, Any]:
        """获取记忆数据"""
        if ctx is None or ctx.session is None:
            # 在测试环境中使用本地内存
            return self._local_memory

        memory = ctx.session.state.get(self._memory_key, {
            'satellite_id': self.satellite_id,
            'tasks': {},
            'resource_status': {},
            'last_update': self._time_manager.get_current_simulation_time().isoformat()
        })
        return memory

    def _save_memory(self, ctx: Optional[InvocationContext], memory: Dict[str, Any]):
        """保存记忆数据"""
        if ctx is None or ctx.session is None:
            # 在测试环境中保存到本地内存
            self._local_memory = memory
            return

        ctx.session.state[self._memory_key] = memory


class TaskManager:
    """任务管理器"""
    
    def __init__(self, satellite_id: str, satellite_agent=None):
        self.satellite_id = satellite_id
        self.satellite_agent = satellite_agent  # 引用卫星智能体实例
        self.max_concurrent_tasks = 3  # 最大并发任务数
    
    def can_accept_task(self, ctx: InvocationContext, new_task: TaskInfo) -> bool:
        """检查是否可以接受新任务"""
        memory_module = MemoryModule(self.satellite_id)
        executing_tasks = memory_module.get_executing_tasks(ctx)
        
        # 检查并发任务数限制
        if len(executing_tasks) >= self.max_concurrent_tasks:
            return False
        
        # 检查时间冲突
        for task in executing_tasks:
            if self._has_time_conflict(new_task, task):
                return False
        
        return True
    
    def _has_time_conflict(self, task1: TaskInfo, task2: TaskInfo) -> bool:
        """检查两个任务是否有时间冲突"""
        return not (task1.end_time <= task2.start_time or task2.end_time <= task1.start_time)
    
    def calculate_task_priority(self, task: TaskInfo, optimization_metrics: OptimizationMetrics) -> float:
        """计算任务优先级"""
        # 基于优化指标计算优先级
        priority = (
            0.4 * (1.0 / max(optimization_metrics.gdop_value, 0.001)) +  # GDOP越小越好
            0.3 * optimization_metrics.schedulability +
            0.2 * optimization_metrics.robustness +
            0.1 * optimization_metrics.resource_utilization
        )
        return priority

    def add_task(self, task: TaskInfo) -> bool:
        """
        添加任务到卫星智能体

        Args:
            task: 任务信息

        Returns:
            是否成功添加任务
        """
        try:
            # 在测试环境中，我们简化任务接受逻辑
            # 实际使用中应该有完整的上下文和资源检查

            # 简单检查：确保任务ID不为空
            if not task.task_id:
                logger.warning(f"卫星 {self.satellite_id} 拒绝任务：任务ID为空")
                return False

            # 简单检查：确保时间窗口有效
            if task.start_time >= task.end_time:
                logger.warning(f"卫星 {self.satellite_id} 拒绝任务 {task.task_id}：时间窗口无效")
                return False

            # 在测试环境中，我们直接接受任务
            # 实际环境中，这里应该调用memory_module.store_task(ctx, task)
            logger.info(f"✅ 卫星 {self.satellite_id} 成功接受任务 {task.task_id}")
            logger.info(f"   任务类型: {task.metadata.get('task_type', 'unknown')}")
            logger.info(f"   目标ID: {task.target_id}")
            logger.info(f"   优先级: {task.priority}")
            logger.info(f"   时间窗口: {task.start_time} - {task.end_time}")

            # 关键修复：调用卫星智能体的receive_task方法来实际处理任务
            if self.satellite_agent:
                import asyncio

                # 🔧 修复：从任务中提取导弹目标信息
                missile_target = None
                if task.metadata:
                    # 尝试从不同字段提取导弹目标信息
                    if 'missile_target_names' in task.metadata:
                        missile_names = task.metadata['missile_target_names']
                        if missile_names and len(missile_names) > 0:
                            missile_target = missile_names[0]  # 使用第一个导弹作为主要目标
                    elif 'primary_target' in task.metadata:
                        missile_target = task.metadata['primary_target']
                    elif task.target_id and task.target_id != 'unknown':
                        missile_target = task.target_id

                # 在异步环境中运行任务处理，传递导弹目标信息
                asyncio.create_task(self.satellite_agent.receive_task(task, missile_target))
                logger.info(f"📋 已启动任务处理流程: {task.task_id} (目标: {missile_target})")
            else:
                logger.warning(f"⚠️ 卫星智能体实例未设置，无法处理任务 {task.task_id}")

            return True

        except Exception as e:
            logger.error(f"❌ 卫星 {self.satellite_id} 添加任务失败: {e}")
            return False


class SatelliteAgent(LlmAgent):
    """
    卫星智能体

    基于ADK的LlmAgent实现，每颗卫星对应一个智能体实例。
    负责任务管理、资源状态维护、与组长协调等功能。
    继承LlmAgent以支持直接的大模型访问和专业分析能力。
    """
    
    def __init__(
        self,
        satellite_id: str,
        name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None,
        stk_manager=None,
        multi_agent_system=None
    ):
        """
        初始化卫星智能体

        Args:
            satellite_id: 卫星ID（与STK中卫星ID一致）
            name: 智能体名称
            config: 配置参数
            config_path: 配置文件路径
            stk_manager: STK管理器实例（可选，用于确保连接一致性）
        """
        # 统一名称格式：确保讨论组中的名称一致性
        agent_name = name or satellite_id  # 直接使用satellite_id作为名称，避免前缀混乱

        # 初始化大模型配置管理器
        llm_config_mgr = get_llm_config_manager(config_path or "config/config.yaml")

        # 初始化时间管理器
        from ..utils.time_manager import get_time_manager
        time_manager = get_time_manager()

        # 获取大模型配置
        llm_config = llm_config_mgr.get_llm_config('satellite_agents')

        # 获取智能体提示词配置并格式化
        system_prompt = llm_config_mgr.format_system_prompt(
            'satellite_agents',
            satellite_id=satellite_id,
            current_time=time_manager.get_current_simulation_time().isoformat()  # 使用仿真时间
        )

        # 智能体描述
        description = f"卫星 {satellite_id} 智能体，负责任务管理和资源协调"

        # 获取模型配置
        model_name = llm_config.model  # 使用LLMConfig的model属性

        # 初始化ADK LlmAgent（支持直接大模型访问）
        super().__init__(
            name=agent_name,  # 使用统一的名称格式
            description=description,
            model=LiteLlm(model=model_name),  # 使用配置的模型
            instruction=system_prompt  # 使用格式化的系统提示词
        )

        # 使用object.__setattr__绕过Pydantic限制设置实例变量
        object.__setattr__(self, '_satellite_id', satellite_id)
        object.__setattr__(self, '_config', config or {})
        object.__setattr__(self, '_system_prompt', system_prompt)
        object.__setattr__(self, '_llm_config', llm_config)
        object.__setattr__(self, '_time_manager', time_manager)

        # 添加轨道参数属性和公共属性（避免与BaseAgent属性冲突）
        object.__setattr__(self, '_satellite_id_public', satellite_id)
        object.__setattr__(self, '_config_public', config or {})
        object.__setattr__(self, 'orbital_parameters', (config or {}).get('orbital_parameters', {}))
        object.__setattr__(self, 'payload_config', (config or {}).get('payload_config', {}))

        # 初始化可见窗口计算器
        object.__setattr__(self, '_visibility_calculator', None)
        object.__setattr__(self, '_shared_stk_manager', stk_manager)  # 保存传入的STK管理器
        object.__setattr__(self, '_multi_agent_system', multi_agent_system)  # 保存多智能体系统引用
        self._init_visibility_calculator()

        # 初始化LiteLLM客户端
        object.__setattr__(self, '_litellm_client', None)
        self._init_litellm_client(llm_config_mgr)

        # 状态变量
        object.__setattr__(self, '_current_leader', None)  # 当前组长智能体
        object.__setattr__(self, '_discussion_group_id', None)  # 当前讨论组ID
        object.__setattr__(self, '_resource_status', ResourceStatus(
            satellite_id=satellite_id,
            power_level=1.0,
            thermal_status="normal",
            payload_status="operational",
            communication_status="active",
            last_update=time_manager.get_current_simulation_time()
        ))

        # 初始化组件（在BaseAgent初始化后）
        object.__setattr__(self, '_memory_module', MemoryModule(satellite_id))
        object.__setattr__(self, '_task_manager', TaskManager(satellite_id, self))

        # 创建工具（在初始化后设置）
        object.__setattr__(self, '_tools', self._create_tools())

        logger.info(f"🛰️ 卫星智能体 {agent_name} 初始化完成（支持LLM推理）")

    @property
    def config(self) -> Dict[str, Any]:
        """获取配置信息（向后兼容性）"""
        return self._config

    @config.setter
    def config(self, value: Dict[str, Any]):
        """设置配置信息（向后兼容性）"""
        self._config = value

    @property
    def satellite_id(self) -> str:
        """获取卫星ID"""
        return self._satellite_id_public

    def _init_litellm_client(self, llm_config_mgr):
        """初始化LiteLLM客户端"""
        try:
            from ..utils.litellm_client import LiteLLMClient

            # 构建配置字典
            litellm_config = {
                'model': self._llm_config.model,
                'api_key': self._llm_config.api_key,
                'base_url': self._llm_config.base_url,
                'temperature': self._llm_config.temperature,
                'max_tokens': self._llm_config.max_tokens
            }

            # 创建LiteLLM客户端
            litellm_client = LiteLLMClient(litellm_config)

            object.__setattr__(self, '_litellm_client', litellm_client)
            logger.info(f"✅ 卫星智能体 {self.satellite_id} LiteLLM客户端初始化成功")

        except Exception as e:
            logger.error(f"❌ 卫星智能体 {self.satellite_id} LiteLLM客户端初始化失败: {e}")
            object.__setattr__(self, '_litellm_client', None)

    def _init_visibility_calculator(self):
        """初始化可见窗口计算器 - 使用STK COM接口"""
        try:
            from ..stk_interface.visibility_calculator import get_visibility_calculator
            from ..utils.config_manager import get_config_manager

            # 获取配置管理器
            config_manager = get_config_manager()

            # 关键修复：如果有共享的STK管理器，使用它来创建可见性计算器
            if hasattr(self, '_shared_stk_manager') and self._shared_stk_manager:
                logger.info(f"✅ 卫星智能体 {self.satellite_id} 使用共享的STK管理器")
                # 直接创建可见性计算器并设置STK管理器
                from ..stk_interface.visibility_calculator import VisibilityCalculator
                visibility_calculator = VisibilityCalculator(config_manager)
                visibility_calculator.stk_manager = self._shared_stk_manager
            else:
                # 使用默认方式创建STK可见窗口计算器
                visibility_calculator = get_visibility_calculator(config_manager)

            object.__setattr__(self, '_visibility_calculator', visibility_calculator)

            if visibility_calculator:
                logger.info(f"✅ 卫星智能体 {self.satellite_id} STK COM可见窗口计算器初始化成功")
            else:
                logger.warning(f"⚠️ 卫星智能体 {self.satellite_id} STK COM可见窗口计算器初始化失败，将使用模拟模式")

        except Exception as e:
            logger.error(f"❌ 卫星智能体 {self.satellite_id} STK可见窗口计算器初始化失败: {e}")
            object.__setattr__(self, '_visibility_calculator', None)

    @property
    def satellite_id(self) -> str:
        """获取卫星ID"""
        return self._satellite_id

    @property
    def memory_module(self) -> MemoryModule:
        """获取记忆模块"""
        return self._memory_module

    @property
    def task_manager(self) -> TaskManager:
        """获取任务管理器"""
        return self._task_manager

    async def generate_response(self, user_message: str, temperature: float = 0.3) -> str:
        """
        使用LLM生成响应（用于讨论组推理）

        Args:
            user_message: 用户消息
            temperature: 温度参数

        Returns:
            生成的响应
        """
        if self._litellm_client:
            try:
                logger.info(f"🧠 卫星 {self.satellite_id} 开始LLM推理...")

                response = await self._litellm_client.generate_response(
                    system_prompt=self._system_prompt,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=2048
                )

                logger.info(f"✅ 卫星 {self.satellite_id} LLM推理完成，响应长度: {len(response)}")
                logger.debug(f"🧠 卫星 {self.satellite_id} LLM响应: {response[:200]}...")

                return response

            except Exception as e:
                logger.error(f"❌ 卫星 {self.satellite_id} LLM推理失败: {e}")
                return f"卫星 {self.satellite_id} LLM推理失败: {e}"
        else:
            logger.warning(f"⚠️ 卫星 {self.satellite_id} LiteLLM客户端未初始化，使用默认响应")
            return f"卫星 {self.satellite_id} 响应：LiteLLM客户端未初始化，无法进行推理"

    async def generate_litellm_response(self, user_message: str, temperature: float = 0.3) -> str:
        """
        使用LiteLLM客户端生成响应（兼容方法）

        Args:
            user_message: 用户消息
            temperature: 温度参数

        Returns:
            生成的响应
        """
        return await self.generate_response(user_message, temperature)

    @property
    def current_leader(self) -> Optional[str]:
        """获取当前组长"""
        return self._current_leader

    @property
    def discussion_group_id(self) -> Optional[str]:
        """获取讨论组ID"""
        return self._discussion_group_id

    @property
    def resource_status(self) -> ResourceStatus:
        """获取资源状态"""
        return self._resource_status

    @property
    def tools(self) -> List[FunctionTool]:
        """获取智能体工具"""
        return self._tools
    
    def _create_tools(self) -> List[FunctionTool]:
        """创建智能体工具"""
        tools = []
        
        # 任务接收工具
        async def receive_task_info(task_data: str) -> str:
            """接收元任务信息"""
            try:
                task_dict = json.loads(task_data)
                task = TaskInfo(
                    task_id=task_dict['task_id'],
                    target_id=task_dict['target_id'],
                    start_time=datetime.fromisoformat(task_dict['start_time']),
                    end_time=datetime.fromisoformat(task_dict['end_time']),
                    priority=task_dict.get('priority', 0.5),
                    status='pending',
                    metadata=task_dict.get('metadata', {})
                )
                
                # 这里将实现任务接收逻辑
                return f"任务 {task.task_id} 接收成功"
                
            except Exception as e:
                return f"任务接收失败: {e}"
        
        tools.append(FunctionTool(func=receive_task_info))
        
        # 优化指标计算工具
        async def calculate_optimization_metrics(target_info: str) -> str:
            """计算优化指标"""
            try:
                # 这里将实现GDOP、调度性、鲁棒性计算
                metrics = OptimizationMetrics(
                    gdop_value=0.85,  # 模拟值
                    schedulability=0.75,
                    robustness=0.80,
                    resource_utilization=0.70
                )
                
                return json.dumps(asdict(metrics))
                
            except Exception as e:
                return f"优化指标计算失败: {e}"
        
        tools.append(FunctionTool(func=calculate_optimization_metrics))
        
        # 资源状态更新工具
        async def update_resource_status() -> str:
            """更新资源状态"""
            try:
                self.resource_status.last_update = self._time_manager.get_current_simulation_time()
                # 这里将实现实际的资源状态检查
                return f"资源状态更新完成: {self.resource_status.payload_status}"
                
            except Exception as e:
                return f"资源状态更新失败: {e}"
        
        tools.append(FunctionTool(func=update_resource_status))

        # 自主获取导弹轨迹工具
        async def get_missile_trajectory(missile_id: str) -> str:
            """获取指定导弹的轨迹信息"""
            try:
                logger.info(f"🎯 卫星 {self.satellite_id} 自主获取导弹轨迹: {missile_id}")

                # 使用STK接口获取导弹轨迹
                if hasattr(self, '_visibility_calculator') and self._visibility_calculator:
                    stk_manager = self._visibility_calculator.stk_manager
                    if stk_manager and hasattr(stk_manager, 'missile_manager'):
                        trajectory_info = stk_manager.missile_manager.get_missile_trajectory_info(missile_id)
                        if trajectory_info:
                            logger.info(f"✅ 成功获取导弹 {missile_id} 轨迹信息")
                            return json.dumps({
                                'status': 'success',
                                'missile_id': missile_id,
                                'trajectory': trajectory_info
                            })
                        else:
                            return json.dumps({
                                'status': 'error',
                                'message': f'无法获取导弹 {missile_id} 轨迹信息'
                            })
                    else:
                        return json.dumps({
                            'status': 'error',
                            'message': 'STK管理器或导弹管理器未初始化'
                        })
                else:
                    return json.dumps({
                        'status': 'error',
                        'message': '可见性计算器未初始化'
                    })

            except Exception as e:
                logger.error(f"❌ 获取导弹轨迹失败: {e}")
                return json.dumps({
                    'status': 'error',
                    'message': f'获取导弹轨迹失败: {e}'
                })

        tools.append(FunctionTool(func=get_missile_trajectory))

        # 计算卫星对导弹可见性工具
        async def calculate_satellite_visibility(missile_id: str) -> str:
            """计算所有卫星对指定导弹的可见性"""
            try:
                logger.info(f"🔍 卫星 {self.satellite_id} 计算对导弹 {missile_id} 的可见性")

                if not self._visibility_calculator:
                    return json.dumps({
                        'status': 'error',
                        'message': '可见性计算器未初始化'
                    })

                # 获取所有卫星ID
                all_satellite_ids = await self._get_all_satellite_ids()

                # 使用STK COM接口计算星座可见性
                constellation_result = self._visibility_calculator.calculate_constellation_access(
                    satellite_ids=all_satellite_ids,
                    missile_id=missile_id
                )

                if constellation_result and not constellation_result.get('error'):
                    logger.info(f"✅ 成功计算导弹 {missile_id} 的可见性")
                    return json.dumps({
                        'status': 'success',
                        'missile_id': missile_id,
                        'visibility_result': constellation_result
                    })
                else:
                    error_msg = constellation_result.get('error', 'Unknown error') if constellation_result else 'No result'
                    return json.dumps({
                        'status': 'error',
                        'message': f'可见性计算失败: {error_msg}'
                    })

            except Exception as e:
                logger.error(f"❌ 计算可见性失败: {e}")
                return json.dumps({
                    'status': 'error',
                    'message': f'计算可见性失败: {e}'
                })

        tools.append(FunctionTool(func=calculate_satellite_visibility))

        # 生成元任务信息工具
        async def generate_meta_task_info(missile_targets: str, visibility_results: str) -> str:
            """基于导弹轨迹和可见性信息生成元任务信息"""
            try:
                logger.info(f"📋 卫星 {self.satellite_id} 生成元任务信息")

                # 解析输入参数
                missile_data = json.loads(missile_targets)
                visibility_data = json.loads(visibility_results)

                # 生成元任务信息
                meta_task_info = {
                    'task_id': f"META_TASK_{uuid4().hex[:8].upper()}",
                    'generated_by': self.satellite_id,
                    'generation_time': datetime.now().isoformat(),
                    'missile_targets': missile_data,
                    'visibility_analysis': visibility_data,
                    'recommended_satellites': [],
                    'task_assignments': []
                }

                # 分析可见性结果，推荐参与卫星
                for missile_id, vis_result in visibility_data.items():
                    if isinstance(vis_result, dict) and 'satellites_with_access' in vis_result:
                        visible_satellites = vis_result['satellites_with_access']
                        meta_task_info['recommended_satellites'].extend(visible_satellites)

                        # 为每个导弹生成任务分配
                        task_assignment = {
                            'missile_id': missile_id,
                            'assigned_satellites': visible_satellites,
                            'task_type': 'collaborative_tracking',
                            'priority': 'high'
                        }
                        meta_task_info['task_assignments'].append(task_assignment)

                # 去重推荐卫星列表
                meta_task_info['recommended_satellites'] = list(set(meta_task_info['recommended_satellites']))

                logger.info(f"✅ 生成元任务信息完成，推荐 {len(meta_task_info['recommended_satellites'])} 个卫星参与")

                return json.dumps({
                    'status': 'success',
                    'meta_task_info': meta_task_info
                })

            except Exception as e:
                logger.error(f"❌ 生成元任务信息失败: {e}")
                return json.dumps({
                    'status': 'error',
                    'message': f'生成元任务信息失败: {e}'
                })

        tools.append(FunctionTool(func=generate_meta_task_info))

        # 创建基于可见性的讨论组工具
        async def create_visibility_based_discussion_group(meta_task_info: str) -> str:
            """基于可见性分析结果创建讨论组"""
            try:
                logger.info(f"🎯 卫星 {self.satellite_id} 创建基于可见性的讨论组")

                # 解析元任务信息
                task_data = json.loads(meta_task_info)
                meta_task = task_data.get('meta_task_info', {})

                # 获取推荐的卫星列表
                recommended_satellites = meta_task.get('recommended_satellites', [])

                if not recommended_satellites:
                    return json.dumps({
                        'status': 'error',
                        'message': '没有推荐的卫星参与讨论组'
                    })

                # 构建讨论组创建请求
                discussion_request = {
                    'task_id': meta_task.get('task_id', f"DISCUSSION_{uuid4().hex[:8]}"),
                    'task_description': f"协同处理导弹跟踪任务",
                    'leader_satellite': self.satellite_id,
                    'member_satellites': [sat for sat in recommended_satellites if sat != self.satellite_id],
                    'collaboration_mode': 'iterative_refinement',
                    'requires_visibility_analysis': True
                }

                # 调用ADK官方讨论组创建方法
                result = await self._create_adk_official_discussion_group(
                    task_id=discussion_request['task_id'],
                    task_description=discussion_request['task_description'],
                    member_satellite_ids=discussion_request['member_satellites']
                )

                if result and "成功" in result:
                    logger.info(f"✅ 基于可见性创建讨论组成功: {len(discussion_request['member_satellites'])} 个成员")
                    return json.dumps({
                        'status': 'success',
                        'discussion_group_id': discussion_request['task_id'],
                        'leader': self.satellite_id,
                        'members': discussion_request['member_satellites'],
                        'total_participants': len(discussion_request['member_satellites']) + 1
                    })
                else:
                    return json.dumps({
                        'status': 'error',
                        'message': f'讨论组创建失败: {result}'
                    })

            except Exception as e:
                logger.error(f"❌ 创建基于可见性的讨论组失败: {e}")
                return json.dumps({
                    'status': 'error',
                    'message': f'创建讨论组失败: {e}'
                })

        tools.append(FunctionTool(func=create_visibility_based_discussion_group))

        return tools

    def set_multi_agent_system(self, multi_agent_system):
        """
        设置多智能体系统引用

        Args:
            multi_agent_system: 多智能体系统实例
        """
        try:
            object.__setattr__(self, '_multi_agent_system', multi_agent_system)
            logger.info(f"✅ 卫星 {self.satellite_id} 已连接到多智能体系统")
        except Exception as e:
            logger.error(f"❌ 设置多智能体系统引用失败: {e}")

    def is_connected_to_multi_agent_system(self) -> bool:
        """
        检查是否已连接到多智能体系统

        Returns:
            是否已连接
        """
        connected = hasattr(self, '_multi_agent_system') and self._multi_agent_system is not None
        logger.debug(f"🔍 卫星 {self.satellite_id} 多智能体系统连接状态: {connected}")
        return connected

    async def _get_all_satellite_ids(self) -> List[str]:
        """获取所有卫星ID列表"""
        try:
            satellite_ids = []

            # 从多智能体系统获取
            if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
                all_satellites = self._multi_agent_system.get_all_satellite_agents()
                satellite_ids = list(all_satellites.keys())
                logger.info(f"📡 从多智能体系统获取到 {len(satellite_ids)} 个卫星ID")
            else:
                # 从配置文件获取默认的Walker星座卫星ID
                default_satellite_ids = [
                    "Satellite11", "Satellite12", "Satellite13",
                    "Satellite21", "Satellite22", "Satellite23",
                    "Satellite31", "Satellite32", "Satellite33"
                ]
                satellite_ids = default_satellite_ids
                logger.info(f"📡 使用默认Walker星座卫星ID: {len(satellite_ids)} 个")

            return satellite_ids

        except Exception as e:
            logger.error(f"❌ 获取卫星ID列表失败: {e}")
            return []

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        卫星智能体主要运行逻辑

        在ADK Runner环境中，ctx是真实的InvocationContext，
        支持model_copy和并行分支，具有完整的session.state管理
        """
        logger.info(f"[{self.name}] 卫星智能体开始运行（ADK Runner环境）")

        try:
            # 0. 恢复和管理具身状态（使用真实的ADK InvocationContext）
            await self._restore_embodied_state(ctx)

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"卫星 {self.satellite_id} 具身状态已恢复")])
            )
            # 1. 更新资源状态
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="更新资源状态...")])
            )
            
            await self._update_resource_status_internal()
            
            # 2. 检查任务队列
            executing_tasks = self.memory_module.get_executing_tasks(ctx)
            pending_tasks = self.memory_module.get_pending_tasks(ctx)
            
            status_msg = f"当前状态: 执行中任务 {len(executing_tasks)} 个，待执行任务 {len(pending_tasks)} 个"
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=status_msg)])
            )
            
            # 3. 处理待执行任务
            if pending_tasks:
                for task in pending_tasks[:1]:  # 处理一个待执行任务
                    result = await self._process_pending_task(ctx, task)
                    
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text=result)])
                    )
            
            # 4. 如果有组长，进行协调
            if self.current_leader:
                coordination_result = await self._coordinate_with_leader(ctx)
                
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=coordination_result)])
                )
            
            # 5. 生成状态报告
            report = await self._generate_status_report(ctx)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=report)]),
                actions=EventActions(escalate=False)
            )

            # 保存具身状态（使用真实的ADK InvocationContext）
            await self._save_embodied_state(ctx)

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"卫星 {self.satellite_id} 具身状态已保存")])
            )

        except Exception as e:
            logger.error(f"❌ 卫星智能体运行异常: {e}")

            # 即使出现异常，也要尝试保存状态
            try:
                await self._save_embodied_state(ctx)
            except Exception as save_error:
                logger.error(f"❌ 保存具身状态失败: {save_error}")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"运行异常: {e}")]),
                actions=EventActions(escalate=True)
            )
    
    async def _update_resource_status_internal(self):
        """内部资源状态更新"""
        # 模拟资源状态检查
        self.resource_status.last_update = self._time_manager.get_current_simulation_time()
        # 这里将集成实际的卫星资源监控
    
    async def _process_pending_task(self, ctx: InvocationContext, task: TaskInfo) -> str:
        """处理待执行任务"""
        try:
            # 检查是否可以执行
            if self.task_manager.can_accept_task(ctx, task):
                # 更新任务状态为执行中
                self.memory_module.update_task_status(ctx, task.task_id, 'executing')
                return f"开始执行任务 {task.task_id}"
            else:
                return f"任务 {task.task_id} 暂时无法执行，资源冲突"
                
        except Exception as e:
            return f"任务处理失败: {e}"
    
    async def _coordinate_with_leader(self, ctx: InvocationContext) -> str:
        """与组长协调"""
        try:
            # 这里将实现与组长智能体的协调逻辑
            return f"与组长 {self.current_leader} 协调完成"
            
        except Exception as e:
            return f"协调失败: {e}"
    
    async def _generate_status_report(self, ctx: InvocationContext) -> str:
        """生成状态报告"""
        executing_tasks = self.memory_module.get_executing_tasks(ctx)
        pending_tasks = self.memory_module.get_pending_tasks(ctx)
        
        report = f"""
        卫星 {self.satellite_id} 状态报告:
        - 资源状态: {self.resource_status.payload_status}
        - 功率水平: {self.resource_status.power_level:.2f}
        - 执行中任务: {len(executing_tasks)}
        - 待执行任务: {len(pending_tasks)}
        - 当前组长: {self.current_leader or '无'}
        - 讨论组: {self.discussion_group_id or '未加入'}
        """
        
        return report.strip()
    
    async def _restore_embodied_state(self, ctx: InvocationContext):
        """
        从ADK InvocationContext恢复具身状态

        Args:
            ctx: 真实的ADK InvocationContext，支持session.state管理
        """
        try:
            from ..utils.adk_standard_context import EmbodiedStateManager

            # 使用ADK标准状态管理器
            state_manager = EmbodiedStateManager(ctx.session)
            embodied_state = state_manager.restore_embodied_state(self.satellite_id)

            # 恢复卫星状态
            if embodied_state:
                self._embodied_state = embodied_state
                logger.debug(f"✅ 卫星 {self.satellite_id} 具身状态已从ADK Session恢复")
            else:
                # 初始化默认状态
                self._embodied_state = {
                    'satellite_id': self.satellite_id,
                    'orbital_parameters': {},
                    'resource_status': {
                        'power_level': self.resource_status.power_level,
                        'payload_status': self.resource_status.payload_status
                    },
                    'mission_history': [],
                    'current_tasks': [],
                    'last_update': None
                }
                logger.debug(f"✅ 卫星 {self.satellite_id} 具身状态已初始化")

        except Exception as e:
            logger.error(f"❌ 恢复卫星 {self.satellite_id} 具身状态失败: {e}")

    async def _save_embodied_state(self, ctx: InvocationContext):
        """
        保存具身状态到ADK InvocationContext

        Args:
            ctx: 真实的ADK InvocationContext，支持session.state管理
        """
        try:
            from ..utils.adk_standard_context import EmbodiedStateManager
            from datetime import datetime

            # 更新当前状态
            if hasattr(self, '_embodied_state'):
                self._embodied_state.update({
                    'resource_status': {
                        'power_level': self.resource_status.power_level,
                        'payload_status': self.resource_status.payload_status
                    },
                    'last_update': datetime.now().isoformat()
                })

                # 使用ADK标准状态管理器保存
                state_manager = EmbodiedStateManager(ctx.session)
                state_manager.save_embodied_state(self.satellite_id, self._embodied_state)

                logger.debug(f"✅ 卫星 {self.satellite_id} 具身状态已保存到ADK Session")

        except Exception as e:
            logger.error(f"❌ 保存卫星 {self.satellite_id} 具身状态失败: {e}")

    def join_discussion_group(self, group_id: str, leader_agent: str):
        """加入讨论组"""
        self._discussion_group_id = group_id
        self._current_leader = leader_agent
        logger.info(f"🛰️ {self.name} 加入讨论组 {group_id}，组长: {leader_agent}")

    def leave_discussion_group(self):
        """离开讨论组"""
        old_group = self._discussion_group_id
        self._discussion_group_id = None
        self._current_leader = None
        logger.info(f"🛰️ {self.name} 离开讨论组 {old_group}")
    
    def get_satellite_position(self, time: datetime) -> Tuple[float, float, float]:
        """获取卫星位置（模拟）"""
        # 这里将集成STK接口获取实际位置
        return (0.0, 0.0, 1800.0)  # 模拟位置 (lat, lon, alt)

    async def update_position(self, position_data: Dict[str, Any]):
        """
        更新卫星位置信息

        Args:
            position_data: 位置数据字典，包含lat, lon, alt, timestamp等
        """
        try:
            # 更新位置信息到配置中
            if 'orbital_parameters' not in self._config:
                self._config['orbital_parameters'] = {}

            self._config['orbital_parameters'].update({
                'current_lat': position_data.get('lat', 0.0),
                'current_lon': position_data.get('lon', 0.0),
                'current_alt': position_data.get('alt', 1800.0),
                'position_timestamp': position_data.get('timestamp', datetime.now()).isoformat()
            })

            logger.debug(f"卫星 {self.satellite_id} 位置已更新")

        except Exception as e:
            logger.error(f"更新卫星 {self.satellite_id} 位置失败: {e}")

    async def receive_task(self, task: TaskInfo, missile_target=None):
        """
        接收任务并创建讨论组

        Args:
            task: 任务信息
            missile_target: 导弹目标信息（可选）
        """
        try:
            logger.info(f"🎯 卫星 {self.satellite_id} 接收到任务: {task.task_id}")

            # 检查任务来源
            created_by = task.metadata.get('created_by', 'unknown') if task.metadata else 'unknown'
            logger.info(f"   任务来源: {created_by}")

            # 检查是否为元任务集
            if task.metadata and task.metadata.get('task_type') == 'meta_task_set':
                logger.info(f"📋 处理元任务集: {task.task_id}")
                logger.info(f"   包含导弹数量: {task.metadata.get('missile_count', 0)}")
                logger.info(f"   导弹列表: {task.metadata.get('missile_list', [])}")

                # 处理元任务集
                await self._process_meta_task_set(task)
            elif task.metadata and task.metadata.get('task_type') == 'collaborative_tracking':
                # 处理协同跟踪任务（来自仿真调度智能体的委托）
                logger.info(f"🤝 处理协同跟踪任务: {task.task_id}")

                # 存储任务信息
                memory_module = MemoryModule(self.satellite_id)
                memory_module.store_task(None, task)  # 在实际ADK环境中会传入ctx

                # 获取预定义的参与者列表
                participant_list = task.metadata.get('participant_list', [])
                if participant_list:
                    logger.info(f"   使用预定义参与者列表: {participant_list}")
                    # 获取参与者卫星智能体实例
                    member_satellites = await self._get_satellite_agents_by_ids(participant_list[1:])  # 排除自己
                    await self._create_discussion_group_as_leader(task, missile_target, member_satellites)
                else:
                    # 动态查找成员卫星
                    await self._create_discussion_group_as_leader(task, missile_target)
            else:
                # 处理普通任务
                # 存储任务信息
                memory_module = MemoryModule(self.satellite_id)
                memory_module.store_task(None, task)  # 在实际ADK环境中会传入ctx

                # 作为组长创建讨论组
                await self._create_discussion_group_as_leader(task, missile_target)

        except Exception as e:
            logger.error(f"❌ 卫星 {self.satellite_id} 接收任务失败: {e}")

            # 🔧 修复：即使任务处理失败，也要发送失败通知
            try:
                failure_result = {
                    'task_id': task.task_id,
                    'status': 'failed',
                    'success': False,
                    'error': str(e),
                    'satellite_id': self.satellite_id,
                    'completion_time': datetime.now().isoformat()
                }
                await self._report_result_to_scheduler(task, failure_result)
            except Exception as report_error:
                logger.error(f"❌ 发送失败通知也失败: {report_error}")

    async def _process_meta_task_set(self, task: TaskInfo):
        """
        处理元任务集 - 支持自主处理模式

        Args:
            task: 元任务集任务信息
        """
        try:
            logger.info(f"🎯 卫星 {self.satellite_id} 开始处理元任务集 {task.task_id}")

            # 检查是否为自主处理模式
            requires_autonomous = task.metadata.get('requires_autonomous_processing', False)

            if requires_autonomous:
                logger.info(f"🚀 启动自主处理模式")
                await self._process_autonomous_meta_task(task)
            else:
                logger.info(f"📋 使用传统处理模式")
                # 1. 计算所有卫星对所有目标的可见性窗口
                if task.metadata.get('requires_visibility_calculation', False):
                    await self._calculate_visibility_for_all_targets(task)

                # 2. 根据可见性结果动态加入讨论组
                if task.metadata.get('requires_discussion_group', False):
                    await self._create_dynamic_discussion_group(task)

            # 3. 存储元任务集信息
            memory_module = MemoryModule(self.satellite_id)
            memory_module.store_task(None, task)

            # 🔧 修复：向仿真调度智能体报告元任务集完成
            meta_task_result = {
                'task_id': task.task_id,
                'status': 'completed',
                'success': True,
                'processing_mode': 'autonomous' if requires_autonomous else 'traditional',
                'satellite_id': self.satellite_id,
                'completion_time': datetime.now().isoformat()
            }
            await self._report_result_to_scheduler(task, meta_task_result)

            logger.info(f"✅ 卫星 {self.satellite_id} 元任务集处理完成")

        except Exception as e:
            logger.error(f"❌ 处理元任务集失败: {e}")

            # 🔧 修复：元任务集处理失败时也要发送失败通知
            try:
                failure_result = {
                    'task_id': task.task_id,
                    'status': 'failed',
                    'success': False,
                    'error': str(e),
                    'satellite_id': self.satellite_id,
                    'completion_time': datetime.now().isoformat()
                }
                await self._report_result_to_scheduler(task, failure_result)
            except Exception as report_error:
                logger.error(f"❌ 发送失败通知也失败: {report_error}")

    async def _process_autonomous_meta_task(self, task: TaskInfo):
        """
        自主处理元任务 - 基于导弹目标名称自主获取信息并创建讨论组

        Args:
            task: 元任务集任务信息
        """
        try:
            logger.info(f"🤖 卫星 {self.satellite_id} 开始自主处理元任务")

            # 1. 从任务中获取导弹目标名称
            missile_target_names = task.metadata.get('missile_target_names', [])
            if not missile_target_names:
                # 兼容旧格式
                missile_target_names = task.metadata.get('missile_list', [])

            logger.info(f"🎯 需要处理的导弹目标: {missile_target_names}")

            if not missile_target_names:
                logger.warning("⚠️ 没有找到导弹目标名称")
                return

            # 2. 为每个导弹目标自主获取轨迹信息
            missile_trajectories = {}
            for missile_id in missile_target_names:
                logger.info(f"📡 自主获取导弹 {missile_id} 轨迹信息...")
                trajectory_result = await self._autonomous_get_missile_trajectory(missile_id)
                if trajectory_result.get('status') == 'success':
                    missile_trajectories[missile_id] = trajectory_result['trajectory']
                    logger.info(f"✅ 成功获取导弹 {missile_id} 轨迹")
                else:
                    logger.warning(f"⚠️ 获取导弹 {missile_id} 轨迹失败: {trajectory_result.get('message')}")

            # 3. 计算所有卫星对所有导弹的可见性
            visibility_results = {}
            for missile_id in missile_target_names:
                logger.info(f"🔍 计算对导弹 {missile_id} 的可见性...")
                visibility_result = await self._autonomous_calculate_visibility(missile_id)
                if visibility_result.get('status') == 'success':
                    visibility_results[missile_id] = visibility_result['visibility_result']
                    logger.info(f"✅ 成功计算导弹 {missile_id} 可见性")
                else:
                    logger.warning(f"⚠️ 计算导弹 {missile_id} 可见性失败: {visibility_result.get('message')}")

            # 4. 生成元任务信息
            logger.info(f"📋 生成元任务信息...")
            meta_task_result = await self._autonomous_generate_meta_task_info(
                missile_trajectories, visibility_results
            )

            if meta_task_result.get('status') == 'success':
                meta_task_info = meta_task_result['meta_task_info']
                logger.info(f"✅ 成功生成元任务信息")

                # 5. 基于可见性结果创建讨论组
                if task.metadata.get('requires_discussion_group', False):
                    logger.info(f"🎯 基于可见性创建讨论组...")
                    discussion_result = await self._autonomous_create_discussion_group(meta_task_info)

                    if discussion_result.get('status') == 'success':
                        logger.info(f"✅ 成功创建讨论组: {discussion_result.get('total_participants')} 个参与者")
                    else:
                        logger.warning(f"⚠️ 创建讨论组失败: {discussion_result.get('message')}")
            else:
                logger.error(f"❌ 生成元任务信息失败: {meta_task_result.get('message')}")

            logger.info(f"🎉 自主处理元任务完成")

        except Exception as e:
            logger.error(f"❌ 自主处理元任务失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")

    async def _autonomous_get_missile_trajectory(self, missile_id: str) -> Dict[str, Any]:
        """自主获取导弹轨迹信息"""
        try:
            if hasattr(self, '_visibility_calculator') and self._visibility_calculator:
                stk_manager = self._visibility_calculator.stk_manager
                if stk_manager and hasattr(stk_manager, 'missile_manager'):
                    trajectory_info = stk_manager.missile_manager.get_missile_trajectory_info(missile_id)
                    if trajectory_info:
                        return {
                            'status': 'success',
                            'missile_id': missile_id,
                            'trajectory': trajectory_info
                        }

            return {
                'status': 'error',
                'message': f'无法获取导弹 {missile_id} 轨迹信息'
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'获取导弹轨迹失败: {e}'
            }

    async def _autonomous_calculate_visibility(self, missile_id: str) -> Dict[str, Any]:
        """自主计算可见性"""
        try:
            if not self._visibility_calculator:
                return {
                    'status': 'error',
                    'message': '可见性计算器未初始化'
                }

            # 获取所有卫星ID
            all_satellite_ids = await self._get_all_satellite_ids()

            # 计算星座可见性
            constellation_result = self._visibility_calculator.calculate_constellation_access(
                satellite_ids=all_satellite_ids,
                missile_id=missile_id
            )

            if constellation_result and not constellation_result.get('error'):
                return {
                    'status': 'success',
                    'missile_id': missile_id,
                    'visibility_result': constellation_result
                }
            else:
                error_msg = constellation_result.get('error', 'Unknown error') if constellation_result else 'No result'
                return {
                    'status': 'error',
                    'message': f'可见性计算失败: {error_msg}'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'计算可见性失败: {e}'
            }

    async def _autonomous_generate_meta_task_info(self, missile_trajectories: Dict, visibility_results: Dict) -> Dict[str, Any]:
        """自主生成元任务信息"""
        try:
            meta_task_info = {
                'task_id': f"META_TASK_{uuid4().hex[:8].upper()}",
                'generated_by': self.satellite_id,
                'generation_time': datetime.now().isoformat(),
                'missile_targets': missile_trajectories,
                'visibility_analysis': visibility_results,
                'recommended_satellites': [],
                'task_assignments': []
            }

            # 分析可见性结果，推荐参与卫星
            for missile_id, vis_result in visibility_results.items():
                if isinstance(vis_result, dict) and 'satellites_with_access' in vis_result:
                    visible_satellites = vis_result['satellites_with_access']
                    meta_task_info['recommended_satellites'].extend(visible_satellites)

                    # 为每个导弹生成任务分配
                    task_assignment = {
                        'missile_id': missile_id,
                        'assigned_satellites': visible_satellites,
                        'task_type': 'collaborative_tracking',
                        'priority': 'high'
                    }
                    meta_task_info['task_assignments'].append(task_assignment)

            # 去重推荐卫星列表
            meta_task_info['recommended_satellites'] = list(set(meta_task_info['recommended_satellites']))

            return {
                'status': 'success',
                'meta_task_info': meta_task_info
            }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'生成元任务信息失败: {e}'
            }

    async def _autonomous_create_discussion_group(self, meta_task_info: Dict) -> Dict[str, Any]:
        """自主创建基于可见性的讨论组"""
        try:
            # 获取推荐的卫星列表
            recommended_satellites = meta_task_info.get('recommended_satellites', [])

            if not recommended_satellites:
                return {
                    'status': 'error',
                    'message': '没有推荐的卫星参与讨论组'
                }

            # 构建讨论组创建请求
            task_id = meta_task_info.get('task_id', f"DISCUSSION_{uuid4().hex[:8]}")
            member_satellites = [sat for sat in recommended_satellites if sat != self.satellite_id]

            # 调用ADK官方讨论组创建方法
            result = await self._create_adk_official_discussion_group(
                task_id=task_id,
                task_description=f"协同处理导弹跟踪任务",
                member_satellite_ids=member_satellites
            )

            if result and "成功" in result:
                return {
                    'status': 'success',
                    'discussion_group_id': task_id,
                    'leader': self.satellite_id,
                    'members': member_satellites,
                    'total_participants': len(member_satellites) + 1
                }
            else:
                return {
                    'status': 'error',
                    'message': f'讨论组创建失败: {result}'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'创建讨论组失败: {e}'
            }

    async def _calculate_visibility_for_all_targets(self, task: TaskInfo):
        """
        并发计算所有卫星对所有目标的可见性窗口 - 使用STK COM接口

        Args:
            task: 元任务集任务信息
        """
        try:
            logger.info(f"🚀 开始并发计算所有目标的可见性窗口")

            if not self._visibility_calculator:
                logger.warning("⚠️ 可见窗口计算器未初始化")
                return

            # 获取所有导弹轨迹
            missile_trajectories = task.metadata.get('missile_trajectories', [])
            all_satellite_ids = await self._get_all_satellite_ids()

            if not missile_trajectories:
                logger.warning("⚠️ 未找到导弹轨迹信息")
                return

            # 并发计算所有目标的可见性
            visibility_results = await self._calculate_visibility_concurrent(
                missile_trajectories, all_satellite_ids
            )

            # 存储可见性结果到任务元数据
            task.metadata['visibility_results'] = visibility_results

            logger.info(f"✅ 并发可见性计算完成，共处理 {len(visibility_results)} 个目标")

        except Exception as e:
            logger.error(f"❌ 并发可见性计算失败: {e}")

    async def _calculate_visibility_concurrent(self, missile_trajectories: List[Dict], all_satellite_ids: List[str]) -> Dict[str, Any]:
        """
        并发计算多个目标的可见性窗口

        Args:
            missile_trajectories: 导弹轨迹列表
            all_satellite_ids: 所有卫星ID列表

        Returns:
            可见性结果字典
        """
        try:
            import asyncio

            logger.info(f"🔄 开始并发计算 {len(missile_trajectories)} 个目标的可见性")

            # 创建并发任务
            tasks = []
            missile_ids = []

            for missile_info in missile_trajectories:
                missile_id = missile_info.get('missile_id')
                if missile_id and all_satellite_ids:
                    task = asyncio.create_task(
                        self._calculate_single_target_visibility(missile_id, all_satellite_ids)
                    )
                    tasks.append(task)
                    missile_ids.append(missile_id)

            if not tasks:
                logger.warning("⚠️ 没有有效的目标需要计算")
                return {}

            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果
            visibility_results = {}
            for i, result in enumerate(results):
                missile_id = missile_ids[i]
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ 目标 {missile_id} 可见性计算失败: {result}")
                    visibility_results[missile_id] = {"error": str(result)}
                else:
                    visibility_results[missile_id] = result
                    if result and not result.get('error'):
                        satellites_with_access = result.get('satellites_with_access', [])
                        total_intervals = result.get('total_access_intervals', 0)
                        logger.info(f"   目标 {missile_id}: {len(satellites_with_access)} 颗卫星有访问, 总间隔数: {total_intervals}")

            logger.info(f"✅ 并发可见性计算完成，成功处理 {len([r for r in visibility_results.values() if not r.get('error')])} 个目标")
            return visibility_results

        except Exception as e:
            logger.error(f"❌ 并发可见性计算失败: {e}")
            return {}

    async def _calculate_single_target_visibility(self, missile_id: str, all_satellite_ids: List[str]) -> Dict[str, Any]:
        """
        计算单个目标的可见性窗口

        Args:
            missile_id: 导弹ID
            all_satellite_ids: 所有卫星ID列表

        Returns:
            可见性结果
        """
        try:
            import asyncio
            # 模拟异步计算延迟
            await asyncio.sleep(0.05)  # 模拟计算时间

            # 使用STK COM接口计算星座可见性
            constellation_result = self._visibility_calculator.calculate_constellation_access(
                satellite_ids=all_satellite_ids,
                missile_id=missile_id
            )

            if constellation_result and not constellation_result.get('error'):
                logger.debug(f"🛰️ 目标 {missile_id} 可见性计算完成")
                return constellation_result
            else:
                error_msg = constellation_result.get('error', 'Unknown error') if constellation_result else 'No result'
                logger.warning(f"⚠️ 目标 {missile_id} 可见性计算失败: {error_msg}")
                return {"error": error_msg}

        except Exception as e:
            logger.error(f"❌ 目标 {missile_id} 可见性计算异常: {e}")
            return {"error": str(e)}

    def _extract_missile_id_from_task(self, task: TaskInfo) -> str:
        """
        从任务信息中提取导弹ID

        Args:
            task: 任务信息

        Returns:
            导弹ID字符串或None
        """
        try:
            # 🔧 修复：优先从target_id获取主要目标
            if task.target_id and task.target_id != 'unknown' and task.target_id != 'multi_missile_targets':
                logger.debug(f"从任务target_id中提取到导弹ID: {task.target_id}")
                return task.target_id

            # 从任务元数据中提取导弹目标名称（新格式）
            if task.metadata:
                # 优先使用missile_target_names
                if 'missile_target_names' in task.metadata:
                    missile_target_names = task.metadata['missile_target_names']
                    if missile_target_names and len(missile_target_names) > 0:
                        missile_id = missile_target_names[0]  # 使用第一个导弹作为主要目标
                        logger.debug(f"从missile_target_names中提取到导弹ID: {missile_id}")
                        return missile_id

                # 兼容primary_target字段
                if 'primary_target' in task.metadata:
                    primary_target = task.metadata['primary_target']
                    if primary_target and primary_target != 'unknown':
                        logger.debug(f"从primary_target中提取到导弹ID: {primary_target}")
                        return primary_target

                # 兼容旧格式：从导弹轨迹信息中提取
                if 'missile_trajectories' in task.metadata:
                    trajectories = task.metadata['missile_trajectories']
                    if trajectories and len(trajectories) > 0:
                        # 使用第一个导弹的ID
                        first_missile = trajectories[0]
                        missile_id = first_missile.get('missile_id')
                        if missile_id:
                            logger.debug(f"从missile_trajectories中提取到导弹ID: {missile_id}")
                            return missile_id

                # 兼容missile_list格式
                if 'missile_list' in task.metadata:
                    missile_list = task.metadata['missile_list']
                    if missile_list and len(missile_list) > 0:
                        if isinstance(missile_list[0], dict):
                            missile_id = missile_list[0].get('missile_id')
                            if missile_id:
                                logger.debug(f"从missile_list中提取到导弹ID: {missile_id}")
                                return missile_id
                        else:
                            # 简单字符串列表
                            missile_id = missile_list[0]
                            logger.debug(f"从missile_list中提取到导弹ID: {missile_id}")
                            return missile_id

            logger.warning("⚠️ 无法从任务信息中提取导弹ID")
            return None

        except Exception as e:
            logger.error(f"❌ 提取导弹ID失败: {e}")
            return None

    async def _create_dynamic_discussion_group(self, task: TaskInfo):
        """
        根据可见性结果创建动态讨论组

        Args:
            task: 元任务集任务信息
        """
        try:
            logger.info(f"🤝 创建动态讨论组，基于可见性结果")

            # 获取可见性结果
            visibility_results = task.metadata.get('visibility_results', {})

            # 找到有可见窗口的所有卫星
            satellites_with_visibility = set()
            for missile_id, constellation_result in visibility_results.items():
                # STK COM接口返回的格式：{"satellites_with_access": ["Satellite11", "Satellite12", ...]}
                if isinstance(constellation_result, dict) and 'satellites_with_access' in constellation_result:
                    satellites_with_access = constellation_result.get('satellites_with_access', [])

                    # 确保satellites_with_access是列表，并且包含字符串
                    if isinstance(satellites_with_access, list):
                        valid_satellite_ids = []
                        for sat_id in satellites_with_access:
                            if isinstance(sat_id, str):
                                valid_satellite_ids.append(sat_id)
                            else:
                                logger.warning(f"⚠️ 跳过非字符串卫星ID: {sat_id} (类型: {type(sat_id)})")

                        satellites_with_visibility.update(valid_satellite_ids)
                        logger.info(f"   导弹 {missile_id}: {len(valid_satellite_ids)} 颗卫星有可见窗口")
                    else:
                        logger.warning(f"⚠️ satellites_with_access 不是列表: {type(satellites_with_access)}")

            # 排除自己
            member_satellite_ids = [sid for sid in satellites_with_visibility if sid != self.satellite_id]

            logger.info(f"   找到 {len(member_satellite_ids)} 个有可见窗口的成员卫星")
            for sat_id in member_satellite_ids:
                logger.info(f"   成员: {sat_id}")

            # 获取成员卫星实例
            member_satellites = await self._get_satellite_agents_by_ids(member_satellite_ids)

            if member_satellites:
                # 创建讨论组
                await self._create_discussion_group_as_leader(task, None, member_satellites)
            else:
                logger.warning("⚠️ 没有找到有可见窗口的成员卫星，无法创建讨论组")

        except Exception as e:
            logger.error(f"❌ 创建动态讨论组失败: {e}")

    async def _create_discussion_group_as_leader(self, task: TaskInfo, missile_target=None, member_satellites=None):
        """
        作为组长创建讨论组

        Args:
            task: 任务信息
            missile_target: 导弹目标信息
            member_satellites: 预定义的成员卫星列表（可选）
        """
        try:
            logger.info(f"👑 卫星 {self.satellite_id} 作为组长创建ADK标准讨论组，任务: {task.task_id}")

            # 查找有可见窗口的其他卫星作为组员
            if member_satellites is None:
                member_satellites = await self._find_member_satellites(task, missile_target)
            else:
                logger.info(f"🎯 使用预定义的成员卫星列表: {len(member_satellites)} 个成员")

            # 准备参与讨论的智能体列表（包括自己作为组长）
            participating_agents = [self] + member_satellites

            # 获取多智能体系统引用
            if not self.is_connected_to_multi_agent_system():
                logger.error("❌ 多智能体系统未连接，无法创建ADK标准讨论组")
                logger.error("   请确保卫星智能体已正确注册到多智能体系统")
                logger.error(f"   当前卫星 {self.satellite_id} 连接状态: {hasattr(self, '_multi_agent_system')}")
                if hasattr(self, '_multi_agent_system'):
                    logger.error(f"   多智能体系统实例: {self._multi_agent_system is not None}")
                return

            # 在ADK Runner环境中，InvocationContext由框架自动提供
            # 这里创建一个临时的session用于状态管理
            from ..utils.adk_standard_context import create_satellite_session

            ctx = create_satellite_session(self.satellite_id, task.task_id)

            # 使用ADK官方讨论系统创建讨论组 - 迭代优化模式
            task_description = f"卫星协同任务 - {task.task_id} (目标: {task.target_id}) - 迭代优化决策 + 并发仿真验证"
            discussion_id = await self._multi_agent_system.create_adk_official_discussion(
                pattern_type="iterative_refinement",  # ADK官方迭代优化模式：并发执行 + 迭代优化
                participating_agents=participating_agents,
                task_description=task_description,
                ctx=ctx
            )

            if discussion_id:
                logger.info(f"🎉 ADK标准讨论组创建成功: {discussion_id}")
                logger.info(f"   组长: {self.satellite_id}")
                logger.info(f"   成员: {[sat.satellite_id for sat in member_satellites]}")

                # 存储讨论组信息到本地状态
                discussion_info = {
                    'discussion_id': discussion_id,
                    'task_id': task.task_id,
                    'target_id': task.target_id,
                    'leader': self.satellite_id,
                    'members': [sat.satellite_id for sat in member_satellites],
                    'discussion_type': 'parallel',
                    'created_time': task.start_time.isoformat(),
                    'status': 'active',
                    'source': 'adk_standard_discussion_system'
                }

                # 存储到卫星智能体的讨论组记录中
                if not hasattr(self, '_discussion_groups'):
                    self._discussion_groups = {}
                self._discussion_groups[discussion_id] = discussion_info

                # 模拟处理讨论结果
                await self._handle_adk_discussion_result(task, discussion_id)
            else:
                logger.error(f"❌ ADK标准讨论组创建失败")

        except Exception as e:
            logger.error(f"❌ 创建ADK标准讨论组失败: {e}")

    async def _handle_adk_discussion_result(self, task: TaskInfo, discussion_id: str):
        """
        处理ADK标准讨论组的结果

        Args:
            task: 任务信息
            discussion_id: 讨论组ID
        """
        try:
            logger.info(f"📋 处理ADK标准讨论组结果: {discussion_id}")

            # 🔧 修复：从实际的讨论组执行中获取结果
            # 安全解散讨论组并获取执行结果
            discussion_result = await self._safely_dissolve_discussion_group(discussion_id)

            if not discussion_result:
                # 如果没有获取到结果，使用默认值
                discussion_result = {
                    'success': False,
                    'status': 'failed',
                    'quality_score': 0.0,
                    'response': '未获取到讨论组执行结果',
                    'iterations': 0
                }
                logger.warning(f"⚠️ 未获取到讨论组 {discussion_id} 的执行结果，使用默认值")

            # 转换为任务结果格式
            task_result = {
                'discussion_id': discussion_id,
                'task_id': task.task_id,
                'status': discussion_result.get('status', 'failed'),
                'quality_score': discussion_result.get('quality_score', 0.0),
                'iterations': discussion_result.get('iterations', 0),
                'llm_response': discussion_result.get('response', ''),
                'execution_time': discussion_result.get('execution_time'),
                'decisions': [
                    f"基于LLM分析的专业决策",
                    f"GDOP优化建议",
                    f"鲁棒性评估结果"
                ],
                'resource_allocation': {
                    'primary_tracker': self.satellite_id,
                    'backup_trackers': [],
                    'data_relay': True
                }
            }

            # 更新任务状态为已完成
            if hasattr(self, 'memory_module'):
                # 创建模拟的InvocationContext用于内存模块
                from google.adk.agents.invocation_context import InvocationContext
                from google.adk.sessions import Session
                from unittest.mock import Mock

                mock_session = Session(
                    id=f"satellite_memory_{self.satellite_id}",
                    app_name="satellite_agent",
                    user_id=self.satellite_id
                )
                mock_ctx = Mock()
                mock_ctx.session = mock_session
                mock_ctx.session.state = {}

                # 🔧 修复：更新任务状态为已完成，而不是执行中
                self.memory_module.update_task_status(mock_ctx, task.task_id, 'completed')

            # 🔧 修复：向仿真调度智能体报告任务完成
            await self._report_result_to_scheduler(task, task_result)

            # 注意：讨论组已在获取结果时解散，这里不需要重复解散

            logger.info(f"✅ ADK标准讨论组结果处理完成: {discussion_id}")

        except Exception as e:
            logger.error(f"❌ 处理ADK标准讨论组结果失败: {e}")

    async def _safely_dissolve_discussion_group(self, discussion_id: str):
        """
        安全解散讨论组（ADK标准方式）

        调用ADK官方讨论系统的安全解散方法，确保：
        1. 具身智能体状态被保持
        2. 下次滚动规划可以正确使用这些状态
        3. 符合ADK官方最佳实践
        """
        try:
            if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
                # 获取ADK官方讨论系统
                adk_discussion_system = getattr(self._multi_agent_system, '_adk_official_discussion_system', None)

                if adk_discussion_system:
                    logger.info(f"🔄 安全解散讨论组: {discussion_id}")

                    # 调用ADK标准的安全解散方法（现在返回执行结果）
                    result = await adk_discussion_system.complete_discussion(discussion_id)

                    if result.get('success', False):
                        logger.info(f"✅ 讨论组 {discussion_id} 已安全解散")
                        logger.info(f"   具身智能体状态已保持，可用于下次滚动规划")

                        # 记录执行结果
                        status = result.get('status', 'unknown')
                        quality_score = result.get('quality_score', 0.0)
                        iterations = result.get('iterations', 0)

                        logger.info(f"📊 讨论组执行结果:")
                        logger.info(f"   状态: {status}")
                        logger.info(f"   质量评分: {quality_score:.3f}")
                        logger.info(f"   迭代次数: {iterations}")

                        # 返回执行结果供上层使用
                        return result
                    else:
                        logger.warning(f"⚠️ 讨论组 {discussion_id} 解散失败")
                        return result
                else:
                    logger.warning(f"⚠️ ADK官方讨论系统不可用，无法安全解散讨论组")
            else:
                logger.warning(f"⚠️ 多智能体系统不可用，无法解散讨论组")

        except Exception as e:
            logger.error(f"❌ 安全解散讨论组失败: {e}")
            # 不抛出异常，确保任务处理可以继续

    async def _find_member_satellites(self, task: TaskInfo, missile_target=None) -> List['SatelliteAgent']:
        """
        查找有可见窗口的其他卫星作为讨论组成员

        Args:
            task: 任务信息
            missile_target: 导弹目标信息

        Returns:
            成员卫星列表
        """
        try:
            logger.info(f"🔍 为任务 {task.task_id} 查找有可见窗口的成员卫星")

            member_satellites = []

            # 🔧 修复：优化可见性计算逻辑
            if self._visibility_calculator:
                # 从任务元数据中提取导弹ID
                missile_id = self._extract_missile_id_from_task(task)

                # 如果没有传递missile_target参数，尝试从任务中提取
                if not missile_target and missile_id:
                    missile_target = missile_id
                    logger.info(f"🎯 从任务中提取导弹目标: {missile_target}")

                if missile_target and missile_id:
                    logger.info(f"🔍 使用STK COM接口计算可见性: {missile_id}")

                    # 获取所有可用卫星ID
                    all_satellite_ids = await self._get_all_satellite_ids()

                    # 使用STK COM接口计算星座可见性
                    constellation_result = self._visibility_calculator.calculate_constellation_access(
                        satellite_ids=all_satellite_ids,
                        missile_id=missile_id
                    )

                    if constellation_result and not constellation_result.get('error'):
                        # 获取有访问权限的卫星ID列表
                        visible_satellite_ids = constellation_result.get('satellites_with_access', [])

                        # 排除自己，获取成员卫星实例
                        member_satellite_ids = [sid for sid in visible_satellite_ids if sid != self.satellite_id]
                        member_satellites = await self._get_satellite_agents_by_ids(member_satellite_ids)

                        logger.info(f"✅ 通过STK COM接口找到 {len(member_satellites)} 个成员卫星")
                        for sat in member_satellites:
                            logger.info(f"   成员卫星: {sat.satellite_id}")
                    else:
                        logger.warning(f"⚠️ STK可见性计算失败: {constellation_result.get('error', 'Unknown error')}")
                        logger.info(f"💡 将使用默认成员选择策略")
                else:
                    if not missile_target:
                        logger.warning("⚠️ 缺少导弹目标信息，使用默认成员选择")
                    if not missile_id:
                        logger.warning("⚠️ 无法提取导弹ID信息，使用默认成员选择")
            else:
                logger.warning("⚠️ 可见窗口计算器未初始化，使用默认成员选择")

            # 🔧 新增：如果没有找到成员卫星，使用默认选择策略
            if len(member_satellites) == 0:
                logger.info(f"🔄 启用默认成员选择策略")
                member_satellites = await self._select_default_members(task)

            return member_satellites

        except Exception as e:
            logger.error(f"❌ 查找成员卫星失败: {e}")
            return []

    async def _select_default_members(self, task: TaskInfo) -> List['SatelliteAgent']:
        """
        默认成员选择策略
        当可见性计算失败时，选择部分卫星作为讨论组成员

        Args:
            task: 任务信息

        Returns:
            默认选择的成员卫星列表
        """
        try:
            logger.info(f"🔄 执行默认成员选择策略")

            # 获取系统中所有卫星智能体
            if not self.is_connected_to_multi_agent_system():
                logger.warning("⚠️ 多智能体系统未连接，无法获取其他卫星")
                return []

            all_satellites = self._multi_agent_system.get_all_satellite_agents()

            # 排除自己
            other_satellites = [sat for sat_id, sat in all_satellites.items() if sat_id != self.satellite_id]

            logger.info(f"📊 可选择的其他卫星数量: {len(other_satellites)}")

            # 默认选择策略：选择前2-3个卫星作为成员
            max_members = min(3, len(other_satellites))  # 最多选择3个成员
            selected_members = other_satellites[:max_members]

            logger.info(f"✅ 默认选择了 {len(selected_members)} 个成员卫星:")
            for sat in selected_members:
                logger.info(f"   默认成员: {sat.satellite_id}")

            return selected_members

        except Exception as e:
            logger.error(f"❌ 默认成员选择失败: {e}")
            return []



    async def _get_all_satellite_ids(self) -> List[str]:
        """
        获取所有可用卫星ID - 从STK管理器中获取真实的卫星ID

        Returns:
            卫星ID列表
        """
        try:
            # 从可见性计算器的STK管理器中获取真实的卫星ID
            if self._visibility_calculator and self._visibility_calculator.stk_manager:
                stk_manager = self._visibility_calculator.stk_manager

                # 获取STK中的所有卫星对象
                satellite_objects = stk_manager.get_objects("Satellite")

                # 提取卫星ID（去掉"Satellite/"前缀）
                all_satellite_ids = []
                for sat_path in satellite_objects:
                    if "/" in sat_path:
                        sat_id = sat_path.split("/")[-1]
                        all_satellite_ids.append(sat_id)
                    else:
                        all_satellite_ids.append(sat_path)

                if all_satellite_ids:
                    logger.debug(f"从STK获取到 {len(all_satellite_ids)} 个卫星ID: {all_satellite_ids}")
                    return all_satellite_ids
                else:
                    logger.warning("⚠️ STK中没有找到卫星对象")

            # 如果STK不可用，使用备用方案：从卫星智能体工厂获取
            try:
                from ..agents.satellite_agent_factory import SatelliteAgentFactory
                from ..utils.config_manager import get_config_manager

                config_manager = get_config_manager()
                factory = SatelliteAgentFactory(config_manager)

                # 获取所有已创建的卫星智能体ID
                all_agents = factory.get_all_satellite_agents()
                all_satellite_ids = list(all_agents.keys())

                if all_satellite_ids:
                    logger.debug(f"从卫星工厂获取到 {len(all_satellite_ids)} 个卫星ID: {all_satellite_ids}")
                    return all_satellite_ids

            except Exception as factory_error:
                logger.debug(f"从卫星工厂获取卫星ID失败: {factory_error}")

            # 最后的备用方案：使用Walker星座的标准命名
            logger.warning("⚠️ 无法从STK或工厂获取卫星ID，使用Walker星座标准命名")
            all_satellite_ids = [
                "Satellite11", "Satellite12", "Satellite13",
                "Satellite21", "Satellite22", "Satellite23",
                "Satellite31", "Satellite32", "Satellite33"
            ]

            logger.debug(f"使用备用卫星ID列表: {all_satellite_ids}")
            return all_satellite_ids

        except Exception as e:
            logger.error(f"❌ 获取卫星ID列表失败: {e}")
            return []

    async def _get_satellite_agents_by_ids(self, satellite_ids: List[str]) -> List['SatelliteAgent']:
        """
        根据卫星ID获取卫星智能体实例

        Args:
            satellite_ids: 卫星ID列表

        Returns:
            卫星智能体实例列表
        """
        try:
            satellite_agents = []

            logger.info(f"🔍 尝试获取 {len(satellite_ids)} 个卫星智能体实例")

            # 检查多智能体系统连接状态
            if not self.is_connected_to_multi_agent_system():
                logger.error("❌ 多智能体系统未连接，无法获取其他卫星智能体")
                logger.error("   请确保卫星智能体已正确注册到多智能体系统")
                return []

            # 从多智能体系统中获取卫星智能体实例
            logger.debug(f"📡 多智能体系统类型: {type(self._multi_agent_system).__name__}")

            # 获取系统中所有可用的卫星智能体
            all_available_satellites = self._multi_agent_system.get_all_satellite_agents()
            logger.info(f"📡 系统中可用的卫星智能体: {list(all_available_satellites.keys())}")

            for satellite_id in satellite_ids:
                # 尝试从多智能体系统获取卫星智能体
                satellite_agent = self._multi_agent_system.get_satellite_agent(satellite_id)
                if satellite_agent:
                    satellite_agents.append(satellite_agent)
                    logger.info(f"   ✅ 找到卫星智能体: {satellite_id}")
                else:
                    logger.warning(f"   ⚠️ 未找到卫星智能体: {satellite_id}")
                    logger.debug(f"      可用的卫星: {list(all_available_satellites.keys())}")

            logger.info(f"✅ 成功获取 {len(satellite_agents)} 个卫星智能体实例")
            return satellite_agents

        except Exception as e:
            logger.error(f"❌ 获取卫星智能体实例失败: {e}")
            return []

    async def _handle_discussion_result(self, task: TaskInfo, discussion_result: Dict[str, Any]):
        """
        处理讨论结果

        Args:
            task: 任务信息
            discussion_result: 讨论结果
        """
        try:
            logger.info(f"📊 处理讨论结果，任务: {task.task_id}")

            if discussion_result.get('success', False):
                logger.info(f"✅ 任务 {task.task_id} 讨论成功完成")

                # 更新任务状态
                memory_module = MemoryModule(self.satellite_id)
                task.status = 'completed'
                memory_module.store_task(None, task)

                # 返回结果给仿真调度智能体
                await self._report_result_to_scheduler(task, discussion_result)

            else:
                logger.warning(f"⚠️ 任务 {task.task_id} 讨论失败")
                task.status = 'failed'

        except Exception as e:
            logger.error(f"❌ 处理讨论结果失败: {e}")

    async def _report_result_to_scheduler(self, task: TaskInfo, discussion_result: Dict[str, Any]):
        """
        向仿真调度智能体报告结果

        Args:
            task: 任务信息
            discussion_result: 讨论结果
        """
        try:
            logger.info(f"📤 向仿真调度智能体报告任务 {task.task_id} 的结果")

            # 导入任务完成通知系统
            from src.utils.task_completion_notifier import get_task_completion_notifier, TaskCompletionResult

            # 构建任务完成结果
            completion_result = TaskCompletionResult(
                task_id=task.task_id,
                satellite_id=self.satellite_id,
                discussion_id=discussion_result.get('discussion_id', 'unknown'),
                status='completed' if discussion_result.get('success', False) else 'failed',
                completion_time=datetime.now().isoformat(),
                iterations_completed=discussion_result.get('total_iterations', 0),
                quality_score=discussion_result.get('final_quality_score', 0.0),
                discussion_result=discussion_result,
                metadata={
                    'target_id': task.target_id,
                    'priority': task.priority,
                    'start_time': task.start_time.isoformat() if task.start_time else None,
                    'end_time': task.end_time.isoformat() if task.end_time else None,
                    'satellite_position': getattr(self, 'current_position', None),
                    'task_metadata': task.metadata
                }
            )

            # 通过任务完成通知系统发送通知
            notifier = get_task_completion_notifier()
            await notifier.notify_task_completion(completion_result)

            logger.info(f"✅ 任务结果已成功报告给仿真调度智能体: {task.task_id}")
            logger.info(f"   状态: {completion_result.status}")
            logger.info(f"   迭代次数: {completion_result.iterations_completed}")
            logger.info(f"   质量分数: {completion_result.quality_score:.3f}")

        except Exception as e:
            logger.error(f"❌ 报告结果失败: {e}")

            # 即使报告失败，也尝试发送一个基本的失败通知
            try:
                from src.utils.task_completion_notifier import notify_task_completed
                await notify_task_completed(
                    task_id=task.task_id,
                    satellite_id=self.satellite_id,
                    discussion_id='unknown',
                    status='failed',
                    metadata={'error': str(e)}
                )
            except Exception as e2:
                logger.error(f"❌ 发送失败通知也失败: {e2}")

    def _get_discussion_config(self) -> Dict[str, Any]:
        """
        获取讨论配置

        Returns:
            讨论配置字典
        """
        try:
            # 从配置管理器获取讨论配置
            if hasattr(self, '_config_manager') and self._config_manager:
                config = self._config_manager.get_config()
                return config.get('multi_agent_system', {}).get('leader_agents', {})
            else:
                # 默认配置
                return {
                    'max_discussion_rounds': 5,
                    'discussion_timeout': 600,
                    'consensus_threshold': 0.8
                }
        except Exception as e:
            logger.warning(f"⚠️ 获取讨论配置失败: {e}")
            return {
                'max_discussion_rounds': 5,
                'discussion_timeout': 600,
                'consensus_threshold': 0.8
            }

    def _create_mock_invocation_context(self):
        """
        创建标准ADK Session

        根据ADK官方文档，使用标准方式创建Session用于状态管理

        Returns:
            ADK Session实例
        """
        try:
            from ..utils.adk_standard_context import create_standard_session

            session_id = f"satellite_mock_{self.satellite_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            return create_standard_session(
                app_name="satellite_agent",
                user_id=self.satellite_id,
                session_id=session_id
            )

        except Exception as e:
            logger.error(f"❌ 创建ADK Session失败: {e}")
            return None
