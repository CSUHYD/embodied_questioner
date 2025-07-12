from ai2thor.controller import Controller
import random
import math
import re
import time
import threading
import copy
from PIL import Image
import sys
import os
# from vlmCall import 
from vlmCall_ollama import VLMAPI
from utils import save_data_to_json,save_image,clear_folder,load_json,get_volume_distance_rate

from baseAction import BaseAction
from RocAgent import RocAgent       
import json

def load_prompt_config(config_path="config/prompt_config.json"):
    """加载 prompt 配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Config file {config_path} not found, using default config")
        return 

# 默认配置
PROMPT_CONFIG = load_prompt_config()


class SceneManager:
    def __init__(self, timeout=40):
        self.timeout = timeout

    def initialize_scene(self, scene_diagonal, origin_pos_path, scene):
        controller = Controller( 
            agentMode="default",                
            visibilityDistance=scene_diagonal, 
            scene=scene,
            gridSize=0.1,                      
            snapToGrid=True,                   
            rotateStepDegrees=90,               
            renderDepthImage=False,            
            renderInstanceSegmentation=False,   
            width=1600,  
            height=900, 
            fieldOfView=90,                    
        )
        
        if scene!='FloorPlan22':
            pos=load_json(origin_pos_path)
            position=pos["position"]
            rotation=pos["rotation"]  
            horizon=pos["cameraHorizon"]   
            
            controller.step(
                action="Teleport",
                position=position,
                rotation=rotation,
                horizon=horizon,
                standing=True
            )
            
        if scene=='FloorPlan6':
            controller.step(action='MoveLeft',moveMagnitude=0.2)
            controller.step(action='MoveAhead',moveMagnitude=1.5)
            controller.step(action='RotateRight',degrees=90)
            controller.step(action='MoveAhead',moveMagnitude=1.5)
            controller.step(action='MoveAhead',moveMagnitude=2)
            controller.step(action='RotateRight',degrees=90)
            controller.step(action='MoveAhead',moveMagnitude=1.5)
            controller.step(action='MoveAhead',moveMagnitude=2)
            controller.step(action='RotateRight',degrees=120)
        if scene=='FloorPlan22':
            controller.step(action='MoveAhead',moveMagnitude=1.5)
            controller.step(action='RotateRight',degrees=90)
            controller.step(action='MoveAhead',moveMagnitude=1.5)
            controller.step(action='MoveAhead',moveMagnitude=1)
            controller.step(action='RotateRight',degrees=150)
        if scene=='FloorPlan12':
            controller.step(action='RotateRight',degrees=180)
        if scene=='FloorPlan21':
            controller.step(action='RotateRight',degrees=180)
        if scene=='FloorPlan15':
            controller.step(action='MoveRight',moveMagnitude=0.7)
            controller.step(action='MoveAhead',moveMagnitude=1.3)
            controller.step(action='RotateRight',degrees=180)
        if scene=='FloorPlan17':
            controller.step(action='MoveAhead',moveMagnitude=1)
            controller.step(action='RotateRight',degrees=180)  
        if scene=='FloorPlan25':
            controller.step(action='MoveBack',moveMagnitude=1)
        if scene=="FloorPlan26":
            controller.step(action='RotateLeft',degrees=90)    
        
        metadata=controller.last_event.metadata
        
        return controller, metadata

    def run_initial_scene(self, scene_diagonal, origin_pos_path, scene, retry_limit=3):
        controller = None
        metadata = None
        retry_count = 0

        def init_task():
            nonlocal controller
            nonlocal metadata
            controller, metadata = self.initialize_scene(scene_diagonal, origin_pos_path, scene) 
            
        init_thread = threading.Thread(target=init_task)

        init_thread.start()

        init_thread.join(self.timeout) 

        if init_thread.is_alive():
            print(f"Initialization exceeded {self.timeout} seconds, retrying...")
            retry_count += 1
            controller, metadata = self.initialize_scene(scene_diagonal, origin_pos_path, scene)
            return controller, metadata
        else:
            print("Initialization succeeded") 
            return controller, metadata


class TaskPlanner:
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or PROMPT_CONFIG

    def init_plan_task(self, taskname, environment_description):
        """首次任务规划"""
        systext = self.config["task_planning"]["systext"]
        usertext = self.config["task_planning"]["usertext"].format(
            taskname=taskname,
            environment_description=environment_description
        )
        llmapi = VLMAPI(self.model)
        planning_result = llmapi.vlm_request(systext, usertext)
        subtasks = self._parse_subtasks(planning_result)
        return subtasks

    def plan_task(self, current_state, feedback, environment_description):
        """执行任务过程中遇到问题时重新规划。current_state/feedback/环境描述可用于 prompt"""
        systext = self.config.get("replan_task", {}).get("systext", "You are a mobile robot task planner. Your job is to replan the task based on the current state and feedback.")
        usertext = self.config.get("replan_task", {}).get("usertext", "Current State: {current_state}\nFeedback: {feedback}\nEnvironment Description: {environment_description}\n\nPlease replan the remaining subtasks. Output format:\n<Subtask1> [action] [target_object]</Subtask1>\n...").format(
            current_state=current_state,
            feedback=feedback,
            environment_description=environment_description
        )
        llmapi = VLMAPI(self.model)
        planning_result = llmapi.vlm_request(systext, usertext)
        subtasks = self._parse_subtasks(planning_result)
        return subtasks

    def _parse_subtasks(self, planning_result):
        import re
        subtask_pattern = r'<Subtask(\d+)>\s*(.*?)\s*</Subtask\1>'
        matches = re.findall(subtask_pattern, planning_result, re.DOTALL)
        subtasks = []
        for match in matches:
            subtask_num, action_description = match
            subtasks.append({
                "subtask_id": int(subtask_num),
                "action": action_description.strip(),
                "objectId": "",
                "objectType": "",
                "baseaction": "",
                "reward": 1,
                "relatedObject": []
            })
        return subtasks

class ObservationGenerator:
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or PROMPT_CONFIG

    def generate_observation(self, image_path):
        systext = self.config["observation"]["systext"]
        usertext = self.config["observation"]["usertext"]
        llmapi = VLMAPI(self.model)
        observation = llmapi.vlm_request(systext, usertext, image_path)
        return observation

class RobotController:
    def __init__(self, controller, metadata, model, origin_path, config=None):
        self.controller = controller
        self.metadata = metadata
        self.model = model
        self.origin_path = origin_path
        self.observation_generator = ObservationGenerator(model, config)
        self.task_planner = TaskPlanner(model, config)

    def save_initial_observation_image(self):
        event = self.controller.last_event
        init_image_path = f"{self.origin_path}/0_init_observe.png"
        os.makedirs(os.path.dirname(init_image_path), exist_ok=True)
        save_image(event, init_image_path)
        return init_image_path

    def generate_observation(self, image_path):
        return self.observation_generator.generate_observation(image_path)

    def plan_task(self, taskname, environment_description):
        """任务规划：将任务分解为子任务"""
        return self.task_planner.plan_task(taskname, environment_description)


if __name__=="__main__":
    env="taskgenerate"
    model = "qwen2.5vl:32b" # use gpt-4o to generate trajectories
    # you can set timeout for AI2THOR init here.
    timeout=40           

    ###### step1. choose the task type here ####################
    tasktype="pickup_and_put"
    room_type = ['kitchens','living_rooms','bedrooms','bathrooms']
    room = 'kitchens'
    scene = 'FloorPlan1'
    #### generate trajectories ##########
    metadata_path=f"data_engine/{env}/{room}/{scene}/metadata.json"
    print("metadata_path:",metadata_path)
    generate_task=f"data_engine/{tasktype}_task_metadata/{scene}.json"
    print("task_metadata_path:",generate_task)
    
    metadata=load_json(metadata_path)
    metadata=metadata[0]
    tasks=load_json(generate_task)[0]

    for instruction_idx, task in enumerate(tasks, start=0):                                                            
        print("\n\n*********************************************************************")
        print(f"Scene:{scene} Task_Type: {tasktype} Processing_Task: {instruction_idx}")
        print("*********************************************************************\n")

        task=tasks[instruction_idx]
        print("task:",task)
        
        start_time = time.time()
        origin_path=f"data/data_{task['tasktype']}/{scene}_{task['tasktype']}_{instruction_idx}"
        
        scene_size= metadata["sceneBounds"]["size"]
        scene_diagonal = math.sqrt(scene_size["x"]**2 + scene_size["z"]**2)
        origin_pos_path=f"data_engine/{env}/{room}/{scene}/originPos.json" 
        
        max_retries=2
        error_paths = []  
        for attempt in range(max_retries + 1): 
            try:
                scene_manager = SceneManager(timeout)
                controller, metadata=scene_manager.run_initial_scene(scene_diagonal, origin_pos_path, scene)

                # 封装后的机器人控制器
                robot_controller = RobotController(controller, metadata, model, origin_path)
                # 步骤1：保存初始观察图片
                init_image_path = robot_controller.save_initial_observation_image()
                # 步骤2：生成observation
                observation = robot_controller.generate_observation(init_image_path)
                print("[Observation]", observation)
                
                # 步骤3：任务规划
                taskname = task["taskname"]
                subtasks = robot_controller.task_planner.init_plan_task(taskname, observation)
                print("[Task Planning]", subtasks)
                
                # 后续步骤可继续扩展
                
                # o1stylegenerate=O1StyleGenerate(
                #     controller,scene,origin_path,metadata,task,model=model
                # )
                # o1stylegenerate.initial_navigable_list()
                
                # # json_path=f"{origin_path}/metadata/0_metadata.json"
                # # o1stylegenerate.generate_o1style_data["round_metadata"].append(json_path)
                # # save_data_to_json(o1stylegenerate.metadata,json_path)
                # # o1stylegenerate.generate_o1style_data["round_navigable_list"].append(o1stylegenerate.navigable_list)

                
                # o1stylegenerate.generate_o1style_data["task_metadata"]=task
                
                # o1stylegenerate.generate_o1style_data["scene"]=scene
                # o1stylegenerate.generate_o1style_data["tasktype"]=tasktype 
                # o1stylegenerate.generate_o1style_data["instruction_idx"]=instruction_idx
                
                # o1stylegenerate.generate_one_o1style_data(plan_num,correct_num)
                
                # end_time = time.time()

                # execution_time = end_time - start_time
                # print(f"Execution time: {execution_time:.4f} seconds") 
                
                # o1stylegenerate.generate_o1style_data["time"]=execution_time

                # path=f"{origin_path}/{scene}_{task['tasktype']}_{instruction_idx}_{trajectory_idx}.json"
                
                # save_data_to_json(o1stylegenerate.generate_o1style_data,path)
                # print("generate_o1style_data save:",{path})
                
                # controller.stop()
                # break

            except Exception as e:
                print(f"Error:{e},try again.")
                clear_folder(origin_path)
            
                if attempt == max_retries - 1: 
                    print(f"Retry {max_retries} times, jump the task.")
                    error_paths.append(origin_path)  
                    save_data_to_json(error_paths,"./wrong_generte_path_list.json")
                    continue
