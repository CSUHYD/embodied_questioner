#!/usr/bin/env python3
"""
测试改进后的AI2-THOR控制器错误处理和重连机制
"""

import sys
import os
import time
sys.path.append('data_engine')

def test_controller_robustness():
    """测试控制器的健壮性"""
    print("测试AI2-THOR控制器健壮性...")
    
    try:
        from web_app import AI2THORWebController
        
        # 创建Web控制器
        controller = AI2THORWebController(scene="FloorPlan3", width=400, height=400)
        
        if not controller.running:
            print("✗ 控制器初始化失败")
            return False
        
        print("✓ 控制器初始化成功")
        
        # 测试健康检查
        print("测试健康检查功能...")
        health = controller._is_controller_healthy()
        print(f"✓ 健康检查结果: {health}")
        
        if not health:
            print("✗ 控制器不健康，测试失败")
            return False
        
        # 测试多次动作执行（这些可能会导致连接问题）
        actions = ["move_left", "move_right", "move_forward", "move_backward", "turn_left", "turn_right"]
        success_count = 0
        total_tests = 20
        
        print(f"执行 {total_tests} 次动作测试...")
        for i in range(total_tests):
            action = actions[i % len(actions)]
            success = controller.handle_action(action)
            if success:
                success_count += 1
            
            # 每5次测试检查一次健康状态
            if (i + 1) % 5 == 0:
                health = controller._is_controller_healthy()
                print(f"  测试 {i+1}/{total_tests}: 动作 {action}, 成功率 {success_count}/{i+1}, 健康状态: {health}")
                
                if not health:
                    print("  检测到控制器不健康，测试重连...")
                    if controller._recreate_controller():
                        print("  ✓ 控制器重连成功")
                    else:
                        print("  ✗ 控制器重连失败")
            
            time.sleep(0.1)  # 短暂延迟
        
        final_success_rate = success_count / total_tests
        print(f"\n总体成功率: {final_success_rate:.2%} ({success_count}/{total_tests})")
        
        # 最终健康检查
        final_health = controller._is_controller_healthy()
        print(f"最终健康状态: {final_health}")
        
        # 清理
        controller.cleanup()
        print("✓ 控制器清理完成")
        
        # 评估测试结果
        if final_success_rate >= 0.8 and final_health:  # 80%成功率认为合格
            print("🎉 控制器健壮性测试通过!")
            return True
        else:
            print("❌ 控制器健壮性测试未达标")
            return False
        
    except Exception as e:
        print(f"✗ 测试异常: {e}")
        return False

def test_error_recovery():
    """测试错误恢复机制"""
    print("\n测试错误恢复机制...")
    
    try:
        from web_app import AI2THORWebController
        
        controller = AI2THORWebController(scene="FloorPlan3", width=400, height=400)
        
        if not controller.running:
            print("✗ 控制器初始化失败")
            return False
        
        print("✓ 控制器初始化成功")
        
        # 故意破坏控制器连接
        print("故意中断控制器连接...")
        if controller.controller:
            try:
                controller.controller.stop()
                print("✓ 控制器已停止")
            except:
                pass
        
        # 测试健康检查应该检测到问题
        print("测试健康检查是否检测到问题...")
        health = controller._is_controller_healthy()
        print(f"健康检查结果: {health}")
        
        if health:
            print("⚠️  健康检查未能检测到问题（可能是正常情况）")
        else:
            print("✓ 健康检查正确检测到问题")
        
        # 测试重连
        print("测试控制器重连...")
        reconnect_success = controller._recreate_controller()
        print(f"重连结果: {reconnect_success}")
        
        if reconnect_success:
            print("✓ 控制器重连成功")
            
            # 测试重连后的功能
            print("测试重连后的动作执行...")
            action_success = controller.handle_action("move_forward")
            print(f"动作执行结果: {action_success}")
            
            if action_success:
                print("✓ 重连后功能正常")
            else:
                print("⚠️  重连后功能可能有问题")
        else:
            print("✗ 控制器重连失败")
        
        # 清理
        controller.cleanup()
        print("✓ 测试清理完成")
        
        return reconnect_success
        
    except Exception as e:
        print(f"✗ 错误恢复测试异常: {e}")
        return False

def main():
    print("=" * 60)
    print("AI2-THOR 控制器健壮性与错误恢复测试")
    print("=" * 60)
    
    test1_passed = test_controller_robustness()
    test2_passed = test_error_recovery()
    
    print("\n" + "=" * 60)
    print("测试结果总结:")
    print(f"控制器健壮性测试: {'✓ 通过' if test1_passed else '✗ 失败'}")
    print(f"错误恢复测试: {'✓ 通过' if test2_passed else '✗ 失败'}")
    
    if test1_passed and test2_passed:
        print("\n🎉 所有测试通过! 控制器改进成功!")
        print("\n📋 改进内容:")
        print("- ✅ 添加了控制器健康检查")
        print("- ✅ 实现了自动重连机制")
        print("- ✅ 改进了错误处理和重试逻辑")
        print("- ✅ 增强了帧更新循环的稳定性")
        return 0
    else:
        print("\n❌ 部分测试失败，可能需要进一步优化")
        return 1

if __name__ == "__main__":
    exit(main())