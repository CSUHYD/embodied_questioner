# AI2-THOR Web Demo

一个基于Web的AI2-THOR环境演示应用，支持通过键盘控制代理人移动，功能类似于 [ai2thor.allenai.org/demo](https://ai2thor.allenai.org/demo)。

## 功能特性

- 🌐 **Web界面**: 无需安装额外软件，直接在浏览器中运行
- 🎮 **键盘控制**: 支持WASD移动、视角控制、物体交互
- 🔄 **实时更新**: 使用WebSocket实现实时视频流和状态更新
- 🏠 **多场景支持**: 支持多个AI2-THOR内置场景
- 📊 **状态显示**: 实时显示代理人位置、朝向、手持物体等信息
- 🎯 **物体检测**: 自动检测鼠标悬停或中心十字光标下的物体

## 快速开始

### 1. 环境要求

确保已安装必要的依赖：

```bash
# 安装Python依赖
pip install flask flask-socketio opencv-python ai2thor numpy

# 或使用项目已有的requirements.txt
pip install -r requirements.txt
```

### 2. 启动应用

```bash
# 方法1: 使用启动脚本 (推荐)
python start_web_demo.py

# 方法2: 直接运行Web应用
python web_app.py
```

### 3. 访问应用

在浏览器中打开：`http://localhost:5001`

**注意**: 如果端口5001被占用，启动脚本会自动尝试其他可用端口(5002, 5003, 8000, 8080)。

## 使用说明

### 初始化环境

1. 在Web界面选择想要的场景 (FloorPlan1-5, FloorPlan201, FloorPlan301, FloorPlan401)
2. 点击"初始化环境"按钮
3. 等待环境加载完成

### 控制方式

#### 键盘控制 (推荐)
- **WASD**: 移动控制 (前进/左移/后退/右移)
- **Q/E**: 转向控制 (左转/右转)  
- **R/F**: 视角控制 (向上/向下)
- **空格**: 拾取物体
- **X**: 放下物体
- **C**: 交互/开关物体

#### 鼠标点击控制
- 使用右侧控制面板的按钮进行操作
- 包括移动、转向、视角、动作控制

### 界面说明

- **主视图**: 显示代理人的第一人称视角，带有绿色十字光标
- **连接状态**: 右上角显示WebSocket连接状态
- **控制面板**: 右侧包含操作说明、控制按钮、代理人状态信息
- **状态栏**: 底部显示当前操作状态和错误信息

## 技术架构

### 后端 (Python)
- **Flask**: Web服务器框架
- **Flask-SocketIO**: WebSocket支持，实现实时通信
- **AI2-THOR**: 3D仿真环境
- **OpenCV**: 图像处理和编码
- **RocAgent**: 代理人控制逻辑

### 前端 (HTML/JavaScript)
- **Socket.IO**: WebSocket客户端
- **HTML5 Canvas**: 视频流显示
- **CSS3**: 响应式界面设计
- **JavaScript**: 键盘事件处理和状态管理

### 数据流
1. 用户在浏览器中进行操作
2. JavaScript捕获键盘/鼠标事件
3. 通过WebSocket发送动作命令到后端
4. Python后端控制AI2-THOR执行动作
5. 获取更新后的视频帧和状态信息
6. 通过WebSocket实时推送到前端
7. 浏览器更新显示

## 支持的场景

| 场景ID | 类型 | 描述 |
|--------|------|------|
| FloorPlan1 | 厨房 | 标准厨房环境 |
| FloorPlan2 | 客厅 | 客厅环境 |
| FloorPlan3 | 厨房 | 另一个厨房布局 |
| FloorPlan4 | 客厅 | 另一个客厅布局 |
| FloorPlan5 | 卧室 | 卧室环境 |
| FloorPlan201 | 客厅 | 高级客厅场景 |
| FloorPlan301 | 卧室 | 高级卧室场景 |
| FloorPlan401 | 浴室 | 浴室环境 |

## 支持的动作

### 移动动作
- `move_forward`: 向前移动
- `move_backward`: 向后移动  
- `move_left`: 向左移动
- `move_right`: 向右移动
- `turn_left`: 左转
- `turn_right`: 右转

### 视角动作
- `look_up`: 向上看
- `look_down`: 向下看

### 交互动作
- `pickup`: 拾取物体
- `drop`: 放下物体
- `interact`: 交互(开关门窗等)

## 故障排除

### 常见问题

1. **环境初始化失败**
   - 检查AI2-THOR是否正确安装
   - 确保有足够的系统内存
   - 检查端口5000是否被占用

2. **键盘控制无响应**
   - 确保浏览器窗口处于焦点状态
   - 检查是否在输入框中（会禁用键盘控制）
   - 刷新页面重新连接

3. **视频画面不更新**
   - 检查WebSocket连接状态
   - 查看浏览器控制台是否有错误
   - 重新初始化环境

4. **代理人动作执行失败**
   - 检查动作是否合法（如在墙边无法继续移动）
   - 确保目标物体可见且可操作
   - 查看状态栏的错误信息

### 性能优化

- 关闭浏览器的其他标签页以节省内存
- 降低视频帧率可以减少CPU使用
- 在配置较低的设备上选择较小的场景

## 开发说明

### 文件结构
```
├── web_app.py              # 主Web应用
├── start_web_demo.py       # 启动脚本
├── templates/
│   └── index.html          # Web界面模板
├── data_engine/
│   ├── RocAgent.py         # 代理人控制
│   ├── baseAction.py       # 基础动作定义
│   └── ...                 # 其他项目文件
└── README_web_demo.md      # 本文档
```

### 扩展功能

要添加新的控制功能：

1. 在`web_app.py`的`handle_action`方法中添加新动作
2. 在`index.html`中添加对应的按钮和键盘映射
3. 在`keyMappings`对象中定义键盘快捷键

### API接口

- `POST /api/init`: 初始化环境
- `POST /api/action`: 执行动作
- `GET /api/agent_info`: 获取代理人信息
- `WebSocket /`: 实时通信

## 致谢

本Web演示基于项目现有的AI2-THOR集成代码构建，复用了`third_person_observer.py`中的控制逻辑和`RocAgent`的动作系统。