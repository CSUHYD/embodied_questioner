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

def load_scene_config(config_path="config/scene_config.json"):
    """加载场景配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Scene config file {config_path} not found, using default config")
        return {}

# 默认配置
PROMPT_CONFIG = load_prompt_config()
SCENE_CONFIG = load_scene_config()


class SceneManager:
    def __init__(self, timeout=40, scene_config=None):
        self.timeout = timeout
        self.scene_config = scene_config or SCENE_CONFIG
        
        # 从配置文件加载场景配置
        self.scene_configs = self.scene_config.get("scene_configs", {})
        self.room_configs = self.scene_config.get("room_configs", {})
        self.controller_config = self.scene_config.get("controller_config", {})

    def get_scene_paths(self, env, room, scene, tasktype):
        """生成场景相关的路径"""
        metadata_path = f"data_engine/{env}/{room}/{scene}/metadata.json"
        origin_pos_path = f"data_engine/{env}/{room}/{scene}/originPos.json"
        generate_task = f"data_engine/{tasktype}_task_metadata/{scene}.json"
        
        return {
            'metadata_path': metadata_path,
            'origin_pos_path': origin_pos_path,
            'generate_task': generate_task
        }

    def get_floorplans_by_room(self, room):
        """根据房间类型获取对应的楼层平面图列表"""
        if room not in self.room_configs:
            return []
            
        room_config = self.room_configs[room]
        floorplans = room_config.get("floorplans", [])
        
        # 生成FloorPlan名称
        if room == 'kitchens':
            return [f"FloorPlan{i}" for i in floorplans]
        elif room == 'living_rooms':
            return [f"FloorPlan{i}" for i in floorplans]
        elif room == 'bedrooms':
            return [f"FloorPlan{i}" for i in floorplans]
        elif room == 'bathrooms':
            return [f"FloorPlan{i}" for i in floorplans]
        else:
            return []

    def calculate_scene_diagonal(self, metadata):
        """计算场景对角线距离"""
        scene_size = metadata["sceneBounds"]["size"]
        return math.sqrt(scene_size["x"]**2 + scene_size["z"]**2)

    def initialize_scene(self, scene_diagonal, origin_pos_path, scene):
        """初始化场景"""
        # 使用配置文件中的控制器配置
        controller = Controller( 
            agentMode=self.controller_config.get("agentMode", "default"),
            visibilityDistance=scene_diagonal, 
            scene=scene,
            gridSize=self.controller_config.get("gridSize", 0.1),
            snapToGrid=self.controller_config.get("snapToGrid", True),
            rotateStepDegrees=self.controller_config.get("rotateStepDegrees", 90),
            renderDepthImage=self.controller_config.get("renderDepthImage", False),
            renderInstanceSegmentation=self.controller_config.get("renderInstanceSegmentation", False),
            width=self.controller_config.get("width", 1600),
            height=self.controller_config.get("height", 900),
            fieldOfView=self.controller_config.get("fieldOfView", 90),
        )
        
        # 设置初始位置（除了FloorPlan22）
        if scene != 'FloorPlan22':
            pos = load_json(origin_pos_path)
            position = pos["position"]
            rotation = pos["rotation"]  
            horizon = pos["cameraHorizon"]   
            
            controller.step(
                action="Teleport",
                position=position,
                rotation=rotation,
                horizon=horizon,
                standing=True
            )
        
        # 执行场景特定的初始化动作
        self._execute_scene_specific_actions(controller, scene)
        
        metadata = controller.last_event.metadata
        return controller, metadata

    def _execute_scene_specific_actions(self, controller, scene):
        """执行场景特定的初始化动作"""
        if scene in self.scene_configs:
            for action_config in self.scene_configs[scene]:
                action = action_config["action"]
                if "moveMagnitude" in action_config:
                    controller.step(action=action, moveMagnitude=action_config["moveMagnitude"])
                elif "degrees" in action_config:
                    controller.step(action=action, degrees=action_config["degrees"])

    def run_initial_scene(self, scene_diagonal, origin_pos_path, scene, retry_limit=3):
        """运行场景初始化，支持超时和重试"""
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

    def load_scene_metadata(self, metadata_path):
        """加载场景元数据"""
        metadata = load_json(metadata_path)
        return metadata[0] if metadata else None

    def load_scene_tasks(self, generate_task):
        """加载场景任务"""
        tasks = load_json(generate_task)
        return tasks[0] if tasks else []


class TaskPlanner:
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or PROMPT_CONFIG

    def plan_high_level_subgoals(self, taskname, environment_description, memory_text=None):
        """
        调用 high_level_task_planning prompt，输出高层子目标 <SubgoalN> 标签
        """
        systext = self.config["high_level_task_planning"]["systext"]
        history_info = ""
        if memory_text:
            history_info = f"History:\n{memory_text}\n"
        usertext = self.config["high_level_task_planning"]["usertext"].format(
            history_info=history_info,
            taskname=taskname,
            environment_description=environment_description
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 解析 <SubgoalN> 标签，支持“子目标: 描述”格式
        import re
        subgoal_pattern = r'<Subgoal\d+>(.*?)</Subgoal\d+>'
        matches = re.findall(subgoal_pattern, result, re.DOTALL)
        subgoals = [m.strip() for m in matches]
        return subgoals

    def plan_executable_subtasks(self, subgoal, context=None):
        """
        调用 executable_task_planning prompt，将高层子目标细化为可执行动作序列 <SubtaskN> 标签
        """
        systext = self.config["executable_task_planning"]["systext"]
        usertext = self.config["executable_task_planning"]["usertext"].format(
            subgoal=subgoal,
            context=context or ""
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 解析 <SubtaskN> 标签
        import re
        subtask_pattern = r'<Subtask(\d+)>\s*\[(.*?)\]\s*\[(.*?)\]\s*</Subtask\1>'
        matches = re.findall(subtask_pattern, result, re.DOTALL)
        subtasks = []
        for match in matches:
            subtask_num, action, objtype = match
            subtasks.append({
                "subtask_id": int(subtask_num),
                "action": action.strip(),
                "objectId": "",
                "objectType": objtype.strip()
            })
        return subtasks


    def _parse_subtasks(self, planning_result):
        import re
        subtask_pattern = r'<Subtask(\d+)>\s*(.*?)\s*</Subtask\1>'
        matches = re.findall(subtask_pattern, planning_result, re.DOTALL)
        subtasks = []
        for match in matches:
            subtask_num, action_description = match
            # 提取 [action] [object] 格式
            action_type = ""
            object_type = ""
            action_obj_pattern = r'\[(.*?)\]\s*\[(.*?)\]'
            m = re.search(action_obj_pattern, action_description)
            if m:
                action_type = m.group(1).strip()
                object_type = m.group(2).strip()
            else:
                # 兼容只写了 action 或格式不标准的情况
                action_type = action_description.strip()
            subtasks.append({
                "subtask_id": int(subtask_num),
                "action": action_type,
                "objectId": "",
                "objectType": object_type
            })
        return subtasks

    def replan_based_on_user_response(self, taskname, observation, user_response, memory_text=None, navigable_list=None):
        """
        根据用户回答生成新的plan（subgoals或subtasks）。
        """
        prompt_cfg = self.config.get("replan_by_user_response")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        navigable_str = ""
        if navigable_list:
            types = list(set([item["objectType"] for item in navigable_list]))
            navigable_str = ", ".join(types)
        usertext = usertext.format(
            taskname=taskname,
            observation=observation or "",
            user_response=user_response or "",
            memory_text=memory_text or "",
            navigable_str=navigable_str
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 复用高层subgoal的正则解析
        import re
        subgoal_pattern = r'<Subgoal\d+>(.*?)</Subgoal\d+>'
        matches = re.findall(subgoal_pattern, result, re.DOTALL)
        subgoals = [m.strip() for m in matches]
        return subgoals


class ObservationGenerator:
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or PROMPT_CONFIG

    def generate_observation(self, image_path, navigable_list=None):
        # 借鉴 o1StyleGenerate，Observation 只需简要描述可见物体，不需要物体关系，输出 <Observation>...</Observation>
        # 获取可见类别
        navigable_categories = []
        if navigable_list:
            navigable_categories = list(set([item["objectType"] for item in navigable_list]))
        systext = self.config["observation"]["systext"]
        usertext = self.config["observation"].get("usertext", "").format(navigable_categories=navigable_categories)
        llmapi = VLMAPI(self.model)
        observation = llmapi.vlm_request(systext, usertext, image_path)
        return observation

class QuestionGenerator:
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or PROMPT_CONFIG

    def generate_general_question_for_plan(self, taskname, subgoals, observation=None):
        """
        针对初始任务规划（subgoals）和observation，自动提出一个general类型的问题。
        """
        prompt_cfg = self.config.get("general_plan_question")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        subgoals_str = "\n".join([f"- {g}" for g in subgoals])
        usertext = usertext.format(taskname=taskname, subgoals=subgoals_str, observation=observation or "")
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        import re
        m = re.search(r'QUESTION:\s*(.*)', result)
        question = m.group(1).strip() if m else result.strip()
        return question

    def should_ask_question_vlm(self, taskname, observation=None, planning=None, memory_text=None, navigable_list=None, error_message=None):
        """
        由VLM判断是否需要提问，并返回(should_ask, type, question)
        """
        import re
        prompt_cfg = self.config["question_judge"]
        systext = prompt_cfg["systext"]
        # 直接将变量显式输入
        navigable_str = ""
        if navigable_list:
            types = list(set([item["objectType"] for item in navigable_list]))
            navigable_str = ", ".join(types)
        usertext = prompt_cfg["usertext"].format(
            taskname=taskname,
            observation=observation or "",
            planning=planning or "",
            memory_text=memory_text or "",
            navigable_str=navigable_str,
            error_message=error_message or ""
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        ask = re.search(r'ASK:\s*(yes|no)', result, re.IGNORECASE)
        qtype = re.search(r'TYPE:\s*(clarification|help|general)', result, re.IGNORECASE)
        question = re.search(r'QUESTION:\s*(.*)', result)
        should_ask = ask and ask.group(1).strip().lower() == "yes"
        question_type = qtype.group(1).strip().lower() if qtype else "general"
        question_text = question.group(1).strip() if question else ""
        return should_ask, question_type, question_text


class UserResponseHandler:
    def __init__(self, model, taskname, plan, memory, config=None):
        self.model = model
        self.taskname = taskname
        self.plan = plan
        self.memory = memory
        self.config = config or PROMPT_CONFIG

    def init_response(self, user_response):
        """
        综合当前task、规划、问答历史和用户回答，判断是否需要replan。
        返回 (need_replan: bool, reason: str)
        """
        # 这里可以用LLM判断，也可以用规则。先给出LLM prompt方案：
        prompt_cfg = self.config.get("user_response_replan_judge")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]

        plan_str = "\n".join([str(p) for p in self.plan]) if isinstance(self.plan, list) else str(self.plan)
        memory_str = "\n".join([m["content"] if isinstance(m, dict) and "content" in m else str(m) for m in self.memory]) if isinstance(self.memory, list) else str(self.memory)
        usertext = usertext.format(
            taskname=self.taskname,
            plan=plan_str,
            memory=memory_str,
            user_response=user_response
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        import re
        m = re.search(r'REPLAN:\s*(yes|no)', result, re.IGNORECASE)
        reason_m = re.search(r'REASON:\s*(.*)', result)
        need_replan = m and m.group(1).strip().lower() == "yes"
        reason = reason_m.group(1).strip() if reason_m else result.strip()
        return need_replan, reason

    def get_user_response(self, question):
        """模拟或实际获取用户回答。实际部署时可替换为input()或UI交互。"""
        user_response = input("😁：请输入你的回答：")
        # 这里可替换为实际交互
        return user_response


class RobotController:
    def __init__(self, controller, metadata, model, origin_path, config=None):
        self.memory = []  # 长期记忆
        self.controller = controller
        self.metadata = metadata
        self.model = model
        self.origin_path = origin_path
        self.observation_generator = ObservationGenerator(model, config)
        self.task_planner = TaskPlanner(model, config)
        self.question_generator = QuestionGenerator(model, config)
        self.user_response_handler = UserResponseHandler(model, None, None, self.memory, config)
        # 添加navigable_list相关属性
        self.navigable_list = []
        self.round = 1
        self.his_objects_list = []
        # 添加提问相关属性
        self.failed_attempts = 0
        self.last_question = None
        self.user_responses = []
        # 新增：统一历史记录字典
        self.history = {
            "observation": [],
            "planning": [],
            "qa": []
        }


    def add_memory(self, entry, memory_type):
        """
        存储记忆内容，memory_type为类别（如'planning'、'question'、'answer'等），entry为内容。
        """
        self.memory.append({"type": memory_type, "content": entry})

    def get_memory_text(self, max_steps=10, type_filter=None):
        """
        返回最近的max_steps条记忆内容，可选按type过滤。
        """
        if type_filter:
            filtered = [m["content"] for m in self.memory if m["type"] == type_filter]
            return "\n".join(filtered[-max_steps:])
        else:
            return "\n".join(m["content"] for m in self.memory[-max_steps:])

    def initial_navigable_list(self):
        """初始化可导航对象列表"""
        self.metadata = self.controller.last_event.metadata
        list_obj = get_volume_distance_rate(self.metadata)
        for item in list_obj:
            if item["isnavigable"] and item["objectType"] != "Floor":
                objectType = item["objectType"]
                objectId = item["objectId"]
                visibleTimes = 1
                choseTimes = 0
                obj_navigable = {
                    "objectType": objectType,
                    "objectId": objectId,
                    "visibleTimes": visibleTimes,
                    "choseTimes": choseTimes
                }
                self.navigable_list.append(obj_navigable)
        return self.navigable_list

    def update_navigable_list_vtime(self):
        """更新可导航对象列表的可见次数"""
        self.metadata = self.controller.last_event.metadata
        list_obj = get_volume_distance_rate(self.metadata)
        for item in list_obj:
            if item["isnavigable"]:
                found = False
                for last_item in self.navigable_list:
                    if last_item["objectId"] == item["objectId"]:
                        last_item["visibleTimes"] += 1
                        found = True
                        break
                    
                if not found:
                    new_item = {
                        "objectType": item["objectType"],
                        "objectId": item["objectId"],
                        "visibleTimes": 1,
                        "choseTimes": 0
                    }
                    self.navigable_list.append(new_item)
        return self.navigable_list

    def get_object_types_from_navigable_list(self):
        """从可导航列表中获取对象类型"""
        object_types = [item['objectType'] for item in self.navigable_list]
        unique_object_types = list(set(object_types))
        return unique_object_types

    def update(self):
        """更新控制器状态"""
        self.metadata = self.controller.last_event.metadata
        self.navigable_list = self.update_navigable_list_vtime()

    def save_initial_observation_image(self):
        event = self.controller.last_event
        init_image_path = f"{self.origin_path}/0_init_observe.png"
        os.makedirs(os.path.dirname(init_image_path), exist_ok=True)
        save_image(event, init_image_path)
        return init_image_path

    def generate_observation(self, image_path):
        # 传递 navigable_list 以便 Observation 只描述可导航类别
        # 初始化可导航列表
        self.navigable_list = self.initial_navigable_list()
        obs = self.observation_generator.generate_observation(image_path, self.navigable_list)
        # 记录 observation 历史，增加 round
        self.history["observation"].append({"round": self.round, "content": obs})
        return obs

    def plan_high_level_task(self, taskname, environment_description, memory_text=None):
        """首次任务规划：将任务分解为子任务，不使用memory"""
        subtasks = self.task_planner.plan_high_level_subgoals(
            taskname, environment_description, memory_text=memory_text
        )
        self.add_memory(f"Initial Task Planning: {subtasks}", "planning")
        # 记录 planning 历史，增加 round
        self.history["planning"].append({"round": self.round, "content": subtasks})
        return subtasks

    def plan_task(self, taskname, environment_description):
        """任务规划：将任务分解为子任务，并将memory作为上下文"""
        memory_text = self.get_memory_text()
        subtasks = self.task_planner.init_plan_task(
            taskname, environment_description, navigable_list=self.navigable_list, memory_text=memory_text
        )
        self.add_memory(f"Task Planning: {subtasks}", "planning")
        # 记录 planning 历史，增加 round
        self.history["planning"].append({"round": self.round, "content": subtasks})
        return subtasks

    def format_subtasks_as_tags(self, subtasks):
        """将subtasks列表格式化为 <SubtaskN> 标签字符串"""
        tag_strs = []
        for sub in subtasks:
            tag_strs.append(f"<Subtask{sub['subtask_id']}> [{sub['action']}] [{sub['objectType']}] </Subtask{sub['subtask_id']}>\n")
        return "".join(tag_strs)

    def get_user_response(self, question):
        """模拟或实际获取用户回答。实际部署时可替换为input()或UI交互。"""
        user_response = input("😁：请输入你的回答：")
        # 这里可替换为实际交互
        return user_response

    def get_navigable_list(self):
        """获取可导航列表"""
        return self.navigable_list

    def add_to_history(self, object_info):
        """添加对象到历史列表"""
        self.his_objects_list.append(object_info)
        self.add_memory(f"History: {object_info}", "history")


    def receive_user_response(self, response):
        """接收用户回答"""
        self.user_responses.append({
            "question": self.last_question,
            "response": response,
            "timestamp": time.time()
        })
        # 记录问答历史，增加 round
        self.history["qa"].append({"round": self.round, "question": self.last_question, "response": response, "type": "answer"})
        print(f"👤 用户回答: {response}")
        self.add_memory(f"Robot Question: {self.last_question}. User Response: {response}.", "qa")

    def try_ask_question(self, taskname, observation, subtasks):
        # 组织 observation
        obs_str = observation if observation else ""
        # 格式化 subtasks 为多行可读文本
        planning_str = ""
        if isinstance(subtasks, list) and len(subtasks) > 0 and isinstance(subtasks[0], dict):
            if 'subgoal_id' in subtasks[0]:
                planning_str = "\n".join([f"Subgoal{sub['subgoal_id']}: {sub.get('subgoal','')} - {sub.get('description','')}" for sub in subtasks])
            elif 'subtask_id' in subtasks[0]:
                planning_str = "\n".join([f"Subtask{sub['subtask_id']}: {sub.get('action','')} - {sub.get('objectType','')}" for sub in subtasks])
            else:
                planning_str = str(subtasks)
        elif subtasks:
            planning_str = str(subtasks)
        memory_text = self.get_memory_text()
        should_ask, question_type, question = self.question_generator.should_ask_question_vlm(
            taskname=taskname,
            observation=obs_str,
            planning=planning_str,
            navigable_list=self.navigable_list
        )
        if should_ask:
            self.last_question = question
            self.add_memory(f"Question({question_type}): {question}", "question")
            # 记录问答历史，增加 round
            self.history["qa"].append({"round": self.round, "question": question, "type": question_type})
            print(f"\n🤖 机器人提问({question_type}): {question}")
            return question
        return None

    def increment_failed_attempts(self):
        """增加失败次数"""
        self.failed_attempts += 1
        self.add_memory(f"Failed attempt #{self.failed_attempts}", "failed_attempts")

    def reset_failed_attempts(self):
        """重置失败次数"""
        self.failed_attempts = 0
        self.add_memory("Reset failed attempts", "failed_attempts")

    def get_question_history(self):
        """获取提问历史"""
        return self.user_responses

    def ask_general_question_for_plan(self, taskname, subgoals, observation=None):
        """
        针对初始任务规划和observation，自动提出general类型的问题并存入memory。
        """
        question = self.question_generator.generate_general_question_for_plan(taskname, subgoals, observation=observation)
        self.last_question = question
        self.add_memory(f"General Question: {question}", "question")
        print(f"\n🤖 机器人提出general问题: {question}")
        return question

    def set_user_response_handler_context(self, taskname, plan):
        self.user_response_handler.taskname = taskname
        self.user_response_handler.plan = plan
        self.user_response_handler.memory = self.memory


if __name__=="__main__":
    env="taskgenerate"
    model = "qwen2.5vl:32b" # use gpt-4o to generate trajectories
    # you can set timeout for AI2THOR init here.        

    ###### step1. choose the task type here ####################
    tasktype="pickup_and_put"
    room_type = ['kitchens','living_rooms','bedrooms','bathrooms']
    room = 'kitchens'
    scene = 'FloorPlan3'
    
    # 创建场景管理器
    scene_manager = SceneManager()
    
    # 获取场景相关路径
    paths = scene_manager.get_scene_paths(env, room, scene, tasktype)
    metadata_path = paths['metadata_path']
    origin_pos_path = paths['origin_pos_path']
    generate_task = paths['generate_task']
    
    print("metadata_path:", metadata_path)
    print("task_metadata_path:", generate_task)
    
    # 加载场景元数据和任务
    metadata = scene_manager.load_scene_metadata(metadata_path)
    tasks = scene_manager.load_scene_tasks(generate_task)

    for instruction_idx, task in enumerate(tasks, start=0):                                                            
        print("\n\n*********************************************************************")
        print(f"Scene:{scene} Task_Type: {tasktype} Processing_Task: {instruction_idx}")
        print("*********************************************************************\n")

        task=tasks[instruction_idx]
        print("task:",task)
        
        start_time = time.time()
        origin_path=f"data/data_{task['tasktype']}/{scene}_{task['tasktype']}_{instruction_idx}"
        
        # 计算场景对角线距离
        scene_diagonal = scene_manager.calculate_scene_diagonal(metadata)
        
        max_retries=2
        error_paths = []  
        for attempt in range(max_retries + 1): 
            try:
                # 使用场景管理器初始化场景
                controller, metadata = scene_manager.run_initial_scene(scene_diagonal, origin_pos_path, scene)

                # 封装后的机器人控制器
                robot_controller = RobotController(controller, metadata, model, origin_path)
                
                # 步骤1：保存初始观察图片
                init_image_path = robot_controller.save_initial_observation_image()
                
                # 步骤2：生成observation
                observation = robot_controller.generate_observation(init_image_path)
                print("[Observation]", observation)
                
                # 步骤3：任务规划（只用高层taskname和observation）
                taskname = task["taskname"]  # 例如 "把苹果放进冰箱"
                subtasks = robot_controller.plan_high_level_task(taskname, observation)
                print("[Initial Task Planning]", subtasks)
                
                # 检查是否需要提问
                question = robot_controller.ask_general_question_for_plan(taskname, subtasks)
                
                if question:
                    robot_controller.set_user_response_handler_context(taskname, subtasks)
                    # 获取用户回答
                    user_response = robot_controller.user_response_handler.get_user_response(question)
                    robot_controller.receive_user_response(user_response)

                    print("[Re-planning based on user response]")
                    # 先判断是否需要replan
                    need_replan, reason = robot_controller.user_response_handler.init_response(user_response)
                    if need_replan:
                        new_subtasks = robot_controller.task_planner.replan_based_on_user_response(
                            taskname, observation, user_response, robot_controller.get_memory_text(), robot_controller.navigable_list
                        )
                        print("[Re-planned Task]", new_subtasks)
                        robot_controller.add_memory(f"Re-planned Task: {new_subtasks}", "planning")
                        # 你可以在此处继续后续执行新规划的逻辑
                    else:
                        print(f"无需replan，原因：{reason}")

                # 步骤4：获取可导航对象类型（用于后续规划）
                navigable_types = robot_controller.get_object_types_from_navigable_list()
                print("[Navigable Types]", navigable_types)
                
                # 步骤5：更新可导航列表
                robot_controller.update()
                updated_navigable_list = robot_controller.get_navigable_list()
                print("[Updated Navigable List]", len(updated_navigable_list), "objects")
                
                # 后续步骤：循环执行子任务
                # for subtask in subtasks:
                #     print("执行子任务:", subtask)
                #     # 这里可以根据subtask["action"]和["objectType"]等，调用底层控制API
                #     # 每步可观测、可replan
                #     # 伪代码：
                #     # result = robot_controller.execute_subtask(subtask)
                #     # if result == "need_replan":
                #     #     observation = robot_controller.generate_observation(...)
                #     #     subtasks = robot_controller.plan_task(taskname, observation)
                #     #     break
                
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
