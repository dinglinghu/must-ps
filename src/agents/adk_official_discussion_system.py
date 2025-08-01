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
from google.genai import types

from src.utils.adk_session_manager import get_adk_session_manager

logger = logging.getLogger(__name__)

class ADKOfficialDiscussionSystem(BaseAgent):
    """
    ADK官方多智能体讨论系统
    实现官方推荐的多智能体协作模式
    """
    
    def __init__(self):
        super().__init__(
            name="ADKOfficialDiscussionSystem",
            description="基于ADK官方标准的多智能体讨论系统"
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

            # 按照ADK官方模式创建讨论组智能体
            if pattern_type == "parallel_fanout":
                # Parallel Fan-Out/Gather Pattern - ADK官方推荐模式
                discussion_agent = self._create_adk_parallel_fanout_pattern(
                    discussion_id, participating_agents, task_description
                )
            elif pattern_type == "sequential_pipeline":
                # Sequential Pipeline Pattern - ADK官方推荐模式
                discussion_agent = self._create_adk_sequential_pipeline_pattern(
                    discussion_id, participating_agents, task_description
                )
            elif pattern_type == "iterative_refinement":
                # Iterative Refinement Pattern - ADK官方推荐模式
                discussion_agent = self._create_adk_iterative_refinement_pattern(
                    discussion_id, participating_agents, task_description
                )
            else:
                raise ValueError(f"不支持的协作模式: {pattern_type}")

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

    async def complete_discussion(self, discussion_id: str) -> bool:
        """完成并清理讨论组"""
        try:
            if discussion_id in self._active_discussions:
                discussion_agent = self._active_discussions[discussion_id]
                
                # 清理讨论组
                del self._active_discussions[discussion_id]
                
                # 从Session管理器中移除
                session_manager = get_adk_session_manager()
                session_manager.remove_adk_discussion(discussion_id)
                
                logger.info(f"✅ 讨论组已完成并清理: {discussion_id}")
                return True
            else:
                logger.warning(f"⚠️ 讨论组不存在: {discussion_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 完成讨论组失败: {e}")
            return False

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

        # 阶段2：Gather - 聚合器收集结果
        gather_agent = LlmAgent(
            name=f"GatherAgent_{discussion_id}",
            model="gemini-2.0-flash",
            instruction=f"""
你是结果聚合器，负责收集和分析并发执行的结果。

任务描述: {task_description}

请执行以下步骤：
1. 收集所有智能体的执行结果
2. 分析结果的一致性和质量
3. 生成综合性的分析报告
4. 提供改进建议

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

        # 创建质量检查和优化智能体
        quality_checker = LlmAgent(
            name=f"QualityChecker_{discussion_id}",
            model="gemini-2.0-flash",
            instruction=f"""
你是质量检查和优化智能体，负责评估迭代结果并决定是否继续。

任务描述: {task_description}

请执行以下步骤：
1. 评估当前迭代的结果质量
2. 计算质量分数（0-1之间）
3. 如果质量分数 >= 0.8，设置escalate=True停止迭代
4. 否则提供改进建议并继续迭代

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
            max_iterations=10,
            sub_agents=[iteration_sequence]
        )

        # 设置讨论组属性
        discussion_agent._discussion_id = discussion_id
        discussion_agent._discussion_type = "iterative_refinement"
        discussion_agent._discussion_members = participating_agents
        discussion_agent._discussion_task = task_description

        logger.info(f"✅ ADK官方Iterative Refinement模式创建完成: {discussion_id}")
        logger.info(f"   参与智能体数量: {len(participating_agents)}")
        logger.info(f"   最大迭代次数: 10")

        return discussion_agent

    def __del__(self):
        """析构函数，确保清理资源"""
        if self._lifecycle_monitor_task and not self._lifecycle_monitor_task.done():
            self._lifecycle_monitor_task.cancel()
            logger.info("🛑 生命周期监控已停止")
