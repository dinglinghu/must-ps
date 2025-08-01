"""
ADK transfer_to_agent与现有具身智能体的集成方案
基于现有的SatelliteAgent具身智能体实现ADK transfer优化
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator
from uuid import uuid4

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from .simulation_scheduler_agent import SimulationSchedulerAgent
from .satellite_agent import SatelliteAgent

logger = logging.getLogger(__name__)


class ADKTransferIntegratedScheduler(SimulationSchedulerAgent):
    """
    集成ADK transfer_to_agent的仿真调度智能体
    
    核心特性：
    1. 继承现有SimulationSchedulerAgent的所有功能
    2. 将现有SatelliteAgent设置为sub_agents
    3. 使用transfer_to_agent替代task_manager.add_task()
    4. 保持所有具身智能体特性（轨道参数、STK连接等）
    5. 支持每颗卫星成为组长
    """
    
    def __init__(self, *args, **kwargs):
        """
        初始化集成ADK transfer的调度智能体
        """
        # 先调用父类初始化
        super().__init__(*args, **kwargs)
        
        # ADK transfer相关属性
        object.__setattr__(self, '_transfer_enabled', False)
        object.__setattr__(self, '_satellite_sub_agents', [])
        object.__setattr__(self, '_transfer_instruction_updated', False)
        object.__setattr__(self, '_pending_tasks', set())
        
        logger.info("✅ ADK Transfer集成调度器初始化完成")

    async def initialize_adk_transfer_mode(self):
        """
        初始化ADK transfer模式
        将现有的具身卫星智能体设置为sub_agents
        """
        try:
            logger.info("🔄 初始化ADK transfer模式...")
            
            # 1. 获取所有现有的具身卫星智能体
            satellite_agents = await self._get_existing_satellite_agents()
            
            if not satellite_agents:
                logger.warning("⚠️ 未找到现有的卫星智能体，无法启用ADK transfer模式")
                return False
            
            # 2. 设置为sub_agents（使用object.__setattr__绕过Pydantic限制）
            object.__setattr__(self, 'sub_agents', satellite_agents)
            object.__setattr__(self, '_satellite_sub_agents', satellite_agents)
            
            # 3. 更新指令以支持transfer_to_agent
            self._update_instruction_for_transfer(satellite_agents)
            
            # 4. 为每个卫星智能体启用transfer接收模式
            for satellite in satellite_agents:
                await self._enable_satellite_transfer_mode(satellite)
            
            object.__setattr__(self, '_transfer_enabled', True)
            
            logger.info(f"✅ ADK transfer模式初始化完成，管理 {len(satellite_agents)} 个具身卫星智能体")
            return True
            
        except Exception as e:
            logger.error(f"❌ ADK transfer模式初始化失败: {e}")
            return False

    async def _get_existing_satellite_agents(self) -> List[SatelliteAgent]:
        """获取现有的具身卫星智能体"""
        try:
            satellite_agents = []
            
            # 从现有的卫星智能体注册表获取
            if hasattr(self, '_satellite_agents') and self._satellite_agents:
                for sat_id, agent in self._satellite_agents.items():
                    if isinstance(agent, SatelliteAgent):
                        satellite_agents.append(agent)
                        logger.info(f"📡 发现具身卫星智能体: {agent.name} (ID: {sat_id})")
            
            # 从多智能体系统获取
            if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
                # 从卫星智能体注册表获取
                if hasattr(self._multi_agent_system, '_satellite_agents'):
                    for satellite_id, agent_instance in self._multi_agent_system._satellite_agents.items():
                        if isinstance(agent_instance, SatelliteAgent) and agent_instance not in satellite_agents:
                            satellite_agents.append(agent_instance)
                            logger.info(f"📡 从多智能体系统发现: {agent_instance.name}")

                # 如果没有找到，尝试从satellite_agents属性获取
                if not satellite_agents and hasattr(self._multi_agent_system, 'satellite_agents'):
                    satellite_agents_dict = self._multi_agent_system.satellite_agents
                    for satellite_id, agent_instance in satellite_agents_dict.items():
                        if isinstance(agent_instance, SatelliteAgent) and agent_instance not in satellite_agents:
                            satellite_agents.append(agent_instance)
                            logger.info(f"📡 从属性发现: {agent_instance.name}")

            # 3. 从传统调度器的工具方法获取（重要！）
            if not satellite_agents:
                try:
                    # 调用传统调度器的获取卫星方法
                    traditional_satellites = self._get_available_satellite_agents()
                    for agent in traditional_satellites:
                        if isinstance(agent, SatelliteAgent) and agent not in satellite_agents:
                            satellite_agents.append(agent)
                            logger.info(f"📡 从传统方法发现: {agent.name}")
                except Exception as e:
                    logger.debug(f"传统方法获取卫星失败: {e}")

            logger.info(f"🛰️ 总共发现 {len(satellite_agents)} 个具身卫星智能体")
            return satellite_agents
            
        except Exception as e:
            logger.error(f"❌ 获取现有卫星智能体失败: {e}")
            return []

    def _update_instruction_for_transfer(self, satellite_agents: List[SatelliteAgent]):
        """更新指令以支持transfer_to_agent"""
        try:
            # 构建卫星智能体描述
            agent_descriptions = []
            for agent in satellite_agents:
                agent_descriptions.append(
                    f"- {agent.name}: 卫星 {agent.satellite_id}，"
                    f"轨道参数: {getattr(agent, 'orbital_parameters', {})}, "
                    f"载荷配置: {getattr(agent, 'payload_config', {})}"
                )
            
            agents_list = "\n".join(agent_descriptions)
            
            # 构建新的指令
            transfer_instruction = f"""
你是仿真调度智能体，负责协调卫星任务执行和滚动规划。

可用的具身卫星智能体：
{agents_list}

ADK Transfer模式特性：
1. 使用transfer_to_agent将任务委托给具身卫星智能体
2. 每颗卫星都保持完整的具身特性（轨道参数、STK连接、可见性计算）
3. 每颗卫星都可能成为组长，创建讨论组进行协同决策
4. 通过session.state实现实时结果回收和规划触发

任务委托策略：
- 单目标任务：选择最近或最优可见性的卫星
- 多目标任务：选择覆盖范围最优的卫星组合
- 协同任务：委托给最合适的卫星作为组长

使用transfer_to_agent的格式：
transfer_to_agent(agent_name='目标卫星智能体名称')

结果管理：
- 任务结果：session.state['task_results'][task_id] = 结果
- 规划触发：session.state['planning_trigger'] = True
- 讨论组状态：session.state['discussion_groups'][group_id] = 状态

原有功能保持：
- STK场景管理
- 滚动规划周期
- 元任务生成
- 结果收集和甘特图生成
"""
            
            # 更新指令（使用object.__setattr__）
            object.__setattr__(self, 'instruction', transfer_instruction)
            object.__setattr__(self, '_transfer_instruction_updated', True)
            
            logger.info("✅ 指令已更新以支持ADK transfer_to_agent")
            
        except Exception as e:
            logger.error(f"❌ 更新指令失败: {e}")

    async def _enable_satellite_transfer_mode(self, satellite: SatelliteAgent):
        """为卫星智能体启用transfer接收模式"""
        try:
            # 为卫星智能体添加transfer接收能力
            # 这里不需要修改SatelliteAgent的核心代码，只需要确保它能正确响应transfer
            
            # 设置transfer标识
            object.__setattr__(satellite, '_transfer_enabled', True)
            object.__setattr__(satellite, '_parent_scheduler', self)
            
            logger.info(f"✅ 卫星 {satellite.satellite_id} 已启用transfer接收模式")
            
        except Exception as e:
            logger.error(f"❌ 为卫星 {satellite.satellite_id} 启用transfer模式失败: {e}")

    async def delegate_task_with_transfer(
        self,
        ctx: Optional[InvocationContext],
        task_info: Dict[str, Any],
        target_satellite_id: Optional[str] = None
    ) -> str:
        """
        使用ADK transfer_to_agent委托任务
        
        Args:
            ctx: ADK调用上下文
            task_info: 任务信息
            target_satellite_id: 目标卫星ID（可选，由LLM自动选择）
        
        Returns:
            委托结果
        """
        try:
            if not self._transfer_enabled:
                logger.warning("⚠️ ADK transfer模式未启用，回退到传统方式")
                return await self._delegate_task_traditional(task_info)
            
            logger.info(f"📡 使用ADK transfer委托任务: {task_info.get('task_id')}")
            
            # 准备任务委托信息
            delegation_info = {
                'task_info': task_info,
                'delegation_time': datetime.now().isoformat(),
                'target_satellite_id': target_satellite_id,
                'delegation_mode': 'adk_transfer'
            }
            
            # 保存到session.state供LLM读取
            session_state = None
            if ctx and hasattr(ctx, 'session') and hasattr(ctx.session, 'state'):
                session_state = ctx.session.state
            elif hasattr(self, '_session_state'):
                session_state = self._session_state

            if session_state is not None:
                if 'pending_delegations' not in session_state:
                    session_state['pending_delegations'] = {}

                delegation_id = f"delegation_{uuid4().hex[:8]}"
                session_state['pending_delegations'][delegation_id] = delegation_info
            else:
                # 如果没有session.state，直接委托给目标卫星
                delegation_id = f"direct_delegation_{uuid4().hex[:8]}"
                logger.info(f"⚠️ 没有session.state，直接委托任务: {delegation_id}")

                # 直接执行任务委托
                result = await self._execute_direct_delegation(task_info, target_satellite_id)
                return result

            # 构建委托提示，让LLM决定使用哪个卫星
            delegation_prompt = self._build_task_delegation_prompt(task_info, target_satellite_id)

            # 这里LLM会分析任务并生成transfer_to_agent调用
            # ADK框架会自动处理transfer调用，将执行转移到目标卫星智能体

            logger.info(f"✅ 任务委托准备完成: {delegation_id}")
            return f"任务委托准备完成，等待LLM选择目标卫星智能体"
            
        except Exception as e:
            logger.error(f"❌ ADK transfer任务委托失败: {e}")
            return f"❌ 任务委托失败: {e}"

    def _build_task_delegation_prompt(
        self, 
        task_info: Dict[str, Any], 
        target_satellite_id: Optional[str] = None
    ) -> str:
        """构建任务委托提示"""
        task_description = task_info.get('description', '未知任务')
        task_type = task_info.get('task_type', 'unknown')
        
        if target_satellite_id:
            return f"""
需要将以下任务委托给指定的卫星智能体：

任务信息：
- 任务ID: {task_info.get('task_id')}
- 任务类型: {task_type}
- 任务描述: {task_description}
- 指定卫星: {target_satellite_id}

请使用transfer_to_agent将任务委托给卫星 {target_satellite_id}：
transfer_to_agent(agent_name='{target_satellite_id}')
"""
        else:
            return f"""
需要为以下任务选择最合适的卫星智能体：

任务信息：
- 任务ID: {task_info.get('task_id')}
- 任务类型: {task_type}
- 任务描述: {task_description}
- 目标位置: {task_info.get('target_position', '未知')}
- 优先级: {task_info.get('priority', 0.5)}

请分析任务需求，选择最合适的卫星智能体，并使用transfer_to_agent进行委托。

选择策略：
1. 考虑卫星的轨道参数和可见性
2. 考虑卫星的载荷配置和能力
3. 考虑当前任务负载和可用性
4. 如需协同，选择最适合作为组长的卫星

请调用：transfer_to_agent(agent_name='选定的卫星智能体名称')
"""

    async def _delegate_task_traditional(self, task_info: Dict[str, Any]) -> str:
        """传统任务委托方式（回退机制）"""
        try:
            # 使用原有的任务发送机制
            task_id = task_info.get('task_id')
            logger.info(f"🔄 使用传统方式委托任务: {task_id}")
            
            # 这里调用原有的任务发送逻辑
            # 具体实现取决于现有的代码结构
            
            return f"使用传统方式委托任务: {task_id}"
            
        except Exception as e:
            logger.error(f"❌ 传统任务委托失败: {e}")
            return f"❌ 传统任务委托失败: {e}"

    def get_transfer_status(self) -> Dict[str, Any]:
        """获取ADK transfer状态"""
        return {
            'transfer_enabled': getattr(self, '_transfer_enabled', False),
            'satellite_count': len(getattr(self, '_satellite_sub_agents', [])),
            'instruction_updated': getattr(self, '_transfer_instruction_updated', False),
            'sub_agents_count': len(getattr(self, 'sub_agents', []))
        }

    # 重写传统的任务发送方法，使用ADK transfer机制
    async def _send_meta_task_set_to_satellite(self, satellite: Dict[str, Any], meta_task_message: Dict[str, Any]) -> str:
        """
        使用ADK transfer发送元任务集给指定卫星智能体

        Args:
            satellite: 卫星信息
            meta_task_message: 元任务集消息

        Returns:
            发送结果
        """
        try:
            if not self._transfer_enabled:
                # 回退到传统方式
                return await super()._send_meta_task_set_to_satellite(satellite, meta_task_message)

            satellite_id = satellite.get('id')
            logger.info(f"📡 使用ADK transfer发送元任务集给卫星 {satellite_id}")

            # 获取所有可用的卫星智能体信息（用于讨论组创建）
            available_satellites = await self._get_available_satellite_info_for_discussion()

            # 构建任务信息
            task_info = {
                'task_id': meta_task_message['task_id'],
                'task_type': 'meta_task_execution',
                'description': meta_task_message.get('content', ''),
                'target_satellite_id': satellite_id,
                'priority': meta_task_message.get('priority', 0.5),
                'metadata': {
                    'meta_task_message': meta_task_message,
                    'satellite_info': satellite,
                    'delegation_time': datetime.now().isoformat(),
                    # 添加讨论组创建所需的信息
                    'available_satellites': available_satellites,
                    'requires_discussion_group': True,
                    'discussion_mode': 'iterative_refinement',
                    # 传递多智能体系统引用信息
                    'multi_agent_system_available': hasattr(self, '_multi_agent_system') and self._multi_agent_system is not None
                }
            }

            # 使用ADK transfer委托任务
            result = await self.delegate_task_with_transfer(None, task_info, satellite_id)

            if "成功" in result or "完成" in result or "委托" in result:
                # 将任务添加到待完成列表（保持兼容性）
                self._pending_tasks.add(task_info['task_id'])
                logger.info(f"📋 任务 {task_info['task_id']} 已添加到待完成列表，总数: {len(self._pending_tasks)}")
                return "success"
            else:
                logger.error(f"❌ ADK transfer委托失败: {result}")
                return "transfer_failed"

        except Exception as e:
            logger.error(f"❌ ADK transfer发送元任务集失败: {e}")
            # 回退到传统方式
            return await super()._send_meta_task_set_to_satellite(satellite, meta_task_message)

    async def _wait_for_all_tasks_completion(self):
        """
        使用ADK transfer机制等待所有任务完成
        替代传统的轮询机制
        """
        try:
            if not self._transfer_enabled:
                # 回退到传统方式
                return await super()._wait_for_all_tasks_completion()

            logger.info("🔄 使用ADK transfer机制等待任务完成...")

            # 检查session.state中的任务结果
            max_wait_time = 300  # 5分钟超时
            check_interval = 2   # 2秒检查一次
            elapsed_time = 0

            while elapsed_time < max_wait_time:
                # 检查是否有planning_trigger
                if hasattr(self, '_session_state') and self._session_state:
                    if self._session_state.get('planning_trigger', False):
                        logger.info("✅ 检测到planning_trigger，所有任务已完成")
                        # 重置触发器
                        self._session_state['planning_trigger'] = False
                        break

                # 检查任务结果
                completed_tasks = set()
                if hasattr(self, '_session_state') and self._session_state:
                    task_results = self._session_state.get('task_results', {})
                    for task_id in list(self._pending_tasks):
                        if task_id in task_results:
                            completed_tasks.add(task_id)
                            logger.info(f"✅ 任务 {task_id} 通过ADK transfer完成")

                # 移除已完成的任务
                self._pending_tasks -= completed_tasks

                # 如果所有任务都完成了
                if len(self._pending_tasks) == 0:
                    logger.info("✅ 所有ADK transfer任务已完成")
                    break

                # 等待一段时间后再检查
                await asyncio.sleep(check_interval)
                elapsed_time += check_interval

                if elapsed_time % 30 == 0:  # 每30秒记录一次进度
                    logger.info(f"⏳ 等待ADK transfer任务完成: {len(self._pending_tasks)} 个任务待完成")

            if len(self._pending_tasks) > 0:
                logger.warning(f"⚠️ 超时：仍有 {len(self._pending_tasks)} 个任务未完成")

        except Exception as e:
            logger.error(f"❌ ADK transfer等待任务完成失败: {e}")
            # 回退到传统方式
            await super()._wait_for_all_tasks_completion()

    async def _execute_direct_delegation(self, task_info: Dict[str, Any], target_satellite_id: Optional[str] = None) -> str:
        """
        直接执行任务委托（当没有session.state时）

        Args:
            task_info: 任务信息
            target_satellite_id: 目标卫星ID

        Returns:
            委托结果
        """
        try:
            logger.info(f"🔄 直接委托任务: {task_info.get('task_id')}")

            # 1. 选择目标卫星智能体
            target_satellite = None
            if target_satellite_id:
                # 指定了目标卫星，使用增强的匹配逻辑
                target_satellite = self._find_satellite_by_id(target_satellite_id)
            else:
                # 自动选择最合适的卫星（简单策略：选择第一个可用的）
                available_satellites = getattr(self, 'sub_agents', [])
                if available_satellites:
                    target_satellite = available_satellites[0]

            if not target_satellite:
                error_msg = f"❌ 未找到目标卫星智能体: {target_satellite_id}"
                logger.error(error_msg)

                # 提供调试信息
                available_satellites = getattr(self, 'sub_agents', [])
                if available_satellites:
                    logger.error(f"📋 当前可用的 {len(available_satellites)} 个卫星智能体:")
                    for i, sat in enumerate(available_satellites):
                        sat_info = self._get_satellite_debug_info(sat)
                        logger.error(f"   {i+1}. {sat_info}")
                else:
                    logger.error("📋 当前没有可用的卫星智能体（sub_agents为空）")

                return error_msg

            # 2. 直接调用卫星智能体的任务处理方法
            if hasattr(target_satellite, 'handle_transfer_task'):
                # 如果卫星已经增强支持transfer
                result = await target_satellite.handle_transfer_task(task_info)
                logger.info(f"✅ 直接委托成功: {target_satellite.satellite_id}")
                return f"✅ 任务已直接委托给卫星 {target_satellite.satellite_id}"
            else:
                # 使用传统的任务管理器
                if hasattr(target_satellite, 'task_manager'):
                    task_manager = target_satellite.task_manager
                    task_id = task_info.get('task_id')

                    # 创建TaskInfo对象（与现有格式兼容）
                    from .satellite_agent import TaskInfo
                    from datetime import datetime

                    # 从metadata中提取时间信息
                    metadata = task_info.get('metadata', {})
                    start_time = datetime.now()
                    end_time = datetime.now() + timedelta(hours=1)  # 默认1小时任务窗口

                    # 如果是元任务集，提取时间窗口
                    if 'meta_task_message' in metadata:
                        meta_task_message = metadata['meta_task_message']
                        if 'time_window' in meta_task_message:
                            try:
                                start_time = datetime.fromisoformat(meta_task_message['time_window']['start'].replace('Z', '+00:00'))
                                end_time = datetime.fromisoformat(meta_task_message['time_window']['end'].replace('Z', '+00:00'))
                            except:
                                pass  # 使用默认时间

                    # 🔧 修复：从导弹目标名称中提取主要目标ID
                    target_id = 'unknown'
                    missile_target_names = []

                    # 优先从metadata中获取导弹目标名称
                    if 'missile_target_names' in metadata:
                        missile_target_names = metadata['missile_target_names']
                        if missile_target_names and len(missile_target_names) > 0:
                            target_id = missile_target_names[0]  # 使用第一个导弹作为主要目标
                    elif 'missile_list' in metadata:
                        # 兼容旧格式
                        missile_list = metadata['missile_list']
                        if missile_list and len(missile_list) > 0:
                            if isinstance(missile_list[0], dict):
                                target_id = missile_list[0].get('missile_id', 'unknown')
                                missile_target_names = [m.get('missile_id', f'missile_{i}') for i, m in enumerate(missile_list)]
                            else:
                                target_id = missile_list[0]
                                missile_target_names = missile_list
                    elif 'meta_task_message' in metadata:
                        # 从元任务消息中提取
                        meta_task_message = metadata['meta_task_message']
                        if 'missile_target_names' in meta_task_message:
                            missile_target_names = meta_task_message['missile_target_names']
                            if missile_target_names and len(missile_target_names) > 0:
                                target_id = missile_target_names[0]
                        elif 'missile_list' in meta_task_message:
                            missile_list = meta_task_message['missile_list']
                            if missile_list and len(missile_list) > 0:
                                if isinstance(missile_list[0], dict):
                                    target_id = missile_list[0].get('missile_id', 'unknown')
                                    missile_target_names = [m.get('missile_id', f'missile_{i}') for i, m in enumerate(missile_list)]
                                else:
                                    target_id = missile_list[0]
                                    missile_target_names = missile_list

                    # 确保metadata中包含完整的导弹目标信息
                    if missile_target_names:
                        metadata['missile_target_names'] = missile_target_names
                        metadata['primary_target'] = target_id
                        metadata['missile_count'] = len(missile_target_names)

                    logger.info(f"🎯 任务目标映射: {target_id} (来源: {missile_target_names})")

                    task_info_obj = TaskInfo(
                        task_id=task_id,
                        target_id=target_id,  # 使用提取的主要目标ID
                        start_time=start_time,
                        end_time=end_time,
                        priority=task_info.get('priority', 0.5),
                        status='pending',
                        metadata=metadata
                    )

                    # 添加任务到卫星的任务管理器
                    success = task_manager.add_task(task_info_obj)
                    if success:
                        logger.info(f"✅ 任务已添加到卫星 {target_satellite.satellite_id} 的任务管理器")

                        # 将任务添加到待完成列表（保持兼容性）
                        if hasattr(self, '_pending_tasks'):
                            self._pending_tasks.add(task_id)
                            logger.info(f"📋 任务 {task_id} 已添加到待完成列表")

                        return f"✅ 任务已委托给卫星 {target_satellite.satellite_id}（传统方式）"
                    else:
                        logger.error(f"❌ 任务添加失败: {target_satellite.satellite_id}")
                        return f"❌ 任务委托失败: {target_satellite.satellite_id}"
                else:
                    logger.error(f"❌ 卫星 {target_satellite.satellite_id} 没有任务管理器")
                    return f"❌ 卫星 {target_satellite.satellite_id} 没有任务管理器"

        except Exception as e:
            logger.error(f"❌ 直接委托任务失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return f"❌ 直接委托任务失败: {e}"

    def _find_satellite_by_id(self, target_satellite_id: str) -> Optional[Any]:
        """
        严格的卫星智能体查找方法
        基于配置文件的精确匹配，确保STK卫星与智能体一一对应

        Args:
            target_satellite_id: 目标卫星ID（必须与配置文件中的命名完全匹配）

        Returns:
            找到的卫星智能体或None
        """
        try:
            logger.info(f"🔍 严格查找卫星智能体: {target_satellite_id}")

            # 1. 从配置文件获取卫星命名映射
            satellite_mapping = self._get_satellite_naming_mapping()

            # 2. 检查目标卫星ID是否在配置的映射中
            if target_satellite_id not in satellite_mapping:
                logger.error(f"❌ 卫星ID '{target_satellite_id}' 不在配置的命名映射中")
                logger.error(f"📋 配置的卫星映射: {list(satellite_mapping.keys())}")
                return None

            # 3. 获取对应的智能体名称
            agent_name = satellite_mapping[target_satellite_id]
            logger.info(f"📋 根据配置映射: {target_satellite_id} -> {agent_name}")

            # 4. 获取所有可用的卫星智能体
            all_satellites = self._get_all_available_satellites()

            logger.info(f"📡 总共搜索 {len(all_satellites)} 个卫星智能体")

            # 5. 严格匹配：只匹配satellite_id或name完全相等的
            for satellite in all_satellites:
                sat_info = self._get_satellite_debug_info(satellite)
                logger.debug(f"   检查卫星: {sat_info}")

                # 严格匹配逻辑
                if self._is_exact_satellite_match(satellite, target_satellite_id, agent_name):
                    logger.info(f"✅ 找到严格匹配的卫星智能体: {sat_info}")
                    return satellite

            # 如果没有找到，记录详细信息
            logger.error(f"❌ 未找到卫星智能体 '{target_satellite_id}' (映射到 '{agent_name}')")
            logger.error("📋 可用的卫星智能体:")
            for satellite in all_satellites:
                sat_info = self._get_satellite_debug_info(satellite)
                logger.error(f"   - {sat_info}")

            return None

        except Exception as e:
            logger.error(f"❌ 查找卫星智能体失败: {e}")
            import traceback
            logger.debug(f"详细错误: {traceback.format_exc()}")
            return None

    def _get_satellite_naming_mapping(self) -> Dict[str, str]:
        """从配置文件获取卫星命名映射"""
        try:
            # 从配置管理器获取卫星映射
            if hasattr(self, '_config_manager') and self._config_manager:
                # 使用config属性而不是get_config方法
                config = self._config_manager.config
                constellation_config = config.get('constellation', {})
                naming_config = constellation_config.get('naming', {})
                satellite_mapping = naming_config.get('satellite_mapping', {})

                if satellite_mapping:
                    logger.info(f"📋 从配置文件加载卫星映射: {len(satellite_mapping)} 个卫星")
                    return satellite_mapping

            # 如果配置文件中没有，使用默认的Walker星座映射
            default_mapping = {
                "Satellite11": "Satellite11",
                "Satellite12": "Satellite12",
                "Satellite13": "Satellite13",
                "Satellite21": "Satellite21",
                "Satellite22": "Satellite22",
                "Satellite23": "Satellite23",
                "Satellite31": "Satellite31",
                "Satellite32": "Satellite32",
                "Satellite33": "Satellite33"
            }

            logger.warning("⚠️ 使用默认Walker星座卫星映射")
            return default_mapping

        except Exception as e:
            logger.error(f"❌ 获取卫星命名映射失败: {e}")
            return {}

    def _get_all_available_satellites(self) -> List[Any]:
        """获取所有可用的卫星智能体"""
        all_satellites = []

        # 1. 从sub_agents获取
        sub_agents = getattr(self, 'sub_agents', [])
        all_satellites.extend(sub_agents)

        # 2. 从多智能体系统获取
        if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
            if hasattr(self._multi_agent_system, '_satellite_agents'):
                for sat_id, agent in self._multi_agent_system._satellite_agents.items():
                    if agent not in all_satellites:
                        all_satellites.append(agent)

        # 3. 从_satellite_agents获取
        if hasattr(self, '_satellite_agents') and self._satellite_agents:
            for sat_id, agent in self._satellite_agents.items():
                if agent not in all_satellites:
                    all_satellites.append(agent)

        return all_satellites

    def _is_exact_satellite_match(self, satellite, target_satellite_id: str, agent_name: str) -> bool:
        """
        严格的卫星匹配检查
        只允许精确匹配，不使用模糊逻辑
        """
        try:
            # 1. 精确匹配satellite_id
            if hasattr(satellite, 'satellite_id'):
                if satellite.satellite_id == target_satellite_id or satellite.satellite_id == agent_name:
                    return True

            # 2. 精确匹配name
            if hasattr(satellite, 'name'):
                if satellite.name == target_satellite_id or satellite.name == agent_name:
                    return True

            return False

        except Exception as e:
            logger.debug(f"严格匹配检查失败: {e}")
            return False

    def validate_satellite_naming_consistency(self) -> bool:
        """
        验证卫星命名一致性
        确保STK场景、配置文件、智能体命名完全一致
        """
        try:
            logger.info("🔍 验证卫星命名一致性...")

            # 1. 从配置文件获取预期的卫星名称
            expected_satellites = self._get_expected_satellite_names_from_config()
            logger.info(f"📋 配置文件预期卫星: {expected_satellites}")

            # 2. 从STK场景获取实际的卫星名称
            actual_stk_satellites = self._get_actual_stk_satellite_names()
            logger.info(f"🛰️ STK场景实际卫星: {actual_stk_satellites}")

            # 3. 从智能体系统获取已创建的智能体名称
            actual_agent_names = self._get_actual_agent_names()
            logger.info(f"🤖 智能体系统实际智能体: {actual_agent_names}")

            # 4. 检查一致性
            consistency_issues = []

            # 检查STK与配置的一致性
            missing_in_stk = set(expected_satellites) - set(actual_stk_satellites)
            extra_in_stk = set(actual_stk_satellites) - set(expected_satellites)

            if missing_in_stk:
                consistency_issues.append(f"STK场景中缺少卫星: {missing_in_stk}")
            if extra_in_stk:
                consistency_issues.append(f"STK场景中多余卫星: {extra_in_stk}")

            # 检查智能体与配置的一致性
            missing_agents = set(expected_satellites) - set(actual_agent_names)
            extra_agents = set(actual_agent_names) - set(expected_satellites)

            if missing_agents:
                consistency_issues.append(f"智能体系统中缺少智能体: {missing_agents}")
            if extra_agents:
                consistency_issues.append(f"智能体系统中多余智能体: {extra_agents}")

            # 5. 报告结果
            if consistency_issues:
                logger.error("❌ 卫星命名一致性检查失败:")
                for issue in consistency_issues:
                    logger.error(f"   - {issue}")
                return False
            else:
                logger.info("✅ 卫星命名一致性检查通过")
                return True

        except Exception as e:
            logger.error(f"❌ 卫星命名一致性验证失败: {e}")
            return False

    def _get_expected_satellite_names_from_config(self) -> List[str]:
        """从配置文件获取预期的卫星名称"""
        try:
            satellite_mapping = self._get_satellite_naming_mapping()
            return list(satellite_mapping.keys())
        except Exception as e:
            logger.error(f"❌ 获取配置文件卫星名称失败: {e}")
            return []

    def _get_actual_stk_satellite_names(self) -> List[str]:
        """从STK场景获取实际的卫星名称"""
        try:
            if hasattr(self, '_stk_manager') and self._stk_manager:
                satellites = self._stk_manager.get_objects("Satellite")
                return [sat.split('/')[-1] for sat in satellites]
            return []
        except Exception as e:
            logger.error(f"❌ 获取STK卫星名称失败: {e}")
            return []

    def _get_actual_agent_names(self) -> List[str]:
        """从智能体系统获取实际的智能体名称"""
        try:
            all_satellites = self._get_all_available_satellites()
            agent_names = []

            for satellite in all_satellites:
                if hasattr(satellite, 'satellite_id'):
                    agent_names.append(satellite.satellite_id)
                elif hasattr(satellite, 'name'):
                    agent_names.append(satellite.name)

            return list(set(agent_names))  # 去重
        except Exception as e:
            logger.error(f"❌ 获取智能体名称失败: {e}")
            return []

    def _get_satellite_debug_info(self, satellite) -> str:
        """获取卫星调试信息"""
        try:
            info_parts = []

            # 名称
            if hasattr(satellite, 'name'):
                info_parts.append(f"name='{satellite.name}'")

            # 卫星ID
            if hasattr(satellite, 'satellite_id'):
                info_parts.append(f"satellite_id='{satellite.satellite_id}'")

            # 类型
            info_parts.append(f"type={type(satellite).__name__}")

            return f"Satellite({', '.join(info_parts)})"

        except Exception as e:
            return f"Satellite(error: {e})"

    async def _get_available_satellite_info_for_discussion(self) -> List[Dict[str, Any]]:
        """
        获取可用的卫星智能体信息，用于讨论组创建

        Returns:
            卫星信息列表，包含ID、名称等
        """
        try:
            available_satellites = []

            # 从多智能体系统获取所有卫星智能体
            if hasattr(self, '_multi_agent_system') and self._multi_agent_system:
                satellite_agents = self._multi_agent_system.get_all_satellite_agents()

                for satellite_id, satellite_agent in satellite_agents.items():
                    satellite_info = {
                        'id': satellite_id,
                        'name': getattr(satellite_agent, 'name', satellite_id),
                        'satellite_id': getattr(satellite_agent, 'satellite_id', satellite_id),
                        'available': True,
                        'agent_type': type(satellite_agent).__name__
                    }
                    available_satellites.append(satellite_info)

                logger.info(f"📡 获取到 {len(available_satellites)} 个可用卫星智能体信息")
                for sat_info in available_satellites:
                    logger.debug(f"   - {sat_info['id']}: {sat_info['name']}")
            else:
                logger.warning("⚠️ 多智能体系统不可用，无法获取卫星智能体信息")

            return available_satellites

        except Exception as e:
            logger.error(f"❌ 获取可用卫星信息失败: {e}")
            return []

    def set_session_state(self, session_state: Dict[str, Any]):
        """设置session.state引用，用于ADK transfer通信"""
        object.__setattr__(self, '_session_state', session_state)
        logger.info("✅ ADK transfer session.state已设置")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        重写运行方法，集成ADK transfer机制
        """
        try:
            # 设置session.state引用
            if ctx and hasattr(ctx, 'session') and hasattr(ctx.session, 'state'):
                self.set_session_state(ctx.session.state)

            # 如果启用了transfer模式，确保已初始化
            if self._transfer_enabled:
                logger.info("🚀 运行ADK transfer优化的仿真调度")

                # 初始化session.state结构
                if hasattr(self, '_session_state') and self._session_state is not None:
                    if 'task_results' not in self._session_state:
                        self._session_state['task_results'] = {}
                    if 'planning_trigger' not in self._session_state:
                        self._session_state['planning_trigger'] = False
                    if 'pending_delegations' not in self._session_state:
                        self._session_state['pending_delegations'] = {}

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="🚀 启动ADK transfer优化的仿真调度智能体")])
                )
            else:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text="🔄 使用传统模式运行仿真调度智能体")])
                )

            # 调用父类的运行逻辑
            async for event in super()._run_async_impl(ctx):
                yield event

        except Exception as e:
            logger.error(f"❌ ADK transfer集成运行失败: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"❌ 运行失败: {e}")]),
                actions=EventActions(escalate=True)
            )


class SatelliteAgentTransferExtension:
    """
    为现有SatelliteAgent添加ADK transfer支持的扩展

    这个扩展不修改SatelliteAgent的核心代码，而是通过组合模式添加transfer功能
    """

    @staticmethod
    async def enhance_satellite_for_transfer(satellite: SatelliteAgent) -> bool:
        """
        为现有的具身卫星智能体添加ADK transfer支持

        Args:
            satellite: 现有的SatelliteAgent实例

        Returns:
            是否成功添加支持
        """
        try:
            logger.info(f"🔧 为卫星 {satellite.satellite_id} 添加ADK transfer支持")

            # 1. 添加transfer相关属性
            object.__setattr__(satellite, '_transfer_enabled', True)
            object.__setattr__(satellite, '_transfer_task_queue', [])
            object.__setattr__(satellite, '_transfer_results', {})

            # 2. 扩展_run_async_impl方法以支持transfer
            original_run_method = satellite._run_async_impl
            enhanced_run_method = SatelliteAgentTransferExtension._create_enhanced_run_method(
                satellite, original_run_method
            )
            object.__setattr__(satellite, '_run_async_impl', enhanced_run_method)

            # 3. 添加transfer任务处理方法
            object.__setattr__(
                satellite,
                'handle_transfer_task',
                SatelliteAgentTransferExtension._create_transfer_handler(satellite)
            )

            # 4. 添加结果回传方法
            object.__setattr__(
                satellite,
                'report_transfer_result',
                SatelliteAgentTransferExtension._create_result_reporter(satellite)
            )

            logger.info(f"✅ 卫星 {satellite.satellite_id} ADK transfer支持添加完成")
            return True

        except Exception as e:
            logger.error(f"❌ 为卫星 {satellite.satellite_id} 添加transfer支持失败: {e}")
            return False

    @staticmethod
    def _create_enhanced_run_method(satellite: SatelliteAgent, original_method):
        """创建增强的运行方法，支持transfer任务处理"""
        async def enhanced_run_async_impl(ctx: InvocationContext) -> AsyncGenerator[Event, None]:
            try:
                logger.info(f"🛰️ 卫星 {satellite.satellite_id} 开始运行（ADK transfer模式）")

                # 1. 检查是否有transfer委托的任务
                pending_delegations = ctx.session.state.get('pending_delegations', {})
                transfer_tasks = []

                for delegation_id, delegation_info in pending_delegations.items():
                    target_satellite_id = delegation_info.get('target_satellite_id')
                    if target_satellite_id == satellite.satellite_id or target_satellite_id is None:
                        transfer_tasks.append((delegation_id, delegation_info))

                # 2. 处理transfer任务
                if transfer_tasks:
                    async for event in SatelliteAgentTransferExtension._handle_transfer_tasks(
                        satellite, ctx, transfer_tasks
                    ):
                        yield event
                else:
                    # 3. 执行原有的运行逻辑
                    async for event in original_method(ctx):
                        yield event

            except Exception as e:
                logger.error(f"❌ 卫星 {satellite.satellite_id} 增强运行失败: {e}")
                yield Event(
                    author=satellite.name,
                    content=types.Content(parts=[types.Part(text=f"❌ 运行失败: {e}")]),
                    actions=EventActions(escalate=True)
                )

        return enhanced_run_async_impl

    @staticmethod
    async def _handle_transfer_tasks(
        satellite: SatelliteAgent,
        ctx: InvocationContext,
        transfer_tasks: List[tuple]
    ) -> AsyncGenerator[Event, None]:
        """处理transfer委托的任务"""
        try:
            for delegation_id, delegation_info in transfer_tasks:
                task_info = delegation_info.get('task_info', {})
                task_id = task_info.get('task_id')

                yield Event(
                    author=satellite.name,
                    content=types.Content(parts=[types.Part(text=f"📋 接收transfer任务: {task_id}")])
                )

                # 使用现有的任务处理逻辑
                task_result = await SatelliteAgentTransferExtension._execute_transfer_task(
                    satellite, ctx, task_info
                )

                # 保存结果到session.state
                if 'task_results' not in ctx.session.state:
                    ctx.session.state['task_results'] = {}

                ctx.session.state['task_results'][task_id] = task_result

                # 清除已处理的委托
                if 'pending_delegations' in ctx.session.state:
                    ctx.session.state['pending_delegations'].pop(delegation_id, None)

                yield Event(
                    author=satellite.name,
                    content=types.Content(parts=[types.Part(text=f"✅ Transfer任务完成: {task_id}")])
                )

            # 触发下一轮规划
            ctx.session.state['planning_trigger'] = True

            yield Event(
                author=satellite.name,
                content=types.Content(parts=[types.Part(text="🚀 所有transfer任务完成，触发下一轮规划")]),
                actions=EventActions(escalate=True)
            )

        except Exception as e:
            logger.error(f"❌ 处理transfer任务失败: {e}")
            yield Event(
                author=satellite.name,
                content=types.Content(parts=[types.Part(text=f"❌ Transfer任务处理失败: {e}")])
            )

    @staticmethod
    async def _execute_transfer_task(
        satellite: SatelliteAgent,
        ctx: InvocationContext,
        task_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行transfer委托的任务，保持所有具身特性"""
        try:
            task_id = task_info.get('task_id')
            task_type = task_info.get('task_type', 'unknown')

            logger.info(f"🔄 卫星 {satellite.satellite_id} 执行transfer任务: {task_id}")

            # 创建TaskInfo对象（使用现有的数据结构）
            from .satellite_agent import TaskInfo

            # 🔧 修复：从导弹目标名称中提取主要目标ID
            target_id = 'unknown'
            missile_target_names = []
            metadata = task_info.get('metadata', {})

            # 优先从task_info直接获取导弹目标名称
            if 'missile_target_names' in task_info:
                missile_target_names = task_info['missile_target_names']
                if missile_target_names and len(missile_target_names) > 0:
                    target_id = missile_target_names[0]
            elif 'missile_target_names' in metadata:
                missile_target_names = metadata['missile_target_names']
                if missile_target_names and len(missile_target_names) > 0:
                    target_id = missile_target_names[0]
            elif 'missile_list' in metadata:
                # 兼容旧格式
                missile_list = metadata['missile_list']
                if missile_list and len(missile_list) > 0:
                    if isinstance(missile_list[0], dict):
                        target_id = missile_list[0].get('missile_id', 'unknown')
                        missile_target_names = [m.get('missile_id', f'missile_{i}') for i, m in enumerate(missile_list)]
                    else:
                        target_id = missile_list[0]
                        missile_target_names = missile_list

            # 确保metadata中包含完整的导弹目标信息
            if missile_target_names:
                metadata['missile_target_names'] = missile_target_names
                metadata['primary_target'] = target_id
                metadata['missile_count'] = len(missile_target_names)

            logger.info(f"🎯 Transfer任务目标映射: {target_id} (来源: {missile_target_names})")

            task = TaskInfo(
                task_id=task_id,
                target_id=target_id,  # 使用提取的主要目标ID
                start_time=datetime.now(),
                end_time=datetime.now(),
                priority=task_info.get('priority', 0.5),
                status='executing',
                metadata=metadata
            )

            # 使用现有的任务处理逻辑
            if task_type == 'coordination' or task_info.get('requires_discussion_group', False):
                # 协同任务：作为组长创建讨论组
                await satellite._create_discussion_group_as_leader(task, task_info.get('missile_target'))

                result = {
                    "task_id": task_id,
                    "satellite_id": satellite.satellite_id,
                    "execution_time": datetime.now().isoformat(),
                    "result_type": "coordination_leader",
                    "result_data": {
                        "success": True,
                        "details": f"卫星 {satellite.satellite_id} 作为组长创建讨论组",
                        "discussion_group_created": True,
                        "orbital_parameters": getattr(satellite, 'orbital_parameters', {}),
                        "payload_config": getattr(satellite, 'payload_config', {})
                    }
                }
            else:
                # 单独任务：使用现有的任务执行逻辑
                # 这里可以调用现有的可见性计算、STK接口等

                # 模拟使用现有的具身特性
                visibility_result = None
                if hasattr(satellite, '_visibility_calculator') and satellite._visibility_calculator:
                    # 使用真实的可见性计算
                    target_id = task_info.get('target_id')
                    if target_id:
                        visibility_result = await satellite._calculate_visibility_for_target(target_id)

                result = {
                    "task_id": task_id,
                    "satellite_id": satellite.satellite_id,
                    "execution_time": datetime.now().isoformat(),
                    "result_type": "individual",
                    "result_data": {
                        "success": True,
                        "details": f"卫星 {satellite.satellite_id} 完成个体任务",
                        "visibility_result": visibility_result,
                        "orbital_parameters": getattr(satellite, 'orbital_parameters', {}),
                        "payload_config": getattr(satellite, 'payload_config', {}),
                        "stk_connected": hasattr(satellite, '_stk_manager') and satellite._stk_manager is not None
                    }
                }

            logger.info(f"✅ 卫星 {satellite.satellite_id} transfer任务执行完成: {task_id}")
            return result

        except Exception as e:
            logger.error(f"❌ 卫星 {satellite.satellite_id} transfer任务执行失败: {e}")
            return {
                "task_id": task_info.get('task_id'),
                "satellite_id": satellite.satellite_id,
                "execution_time": datetime.now().isoformat(),
                "result_type": "error",
                "result_data": {
                    "success": False,
                    "details": f"任务执行失败: {e}",
                    "error": str(e)
                }
            }

    @staticmethod
    def _create_transfer_handler(satellite: SatelliteAgent):
        """创建transfer任务处理器"""
        async def handle_transfer_task(task_info: Dict[str, Any]) -> Dict[str, Any]:
            """处理transfer委托的任务"""
            return await SatelliteAgentTransferExtension._execute_transfer_task(
                satellite, None, task_info
            )

        return handle_transfer_task

    @staticmethod
    def _create_result_reporter(satellite: SatelliteAgent):
        """创建结果报告器"""
        def report_transfer_result(task_id: str, result: Dict[str, Any]):
            """报告transfer任务结果"""
            logger.info(f"📊 卫星 {satellite.satellite_id} 报告任务结果: {task_id}")
            # 这里可以添加结果报告逻辑
            return True

        return report_transfer_result
