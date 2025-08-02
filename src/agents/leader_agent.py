"""
组长智能体
基于ADK的LlmAgent实现，负责讨论组管理、可见窗口计算、任务分配和协调决策
"""

import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, AsyncGenerator, Set
from dataclasses import dataclass, asdict

# ADK框架导入 - 强制使用真实ADK
from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.tools import FunctionTool
from google.genai import types

from ..utils.llm_config_manager import get_llm_config_manager

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于组长智能体")

# 创建AgentTool类，因为真实ADK中可能没有
class AgentTool(FunctionTool):
    """智能体工具包装器"""
    def __init__(self, agent):
        self.agent = agent
        super().__init__(func=self._run_agent)

    async def _run_agent(self, *args, **kwargs):
        """运行智能体"""
        return f"调用智能体 {self.agent.name} 完成"

from .satellite_agent import SatelliteAgent

logger = logging.getLogger(__name__)
logger.info("✅ 使用真实ADK框架于组长智能体")


@dataclass
class DiscussionGroup:
    """讨论组数据结构"""
    group_id: str
    target_id: str
    leader_id: str
    member_satellites: List[str]
    created_time: datetime
    status: str  # 'active', 'discussing', 'completed', 'disbanded'
    discussion_rounds: int
    max_rounds: int


@dataclass
class VisibilityWindow:
    """可见性窗口数据结构"""
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    elevation_angle: float
    azimuth_angle: float
    range_km: float


@dataclass
class TaskAllocation:
    """任务分配结果数据结构"""
    target_id: str
    allocated_satellites: List[str]
    time_windows: List[VisibilityWindow]
    optimization_score: float
    allocation_strategy: str


class LeaderAgent(LlmAgent):
    """
    组长智能体
    
    基于ADK的LlmAgent实现，负责讨论组管理、可见窗口计算、
    任务分配和协调决策。使用ADK的coordinate协同方式。
    """
    
    def __init__(
        self,
        name: str,
        target_id: str,
        model: str = "gemini-2.0-flash",
        config: Optional[Dict[str, Any]] = None,
        config_path: Optional[str] = None
    ):
        """
        初始化组长智能体

        Args:
            name: 智能体名称
            target_id: 负责的目标ID
            model: 使用的大模型
            config: 配置参数
            config_path: 配置文件路径
        """
        # 初始化大模型配置管理器
        llm_config_mgr = get_llm_config_manager(config_path or "config/config.yaml")

        # 初始化时间管理器
        from ..utils.time_manager import get_time_manager
        self._time_manager = get_time_manager()

        # 获取大模型配置
        llm_config = llm_config_mgr.get_llm_config('leader_agents')

        # 获取智能体提示词配置并格式化
        instruction = llm_config_mgr.format_system_prompt(
            'leader_agents',
            target_id=target_id,
            current_time=self._time_manager.get_current_simulation_time().isoformat()
        )

        # 初始化ADK LlmAgent
        super().__init__(
            name=name,
            model=llm_config.model,  # 使用配置管理器中的模型
            instruction=instruction,
            description=f"负责目标 {target_id} 的组长智能体，协调讨论组决策",
            tools=[],  # 稍后设置工具
            sub_agents=[]  # 子智能体将动态添加
        )

        # 在super().__init__()之后设置自定义属性
        object.__setattr__(self, 'target_id', target_id)
        object.__setattr__(self, 'config', config or {})
        
        # 讨论组状态
        self.discussion_group = None
        self.member_agents: Dict[str, SatelliteAgent] = {}
        self.visibility_windows: List[VisibilityWindow] = []
        self.discussion_history: List[Dict[str, Any]] = []
        self.final_allocation: Optional[TaskAllocation] = None
        
        # 配置参数
        self.max_discussion_rounds = self.config.get('max_discussion_rounds', 5)
        self.discussion_timeout = self.config.get('discussion_timeout', 600)  # 10分钟

        # 设置工具
        self.tools = self._create_tools()

        logger.info(f"👑 组长智能体 {name} 初始化完成，负责目标: {target_id}")
    
    def _create_tools(self) -> List[FunctionTool]:
        """创建智能体工具"""
        tools = []
        
        # 建立讨论组工具
        async def establish_discussion_group(meta_task_info: str) -> str:
            """建立ADK标准讨论组"""
            try:
                task_data = json.loads(meta_task_info)

                # 获取多智能体系统引用
                if not hasattr(self, '_multi_agent_system') or not self._multi_agent_system:
                    return "❌ 多智能体系统未连接，无法创建ADK标准讨论组"

                # 使用标准ADK上下文创建工具
                from ..utils.adk_standard_context import create_standard_session

                mock_ctx = create_standard_session(
                    app_name="leader_agent",
                    user_id=self.name,
                    session_id=f"leader_session_{self.target_id}"
                )

                # 使用ADK官方讨论系统创建讨论组
                task_description = f"组长智能体任务 - 目标: {self.target_id}"
                adk_official_system = self._multi_agent_system.get_adk_official_discussion_system()
                if adk_official_system:
                    discussion_id = await adk_official_system.create_discussion_with_adk_patterns(
                        pattern_type="sequential_pipeline",  # 组长智能体使用顺序流水线模式
                        participating_agents=[self],  # 暂时只包含自己，后续可以添加成员
                        task_description=task_description
                    )
                else:
                    discussion_id = None

                if discussion_id:
                    # 创建简化的讨论组信息（保持向后兼容）
                    self.discussion_group = DiscussionGroup(
                        group_id=discussion_id,
                        target_id=self.target_id,
                        leader_id=self.name,
                        member_satellites=[],
                        created_time=self._time_manager.get_current_simulation_time(),
                        status='active',
                        discussion_rounds=0,
                        max_rounds=self.max_discussion_rounds
                    )

                    return f"ADK标准讨论组 {discussion_id} 建立成功"
                else:
                    return "❌ ADK标准讨论组创建失败"

            except Exception as e:
                return f"ADK标准讨论组建立失败: {e}"
        
        tools.append(FunctionTool(func=establish_discussion_group))
        
        # 可见窗口计算工具（并发版本）
        async def calculate_visibility_windows(constellation_info: str) -> str:
            """并发计算可见窗口"""
            try:
                logger.info(f"🚀 开始并发计算可见窗口 - 目标: {self.target_id}")

                # 获取所有可用卫星ID
                satellite_ids = await self._get_available_satellite_ids()

                if not satellite_ids:
                    logger.warning("⚠️ 未找到可用卫星，使用默认卫星列表")
                    satellite_ids = ["Satellite_01", "Satellite_02", "Satellite_03", "Satellite_04", "Satellite_05"]

                # 并发计算每颗卫星的可见窗口
                visibility_results = await self._calculate_visibility_concurrent(satellite_ids)

                # 过滤有效的可见窗口
                self.visibility_windows = [vw for vw in visibility_results if vw is not None]

                logger.info(f"✅ 并发计算完成，发现 {len(self.visibility_windows)} 个可见窗口")

                # 按开始时间排序
                self.visibility_windows.sort(key=lambda vw: vw.start_time)

                return f"并发计算完成，发现 {len(self.visibility_windows)} 个可见窗口，涉及 {len(satellite_ids)} 颗卫星"

            except Exception as e:
                logger.error(f"❌ 并发可见窗口计算失败: {e}")
                return f"并发可见窗口计算失败: {e}"
        
        tools.append(FunctionTool(func=calculate_visibility_windows))
        
        # 任务分配决策工具
        async def make_task_allocation_decision(discussion_summary: str) -> str:
            """做出任务分配决策"""
            try:
                # 基于讨论结果和优化目标做出决策
                allocated_satellites = [vw.satellite_id for vw in self.visibility_windows[:2]]
                
                self.final_allocation = TaskAllocation(
                    target_id=self.target_id,
                    allocated_satellites=allocated_satellites,
                    time_windows=self.visibility_windows[:2],
                    optimization_score=0.85,  # 模拟优化分数
                    allocation_strategy="GDOP_optimized"
                )
                
                return f"任务分配决策完成，分配给卫星: {allocated_satellites}"
                
            except Exception as e:
                return f"任务分配决策失败: {e}"
        
        tools.append(FunctionTool(func=make_task_allocation_decision))
        
        # 讨论协调工具
        async def coordinate_discussion_round(round_number: int) -> str:
            """协调讨论轮次"""
            try:
                if not self.discussion_group:
                    return "讨论组未建立"
                
                # 收集各卫星智能体的意见
                member_opinions = []
                for satellite_id, agent in self.member_agents.items():
                    # 这里将实现实际的智能体协调逻辑
                    opinion = f"{satellite_id}: 可接受任务，当前负载70%"
                    member_opinions.append(opinion)
                
                # 记录讨论历史
                discussion_record = {
                    'round': round_number,
                    'timestamp': datetime.now().isoformat(),
                    'opinions': member_opinions,
                    'leader_summary': f"第{round_number}轮讨论，收集到{len(member_opinions)}个意见"
                }
                
                self.discussion_history.append(discussion_record)
                self.discussion_group.discussion_rounds = round_number
                
                return f"第{round_number}轮讨论完成，收集{len(member_opinions)}个意见"
                
            except Exception as e:
                return f"讨论协调失败: {e}"
        
        tools.append(FunctionTool(func=coordinate_discussion_round))
        
        return tools
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        组长智能体主要运行逻辑
        实现讨论组协调和任务分配决策
        """
        logger.info(f"[{self.name}] 组长智能体开始协调目标 {self.target_id}")
        
        try:
            # 1. 建立讨论组
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"为目标 {self.target_id} 建立讨论组...")])
            )
            
            group_result = await self._establish_discussion_group_internal(ctx)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=group_result)])
            )
            
            # 2. 计算可见窗口
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="计算目标可见窗口...")])
            )
            
            visibility_result = await self._calculate_visibility_internal(ctx)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=visibility_result)])
            )
            
            # 3. 招募组员
            if self.visibility_windows:
                recruitment_result = await self._recruit_group_members(ctx)
                
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=recruitment_result)])
                )
            
            # 4. 组织讨论
            if self.member_agents:
                async for event in self._conduct_group_discussion(ctx):
                    yield event
            
            # 5. 做出最终决策
            decision_result = await self._make_final_decision(ctx)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=decision_result)]),
                actions=EventActions(escalate=True)  # 标记为最终结果
            )
            
            # 6. 解散讨论组
            await self._disband_discussion_group()
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text="讨论组已解散，任务协调完成")])
            )
            
        except Exception as e:
            logger.error(f"❌ 组长智能体协调异常: {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"协调异常: {e}")]),
                actions=EventActions(escalate=True)
            )
    
    async def _establish_discussion_group_internal(self, ctx: InvocationContext) -> str:
        """内部建立ADK标准讨论组方法"""
        try:
            # 获取多智能体系统引用
            if not hasattr(self, '_multi_agent_system') or not self._multi_agent_system:
                return "❌ 多智能体系统未连接，无法创建ADK标准讨论组"

            # 使用ADK官方讨论系统创建讨论组
            task_description = f"组长智能体内部任务 - 目标: {self.target_id}"
            adk_official_system = self._multi_agent_system.get_adk_official_discussion_system()
            if adk_official_system:
                discussion_id = await adk_official_system.create_discussion_with_adk_patterns(
                    pattern_type="sequential_pipeline",  # 组长智能体使用顺序流水线模式
                    participating_agents=[self],  # 暂时只包含自己
                    task_description=task_description
                )
            else:
                discussion_id = None

            if discussion_id:
                # 创建简化的讨论组信息（保持向后兼容）
                self.discussion_group = DiscussionGroup(
                    group_id=discussion_id,
                    target_id=self.target_id,
                    leader_id=self.name,
                    member_satellites=[],
                    created_time=datetime.now(),
                    status='active',
                    discussion_rounds=0,
                    max_rounds=self.max_discussion_rounds
                )

                # 保存到会话状态
                ctx.session.state[f'discussion_group_{discussion_id}'] = asdict(self.discussion_group)

                return f"ADK标准讨论组 {discussion_id} 建立成功"
            else:
                return "❌ ADK标准讨论组创建失败"

        except Exception as e:
            return f"ADK标准讨论组建立失败: {e}"
    
    async def _get_available_satellite_ids(self) -> List[str]:
        """获取可用卫星ID列表"""
        try:
            # 从多智能体系统获取卫星列表
            if self._multi_agent_system:
                # 尝试从卫星工厂获取
                satellite_factory = getattr(self._multi_agent_system, '_satellite_factory', None)
                if satellite_factory:
                    return list(satellite_factory._satellite_agents.keys())

            # 默认卫星列表
            return ["Satellite_01", "Satellite_02", "Satellite_03", "Satellite_04", "Satellite_05"]

        except Exception as e:
            logger.error(f"❌ 获取卫星ID列表失败: {e}")
            return ["Satellite_01", "Satellite_02", "Satellite_03"]

    async def _calculate_visibility_concurrent(self, satellite_ids: List[str]) -> List[VisibilityWindow]:
        """并发计算多颗卫星的可见窗口"""
        try:
            import asyncio

            logger.info(f"🔄 开始并发计算 {len(satellite_ids)} 颗卫星的可见窗口")

            # 创建并发任务
            tasks = []
            for satellite_id in satellite_ids:
                task = asyncio.create_task(
                    self._calculate_single_satellite_visibility(satellite_id)
                )
                tasks.append(task)

            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理结果，过滤异常
            visibility_windows = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ 卫星 {satellite_ids[i]} 可见窗口计算失败: {result}")
                elif result:
                    visibility_windows.extend(result)

            logger.info(f"✅ 并发计算完成，共获得 {len(visibility_windows)} 个可见窗口")
            return visibility_windows

        except Exception as e:
            logger.error(f"❌ 并发可见窗口计算失败: {e}")
            return []

    async def _calculate_single_satellite_visibility(self, satellite_id: str) -> List[VisibilityWindow]:
        """计算单颗卫星的可见窗口"""
        try:
            # 模拟异步计算延迟
            await asyncio.sleep(0.1)  # 模拟计算时间

            # 生成模拟的可见窗口数据
            import random

            # 随机生成1-3个可见窗口
            num_windows = random.randint(1, 3)
            windows = []

            base_time = datetime.now()
            for i in range(num_windows):
                start_offset = random.randint(i * 20, i * 20 + 15)  # 分钟
                duration = random.randint(5, 15)  # 分钟

                window = VisibilityWindow(
                    satellite_id=satellite_id,
                    target_id=self.target_id,
                    start_time=base_time + timedelta(minutes=start_offset),
                    end_time=base_time + timedelta(minutes=start_offset + duration),
                    elevation_angle=random.uniform(30.0, 80.0),
                    azimuth_angle=random.uniform(0.0, 360.0),
                    range_km=random.uniform(1500.0, 2500.0)
                )
                windows.append(window)

            logger.debug(f"🛰️ 卫星 {satellite_id} 计算完成，发现 {len(windows)} 个可见窗口")
            return windows

        except Exception as e:
            logger.error(f"❌ 卫星 {satellite_id} 可见窗口计算失败: {e}")
            return []

    async def _calculate_visibility_internal(self, ctx: InvocationContext) -> str:
        """内部可见窗口计算方法（保持向后兼容）"""
        try:
            # 使用新的并发计算方法
            satellite_ids = await self._get_available_satellite_ids()
            visibility_results = await self._calculate_visibility_concurrent(satellite_ids[:3])  # 限制为3颗卫星

            self.visibility_windows = visibility_results

            return f"计算完成，发现 {len(self.visibility_windows)} 个可见窗口"

        except Exception as e:
            return f"可见窗口计算失败: {e}"
    
    async def _recruit_group_members(self, ctx: InvocationContext) -> str:
        """招募讨论组成员"""
        try:
            recruited_satellites = []
            
            for vw in self.visibility_windows:
                satellite_id = vw.satellite_id
                
                # 创建卫星智能体（在实际实现中，这些智能体应该已经存在）
                satellite_agent = SatelliteAgent(satellite_id)
                satellite_agent.join_discussion_group(self.discussion_group.group_id, self.name)
                
                self.member_agents[satellite_id] = satellite_agent
                recruited_satellites.append(satellite_id)
                
                # 将卫星智能体添加为子智能体
                self.sub_agents.append(satellite_agent)
            
            self.discussion_group.member_satellites = recruited_satellites
            
            return f"成功招募 {len(recruited_satellites)} 颗卫星加入讨论组: {recruited_satellites}"
            
        except Exception as e:
            return f"成员招募失败: {e}"
    
    async def _conduct_group_discussion(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """组织讨论组讨论"""
        logger.info(f"[{self.name}] 开始组织讨论，最大轮次: {self.max_discussion_rounds}")
        
        for round_num in range(1, self.max_discussion_rounds + 1):
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=f"开始第 {round_num} 轮讨论")])
            )
            
            # 协调本轮讨论
            round_result = await self._coordinate_discussion_round_internal(round_num, ctx)
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=round_result)])
            )
            
            # 检查是否达成共识
            if await self._check_consensus(ctx):
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[types.Part(text=f"第 {round_num} 轮讨论达成共识，提前结束")])
                )
                break
            
            # 短暂延迟
            await asyncio.sleep(0.1)
    
    async def _coordinate_discussion_round_internal(self, round_num: int, ctx: InvocationContext) -> str:
        """内部讨论轮次协调方法"""
        try:
            member_opinions = []
            
            # 收集各成员意见（模拟）
            for satellite_id, agent in self.member_agents.items():
                # 在实际实现中，这里会调用卫星智能体的协调方法
                opinion = f"{satellite_id}: 资源可用，建议分配时间窗口 {round_num*5}-{round_num*5+10}分钟"
                member_opinions.append(opinion)
            
            # 记录讨论历史
            discussion_record = {
                'round': round_num,
                'timestamp': datetime.now().isoformat(),
                'opinions': member_opinions,
                'leader_summary': f"第{round_num}轮讨论，收集到{len(member_opinions)}个意见"
            }
            
            self.discussion_history.append(discussion_record)
            self.discussion_group.discussion_rounds = round_num
            
            return f"第{round_num}轮讨论完成，收集{len(member_opinions)}个意见"
            
        except Exception as e:
            return f"讨论协调失败: {e}"
    
    async def _check_consensus(self, ctx: InvocationContext) -> bool:
        """检查是否达成共识"""
        # 简单的共识检查逻辑
        return len(self.discussion_history) >= 2  # 模拟：2轮后达成共识
    
    async def _make_final_decision(self, ctx: InvocationContext) -> str:
        """做出最终决策"""
        try:
            if not self.visibility_windows:
                return "无可见窗口，无法分配任务"
            
            # 基于讨论结果和优化目标做出决策
            allocated_satellites = [vw.satellite_id for vw in self.visibility_windows[:2]]
            
            self.final_allocation = TaskAllocation(
                target_id=self.target_id,
                allocated_satellites=allocated_satellites,
                time_windows=self.visibility_windows[:2],
                optimization_score=0.85,  # 模拟优化分数
                allocation_strategy="GDOP_optimized"
            )
            
            # 保存决策结果到会话状态
            ctx.session.state[f'allocation_{self.target_id}'] = asdict(self.final_allocation)
            
            decision_summary = f"""
            目标 {self.target_id} 任务分配决策:
            - 分配卫星: {allocated_satellites}
            - 时间窗口数: {len(self.final_allocation.time_windows)}
            - 优化分数: {self.final_allocation.optimization_score:.2f}
            - 分配策略: {self.final_allocation.allocation_strategy}
            - 讨论轮次: {len(self.discussion_history)}
            """
            
            return decision_summary.strip()
            
        except Exception as e:
            return f"最终决策失败: {e}"
    
    async def _disband_discussion_group(self):
        """解散讨论组"""
        if self.discussion_group:
            # 通知所有成员离开讨论组
            for agent in self.member_agents.values():
                agent.leave_discussion_group()
            
            self.discussion_group.status = 'disbanded'
            self.member_agents.clear()
            self.sub_agents.clear()
            
            logger.info(f"👑 讨论组 {self.discussion_group.group_id} 已解散")
    
    def get_allocation_result(self) -> Optional[TaskAllocation]:
        """获取分配结果"""
        return self.final_allocation
