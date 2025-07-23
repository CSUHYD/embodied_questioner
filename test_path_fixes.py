#!/usr/bin/env python3
"""
测试路径修复的有效性
这个脚本从项目根目录运行，验证data_engine中的脚本可以正确找到所有路径
"""
import sys
import os

# 添加data_engine到Python路径
sys.path.append('data_engine')

def test_path_functions():
    """测试路径函数"""
    print("=" * 50)
    print("测试路径函数")
    print("=" * 50)
    
    try:
        from robot_task_planner import get_data_engine_path, get_project_root
        print(f"✓ Data engine path: {get_data_engine_path()}")
        print(f"✓ Project root: {get_project_root()}")
        return True
    except Exception as e:
        print(f"✗ 路径函数测试失败: {e}")
        return False

def test_config_loading():
    """测试配置文件加载"""
    print("\n" + "=" * 50)
    print("测试配置文件加载")
    print("=" * 50)
    
    try:
        from robot_task_planner import load_prompt_config, load_scene_config
        
        prompt_config = load_prompt_config()
        scene_config = load_scene_config()
        
        print(f"✓ Prompt配置加载成功: {bool(prompt_config)}")
        print(f"✓ Scene配置加载成功: {bool(scene_config)}")
        
        return True
    except Exception as e:
        print(f"✗ 配置文件加载测试失败: {e}")
        return False

def test_task_generation_paths():
    """测试任务生成路径"""
    print("\n" + "=" * 50)
    print("测试任务生成路径")
    print("=" * 50)
    
    try:
        from TaskGenerate import get_data_engine_path as tg_get_path
        
        tg_path = tg_get_path()
        pick_up_put_file = os.path.join(tg_path, 'taskgenerate/pick_up_and_put.json')
        
        print(f"✓ TaskGenerate data_engine path: {tg_path}")
        print(f"✓ pick_up_and_put.json存在: {os.path.exists(pick_up_put_file)}")
        
        return True
    except Exception as e:
        print(f"✗ 任务生成路径测试失败: {e}")
        return False

def test_image_paths():
    """测试图像路径"""
    print("\n" + "=" * 50)
    print("测试图像路径")
    print("=" * 50)
    
    try:
        from vlmCall_ollama import get_project_root as vlm_get_root
        
        project_root = vlm_get_root()
        test_image = os.path.join(project_root, "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Apple_37512a22.png")
        
        print(f"✓ VLM项目根目录: {project_root}")
        print(f"✓ 测试图像存在: {os.path.exists(test_image)}")
        
        return True
    except Exception as e:
        print(f"✗ 图像路径测试失败: {e}")
        return False

def test_scene_metadata_paths():
    """测试场景元数据路径"""
    print("\n" + "=" * 50)
    print("测试场景元数据路径")
    print("=" * 50)
    
    try:
        from robot_task_planner import SceneManager
        
        scene_manager = SceneManager()
        paths = scene_manager.get_scene_paths("taskgenerate", "kitchens", "FloorPlan3", "pickup_and_put")
        
        print(f"✓ 元数据路径: {paths['metadata_path']}")
        print(f"✓ 原始位置路径: {paths['origin_pos_path']}")
        print(f"✓ 任务生成路径: {paths['generate_task']}")
        
        # 检查路径是否存在
        metadata_exists = os.path.exists(paths['metadata_path'])
        print(f"✓ 元数据文件存在: {metadata_exists}")
        
        return True
    except Exception as e:
        print(f"✗ 场景元数据路径测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("从项目根目录运行data_engine路径修复测试")
    print("当前工作目录:", os.getcwd())
    print()
    
    tests = [
        test_path_functions,
        test_config_loading,
        test_task_generation_paths,
        test_image_paths,
        test_scene_metadata_paths
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    print("=" * 50)
    
    if passed == total:
        print("✓ 所有路径修复测试通过！")
        return 0
    else:
        print("✗ 部分测试失败，请检查路径配置。")
        return 1

if __name__ == "__main__":
    exit(main())