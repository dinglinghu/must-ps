# 基于多智能体协同的多星多任务规划系统

## 系统概述

本系统是基于Google ADK开源框架实现的分布式多智能体协同系统，专门用于天基低轨预警系统的多星多任务规划。系统采用无中心节点的分布式架构，通过智能体间的协同决策实现最优的任务分配和资源调度。

### 核心特性

- **分布式多智能体架构**: 基于ADK框架的无中心节点设计
- **智能协同决策**: 通过讨论组机制实现智能体间的协调
- **多目标优化**: 集成GDOP、调度性、鲁棒性三大优化目标
- **滚动规划**: 支持动态任务规划和实时调整
- **可视化输出**: 自动生成协调结果报告和分析图表

## 系统架构

### 智能体层次结构

```
仿真调度智能体 (SimulationSchedulerAgent)
├── 组长智能体1 (LeaderAgent for Target1)
│   ├── 卫星智能体1 (SatelliteAgent_01)
│   ├── 卫星智能体2 (SatelliteAgent_02)
│   └── 卫星智能体N (SatelliteAgent_0N)
├── 组长智能体2 (LeaderAgent for Target2)
│   └── ...
└── 独立卫星智能体 (未分配到讨论组)
```

### 核心组件

1. **仿真调度智能体 (SimulationSchedulerAgent)**
   - 基于ADK的LlmAgent
   - 负责STK场景管理和滚动规划
   - 元任务生成和分发
   - 结果收集和报告生成

2. **卫星智能体 (SatelliteAgent)**
   - 基于ADK的BaseAgent
   - 每颗卫星对应一个智能体实例
   - 任务管理和资源状态维护
   - 与组长协调决策

3. **组长智能体 (LeaderAgent)**
   - 基于ADK的LlmAgent
   - 负责讨论组管理和协调
   - 可见窗口计算和任务分配
   - 最终决策制定

4. **协调管理器 (CoordinationManager)**
   - 智能体间消息传递
   - 状态共享和同步
   - 协调会话管理

5. **优化计算器 (OptimizationCalculator)**
   - GDOP跟踪精度计算
   - 资源调度性评估
   - 鲁棒性指标分析

## 安装和配置

### 环境要求

- Python 3.8+
- Google ADK框架 (可选，系统提供模拟实现)
- STK软件 (用于仿真场景)
- 相关Python依赖包

### 安装步骤

1. **克隆项目**
   ```bash
   git clone <repository_url>
   cd data-generate
   ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置ADK框架** (可选)
   ```bash
   # 如果有ADK框架访问权限
   pip install google-adk
   ```

4. **配置大模型API**
   ```bash
   # 设置API密钥环境变量
   export GOOGLE_API_KEY="your_api_key"
   ```

### 配置文件

主要配置文件位于 `config/config.yaml`，包含以下配置项：

- **多智能体系统配置**: 智能体参数、协调机制、优化目标
- **STK接口配置**: 星座参数、载荷配置、导弹设置
- **大模型API配置**: 模型选择、API参数、备用模型
- **输出配置**: 文件格式、目录结构、可视化参数

## 使用方法

### 基本运行

```bash
# 运行多智能体系统
python src/main_multi_agent.py
```

### 测试验证

```bash
# 运行测试用例
python tests/test_multi_agent_system.py
```

### 自定义配置

1. **修改星座配置**
   ```yaml
   constellation:
     total_satellites: 24
     planes: 6
     satellites_per_plane: 4
   ```

2. **调整智能体参数**
   ```yaml
   multi_agent_system:
     leader_agents:
       max_discussion_rounds: 5
       discussion_timeout: 600
   ```

3. **设置优化权重**
   ```yaml
   optimization:
     gdop:
       weight: 0.4
     schedulability:
       weight: 0.3
     robustness:
       weight: 0.3
   ```

## 工作流程

### 1. 系统初始化
- 加载配置文件
- 初始化核心组件
- 创建仿真调度智能体

### 2. 滚动规划循环
- 检测导弹目标
- 生成元任务信息集
- 分发任务给最近卫星

### 3. 讨论组协调
- 创建组长智能体
- 招募相关卫星智能体
- 组织多轮讨论决策

### 4. 任务分配优化
- 计算可见窗口
- 评估优化指标
- 制定最终分配方案

### 5. 结果输出
- 生成甘特图
- 保存协调结果
- 输出系统报告

## 输出文件

系统运行后会在 `output/` 目录下生成以下文件：

```
output/
└── simulation_YYYYMMDD_HHMMSS/
    ├── meta_tasks/              # 元任务信息
    ├── gantt_charts/            # 甘特图文件
    ├── coordination_results/    # 协调结果
    ├── agent_logs/              # 智能体日志
    └── simulation_report.txt    # 仿真报告
```

### 主要输出文件说明

- **甘特图**: 可视化任务分配时间线
- **协调结果**: JSON格式的详细分配方案
- **仿真报告**: 系统运行统计和性能指标
- **智能体日志**: 各智能体的决策过程记录

## 优化目标

### 1. GDOP跟踪精度
- 最小化几何精度衰减因子
- 提高目标跟踪精度
- 优化卫星几何配置

### 2. 资源调度性
- 最大化资源利用率
- 减少任务冲突
- 平衡负载分布

### 3. 系统鲁棒性
- 增强故障容忍能力
- 提高适应性
- 保证服务连续性

## 扩展开发

### 添加新的智能体类型

1. 继承ADK的BaseAgent或LlmAgent
2. 实现 `_run_async_impl` 方法
3. 注册到协调管理器

### 自定义优化算法

1. 扩展OptimizationCalculator类
2. 实现新的优化指标计算
3. 更新综合评分函数

### 集成新的仿真环境

1. 实现新的接口适配器
2. 扩展元任务管理器
3. 更新配置文件结构

## 故障排除

### 常见问题

1. **ADK框架未安装**
   - 系统会自动使用模拟实现
   - 功能完整，仅缺少真实的LLM调用

2. **STK连接失败**
   - 检查STK软件是否运行
   - 验证COM接口配置

3. **大模型API调用失败**
   - 检查API密钥配置
   - 验证网络连接
   - 使用备用模型

### 调试模式

```bash
# 启用详细日志
export LOG_LEVEL=DEBUG
python src/main_multi_agent.py
```

## 性能优化

### 系统调优建议

1. **智能体数量**: 根据硬件资源调整卫星数量
2. **讨论轮次**: 平衡决策质量和运行时间
3. **消息队列**: 调整队列大小和超时时间
4. **优化权重**: 根据任务需求调整目标权重

### 监控指标

- 智能体响应时间
- 协调成功率
- 资源利用率
- 系统吞吐量

## 贡献指南

欢迎贡献代码和改进建议！请遵循以下步骤：

1. Fork项目仓库
2. 创建功能分支
3. 提交代码更改
4. 运行测试用例
5. 提交Pull Request

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 联系方式

如有问题或建议，请通过以下方式联系：

- 项目Issues: <repository_issues_url>
- 邮箱: <contact_email>
- 文档: <documentation_url>

---

*基于多智能体协同的多星多任务规划系统 v1.0.0*
