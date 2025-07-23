#!/usr/bin/env python3
"""
Test Tasks Demo Script
演示如何使用 test_tasks.json 中的测试任务
"""

from robot_task_planner import SceneManager

def list_all_test_tasks():
    """列出所有可用的测试任务"""
    print("=" * 80)
    print("📋 所有可用的测试任务")
    print("=" * 80)
    
    scene_manager = SceneManager()
    tasks = scene_manager.load_test_tasks()
    
    for task in tasks:
        print(f"ID: {task['id']}")
        print(f"任务: {task['taskname']}")
        print(f"描述: {task['description']}")
        print(f"场景: {task['scene']} ({task['room']})")
        print(f"类型: {task['tasktype']}")
        print("-" * 80)
    
    return tasks

def show_task_categories():
    """显示任务分类统计"""
    print("\n📊 任务分类统计")
    print("=" * 40)
    
    scene_manager = SceneManager()
    tasks = scene_manager.load_test_tasks()
    
    # 按类型分类
    task_types = {}
    for task in tasks:
        task_type = task['tasktype']
        if task_type not in task_types:
            task_types[task_type] = []
        task_types[task_type].append(task)
    
    for task_type, type_tasks in task_types.items():
        print(f"{task_type}: {len(type_tasks)} 个任务")
        for task in type_tasks:
            print(f"  - {task['id']}: {task['taskname']}")
    
    print(f"\n总计: {len(tasks)} 个测试任务")

def show_usage_examples():
    """显示使用示例"""
    print("\n🛠 使用示例")
    print("=" * 40)
    
    print("1. 运行单个测试任务:")
    print("   修改 robot_task_planner.py 中的配置:")
    print("   USE_TEST_TASKS = True")
    print("   TEST_TASK_ID = 'test_001'")
    print("   RUN_ALL_TEST_TASKS = False")
    print()
    
    print("2. 运行所有测试任务:")
    print("   USE_TEST_TASKS = True")
    print("   RUN_ALL_TEST_TASKS = True")
    print()
    
    print("3. 使用手动指定的任务:")
    print("   USE_TEST_TASKS = False")
    print("   然后修改 manual_task 中的 taskname")
    print()
    
    print("4. 推荐的测试顺序:")
    recommended_order = [
        "test_001", "test_006", "test_010",  # 简单任务
        "test_002", "test_003", "test_005",  # 中等任务
        "test_004", "test_015"               # 复杂任务
    ]
    
    scene_manager = SceneManager()
    for task_id in recommended_order:
        task = scene_manager.get_test_task_by_id(task_id)
        if task:
            print(f"   {task_id}: {task['taskname']}")

def test_task_loading():
    """测试任务加载功能"""
    print("\n🧪 测试任务加载功能")
    print("=" * 40)
    
    scene_manager = SceneManager()
    
    # 测试加载所有任务
    tasks = scene_manager.load_test_tasks()
    print(f"✅ 成功加载 {len(tasks)} 个测试任务")
    
    # 测试获取特定任务
    test_task = scene_manager.get_test_task_by_id("test_001")
    if test_task:
        print(f"✅ 成功获取任务 test_001: {test_task['taskname']}")
    else:
        print("❌ 获取任务 test_001 失败")
    
    # 测试获取不存在的任务
    non_exist_task = scene_manager.get_test_task_by_id("test_999")
    if non_exist_task:
        print("❌ 错误：获取到了不存在的任务")
    else:
        print("✅ 正确处理了不存在的任务")

def main():
    """主函数"""
    print("🎮 测试任务系统演示")
    print("=" * 80)
    
    try:
        # 列出所有任务
        tasks = list_all_test_tasks()
        
        # 显示分类统计
        show_task_categories()
        
        # 显示使用示例
        show_usage_examples()
        
        # 测试功能
        test_task_loading()
        
        print("\n✅ 演示完成！")
        print("现在你可以:")
        print("1. 编辑 robot_task_planner.py 中的配置")
        print("2. 运行 python robot_task_planner.py")
        print("3. 查看执行结果和日志")
        
    except Exception as e:
        print(f"❌ 演示失败: {e}")

if __name__ == "__main__":
    main()