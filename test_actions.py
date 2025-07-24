#!/usr/bin/env python3
"""
测试修复后的动作系统
"""

import sys
import os
sys.path.append('data_engine')

def test_baseaction_fixes():
    """测试BaseAction修复"""
    print("测试BaseAction修复...")
    
    try:
        from baseAction import BaseAction
        from ai2thor.controller import Controller
        
        # 创建控制器
        controller = Controller(
            scene="FloorPlan3",
            width=400,
            height=400,
            agentMode="default"
        )
        
        action = BaseAction()
        
        print("✓ AI2-THOR控制器创建成功")
        
        # 测试move_left是否返回结果
        print("测试 move_left 动作...")
        result = action.action_mapping["move_left"](controller, 0.1)
        if result is not None:
            print(f"✓ move_left 返回结果: {result.metadata.get('lastActionSuccess', False)}")
        else:
            print("✗ move_left 返回 None")
        
        # 测试move_right是否返回结果
        print("测试 move_right 动作...")
        result = action.action_mapping["move_right"](controller, 0.1)
        if result is not None:
            print(f"✓ move_right 返回结果: {result.metadata.get('lastActionSuccess', False)}")
        else:
            print("✗ move_right 返回 None")
        
        # 测试release动作
        print("测试 release 动作...")
        result = action.action_mapping["release"](controller)
        if result is not None:
            success = result.metadata.get('lastActionSuccess', False)
            print(f"✓ release 返回结果: {success}")
            if not success:
                print(f"  错误信息: {result.metadata.get('errorMessage', 'No error message')}")
        else:
            print("✗ release 返回 None")
        
        controller.stop()
        print("✓ 所有动作测试完成")
        return True
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        return False

def test_web_controller():
    """测试Web控制器"""
    print("\n测试Web控制器...")
    
    try:
        from web_app import AI2THORWebController
        
        # 创建Web控制器
        web_controller = AI2THORWebController(scene="FloorPlan3", width=400, height=400)
        
        if not web_controller.running:
            print("✗ Web控制器初始化失败")
            return False
        
        print("✓ Web控制器初始化成功")
        
        # 测试健康检查
        health = web_controller._is_controller_healthy()
        print(f"✓ 控制器健康检查: {health}")
        
        # 测试几个动作
        actions_to_test = ["move_left", "move_right", "move_forward", "turn_left"]
        
        for action in actions_to_test:
            print(f"测试动作: {action}")
            success = web_controller.handle_action(action)
            print(f"  结果: {'成功' if success else '失败'}")
        
        # 清理
        web_controller.cleanup()
        print("✓ Web控制器测试完成")
        return True
        
    except Exception as e:
        print(f"✗ Web控制器测试失败: {e}")
        return False

def main():
    print("=" * 50)
    print("AI2-THOR 动作系统修复测试")
    print("=" * 50)
    
    test1_passed = test_baseaction_fixes()
    test2_passed = test_web_controller()
    
    print("\n" + "=" * 50)
    print("测试结果:")
    print(f"BaseAction修复测试: {'✓ 通过' if test1_passed else '✗ 失败'}")
    print(f"Web控制器测试: {'✓ 通过' if test2_passed else '✗ 失败'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过! 修复成功!")
        return 0
    else:
        print("\n❌ 部分测试失败，需要进一步检查")
        return 1

if __name__ == "__main__":
    exit(main())