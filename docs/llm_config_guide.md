# 大模型配置和提示词管理指南

## 概述

本指南详细介绍如何在多智能体系统中统一管理大模型配置、API密钥和智能体提示词。系统采用配置文件集中管理的方式，支持多种大模型提供商和智能体角色的个性化配置。

## 配置文件结构

### 主配置文件: `config/config.yaml`

配置文件包含以下主要部分：

```yaml
llm:                    # 大模型配置
agent_prompts:          # 智能体提示词配置
```

## 大模型配置 (llm)

### 主要配置 (primary)

```yaml
llm:
  primary:
    provider: "google"              # 提供商
    model: "gemini-2.0-flash"       # 模型名称
    api_key_env: "GOOGLE_API_KEY"   # API密钥环境变量
    max_tokens: 4096                # 最大令牌数
    temperature: 0.7                # 温度参数
    timeout: 30                     # 超时时间
```

### 支持的提供商

| 提供商 | 配置值 | 环境变量 | 示例模型 |
|--------|--------|----------|----------|
| Google | `google` | `GOOGLE_API_KEY` | `gemini-2.0-flash` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4` |
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-sonnet-20240229` |
| Azure | `azure` | `AZURE_OPENAI_API_KEY` | `gpt-4` |

### 智能体特定配置 (agent_specific)

为不同类型的智能体配置专用模型：

```yaml
llm:
  agent_specific:
    simulation_scheduler:
      model: "gemini-2.0-flash"
      temperature: 0.3              # 较低温度，更稳定
      max_tokens: 8192              # 更大令牌限制
    
    leader_agents:
      model: "gemini-2.0-flash"
      temperature: 0.5              # 中等温度
      max_tokens: 4096
    
    satellite_agents:
      model: "gemini-1.5-flash"     # 轻量模型
      temperature: 0.2              # 低温度，注重准确性
      max_tokens: 2048
```

### 备用模型配置 (fallback)

配置备用模型以提高系统可靠性：

```yaml
llm:
  fallback:
    - provider: "openai"
      model: "gpt-4"
      api_key_env: "OPENAI_API_KEY"
    - provider: "anthropic"
      model: "claude-3-sonnet-20240229"
      api_key_env: "ANTHROPIC_API_KEY"
```

## 智能体提示词配置 (agent_prompts)

### 仿真调度智能体 (simulation_scheduler)

```yaml
agent_prompts:
  simulation_scheduler:
    system_prompt: |
      你是天基低轨预警系统的仿真调度智能体，负责整个多星多任务规划系统的协调和管理。
      
      ## 你的职责：
      1. **场景管理**: 管理STK仿真场景
      2. **滚动规划**: 执行周期性的任务规划
      3. **任务分发**: 将检测到的目标分配给最适合的卫星智能体
      4. **协调管理**: 创建和管理讨论组
      5. **结果收集**: 收集各智能体的规划结果
    
    user_prompt_template: |
      当前仿真时间: {current_time}
      规划周期: 第{planning_cycle}轮
      检测到的目标: {detected_targets}
      可用卫星: {available_satellites}
      
      请执行滚动规划并协调多智能体任务分配。
    
    few_shot_examples:
      - input: "检测到导弹目标，需要进行任务规划"
        output: "开始第1轮滚动规划，检测到1个导弹目标，分配给最近的3颗卫星进行跟踪"
```

### 卫星智能体 (satellite_agents)

```yaml
agent_prompts:
  satellite_agents:
    system_prompt: |
      你是卫星智能体，代表一颗具体的低轨道预警卫星。
      
      ## 你的身份：
      - 卫星ID: {satellite_id}
      - 轨道高度: 约1800公里
      - 载荷类型: 红外传感器、可见光相机
      
      ## 你的能力：
      1. **任务管理**: 接收、执行和报告任务状态
      2. **资源监控**: 监控电力、热控、载荷状态
      3. **协同决策**: 参与讨论组，与其他卫星协调
    
    user_prompt_template: |
      当前时间: {current_time}
      卫星位置: {satellite_position}
      资源状态: 电力{power_level}%, 热控{thermal_status}
      分配任务: {assigned_tasks}
      
      请评估任务可行性并提供执行建议。
```

### 组长智能体 (leader_agents)

```yaml
agent_prompts:
  leader_agents:
    system_prompt: |
      你是组长智能体，负责特定目标的多卫星协调和讨论组管理。
      
      ## 你的职责：
      1. **讨论组管理**: 创建和主持多卫星讨论组
      2. **任务协调**: 协调多颗卫星对同一目标的观测
      3. **决策制定**: 基于讨论结果制定最终的任务分配方案
      
      ## 协调原则：
      1. **GDOP最优**: 选择几何精度衰减因子最小的卫星组合
      2. **连续覆盖**: 确保目标跟踪的时间连续性
      3. **资源平衡**: 合理分配卫星资源，避免过载
```

### 通用配置 (common)

```yaml
agent_prompts:
  common:
    global_instructions: |
      ## 通用要求：
      1. 始终使用专业的航天和军事术语
      2. 提供具体的时间戳和坐标信息
      3. 考虑物理约束和技术限制
      4. 优先考虑任务成功率和系统安全
    
    error_handling: |
      当遇到错误或异常情况时：
      1. 立即报告问题的性质和严重程度
      2. 提供可能的原因分析
      3. 建议应急处理措施
    
    collaboration: |
      在多智能体协作中：
      1. 主动分享关键信息
      2. 尊重其他智能体的专业判断
      3. 寻求共识，避免无谓争论
```

## API密钥管理

### 环境变量配置

1. **复制模板文件**:
   ```bash
   cp .env.template .env
   ```

2. **编辑 .env 文件**:
   ```bash
   # Google Gemini API密钥
   GOOGLE_API_KEY=your_actual_api_key_here
   
   # OpenAI API密钥（备用）
   OPENAI_API_KEY=your_openai_api_key_here
   
   # Anthropic Claude API密钥（备用）
   ANTHROPIC_API_KEY=your_anthropic_api_key_here
   ```

3. **加载环境变量**:
   ```bash
   # Linux/Mac
   source .env
   
   # Windows
   # 手动设置环境变量或使用python-dotenv
   ```

### 安全最佳实践

1. **不要在代码中硬编码API密钥**
2. **使用环境变量存储敏感信息**
3. **将 .env 文件添加到 .gitignore**
4. **定期轮换API密钥**
5. **使用最小权限原则**

## 配置管理器使用

### 基本用法

```python
from src.utils.llm_config_manager import get_llm_config_manager

# 获取配置管理器
config_mgr = get_llm_config_manager("config/config.yaml")

# 获取大模型配置
llm_config = config_mgr.get_llm_config('simulation_scheduler')
print(f"模型: {llm_config.model}")
print(f"温度: {llm_config.temperature}")

# 获取提示词配置
prompt_config = config_mgr.get_agent_prompt_config('satellite_agents')
print(f"系统提示词长度: {len(prompt_config.system_prompt)}")

# 格式化提示词
system_prompt = config_mgr.format_system_prompt(
    'satellite_agents',
    satellite_id="SAT_001",
    current_time="2025-01-27T12:00:00"
)
```

### 在智能体中使用

```python
class SatelliteAgent(BaseAgent):
    def __init__(self, satellite_id: str, config_path: str = None):
        # 获取配置管理器
        llm_config_mgr = get_llm_config_manager(config_path)
        
        # 获取模型配置
        llm_config = llm_config_mgr.get_llm_config('satellite_agents')
        
        # 格式化系统提示词
        system_prompt = llm_config_mgr.format_system_prompt(
            'satellite_agents',
            satellite_id=satellite_id,
            current_time=datetime.now().isoformat()
        )
        
        # 初始化智能体
        super().__init__(
            name=f"Agent_{satellite_id}",
            model=llm_config.model,
            instruction=system_prompt
        )
```

## 配置验证

### 使用验证脚本

```bash
# 运行配置验证
python scripts/validate_config.py
```

验证内容包括：
- API密钥配置检查
- 配置文件语法验证
- 大模型配置完整性
- 提示词配置验证
- 提示词格式化测试

### 手动验证

```python
from src.utils.llm_config_manager import get_llm_config_manager

config_mgr = get_llm_config_manager()

# 验证配置
if config_mgr.validate_config():
    print("✅ 配置验证通过")
else:
    print("❌ 配置验证失败")
```

## Web界面管理

### 访问配置管理页面

1. 启动ADK开发UI:
   ```bash
   python start_adk_ui.py
   ```

2. 访问配置管理页面:
   ```
   http://localhost:8080/config
   ```

### 功能特性

- **配置概览**: 显示主要模型、API密钥状态等
- **大模型配置**: 查看主要配置、智能体特定配置、备用模型
- **提示词配置**: 查看各智能体的提示词统计信息
- **性能配置**: 查看并发、缓存等性能设置
- **安全配置**: 查看内容过滤、安全设置等

## 故障排除

### 常见问题

1. **API密钥未配置**:
   ```
   ❌ 环境变量 GOOGLE_API_KEY 未设置
   ```
   解决方案: 检查 .env 文件和环境变量设置

2. **配置文件语法错误**:
   ```
   ❌ 配置文件加载失败: YAML语法错误
   ```
   解决方案: 检查YAML文件缩进和语法

3. **提示词格式化失败**:
   ```
   ⚠️ 提示词格式化缺少参数: satellite_id
   ```
   解决方案: 检查提示词模板中的占位符

### 调试技巧

1. **启用详细日志**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **检查配置加载**:
   ```python
   config_mgr = get_llm_config_manager()
   print(config_mgr.config)  # 打印原始配置
   ```

3. **测试API连接**:
   ```python
   llm_config = config_mgr.get_llm_config()
   print(f"API密钥: {llm_config.api_key[:10]}...")  # 只显示前10位
   ```

## 最佳实践

### 配置组织

1. **分层配置**: 使用主要配置 + 智能体特定配置
2. **环境分离**: 开发、测试、生产环境使用不同配置
3. **版本控制**: 配置文件纳入版本控制，但排除敏感信息

### 提示词设计

1. **角色明确**: 清晰定义智能体的角色和职责
2. **上下文丰富**: 提供充分的背景信息和约束条件
3. **格式统一**: 使用一致的提示词结构和格式
4. **示例引导**: 提供few-shot示例指导模型行为

### 安全考虑

1. **密钥轮换**: 定期更换API密钥
2. **访问控制**: 限制配置文件的访问权限
3. **审计日志**: 记录配置变更和API调用
4. **内容过滤**: 启用适当的安全过滤机制

---

**配置管理是多智能体系统的核心基础，正确的配置能够显著提升系统的性能、可靠性和安全性。**
