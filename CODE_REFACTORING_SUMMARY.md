# 代码精简总结

## 精简前后对比
- **精简前**: 1751行
- **精简后**: 1738行
- **减少行数**: 13行

## 主要精简内容

### 1. ✅ 合并重复的配置加载逻辑
**精简前**: 两个独立的配置加载函数，各自处理路径和错误
```python
def load_prompt_config(config_path="config/prompt_config.json"):
    if not os.path.isabs(config_path):
        config_path = os.path.join(get_data_engine_path(), config_path)
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"Config file {config_path} not found")
        return {}

def load_scene_config(config_path="config/scene_config.json"):
    # 类似的重复逻辑...
```

**精简后**: 统一的配置加载函数
```python
def load_config_file(config_path, default_value=None, fallback_to_root=False):
    """通用配置文件加载函数"""
    # 统一的路径处理和错误处理逻辑

def load_prompt_config(config_path="config/prompt_config.json"):
    return load_config_file(config_path, default_value={})

def load_scene_config(config_path="config/scene_config.json"):
    return load_config_file(config_path, default_value={}, fallback_to_root=True)
```

### 2. ✅ 精简重复的路径处理函数
**精简前**: 多个函数中重复的路径处理逻辑
```python
def load_test_tasks(self, test_tasks_path="test_tasks.json"):
    if not os.path.isabs(test_tasks_path):
        test_tasks_path = os.path.join(get_data_engine_path(), test_tasks_path)
    # ...

def get_test_task_by_id(self, task_id, test_tasks_path="test_tasks.json"):
    if not os.path.isabs(test_tasks_path):
        test_tasks_path = os.path.join(get_data_engine_path(), test_tasks_path)
    # ...
```

**精简后**: 添加通用路径处理工具
```python
def _get_absolute_path(self, path):
    """获取绝对路径的工具函数"""
    if not os.path.isabs(path):
        return os.path.join(get_data_engine_path(), path)
    return path

def load_test_tasks(self, test_tasks_path="test_tasks.json"):
    test_tasks_path = self._get_absolute_path(test_tasks_path)
    # ...
```

### 3. ✅ 简化楼层平面图生成逻辑
**精简前**: 每个房间类型都有重复的条件判断
```python
def get_floorplans_by_room(self, room):
    if room == 'kitchens':
        return [f"FloorPlan{i}" for i in floorplans]
    elif room == 'living_rooms':
        return [f"FloorPlan{i}" for i in floorplans]
    elif room == 'bedrooms':
        return [f"FloorPlan{i}" for i in floorplans]
    elif room == 'bathrooms':
        return [f"FloorPlan{i}" for i in floorplans]
    # ...
```

**精简后**: 统一处理逻辑
```python
def get_floorplans_by_room(self, room):
    if room not in self.room_configs:
        return []
    floorplans = self.room_configs[room].get("floorplans", [])
    return [f"FloorPlan{i}" for i in floorplans]  # 所有房间类型统一处理
```

### 4. ✅ 创建通用XML标签解析函数
**精简前**: 多个函数中重复的正则表达式解析
```python
# 在多个函数中重复出现
import re
subgoal_pattern = r'<Subgoal\d+>(.*?)</Subgoal\d+>'
matches = re.findall(subgoal_pattern, result, re.DOTALL)
subgoals = [m.strip() for m in matches]

# 类似的模式在subtask、action、task解析中重复出现
```

**精简后**: 统一的XML标签解析函数
```python
def parse_xml_tags(text, tag_name):
    """通用的XML标签解析函数"""
    pattern = f'<{tag_name}(\\d+)>(.*?)</{tag_name}\\1>'
    matches = re.findall(pattern, text, re.DOTALL)
    return [(int(num), content.strip()) for num, content in matches]

# 在各个函数中使用
matches = parse_xml_tags(result, "Subgoal")
subgoals = [content for _, content in matches]
```

### 5. ✅ 移除冗余的导入和变量
**移除的冗余内容**:
- 13个重复的 `import re` 语句（函数内部导入）
- 未使用的 `import functools`
- 未使用的 `room_type` 变量定义

### 6. ✅ 简化日志和错误处理
- 统一了配置文件加载的错误处理逻辑
- 减少了重复的日志输出模式

## 代码质量改进

### 可维护性提升
- **模块化**: 通用函数可以在多个地方复用
- **一致性**: 所有XML标签解析使用统一的函数
- **可扩展性**: 新增配置文件类型只需调用通用加载函数

### 代码可读性改进
- **减少重复**: 消除了大量重复代码
- **功能聚合**: 相似功能集中在通用函数中
- **命名清晰**: 工具函数命名更加清晰和专业

### 性能优化
- **减少重复导入**: 移除了函数内部的重复import语句
- **统一正则编译**: XML标签解析更加高效

## 测试验证

所有精简后的功能都通过了验证测试：
- ✅ 配置文件加载正常
- ✅ 路径处理功能正常
- ✅ XML标签解析功能正常
- ✅ 代码导入无错误

## 后续建议

虽然本次精简主要专注于消除重复代码，但文件仍然较大（1738行）。如需进一步优化，建议：

1. **模块拆分**: 将不同功能类拆分到独立文件
2. **配置外置**: 将硬编码的配置移至配置文件
3. **函数拆分**: 将超长函数（如execute_decisions）进一步拆分
4. **接口抽象**: 为不同的规划和执行阶段定义清晰的接口

本次精简为后续更深入的重构奠定了良好基础。