# 基于ADK框架的多智能体协同多星多任务规划系统架构设计

## 1. 系统总体架构

### 1.1 架构概述
本系统采用基于Google ADK开源框架的分布式多智能体架构，实现无中心节点的卫星星座任务规划。系统包含三类核心智能体：

- **仿真调度智能体 (SimulationSchedulerAgent)**: 基于ADK的LlmAgent，负责STK场景管理和滚动规划
- **卫星智能体 (SatelliteAgent)**: 基于ADK的BaseAgent，每颗卫星对应一个智能体
- **组长智能体 (LeaderAgent)**: 基于ADK的LlmAgent，负责讨论组协调和决策

### 1.2 智能体层次结构
```
仿真调度智能体 (Root Agent)
├── 组长智能体1 (Leader for Target1)
│   ├── 卫星智能体1 (Satellite_01)
│   ├── 卫星智能体2 (Satellite_02)
│   └── 卫星智能体N (Satellite_0N)
├── 组长智能体2 (Leader for Target2)
│   └── ...
└── 独立卫星智能体 (未分配到讨论组)
```

## 2. 智能体详细设计

### 2.1 仿真调度智能体 (SimulationSchedulerAgent)
**基类**: ADK LlmAgent
**职责**:
- STK仿真场景创建与配置
- 滚动规划周期管理
- 元任务信息集生成
- 导弹目标检测与分发
- 规划结果收集与可视化

**核心功能**:
- `create_stk_scenario()`: 创建STK仿真场景
- `generate_meta_tasks()`: 生成元任务信息集
- `distribute_tasks()`: 分发任务给最近卫星
- `collect_planning_results()`: 收集规划结果
- `generate_gantt_charts()`: 生成甘特图

### 2.2 卫星智能体 (SatelliteAgent)
**基类**: ADK BaseAgent
**职责**:
- 任务列表管理（执行中/未执行）
- 与组长协调决策
- 资源状态维护
- 优化目标计算

**核心属性**:
- `satellite_id`: 卫星ID（与STK中卫星ID一致）
- `memory_module`: 记忆模块（基于ADK Session State）
- `task_manager`: 任务管理器
- `resource_status`: 资源状态

**核心功能**:
- `receive_task_info()`: 接收元任务信息
- `coordinate_with_leader()`: 与组长协调
- `calculate_optimization_metrics()`: 计算优化指标
- `update_task_status()`: 更新任务状态

### 2.3 组长智能体 (LeaderAgent)
**基类**: ADK LlmAgent
**职责**:
- 讨论组建立与管理
- 可见窗口计算协调
- 任务分配决策
- 讨论结果汇总

**核心功能**:
- `establish_discussion_group()`: 建立讨论组
- `calculate_visibility_windows()`: 计算可见窗口
- `coordinate_task_allocation()`: 协调任务分配
- `make_final_decision()`: 做出最终决策

## 3. 协同机制设计

### 3.1 任务驱动协同模式
基于ADK的LLM-Driven Delegation机制：
- 卫星接收导弹目标信息后自动成为组长
- 使用`transfer_to_agent()`进行智能体间转移
- 通过Session State共享任务信息

### 3.2 分布式决策机制
基于ADK的Multi-Agent Coordination：
- 使用Shared Session State进行状态共享
- 通过AgentTool实现智能体间显式调用
- 采用Coordinator/Dispatcher模式进行任务分发

### 3.3 消息传递机制
- **状态共享**: 使用ADK Session State存储共享信息
- **事件通信**: 通过ADK Event系统传递消息
- **工具调用**: 使用AgentTool包装智能体为工具

## 4. 优化目标集成

### 4.1 GDOP跟踪精度计算
```python
def calculate_gdop(satellite_positions, target_position, time_window):
    """计算几何精度衰减因子"""
    # 实现GDOP计算公式
    pass
```

### 4.2 资源调度性评估
```python
def evaluate_schedulability(satellite_resources, task_requirements):
    """评估资源调度性"""
    # 实现调度性评估算法
    pass
```

### 4.3 鲁棒性指标
```python
def calculate_robustness(current_plan, disturbance_scenarios):
    """计算规划方案鲁棒性"""
    # 实现鲁棒性评估算法
    pass
```

## 5. 配置管理

### 5.1 智能体配置
```yaml
multi_agent_system:
  simulation_scheduler:
    model: "gemini-2.0-flash"
    max_discussion_rounds: 5
    rolling_planning_interval: 300  # 秒
  
  satellite_agents:
    memory_timeout: 3600  # 秒
    task_queue_size: 10
    
  leader_agents:
    discussion_timeout: 600  # 秒
    max_group_size: 8
```

### 5.2 协同配置
```yaml
coordination:
  message_passing:
    timeout: 30  # 秒
    retry_attempts: 3
  
  decision_making:
    consensus_threshold: 0.8
    voting_mechanism: "weighted"
```

## 6. 系统集成

### 6.1 与STK接口集成
- 复用现有STK管理器
- 集成可见窗口计算器
- 利用导弹管理器

### 6.2 与元任务管理集成
- 复用元任务管理器
- 集成甘特图生成器
- 利用时间管理器

### 6.3 大模型API集成
- 使用ADK的litellm集成
- 支持多种大模型后端
- 统一API调用接口

## 7. 部署架构

### 7.1 本地部署
- 单机多智能体运行
- 共享STK实例
- 本地文件系统存储

### 7.2 分布式部署（未来扩展）
- 基于ADK的Agent Engine
- 云端智能体协调
- 分布式状态管理

## 8. 下一步实现计划

1. 实现仿真调度智能体基础框架
2. 实现卫星智能体基类
3. 实现组长智能体协调机制
4. 集成优化目标计算
5. 完善协同机制
6. 系统测试与验证
