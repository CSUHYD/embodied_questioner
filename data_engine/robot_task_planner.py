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
import functools
import logging


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
        self.subgoals = []  # 当前高层子目标

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
        self.subgoals = subgoals
        return subgoals

    def plan_executable_subtasks(self, subgoal, context=None):
        """
        调用 executable_task_planning prompt，将高层子目标细化为可执行动作序列。
        严格解析 <SubtaskN> [action] [target_object]</SubtaskN> 格式，action必须在支持的动作类型列表中。
        """
        supported_actions = [
            "search", "open", "close", "break", "cook", "slice", "toggle_on", "toggle_off", "dirty", "clean", "fill", "empty", "use_up", "pick_up", "put"
        ]
        systext = self.config["executable_task_planning"]["systext"]
        usertext = self.config["executable_task_planning"]["usertext"].format(
            subgoal=subgoal,
            context=context or ""
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 解析 <SubtaskN> [action] [target_object]</SubtaskN> 格式
        import re
        subtask_pattern = r'<Subtask\d+>\s*([a-zA-Z_]+)\s+([^<\n]+)\s*</Subtask\d+>'
        matches = re.findall(subtask_pattern, result)
        subtasks = []
        for action, objectType in matches:
            action = action.strip()
            objectType = objectType.strip()
            if action in supported_actions:
                subtasks.append({
                    "action": action,
                    "objectType": objectType
                })
        return subtasks

    def replan_based_on_user_response(self, taskname, observation, question, response, subgoal):
        """
        根据用户回答生成新的plan（subgoals）。
        """
        prompt_cfg = self.config.get("replan_by_user_response")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        usertext = usertext.format(
            taskname=taskname,
            observation=observation or "",
            question=question or "",
            response=response or "",
            subgoal=subgoal or ""
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 复用高层subgoal的正则解析
        import re
        subgoal_pattern = r'<Subgoal\d+>(.*?)</Subgoal\d+>'
        matches = re.findall(subgoal_pattern, result, re.DOTALL)
        subgoals = [m.strip() for m in matches]
        self.subgoals = subgoals  # 更新成员变量
        return subgoals

    def subgoals_to_subtasks(self, subgoals, context=None):
        """
        Break down high-level subgoals into a sequence of executable subtasks with decisionmaking, following o1stylegenerate style.

        Args:
            subgoals (list): List of high-level subgoal strings.
            context (str, optional): Additional context for planning.

        Returns:
            list: List of dicts, each with keys:
                - 'action': The executable action (str)
                - 'objectType': The target object type (str)
                - 'decisionmaking': The decision string, e.g. 'navigate to Table'
        
        Example output:
            [
                {'action': 'navigate to', 'objectType': 'Table', 'decisionmaking': 'navigate to Table'},
                {'action': 'open', 'objectType': 'Fridge', 'decisionmaking': 'open Fridge'},
                ...
            ]
        """
        all_subtasks = []
        for idx, subgoal in enumerate(subgoals):
            # Decompose each subgoal into executable subtasks
            subtasks = self.plan_executable_subtasks(subgoal, context=context)
            for subtask in subtasks:
                action = subtask.get("action", "")
                objectType = subtask.get("objectType", "")
                # Format decision string (no <DecisionMaking> tag)
                if action and objectType:
                    decisionmaking = f"{action} {objectType}"
                elif action:
                    decisionmaking = f"{action}"
                else:
                    decisionmaking = ""
                all_subtasks.append({
                    "action": action,
                    "objectType": objectType,
                    "decisionmaking": decisionmaking
                })
        return all_subtasks


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

    def save_initial_observation_image(self, controller, origin_path):
        event = controller.last_event
        init_image_path = f"{origin_path}/0_init_observe.png"
        os.makedirs(os.path.dirname(init_image_path), exist_ok=True)
        save_image(event, init_image_path)
        return init_image_path

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

    # def should_ask_question_vlm(self, taskname, observation=None, planning=None, memory_text=None, navigable_list=None, error_message=None):
    #     """
    #     由VLM判断是否需要提问，并返回(should_ask, type, question)
    #     """
    #     import re
    #     prompt_cfg = self.config["question_judge"]
    #     systext = prompt_cfg["systext"]
    #     # 直接将变量显式输入
    #     navigable_str = ""
    #     if navigable_list:
    #         types = list(set([item["objectType"] for item in navigable_list]))
    #         navigable_str = ", ".join(types)
    #     usertext = prompt_cfg["usertext"].format(
    #         taskname=taskname,
    #         observation=observation or "",
    #         planning=planning or "",
    #         memory_text=memory_text or "",
    #         navigable_str=navigable_str,
    #         error_message=error_message or ""
    #     )
    #     llmapi = VLMAPI(self.model)
    #     result = llmapi.vlm_request(systext, usertext)
    #     ask = re.search(r'ASK:\s*(yes|no)', result, re.IGNORECASE)
    #     qtype = re.search(r'TYPE:\s*(clarification|help|general)', result, re.IGNORECASE)
    #     question = re.search(r'QUESTION:\s*(.*)', result)
    #     should_ask = ask and ask.group(1).strip().lower() == "yes"
    #     question_type = qtype.group(1).strip().lower() if qtype else "general"
    #     question_text = question.group(1).strip() if question else ""
    #     return should_ask, question_type, question_text


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
        # user_response = input("😁：请输入你的回答：")
        # 这里可替换为实际交互
        user_response = 'please find the plate first'
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

    def generate_observation(self, image_path):
        # 传递 navigable_list 以便 Observation 只描述可导航类别
        # 初始化可导航列表
        self.navigable_list = self.initial_navigable_list()
        obs = self.observation_generator.generate_observation(image_path, self.navigable_list)
        return obs

    def plan_high_level_task(self, taskname, environment_description, memory_text=None):
        """首次任务规划：将任务分解为子任务，不使用memory"""
        subgoals = self.task_planner.plan_high_level_subgoals(
            taskname, environment_description, memory_text=memory_text
        )
        self.add_memory(f"Initial Task Planning: {subgoals}", "planning")
        return subgoals

    def get_navigable_list(self):
        """获取可导航列表"""
        return self.navigable_list

    def receive_user_response(self, response):
        """接收用户回答"""
        logging.info("[ROBOT QUESTION] %s. User Response: %s.", self.last_question, response)

    def ask_general_question_for_plan(self, taskname, subgoals, observation=None):
        """
        针对初始任务规划和observation，自动提出general类型的问题并存入memory。
        """
        question = self.question_generator.generate_general_question_for_plan(taskname, subgoals, observation=observation)
        self.last_question = question
        self.add_memory(f"General Question: {question}", "question")
        logging.info("[GENERAL QUESTION] %s", question)
        return question

    def set_user_response_handler_context(self, taskname, plan):
        self.user_response_handler.taskname = taskname
        self.user_response_handler.plan = plan
        self.user_response_handler.memory = self.memory

    def rank_possible_placement_locations(self, target, observation, navigable_list, max_num=3):
        """
        输入目标、环境描述、可导航物体列表，调用VLM/LLM排序最有可能放置目标的位置
        返回排序后的objectType列表，长度不超过max_num
        """
        categories = list(set([item["objectType"] for item in navigable_list]))
        prompt_cfg = self.observation_generator.config.get("placement_ranking", {})
        systext = prompt_cfg.get("systext", "")
        usertext_template = prompt_cfg.get("usertext", "")
        usertext = usertext_template.format(
            target=target,
            observation=observation,
            categories=", ".join(categories),
            max_num=max_num
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 解析结果为列表
        result = result.strip('[]')
        result = result.replace(" ", "").replace("'", "").replace('"', "")
        possible_list = [x for x in result.split(',') if x in categories]
        return possible_list[:max_num]

    def navigate_to_object(self, object_id):
        """
        导航到指定objectId的位置。假设有RocAgent或controller的navigate方法。
        """
        # 这里假设你有RocAgent或类似API
        # 你可以根据实际情况替换为你的底层导航实现
        target_object = next((item for item in self.metadata["objects"] if item["objectId"] == object_id), None)
        if target_object is None:
            print(f"[NAVIGATION] ObjectId {object_id} not found in metadata.")
            return False
        # 假设有self.rocAgent
        if hasattr(self, "rocAgent"):
            self.rocAgent.navigate(target_object)
        else:
            # 如果没有rocAgent，可以在此处集成controller的导航API
            print(f"[NAVIGATION] Navigating to object {object_id} (type: {target_object['objectType']})")
            # 伪代码：self.controller.step(action="Navigate", objectId=object_id)
        return True

    def navigate_to_possible_locations(self, possible_list, navigable_list):
        """
        依次导航到possible_list中的objectType对应的位置。
        """
        for object_type in possible_list:
            object_id = next((item["objectId"] for item in navigable_list if item["objectType"] == object_type), None)
            if object_id is None:
                print(f"[NAVIGATION] No objectId found for objectType {object_type}.")
                continue
            print(f"[NAVIGATION] Navigating to {object_type} (objectId: {object_id}) ...")
            success = self.navigate_to_object(object_id)
            # 可选：每次导航后可插入检测是否已找到目标的逻辑
            # if self.check_target_found():
            #     print("[NAVIGATION] Target found, stopping navigation.")
            #     break

    def verify_task_completed(self):
        """
        判断当前任务是否完成。可根据metadata、flag、reward等，也可扩展为VLM判定。
        返回True表示完成，False表示未完成。
        """
        # 示例1：基于metadata的flag
        if hasattr(self, "metadata") and isinstance(self.metadata, dict):
            if self.metadata.get("flag") == "success":
                return True
        # 示例2：基于reward
        if hasattr(self, "reward") and getattr(self, "reward", 0) >= getattr(self, "totalreward", 1):
            return True
        # 示例3：可扩展为VLM判定
        # result = self.check_completion_via_vlm(...)
        # if result: return True
        return False

    def execute_subtasks(self, subtasks_with_decision, navigable_list=None):
        """
        遍历subtasks_with_decision，自动执行导航或输出交互动作。
        navigable_list可选，未传则自动获取。
        每步执行后自动判定是否完成，完成则提前终止。
        """
        if navigable_list is None:
            navigable_list = self.get_navigable_list()
        for subtask in subtasks_with_decision:
            action = subtask["action"]
            object_type = subtask["objectType"]
            decisionmaking = subtask["decisionmaking"]
            print(f"[EXECUTE] {decisionmaking}")

            if action.lower() in ["navigate to", "goto", "go to", "move to"]:
                object_id = next((item["objectId"] for item in navigable_list if item["objectType"] == object_type), None)
                if object_id:
                    self.navigate_to_object(object_id)
                else:
                    print(f"[WARNING] No objectId found for objectType {object_type} in navigable_list.")
            elif action.lower() in ["pickup", "pick up", "open", "close", "toggle"]:
                print(f"[INTERACT] Would perform {action} on {object_type} (需实现具体API)")
            else:
                print(f"[SKIP] Action {action} not recognized for auto-execution.")

            # 每步执行后判定是否完成
            if self.verify_task_completed():
                print("[COMPLETE] Task judged as completed, stopping further execution.")
                break
            else:
                print("[FAILURE]")


if __name__=="__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()]
    )
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
    
    logging.info("metadata_path: %s", metadata_path)
    logging.info("task_metadata_path: %s", generate_task)
    
    # 加载场景元数据和任务
    metadata = scene_manager.load_scene_metadata(metadata_path)
    tasks = scene_manager.load_scene_tasks(generate_task)

    for instruction_idx, task in enumerate(tasks, start=0):                                                            
        logging.info("\n\n*********************************************************************")
        logging.info(f"Scene:{scene} Task_Type: {tasktype} Processing_Task: {instruction_idx}")
        logging.info("*********************************************************************\n")

        task=tasks[instruction_idx]
        logging.info("task: %s", task)
        
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
                init_image_path = robot_controller.observation_generator.save_initial_observation_image(robot_controller.controller, robot_controller.origin_path)
                
                # 步骤2：生成observation
                observation = robot_controller.generate_observation(init_image_path)
                logging.info("[OBSERVATION] %s", observation)
                
                # 步骤3：高层任务规划（只用高层taskname和observation）
                taskname = task["taskname"]  # 例如 "把苹果放进冰箱"
                subgoals = robot_controller.plan_high_level_task(taskname, observation)
                logging.info("[INITIAL TASK PLANNING] %s", str(subgoals))
                
                # 检查是否需要提问
                question = robot_controller.ask_general_question_for_plan(taskname, subgoals)
                
                if question:
                    robot_controller.set_user_response_handler_context(taskname, subgoals)
                    # 获取用户回答
                    user_response = robot_controller.user_response_handler.get_user_response(question)
                    robot_controller.receive_user_response(user_response)

                    logging.info("[RE-PLANNING BASED ON USER RESPONSE]")
                    # 先判断是否需要replan
                    need_replan, reason = robot_controller.user_response_handler.init_response(user_response)
                    if need_replan:
                        old_subgoals = robot_controller.task_planner.subgoals
                        new_subgoals = robot_controller.task_planner.replan_based_on_user_response(
                            taskname, observation, robot_controller.last_question, user_response, subgoals
                        )
                        robot_controller.task_planner.subgoals = new_subgoals
                        logging.info("[REPLAN] Old subgoals: %s", old_subgoals)
                        logging.info("[REPLAN] New subgoals: %s", new_subgoals)
                        robot_controller.add_memory(f"{new_subgoals}", "planning")
                        # 你可以在此处继续后续执行新规划的逻辑
                    else:
                        logging.info("[NO REPLAN NEEDED] Reason: %s", reason)

                
                # 步骤4：底层任务规划：把subgoals细化为可执行subtasks，并生成decisionmaking
                # 遍历 subgoals
                #   把 subgoal 转化成可以执行决策decisionmaking，即机器人的 actions（包含find, navigate, interact等）
                #       遍历 actions
                #       Execute：执行action
                #       确认是否完成（通过截图+VLM）
                subtasks_with_decision = robot_controller.task_planner.subgoals_to_subtasks(subgoals)
                logging.info("[SUBTASKS WITH DECISION] %s", subtasks_with_decision)
                robot_controller.execute_subtasks(subtasks_with_decision)
                # 可选：每步执行后插入“确认是否完成”逻辑（如通过截图+VLM判断）
                # for subtask in subtasks_with_decision:
                #     # ...执行action后...
                #     # result = robot_controller.check_completion_via_vlm(...)
                #     # if result: break
                
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
                logging.error("[ERROR] %s, try again.", e)
                clear_folder(origin_path)
            
                if attempt == max_retries - 1: 
                    logging.warning("[RETRY %d TIMES, JUMP THE TASK]", max_retries)
                    error_paths.append(origin_path)  
                    save_data_to_json(error_paths,"./wrong_generte_path_list.json")
                    continue
