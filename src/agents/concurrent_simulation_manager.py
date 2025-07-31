#!/usr/bin/env python3
"""
并发仿真管理器
实现组员智能体的并发仿真计算，提升仿真速度
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

logger = logging.getLogger(__name__)


class ConcurrentSimulationManager(BaseAgent):
    """
    并发仿真管理器

    在迭代优化过程中管理组员智能体的并发仿真计算，
    实现parallel_fanout模式的性能优势，同时保持ADK框架的设计原则。
    """

    def __init__(self, name: str, member_agents: List[BaseAgent], max_concurrent: int = 10):
        """
        初始化并发仿真管理器

        Args:
            name: 管理器名称
            member_agents: 参与并发仿真的组员智能体列表
            max_concurrent: 最大并发数量
        """
        super().__init__(
            name=name,
            description=f"并发仿真管理器，管理{len(member_agents)}个组员智能体的并发仿真计算"
        )

        # 使用 object.__setattr__ 来设置属性，避免 Pydantic 验证
        object.__setattr__(self, 'member_agents', member_agents)
        object.__setattr__(self, 'max_concurrent', max_concurrent)
        object.__setattr__(self, 'simulation_timeout', 300)  # 5分钟超时

        logger.info(f"✅ 并发仿真管理器初始化完成: {name}")
        logger.info(f"   管理组员数量: {len(member_agents)}")
        logger.info(f"   最大并发数: {max_concurrent}")
    
    async def _run_async_impl(self, ctx: InvocationContext):
        """执行并发仿真管理"""
        try:
            logger.info(f"🚀 并发仿真管理器开始执行: {self.name}")
            
            # 获取当前迭代的优化参数
            optimization_params = ctx.session.state.get('current_optimization', {})
            iteration_count = ctx.session.state.get('iteration_count', 0)
            
            logger.info(f"📋 第 {iteration_count} 轮迭代并发仿真")
            logger.info(f"   参与智能体: {len(self.member_agents)}个")
            logger.info(f"   优化参数: {list(optimization_params.keys()) if optimization_params else '无'}")
            
            # 执行并发仿真
            simulation_results = await self._execute_concurrent_simulation(
                optimization_params, ctx
            )
            
            # 汇聚和分析结果
            aggregated_result = await self._aggregate_simulation_results(
                simulation_results, ctx
            )
            
            # 保存结果到Session State
            ctx.session.state['concurrent_simulation_result'] = aggregated_result
            ctx.session.state['simulation_completed'] = True
            
            # 生成结果事件
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(
                    text=f"并发仿真完成 - 参与智能体: {len(self.member_agents)}个, "
                         f"成功率: {aggregated_result.get('success_rate', 0):.1%}, "
                         f"平均性能: {aggregated_result.get('average_performance', 0):.3f}"
                )])
            )
            
            logger.info(f"✅ 并发仿真管理器执行完成: {self.name}")
            
        except Exception as e:
            logger.error(f"❌ 并发仿真管理器执行失败: {e}")
            
            # 保存错误信息
            ctx.session.state['concurrent_simulation_result'] = {
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(
                    text=f"并发仿真失败: {e}"
                )]),
                actions=EventActions(escalate=True)
            )
    
    async def _execute_concurrent_simulation(self, optimization_params: Dict[str, Any],
                                           ctx: InvocationContext) -> List[Dict[str, Any]]:
        """执行并发仿真计算"""
        try:
            logger.info(f"🔄 开始并发仿真计算 - 组员数量: {len(self.member_agents)}")

            # 清除之前的仿真结果
            for member in self.member_agents:
                ctx.session.state.pop(f'member_{member.name}_simulation', None)

            # 创建仿真任务
            simulation_tasks = []
            for i, member in enumerate(self.member_agents):
                logger.info(f"🛰️ 启动组员 {member.name} 的仿真任务")
                task = asyncio.create_task(
                    self._execute_member_simulation(member, optimization_params, ctx, i)
                )
                simulation_tasks.append(task)

            # 等待所有仿真任务完成
            logger.info(f"⏳ 等待 {len(simulation_tasks)} 个并发仿真任务完成...")
            completed_results = await asyncio.gather(*simulation_tasks, return_exceptions=True)

            # 处理完成的结果
            successful_results = []
            for i, result in enumerate(completed_results):
                if isinstance(result, Exception):
                    logger.warning(f"⚠️ 组员 {self.member_agents[i].name} 仿真任务异常: {result}")
                else:
                    successful_results.append(result)

            # 收集所有结果
            all_results = []
            for member in self.member_agents:
                member_result = ctx.session.state.get(f'member_{member.name}_simulation', {})
                if member_result:
                    all_results.append(member_result)
                else:
                    logger.warning(f"⚠️ 组员 {member.name} 没有仿真结果")

            logger.info(f"✅ 并发仿真计算完成，收集到 {len(all_results)} 个结果")
            logger.info(f"   成功任务: {len(successful_results)}/{len(simulation_tasks)}")

            return all_results

        except Exception as e:
            logger.error(f"❌ 并发仿真计算失败: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _execute_member_simulation(self, member: BaseAgent, optimization_params: Dict[str, Any],
                                       ctx: InvocationContext, index: int) -> Dict[str, Any]:
        """执行单个组员的仿真计算"""
        try:
            logger.info(f"🛰️ 组员 {member.name} 开始仿真计算")

            # 构建仿真提示词
            simulation_prompt = self._build_simulation_prompt(member, optimization_params, ctx)

            # 执行LLM推理进行仿真计算
            if hasattr(member, 'generate_litellm_response'):
                try:
                    start_time = datetime.now()

                    logger.info(f"🧠 组员 {member.name} 开始LLM推理仿真...")

                    # 执行仿真计算
                    simulation_response = await asyncio.wait_for(
                        member.generate_litellm_response(simulation_prompt, temperature=0.3),
                        timeout=self.simulation_timeout
                    )

                    execution_time = (datetime.now() - start_time).total_seconds()

                    logger.info(f"✅ 组员 {member.name} LLM推理完成，耗时: {execution_time:.2f}s，响应长度: {len(simulation_response)}")

                    # 解析仿真结果
                    simulation_result = self._parse_simulation_result(
                        member, simulation_response, execution_time
                    )

                    logger.info(f"✅ 组员 {member.name} 仿真完成，GDOP贡献: {simulation_result.get('simulation_data', {}).get('gdop_contribution', 0):.3f}")

                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ 组员 {member.name} 仿真超时（{self.simulation_timeout}s）")
                    simulation_result = self._create_timeout_result(member)

                except Exception as e:
                    logger.error(f"❌ 组员 {member.name} 仿真失败: {e}")
                    simulation_result = self._create_error_result(member, str(e))
            else:
                # 模拟仿真结果
                simulation_result = self._create_mock_simulation_result(member, optimization_params)
                logger.info(f"🔧 组员 {member.name} 使用模拟仿真")

            # 保存到Session State
            ctx.session.state[f'member_{member.name}_simulation'] = simulation_result

            return simulation_result

        except Exception as e:
            logger.error(f"❌ 组员 {member.name} 仿真执行异常: {e}")
            import traceback
            traceback.print_exc()
            return self._create_error_result(member, str(e))
    
    def _build_simulation_prompt(self, member: BaseAgent, optimization_params: Dict[str, Any], 
                               ctx: InvocationContext) -> str:
        """构建仿真计算提示词"""
        iteration_count = ctx.session.state.get('iteration_count', 0)
        task_description = ctx.session.state.get('iterative_task', {}).get('task_description', '未知任务')
        
        return f"""
你是卫星智能体 {getattr(member, 'satellite_id', member.name)}，正在参与第 {iteration_count} 轮迭代优化的并发仿真计算。

任务描述: {task_description}

当前优化参数:
{self._format_optimization_params(optimization_params)}

请基于你的具身状态（轨道、传感器、资源）进行仿真计算：

1. 分析当前优化参数对你的影响
2. 计算预期的性能指标：
   - GDOP贡献值 (越小越好)
   - 覆盖率贡献 (0-1)
   - 资源利用率 (0-1)
3. 评估可行性和风险
4. 提供具体的数值结果

请以JSON格式输出结果：
{{
    "gdop_contribution": 数值,
    "coverage_contribution": 数值,
    "resource_utilization": 数值,
    "feasibility_score": 数值,
    "risk_assessment": "低/中/高",
    "performance_summary": "简要说明"
}}
"""
    
    def _format_optimization_params(self, params: Dict[str, Any]) -> str:
        """格式化优化参数"""
        if not params:
            return "- 无特定优化参数"
        
        formatted = []
        for key, value in params.items():
            formatted.append(f"- {key}: {value}")
        return '\n'.join(formatted)
    
    def _parse_simulation_result(self, member: BaseAgent, response: str, 
                               execution_time: float) -> Dict[str, Any]:
        """解析仿真结果"""
        try:
            import json
            import re
            
            # 尝试提取JSON
            json_match = re.search(r'\{[^}]*\}', response, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
            else:
                # 如果没有JSON，创建默认结果
                result_data = {
                    "gdop_contribution": 1.0,
                    "coverage_contribution": 0.5,
                    "resource_utilization": 0.6,
                    "feasibility_score": 0.7,
                    "risk_assessment": "中",
                    "performance_summary": "解析失败，使用默认值"
                }
            
            return {
                'agent_name': member.name,
                'agent_id': getattr(member, 'satellite_id', member.name),
                'success': True,
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat(),
                'simulation_data': result_data,
                'raw_response': response
            }
            
        except Exception as e:
            logger.warning(f"⚠️ 解析 {member.name} 仿真结果失败: {e}")
            return self._create_error_result(member, f"结果解析失败: {e}")
    
    def _create_mock_simulation_result(self, member: BaseAgent, 
                                     optimization_params: Dict[str, Any]) -> Dict[str, Any]:
        """创建模拟仿真结果"""
        import random
        
        # 基于智能体名称生成一致的随机结果
        random.seed(hash(member.name) % 1000)
        
        return {
            'agent_name': member.name,
            'agent_id': getattr(member, 'satellite_id', member.name),
            'success': True,
            'execution_time': random.uniform(1.0, 3.0),
            'timestamp': datetime.now().isoformat(),
            'simulation_data': {
                'gdop_contribution': random.uniform(0.5, 1.5),
                'coverage_contribution': random.uniform(0.4, 0.9),
                'resource_utilization': random.uniform(0.3, 0.8),
                'feasibility_score': random.uniform(0.6, 0.95),
                'risk_assessment': random.choice(['低', '中', '高']),
                'performance_summary': f"模拟仿真结果 - {member.name}"
            },
            'is_mock': True
        }
    
    def _create_timeout_result(self, member: BaseAgent) -> Dict[str, Any]:
        """创建超时结果"""
        return {
            'agent_name': member.name,
            'agent_id': getattr(member, 'satellite_id', member.name),
            'success': False,
            'error': 'timeout',
            'execution_time': self.simulation_timeout,
            'timestamp': datetime.now().isoformat()
        }
    
    def _create_error_result(self, member: BaseAgent, error_msg: str) -> Dict[str, Any]:
        """创建错误结果"""
        return {
            'agent_name': member.name,
            'agent_id': getattr(member, 'satellite_id', member.name),
            'success': False,
            'error': error_msg,
            'execution_time': 0.0,
            'timestamp': datetime.now().isoformat()
        }
    
    async def _aggregate_simulation_results(self, results: List[Dict[str, Any]], 
                                          ctx: InvocationContext) -> Dict[str, Any]:
        """汇聚仿真结果"""
        try:
            logger.info(f"📊 开始汇聚 {len(results)} 个仿真结果")
            
            successful_results = [r for r in results if r.get('success', False)]
            success_rate = len(successful_results) / len(results) if results else 0
            
            if not successful_results:
                return {
                    'success': False,
                    'success_rate': 0.0,
                    'error': '所有仿真都失败了',
                    'timestamp': datetime.now().isoformat()
                }
            
            # 计算聚合指标
            total_gdop = sum(r['simulation_data']['gdop_contribution'] 
                           for r in successful_results if 'simulation_data' in r)
            avg_coverage = sum(r['simulation_data']['coverage_contribution'] 
                             for r in successful_results if 'simulation_data' in r) / len(successful_results)
            avg_resource = sum(r['simulation_data']['resource_utilization'] 
                             for r in successful_results if 'simulation_data' in r) / len(successful_results)
            avg_feasibility = sum(r['simulation_data']['feasibility_score'] 
                                for r in successful_results if 'simulation_data' in r) / len(successful_results)
            
            # 计算综合性能分数
            performance_score = self._calculate_performance_score(
                total_gdop, avg_coverage, avg_resource, avg_feasibility
            )
            
            aggregated = {
                'success': True,
                'success_rate': success_rate,
                'participant_count': len(results),
                'successful_count': len(successful_results),
                'aggregated_metrics': {
                    'total_gdop': total_gdop,
                    'average_coverage': avg_coverage,
                    'average_resource_utilization': avg_resource,
                    'average_feasibility': avg_feasibility,
                    'performance_score': performance_score
                },
                'individual_results': successful_results,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✅ 仿真结果汇聚完成")
            logger.info(f"   成功率: {success_rate:.1%}")
            logger.info(f"   综合性能分数: {performance_score:.3f}")
            
            return aggregated
            
        except Exception as e:
            logger.error(f"❌ 仿真结果汇聚失败: {e}")
            return {
                'success': False,
                'error': f'结果汇聚失败: {e}',
                'timestamp': datetime.now().isoformat()
            }
    
    def _calculate_performance_score(self, gdop: float, coverage: float, 
                                   resource: float, feasibility: float) -> float:
        """计算综合性能分数"""
        try:
            # 权重设置
            weights = {
                'gdop': 0.3,        # GDOP权重30% (越小越好)
                'coverage': 0.3,    # 覆盖率权重30%
                'resource': 0.2,    # 资源利用率权重20%
                'feasibility': 0.2  # 可行性权重20%
            }
            
            # 归一化GDOP (越小越好，转换为越大越好)
            gdop_score = max(0, min(1, (3.0 - gdop) / 2.0))
            
            # 计算加权总分
            total_score = (
                weights['gdop'] * gdop_score +
                weights['coverage'] * coverage +
                weights['resource'] * resource +
                weights['feasibility'] * feasibility
            )
            
            return min(1.0, max(0.0, total_score))
            
        except Exception as e:
            logger.error(f"❌ 性能分数计算失败: {e}")
            return 0.5
