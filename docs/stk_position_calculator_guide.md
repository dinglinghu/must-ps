# STK位置计算器集成指南

## 📖 概述

STK位置计算器是一个基于STK COM接口的真实卫星位置计算模块，用于替换系统中原有的模拟位置计算方法，提供精确的卫星位置和距离计算功能。

## 🎯 主要功能

### ✅ 已实现功能

1. **真实卫星位置获取**
   - 通过STK COM接口获取卫星的真实位置
   - 支持经纬度坐标和笛卡尔坐标
   - 自动坐标系转换

2. **精确距离计算**
   - 3D空间距离计算
   - 卫星与目标之间的真实距离
   - 支持批量距离计算

3. **最近卫星查找**
   - 基于真实位置的最近卫星排序
   - 支持指定返回卫星数量
   - 距离结果详细信息

4. **系统集成**
   - 与现有STK管理器集成
   - 回退机制保证系统稳定性
   - 透明替换模拟计算方法

## 🔧 技术架构

### 核心组件

```
STKPositionCalculator
├── STK COM接口连接
├── 位置数据获取
├── 坐标系转换
├── 距离计算
└── 最近卫星查找
```

### 数据结构

```python
@dataclass
class SatellitePosition:
    satellite_id: str
    time: datetime
    latitude: float      # 纬度（度）
    longitude: float     # 经度（度）
    altitude: float      # 高度（公里）
    x: float            # 笛卡尔坐标X（公里）
    y: float            # 笛卡尔坐标Y（公里）
    z: float            # 笛卡尔坐标Z（公里）

@dataclass
class DistanceResult:
    distance_km: float
    satellite_position: SatellitePosition
    target_position: Dict[str, float]
    calculation_time: datetime
    calculation_method: str
```

## 🚀 使用方法

### 1. 基本使用

```python
from src.stk_interface.stk_position_calculator import get_stk_position_calculator

# 获取STK位置计算器实例
calculator = get_stk_position_calculator()

# 获取卫星位置
position = calculator.get_satellite_position("SAT_001", datetime.now())
if position:
    print(f"卫星位置: ({position.latitude}°, {position.longitude}°, {position.altitude}km)")
```

### 2. 距离计算

```python
# 定义目标位置
target_position = {
    'lat': 39.9042,  # 北京纬度
    'lon': 116.4074, # 北京经度
    'alt': 0.0       # 地面高度
}

# 计算距离
distance_result = calculator.calculate_distance_to_target(
    "SAT_001", target_position, datetime.now()
)

if distance_result:
    print(f"距离: {distance_result.distance_km:.1f} km")
```

### 3. 查找最近卫星

```python
# 卫星列表
satellite_ids = ["SAT_001", "SAT_002", "SAT_003"]

# 查找最近的3颗卫星
nearest_satellites = calculator.find_nearest_satellites(
    satellite_ids, target_position, datetime.now(), count=3
)

for result in nearest_satellites:
    print(f"{result.satellite_position.satellite_id}: {result.distance_km:.1f} km")
```

## 🔗 系统集成

### 已集成的组件

1. **导弹目标分发器** (`missile_target_distributor.py`)
   - 使用真实卫星位置进行目标分配
   - 精确的距离计算

2. **仿真调度智能体** (`simulation_scheduler_agent.py`)
   - 基于真实位置的最近卫星查找
   - 改进的任务调度算法

3. **卫星智能体** (`satellite_agent.py`)
   - 真实位置获取方法
   - STK位置数据接口

### 集成效果

#### ✅ 改进前（模拟位置）
- 使用哈希函数生成模拟位置
- 简化的2D距离计算
- 位置精度低，影响任务分配

#### ✅ 改进后（STK真实位置）
- 从STK获取真实卫星位置
- 精确的3D空间距离计算
- 高精度位置数据，优化任务分配

## 🛡️ 回退机制

系统设计了多层回退机制确保稳定性：

### 1. STK连接回退
```
STK COM接口 → 卫星智能体位置方法 → 模拟位置
```

### 2. 位置获取回退
```
LLA Position → Cartesian Position → Position → 模拟位置
```

### 3. 距离计算回退
```
STK真实距离 → 简化距离计算 → 默认距离
```

## ⚙️ 配置要求

### STK软件要求
- STK 12或更高版本
- COM接口已启用
- 卫星对象已创建在场景中

### Python依赖
```python
win32com.client  # Windows COM接口
pythoncom       # COM组件初始化
```

### 卫星命名规范
支持以下卫星命名格式：
- `Satellite1`, `Satellite2`, ...
- `SAT_001`, `SAT_002`, ...
- `Satellite_001`, `Satellite_002`, ...
- `Walker_001`, `Walker_002`, ...

## 🔍 故障排除

### 常见问题

1. **STK连接失败**
   ```
   解决方案：
   - 确认STK软件已启动
   - 检查COM接口是否启用
   - 验证STK版本兼容性
   ```

2. **卫星对象未找到**
   ```
   解决方案：
   - 检查STK场景中是否存在卫星对象
   - 验证卫星命名格式
   - 确认场景已正确加载
   ```

3. **位置数据获取失败**
   ```
   解决方案：
   - 检查时间格式是否正确
   - 验证卫星轨道数据
   - 确认仿真时间范围
   ```

### 调试信息

启用详细日志：
```python
import logging
logging.getLogger('src.stk_interface.stk_position_calculator').setLevel(logging.DEBUG)
```

## 📊 性能优化

### 批量操作
```python
# 批量获取多颗卫星位置
positions = calculator.get_multiple_satellite_positions(
    satellite_ids, datetime.now()
)
```

### 缓存机制
- 位置数据自动缓存
- 减少STK COM调用次数
- 提高计算效率

## 🎯 未来扩展

### 计划功能
1. **轨道预测**
   - 基于轨道参数的位置预测
   - 多时间点位置计算

2. **可见性分析**
   - 卫星-目标可见性计算
   - 遮挡分析

3. **性能优化**
   - 异步位置获取
   - 并行距离计算

## 📝 更新日志

### v1.0.0 (2025-08-02)
- ✅ 基础STK COM接口集成
- ✅ 真实卫星位置获取
- ✅ 精确距离计算
- ✅ 最近卫星查找
- ✅ 系统集成完成
- ✅ 回退机制实现

## 🤝 贡献指南

### 代码规范
- 遵循现有代码风格
- 添加详细的文档字符串
- 包含错误处理和日志记录

### 测试要求
- 单元测试覆盖
- 集成测试验证
- 性能测试评估

---

**📞 技术支持**

如有问题或建议，请联系开发团队或提交Issue。
