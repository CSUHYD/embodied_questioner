# 路径问题修复总结

## 问题描述
当从项目根目录 `embodied_reasoner` 运行 `data_engine` 目录下的脚本时，会出现路径问题，因为脚本中使用了相对路径，这些路径假设脚本从 `data_engine` 目录内运行。

## 修复方案
在每个受影响的脚本中添加了路径解析函数，使脚本能够正确处理从任意目录运行的情况。

### 核心修复函数
```python
def get_data_engine_path():
    """获取data_engine目录的绝对路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return script_dir

def get_project_root():
    """获取项目根目录的绝对路径"""
    data_engine_path = get_data_engine_path()
    return os.path.dirname(data_engine_path)
```

## 修复的文件列表

### ✅ 1. robot_task_planner.py
- **配置文件路径**: 修复 `load_prompt_config` 和 `load_scene_config` 函数
- **测试任务路径**: 修复 `load_test_tasks` 和 `get_test_task_by_id` 函数
- **场景元数据路径**: 修复 `get_scene_paths` 函数中的路径构造
- **日志目录路径**: 修复日志文件创建路径
- **数据输出路径**: 修复数据保存路径

### ✅ 2. robot_task_planner_subgoal.py
- **配置文件路径**: 修复 `load_prompt_config` 和 `load_scene_config` 函数
- 应用了与主规划器相同的路径修复逻辑

### ✅ 3. TaskGenerate.py
- **任务生成目录引用**: 修复 `pick_up_and_put.json` 文件路径
- 所有4个引用都已修复为使用绝对路径

### ✅ 4. vlmCall_ollama.py
- **配置文件路径**: 修复配置文件加载
- **图像数据路径**: 修复测试代码中的图像路径引用

## 特殊处理

### 配置文件查找逻辑
对于 `scene_config.json`，实现了智能查找逻辑：
1. 首先在 `data_engine/config/` 目录中查找
2. 如果不存在，则在项目根目录的 `config/` 目录中查找

这样可以兼容不同的配置文件放置方式。

## 测试验证

创建了 `test_path_fixes.py` 脚本来验证所有修复：

```bash
python test_path_fixes.py
```

测试覆盖：
- ✅ 路径函数测试
- ✅ 配置文件加载测试  
- ✅ 任务生成路径测试
- ✅ 图像路径测试
- ✅ 场景元数据路径测试

## 使用说明

修复后，您可以从项目根目录直接运行 data_engine 中的脚本：

```bash
# 从根目录运行
python data_engine/robot_task_planner.py

# 或者仍然可以从 data_engine 目录运行
cd data_engine
python robot_task_planner.py
```

两种方式都可以正确工作，脚本会自动检测执行环境并使用正确的路径。

## 影响的路径类型

1. **配置文件**: `config/prompt_config.json`, `config/scene_config.json`
2. **测试任务**: `test_tasks.json`
3. **场景元数据**: `taskgenerate/*/metadata.json`, `taskgenerate/*/originPos.json`
4. **任务元数据**: `*_task_metadata/*.json`
5. **日志文件**: `logs/*`
6. **数据输出**: `data/data_*/*`
7. **图像文件**: `data/item_image/*`

所有这些路径现在都能正确解析，无论脚本从哪个目录运行。