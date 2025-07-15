#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json
import math

# 添加data_engine目录到路径
sys.path.append('data_engine')

def analyze_navigable_objects():
    """分析可导航对象的判断逻辑"""
    print("=== 分析可导航对象判断逻辑 ===")
    
    # 模拟冰箱的metadata
    fridge_metadata = {
        "objects": [
            {
                "objectId": "Fridge_1",
                "objectType": "Fridge",
                "visible": True,
                "axisAlignedBoundingBox": {
                    "size": {"x": 0.8, "y": 1.8, "z": 0.6},  # 冰箱尺寸
                    "center": {"x": 2.0, "y": 0.9, "z": 1.5}  # 冰箱位置
                }
            },
            {
                "objectId": "Tomato_1", 
                "objectType": "Tomato",
                "visible": True,
                "axisAlignedBoundingBox": {
                    "size": {"x": 0.05, "y": 0.05, "z": 0.05},  # 番茄尺寸
                    "center": {"x": 2.0, "y": 0.9, "z": 1.5}  # 番茄位置（在冰箱内）
                }
            }
        ],
        "agent": {
            "position": {"x": 0.0, "y": 0.0, "z": 0.0}  # 机器人位置
        }
    }
    
    # 模拟get_volume_distance_rate函数的逻辑
    def analyze_object(obj, agent_pos):
        size = obj["axisAlignedBoundingBox"]["size"]
        v = size["x"] * size["y"] * size["z"]  # 体积
        dx = obj["axisAlignedBoundingBox"]["center"]["x"]
        dz = obj["axisAlignedBoundingBox"]["center"]["z"]
        agentx = agent_pos["x"]
        agentz = agent_pos["z"]
        d = math.sqrt((dx-agentx)**2 + (dz-agentz)**2)  # 距离
        
        sxz = size["x"] * size["z"]
        sxy = size["x"] * size["y"]
        szy = size["y"] * size["z"]
        s = max(sxz, sxy, szy)  # 最大表面积
        
        if d != 0:
            rate = v / d
        else:
            rate = 0
        
        # 判断是否可导航
        isnavigable = False
        if obj["visible"] == True:
            if v < 0.01:  # 小物体
                isnavigable = False
                if s > 0.5 and d < 10:
                    isnavigable = True
                elif s > 0.15 and d < 4:
                    isnavigable = True
                elif s > 0.08 and d < 2.5:
                    isnavigable = True 
                elif v > 0.005 and d < 2:
                    isnavigable = True 
                elif v > 0.001 and d < 1.5:
                    isnavigable = True
                elif d < 1:
                    isnavigable = True
            else:  # 大物体
                isnavigable = True
                if rate <= 0.02:
                    isnavigable = False
                    if s > 0.5 and d < 10:
                        isnavigable = True
                    elif s > 0.15 and d < 4:
                        isnavigable = True
                    elif s > 0.08 and d < 2.5:
                        isnavigable = True 
                    elif v > 0.005 and d < 2:
                        isnavigable = True 
                    elif v > 0.001 and d < 1.5:
                        isnavigable = True
                    elif d < 1:
                        isnavigable = True
        
        return {
            "objectId": obj["objectId"],
            "objectType": obj["objectType"],
            "visible": obj["visible"],
            "volume": v,
            "s": s,
            "distance": d,
            "rate": rate,
            "isnavigable": isnavigable
        }
    
    # 分析冰箱
    print("\n--- 分析冰箱 ---")
    fridge = fridge_metadata["objects"][0]
    agent_pos = fridge_metadata["agent"]["position"]
    fridge_analysis = analyze_object(fridge, agent_pos)
    
    print(f"冰箱体积: {fridge_analysis['volume']:.4f}")
    print(f"冰箱表面积: {fridge_analysis['s']:.4f}")
    print(f"冰箱距离: {fridge_analysis['distance']:.4f}")
    print(f"冰箱rate: {fridge_analysis['rate']:.4f}")
    print(f"冰箱是否可导航: {fridge_analysis['isnavigable']}")
    
    # 分析番茄
    print("\n--- 分析番茄 ---")
    tomato = fridge_metadata["objects"][1]
    tomato_analysis = analyze_object(tomato, agent_pos)
    
    print(f"番茄体积: {tomato_analysis['volume']:.4f}")
    print(f"番茄表面积: {tomato_analysis['s']:.4f}")
    print(f"番茄距离: {tomato_analysis['distance']:.4f}")
    print(f"番茄rate: {tomato_analysis['rate']:.4f}")
    print(f"番茄是否可导航: {tomato_analysis['isnavigable']}")
    
    # 分析不同距离下的冰箱
    print("\n--- 分析不同距离下的冰箱 ---")
    distances = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]
    for dist in distances:
        # 修改冰箱位置
        modified_fridge = fridge.copy()
        modified_fridge["axisAlignedBoundingBox"]["center"]["x"] = dist
        modified_fridge["axisAlignedBoundingBox"]["center"]["z"] = 0
        
        analysis = analyze_object(modified_fridge, agent_pos)
        print(f"距离{dist}m: 体积={analysis['volume']:.4f}, 表面积={analysis['s']:.4f}, rate={analysis['rate']:.4f}, 可导航={analysis['isnavigable']}")

def test_real_scenario():
    """测试真实场景"""
    print("\n=== 测试真实场景 ===")
    
    try:
        from data_engine.utils import get_volume_distance_rate
        
        # 模拟真实场景的metadata
        real_metadata = {
            "objects": [
                {
                    "objectId": "Fridge_1",
                    "objectType": "Fridge", 
                    "visible": True,
                    "axisAlignedBoundingBox": {
                        "size": {"x": 0.8, "y": 1.8, "z": 0.6},
                        "center": {"x": 2.0, "y": 0.9, "z": 1.5}
                    }
                },
                {
                    "objectId": "Cabinet_1",
                    "objectType": "Cabinet",
                    "visible": True, 
                    "axisAlignedBoundingBox": {
                        "size": {"x": 0.6, "y": 0.8, "z": 0.4},
                        "center": {"x": 1.0, "y": 0.4, "z": 0.8}
                    }
                },
                {
                    "objectId": "Tomato_1",
                    "objectType": "Tomato",
                    "visible": True,
                    "axisAlignedBoundingBox": {
                        "size": {"x": 0.05, "y": 0.05, "z": 0.05},
                        "center": {"x": 2.0, "y": 0.9, "z": 1.5}
                    }
                }
            ],
            "agent": {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0}
            }
        }
        
        # 调用真实的get_volume_distance_rate函数
        navigable_objects = get_volume_distance_rate(real_metadata)
        
        print("所有对象分析:")
        for obj in navigable_objects:
            print(f"- {obj['objectType']}: 体积={obj['volume']:.4f}, 距离={obj['distance']:.4f}, rate={obj['rate']:.4f}, 可导航={obj['isnavigable']}")
        
        # 筛选可导航对象
        navigable_list = [obj for obj in navigable_objects if obj['isnavigable'] and obj['objectType'] != 'Floor']
        print(f"\n可导航对象数量: {len(navigable_list)}")
        for obj in navigable_list:
            print(f"- {obj['objectType']} ({obj['objectId']})")
        
    except Exception as e:
        print(f"测试失败: {e}")

def test_robot_controller_navigable():
    """测试RobotController中的navigable_list生成"""
    print("\n=== 测试RobotController中的navigable_list生成 ===")
    
    try:
        from data_engine.robot_task_planner import RobotController
        
        # 创建模拟控制器
        class MockController:
            def __init__(self):
                self.last_event = type('MockEvent', (), {
                    'metadata': {
                        'objects': [
                            {
                                'objectId': 'Fridge_1',
                                'objectType': 'Fridge',
                                'visible': True,
                                'axisAlignedBoundingBox': {
                                    'size': {'x': 0.8, 'y': 1.8, 'z': 0.6},
                                    'center': {'x': 2.0, 'y': 0.9, 'z': 1.5}
                                }
                            },
                            {
                                'objectId': 'Cabinet_1',
                                'objectType': 'Cabinet',
                                'visible': True,
                                'axisAlignedBoundingBox': {
                                    'size': {'x': 0.6, 'y': 0.8, 'z': 0.4},
                                    'center': {'x': 1.0, 'y': 0.4, 'z': 0.8}
                                }
                            },
                            {
                                'objectId': 'Tomato_1',
                                'objectType': 'Tomato',
                                'visible': True,
                                'axisAlignedBoundingBox': {
                                    'size': {'x': 0.05, 'y': 0.05, 'z': 0.05},
                                    'center': {'x': 2.0, 'y': 0.9, 'z': 1.5}
                                }
                            }
                        ],
                        'agent': {'position': {'x': 0.0, 'y': 0.0, 'z': 0.0}},
                        'sceneBounds': {'size': {'x': 10, 'z': 10}}
                    }
                })()
        
        controller = MockController()
        metadata = controller.last_event.metadata
        model = "test_model"
        origin_path = "test_path"
        
        # 创建机器人控制器
        robot_controller = RobotController(controller, metadata, model, origin_path)
        print("✓ RobotController实例化成功")
        
        # 模拟get_volume_distance_rate函数
        def mock_get_volume_distance_rate(metadata):
            print("调用get_volume_distance_rate函数")
            result = [
                {
                    "objectId": "Fridge_1",
                    "objectType": "Fridge",
                    "visible": True,
                    "volume": 0.864,
                    "s": 1.44,
                    "distance": 2.5,
                    "rate": 0.3456,
                    "isnavigable": True
                },
                {
                    "objectId": "Cabinet_1",
                    "objectType": "Cabinet",
                    "visible": True,
                    "volume": 0.192,
                    "s": 0.48,
                    "distance": 1.28,
                    "rate": 0.1499,
                    "isnavigable": True
                },
                {
                    "objectId": "Tomato_1",
                    "objectType": "Tomato",
                    "visible": True,
                    "volume": 0.0001,
                    "s": 0.0025,
                    "distance": 2.5,
                    "rate": 0.0001,
                    "isnavigable": False
                }
            ]
            print(f"get_volume_distance_rate返回 {len(result)} 个对象")
            for obj in result:
                print(f"  - {obj['objectType']}: isnavigable={obj['isnavigable']}")
            return result
        
        import data_engine.robot_task_planner as rtp
        rtp.get_volume_distance_rate = mock_get_volume_distance_rate
        
        # 调用initial_navigable_list方法
        print("\n调用initial_navigable_list方法...")
        navigable_list = robot_controller.initial_navigable_list()
        
        print(f"\n最终navigable_list包含 {len(navigable_list)} 个对象:")
        for obj in navigable_list:
            print(f"  - {obj['objectType']} ({obj['objectId']})")
        
        # 检查是否有冰箱
        fridge_in_list = any(obj['objectType'] == 'Fridge' for obj in navigable_list)
        print(f"\n冰箱是否在navigable_list中: {fridge_in_list}")
        
        if not fridge_in_list:
            print("❌ 问题确认：冰箱不在navigable_list中")
            print("可能的原因：")
            print("1. get_volume_distance_rate返回的冰箱isnavigable=False")
            print("2. initial_navigable_list的过滤逻辑有问题")
            print("3. 真实场景中冰箱的metadata与模拟不同")
        else:
            print("✅ 冰箱在navigable_list中")
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_real_metadata():
    """测试真实场景的metadata"""
    print("\n=== 测试真实场景的metadata ===")
    
    try:
        # 尝试加载真实的metadata文件
        metadata_path = "data_engine/taskgenerate/kitchens/FloorPlan3/metadata.json"
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            print(f"加载真实metadata，包含 {len(metadata[0]['objects'])} 个对象")
            
            # 查找冰箱
            fridge_objects = [obj for obj in metadata[0]['objects'] if obj['objectType'] == 'Fridge']
            print(f"找到 {len(fridge_objects)} 个冰箱对象")
            
            for i, fridge in enumerate(fridge_objects):
                print(f"\n冰箱 {i+1}:")
                print(f"  objectId: {fridge['objectId']}")
                print(f"  visible: {fridge['visible']}")
                if 'axisAlignedBoundingBox' in fridge:
                    size = fridge['axisAlignedBoundingBox']['size']
                    center = fridge['axisAlignedBoundingBox']['center']
                    volume = size['x'] * size['y'] * size['z']
                    print(f"  体积: {volume:.4f}")
                    print(f"  位置: ({center['x']:.2f}, {center['y']:.2f}, {center['z']:.2f})")
            
            # 查找番茄
            tomato_objects = [obj for obj in metadata[0]['objects'] if obj['objectType'] == 'Tomato']
            print(f"\n找到 {len(tomato_objects)} 个番茄对象")
            
            for i, tomato in enumerate(tomato_objects):
                print(f"\n番茄 {i+1}:")
                print(f"  objectId: {tomato['objectId']}")
                print(f"  visible: {tomato['visible']}")
                if 'axisAlignedBoundingBox' in tomato:
                    size = tomato['axisAlignedBoundingBox']['size']
                    center = tomato['axisAlignedBoundingBox']['center']
                    volume = size['x'] * size['y'] * size['z']
                    print(f"  体积: {volume:.4f}")
                    print(f"  位置: ({center['x']:.2f}, {center['y']:.2f}, {center['z']:.2f})")
        else:
            print(f"metadata文件不存在: {metadata_path}")
            
    except Exception as e:
        print(f"测试失败: {e}")

def suggest_solutions():
    """建议解决方案"""
    print("\n=== 解决方案建议 ===")
    
    print("1. 调整距离阈值:")
    print("   - 当前冰箱距离2.5m，可能超出某些距离条件")
    print("   - 建议增加距离阈值或调整rate判断逻辑")
    
    print("\n2. 调整rate阈值:")
    print("   - 当前rate=0.02的阈值可能过于严格")
    print("   - 建议将rate阈值从0.02调整到0.01或更低")
    
    print("\n3. 针对大型物体的特殊处理:")
    print("   - 冰箱等大型物体应该有特殊的判断逻辑")
    print("   - 可以基于物体类型进行特殊处理")
    
    print("\n4. 增加调试信息:")
    print("   - 在get_volume_distance_rate函数中添加详细日志")
    print("   - 输出每个对象的判断过程")

def main():
    """主函数"""
    print("开始分析navigable_list问题...")
    
    analyze_navigable_objects()
    test_real_scenario()
    test_robot_controller_navigable()
    test_real_metadata()
    suggest_solutions()
    
    print("\n🎉 分析完成！")

if __name__ == "__main__":
    main() 