# ADK开发UI - 多智能体系统管理界面

## 概述

ADK开发UI是基于Google ADK开源框架设计的Web管理界面，专门用于多智能体系统的管理、调试和开发。界面设计严格参考ADK官方项目的设计规范和最佳实践。

### 官方参考
- **ADK官方项目**: https://github.com/google/adk-java
- **ADK文档**: https://google.github.io/adk-docs/
- **设计理念**: 遵循ADK官方的UI设计模式和交互规范

## 功能特性

### 🎯 核心功能
- **智能体管理**: 实时监控和管理所有智能体实例
- **会话管理**: 创建、监控和调试多智能体会话
- **系统监控**: 实时查看系统状态和性能指标
- **日志查看**: 实时日志流和高级过滤功能
- **调试工具**: 智能体交互和调试功能

### 🎨 界面特性
- **响应式设计**: 适配桌面和移动设备
- **实时更新**: 基于WebSocket的实时数据更新
- **专业外观**: 遵循Google Material Design规范
- **直观操作**: 简洁明了的用户界面

## 快速开始

### 1. 安装依赖

```bash
# 安装Web框架依赖
pip install flask flask-socketio

# 确保ADK框架已安装
pip install google-adk
```

### 2. 启动UI服务器

```bash
# 使用启动脚本
python start_adk_ui.py
```

### 3. 访问界面

打开浏览器访问: http://localhost:8080

## 界面导航

### 主要页面

#### 1. 系统概览 (/)
- **系统状态**: 实时显示系统运行状态
- **智能体统计**: 各类智能体数量统计
- **系统架构图**: 可视化的智能体层次结构
- **快速操作**: 常用功能的快捷入口
- **最近日志**: 最新的系统日志信息

#### 2. 智能体管理 (/agents)
- **智能体列表**: 所有智能体的详细信息
- **智能体详情**: 查看智能体配置和状态
- **智能体交互**: 直接与智能体进行交互
- **实时监控**: 智能体运行状态监控

#### 3. 会话管理 (/sessions)
- **会话列表**: 所有活跃和历史会话
- **会话详情**: 查看会话消息历史
- **新建会话**: 创建新的多智能体会话
- **会话控制**: 暂停、恢复、结束会话

#### 4. 日志查看 (/logs)
- **实时日志**: 实时显示系统日志
- **日志过滤**: 按级别、时间、关键词过滤
- **日志搜索**: 高级搜索和高亮显示
- **自动刷新**: 可配置的自动刷新功能

## 使用指南

### 启动多智能体系统

1. **通过UI启动**:
   - 点击侧边栏的"启动系统"按钮
   - 系统将自动初始化所有组件

2. **配置参数**:
   - 配置文件路径: `config/config.yaml`
   - 输出目录: `output/`

### 管理智能体

1. **查看智能体列表**:
   - 访问"智能体管理"页面
   - 查看所有智能体的状态和信息

2. **智能体交互**:
   - 点击智能体卡片查看详情
   - 使用"运行智能体"功能进行交互
   - 实时查看智能体响应

3. **智能体类型**:
   - **仿真调度智能体**: 负责场景管理和任务协调
   - **卫星智能体**: 负责卫星任务管理
   - **组长智能体**: 负责讨论组协调

### 会话管理

1. **创建新会话**:
   - 点击"新建会话"按钮
   - 填写用户ID和初始消息
   - 系统自动创建会话

2. **监控会话**:
   - 查看会话状态和消息历史
   - 实时监控会话活动
   - 管理会话生命周期

### 日志监控

1. **实时查看**:
   - 日志自动实时更新
   - 支持不同级别的日志显示

2. **高级过滤**:
   - 按日志级别过滤
   - 关键词搜索
   - 时间范围过滤

3. **自动刷新**:
   - 启用自动刷新功能
   - 可配置刷新间隔

## API接口

### 系统控制API

```http
# 启动系统
POST /api/system/start
Content-Type: application/json
{
  "config_path": "config/config.yaml",
  "output_dir": "output"
}

# 停止系统
POST /api/system/stop

# 获取系统状态
GET /api/system/status
```

### 智能体管理API

```http
# 获取智能体列表
GET /api/agents/list

# 获取智能体详情
GET /api/agents/{agent_id}/details
```

### 日志API

```http
# 获取日志
GET /api/logs
```

## WebSocket事件

### 客户端事件

```javascript
// 连接到服务器
socket.on('connect', function() {
    console.log('已连接到服务器');
});

// 运行智能体
socket.emit('run_agent', {
    agent_id: 'agent_id',
    message: 'message'
});
```

### 服务器事件

```javascript
// 智能体响应
socket.on('agent_response', function(data) {
    console.log('智能体响应:', data);
});

// 新日志
socket.on('new_log', function(logEntry) {
    console.log('新日志:', logEntry);
});
```

## 技术架构

### 后端技术栈
- **Flask**: Web框架
- **Flask-SocketIO**: WebSocket支持
- **Google ADK**: 智能体框架
- **Python**: 主要编程语言

### 前端技术栈
- **Bootstrap 5**: UI框架
- **Socket.IO**: 实时通信
- **Font Awesome**: 图标库
- **原生JavaScript**: 交互逻辑

### 设计原则
- **ADK兼容**: 严格遵循ADK框架规范
- **实时性**: 基于WebSocket的实时更新
- **响应式**: 适配不同屏幕尺寸
- **可扩展**: 模块化的组件设计

## 开发和扩展

### 添加新页面

1. **创建HTML模板**:
   ```html
   {% extends "base.html" %}
   {% block content %}
   <!-- 页面内容 -->
   {% endblock %}
   ```

2. **添加路由**:
   ```python
   @self.app.route('/new_page')
   def new_page():
       return render_template('new_page.html')
   ```

### 添加新API

```python
@self.app.route('/api/new_endpoint')
def new_endpoint():
    # API逻辑
    return jsonify({'result': 'success'})
```

### 添加WebSocket事件

```python
@self.socketio.on('new_event')
def handle_new_event(data):
    # 事件处理逻辑
    emit('response_event', {'data': data})
```

## 故障排除

### 常见问题

1. **端口占用**:
   ```bash
   # 检查端口占用
   netstat -ano | findstr :8080
   # 修改端口
   ui = ADKDevUI(host="localhost", port=8081)
   ```

2. **依赖缺失**:
   ```bash
   pip install flask flask-socketio
   ```

3. **ADK框架问题**:
   - 确保ADK框架正确安装
   - 检查API密钥配置

### 调试模式

```python
# 启用调试模式
ui.run(debug=True)
```

## 最佳实践

### 性能优化
- 限制日志数量避免内存溢出
- 使用分页加载大量数据
- 合理设置WebSocket连接数

### 安全考虑
- 在生产环境中禁用调试模式
- 配置适当的访问控制
- 使用HTTPS协议

### 监控建议
- 定期检查系统资源使用
- 监控WebSocket连接状态
- 记录用户操作日志

## 更新日志

### v1.0.0 (2025-01-27)
- 初始版本发布
- 基础智能体管理功能
- 实时日志查看
- WebSocket实时通信
- 响应式UI设计

---

**基于Google ADK开源框架设计**  
官方项目: https://github.com/google/adk-java
