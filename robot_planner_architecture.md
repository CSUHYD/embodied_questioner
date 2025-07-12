# Robot Task Planner - 简明系统架构

## 1. 系统目标
- 基于视觉语言模型（VLM）自主推理和决策
- 不预设动作，完全依赖VLM
- 支持英文交互和用户问答

## 2. 核心模块

```
RobotTaskPlanner (主流程控制)
├── VLMReasoning (VLM推理与决策)
├── ActionExecutor (动作执行)
├── EnvObserver (环境观察/对象列表)
├── UserInteraction (用户问答管理)
└── TrajectoryRecorder (轨迹与日志)
```

## 3. 数据流

1. **环境观察**（EnvObserver）
   - 获取当前环境元数据、可见对象
2. **VLM推理**（VLMReasoning）
   - 输入：图像、对象列表、历史轨迹、任务描述
   - 输出：<Observation>、<Thinking>、<Planning>、<DecisionMaking>、<Question>
3. **用户交互**（UserInteraction）
   - 若VLM输出<Question>，等待用户输入，反馈给VLM
4. **动作执行**（ActionExecutor）
   - 根据<DecisionMaking>执行环境动作
   - 更新环境状态
5. **轨迹记录**（TrajectoryRecorder）
   - 记录每轮的观察、推理、决策、动作、用户交互

## 4. 典型流程

```
初始化 → 观察 → VLM推理 → (可选)用户问答 → 决策 → 动作执行 → 状态更新 → 记录 → 下一轮/终止
```

## 5. 各模块职责

- **RobotTaskPlanner**：主循环，调度各模块，异常处理
- **VLMReasoning**：构造prompt，调用VLM，解析结构化输出
- **ActionExecutor**：解析决策，调用AI2THOR接口执行
- **EnvObserver**：获取/更新可见对象、环境元数据
- **UserInteraction**：管理VLM提问与用户答复
- **TrajectoryRecorder**：保存每轮的所有信息，便于回溯和分析

---

> 本架构适合基于VLM的自主机器人任务规划，强调模块解耦与数据流清晰。 