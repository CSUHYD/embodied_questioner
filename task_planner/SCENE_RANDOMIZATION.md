# AI2THOR 场景物品位置随机化功能

## 功能概述

本功能为AI2THOR场景初始化添加了物品位置随机化能力，可以在每次运行任务时自动打乱场景中可移动物品的位置，增强训练的多样性和泛化能力。

## 特性

- **智能物品筛选**：自动识别可移动的物品（如食物、餐具、日用品等）
- **安全放置**：确保物品被合理地放置在适当的接收容器上
- **可配置比例**：可设置随机化物品的比例（0-1）
- **可重现性**：支持设置随机种子以获得可重现的结果
- **容器状态随机化**：同时随机化可开启物品（如柜子、抽屉）的开关状态

## 文件结构

```
task_planner/
├── scene_randomizer.py          # 核心随机化逻辑
├── robot_task_planner.py        # 集成到主程序
├── test_scene_randomizer.py     # 测试脚本
├── config/
│   └── scene_config.json        # 配置文件
└── SCENE_RANDOMIZATION.md       # 本文档
```

## 配置说明

在 `task_planner/config/scene_config.json` 中添加以下配置：

```json
{
  "randomization": {
    "enabled": false,                    // 是否启用随机化
    "seed": null,                       // 随机种子，null表示完全随机
    "randomize_ratio": 0.4,             // 随机化比例（0-1）
    "safe_distance": 0.2,               // 物品间安全距离
    "max_attempts": 10,                 // 每个物品最大尝试次数
    "moveable_types": [                 // 可移动物品类型
      "Apple", "Bread", "Egg", "Lettuce", "Potato", "Tomato",
      "Cup", "Mug", "Plate", "Bowl", "Knife", "Fork", "Spoon",
      "Bottle", "Can", "Box", "Newspaper", "Book", "RemoteControl",
      "KeyChain", "CreditCard", "Pen", "Pencil", "CellPhone"
    ],
    "immoveable_types": [               // 不可移动物品类型
      "Sink", "Stove", "Fridge", "Microwave", "Toaster", 
      "Cabinet", "Drawer", "CounterTop", "Table", "Chair", "Sofa"
    ]
  }
}
```

## 使用方法

### 1. 启用随机化

修改配置文件中的 `enabled` 为 `true`：

```json
{
  "randomization": {
    "enabled": true,
    "randomize_ratio": 0.5,
    "seed": 42
  }
}
```

### 2. 运行任务

正常运行任务程序，随机化将在场景初始化后自动执行：

```bash
cd task_planner
python robot_task_planner.py
```

### 3. 测试功能

运行测试脚本验证随机化功能：

```bash
cd task_planner
python test_scene_randomizer.py
```

## 参数详解

### enabled (bool)
- **默认值**: `false`
- **说明**: 控制是否启用场景随机化功能

### seed (int | null)
- **默认值**: `null`
- **说明**: 随机种子，设置固定值可获得可重现的结果，设为null则每次都不同

### randomize_ratio (float)
- **默认值**: `0.4`
- **范围**: `0.0 - 1.0`
- **说明**: 要随机化的物品比例，0.4表示随机化40%的可移动物品

### safe_distance (float)
- **默认值**: `0.2`
- **说明**: 物品间最小安全距离（米）

### max_attempts (int)
- **默认值**: `10`
- **说明**: 为每个物品寻找新位置的最大尝试次数

### moveable_types (list)
- **说明**: 定义哪些物品类型可以被随机化移动
- **建议**: 只包含小型、便携的物品

### immoveable_types (list)
- **说明**: 定义哪些物品类型不应被移动
- **建议**: 包含大型家具和固定设施

## 工作原理

1. **场景初始化**: 在AI2THOR场景加载完成后触发
2. **物品筛选**: 识别场景中所有可移动的物品
3. **随机选择**: 根据配置的比例随机选择要移动的物品
4. **寻找容器**: 为每个物品寻找合适的接收容器
5. **安全放置**: 尝试将物品放置到新位置
6. **状态随机化**: 随机化可开启物品的开关状态

## 日志输出

启用后会产生如下日志：

```
[INFO] Starting scene randomization for FloorPlan3
[INFO] Found 15 moveable objects
[INFO] Found 8 available receptacles
[DEBUG] Successfully moved Apple to CounterTop
[INFO] Successfully randomized 6/8 objects
[INFO] Scene randomization completed for FloorPlan3
```

## 注意事项

1. **性能影响**: 随机化过程可能需要几秒钟时间，特别是在复杂场景中
2. **物理约束**: 并非所有物品都能成功移动，受AI2THOR物理引擎限制
3. **任务适应性**: 某些特定任务可能需要调整可移动物品类型列表
4. **调试建议**: 使用固定种子进行调试，确保结果可重现

## 故障排除

### 随机化失败
- 检查日志中的错误信息
- 确认场景中有足够的接收容器
- 调整 `max_attempts` 增加尝试次数

### 物品消失
- 检查 `moveable_types` 配置是否合理
- 确认物品的 `pickupable` 属性为true

### 性能问题
- 降低 `randomize_ratio` 减少需要移动的物品数量
- 减少 `max_attempts` 降低每个物品的尝试次数

## 扩展开发

### 添加新的物品类型

```python
# 在配置中添加新的可移动物品类型
"moveable_types": [
    "Apple", "Bread", "Egg",
    "NewItemType"  # 添加新类型
]
```

### 自定义放置策略

```python
# 在SceneRandomizer类中重写_randomize_single_object方法
def _randomize_single_object(self, controller, obj, receptacles):
    # 实现自定义放置逻辑
    pass
```

### 添加新的随机化规则

```python
# 在SceneRandomizer类中添加新方法
def randomize_lighting(self, controller):
    # 实现光照随机化
    pass
```

## 版本历史

- **v1.0**: 初始版本，支持基本物品位置随机化
- **v1.1**: 添加容器状态随机化功能
- **v1.2**: 增强错误处理和日志记录

## 贡献

如有改进建议或发现问题，请提交Issue或Pull Request。