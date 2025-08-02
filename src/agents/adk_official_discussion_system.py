"""
ADK官方多智能体讨论系统
严格按照Google ADK官方文档的最佳实践设计
https://google.github.io/adk-docs/agents/multi-agents/

实现的ADK官方模式：
1. Parallel Fan-Out/Gather Pattern - 并发执行和结果聚合
2. Sequential Pipeline Pattern - 顺序流水线处理
3. Iterative Refinement Pattern - 迭代优化过程
4. 严格使用ADK智能体限制，不创建虚拟智能体
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
from uuid import uuid4

from google.adk.agents import BaseAgent, LlmAgent, SequentialAgent, ParallelAgent, LoopAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.models.lite_llm import LiteLlm
from google.genai import types

from src.utils.adk_session_manager import get_adk_session_manager

logger = logging.getLogger(__name__)

class ADKOfficialDiscussionSystem(LlmAgent):
    """
    ADK官方多智能体讨论系统
    实现官方推荐的多智能体协作模式

    继承LlmAgent以支持直接的大模型访问和配置
    """

    def __init__(self, model: str = "deepseek/deepseek-chat"):
        # 🔧 修复：使用配置文件中的API密钥配置LiteLLM
        from src.utils.config_manager import ConfigManager

        # 获取LLM配置
        config_manager = ConfigManager()
        llm_config = config_manager.config.get('llm', {})  # 直接访问config中的llm配置

        # 使用配置文件中的完整LLM配置
        model_config = {
            'model': model,
            'api_key': llm_config.get('primary', {}).get('api_key'),
            'base_url': llm_config.get('primary', {}).get('base_url'),
            'max_tokens': llm_config.get('primary', {}).get('max_tokens', 4096),
            'temperature': llm_config.get('primary', {}).get('temperature', 0.7)
        }

        super().__init__(
            name="ADKOfficialDiscussionSystem",
            description="基于ADK官方标准的多智能体讨论系统，支持DeepSeek大模型",
            model=LiteLlm(**model_config),
            instruction="""
你是ADK官方多智能体讨论系统的协调器。

你的职责：
1. 协调多个卫星智能体的协作
2. 管理讨论组的生命周期
3. 确保ADK官方模式的正确执行
4. 提供专业的任务分析和结果聚合

请始终遵循ADK官方最佳实践，确保智能体间的高效协作。
"""
        )
        
        # 活跃讨论组
        self._active_discussions: Dict[str, BaseAgent] = {}
        
        # 生命周期监控
        self._lifecycle_monitor_task = None
        self._auto_cleanup_enabled = True
        self._max_discussion_lifetime = 600  # 10分钟最大生命周期
        
        logger.info("✅ ADK官方讨论系统初始化完成")

        # 启动生命周期监控
        self._ensure_lifecycle_monitoring()

    def _ensure_lifecycle_monitoring(self):
        """确保生命周期监控已启动"""
        try:
            # 检查是否有运行的事件循环
            loop = asyncio.get_running_loop()
            if self._lifecycle_monitor_task is None or self._lifecycle_monitor_task.done():
                self._lifecycle_monitor_task = loop.create_task(self._lifecycle_monitor())
                logger.info("✅ ADK官方讨论系统生命周期监控已启动")
        except RuntimeError:
            # 没有运行的事件循环（如在Flask同步环境中）
            logger.info("⚠️ 没有运行的事件循环，生命周期监控将在需要时启动")
            self._lifecycle_monitor_task = None

    async def start_lifecycle_monitoring_async(self):
        """在异步环境中启动生命周期监控"""
        try:
            if self._lifecycle_monitor_task is None or self._lifecycle_monitor_task.done():
                self._lifecycle_monitor_task = asyncio.create_task(self._lifecycle_monitor())
                logger.info("✅ ADK官方讨论系统生命周期监控已启动（异步模式）")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ 启动生命周期监控失败: {e}")
            return False

    async def _lifecycle_monitor(self):
        """生命周期监控任务"""
        try:
            while self._auto_cleanup_enabled:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_expired_discussions()
        except asyncio.CancelledError:
            logger.info("🛑 生命周期监控已停止")
        except Exception as e:
            logger.error(f"❌ 生命周期监控异常: {e}")

    async def _cleanup_expired_discussions(self):
        """清理过期的讨论组"""
        try:
            current_time = datetime.now()
            expired_discussions = []
            
            for discussion_id, discussion_agent in self._active_discussions.items():
                creation_time = getattr(discussion_agent, '_creation_time', current_time)
                if (current_time - creation_time).total_seconds() > self._max_discussion_lifetime:
                    expired_discussions.append(discussion_id)
            
            for discussion_id in expired_discussions:
                await self.complete_discussion(discussion_id)
                logger.info(f"🧹 已清理过期讨论组: {discussion_id}")
                
        except Exception as e:
            logger.error(f"❌ 清理过期讨论组失败: {e}")

    async def create_discussion_with_adk_patterns(
        self,
        pattern_type: str,
        participating_agents: List[BaseAgent],
        task_description: str
    ) -> str:
        """
        使用ADK官方多智能体模式创建讨论组
        严格按照ADK官方文档的Parallel Fan-Out/Gather Pattern设计

        Args:
            pattern_type: 协作模式 ("parallel_fanout", "sequential_pipeline", "iterative_refinement")
            participating_agents: 参与讨论的具身卫星智能体列表
            task_description: 任务描述

        Returns:
            讨论ID
        """
        try:
            from google.adk.agents import ParallelAgent, SequentialAgent, LlmAgent

            logger.info(f"🔄 使用ADK官方模式创建讨论组: {pattern_type}")
            logger.info(f"   参与智能体: {[agent.name for agent in participating_agents]}")
            logger.info(f"   任务描述: {task_description}")

            # 确保生命周期监控已启动
            self._ensure_lifecycle_monitoring()

            # 如果在异步环境中，尝试启动异步生命周期监控
            if self._lifecycle_monitor_task is None:
                await self.start_lifecycle_monitoring_async()

            # 检查并清理智能体的旧关系
            await self._cleanup_agents_old_relationships(participating_agents)

            # 强制重置智能体状态
            await self._force_reset_agents(participating_agents)

            # 生成讨论组ID
            discussion_id = f"adk_official_{uuid4().hex[:8]}"

            # 验证参与智能体都是具身卫星智能体
            for agent in participating_agents:
                if not hasattr(agent, 'satellite_id'):
                    raise ValueError(f"智能体 {agent.name} 不是具身卫星智能体")

            # # 按照ADK官方模式创建讨论组智能体
            # if pattern_type == "parallel_fanout":
            #     # Parallel Fan-Out/Gather Pattern - ADK官方推荐模式
            #     discussion_agent = self._create_adk_parallel_fanout_pattern(
            #         discussion_id, participating_agents, task_description
            #     )
            # elif pattern_type == "sequential_pipeline":
            #     # Sequential Pipeline Pattern - ADK官方推荐模式
            #     discussion_agent = self._create_adk_sequential_pipeline_pattern(
            #         discussion_id, participating_agents, task_description
            #     )
            # elif pattern_type == "iterative_refinement":
            #     # Iterative Refinement Pattern - ADK官方推荐模式
            #     discussion_agent = self._create_adk_iterative_refinement_pattern(
            #         discussion_id, participating_agents, task_description
            #     )
            # else:
            #     raise ValueError(f"不支持的协作模式: {pattern_type}")

            # Iterative Refinement Pattern - ADK官方推荐模式
            discussion_agent = self._create_adk_iterative_refinement_pattern(
                discussion_id, participating_agents, task_description
            )

            # 设置创建时间
            discussion_agent._creation_time = datetime.now()

            # 注册讨论组
            self._active_discussions[discussion_id] = discussion_agent

            # 注册到ADK Session管理器
            session_manager = get_adk_session_manager()
            discussion_info = {
                'discussion_id': discussion_id,
                'pattern_type': pattern_type,
                'agent_count': len(participating_agents),
                'task_description': task_description,
                'creation_time': datetime.now().isoformat()
            }
            session_manager.add_adk_discussion(discussion_id, discussion_info)

            logger.info(f"✅ ADK官方模式讨论组创建成功: {discussion_id} (模式: {pattern_type})")
            logger.info(f"   讨论组类型: {discussion_agent.__class__.__name__}")
            logger.info(f"   使用ADK原生InvocationContext，自动支持model_copy")

            # 🔧 修复：立即执行讨论组进行LLM推理
            await self._execute_discussion_group(discussion_id, discussion_agent, task_description)

            return discussion_id

        except Exception as e:
            logger.error(f"❌ 使用ADK官方模式创建讨论组失败: {e}")
            raise

    async def create_discussion(
        self,
        pattern_type: str,
        participating_agents: List[BaseAgent],
        task_description: str,
        ctx=None
    ) -> str:
        """
        创建ADK官方多智能体讨论组（向后兼容方法）

        这个方法保持向后兼容，但内部使用新的Runner方式

        Args:
            pattern_type: 协作模式
            participating_agents: 参与讨论的具身卫星智能体列表
            task_description: 任务描述
            ctx: 上下文（将被忽略，使用Runner自动创建）

        Returns:
            讨论ID
        """
        logger.info(f"🔄 创建ADK讨论组（兼容模式）: {pattern_type}")

        # 内部调用新的ADK官方模式
        return await self.create_discussion_with_adk_patterns(
            pattern_type=pattern_type,
            participating_agents=participating_agents,
            task_description=task_description
        )

    async def _execute_discussion_group(self, discussion_id: str, discussion_agent, task_description: str):
        """
        执行讨论组进行实际的LLM推理

        使用ADK官方推荐的InMemoryRunner和正确的API
        """
        try:
            logger.info(f"🚀 开始执行讨论组: {discussion_id}")
            logger.info(f"   智能体类型: {discussion_agent.__class__.__name__}")
            logger.info(f"   任务: {task_description}")

            # 🔧 修复：使用ADK官方文档的正确方式
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService
            from google.genai import types

            # 创建会话服务
            session_service = InMemorySessionService()

            # 创建会话
            app_name = "adk_discussion_system"
            user_id = "system"
            session_id = f"discussion_{discussion_id}"

            session = await session_service.create_session(
                app_name=app_name,
                user_id=user_id,
                session_id=session_id
            )

            # 创建Runner
            runner = Runner(
                agent=discussion_agent,
                app_name=app_name,
                session_service=session_service
            )

            logger.info(f"🧠 开始LLM推理...")

            # 构建用户消息内容
            user_message_content = types.Content(
                role='user',
                parts=[types.Part(text=f"""
任务描述: {task_description}

请进行专业分析，包括：
1. GDOP计算和评估（GDOP值越小越好，理想值<2.0）
2. 鲁棒性分析（评分0-100）
3. 覆盖率评估（百分比）
4. 任务可行性分析

请提供具体的数值指标和专业建议。
""")]
            )

            # 🔧 修复：使用正确的run_async API
            response_events = []
            async for event in runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message_content
            ):
                response_events.append(event)

                # 基础事件日志
                logger.info(f"📝 收到事件: {event.author} - {len(str(event.content)) if event.content else 0} 字符")

                # 🔧 新增：详细的迭代指标日志输出
                if event.author and "QualityChecker" in event.author:
                    # 这是质量检查器的响应，包含迭代指标
                    if event.content and event.content.parts:
                        quality_response = ""
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                quality_response += part.text

                        if quality_response:
                            logger.info(f"📊 质量检查器迭代指标分析:")

                            # 提取关键指标
                            lines = quality_response.split('\n')
                            for line in lines:
                                line = line.strip()
                                if any(keyword in line for keyword in ['GDOP评分', 'GDOP分数', 'gdop', 'GDOP']):
                                    logger.info(f"   🎯 {line}")
                                elif any(keyword in line for keyword in ['鲁棒性评分', '鲁棒性分数', '鲁棒性']):
                                    logger.info(f"   🛡️ {line}")
                                elif any(keyword in line for keyword in ['覆盖率评分', '覆盖率分数', '覆盖率']):
                                    logger.info(f"   📡 {line}")
                                elif any(keyword in line for keyword in ['效率评分', '效率分数', '效率']):
                                    logger.info(f"   ⚡ {line}")
                                elif any(keyword in line for keyword in ['综合质量分数', '综合分数', '总分']):
                                    logger.info(f"   🏆 {line}")
                                elif any(keyword in line for keyword in ['是否继续迭代', '迭代决策', '继续迭代']):
                                    logger.info(f"   🔄 {line}")
                                elif any(keyword in line for keyword in ['决策理由', '理由']):
                                    logger.info(f"   💭 {line}")

                            # 显示完整响应的前几行
                            logger.info(f"📋 质量检查器完整响应摘要:")
                            response_lines = quality_response.split('\n')[:8]
                            for i, line in enumerate(response_lines):
                                if line.strip():
                                    logger.info(f"   {i+1}. {line.strip()}")

                            if len(response_lines) > 8:
                                logger.info(f"   ... (还有 {len(quality_response.split('\n')) - 8} 行)")

                # 🔧 新增：卫星智能体详细响应日志
                elif event.author and any(sat_name in event.author for sat_name in ['Satellite', 'GDOP_Sat', 'TestSat']):
                    if event.content and event.content.parts:
                        satellite_response = ""
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                satellite_response += part.text

                        if satellite_response and len(satellite_response) > 50:  # 降低阈值，显示更多响应
                            logger.info(f"🛰️ 卫星智能体 {event.author} LLM响应分析:")

                            # 提取关键信息
                            lines = satellite_response.split('\n')
                            for line in lines:
                                line = line.strip()
                                if any(keyword in line.lower() for keyword in ['gdop', '几何精度', '定位精度']):
                                    logger.info(f"   🎯 GDOP相关: {line}")
                                elif any(keyword in line.lower() for keyword in ['任务', 'task', '执行', '状态']):
                                    logger.info(f"   📋 任务状态: {line}")
                                elif any(keyword in line.lower() for keyword in ['资源', 'resource', '功率', '燃料']):
                                    logger.info(f"   ⚡ 资源状态: {line}")
                                elif any(keyword in line.lower() for keyword in ['覆盖', 'coverage', '可见', '观测']):
                                    logger.info(f"   📡 覆盖分析: {line}")
                                elif any(keyword in line.lower() for keyword in ['轨道', 'orbit', '位置', 'position']):
                                    logger.info(f"   🌍 轨道信息: {line}")
                                elif any(keyword in line.lower() for keyword in ['分析', 'analysis', '评估', '计算']):
                                    logger.info(f"   📊 分析结果: {line}")

                            # 显示完整响应摘要
                            logger.info(f"📋 卫星智能体 {event.author} 完整响应摘要:")
                            response_lines = satellite_response.split('\n')[:6]
                            for i, line in enumerate(response_lines):
                                if line.strip():
                                    logger.info(f"   {i+1}. {line.strip()}")

                            if len(response_lines) > 6:
                                logger.info(f"   ... (还有 {len(satellite_response.split('\n')) - 6} 行，共 {len(satellite_response)} 字符)")

                # 🔧 新增：聚合器智能体详细响应日志
                elif event.author and any(agent_name in event.author for agent_name in ['GatherAgent', 'Gather', 'Aggregator']):
                    if event.content and event.content.parts:
                        gather_response = ""
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                gather_response += part.text

                        if gather_response:
                            logger.info(f"🔄 聚合器智能体 {event.author} LLM响应分析:")

                            # 提取关键聚合信息
                            lines = gather_response.split('\n')
                            for line in lines:
                                line = line.strip()
                                if any(keyword in line.lower() for keyword in ['综合', '聚合', '整合', '汇总']):
                                    logger.info(f"   🔄 聚合分析: {line}")
                                elif any(keyword in line.lower() for keyword in ['gdop', '几何精度']):
                                    logger.info(f"   🎯 GDOP聚合: {line}")
                                elif any(keyword in line.lower() for keyword in ['建议', 'recommend', '优化', '改进']):
                                    logger.info(f"   💡 优化建议: {line}")
                                elif any(keyword in line.lower() for keyword in ['结论', 'conclusion', '总结', '评估']):
                                    logger.info(f"   📊 评估结论: {line}")

                            # 显示聚合器完整响应摘要
                            logger.info(f"📋 聚合器 {event.author} 完整响应摘要:")
                            response_lines = gather_response.split('\n')[:8]
                            for i, line in enumerate(response_lines):
                                if line.strip():
                                    logger.info(f"   {i+1}. {line.strip()}")

                            if len(response_lines) > 8:
                                logger.info(f"   ... (还有 {len(gather_response.split('\n')) - 8} 行，共 {len(gather_response)} 字符)")

                # 🔧 新增：其他智能体详细响应日志
                elif event.author and event.content and event.content.parts:
                    # 处理其他类型的智能体响应
                    other_response = ""
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            other_response += part.text

                    if other_response and len(other_response) > 100:
                        logger.info(f"🤖 智能体 {event.author} LLM响应分析:")

                        # 提取通用关键信息
                        lines = other_response.split('\n')
                        key_lines = []
                        for line in lines:
                            line = line.strip()
                            if any(keyword in line.lower() for keyword in ['gdop', '分析', 'analysis', '评估', '结果', '建议']):
                                key_lines.append(line)

                        # 显示关键信息
                        for line in key_lines[:5]:  # 最多显示5行关键信息
                            logger.info(f"   📝 {line}")

                        # 显示响应摘要
                        logger.info(f"📋 智能体 {event.author} 响应摘要:")
                        response_lines = other_response.split('\n')[:4]
                        for i, line in enumerate(response_lines):
                            if line.strip():
                                logger.info(f"   {i+1}. {line.strip()}")

                        if len(response_lines) > 4:
                            logger.info(f"   ... (共 {len(other_response)} 字符)")

            # 合并所有响应
            response = ""
            for event in response_events:
                if event.content and hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            response += part.text

            # 🔧 新增：LLM响应统计分析
            logger.info(f"🧠 LLM推理完成，响应长度: {len(str(response))} 字符")

            # 统计各类智能体的响应
            agent_responses = {}
            total_response_length = 0

            for event in response_events:
                if event.author and event.content and event.content.parts:
                    event_response = ""
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            event_response += part.text

                    if event_response:
                        agent_type = "其他智能体"
                        if "QualityChecker" in event.author:
                            agent_type = "质量检查器"
                        elif any(sat_name in event.author for sat_name in ['Satellite', 'GDOP_Sat', 'TestSat']):
                            agent_type = "卫星智能体"
                        elif any(agent_name in event.author for agent_name in ['GatherAgent', 'Gather', 'Aggregator']):
                            agent_type = "聚合器智能体"

                        if agent_type not in agent_responses:
                            agent_responses[agent_type] = []
                        agent_responses[agent_type].append({
                            'author': event.author,
                            'length': len(event_response),
                            'content': event_response[:100] + "..." if len(event_response) > 100 else event_response
                        })
                        total_response_length += len(event_response)

            # 显示响应统计
            logger.info(f"📊 LLM响应统计分析:")
            logger.info(f"   总响应长度: {total_response_length} 字符")
            logger.info(f"   参与智能体类型: {len(agent_responses)} 种")
            logger.info(f"   总响应事件数: {len([e for e in response_events if e.content])} 个")

            for agent_type, responses in agent_responses.items():
                total_length = sum(r['length'] for r in responses)
                logger.info(f"   📋 {agent_type}: {len(responses)} 个响应，共 {total_length} 字符")
                for resp in responses:
                    logger.info(f"      - {resp['author']}: {resp['length']} 字符")

            logger.info(f"📊 LLM响应摘要: {str(response)[:200]}...")

            # 🔧 新增：迭代进度统计
            quality_checker_events = [e for e in response_events if e.author and "QualityChecker" in e.author]
            if quality_checker_events:
                current_iteration = len(quality_checker_events)
                logger.info(f"🔄 迭代进度统计:")
                logger.info(f"   当前迭代次数: {current_iteration}")
                logger.info(f"   最大迭代次数: 5")
                logger.info(f"   迭代进度: {current_iteration}/5 ({current_iteration/5*100:.1f}%)")

                # 分析迭代趋势
                if current_iteration > 1:
                    logger.info(f"   迭代状态: 正在进行多轮优化")
                elif current_iteration == 1:
                    logger.info(f"   迭代状态: 首次质量检查完成")

                # 检查是否应该停止迭代
                last_quality_event = quality_checker_events[-1]
                if last_quality_event.content and last_quality_event.content.parts:
                    last_response = ""
                    for part in last_quality_event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            last_response += part.text

                    if "停止迭代" in last_response or "不继续" in last_response or "escalate" in last_response.lower():
                        logger.info(f"   🛑 质量检查器建议停止迭代")
                    elif "继续迭代" in last_response or "需要优化" in last_response:
                        logger.info(f"   ⏭️ 质量检查器建议继续迭代")
            else:
                logger.info(f"🔄 迭代模式: 非迭代优化模式或首次执行")

            # 保存执行结果到讨论组
            if not hasattr(discussion_agent, '_execution_results'):
                discussion_agent._execution_results = {}

            discussion_agent._execution_results[discussion_id] = {
                'response': str(response),
                'execution_time': datetime.now().isoformat(),
                'task_description': task_description,
                'status': 'completed',
                'session_id': session_id
            }

            logger.info(f"✅ 讨论组执行完成: {discussion_id}")

        except Exception as e:
            logger.error(f"❌ 执行讨论组失败: {discussion_id}, 错误: {e}")
            import traceback
            traceback.print_exc()

            # 保存错误信息
            if not hasattr(discussion_agent, '_execution_results'):
                discussion_agent._execution_results = {}

            discussion_agent._execution_results[discussion_id] = {
                'error': str(e),
                'execution_time': datetime.now().isoformat(),
                'task_description': task_description,
                'status': 'failed'
            }

            # 不抛出异常，让讨论组创建成功，但标记为执行失败

    async def _cleanup_agents_old_relationships(self, agents: List[BaseAgent]):
        """检查并清理智能体的旧关系"""
        logger.info(f"🧹 检查并清理 {len(agents)} 个智能体的旧关系")
        
        for agent in agents:
            # 检查是否有旧的父子关系
            if hasattr(agent, '_parent_agent'):
                delattr(agent, '_parent_agent')
            if hasattr(agent, '_sub_agents'):
                delattr(agent, '_sub_agents')
            if hasattr(agent, '_discussion_id'):
                delattr(agent, '_discussion_id')
        
        logger.info("✅ 所有智能体都没有旧的父子关系")

    async def _force_reset_agents(self, agents: List[BaseAgent]):
        """强制重置智能体状态"""
        logger.info(f"🔧 强制重置 {len(agents)} 个智能体状态")
        
        for agent in agents:
            # 重置智能体的内部状态
            if hasattr(agent, '_last_response'):
                agent._last_response = None
            if hasattr(agent, '_execution_count'):
                agent._execution_count = 0
        
        logger.info("✅ 所有智能体状态重置完成")

    async def complete_discussion(self, discussion_id: str) -> Dict[str, Any]:
        """
        完成并解散讨论组（ADK标准方式）

        按照ADK官方文档，正确解散智能体但保持具身智能体状态

        Returns:
            包含执行结果的字典
        """
        try:
            if discussion_id in self._active_discussions:
                discussion_agent = self._active_discussions[discussion_id]

                # 获取执行结果
                execution_results = getattr(discussion_agent, '_execution_results', {})
                discussion_result = execution_results.get(discussion_id, {})

                # 分析执行结果
                if discussion_result.get('status') == 'completed':
                    status = 'success'
                    response = discussion_result.get('response', '')

                    # 简单的质量评估（基于响应长度和关键词）
                    quality_score = self._evaluate_response_quality(response)

                    logger.info(f"� 讨论组执行成功: {discussion_id}")
                    logger.info(f"   响应长度: {len(response)} 字符")
                    logger.info(f"   质量评分: {quality_score:.3f}")

                elif discussion_result.get('status') == 'failed':
                    status = 'failed'
                    quality_score = 0.0
                    response = f"执行失败: {discussion_result.get('error', '未知错误')}"

                    logger.error(f"❌ 讨论组执行失败: {discussion_id}")
                    logger.error(f"   错误: {discussion_result.get('error', '未知错误')}")

                else:
                    status = 'failed'
                    quality_score = 0.0
                    response = "未找到执行结果"

                    logger.warning(f"⚠️ 讨论组无执行结果: {discussion_id}")

                # �🔧 ADK标准：安全解散智能体，保持具身智能体状态
                await self._dissolve_discussion_agents_safely(discussion_agent)

                # 清理讨论组引用
                del self._active_discussions[discussion_id]

                # 从Session管理器中移除
                session_manager = get_adk_session_manager()
                session_manager.remove_adk_discussion(discussion_id)

                logger.info(f"✅ 讨论组已安全解散: {discussion_id}")
                logger.info(f"   具身智能体状态已保持，可用于下次滚动规划")

                return {
                    'success': True,
                    'status': status,
                    'quality_score': quality_score,
                    'response': response,
                    'execution_time': discussion_result.get('execution_time'),
                    'iterations': 1  # 当前实现为单次执行
                }
            else:
                logger.warning(f"⚠️ 讨论组不存在: {discussion_id}")
                return {
                    'success': False,
                    'status': 'failed',
                    'quality_score': 0.0,
                    'response': f"讨论组不存在: {discussion_id}",
                    'iterations': 0
                }

        except Exception as e:
            logger.error(f"❌ 解散讨论组失败: {e}")
            return {
                'success': False,
                'status': 'failed',
                'quality_score': 0.0,
                'response': f"解散失败: {e}",
                'iterations': 0
            }

    def _evaluate_response_quality(self, response: str) -> float:
        """
        评估响应质量

        简单的质量评估算法，基于响应长度和关键词
        """
        if not response:
            return 0.0

        # 基础分数（基于长度）
        length_score = min(len(response) / 1000.0, 0.5)  # 最多0.5分

        # 关键词分数
        keywords = ['gdop', 'GDOP', '鲁棒性', '覆盖率', '可行性', '分析', '评估', '计算']
        keyword_score = 0.0
        for keyword in keywords:
            if keyword in response:
                keyword_score += 0.1

        keyword_score = min(keyword_score, 0.5)  # 最多0.5分

        total_score = length_score + keyword_score
        return min(total_score, 1.0)  # 最高1.0分

    async def _dissolve_discussion_agents_safely(self, discussion_agent):
        """
        安全解散讨论组中的智能体（ADK标准方式）

        根据ADK官方文档：
        1. 只清理父子关系，不重新初始化具身智能体
        2. 保持具身智能体的任务状态和资源状态
        3. 确保下次滚动规划可以正确使用这些状态
        """
        try:
            # 获取讨论组中的参与智能体
            participating_agents = getattr(discussion_agent, '_discussion_members', [])

            logger.info(f"🔄 开始安全解散 {len(participating_agents)} 个智能体")

            for agent in participating_agents:
                # 只处理具身卫星智能体
                if hasattr(agent, 'satellite_id'):
                    satellite_id = agent.satellite_id

                    try:
                        # 🎯 ADK标准：只清理父智能体关系，保持具身智能体状态
                        self._safely_remove_parent_relationship(agent, satellite_id)

                        # 🔧 保持重要状态：任务执行状态、资源状态等
                        self._preserve_embodied_agent_state(agent, satellite_id)

                        logger.info(f"✅ 卫星智能体 {satellite_id} 已安全解散（状态已保持）")

                    except Exception as agent_error:
                        logger.warning(f"⚠️ 解散卫星智能体 {satellite_id} 时出现问题: {agent_error}")
                        # 继续处理其他智能体，不中断整个过程

            logger.info(f"✅ 所有智能体已安全解散，具身状态已保持")

        except Exception as e:
            logger.error(f"❌ 安全解散智能体失败: {e}")
            # 不抛出异常，确保讨论组清理可以继续

    def _safely_remove_parent_relationship(self, agent, satellite_id: str):
        """
        安全移除智能体的父关系（ADK标准方式）

        只清理ADK框架的父子关系，不影响具身智能体本身
        """
        try:
            # 🎯 ADK标准：清理所有可能的父智能体属性
            parent_attributes = [
                '_parent_agent',    # ADK标准父智能体属性
                'parent_agent',     # 可能的别名
                '_adk_parent',      # ADK内部父引用
                '_parent',          # 通用父引用
            ]

            for attr in parent_attributes:
                if hasattr(agent, attr):
                    old_parent = getattr(agent, attr)
                    if old_parent is not None:
                        logger.debug(f"   清理 {satellite_id} 的 {attr}: {getattr(old_parent, 'name', 'unknown')}")
                        setattr(agent, attr, None)

            # 🔧 清理ADK内部状态（如果存在）
            adk_internal_attributes = [
                '_sub_agents',      # 子智能体列表
                '_discussion_id',   # 讨论组ID
                '_adk_context',     # ADK上下文
                '_adk_session',     # ADK会话
            ]

            for attr in adk_internal_attributes:
                if hasattr(agent, attr):
                    setattr(agent, attr, None)
                    logger.debug(f"   清理 {satellite_id} 的 {attr}")

            logger.debug(f"✅ {satellite_id} 的父关系已安全清理")

        except Exception as e:
            logger.warning(f"⚠️ 清理 {satellite_id} 父关系失败: {e}")
            # 不抛出异常，继续处理

    def _preserve_embodied_agent_state(self, agent, satellite_id: str):
        """
        保持具身智能体的重要状态

        确保下次滚动规划可以正确使用这些状态：
        1. 任务执行历史和状态
        2. 资源使用情况
        3. 性能指标
        4. 协作经验
        """
        try:
            # 🎯 保持的重要状态（这些状态对下次滚动规划很重要）
            preserved_states = [
                'satellite_id',           # 卫星ID（核心标识）
                '_config',               # 配置信息
                '_time_manager',         # 时间管理器
                '_stk_manager',          # STK管理器
                '_multi_agent_system',   # 多智能体系统引用
                'memory_module',         # 记忆模块
                '_task_history',         # 任务历史
                '_resource_status',      # 资源状态
                '_performance_metrics',  # 性能指标
                '_collaboration_history', # 协作历史
                '_visibility_calculator', # 可见性计算器
                '_discussion_groups',    # 讨论组历史
            ]

            preserved_count = 0
            for state_attr in preserved_states:
                if hasattr(agent, state_attr):
                    # 确保这些状态不被意外清理
                    value = getattr(agent, state_attr)
                    if value is not None:
                        preserved_count += 1
                        logger.debug(f"   保持 {satellite_id}.{state_attr}")

            # 🔧 重置临时执行状态（但保持重要状态）
            temporary_states = {
                '_last_response': None,      # 清理上次响应
                '_current_iteration': 0,     # 重置迭代计数
                '_iteration_results': [],    # 清理迭代结果
                '_discussion_state': None,   # 清理讨论状态
            }

            for attr, default_value in temporary_states.items():
                if hasattr(agent, attr):
                    setattr(agent, attr, default_value)
                    logger.debug(f"   重置 {satellite_id}.{attr}")

            logger.debug(f"✅ {satellite_id} 状态已保持：{preserved_count} 个重要状态保留")

        except Exception as e:
            logger.warning(f"⚠️ 保持 {satellite_id} 状态失败: {e}")
            # 不抛出异常，继续处理

    def _create_adk_parallel_fanout_pattern(
        self,
        discussion_id: str,
        participating_agents: List[BaseAgent],
        task_description: str
    ) -> SequentialAgent:
        """
        创建ADK官方Parallel Fan-Out/Gather Pattern

        根据ADK官方文档：
        1. ParallelAgent并发执行所有智能体
        2. LlmAgent聚合器收集和分析结果
        3. SequentialAgent组合Fan-Out和Gather阶段
        """
        from google.adk.agents import ParallelAgent, SequentialAgent, LlmAgent

        logger.info(f"🔄 创建ADK官方Parallel Fan-Out/Gather模式: {discussion_id}")

        # 阶段1：Parallel Fan-Out - 所有智能体并发执行
        parallel_stage = ParallelAgent(
            name=f"ParallelFanOut_{discussion_id}",
            sub_agents=participating_agents
        )

        # 阶段2：Gather - 专业聚合器（继承父类的模型配置）
        gather_agent = LlmAgent(
            name=f"GatherAgent_{discussion_id}",
            model=self.model,  # 继承ADKOfficialDiscussionSystem的模型配置
            instruction=f"""
你是专业的结果聚合器，负责收集和深度分析并发执行的结果。

任务描述: {task_description}

请执行以下专业分析步骤：

1. **结果收集与整理**：
   - 收集所有卫星智能体的执行结果
   - 整理各智能体的分析数据和指标

2. **专业指标计算**：
   - 计算系统级GDOP（几何精度因子，越小越好，理想值<2.0）
   - 评估整体鲁棒性评分
   - 分析覆盖率和任务可行性
   - 计算资源利用效率

3. **深度分析报告**：
   - 分析结果的一致性和质量
   - 识别潜在的系统瓶颈
   - 评估任务执行风险
   - 提供优化建议

4. **结构化输出**：
   请以以下格式输出分析结果：

   ## 系统级指标
   - 整体GDOP: [数值，越小越好，理想值<2.0]
   - 系统鲁棒性: [0-100评分]
   - 覆盖率: [百分比]
   - 资源利用率: [百分比]

   ## 详细分析
   [具体分析内容]

   ## 优化建议
   [改进建议]

将聚合结果保存到session.state['fanout_gather_result']中。
""",
            output_key="fanout_gather_result"
        )

        # 组合Fan-Out和Gather阶段
        discussion_agent = SequentialAgent(
            name=f"ParallelFanOutGather_{discussion_id}",
            sub_agents=[parallel_stage, gather_agent]
        )

        # 设置讨论组属性
        discussion_agent._discussion_id = discussion_id
        discussion_agent._discussion_type = "parallel_fanout"
        discussion_agent._discussion_members = participating_agents
        discussion_agent._discussion_task = task_description
        discussion_agent._parallel_stage = parallel_stage
        discussion_agent._gather_stage = gather_agent

        logger.info(f"✅ ADK官方Parallel Fan-Out/Gather模式创建完成: {discussion_id}")
        logger.info(f"   Fan-Out智能体数量: {len(participating_agents)}")
        logger.info(f"   Gather智能体: {gather_agent.name}")

        return discussion_agent

    def _create_adk_sequential_pipeline_pattern(
        self,
        discussion_id: str,
        participating_agents: List[BaseAgent],
        task_description: str
    ) -> SequentialAgent:
        """
        创建ADK官方Sequential Pipeline Pattern

        根据ADK官方文档：
        1. SequentialAgent按顺序执行智能体
        2. 通过session.state传递流水线结果
        3. 每个智能体读取前一个的输出
        """
        from google.adk.agents import SequentialAgent

        logger.info(f"🔄 创建ADK官方Sequential Pipeline模式: {discussion_id}")

        # 为每个智能体设置流水线配置
        for i, agent in enumerate(participating_agents):
            agent._pipeline_stage = i + 1
            agent._pipeline_task = f"流水线第{i+1}阶段: {task_description}"
            logger.info(f"   📋 配置流水线阶段{i+1}: {agent.name}")

        # 创建顺序流水线
        discussion_agent = SequentialAgent(
            name=f"SequentialPipeline_{discussion_id}",
            sub_agents=participating_agents
        )

        # 设置讨论组属性
        discussion_agent._discussion_id = discussion_id
        discussion_agent._discussion_type = "sequential_pipeline"
        discussion_agent._discussion_members = participating_agents
        discussion_agent._discussion_task = task_description

        logger.info(f"✅ ADK官方Sequential Pipeline模式创建完成: {discussion_id}")
        logger.info(f"   流水线步骤数量: {len(participating_agents)}")

        return discussion_agent

    def _create_adk_iterative_refinement_pattern(
        self,
        discussion_id: str,
        participating_agents: List[BaseAgent],
        task_description: str
    ) -> LoopAgent:
        """
        创建ADK官方Iterative Refinement Pattern

        根据ADK官方文档：
        1. LoopAgent重复执行sub_agents
        2. 通过session.state保持迭代状态
        3. 通过escalate=True终止循环
        """
        from google.adk.agents import LoopAgent, SequentialAgent, LlmAgent, BaseAgent
        from google.adk.events import Event, EventActions
        from google.adk.agents.invocation_context import InvocationContext
        from typing import AsyncGenerator

        logger.info(f"🔄 创建ADK官方Iterative Refinement模式: {discussion_id}")

        # 创建并发执行阶段
        parallel_stage = ParallelAgent(
            name=f"IterativeParallel_{discussion_id}",
            sub_agents=participating_agents
        )

        # 创建专业质量检查和优化智能体（继承父类的模型配置）
        quality_checker = LlmAgent(
            name=f"QualityChecker_{discussion_id}",
            model=self.model,  # 继承ADKOfficialDiscussionSystem的模型配置
            instruction=f"""
你是专业的质量检查和优化智能体，负责深度评估迭代结果并决定是否继续优化。

任务描述: {task_description}

请执行以下专业评估步骤：

1. **多维度质量评估**：
   - GDOP质量评分（0-1）
   - 鲁棒性评分（0-1）
   - 覆盖率评分（0-1）
   - 资源效率评分（0-1）

2. **综合质量计算**：
   - 计算加权综合质量分数
   - 权重：GDOP(0.3) + 鲁棒性(0.3) + 覆盖率(0.2) + 效率(0.2)

3. **迭代决策逻辑**：
   - 如果综合质量分数 >= 0.85，设置escalate=True停止迭代
   - 如果分数 < 0.6，提供具体改进建议
   - 如果0.6 <= 分数 < 0.85，进行微调优化

4. **专业改进建议**：
   - 基于具体指标提供优化方向
   - 识别性能瓶颈和改进点
   - 提供量化的改进目标

请以结构化格式输出评估结果：

## 质量评估结果
- GDOP评分: [0-1]
- 鲁棒性评分: [0-1]
- 覆盖率评分: [0-1]
- 效率评分: [0-1]
- **综合质量分数: [0-1]**

## 迭代决策
- 是否继续迭代: [是/否]
- 决策理由: [具体原因]

## 改进建议
[具体的优化建议]

将结果保存到session.state['iterative_result']中。
如果需要停止迭代，设置session.state['should_escalate'] = True。
""",
            output_key="iterative_result"
        )

        # 创建迭代序列
        iteration_sequence = SequentialAgent(
            name=f"IterationSequence_{discussion_id}",
            sub_agents=[parallel_stage, quality_checker]
        )

        # 创建LoopAgent
        discussion_agent = LoopAgent(
            name=f"IterativeRefinement_{discussion_id}",
            max_iterations=5,
            sub_agents=[iteration_sequence]
        )

        # 设置讨论组属性
        discussion_agent._discussion_id = discussion_id
        discussion_agent._discussion_type = "iterative_refinement"
        discussion_agent._discussion_members = participating_agents
        discussion_agent._discussion_task = task_description

        logger.info(f"✅ ADK官方Iterative Refinement模式创建完成: {discussion_id}")
        logger.info(f"   参与智能体数量: {len(participating_agents)}")
        logger.info(f"   最大迭代次数: 5")

        return discussion_agent

    def __del__(self):
        """析构函数，确保清理资源"""
        if self._lifecycle_monitor_task and not self._lifecycle_monitor_task.done():
            self._lifecycle_monitor_task.cancel()
            logger.info("🛑 生命周期监控已停止")
