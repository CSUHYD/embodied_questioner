#!/usr/bin/env python3
"""
场景随机化功能测试脚本

用于测试AI2THOR场景物品位置随机化功能
"""

import os
import sys
import json
import logging

# 添加task_planner路径到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 添加data_engine路径到sys.path
data_engine_path = os.path.join(os.path.dirname(current_dir), 'data_engine')
if data_engine_path not in sys.path:
    sys.path.insert(0, data_engine_path)

from ai2thor.controller import Controller
from scene_randomizer import SceneRandomizer, DEFAULT_RANDOMIZE_CONFIG
from utils import load_json

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def test_scene_randomizer():
    """测试场景随机化功能"""
    logging.info("Starting scene randomizer test...")
    
    # 测试配置
    test_config = {
        "enabled": True,
        "seed": 42,  # 固定种子以便重现结果
        "randomize_ratio": 0.6,  # 随机化60%的物品
        "safe_distance": 0.2,
        "max_attempts": 5,
        "moveable_types": [
            "Apple", "Bread", "Egg", "Lettuce", "Potato", "Tomato",
            "Cup", "Mug", "Plate", "Bowl", "Knife", "Fork", "Spoon",
            "Bottle", "Can", "Box"
        ]
    }
    
    try:
        # 创建随机化器
        randomizer = SceneRandomizer(test_config)
        logging.info(f"Created randomizer with config: enabled={randomizer.enabled}")
        
        # 初始化AI2THOR控制器
        controller = Controller(
            agentMode="default",
            visibilityDistance=1.5,
            scene="FloorPlan3",  # 使用FloorPlan3作为测试场景
            gridSize=0.1,
            snapToGrid=True,
            rotateStepDegrees=90,
            renderDepthImage=False,
            renderInstanceSegmentation=False,
            width=1600,
            height=900,
            fieldOfView=90
        )
        
        logging.info("AI2THOR controller initialized successfully")
        
        # 获取随机化前的物品状态
        initial_objects = controller.last_event.metadata.get("objects", [])
        moveable_objects_before = [
            {
                "id": obj["objectId"],
                "type": obj["objectType"],
                "position": obj["position"],
                "pickupable": obj.get("pickupable", False)
            }
            for obj in initial_objects
            if obj.get("objectType", "") in test_config["moveable_types"] and obj.get("pickupable", False)
        ]
        
        logging.info(f"Found {len(moveable_objects_before)} moveable objects before randomization")
        for obj in moveable_objects_before[:5]:  # 只显示前5个
            logging.info(f"  - {obj['type']} at {obj['position']}")
        
        # 执行随机化
        success = randomizer.randomize_scene_objects(controller, "FloorPlan3")
        
        if success:
            logging.info("Scene randomization completed successfully!")
            
            # 获取随机化后的物品状态
            final_objects = controller.last_event.metadata.get("objects", [])
            moveable_objects_after = [
                {
                    "id": obj["objectId"],
                    "type": obj["objectType"],
                    "position": obj["position"],
                    "pickupable": obj.get("pickupable", False)
                }
                for obj in final_objects
                if obj.get("objectType", "") in test_config["moveable_types"] and obj.get("pickupable", False)
            ]
            
            logging.info(f"Found {len(moveable_objects_after)} moveable objects after randomization")
            
            # 比较位置变化
            moved_count = 0
            for before_obj in moveable_objects_before:
                for after_obj in moveable_objects_after:
                    if before_obj["id"] == after_obj["id"]:
                        before_pos = before_obj["position"]
                        after_pos = after_obj["position"]
                        
                        # 计算距离
                        distance = ((before_pos["x"] - after_pos["x"])**2 + 
                                  (before_pos["y"] - after_pos["y"])**2 + 
                                  (before_pos["z"] - after_pos["z"])**2)**0.5
                        
                        if distance > 0.1:  # 如果移动距离超过0.1单位
                            moved_count += 1
                            logging.info(f"  {before_obj['type']} moved {distance:.2f} units")
                        break
            
            logging.info(f"Total objects moved: {moved_count}/{len(moveable_objects_before)}")
            
            # 测试可开启物品随机化
            randomizer.randomize_openable_objects(controller)
            logging.info("Openable objects randomization completed")
            
        else:
            logging.error("Scene randomization failed!")
            
        # 清理
        controller.stop()
        logging.info("Test completed successfully")
        
        return success
        
    except Exception as e:
        logging.error(f"Test failed with error: {str(e)}")
        return False

def create_test_scene_config():
    """创建测试用的场景配置文件"""
    test_config_path = os.path.join(current_dir, "config", "test_scene_config.json")
    
    test_config = {
        "controller_config": {
            "agentMode": "default",
            "gridSize": 0.1,
            "snapToGrid": True,
            "rotateStepDegrees": 90,
            "renderDepthImage": False,
            "renderInstanceSegmentation": False,
            "width": 1600,
            "height": 900,
            "fieldOfView": 90
        },
        "randomization": {
            "enabled": True,  # 启用测试
            "seed": 12345,
            "randomize_ratio": 0.5,
            "safe_distance": 0.2,
            "max_attempts": 8,
            "moveable_types": [
                "Apple", "Bread", "Egg", "Lettuce", "Potato", "Tomato",
                "Cup", "Mug", "Plate", "Bowl", "Knife", "Fork", "Spoon",
                "Bottle", "Can", "Box", "Newspaper", "Book", "RemoteControl"
            ]
        }
    }
    
    # 确保config目录存在
    config_dir = os.path.dirname(test_config_path)
    os.makedirs(config_dir, exist_ok=True)
    
    # 保存测试配置
    with open(test_config_path, 'w', encoding='utf-8') as f:
        json.dump(test_config, f, indent=4, ensure_ascii=False)
    
    logging.info(f"Test configuration saved to: {test_config_path}")
    return test_config_path

if __name__ == "__main__":
    logging.info("="*60)
    logging.info("AI2THOR Scene Randomizer Test")
    logging.info("="*60)
    
    # 创建测试配置
    test_config_path = create_test_scene_config()
    
    # 运行测试
    success = test_scene_randomizer()
    
    if success:
        logging.info("All tests passed! ✅")
        logging.info("\n使用方法:")
        logging.info("1. 修改 task_planner/config/scene_config.json 中的 randomization.enabled 为 true")
        logging.info("2. 调整 randomize_ratio 控制随机化比例 (0-1)")
        logging.info("3. 设置 seed 为固定值以获得可重现的结果，或设为 null 获得完全随机")
        logging.info("4. 运行正常的任务程序，场景物品位置将自动随机化")
    else:
        logging.error("Tests failed! ❌")
        sys.exit(1)