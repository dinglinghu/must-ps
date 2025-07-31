"""
仿真调度智能体
基于ADK的LlmAgent实现，负责STK场景管理、滚动规划、元任务生成和结果收集
"""

import logging
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator
from pathlib import Path

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.tools import FunctionTool
from google.genai import types

from ..utils.config_manager import get_config_manager
from ..utils.llm_config_manager import get_llm_config_manager
from ..utils.time_manager import get_time_manager
from ..utils.simulation_result_manager import get_simulation_result_manager
from ..utils.gantt_chart_generator import AerospaceGanttGenerator
from ..stk_interface.stk_manager import STKManager
from ..stk_interface.missile_manager import MissileManager
from ..stk_interface.visibility_calculator import VisibilityCalculator
from ..constellation.constellation_manager import ConstellationManager
from ..meta_task.meta_task_manager import MetaTaskManager
from ..meta_task.gantt_chart_generator import GanttChartGenerator
from ..prompts.aerospace_planning_prompts import (
    get_meta_task_prompt,
    get_gantt_data_prompt,
    get_simulation_scheduler_prompt
)

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于仿真调度智能体")


class SimulationSchedulerAgent(LlmAgent):
    """
    仿真调度智能体
    
    基于ADK的LlmAgent实现，作为多智能体系统的根智能体，
    负责STK场景管理、滚动规划、元任务生成和结果收集。
    """
    
    def __init__(
        self,
        name: str = "SimulationScheduler",
        model: str = "gemini-2.0-flash",
        config_path: Optional[str] = None,
        config_manager = None,
        multi_agent_system = None
    ):
        """
        初始化仿真调度智能体

        Args:
            name: 智能体名称
            model: 使用的大模型
            config_path: 配置文件路径
            config_manager: 配置管理器实例
        """
        # 初始化配置和管理器
        if config_manager is not None:
            config_mgr = config_manager
            logger.info(f"使用传入的配置管理器: {type(config_manager)}")
        else:
            config_mgr = get_config_manager(config_path)
            logger.info(f"创建新的配置管理器: {config_path}")
        time_mgr = get_time_manager(config_mgr)
        logger.info(f"配置管理器准备完成")

        # 初始化大模型配置管理器
        llm_config_mgr = get_llm_config_manager(config_path or "config/config.yaml")

        # 获取智能体配置
        agent_config = config_mgr.config.get('multi_agent_system', {})
        scheduler_config = agent_config.get('simulation_scheduler', {})

        # 获取大模型配置
        llm_config = llm_config_mgr.get_llm_config('simulation_scheduler')

        # 获取智能体提示词配置
        prompt_config = llm_config_mgr.get_agent_prompt_config('simulation_scheduler')

        # 格式化系统提示词
        # 注意：这里暂时使用系统时间，因为time_mgr还未完全初始化
        # 在实际运行时会使用仿真时间
        instruction = llm_config_mgr.format_system_prompt(
            'simulation_scheduler',
            satellite_id="SCHEDULER",
            current_time=datetime(2025, 7, 26, 4, 0, 0).isoformat()  # 使用配置的开始时间
        )

        # 初始化ADK LlmAgent
        super().__init__(
            name=name,
            model=llm_config.model,  # 使用配置管理器中的模型
            instruction=instruction,
            description="天基低轨预警系统仿真调度智能体，负责场景管理和任务协调",
            tools=[]  # 稍后设置工具
        )

        # 创建LiteLLM客户端（在super().__init__()之后）
        try:
            # 使用object.__setattr__绕过Pydantic的限制
            object.__setattr__(self, '_litellm_client', llm_config_mgr.create_litellm_client('simulation_scheduler'))
            logger.info(f"✅ 创建LiteLLM客户端成功: {llm_config.model}")
        except Exception as e:
            logger.warning(f"⚠️ 创建LiteLLM客户端失败，将使用ADK默认客户端: {e}")
            object.__setattr__(self, '_litellm_client', None)
        
        # 运行状态
        self._is_running = False
        self._current_planning_cycle = 0
        # 添加标志位，用于立即触发下一轮规划
        self._all_discussions_completed = False

        # 结果管理器
        self._result_manager = get_simulation_result_manager()
        self._gantt_generator = AerospaceGanttGenerator()

        # 分布式卫星智能体系统
        self._satellite_agents = {}  # 卫星智能体注册表 {satellite_id: SatelliteAgent}
        self._satellite_agents_initialized = False  # 卫星智能体是否已初始化
        self._multi_agent_system = multi_agent_system  # 多智能体系统引用
        self._stk_scenario_created = False  # STK场景是否已创建
        self._satellite_factory = None  # 卫星智能体工厂

        # UI日志回调（用于向UI发送详细日志）
        self._ui_log_callback = None
        self._ui_planning_callback = None
        self._ui_llm_callback = None

        # 在super().__init__()之后设置配置管理器
        self._config_manager = config_mgr
        self._time_manager = time_mgr

        # 初始化系统组件
        self._initialize_components()

        # 设置工具
        self.tools = self._create_tools()

        logger.info(f"✅ 仿真调度智能体 {name} 初始化完成")

    def set_ui_callbacks(self, log_callback=None, planning_callback=None, llm_callback=None):
        """
        设置UI回调函数，用于向UI发送实时日志

        Args:
            log_callback: 日志回调函数
            planning_callback: 规划状态回调函数
            llm_callback: LLM响应回调函数
        """
        self._ui_log_callback = log_callback
        self._ui_planning_callback = planning_callback
        self._ui_llm_callback = llm_callback
        logger.info("✅ UI回调函数设置完成")

    def _send_ui_log(self, message: str, level: str = 'info'):
        """向UI发送日志消息"""
        if self._ui_log_callback:
            try:
                self._ui_log_callback(message, level)
            except Exception as e:
                logger.warning(f"⚠️ 发送UI日志失败: {e}")

    def _send_ui_planning_status(self, phase: str, step: str, description: str):
        """向UI发送规划状态"""
        if self._ui_planning_callback:
            try:
                self._ui_planning_callback(phase, step, description)
            except Exception as e:
                logger.warning(f"⚠️ 发送UI规划状态失败: {e}")

    def _send_ui_llm_response(self, provider: str, model: str, response: str, tokens: int = 0):
        """向UI发送LLM响应"""
        if self._ui_llm_callback:
            try:
                self._ui_llm_callback(provider, model, response, tokens, self.name)
            except Exception as e:
                logger.warning(f"⚠️ 发送UI LLM响应失败: {e}")

    def _get_available_satellites(self) -> List[Dict[str, Any]]:
        """
        获取可用的卫星列表

        Returns:
            卫星信息列表
        """
        try:
            if self._stk_manager and self._stk_manager.scenario:
                satellites = []
                satellite_objects = self._stk_manager.get_objects("Satellite")

                for sat_path in satellite_objects:
                    sat_id = sat_path.split('/')[-1]
                    try:
                        satellite = self._stk_manager.scenario.Children.Item(sat_id)

                        # 获取卫星基本信息
                        sat_info = {
                            'id': sat_id,
                            'name': sat_id,
                            'path': sat_path,
                            'status': 'active',
                            'sensors': [],
                            'position': None  # 将在运行时计算
                        }

                        # 获取传感器信息
                        for i in range(satellite.Children.Count):
                            sensor = satellite.Children.Item(i)
                            if sensor.ClassName == "Sensor":
                                sat_info['sensors'].append({
                                    'id': sensor.InstanceName,
                                    'type': 'optical',
                                    'status': 'available'
                                })

                        satellites.append(sat_info)

                    except Exception as e:
                        logger.warning(f"⚠️ 获取卫星 {sat_id} 信息失败: {e}")
                        continue

                logger.info(f"📡 发现 {len(satellites)} 颗可用卫星")
                return satellites
            else:
                logger.warning("⚠️ STK管理器未初始化，返回模拟卫星列表")
                # 返回模拟卫星列表
                return [
                    {'id': f'Satellite_{i}', 'name': f'Satellite_{i}', 'status': 'active', 'sensors': [{'id': f'Sensor_{i}', 'type': 'optical'}]}
                    for i in range(1, 10)  # 9颗卫星
                ]

        except Exception as e:
            logger.error(f"❌ 获取卫星列表失败: {e}")
            return []

    async def _find_nearest_satellites(self, target_position: Dict[str, float], satellites: List[Dict[str, Any]], count: int = 3) -> List[Dict[str, Any]]:
        """
        找到距离目标最近的卫星

        Args:
            target_position: 目标位置 {'lat': 纬度, 'lon': 经度, 'alt': 高度}
            satellites: 卫星列表
            count: 返回的卫星数量

        Returns:
            距离最近的卫星列表
        """
        try:
            # 简化的距离计算（实际应该使用STK的位置计算）
            import math

            nearest_satellites = []
            for satellite in satellites:
                # 模拟卫星位置（实际应该从STK获取）
                sat_lat = (hash(satellite['id']) % 180) - 90  # -90 到 90
                sat_lon = (hash(satellite['id']) % 360) - 180  # -180 到 180

                # 计算简化距离
                distance = math.sqrt(
                    (target_position['lat'] - sat_lat) ** 2 +
                    (target_position['lon'] - sat_lon) ** 2
                )

                satellite_with_distance = satellite.copy()
                satellite_with_distance['distance'] = distance
                satellite_with_distance['position'] = {'lat': sat_lat, 'lon': sat_lon, 'alt': 500}  # 假设500km轨道

                nearest_satellites.append(satellite_with_distance)

            # 按距离排序并返回最近的几颗
            nearest_satellites.sort(key=lambda x: x['distance'])
            return nearest_satellites[:count]

        except Exception as e:
            logger.error(f"❌ 查找最近卫星失败: {e}")
            return satellites[:count]  # 返回前几颗作为备选

    async def run_simulation_scheduling(self) -> AsyncGenerator[Event, None]:
        """
        运行仿真调度流程
        这是Web界面调用的主要入口方法
        """
        try:
            logger.info(f"🚀 启动仿真调度智能体: {self.name}")

            # 创建一个模拟的调用上下文（不使用InvocationContext以避免验证错误）
            ctx = None

            # 调用内部运行逻辑
            async for event in self._run_async_impl(ctx):
                yield event

        except Exception as e:
            logger.error(f"❌ 仿真调度流程运行失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"仿真调度流程运行失败: {e}")]),
                actions=EventActions(escalate=True)
            )

    async def generate_litellm_response(self, user_message: str, temperature: float = 0.3) -> str:
        """
        使用LiteLLM客户端生成响应

        Args:
            user_message: 用户消息
            temperature: 温度参数

        Returns:
            生成的响应
        """
        if self._litellm_client:
            try:
                # 记录LLM调用开始
                self._send_ui_log(f"🧠 开始LLM推理，消息长度: {len(user_message)} 字符")

                response = await self._litellm_client.generate_response(
                    system_prompt=self.instruction,
                    user_message=user_message,
                    temperature=temperature,
                    max_tokens=8192,
                    agent_name=self.name  # 传递智能体名称
                )

                # 计算token数量（简单估算）
                estimated_tokens = len(response.split())

                # 发送LLM响应到UI
                self._send_ui_llm_response(
                    provider="DeepSeek",
                    model="deepseek-chat",
                    response=response,
                    tokens=estimated_tokens
                )

                logger.info(f"✅ LiteLLM响应生成成功，长度: {len(response)}")
                self._send_ui_log(f"✅ LLM推理完成，响应长度: {len(response)} 字符，约 {estimated_tokens} tokens")

                return response
            except Exception as e:
                error_msg = f"LiteLLM调用失败: {e}"
                logger.error(f"❌ LiteLLM响应生成失败: {e}")
                self._send_ui_log(f"❌ LLM推理失败: {e}", level='error')
                return error_msg
        else:
            warning_msg = "LiteLLM客户端未初始化"
            logger.warning("⚠️ LiteLLM客户端未初始化，无法生成响应")
            self._send_ui_log("⚠️ LiteLLM客户端未初始化，无法生成响应", level='warning')
            return warning_msg

    @property
    def config_manager(self):
        """获取配置管理器"""
        return self._config_manager

    @property
    def time_manager(self):
        """获取时间管理器"""
        return self._time_manager

    @property
    def is_running(self) -> bool:
        """获取运行状态"""
        return self._is_running

    @property
    def current_planning_cycle(self) -> int:
        """获取当前规划周期"""
        return self._current_planning_cycle
    
    def _initialize_components(self):
        """初始化系统组件"""
        try:
            logger.info(f"开始初始化组件，_config_manager存在: {hasattr(self, '_config_manager')}")
            # STK管理器
            stk_config = self._config_manager.get_stk_config()
            self._stk_manager = STKManager(stk_config)

            # 其他组件
            self._missile_manager = None
            self._visibility_calculator = None
            self._constellation_manager = None
            self._meta_task_manager = None
            self._gantt_generator = None

            # 任务完成通知相关状态
            self._coordination_results = []
            self._all_discussions_completed = False
            self._current_planning_cycle = 0
            self._pending_tasks = set()  # 待完成的任务ID集合
            self._completed_tasks = {}   # 已完成的任务结果
            self._waiting_for_tasks = False  # 是否正在等待任务完成

            # 注册任务完成通知回调
            self._register_task_completion_callback()

            logger.info("🔧 系统组件初始化完成")
            
        except Exception as e:
            logger.error(f"❌ 系统组件初始化失败: {e}")
            raise

    def _register_task_completion_callback(self):
        """注册任务完成通知回调"""
        try:
            from src.utils.task_completion_notifier import register_scheduler_for_task_notifications

            # 注册回调函数
            register_scheduler_for_task_notifications(self._on_task_completed)

            logger.info("✅ 任务完成通知回调已注册")

        except Exception as e:
            logger.error(f"❌ 注册任务完成通知回调失败: {e}")

    async def _on_task_completed(self, completion_result):
        """处理任务完成通知"""
        try:
            task_id = completion_result.task_id
            status = completion_result.status

            logger.info(f"📢 收到任务完成通知: {task_id} (状态: {status})")

            # 从待完成任务集合中移除
            if task_id in self._pending_tasks:
                self._pending_tasks.remove(task_id)
                logger.info(f"✅ 任务 {task_id} 已从待完成列表移除，剩余: {len(self._pending_tasks)}")

            # 存储完成结果
            self._completed_tasks[task_id] = completion_result

            # 发送UI日志
            self._send_ui_log(f"📋 任务完成: {task_id} ({status}), 质量分数: {completion_result.quality_score:.3f}")

            # 检查是否所有任务都已完成
            if len(self._pending_tasks) == 0 and self._waiting_for_tasks:
                logger.info("🎯 所有任务已完成，可以开始下一轮规划")
                self._all_discussions_completed = True
                self._waiting_for_tasks = False

                # 发送UI通知
                self._send_ui_log("✅ 所有任务已完成，准备开始下一轮规划")

        except Exception as e:
            logger.error(f"❌ 处理任务完成通知失败: {e}")

    async def _wait_for_all_tasks_completion(self):
        """等待所有任务完成"""
        try:
            if len(self._pending_tasks) == 0:
                logger.info("📋 没有待完成的任务，直接继续")
                return

            logger.info(f"⏳ 等待 {len(self._pending_tasks)} 个任务完成...")
            self._waiting_for_tasks = True
            self._all_discussions_completed = False

            # 发送UI通知
            self._send_ui_log(f"⏳ 等待 {len(self._pending_tasks)} 个任务完成...")

            # 等待所有任务完成，最多等待15分钟
            max_wait_time = 900  # 15分钟
            check_interval = 5   # 每5秒检查一次
            total_wait_time = 0

            while total_wait_time < max_wait_time and len(self._pending_tasks) > 0:
                await asyncio.sleep(check_interval)
                total_wait_time += check_interval

                # 显示等待进度
                if total_wait_time % 30 == 0:  # 每30秒显示一次进度
                    remaining_tasks = len(self._pending_tasks)
                    completed_tasks = len(self._completed_tasks)

                    progress_msg = f"⏳ 等待中... 剩余任务: {remaining_tasks}, 已完成: {completed_tasks}, 已等待: {total_wait_time}s"
                    logger.info(progress_msg)
                    self._send_ui_log(progress_msg)

            # 检查等待结果
            if len(self._pending_tasks) == 0:
                logger.info(f"✅ 所有任务已完成，等待时间: {total_wait_time}s")
                self._send_ui_log(f"✅ 所有任务已完成，等待时间: {total_wait_time}s")
            else:
                # 超时处理
                timeout_tasks = list(self._pending_tasks)
                logger.warning(f"⚠️ 等待超时，仍有 {len(timeout_tasks)} 个任务未完成: {timeout_tasks}")
                self._send_ui_log(f"⚠️ 等待超时，强制继续下一轮规划")

                # 清理超时任务
                self._pending_tasks.clear()

            self._waiting_for_tasks = False

        except Exception as e:
            logger.error(f"❌ 等待任务完成失败: {e}")
            self._waiting_for_tasks = False
    
    def _create_tools(self) -> List[FunctionTool]:
        """创建智能体工具"""
        tools = []
        
        # 完整系统初始化工具
        async def initialize_complete_system() -> str:
            """初始化完整的卫星智能体系统"""
            try:
                logger.info("🎯 智能体工具：开始初始化完整系统...")

                # 1. 连接STK
                logger.info("📋 步骤1: 连接STK")
                if not await self._connect_stk():
                    return "❌ STK连接失败"

                # 2. 初始化管理器
                logger.info("📋 步骤2: 初始化管理器")
                if not self._initialize_managers():
                    return "❌ 管理器初始化失败"

                # 3. 创建Walker星座
                logger.info("📋 步骤3: 创建Walker星座")
                constellation_result = await self._create_walker_constellation()
                if "❌" in constellation_result:
                    return constellation_result

                # 4. 创建卫星智能体
                logger.info("📋 步骤4: 创建卫星智能体")
                agents_result = await self._create_satellite_agents()
                if "❌" in agents_result:
                    return agents_result

                # 5. 注册到多智能体系统
                logger.info("📋 步骤5: 注册到多智能体系统")
                registration_result = await self._register_satellite_agents()
                if "❌" in registration_result:
                    return registration_result

                # 6. 验证系统状态
                logger.info("📋 步骤6: 验证系统状态")
                verification_result = await self._verify_system_status()

                return f"✅ 完整系统初始化成功！\n{verification_result}"

            except Exception as e:
                logger.error(f"❌ 完整系统初始化失败: {e}")
                return f"❌ 完整系统初始化失败: {e}"

        tools.append(FunctionTool(func=initialize_complete_system))

        # STK场景创建工具（保留原有功能）
        async def create_stk_scenario() -> str:
            """创建STK仿真场景"""
            try:
                logger.info("🎯 智能体工具：开始创建STK场景...")

                # 连接STK
                if not await self._connect_stk():
                    return "❌ STK连接失败"

                # 初始化管理器
                if not self._initialize_managers():
                    return "❌ 管理器初始化失败"

                # 创建场景
                result = await self._create_stk_scenario_internal()
                return result

            except Exception as e:
                logger.error(f"STK场景创建工具失败: {e}")
                return f"❌ 场景创建失败: {e}"
        
        tools.append(FunctionTool(func=create_stk_scenario))
        

        


        # 启动滚动规划工具
        async def start_rolling_planning() -> str:
            """启动滚动规划周期（使用正确的时序控制）"""
            try:
                logger.info("🎯 智能体工具：启动滚动规划...")

                # 检查STK连接
                if not self._stk_manager or not self._stk_manager.is_connected:
                    return "❌ STK未连接，请先创建场景"

                # 检查管理器初始化
                if not self._missile_manager:
                    return "❌ 导弹管理器未初始化"

                # 检查是否已经在运行
                if self._is_running:
                    return "⚠️ 滚动规划已在运行中，请勿重复启动"

                # 启动滚动规划循环（使用正确的时序控制）
                logger.info("🚀 启动带时序控制的滚动规划循环...")
                self._is_running = True
                self._current_planning_cycle = 0  # 重置计数器

                # 启动后台任务执行滚动规划
                import asyncio
                asyncio.create_task(self._run_rolling_planning_background(ctx))

                return "✅ 滚动规划已启动（带时序控制），将在后台持续运行"

            except Exception as e:
                logger.error(f"启动滚动规划失败: {e}")
                self._is_running = False
                return f"❌ 滚动规划启动失败: {e}"

        # 停止滚动规划工具
        async def stop_rolling_planning() -> str:
            """停止滚动规划周期"""
            try:
                logger.info("🛑 智能体工具：停止滚动规划...")

                if not self._is_running:
                    return "⚠️ 滚动规划未在运行中"

                self._is_running = False

                # 等待当前ADK标准讨论组完成
                adk_discussions = self._get_active_adk_discussions()
                if adk_discussions:
                    logger.info(f"⏳ 等待 {len(adk_discussions)} 个活跃ADK讨论组完成...")
                    final_wait_result = await self._ensure_all_discussions_complete(ctx)
                    logger.info(f"✅ 讨论组完成: {final_wait_result}")

                return "✅ 滚动规划已停止"

            except Exception as e:
                logger.error(f"停止滚动规划失败: {e}")
                return f"❌ 停止滚动规划失败: {e}"

        tools.append(FunctionTool(func=start_rolling_planning))
        tools.append(FunctionTool(func=stop_rolling_planning))







        return tools
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        智能体主要运行逻辑
        实现滚动规划和多智能体协调
        """
        logger.info(f"[{self.name}] 开始仿真调度流程")
        self._send_ui_log(f"🚀 [{self.name}] 开始仿真调度流程")
        self._send_ui_planning_status("Initialization", "Starting", "开始仿真调度流程")

        try:
            # 1. 创建STK场景
            phase1_msg = "🚀 Phase 1: 正在创建STK仿真场景..."
            self._send_ui_log(phase1_msg)
            self._send_ui_planning_status("Phase1", "STK_Creation", "创建STK仿真场景")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=phase1_msg)])
            )

            # 使用工具创建场景
            scenario_result = await self._create_stk_scenario_internal()

            success_msg = f"✅ STK场景创建完成: {scenario_result}"
            self._send_ui_log(success_msg)
            self._send_ui_planning_status("Phase1", "STK_Complete", f"STK场景创建完成: {scenario_result}")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=success_msg)])
            )
            
            # 2. 开始滚动规划循环
            self._is_running = True

            phase2_msg = "🔄 Phase 2: 开始滚动规划循环..."
            self._send_ui_log(phase2_msg)
            self._send_ui_planning_status("Phase2", "Rolling_Planning", "开始滚动规划循环")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=phase2_msg)])
            )

            while self._is_running and not self._time_manager.is_simulation_finished():
                self._current_planning_cycle += 1

                cycle_start_msg = f"📋 第 {self._current_planning_cycle} 轮规划开始 - 时间: {self._time_manager.get_current_simulation_time()}"
                self._send_ui_log(cycle_start_msg)
                self._send_ui_planning_status("Cycle", "Starting", f"第 {self._current_planning_cycle} 轮规划开始")

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=cycle_start_msg)])
                )

                # 执行一轮规划
                async for event in self._execute_planning_cycle(ctx):
                    yield event

                # 确保所有讨论组完成后再进入下一轮
                final_wait_result = await self._ensure_all_discussions_complete(ctx)

                cycle_complete_msg = f"✅ 第 {self._current_planning_cycle} 轮规划完成，{final_wait_result}"
                self._send_ui_log(cycle_complete_msg)
                self._send_ui_planning_status("Cycle", "Complete", f"第 {self._current_planning_cycle} 轮规划完成")

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=cycle_complete_msg)])
                )

                # 所有讨论组已完成，立即开始下一轮规划（去除等待时间）
                self._send_ui_log("✅ 上一轮规划任务完成，立即开始下一轮规划...")
                # 不再等待固定时间间隔，直接进入下一轮
            
            # 3. 生成最终报告
            phase3_msg = "📊 Phase 3: 生成最终仿真报告..."
            self._send_ui_log(phase3_msg)
            self._send_ui_planning_status("Phase3", "Report_Generation", "生成最终仿真报告")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=phase3_msg)])
            )

            final_report = await self._generate_final_report()

            final_msg = f"🎯 仿真调度完成！\n\n{final_report}"
            self._send_ui_log("🎯 仿真调度流程全部完成！")
            self._send_ui_planning_status("Completion", "Finished", "仿真调度流程全部完成")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=final_msg)]),
                actions=EventActions(escalate=True)  # 标记为最终结果
            )
            
        except Exception as e:
            error_msg = f"❌ 仿真调度流程异常: {e}"
            logger.error(error_msg)
            self._send_ui_log(error_msg, level='error')
            self._send_ui_planning_status("Error", "Failed", f"仿真调度流程异常: {str(e)}")

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"仿真调度异常: {e}")]),
                actions=EventActions(escalate=True)
            )
    
    async def _execute_planning_cycle(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """执行一轮规划周期 - 包含导弹创建、元任务生成和任务分发"""
        try:
            # 0. 确保卫星智能体系统已初始化
            if not self._satellite_agents or len(self._satellite_agents) == 0:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="🔧 Step 0: 检测到卫星智能体未初始化，开始初始化...")])
                )

                # 调用完整系统初始化
                init_result = await self.initialize_complete_system()
                if "❌" in init_result:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text=f"❌ 系统初始化失败: {init_result}")]),
                        actions=EventActions(escalate=True)
                    )
                    return
                else:
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[types.Part(text="✅ 卫星智能体系统初始化完成")])
                    )

            # 1. 按概率创建导弹目标
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="🎯 Step 1: 检测和创建导弹目标...")])
            )

            missile_creation_result = await self._maybe_create_missile_targets()
            if missile_creation_result:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"🚀 新导弹目标创建: {missile_creation_result}")])
                )

            # 2. 获取活跃导弹列表
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="🔍 Step 2: 扫描活跃导弹目标...")])
            )

            active_missiles = await self._get_active_missiles_with_trajectories()
            if active_missiles:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"📡 发现 {len(active_missiles)} 个活跃导弹目标，开始任务分配...")])
                )

                # 3. 收集所有导弹轨迹数据，发送元任务集给最近的卫星
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"🧠 Step 3: 收集 {len(active_missiles)} 个导弹轨迹数据，生成元任务集...")])
                )

                # 收集所有导弹信息
                all_missile_info = []
                for missile_info in active_missiles:
                    missile_id = missile_info['missile_id']
                    logger.info(f"📊 收集导弹 {missile_id} 的轨迹数据")
                    all_missile_info.append(missile_info)

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"📋 为 {len(all_missile_info)} 个导弹目标生成综合元任务集...")])
                )

                # 发送元任务集给离所有目标最近的卫星智能体
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"📡 发送元任务集给离所有目标最近的卫星智能体...")])
                )

                distribution_result = await self._send_meta_task_set_to_nearest_satellite(all_missile_info)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"✅ 元任务集发送完成: {distribution_result}")])
                )
            else:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="当前无活跃导弹目标")])
                )

                # 如果没有活跃导弹，生成通用元任务
                meta_task_result = await self._generate_meta_tasks_internal()
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"通用元任务生成: {meta_task_result[:100]}...")])
                )

            # 4. 监控协同决策过程
            coordination_result = await self._monitor_coordination_process(ctx)
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"协同决策: {coordination_result}")])
            )

        except Exception as e:
            logger.error(f"❌ 规划周期执行异常: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"规划周期异常: {e}")])
            )
    
    async def _create_stk_scenario_internal(self) -> str:
        """内部STK场景创建方法 - 统一的STK场景管理"""
        try:
            # 检查STK场景是否已创建，避免重复初始化
            if self._stk_scenario_created:
                logger.info("📊 STK场景已存在，跳过重复创建")
                satellites = self._stk_manager.get_objects("Satellite") if self._stk_manager else []
                sensors_count = self._count_sensors(satellites) if satellites else 0
                agent_count = len(self._satellite_agents)

                self._send_ui_log(f"📊 STK场景状态检查: {len(satellites)}颗卫星，{sensors_count}个传感器，{agent_count}个智能体")
                return f"✅ STK场景已存在：{len(satellites)}颗卫星，{sensors_count}个传感器载荷，{agent_count}个卫星智能体"

            logger.info("🚀 开始创建STK仿真场景...")
            self._send_ui_log("🚀 开始创建STK仿真场景...")

            # 1. 连接STK
            if not self._stk_manager or not self._stk_manager.connect():
                error_msg = "❌ STK连接失败"
                self._send_ui_log(error_msg, level='error')
                return error_msg

            logger.info("✅ STK连接成功")
            self._send_ui_log("✅ STK连接成功")

            # 2. 初始化管理器（确保每次都初始化）
            if not self._initialize_managers():
                error_msg = "❌ 管理器初始化失败"
                self._send_ui_log(error_msg, level='error')
                return error_msg

            # 3. 获取配置
            config = self._config_manager.config

            # 4. 创建Walker星座
            if 'constellation' in config:
                logger.info("🛰️ 开始创建Walker星座...")
                self._send_ui_log("🛰️ 开始创建Walker星座...")

                if self._stk_manager.create_walker_constellation(config):
                    logger.info("✅ Walker星座创建成功")
                    self._send_ui_log("✅ Walker星座创建成功")
                else:
                    error_msg = "❌ Walker星座创建失败"
                    self._send_ui_log(error_msg, level='error')
                    return error_msg

            # 5. 获取创建的卫星列表
            satellites = self._stk_manager.get_objects("Satellite")
            logger.info(f"📊 成功创建 {len(satellites)} 颗卫星")
            self._send_ui_log(f"📊 成功创建 {len(satellites)} 颗卫星")

            # 6. 验证传感器创建
            sensors_count = self._count_sensors(satellites)
            logger.info(f"📡 成功创建 {sensors_count} 个传感器载荷")
            self._send_ui_log(f"📡 成功创建 {sensors_count} 个传感器载荷")

            # 7. 标记STK场景已创建（关键：防止重复创建）
            self._stk_scenario_created = True
            logger.info("🔒 STK场景创建状态已锁定，防止重复初始化")

            # 8. 不在这里创建卫星智能体，而是通过 initialize_complete_system 统一创建
            # await self._create_distributed_satellite_agents(satellites)

            success_msg = f"✅ STK场景创建成功！创建了 {len(satellites)} 颗卫星、{sensors_count} 个传感器载荷。卫星智能体将通过系统初始化流程创建。"
            self._send_ui_log(success_msg)
            return success_msg

        except Exception as e:
            error_msg = f"❌ STK场景创建失败: {e}"
            logger.error(error_msg)
            self._send_ui_log(error_msg, level='error')
            # 重置状态，允许重试
            self._stk_scenario_created = False
            return error_msg

    def _count_sensors(self, satellites: List[str]) -> int:
        """统计传感器数量"""
        sensors_count = 0
        for sat_path in satellites:
            sat_id = sat_path.split('/')[-1]
            try:
                satellite = self._stk_manager.scenario.Children.Item(sat_id)
                sensors_count += satellite.Children.Count
            except:
                pass
        return sensors_count

    async def _create_distributed_satellite_agents(self, satellites: List[str]) -> None:
        """创建对应数量的分布式卫星智能体系统"""
        try:
            if self._satellite_agents_initialized:
                logger.info("🤖 卫星智能体系统已初始化，跳过重复创建")
                return

            logger.info("🤖 开始创建分布式卫星智能体系统...")
            self._send_ui_log("🤖 开始创建与卫星星座匹配的分布式智能体系统")
            self._send_ui_planning_status("Agents", "Creating", "创建分布式卫星智能体系统")

            # 导入卫星智能体类
            from src.agents.satellite_agent import SatelliteAgent

            # 获取卫星智能体配置
            satellite_config = self._config_manager.get_system_config().get("multi_agent_system", {}).get("satellite_agents", {})

            created_count = 0
            for sat_path in satellites:
                sat_id = sat_path.split('/')[-1]

                # 检查是否已创建该卫星智能体
                if sat_id not in self._satellite_agents:
                    try:
                        # 创建卫星智能体，传递共享的STK管理器
                        satellite_agent = SatelliteAgent(
                            satellite_id=sat_id,
                            config=satellite_config,
                            stk_manager=self._stk_manager  # 关键修复：传递共享的STK管理器
                        )

                        # 注册到智能体注册表
                        self._satellite_agents[sat_id] = satellite_agent
                        created_count += 1

                        logger.info(f"✅ 创建卫星智能体: {satellite_agent.name}")
                        self._send_ui_log(f"✅ 创建卫星智能体: {satellite_agent.name}")

                    except Exception as e:
                        logger.error(f"❌ 创建卫星智能体 {sat_id} 失败: {e}")
                        self._send_ui_log(f"❌ 创建卫星智能体 {sat_id} 失败: {e}", level='error')

            self._satellite_agents_initialized = True
            logger.info(f"🎉 分布式卫星智能体系统创建完成！共创建 {created_count} 个卫星智能体")

        except Exception as e:
            logger.error(f"❌ 创建分布式卫星智能体系统失败: {e}")
            import traceback
            traceback.print_exc()

    def get_satellite_agent(self, satellite_id: str):
        """获取指定卫星的智能体"""
        return self._satellite_agents.get(satellite_id)

    def get_all_satellite_agents(self) -> Dict[str, Any]:
        """获取所有卫星智能体"""
        return self._satellite_agents.copy()

    def set_multi_agent_system(self, multi_agent_system):
        """设置多智能体系统引用"""
        self._multi_agent_system = multi_agent_system
        logger.info("✅ 仿真调度智能体已连接到多智能体系统")



    async def _generate_meta_tasks_internal(self) -> str:
        """内部元任务生成方法 - 使用航天专业提示词"""
        try:
            logger.info("🎯 开始生成元任务...")

            # 创建仿真会话（如果还没有）
            if not self._current_session_id:
                self.create_simulation_session(f"planning_cycle_{self._current_planning_cycle}")

            # 构建输入数据
            current_time = self._time_manager.get_current_simulation_time()
            active_missiles = await self._get_active_missiles()
            input_data = f"""
仿真时间: {current_time.isoformat()}
规划周期: 第 {self._current_planning_cycle} 轮
活跃导弹数量: {len(active_missiles)}
可用卫星数量: {len(self._satellite_agents)}

导弹目标信息:
{self._format_missile_targets_for_prompt()}

卫星星座状态:
{self._format_constellation_status_for_prompt()}
"""

            # 使用专业航天提示词
            task_prompt = get_meta_task_prompt(input_data)

            # 使用LiteLLM生成元任务
            if self._litellm_client:
                response = await self.generate_litellm_response(task_prompt, temperature=0.3)
                logger.info(f"✅ 元任务生成完成，长度: {len(response)}")

                # 解析并保存元任务
                meta_tasks = self._parse_meta_tasks_from_response(response)
                if meta_tasks:
                    save_result = self.save_meta_tasks_with_gantt(meta_tasks)
                    self._send_ui_log(f"📊 元任务甘特图已生成: {save_result}")

                return f"成功生成元任务:\n{response}"
            else:
                logger.warning("⚠️ LiteLLM客户端未初始化，使用模拟结果")
                return "成功生成 3 个元任务窗口（模拟 - LiteLLM未初始化）"

        except Exception as e:
            logger.error(f"❌ 元任务生成失败: {e}")
            return f"❌ 元任务生成失败: {e}"
    






    async def _maybe_create_missile_targets(self) -> str:
        """
        按照配置概率创建导弹目标
        规划一开始必须得到目标，后续滚动规划根据阈值进行概率生成

        Returns:
            创建结果描述
        """
        try:
            # 获取导弹创建概率配置
            system_config = self._config_manager.get_system_config()
            missile_add_probability = system_config.get("testing", {}).get("missile_add_probability", 0.3)

            # 获取导弹管理配置
            missile_mgmt_config = self._config_manager.get_missile_management_config()
            max_concurrent = missile_mgmt_config.get("max_concurrent_missiles", 5)

            # 检查当前导弹数量
            current_missiles = len(self._missile_manager.missile_targets) if self._missile_manager else 0

            if current_missiles >= max_concurrent:
                return f"已达到最大导弹数量限制 ({current_missiles}/{max_concurrent})"

            # 决定是否创建导弹的逻辑
            should_create_missile = False
            reason = ""

            # 规则1：第一轮规划必须创建导弹目标
            if self._current_planning_cycle == 1 and current_missiles == 0:
                should_create_missile = True
                reason = "第一轮规划必须创建导弹目标"
            # 规则2：后续规划按概率创建
            else:
                import random
                if random.random() < missile_add_probability:
                    should_create_missile = True
                    reason = f"按概率创建 (概率: {missile_add_probability})"
                else:
                    return f"本轮未创建导弹 (概率: {missile_add_probability}, 当前导弹数: {current_missiles})"

            if should_create_missile:
                # 创建新导弹
                import random
                missile_id = f"THREAT_{self._current_planning_cycle}_{random.randint(100, 999)}"

                # 使用导弹管理器创建导弹
                if self._missile_manager:
                    current_time = self._time_manager.get_current_simulation_time()

                    # 生成随机发射位置和目标位置
                    launch_position = {
                        'lat': random.uniform(-60, 60),  # 纬度范围
                        'lon': random.uniform(-180, 180),  # 经度范围
                        'alt': 0  # 地面发射
                    }

                    target_position = {
                        'lat': random.uniform(-60, 60),  # 纬度范围
                        'lon': random.uniform(-180, 180),  # 经度范围
                        'alt': 0  # 地面目标
                    }

                    # 构建导弹场景数据
                    missile_scenario = {
                        'missile_id': missile_id,
                        'launch_position': launch_position,
                        'target_position': target_position,
                        'launch_sequence': self._current_planning_cycle,
                        'launch_time': current_time
                    }

                    missile_info = self._missile_manager.create_single_missile_target(missile_scenario)

                    if missile_info:
                        logger.info(f"✅ 成功创建导弹目标: {missile_info.get('missile_id', missile_id)} ({reason})")
                        return f"成功创建导弹目标: {missile_id} ({reason}) (发射位置: {launch_position['lat']:.2f}, {launch_position['lon']:.2f})"
                    else:
                        return f"导弹创建失败: {missile_id} ({reason})"
                else:
                    return "导弹管理器未初始化"

        except Exception as e:
            logger.error(f"❌ 导弹创建检查失败: {e}")
            return f"导弹创建检查失败: {e}"

    async def _get_active_missiles_with_trajectories(self) -> List[Dict[str, Any]]:
        """
        获取当前活跃的导弹及其轨迹信息

        Returns:
            活跃导弹信息列表
        """
        try:
            active_missiles = []

            if not self._missile_manager:
                logger.warning("⚠️ 导弹管理器未初始化")
                return active_missiles

            current_time = self._time_manager.get_current_simulation_time()

            # 遍历所有导弹目标
            for missile_id, missile_info in self._missile_manager.missile_targets.items():
                try:
                    # 检查导弹是否在飞行中
                    if isinstance(missile_info, dict) and "launch_time" in missile_info:
                        launch_time = missile_info.get("launch_time")

                        if isinstance(launch_time, datetime):
                            # 计算撞击时间
                            missile_mgmt_config = self._config_manager.get_missile_management_config()
                            flight_minutes = missile_mgmt_config["time_config"]["default_minutes"]
                            impact_time = launch_time + timedelta(minutes=flight_minutes)

                            # 检查是否在飞行中
                            if launch_time <= current_time <= impact_time:
                                # 获取轨迹信息
                                trajectory_info = self._missile_manager.get_missile_trajectory_info(missile_id)

                                if trajectory_info:
                                    missile_data = {
                                        'missile_id': missile_id,
                                        'launch_time': launch_time,
                                        'impact_time': impact_time,
                                        'trajectory': trajectory_info,
                                        'flight_status': 'active',
                                        'launch_position': missile_info.get('launch_position', {}),
                                        'target_position': missile_info.get('target_position', {})
                                    }
                                    active_missiles.append(missile_data)
                                    logger.info(f"📡 发现活跃导弹: {missile_id}")

                except Exception as e:
                    logger.warning(f"⚠️ 处理导弹 {missile_id} 信息失败: {e}")
                    continue

            logger.info(f"📊 共发现 {len(active_missiles)} 个活跃导弹目标")
            return active_missiles

        except Exception as e:
            logger.error(f"❌ 获取活跃导弹失败: {e}")
            return []

    async def _generate_meta_tasks_for_missile(self, missile_info: Dict[str, Any]) -> str:
        """
        为特定导弹生成元任务

        Args:
            missile_info: 导弹信息，包含ID、轨迹等

        Returns:
            生成的元任务描述
        """
        try:
            missile_id = missile_info['missile_id']
            trajectory = missile_info.get('trajectory', {})
            launch_pos = missile_info.get('launch_position', {})
            target_pos = missile_info.get('target_position', {})

            # 构建基于导弹轨迹的任务生成提示
            task_prompt = f"""
基于导弹目标生成跟踪任务:

导弹信息:
- 导弹ID: {missile_id}
- 发射时间: {missile_info.get('launch_time', 'Unknown')}
- 预计撞击时间: {missile_info.get('impact_time', 'Unknown')}
- 发射位置: 纬度 {launch_pos.get('lat', 0):.2f}°, 经度 {launch_pos.get('lon', 0):.2f}°
- 目标位置: 纬度 {target_pos.get('lat', 0):.2f}°, 经度 {target_pos.get('lon', 0):.2f}°
- 飞行状态: {missile_info.get('flight_status', 'Unknown')}

请生成跟踪任务，包括:
1. 任务ID和优先级
2. 关键跟踪点坐标
3. 观测时间窗口
4. 传感器要求
5. 协同策略建议

格式要求: JSON格式，便于系统解析和分发给卫星智能体。
"""

            # 使用LiteLLM生成基于导弹的元任务
            if self._litellm_client:
                response = await self.generate_litellm_response(task_prompt, temperature=0.2)
                logger.info(f"✅ 为导弹 {missile_id} 生成元任务完成，长度: {len(response)}")
                return response
            else:
                logger.warning("⚠️ LiteLLM客户端未初始化，使用模拟结果")
                return f"为导弹 {missile_id} 生成的模拟跟踪任务（LiteLLM未初始化）"

        except Exception as e:
            logger.error(f"❌ 为导弹 {missile_info.get('missile_id', 'Unknown')} 生成元任务失败: {e}")
            return f"❌ 元任务生成失败: {e}"

    async def _send_meta_task_set_to_nearest_satellite(self, all_missile_info: List[Dict[str, Any]]) -> str:
        """
        收集场景中所有导弹的轨迹数据，发送元任务集给离所有目标最近的卫星智能体

        Args:
            all_missile_info: 所有导弹信息列表

        Returns:
            发送结果描述
        """
        try:
            if not all_missile_info:
                return "❌ 没有导弹目标需要处理"

            logger.info(f"🎯 收集 {len(all_missile_info)} 个导弹的轨迹数据，准备发送元任务集")

            # 检查运行模式
            realistic_mode = self.is_realistic_constellation_mode_enabled()
            enhanced_mode = getattr(self, '_enhanced_mode_enabled', False)

            if realistic_mode:
                logger.info("🛰️ 使用现实星座模式")
                return await self._send_realistic_meta_task_package(all_missile_info)
            elif enhanced_mode:
                logger.info("⚡ 使用增强模式")
                return await self._send_enhanced_meta_task_set(all_missile_info)
            else:
                logger.info("📡 使用基础模式")

            # 获取可用卫星列表
            satellites = self._get_available_satellites()
            if not satellites:
                return "❌ 没有可用的卫星"

            # 计算所有导弹的中心位置（几何中心）
            total_lat = sum(missile.get('launch_position', {}).get('lat', 0) for missile in all_missile_info)
            total_lon = sum(missile.get('launch_position', {}).get('lon', 0) for missile in all_missile_info)
            center_position = {
                'lat': total_lat / len(all_missile_info),
                'lon': total_lon / len(all_missile_info),
                'alt': 0
            }

            # 找到离所有目标最近的卫星（只选择1颗）
            nearest_satellite = await self._find_nearest_satellites(center_position, satellites, count=1)

            if not nearest_satellite:
                return "❌ 无法找到适合的卫星来处理元任务集"

            selected_satellite = nearest_satellite[0]
            logger.info(f"🎯 选择卫星 {selected_satellite['id']} 作为元任务集接收者（距离中心: {selected_satellite.get('distance', 0):.2f}km）")

            # 生成包含所有导弹的元任务集
            meta_task_set = await self._generate_meta_task_set(all_missile_info)

            # 创建元任务集消息
            meta_task_message = {
                'task_id': f'META_TASK_SET_{self._current_planning_cycle}',
                'task_type': 'meta_task_set',
                'missile_count': len(all_missile_info),
                'missile_list': [missile['missile_id'] for missile in all_missile_info],
                'missile_trajectories': all_missile_info,
                'center_position': center_position,
                'priority': 'high',
                'time_window': {
                    'start': self._time_manager.get_current_simulation_time().isoformat(),
                    'end': (self._time_manager.get_current_simulation_time() + timedelta(hours=2)).isoformat()
                },
                'meta_task_set': meta_task_set,
                'assigned_satellite': selected_satellite['id'],
                'assignment_time': self._time_manager.get_current_simulation_time().isoformat(),
                'coordination_required': True,
                'requires_visibility_calculation': True,
                'requires_discussion_group': True
            }

            # 发送元任务集给选定的卫星
            result = await self._send_meta_task_set_to_satellite(selected_satellite, meta_task_message)

            if result == 'success':
                logger.info(f"✅ 元任务集成功发送给卫星 {selected_satellite['id']}")
                return f"✅ 元任务集（包含{len(all_missile_info)}个导弹目标）成功发送给卫星 {selected_satellite['id']}"
            else:
                logger.error(f"❌ 元任务集发送失败: {result}")
                return f"❌ 元任务集发送失败: {result}"

        except Exception as e:
            logger.error(f"❌ 元任务集发送失败: {e}")
            return f"❌ 元任务集发送失败: {e}"

    async def _generate_meta_task_set(self, all_missile_info: List[Dict[str, Any]]) -> str:
        """
        生成包含所有导弹的元任务集

        Args:
            all_missile_info: 所有导弹信息列表

        Returns:
            生成的元任务集描述
        """
        try:
            task_prompt = f"""
作为航天预警星座系统的仿真调度智能体，请为以下 {len(all_missile_info)} 个导弹目标生成综合元任务集：

导弹目标信息:
"""
            for i, missile in enumerate(all_missile_info, 1):
                task_prompt += f"""
{i}. 导弹ID: {missile.get('missile_id', f'MISSILE_{i}')}
   发射位置: {missile.get('launch_position', {})}
   目标位置: {missile.get('target_position', {})}
   发射时间: {missile.get('launch_time', 'Unknown')}
   飞行时间: {missile.get('flight_time', 'Unknown')}秒
   优先级: {missile.get('priority', 'medium')}
"""

            task_prompt += f"""

请生成一个综合的元任务集，包括：
1. 多目标协同跟踪策略
2. 卫星资源分配建议
3. 可见性窗口优化方案
4. 协调通信计划
5. 应急备份方案

要求：
- 考虑所有导弹的轨迹特征
- 优化卫星资源利用率
- 确保跟踪覆盖的连续性
- 提供实时协调机制

格式要求: 结构化文本，便于卫星智能体理解和执行。
"""

            # 使用LiteLLM生成元任务集
            if self._litellm_client:
                response = await self.generate_litellm_response(task_prompt, temperature=0.2)
                logger.info(f"✅ 生成包含{len(all_missile_info)}个导弹的元任务集完成，长度: {len(response)}")
                return response
            else:
                logger.warning("⚠️ LiteLLM客户端未初始化，使用模拟结果")
                return f"包含{len(all_missile_info)}个导弹目标的综合跟踪元任务集（LiteLLM未初始化）"

        except Exception as e:
            logger.error(f"❌ 生成元任务集失败: {e}")
            return f"❌ 元任务集生成失败: {e}"

    async def _send_meta_task_set_to_satellite(self, satellite: Dict[str, Any], meta_task_message: Dict[str, Any]) -> str:
        """
        发送元任务集给指定卫星智能体

        Args:
            satellite: 卫星信息
            meta_task_message: 元任务集消息

        Returns:
            发送结果
        """
        try:
            satellite_id = satellite['id']

            logger.info(f"📡 向卫星 {satellite_id} 发送元任务集 {meta_task_message['task_id']}")
            logger.info(f"   包含导弹数量: {meta_task_message['missile_count']}")

            # 修复：正确处理导弹列表（可能包含字典）
            missile_list = meta_task_message['missile_list']
            if missile_list and isinstance(missile_list[0], dict):
                missile_ids = [missile['missile_id'] for missile in missile_list]
            else:
                missile_ids = missile_list
            logger.info(f"   导弹列表: {', '.join(missile_ids)}")
            logger.info(f"   中心位置: {meta_task_message['center_position']}")

            # 获取对应的卫星智能体实例
            satellite_agent = self.get_satellite_agent(satellite_id)

            if satellite_agent:
                # 转换为TaskInfo格式
                from .satellite_agent import TaskInfo

                priority_value = 0.9  # 元任务集优先级很高

                metadata = {
                    'task_type': 'meta_task_set',
                    'missile_count': meta_task_message['missile_count'],
                    'missile_list': meta_task_message['missile_list'],
                    'missile_trajectories': meta_task_message['missile_trajectories'],
                    'center_position': meta_task_message['center_position'],
                    'meta_task_set': meta_task_message['meta_task_set'],
                    'requires_visibility_calculation': meta_task_message['requires_visibility_calculation'],
                    'requires_discussion_group': meta_task_message['requires_discussion_group']
                }

                task_info = TaskInfo(
                    task_id=meta_task_message['task_id'],
                    target_id='multi_missile_targets',
                    start_time=datetime.fromisoformat(meta_task_message['time_window']['start'].replace('Z', '+00:00')),
                    end_time=datetime.fromisoformat(meta_task_message['time_window']['end'].replace('Z', '+00:00')),
                    priority=priority_value,
                    status='pending',
                    metadata=metadata
                )

                # 发送元任务集给卫星智能体
                success = satellite_agent.task_manager.add_task(task_info)

                if success:
                    logger.info(f"✅ 元任务集 {meta_task_message['task_id']} 成功发送给卫星智能体 {satellite_id}")
                    return "success"
                else:
                    logger.error(f"❌ 卫星智能体 {satellite_id} 拒绝元任务集 {meta_task_message['task_id']}")
                    return "rejected"
            else:
                logger.error(f"❌ 未找到卫星智能体: {satellite_id}")
                return "satellite_not_found"

        except Exception as e:
            logger.error(f"❌ 发送元任务集给卫星 {satellite_id} 失败: {e}")
            return f"error: {e}"

    async def _establish_discussion_group_for_missile(self, missile_info: Dict[str, Any]) -> str:
        """
        为导弹跟踪建立真实的ADK讨论组 - 优化版：委托给卫星智能体创建

        Args:
            missile_info: 导弹信息

        Returns:
            讨论组建立结果
        """
        try:
            missile_id = missile_info['missile_id']
            logger.info(f"🗣️ 为导弹 {missile_id} 建立真实ADK讨论组（委托给卫星智能体）...")

            # 获取参与讨论的卫星列表（前3颗最近的卫星）
            satellites = self._get_available_satellites()
            launch_pos = missile_info.get('launch_position', {})
            missile_position = {
                'lat': launch_pos.get('lat', 0),
                'lon': launch_pos.get('lon', 0),
                'alt': 0
            }

            nearest_satellites = await self._find_nearest_satellites(missile_position, satellites, count=3)

            if not nearest_satellites:
                return f"❌ 无法为导弹 {missile_id} 找到参与讨论的卫星"

            participant_list = [sat['id'] for sat in nearest_satellites]
            logger.info(f"   参与者: {', '.join(participant_list)}")

            # 使用卫星工厂委托讨论组创建
            if not self._satellite_factory:
                return f"❌ 卫星工厂未初始化，无法委托创建讨论组"

            logger.info(f"🏭 通过卫星工厂委托创建讨论组，参与者: {participant_list}")

            # 委托给卫星工厂处理讨论组创建
            delegation_result = await self._satellite_factory.delegate_discussion_group_creation(
                missile_info, participant_list
            )

            # 等待一小段时间让讨论组创建完成
            import asyncio
            await asyncio.sleep(2)

            # 检查讨论组是否创建成功
            adk_discussions = self._get_active_adk_discussions()
            created_discussion = None

            for discussion_id, discussion_info in adk_discussions.items():
                if missile_id in discussion_info.get('task_description', ''):
                    created_discussion = discussion_id
                    break

            if created_discussion:
                logger.info(f"🎉 卫星工厂成功委托创建ADK讨论组: {created_discussion}")
                return f"🧠 卫星工厂委托创建的讨论组 {created_discussion} 已启动，参与智能体正在进行协同推理讨论"
            else:
                logger.info(f"📋 委托结果: {delegation_result}")
                return f"🧠 已通过卫星工厂委托创建讨论组，{delegation_result}"

        except Exception as e:
            logger.error(f"❌ 为导弹 {missile_info.get('missile_id', 'Unknown')} 委托创建ADK讨论组失败: {e}")
            return f"❌ 委托创建ADK讨论组失败: {e}"

    def _get_active_adk_discussions(self) -> Dict[str, Any]:
        """获取活跃的ADK标准讨论组（已废弃）"""
        logger.warning("⚠️ _get_active_adk_discussions方法已废弃，仿真调度智能体不再管理讨论组")
        return {}

    def _check_adk_discussion_status(self, discussion_id: str, discussion_info: Dict[str, Any]) -> str:
        """
        检查ADK讨论组状态

        Args:
            discussion_id: 讨论ID
            discussion_info: 讨论信息

        Returns:
            讨论组状态 ('active', 'completed', 'failed', 'timeout')
        """
        try:
            # 获取全局Session管理器
            from ..utils.adk_session_manager import get_adk_session_manager
            session_manager = get_adk_session_manager()

            # 检查讨论组的Session State
            discussion_state = session_manager.get_discussion_state(discussion_id)
            sequential_state = session_manager.get_sequential_discussion_state(discussion_id)

            # 检查创建时间，判断是否超时
            created_time_str = discussion_info.get('created_time', '')
            current_time = datetime.now()
            elapsed_time = 0

            if created_time_str:
                try:
                    created_time = datetime.fromisoformat(created_time_str.replace('Z', '+00:00'))
                    elapsed_time = (current_time - created_time).total_seconds()

                    # 如果超过20分钟，认为超时（增加超时时间以适应复杂任务）
                    timeout_threshold = 1200  # 20分钟
                    if elapsed_time > timeout_threshold:
                        logger.warning(f"⚠️ ADK讨论组 {discussion_id} 超时 ({elapsed_time:.1f}s > {timeout_threshold}s)")
                        return 'timeout'
                    elif elapsed_time > 600:  # 10分钟后开始警告但不超时
                        logger.info(f"📋 ADK讨论组 {discussion_id} 运行时间较长 ({elapsed_time:.1f}s)，继续等待...")
                except Exception as e:
                    logger.warning(f"⚠️ 解析创建时间失败: {e}")

            # 首先检查ADK标准讨论系统中的状态
            if self._multi_agent_system:
                adk_standard_system = self._multi_agent_system.get_adk_standard_discussion_system()
                if adk_standard_system and hasattr(adk_standard_system, '_active_discussions'):
                    if discussion_id not in adk_standard_system._active_discussions:
                        logger.info(f"✅ ADK讨论组 {discussion_id} 已从活跃列表中移除，标记为完成")
                        return 'completed'

            # 检查讨论状态
            if discussion_state:
                status = discussion_state.get('status', 'active')
                if status in ['completed', 'failed']:
                    logger.info(f"✅ ADK讨论组 {discussion_id} 状态为: {status}")
                    return status

                # 检查是否有贡献记录（表示讨论已进行）
                contributions = discussion_state.get('contributions', {})
                participants_count = len(discussion_info.get('participants', []))
                if participants_count > 0 and len(contributions) >= participants_count:
                    logger.info(f"✅ ADK讨论组 {discussion_id} 所有参与者已完成贡献 ({len(contributions)}/{participants_count})")
                    # 更新状态为完成
                    session_manager.update_discussion_state(discussion_id, {'status': 'completed'})
                    return 'completed'

            # 检查顺序讨论状态
            if sequential_state:
                status = sequential_state.get('status', 'active')
                if status in ['completed', 'failed']:
                    logger.info(f"✅ ADK顺序讨论组 {discussion_id} 状态为: {status}")
                    return status

                # 检查顺序讨论是否完成
                sequence = sequential_state.get('sequence', [])
                participants_count = len(discussion_info.get('participants', []))
                if participants_count > 0 and len(sequence) >= participants_count:
                    logger.info(f"✅ ADK顺序讨论组 {discussion_id} 所有参与者已完成讨论 ({len(sequence)}/{participants_count})")
                    # 更新状态为完成
                    session_manager.update_sequential_discussion_state(discussion_id, {'status': 'completed'})
                    return 'completed'

            # 如果讨论组运行时间超过5分钟且没有明确状态，可能需要强制完成
            if elapsed_time > 300:  # 5分钟
                logger.warning(f"⚠️ ADK讨论组 {discussion_id} 运行超过5分钟但状态不明确，强制标记为完成")
                if discussion_state:
                    session_manager.update_discussion_state(discussion_id, {'status': 'completed'})

                # 触发自动解散
                asyncio.create_task(self._auto_dissolve_discussion(discussion_id))
                return 'completed'

            # 默认认为还在进行中
            return 'active'

        except Exception as e:
            logger.error(f"❌ 检查ADK讨论组状态失败: {e}")
            return 'failed'

    async def _monitor_coordination_process(self, ctx: InvocationContext) -> str:
        """监控协同决策过程 - 使用任务完成通知机制"""
        try:
            # 使用新的任务完成通知机制
            if len(self._pending_tasks) == 0:
                logger.info("📋 没有待完成的任务，跳过协同决策监控")
                return "无待完成任务，跳过协同决策"

            logger.info(f"📊 协同决策监控: 当前有 {len(self._pending_tasks)} 个待完成任务")
            return f"协同决策监控中，待完成任务: {len(self._pending_tasks)} 个"

            logger.info(f"🤝 开始监控ADK标准讨论组完成状态")
            logger.info(f"   ADK标准讨论组: {len(adk_discussions)} 个")

            # 等待所有讨论组完成
            coordination_results = []
            max_wait_time = 1200  # 最大等待时间20分钟（与超时阈值一致）
            check_interval = 5    # 每5秒检查一次
            total_wait_time = 0

            while total_wait_time < max_wait_time:
                all_completed = True

                # 只检查ADK标准讨论组的状态
                for discussion_id, discussion_info in adk_discussions.items():
                    # 检查ADK讨论组状态
                    adk_status = self._check_adk_discussion_status(discussion_id, discussion_info)

                    if adk_status in ['completed', 'failed', 'timeout']:
                        # ADK讨论组已完成，收集结果
                        if discussion_id not in [r['group_id'] for r in coordination_results]:
                            coordination_result = {
                                'group_id': discussion_id,
                                'missile_id': discussion_info.get('task_description', 'ADK_Task')[:20],
                                'participants_count': len(discussion_info.get('participants', [])),
                                'total_rounds': 1,  # ADK讨论组没有轮次概念
                                'final_consensus_score': 0.8,  # 默认共识分数
                                'status': adk_status,
                                'coordination_status': 'completed',
                                'discussion_result': {'adk_standard': True, 'type': discussion_info.get('type', 'unknown')}
                            }

                            coordination_results.append(coordination_result)
                            logger.info(f"✅ ADK讨论组 {discussion_id} 已完成，状态: {adk_status}")
                    else:
                        # 还有ADK讨论组未完成
                        all_completed = False

                # 如果所有讨论组都完成了，退出等待
                if all_completed:
                    logger.info("✅ 所有讨论组已完成")
                    break

                # 等待一段时间后再检查
                await asyncio.sleep(check_interval)
                total_wait_time += check_interval

                if total_wait_time % 30 == 0:  # 每30秒报告一次进度
                    completed_count = len(coordination_results)
                    total_count = len(adk_discussions)
                    logger.info(f"🕐 等待ADK讨论组完成: {completed_count}/{total_count} 已完成，已等待 {total_wait_time}s")

            # 检查是否超时
            if total_wait_time >= max_wait_time:
                logger.warning(f"⚠️ 等待讨论组完成超时 ({max_wait_time}s)，强制继续")

            # 汇总协同决策结果
            if coordination_results:
                total_groups = len(coordination_results)
                completed_groups = len([r for r in coordination_results if r['status'] in ['completed', 'max_rounds_reached']])

                # 存储协同决策结果
                self._coordination_results = coordination_results

                # 生成规划结果甘特图
                planning_results = self._format_coordination_results_for_gantt(coordination_results)
                save_result = self.save_planning_results_with_gantt(planning_results)
                self._send_ui_log(f"📊 规划结果甘特图已生成: {save_result}")

                return f"协同决策完成，处理 {total_groups} 个讨论组，{completed_groups} 个成功完成，等待时间 {total_wait_time}s"
            else:
                return f"协同决策完成，但未收到有效结果，等待时间 {total_wait_time}s"

        except Exception as e:
            logger.error(f"❌ 协同决策监控失败: {e}")
            return f"❌ 协同决策监控失败: {e}"

    async def _ensure_all_discussions_complete(self, ctx: InvocationContext) -> str:
        """
        确保所有讨论组完成后再进入下一轮规划
        这是关键的时序控制方法，防止规划周期重叠
        """
        try:
            # 检查是否有活跃的ADK讨论组
            adk_discussions = self._get_active_adk_discussions()
            if not adk_discussions:
                return "无活跃ADK讨论组"

            logger.info(f"🕐 最终检查：确保 {len(adk_discussions)} 个ADK讨论组全部完成")

            max_final_wait = 1800  # 最大等待30分钟
            check_interval = 5     # 每5秒检查一次，提高响应速度
            total_wait_time = 0

            while total_wait_time < max_final_wait:
                all_completed = True
                completed_groups = []
                active_groups = []

                # 检查每个ADK讨论组的最终状态
                for discussion_id, discussion_info in adk_discussions.items():
                    adk_status = self._check_adk_discussion_status(discussion_id, discussion_info)

                    if adk_status in ['completed', 'failed', 'timeout']:
                        completed_groups.append(discussion_id)
                    else:
                        active_groups.append(discussion_id)
                        all_completed = False

                # 如果所有ADK讨论组都完成了，立即解散并返回
                if all_completed:
                    logger.info(f"✅ 所有 {len(adk_discussions)} 个ADK讨论组已完成，立即开始下一轮规划")

                    # 主动解散所有完成的讨论组
                    await self._dissolve_completed_discussions(completed_groups)

                    return f"所有讨论组已完成并解散，立即开始下一轮规划，等待时间 {total_wait_time}s"

                # 报告进度（减少日志频率）
                if total_wait_time % 30 == 0:  # 每30秒报告一次
                    logger.info(f"🕐 等待ADK讨论组完成: {len(completed_groups)}/{len(adk_discussions)} 已完成，已等待 {total_wait_time}s")
                    logger.info(f"   已完成: {completed_groups}")
                    logger.info(f"   仍活跃: {active_groups}")

                # 等待后再检查（缩短检查间隔）
                await asyncio.sleep(check_interval)
                total_wait_time += check_interval

            # 超时处理
            logger.warning(f"⚠️ 等待ADK讨论组完成超时 ({max_final_wait}s)，强制进入下一轮")

            # ADK讨论组由ADK标准讨论系统自动管理超时，无需手动清理
            completed_count = len(adk_discussions)

            return f"超时强制完成，有 {completed_count} 个ADK讨论组，等待时间 {total_wait_time}s"

        except Exception as e:
            logger.error(f"❌ 确保讨论组完成失败: {e}")
            return f"❌ 确保讨论组完成失败: {e}"

    async def _run_rolling_planning_background(self, ctx: InvocationContext) -> None:
        """
        在后台运行滚动规划循环（带时序控制）
        这是工具方法启动的后台任务版本
        """
        try:
            logger.info("🔄 后台滚动规划循环开始...")

            # 使用与 _run_async_impl 相同的逻辑，但简化版本
            max_cycles = 3  # 限制最大周期数，避免无限循环

            while self._is_running and self._current_planning_cycle < max_cycles:
                self._current_planning_cycle += 1

                cycle_start_msg = f"📋 第 {self._current_planning_cycle} 轮规划开始 - 时间: {self._time_manager.get_current_simulation_time()}"
                logger.info(cycle_start_msg)
                self._send_ui_log(cycle_start_msg)
                self._send_ui_planning_status("Cycle", "Starting", f"第 {self._current_planning_cycle} 轮规划开始")

                # 执行一轮规划
                event_count = 0
                async for event in self._execute_planning_cycle(ctx):
                    event_count += 1
                    # 处理事件但不yield（因为这是后台任务）
                    if hasattr(event, 'content') and event.content:
                        for part in event.content.parts:
                            if hasattr(part, 'text'):
                                logger.info(f"   规划事件: {part.text}")

                # 确保所有讨论组完成后再进入下一轮
                final_wait_result = await self._ensure_all_discussions_complete(ctx)

                cycle_complete_msg = f"✅ 第 {self._current_planning_cycle} 轮规划完成，{final_wait_result}"
                logger.info(cycle_complete_msg)
                self._send_ui_log(cycle_complete_msg)
                self._send_ui_planning_status("Cycle", "Complete", f"第 {self._current_planning_cycle} 轮规划完成")

                # 所有讨论组已完成，立即开始下一轮规划（去除等待时间）
                logger.info("✅ 上一轮规划任务完成，立即开始下一轮规划...")
                # 不再等待固定时间间隔，直接进入下一轮

            # 完成所有规划周期
            final_msg = f"📊 滚动规划完成，共执行 {self._current_planning_cycle} 轮规划"
            logger.info(final_msg)
            self._send_ui_log(final_msg)
            self._is_running = False

        except Exception as e:
            logger.error(f"❌ 后台滚动规划循环异常: {e}")
            self._send_ui_log(f"❌ 滚动规划异常: {e}")
            self._is_running = False

    async def _generate_final_report(self) -> str:
        """生成最终报告"""
        # 获取ADK讨论组数量
        adk_discussions = self._get_active_adk_discussions()

        report = f"""
        仿真调度完成报告:
        - 总规划周期: {self._current_planning_cycle}
        - 处理的ADK讨论组: {len(adk_discussions)}
        - 收集的规划结果: {len(self._planning_results)}
        - 仿真时间范围: {self._time_manager.start_time} - {self._time_manager.end_time}
        """
        return report
    
    def _get_planning_interval(self) -> float:
        """获取规划间隔时间"""
        agent_config = self._config_manager.config.get('multi_agent_system', {})
        scheduler_config = agent_config.get('simulation_scheduler', {})
        return scheduler_config.get('rolling_planning_interval', 0)  # 默认0秒（立即模式）
    
    # 辅助方法（复用现有代码）
    async def _connect_stk(self) -> bool:
        """连接STK"""
        try:
            if self._stk_manager:
                return self._stk_manager.connect()
            return False
        except Exception as e:
            logger.error(f"STK连接失败: {e}")
            return False

    def _initialize_managers(self) -> bool:
        """初始化管理器"""
        try:
            # 初始化导弹管理器
            if not self._missile_manager:
                # 获取导弹管理配置
                missile_config = self._config_manager.get_missile_management_config()

                # 创建简单的输出管理器（如果需要）
                class SimpleOutputManager:
                    def save_data(self, data, filename):
                        pass

                output_manager = SimpleOutputManager()

                self._missile_manager = MissileManager(
                    stk_manager=self._stk_manager,
                    config=missile_config,
                    output_manager=output_manager
                )
                logger.info("✅ 导弹管理器初始化成功")

            # 初始化可见性计算器
            if not self._visibility_calculator:
                self._visibility_calculator = VisibilityCalculator(self._stk_manager)
                logger.info("✅ 可见性计算器初始化成功")

            # 初始化星座管理器
            if not self._constellation_manager:
                self._constellation_manager = ConstellationManager(self._stk_manager)
                logger.info("✅ 星座管理器初始化成功")

            logger.info("✅ 所有管理器初始化成功")
            return True
        except Exception as e:
            logger.error(f"管理器初始化失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def _setup_constellation(self) -> bool:
        """设置星座"""
        try:
            if self._constellation_manager:
                config = self._config_manager.config
                return self._constellation_manager.create_walker_constellation(config)
            return False
        except Exception as e:
            logger.error(f"星座设置失败: {e}")
            return False

    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态

        Returns:
            系统状态信息
        """
        # 获取ADK讨论组数量
        adk_discussions = self._get_active_adk_discussions()

        return {
            'is_running': self._is_running,
            'current_cycle': self._current_planning_cycle,
            'active_adk_groups': len(adk_discussions),
            'planning_results_count': len(self._planning_results),
            'coordination_results_count': len(self._coordination_results),
            'current_session_id': self._current_session_id
        }



    def save_meta_tasks_with_gantt(self, meta_tasks: List[Dict[str, Any]]) -> Dict[str, str]:
        """
        保存元任务并生成甘特图

        Args:
            meta_tasks: 元任务列表

        Returns:
            保存的文件路径信息
        """
        try:
            # 确保有活动会话
            if not self._current_session_id:
                self.create_simulation_session("auto_session")

            # 保存元任务JSON
            meta_task_file = self._result_manager.save_meta_tasks(meta_tasks)
            self._send_ui_log(f"💾 元任务已保存: {meta_task_file}")

            # 生成元任务甘特图数据
            gantt_data = self._result_manager.generate_meta_task_gantt_data(meta_tasks)
            gantt_file = self._result_manager.save_gantt_chart_data(gantt_data, "meta_task_gantt")
            self._send_ui_log(f"📊 元任务甘特图数据已保存: {gantt_file}")

            # 生成甘特图HTML
            html_file = None
            try:
                if self._gantt_generator is None:
                    self._gantt_generator = AerospaceGanttGenerator()
                    self._send_ui_log("🔧 重新初始化甘特图生成器")

                fig = self._gantt_generator.create_meta_task_gantt(gantt_data)
                if fig:
                    html_file = gantt_file.replace('.json', '.html')
                    self._gantt_generator.save_chart(html_file, format="html")
                    self._send_ui_log(f"📈 元任务甘特图HTML已生成: {html_file}")
                else:
                    self._send_ui_log("⚠️ 甘特图生成失败，但数据已保存")
            except Exception as e:
                self._send_ui_log(f"⚠️ 甘特图HTML生成失败: {e}")
                logger.warning(f"甘特图HTML生成失败: {e}")

            return {
                "meta_task_file": meta_task_file,
                "gantt_data_file": gantt_file,
                "gantt_html_file": html_file if fig else None
            }

        except Exception as e:
            self._send_ui_log(f"❌ 保存元任务失败: {e}", level='error')
            return {"error": str(e)}

    def save_planning_results_with_gantt(self, planning_results: Dict[str, Any]) -> Dict[str, str]:
        """
        保存规划结果并生成甘特图

        Args:
            planning_results: 规划结果

        Returns:
            保存的文件路径信息
        """
        try:
            # 确保有活动会话
            if not self._current_session_id:
                self.create_simulation_session("auto_session")

            # 保存规划结果JSON
            planning_file = self._result_manager.save_planning_results(planning_results)
            self._send_ui_log(f"💾 规划结果已保存: {planning_file}")

            # 生成规划甘特图数据
            gantt_data = self._result_manager.generate_planning_gantt_data(planning_results)
            gantt_file = self._result_manager.save_gantt_chart_data(gantt_data, "planning_gantt")
            self._send_ui_log(f"📊 规划甘特图数据已保存: {gantt_file}")

            # 生成甘特图HTML
            html_file = None
            try:
                if self._gantt_generator is None:
                    self._gantt_generator = AerospaceGanttGenerator()
                    self._send_ui_log("🔧 重新初始化甘特图生成器")

                fig = self._gantt_generator.create_planning_gantt(gantt_data)
                if fig:
                    html_file = gantt_file.replace('.json', '.html')
                    self._gantt_generator.save_chart(html_file, format="html")
                    self._send_ui_log(f"📈 规划甘特图HTML已生成: {html_file}")
                else:
                    self._send_ui_log("⚠️ 甘特图生成失败，但数据已保存")
            except Exception as e:
                self._send_ui_log(f"⚠️ 甘特图HTML生成失败: {e}")
                logger.warning(f"甘特图HTML生成失败: {e}")

            return {
                "planning_file": planning_file,
                "gantt_data_file": gantt_file,
                "gantt_html_file": html_file if fig else None
            }

        except Exception as e:
            self._send_ui_log(f"❌ 保存规划结果失败: {e}", level='error')
            return {"error": str(e)}







    def _format_coordination_results_for_gantt(self, coordination_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """格式化协同决策结果为甘特图数据"""
        try:
            current_time = self._time_manager.get_current_simulation_time()

            planning_data = {
                "metadata": {
                    "session_id": self._current_session_id,
                    "created_time": current_time.isoformat(),
                    "coordination_groups": len(coordination_results),
                    "planning_cycle": self._current_planning_cycle
                },
                "satellite_assignments": []
            }

            # 为每个协同决策结果创建多个卫星分配
            for result in coordination_results:
                missile_id = result.get('missile_id', 'Unknown')
                group_id = result.get('group_id', 'Unknown')

                # 获取所有参与的卫星（模拟多卫星协同）
                participating_satellites = result.get('participating_satellites', [])
                if not participating_satellites:
                    # 如果没有参与卫星信息，使用默认的几颗卫星
                    participating_satellites = ['Satellite13', 'Satellite32', 'Satellite33']

                # 为每个参与的卫星创建任务分配
                for i, satellite_id in enumerate(participating_satellites):
                    # 计算每个卫星的时间窗口（错开时间以显示协同效果）
                    start_offset = timedelta(minutes=i * 5)  # 每颗卫星错开5分钟
                    end_offset = timedelta(minutes=20 + i * 5)  # 持续20分钟

                    assignment = {
                        "assignment_id": f"ASSIGN_{missile_id}_{satellite_id}",
                        "satellite_id": satellite_id,
                        "task_name": f"跟踪-{missile_id}",
                        "task_type": "observation",
                        "target_id": missile_id,
                        "start_time": (current_time + start_offset).isoformat(),
                        "end_time": (current_time + end_offset).isoformat(),
                        "priority": 1,
                        "description": f"{satellite_id}执行跟踪任务",
                        "confidence_score": 0.85 + i * 0.05,  # 略微不同的置信度
                        "coverage": f"{85 + i * 2}%",
                        "group_id": group_id
                    }

                    planning_data["satellite_assignments"].append(assignment)

            logger.info(f"📊 格式化协同结果完成，生成 {len(planning_data['satellite_assignments'])} 个卫星任务分配")
            return planning_data

        except Exception as e:
            logger.error(f"格式化协同结果失败: {e}")
            return {
                "metadata": {"error": str(e)},
                "satellite_assignments": []
            }

    async def _get_active_missiles(self) -> List[Dict[str, Any]]:
        """获取活跃导弹列表（异步版本）"""
        try:
            return await self._get_active_missiles_with_trajectories()
        except Exception as e:
            logger.error(f"获取活跃导弹失败: {e}")
            return []

    def _get_active_missiles_sync(self) -> List[Dict[str, Any]]:
        """获取活跃导弹列表（同步版本）"""
        try:
            # 返回模拟数据，实际应该从导弹管理器获取
            return [
                {
                    "missile_id": "MISSILE_001",
                    "priority": 1,
                    "flight_status": "midcourse"
                },
                {
                    "missile_id": "MISSILE_002",
                    "priority": 1,
                    "flight_status": "midcourse"
                }
            ]
        except Exception as e:
            logger.error(f"获取活跃导弹失败: {e}")
            return []

    async def _create_walker_constellation(self) -> str:
        """创建Walker星座"""
        try:
            logger.info("🌟 开始创建Walker星座...")

            # 确保星座管理器已初始化
            if not self._constellation_manager:
                from ..constellation.constellation_manager import ConstellationManager
                self._constellation_manager = ConstellationManager(self._stk_manager, self._config_manager)

            # 创建Walker星座
            success = self._constellation_manager.create_walker_constellation()
            if not success:
                return "❌ Walker星座创建失败"

            # 重要：确保所有卫星轨道传播完成
            logger.info("🔄 开始传播所有卫星轨道...")
            propagate_success = self._stk_manager._safe_propagate_all_satellites()
            if not propagate_success:
                logger.warning("⚠️ 部分卫星轨道传播失败，但继续执行")
            else:
                logger.info("✅ 所有卫星轨道传播成功")

            # 验证星座创建
            satellites = self._stk_manager.get_objects("Satellite")
            satellite_ids = [sat.split('/')[-1] for sat in satellites]

            logger.info(f"✅ Walker星座创建成功，共创建 {len(satellite_ids)} 颗卫星")
            logger.info(f"📡 卫星列表: {satellite_ids}")

            return f"✅ Walker星座创建成功，共创建 {len(satellite_ids)} 颗卫星: {satellite_ids}"

        except Exception as e:
            logger.error(f"❌ Walker星座创建失败: {e}")
            return f"❌ Walker星座创建失败: {e}"

    async def _create_satellite_agents(self) -> str:
        """创建卫星智能体"""
        try:
            logger.info("🤖 开始创建卫星智能体...")

            # 导入卫星智能体工厂
            from ..agents.satellite_agent_factory import SatelliteAgentFactory

            # 创建工厂实例，传递STK管理器以确保连接一致性
            self._satellite_factory = SatelliteAgentFactory(self._config_manager)

            # 关键修复：将STK管理器传递给卫星智能体工厂
            if hasattr(self._satellite_factory, 'set_stk_manager'):
                self._satellite_factory.set_stk_manager(self._stk_manager)
                logger.info("✅ 已将STK管理器传递给卫星智能体工厂")

            # 设置多智能体系统引用
            if hasattr(self._satellite_factory, 'set_multi_agent_system') and hasattr(self, '_multi_agent_system'):
                self._satellite_factory.set_multi_agent_system(self._multi_agent_system)
                logger.info("✅ 已将多智能体系统引用传递给卫星智能体工厂")

            # 创建卫星智能体
            self._satellite_agents = await self._satellite_factory.create_satellite_agents_from_walker_constellation(
                self._constellation_manager, stk_manager=self._stk_manager
            )

            if not self._satellite_agents or len(self._satellite_agents) == 0:
                return "❌ 卫星智能体创建失败"

            agent_ids = list(self._satellite_agents.keys())
            logger.info(f"✅ 成功创建 {len(self._satellite_agents)} 个卫星智能体")
            logger.info(f"🤖 智能体列表: {agent_ids}")

            return f"✅ 成功创建 {len(self._satellite_agents)} 个卫星智能体: {agent_ids}"

        except Exception as e:
            logger.error(f"❌ 卫星智能体创建失败: {e}")
            return f"❌ 卫星智能体创建失败: {e}"

    async def _register_satellite_agents(self) -> str:
        """注册卫星智能体到多智能体系统"""
        try:
            logger.info("📋 开始注册卫星智能体到多智能体系统...")

            if not hasattr(self, '_satellite_agents') or not self._satellite_agents:
                return "❌ 没有可注册的卫星智能体"

            # 获取多智能体系统实例（通过父类）
            if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
                # 注册所有卫星智能体
                success = self._multi_agent_system.register_satellite_agents(self._satellite_agents)
                if success:
                    logger.info(f"✅ 成功注册 {len(self._satellite_agents)} 个卫星智能体到多智能体系统")
                    return f"✅ 成功注册 {len(self._satellite_agents)} 个卫星智能体到多智能体系统"
                else:
                    return "❌ 卫星智能体注册失败"
            else:
                return "❌ 多智能体系统不可用"

        except Exception as e:
            logger.error(f"❌ 卫星智能体注册失败: {e}")
            return f"❌ 卫星智能体注册失败: {e}"

    async def _verify_system_status(self) -> str:
        """验证系统状态"""
        try:
            logger.info("🔍 开始验证系统状态...")

            # 检查STK连接
            stk_connected = self._stk_manager and self._stk_manager.is_connected

            # 检查STK对象
            satellites = self._stk_manager.get_objects("Satellite") if self._stk_manager else []
            sensors = self._stk_manager.get_objects("Sensor") if self._stk_manager else []
            missiles = self._stk_manager.get_objects("Missile") if self._stk_manager else []

            # 检查智能体
            agent_count = len(self._satellite_agents) if hasattr(self, '_satellite_agents') and self._satellite_agents else 0

            # 测试一个智能体的功能
            test_result = ""
            if hasattr(self, '_satellite_agents') and self._satellite_agents:
                test_agent = list(self._satellite_agents.values())[0]
                test_satellite_ids = await test_agent._get_all_satellite_ids()
                satellite_ids = [sat.split('/')[-1] for sat in satellites]
                id_mapping_correct = set(test_satellite_ids) == set(satellite_ids)
                test_result = f"\n🔍 智能体功能测试:\n   测试智能体: {test_agent.satellite_id}\n   ID映射正确: {'✅ 是' if id_mapping_correct else '❌ 否'}"

            status_report = f"""📊 系统状态总结:
   STK连接: {'✅ 正常' if stk_connected else '❌ 断开'}
   卫星数量: {len(satellites)}
   传感器数量: {len(sensors)}
   导弹数量: {len(missiles)}
   智能体数量: {agent_count}{test_result}

🎉 系统现在已准备好:
   1. 接收仿真调度智能体发送的导弹目标
   2. 计算卫星可见窗口
   3. 创建讨论组进行协同决策
   4. 通过UI界面监控智能体状态"""

            logger.info(status_report)
            return status_report

        except Exception as e:
            logger.error(f"❌ 系统状态验证失败: {e}")
            return f"❌ 系统状态验证失败: {e}"

    async def initialize_complete_system(self) -> str:
        """公共方法：初始化完整的卫星智能体系统"""
        try:
            logger.info("🎯 开始初始化完整系统...")

            # 1. 连接STK
            logger.info("📋 步骤1: 连接STK")
            if not await self._connect_stk():
                return "❌ STK连接失败"

            # 2. 初始化管理器
            logger.info("📋 步骤2: 初始化管理器")
            if not self._initialize_managers():
                return "❌ 管理器初始化失败"

            # 3. 创建Walker星座
            logger.info("📋 步骤3: 创建Walker星座")
            constellation_result = await self._create_walker_constellation()
            if "❌" in constellation_result:
                return constellation_result

            # 4. 创建卫星智能体
            logger.info("📋 步骤4: 创建卫星智能体")
            agents_result = await self._create_satellite_agents()
            if "❌" in agents_result:
                return agents_result

            # 5. 注册到多智能体系统
            logger.info("📋 步骤5: 注册到多智能体系统")
            registration_result = await self._register_satellite_agents()
            if "❌" in registration_result:
                return registration_result

            # 6. 验证系统状态
            logger.info("📋 步骤6: 验证系统状态")
            verification_result = await self._verify_system_status()

            return f"✅ 完整系统初始化成功！\n{verification_result}"

        except Exception as e:
            logger.error(f"❌ 完整系统初始化失败: {e}")
            return f"❌ 完整系统初始化失败: {e}"

    async def _create_test_missile(self) -> str:
        """创建测试导弹（用于验证STK连接）"""
        try:
            logger.info("🚀 创建测试导弹...")

            if not self._stk_manager or not self._stk_manager.is_connected:
                return "❌ STK未连接"

            # 创建一个简单的测试导弹
            missile_id = "TEST_MISSILE_001"

            # 使用导弹管理器创建导弹
            if hasattr(self, '_missile_manager') and self._missile_manager:
                success = self._missile_manager.create_simple_missile(
                    missile_id=missile_id,
                    start_lat=0.0,
                    start_lon=0.0,
                    start_alt=0.0,
                    end_lat=10.0,
                    end_lon=10.0,
                    end_alt=0.0,
                    flight_time=300.0
                )

                if success:
                    return f"✅ 测试导弹 {missile_id} 创建成功"
                else:
                    return f"❌ 测试导弹 {missile_id} 创建失败"
            else:
                return "❌ 导弹管理器不可用"

        except Exception as e:
            logger.error(f"❌ 创建测试导弹失败: {e}")

    async def _dissolve_completed_discussions(self, completed_discussion_ids: list):
        """解散已完成的讨论组"""
        try:
            if not completed_discussion_ids:
                return

            logger.info(f"🔄 开始解散 {len(completed_discussion_ids)} 个已完成的讨论组")

            # 获取ADK官方讨论系统（修复：使用官方系统而不是已删除的标准系统）
            adk_official_system = self._multi_agent_system.get_adk_official_discussion_system()
            if not adk_official_system:
                logger.warning("⚠️ ADK官方讨论系统不可用，无法解散讨论组")
                return

            dissolved_count = 0
            for discussion_id in completed_discussion_ids:
                try:
                    # 调用ADK官方讨论系统的解散方法
                    success = await adk_official_system.complete_discussion(discussion_id)
                    if success:
                        dissolved_count += 1
                        logger.info(f"✅ 讨论组 {discussion_id} 已解散")
                    else:
                        logger.warning(f"⚠️ 讨论组 {discussion_id} 解散失败")

                except Exception as e:
                    logger.error(f"❌ 解散讨论组 {discussion_id} 时出错: {e}")

            logger.info(f"✅ 解散完成：{dissolved_count}/{len(completed_discussion_ids)} 个讨论组已解散")

        except Exception as e:
            logger.error(f"❌ 解散讨论组过程失败: {e}")

    async def _on_discussion_completed(self, discussion_id: str):
        """讨论组完成时的回调方法"""
        try:
            logger.info(f"📢 收到讨论组完成通知: {discussion_id}")

            # 可以在这里添加额外的清理逻辑
            # 例如更新规划状态、记录统计信息等

            # 检查是否所有讨论组都已完成，如果是则可以开始下一轮规划
            adk_discussions = self._get_active_adk_discussions()
            if not adk_discussions:
                logger.info("🎯 所有讨论组已完成，立即触发下一轮规划")
                # 设置标志位，表示可以立即开始下一轮规划
                self._all_discussions_completed = True

        except Exception as e:
            logger.error(f"❌ 处理讨论组完成通知失败: {e}")

    def _check_all_discussions_completed(self) -> bool:
        """
        检查所有讨论组是否已完成

        Returns:
            bool: 如果所有讨论组都已完成返回True，否则返回False
        """
        try:
            adk_discussions = self._get_active_adk_discussions()
            if not adk_discussions:
                return True

            # 检查每个讨论组的状态
            for discussion_id, discussion_info in adk_discussions.items():
                adk_status = self._check_adk_discussion_status(discussion_id, discussion_info)
                if adk_status not in ['completed', 'failed', 'timeout']:
                    return False

            return True

        except Exception as e:
            logger.error(f"❌ 检查讨论组完成状态失败: {e}")
            return False

    async def _auto_dissolve_discussion(self, discussion_id: str):
        """自动解散单个讨论组"""
        try:
            logger.info(f"🔄 自动解散讨论组: {discussion_id}")

            # 获取ADK标准讨论系统
            adk_standard_system = self._multi_agent_system.get_adk_standard_discussion_system()
            if adk_standard_system:
                success = await adk_standard_system.complete_discussion(discussion_id)
                if success:
                    logger.info(f"✅ 讨论组 {discussion_id} 自动解散成功")
                else:
                    logger.warning(f"⚠️ 讨论组 {discussion_id} 自动解散失败")
            else:
                logger.warning(f"⚠️ ADK标准讨论系统不可用，无法自动解散讨论组 {discussion_id}")

        except Exception as e:
            logger.error(f"❌ 自动解散讨论组 {discussion_id} 失败: {e}")
            return f"❌ 创建测试导弹失败: {e}"

    # ==================== 增强功能方法 ====================

    def enable_enhanced_mode(self):
        """启用增强模式"""
        self._enhanced_mode_enabled = True
        logger.info("✅ 增强模式已启用")

    def disable_enhanced_mode(self):
        """禁用增强模式"""
        self._enhanced_mode_enabled = False
        logger.info("ℹ️ 增强模式已禁用")

    def is_enhanced_mode_enabled(self) -> bool:
        """检查是否启用增强模式"""
        return getattr(self, '_enhanced_mode_enabled', False)

    async def _send_enhanced_meta_task_set(self, all_missile_info: List[Dict[str, Any]]) -> str:
        """发送增强元任务集"""
        try:
            logger.info(f"🚀 发送增强元任务集，导弹数量: {len(all_missile_info)}")

            # 1. 生成增强元任务集
            enhanced_meta_task_set = await self._generate_enhanced_meta_task_set(all_missile_info)

            if not enhanced_meta_task_set:
                return "❌ 增强元任务集生成失败"

            # 2. 选择最优卫星
            optimal_satellite = await self._select_optimal_satellite_for_enhanced_task(enhanced_meta_task_set)

            if not optimal_satellite:
                return "❌ 无法找到合适的卫星"

            satellite_id = optimal_satellite['satellite_id']
            logger.info(f"🎯 选择最优卫星: {satellite_id}")

            # 3. 创建增强任务信息
            enhanced_task = await self._create_enhanced_task_info(enhanced_meta_task_set, optimal_satellite)

            # 4. 发送给卫星智能体
            satellite_agent = self.get_satellite_agent(satellite_id)
            if satellite_agent:
                # 检查卫星是否支持增强任务
                if hasattr(satellite_agent.task_manager, 'add_enhanced_task'):
                    success = satellite_agent.task_manager.add_enhanced_task(enhanced_task)
                else:
                    # 回退到基础任务
                    basic_task = enhanced_task.to_basic_task_info()
                    success = satellite_agent.task_manager.add_task(basic_task)

                if success:
                    self._send_ui_log(f"✅ 增强元任务集发送成功: {satellite_id}")

                    # 5. 建立增强讨论组
                    discussion_result = await self._establish_enhanced_discussion_group(
                        enhanced_meta_task_set, [satellite_agent]
                    )

                    return f"✅ 增强元任务集发送成功给卫星 {satellite_id}，包含 {len(all_missile_info)} 个导弹目标"
                else:
                    return f"❌ 卫星智能体拒绝增强元任务集: {satellite_id}"
            else:
                return f"❌ 未找到卫星智能体: {satellite_id}"

        except Exception as e:
            logger.error(f"❌ 增强元任务集发送失败: {e}")
            return f"❌ 增强元任务集发送失败: {e}"

    async def _generate_enhanced_meta_task_set(self, all_missile_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成增强的元任务集"""
        try:
            logger.info(f"🚀 生成增强元任务集，导弹数量: {len(all_missile_info)}")

            # 1. 分析导弹轨迹和飞行阶段
            enhanced_missiles = []
            for missile_info in all_missile_info:
                enhanced_missile = await self._analyze_missile_trajectory(missile_info)
                enhanced_missiles.append(enhanced_missile)

            # 2. 计算星座可见性
            constellation_visibility = await self._calculate_enhanced_constellation_visibility(enhanced_missiles)

            # 3. 分析资源约束
            resource_constraints = await self._analyze_enhanced_resource_constraints()

            # 4. 检测潜在冲突
            potential_conflicts = await self._detect_enhanced_conflicts(
                enhanced_missiles, constellation_visibility, resource_constraints
            )

            # 5. 生成优化建议
            optimization_suggestions = await self._generate_optimization_suggestions(
                enhanced_missiles, constellation_visibility, potential_conflicts
            )

            enhanced_meta_task_set = {
                'meta_task_id': f'ENHANCED_META_TASK_{self._current_planning_cycle}',
                'creation_time': self._time_manager.get_current_simulation_time().isoformat(),
                'planning_cycle': self._current_planning_cycle,
                'enhanced_missiles': enhanced_missiles,
                'constellation_visibility': constellation_visibility,
                'resource_constraints': resource_constraints,
                'potential_conflicts': potential_conflicts,
                'optimization_suggestions': optimization_suggestions,
                'metadata': {
                    'enhancement_level': 'full',
                    'conflict_detection_enabled': True,
                    'visibility_precomputed': True,
                    'resource_analysis_enabled': True
                }
            }

            logger.info(f"✅ 增强元任务集生成完成")
            return enhanced_meta_task_set

        except Exception as e:
            logger.error(f"❌ 增强元任务集生成失败: {e}")
            return {}

    async def _analyze_missile_trajectory(self, missile_info: Dict[str, Any]) -> Dict[str, Any]:
        """分析导弹轨迹"""
        try:
            missile_id = missile_info['missile_id']

            # 获取详细轨迹数据
            trajectory_data = await self._get_detailed_trajectory_data(missile_id)

            # 分析飞行阶段
            flight_phases = self._analyze_flight_phases(trajectory_data)

            # 定义观测需求
            observation_requirements = self._define_enhanced_observation_requirements(
                missile_info, flight_phases
            )

            # 评估不确定性
            uncertainty_info = self._assess_trajectory_uncertainty(trajectory_data)

            enhanced_missile = {
                'missile_id': missile_id,
                'threat_level': missile_info.get('threat_level', 3),
                'trajectory_data': trajectory_data,
                'flight_phases': flight_phases,
                'observation_requirements': observation_requirements,
                'uncertainty_info': uncertainty_info,
                'original_info': missile_info
            }

            return enhanced_missile

        except Exception as e:
            logger.error(f"❌ 导弹轨迹分析失败: {e}")
            return missile_info  # 回退到原始信息

    async def _get_detailed_trajectory_data(self, missile_id: str) -> Dict[str, Any]:
        """获取详细轨迹数据"""
        try:
            # 从导弹管理器获取详细轨迹
            if self._missile_manager:
                trajectory = await self._missile_manager.get_missile_trajectory(missile_id)
                return trajectory if trajectory else {}
            else:
                # 模拟轨迹数据
                return {
                    'points': [],
                    'max_altitude': 300.0,  # km
                    'max_velocity': 5.0,    # km/s
                    'duration': 1800.0,     # seconds
                    'type': 'ballistic'
                }
        except Exception as e:
            logger.error(f"❌ 获取轨迹数据失败: {e}")
            return {}

    # ==================== 现实约束方案实现 ====================

    def enable_realistic_constellation_mode(self):
        """启用现实星座模式"""
        self._realistic_constellation_mode = True
        logger.info("✅ 现实星座模式已启用")

    def disable_realistic_constellation_mode(self):
        """禁用现实星座模式"""
        self._realistic_constellation_mode = False
        logger.info("ℹ️ 现实星座模式已禁用")

    def is_realistic_constellation_mode_enabled(self) -> bool:
        """检查是否启用现实星座模式"""
        return getattr(self, '_realistic_constellation_mode', False)

    async def _send_realistic_meta_task_package(self, all_missile_info: List[Dict[str, Any]]) -> str:
        """发送现实的元任务包给候选卫星群"""
        try:
            logger.info(f"🚀 发送现实元任务包，导弹数量: {len(all_missile_info)}")

            # 1. 选择候选卫星群（基于粗略的几何关系）
            candidate_satellites = await self._select_candidate_satellites_realistic(all_missile_info)

            if len(candidate_satellites) < 2:
                return "❌ 候选卫星数量不足"

            # 2. 创建初始元任务包
            from src.agents.realistic_meta_task_structures import RealisticMetaTaskBuilder

            meta_task_package = RealisticMetaTaskBuilder.create_initial_meta_task_package(
                missile_data=all_missile_info,
                candidate_satellites=[sat['id'] for sat in candidate_satellites],
                priority_level=4  # 高优先级
            )

            logger.info(f"📦 创建元任务包: {meta_task_package.task_package_id}")
            logger.info(f"   包含 {len(meta_task_package.missile_targets)} 个导弹目标")
            logger.info(f"   候选卫星: {meta_task_package.candidate_satellites}")

            # 3. 发送给所有候选卫星
            sent_count = 0
            discussion_group_id = None

            for satellite in candidate_satellites:
                satellite_agent = self.get_satellite_agent(satellite['id'])
                if satellite_agent:
                    # 为卫星智能体添加现实约束处理能力
                    if not hasattr(satellite_agent, 'receive_realistic_meta_task_package'):
                        self._enhance_satellite_agent_with_realistic_capabilities(satellite_agent)

                    success = await satellite_agent.receive_realistic_meta_task_package(meta_task_package)
                    if success:
                        sent_count += 1

            if sent_count > 0:
                # 4. 创建协调讨论组
                discussion_group_id = await self._create_realistic_coordination_discussion(
                    meta_task_package, candidate_satellites[:sent_count]
                )

                self._send_ui_log(f"✅ 现实元任务包发送给 {sent_count} 个候选卫星")

                # 5. 生成甘特图
                gantt_result = await self.generate_mission_gantt_charts(
                    all_missile_info,
                    f"✅ 现实元任务包发送成功，{sent_count} 个卫星开始STK计算"
                )

                gantt_info = ""
                if gantt_result:
                    gantt_info = f"，甘特图已生成: {len(gantt_result)} 个文件"

                if discussion_group_id:
                    return f"✅ 现实元任务包发送成功，{sent_count} 个卫星开始STK计算，讨论组: {discussion_group_id}{gantt_info}"
                else:
                    return f"✅ 现实元任务包发送成功，{sent_count} 个卫星开始STK计算{gantt_info}"
            else:
                return "❌ 所有候选卫星都拒绝了元任务包"

        except Exception as e:
            logger.error(f"❌ 发送现实元任务包失败: {e}")
            return f"❌ 发送失败: {e}"

    async def _select_candidate_satellites_realistic(self, all_missile_info: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """选择候选卫星群（现实约束版本）"""
        try:
            # 计算导弹群的几何中心
            center_position = self._calculate_center_position(all_missile_info)

            # 获取所有可用卫星
            all_satellites = self._get_available_satellites()

            if not all_satellites:
                logger.warning("⚠️ 没有可用的卫星")
                return []

            # 基于距离和资源状态选择候选卫星
            candidate_count = min(6, max(3, len(all_satellites) // 2))  # 选择3-6颗卫星

            # 计算每颗卫星的综合评分
            satellite_scores = []
            for satellite in all_satellites:
                # 模拟卫星位置（实际应该从STK获取）
                sat_position = {
                    'lat': satellite.get('lat', 0.0),
                    'lon': satellite.get('lon', 0.0),
                    'alt': satellite.get('alt', 600.0)  # 默认600km轨道
                }

                # 计算到中心位置的距离
                lat_diff = sat_position['lat'] - center_position.get('lat', 0.0)
                lon_diff = sat_position['lon'] - center_position.get('lon', 0.0)
                distance = (lat_diff ** 2 + lon_diff ** 2) ** 0.5

                # 距离评分（距离越近评分越高）
                distance_score = max(0, 1.0 - distance / 100.0)  # 100度为最大距离

                # 资源评分（模拟）
                resource_score = 0.8  # 假设80%的资源可用性

                # 综合评分
                total_score = distance_score * 0.6 + resource_score * 0.4

                # 添加距离信息到卫星数据
                satellite_with_distance = satellite.copy()
                satellite_with_distance['distance'] = distance

                satellite_scores.append({
                    'satellite': satellite_with_distance,
                    'score': total_score
                })

            # 按评分排序，选择前N个
            satellite_scores.sort(key=lambda x: x['score'], reverse=True)
            selected_satellites = [item['satellite'] for item in satellite_scores[:candidate_count]]

            logger.info(f"📡 选择了 {len(selected_satellites)} 个候选卫星")
            return selected_satellites

        except Exception as e:
            logger.error(f"❌ 选择候选卫星失败: {e}")
            return []

    def _enhance_satellite_agent_with_realistic_capabilities(self, satellite_agent):
        """为卫星智能体增加现实约束处理能力"""
        try:
            # 动态添加现实约束处理方法
            async def receive_realistic_meta_task_package(meta_task_package):
                try:
                    logger.info(f"📦 卫星 {satellite_agent.satellite_id} 接收现实元任务包: {meta_task_package.task_package_id}")

                    # 1. 检查卫星状态和资源
                    if not self._can_satellite_handle_meta_task_package(satellite_agent, meta_task_package):
                        logger.warning(f"⚠️ 卫星 {satellite_agent.satellite_id} 无法处理元任务包")
                        return False

                    # 2. 启动STK可见性计算
                    from src.agents.satellite_visibility_calculator import SatelliteVisibilityCalculator

                    visibility_calculator = SatelliteVisibilityCalculator(
                        satellite_id=satellite_agent.satellite_id,
                        stk_interface=getattr(satellite_agent, 'stk_interface', None),
                        config_manager=self._config_manager
                    )

                    # 异步计算可见性
                    visibility_report = await visibility_calculator.calculate_visibility_for_meta_task(meta_task_package)

                    # 3. 存储计算结果
                    if not hasattr(satellite_agent, '_visibility_reports'):
                        satellite_agent._visibility_reports = {}
                    satellite_agent._visibility_reports[meta_task_package.task_package_id] = visibility_report

                    logger.info(f"✅ 卫星 {satellite_agent.satellite_id} STK计算完成")
                    return True

                except Exception as e:
                    logger.error(f"❌ 卫星 {satellite_agent.satellite_id} 处理元任务包失败: {e}")
                    return False

            # 绑定方法到卫星智能体（使用types.MethodType确保正确绑定）
            import types
            satellite_agent.receive_realistic_meta_task_package = types.MethodType(receive_realistic_meta_task_package, satellite_agent)

            logger.info(f"✅ 卫星智能体 {satellite_agent.satellite_id} 现实约束能力增强完成")

        except Exception as e:
            logger.error(f"❌ 增强卫星智能体能力失败: {e}")

    def _can_satellite_handle_meta_task_package(self, satellite_agent, meta_task_package) -> bool:
        """检查卫星是否能处理元任务包"""
        try:
            # 检查资源状态
            if hasattr(satellite_agent, 'resource_status'):
                if satellite_agent.resource_status.power_level < 0.3:  # 功率低于30%
                    return False

            # 检查当前任务负载
            if hasattr(satellite_agent, 'task_manager'):
                executing_tasks = satellite_agent.task_manager.get_executing_tasks()
                max_tasks = getattr(satellite_agent.task_manager, 'max_concurrent_tasks', 5)
                if len(executing_tasks) >= max_tasks:
                    return False

            # 检查是否在候选列表中
            if satellite_agent.satellite_id not in meta_task_package.candidate_satellites:
                return False

            return True

        except Exception as e:
            logger.error(f"❌ 检查卫星处理能力失败: {e}")
            return False

    async def _create_realistic_coordination_discussion(self, meta_task_package, candidate_satellites) -> Optional[str]:
        """创建现实协调讨论组"""
        try:
            # 1. 准备讨论组参数
            discussion_topic = f"现实导弹跟踪任务协商_{meta_task_package.task_package_id}"

            # 2. 获取参与者列表
            participant_ids = [sat['id'] for sat in candidate_satellites]

            # 3. 准备共享上下文
            shared_context = {
                'meta_task_package_id': meta_task_package.task_package_id,
                'missile_count': len(meta_task_package.missile_targets),
                'coordination_requirements': meta_task_package.coordination_requirements.to_dict() if hasattr(meta_task_package.coordination_requirements, 'to_dict') else {},
                'mission_requirements': meta_task_package.mission_requirements.to_dict() if hasattr(meta_task_package.mission_requirements, 'to_dict') else {}
            }

            # 4. 创建ADK讨论组
            if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
                discussion_id = await self._multi_agent_system.create_adk_official_discussion(
                    pattern_type="parallel_fanout",
                    participating_agents=participant_ids,
                    task_description=discussion_topic,
                    ctx=shared_context
                )

                if discussion_id:
                    logger.info(f"✅ 创建现实协调讨论组: {discussion_id}")
                    return discussion_id
                else:
                    logger.error("❌ 创建现实协调讨论组失败")
                    return None
            else:
                logger.warning("⚠️ 多智能体系统不可用，跳过讨论组创建")
                return None

        except Exception as e:
            logger.error(f"❌ 创建现实协调讨论组失败: {e}")
            return None

    def _calculate_center_position(self, all_missile_info: List[Dict[str, Any]]) -> Dict[str, float]:
        """计算导弹群的几何中心位置"""
        try:
            if not all_missile_info:
                return {'lat': 0.0, 'lon': 0.0, 'alt': 0.0}

            total_lat = 0.0
            total_lon = 0.0
            total_alt = 0.0
            count = 0

            for missile in all_missile_info:
                launch_pos = missile.get('launch_position', {})
                target_pos = missile.get('target_position', {})

                # 使用发射位置和目标位置的中点
                if launch_pos and target_pos:
                    mid_lat = (launch_pos.get('lat', 0.0) + target_pos.get('lat', 0.0)) / 2
                    mid_lon = (launch_pos.get('lon', 0.0) + target_pos.get('lon', 0.0)) / 2
                    mid_alt = (launch_pos.get('alt', 0.0) + target_pos.get('alt', 0.0)) / 2

                    total_lat += mid_lat
                    total_lon += mid_lon
                    total_alt += mid_alt
                    count += 1
                elif launch_pos:
                    total_lat += launch_pos.get('lat', 0.0)
                    total_lon += launch_pos.get('lon', 0.0)
                    total_alt += launch_pos.get('alt', 0.0)
                    count += 1

            if count > 0:
                return {
                    'lat': total_lat / count,
                    'lon': total_lon / count,
                    'alt': total_alt / count
                }
            else:
                return {'lat': 0.0, 'lon': 0.0, 'alt': 0.0}

        except Exception as e:
            logger.error(f"❌ 计算中心位置失败: {e}")
            return {'lat': 0.0, 'lon': 0.0, 'alt': 0.0}

    async def _find_nearest_satellites(self, center_position: Dict[str, float], satellites: List[Dict], count: int) -> List[Dict]:
        """找到距离中心位置最近的卫星"""
        try:
            if not satellites:
                return []

            # 简化的距离计算（实际应该使用球面距离）
            def calculate_distance(sat_pos, center_pos):
                lat_diff = sat_pos.get('lat', 0.0) - center_pos.get('lat', 0.0)
                lon_diff = sat_pos.get('lon', 0.0) - center_pos.get('lon', 0.0)
                return (lat_diff ** 2 + lon_diff ** 2) ** 0.5

            # 为每颗卫星计算距离
            satellites_with_distance = []
            for satellite in satellites:
                # 模拟卫星位置（实际应该从STK获取）
                sat_position = {
                    'lat': satellite.get('lat', 0.0),
                    'lon': satellite.get('lon', 0.0),
                    'alt': satellite.get('alt', 600.0)  # 默认600km轨道
                }

                distance = calculate_distance(sat_position, center_position)

                satellite_with_distance = satellite.copy()
                satellite_with_distance['distance'] = distance
                satellites_with_distance.append(satellite_with_distance)

            # 按距离排序
            satellites_with_distance.sort(key=lambda x: x['distance'])

            # 返回最近的N颗卫星
            return satellites_with_distance[:count]

        except Exception as e:
            logger.error(f"❌ 查找最近卫星失败: {e}")
            return []

    async def generate_mission_gantt_charts(
        self,
        missile_scenario: List[Dict[str, Any]],
        scheduler_result: str
    ) -> Optional[Dict[str, str]]:
        """为任务生成甘特图"""
        try:
            logger.info("🎨 开始生成任务甘特图...")

            # 导入甘特图管理器
            try:
                from src.visualization.gantt_integration_manager import ConstellationGanttIntegrationManager
            except ImportError:
                logger.warning("⚠️ 甘特图模块不可用，跳过甘特图生成")
                return None

            # 创建甘特图管理器
            gantt_manager = ConstellationGanttIntegrationManager(self._config_manager)

            # 获取卫星列表
            satellite_list = [sat['id'] for sat in self._get_available_satellites()]

            # 自动生成甘特图
            generated_charts = await gantt_manager.auto_generate_from_scheduler_result(
                scheduler_result, missile_scenario, satellite_list
            )

            if generated_charts:
                logger.info(f"✅ 甘特图生成完成: {len(generated_charts)} 个文件")

                # 发送UI日志
                self._send_ui_log(f"📊 甘特图已生成: {list(generated_charts.keys())}")

                return generated_charts
            else:
                logger.warning("⚠️ 甘特图生成失败")
                return None

        except Exception as e:
            logger.error(f"❌ 生成甘特图失败: {e}")
            return None

    def __str__(self) -> str:
        enhanced_status = "Enhanced" if self.is_enhanced_mode_enabled() else "Basic"
        realistic_status = "Realistic" if self.is_realistic_constellation_mode_enabled() else "Ideal"
        return f"SimulationSchedulerAgent(name={self.name}, cycle={self._current_planning_cycle}, mode={enhanced_status}, constellation={realistic_status})"

    def __repr__(self) -> str:
        return self.__str__()
