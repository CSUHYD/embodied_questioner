from ai2thor.controller import Controller
import math
import re
# import time  # 移除，不再需要用于qa_history时间戳
import threading
import sys
import os
import json
import logging

# 添加data_engine路径到sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
data_engine_path = os.path.join(os.path.dirname(current_dir), 'data_engine')
if data_engine_path not in sys.path:
    sys.path.insert(0, data_engine_path)

# 从data_engine导入
from vlmCall_ollama import VLMAPI
from utils import save_data_to_json,save_image,clear_folder,load_json,get_volume_distance_rate
from baseAction import BaseAction
from RocAgent import RocAgent

# 导入SessionManager
from session_manager import SessionManager


def get_data_engine_path():
    """获取data_engine目录的绝对路径"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(script_dir), 'data_engine')


def get_task_planner_path():
    """获取task_planner目录的绝对路径"""
    return os.path.dirname(os.path.abspath(__file__))


def get_project_root():
    """获取项目根目录的绝对路径"""
    data_engine_path = get_data_engine_path()
    return os.path.dirname(data_engine_path)


# 设置日志配置
def setup_logging(log_file=None):
    """设置日志配置，支持同时输出到控制台和文件"""
    handlers = [logging.StreamHandler()]  # 控制台输出
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))  # 文件输出
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
        force=True  # 强制重新配置
    )


def load_config_file(config_path, default_value=None, fallback_to_root=False):
    """通用配置文件加载函数"""
    if default_value is None:
        default_value = {}
    
    if not os.path.isabs(config_path):
        # 首先尝试task_planner目录下的config
        config_path_task_planner = os.path.join(get_task_planner_path(), config_path)
        if os.path.exists(config_path_task_planner):
            config_path = config_path_task_planner
        elif fallback_to_root:
            # 如果不存在且允许回退，尝试项目根目录下的config
            config_path = os.path.join(get_project_root(), config_path)
        else:
            config_path = config_path_task_planner
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logging.warning(f"Config file {config_path} not found, using default config")
        return default_value


def load_prompt_config(config_path="config/prompt_config.json"):
    """加载 prompt 配置文件"""
    return load_config_file(config_path, default_value={})


def load_scene_config(config_path="config/scene_config.json"):
    """加载场景配置文件"""
    return load_config_file(config_path, default_value={}, fallback_to_root=True)

# 默认配置
PROMPT_CONFIG = load_prompt_config()
SCENE_CONFIG = load_scene_config()


def parse_xml_tags(text, tag_name):
    """通用的XML标签解析函数"""
    pattern = f'<{tag_name}(\\d+)>(.*?)</{tag_name}\\1>'
    matches = re.findall(pattern, text, re.DOTALL)
    return [(int(num), content.strip()) for num, content in matches]


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
        data_engine_path = get_data_engine_path()
        # env 参数实际上是 "taskgenerate"，但目录结构是 taskgenerate/{room}/{scene}
        metadata_path = os.path.join(data_engine_path, f"taskgenerate/{room}/{scene}/metadata.json")
        origin_pos_path = os.path.join(data_engine_path, f"taskgenerate/{room}/{scene}/originPos.json")
        generate_task = os.path.join(data_engine_path, f"{tasktype}_task_metadata/{scene}.json")
        
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
        
        # 生成FloorPlan名称 - 所有房间类型都使用相同逻辑
        return [f"FloorPlan{i}" for i in floorplans]

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
            logging.warning(f"Initialization exceeded {self.timeout} seconds, retrying...")
            retry_count += 1
            controller, metadata = self.initialize_scene(scene_diagonal, origin_pos_path, scene)
            return controller, metadata
        else:
            logging.info("Initialization succeeded") 
            return controller, metadata

    def load_scene_metadata(self, metadata_path):
        """加载场景元数据"""
        metadata = load_json(metadata_path)
        return metadata[0] if metadata else None

    def load_scene_tasks(self, generate_task):
        """加载场景任务"""
        tasks = load_json(generate_task)
        return tasks[0] if tasks else []
        
    def _get_absolute_path(self, path):
        """获取绝对路径的工具函数"""
        if not os.path.isabs(path):
            return os.path.join(get_data_engine_path(), path)
        return path

    def load_test_tasks(self, test_tasks_path="test_tasks.json"):
        """加载测试任务配置文件"""
        test_tasks_path = self._get_absolute_path(test_tasks_path)
        try:
            tasks = load_json(test_tasks_path)
            logging.info(f"Loaded {len(tasks)} test tasks from {test_tasks_path}")
            return tasks
        except Exception as e:
            logging.error(f"Failed to load test tasks from {test_tasks_path}: {e}")
            return []
            
    def get_test_task_by_id(self, task_id, test_tasks_path="test_tasks.json"):
        """根据ID获取指定的测试任务"""
        tasks = self.load_test_tasks(test_tasks_path)
        for task in tasks:
            if task.get('id') == task_id:
                return task
        logging.error(f"Test task with ID '{task_id}' not found")
        return None



class TaskPlanner:
    def __init__(self, model, config=None):
        self.model = model
        self.config = config or PROMPT_CONFIG
        self.subgoals = []  # 当前高层子目标
        self.subtasks = []

    def plan_high_level_goals(self, taskname, environment_description, memory_text=None):
        """
        调用 high_level_task_planning prompt，输出高层子目标 <SubgoalN> 标签
        """
        systext = self.config["high_level_goal_planning"]["systext"]
        history_info = ""
        if memory_text:
            history_info = f"History:\n{memory_text}\n"
        usertext = self.config["high_level_goal_planning"]["usertext"].format(
            history_info=history_info,
            taskname=taskname,
            environment_description=environment_description
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        # 解析 <SubgoalN> 标签，支持"子目标: 描述"格式
        matches = parse_xml_tags(result, "Subgoal")
        subgoals = [content for _, content in matches]
        self.subgoals = subgoals
        return subgoals

    def plan_high_level_tasks(self, taskname, environment_description):
        """
        调用 high_level_task_planning prompt，输出高层subtask <SubtaskN> 标签（自然语言步骤）。
        """
        systext = self.config["high_level_task_planning"]["systext"]
        usertext = self.config["high_level_task_planning"]["usertext"].format(
            taskname=taskname,
            environment_description=environment_description
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        matches = parse_xml_tags(result, "Subtask")
        subtasks = [content for _, content in matches]
        self.subtasks = subtasks
        return subtasks


    def plan_executable_subtasks(self, subgoal_or_subtask, all_decisions, mode="goals"):
        """
        调用 executable_task_planning prompt，将高层子目标细化为可执行动作序列。
        严格解析 <SubtaskN> [action] [object1] [object2]</SubtaskN> 格式，put 动作支持两个参数。
        all_decisions: 已有的所有决策（action/objectType），本次输出不能与其重复。
        """
        supported_actions = [
            "search", "open", "close", "break", "cook", "slice", "toggle_on", "toggle_off", "dirty", "clean", "fill", "empty", "use_up", "pick_up", "put"
        ]
        all_decisions_str = "\n".join([f"{d['action']} {d['objectType']} {d.get('targetObject', None)}" for d in all_decisions]) if all_decisions else ""
        
        if mode == "tasks":
            prompt_key = "executable_task_planning_from_tasks"
            prompt_vars = {"subtask": subgoal_or_subtask, "supported_actions": supported_actions, "all_decisions": all_decisions_str}
        else:
            prompt_key = "executable_task_planning_from_goals"
            prompt_vars = {"subgoal": subgoal_or_subtask, "supported_actions": supported_actions, "all_decisions": all_decisions_str}
            
        systext = self.config[prompt_key]["systext"]
        usertext = self.config[prompt_key]["usertext"].format(**prompt_vars)
        
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        
        matches = parse_xml_tags(result, "Subtask")
        
        subtasks = []
        for _, content in matches:
            parts = content.strip().split()
            if not parts:
                continue
            
            action = parts[0]
            args = parts[1:]
            
            if action in supported_actions:
                # 假设第一个参数是objectType，第二个是targetObject（如果有的话）
                objectType = args[0] if len(args) > 0 else None
                targetObject = args[1] if len(args) > 1 else None

                # 去重检查
                if not any(d['action'] == action and d.get('objectType') == objectType and d.get('targetObject') == targetObject for d in all_decisions):
                    subtasks.append({
                        "action": action,
                        "objectType": objectType,
                        "targetObject": targetObject
                    })
        return subtasks


    def replan_subgoals_based_on_user_response(self, taskname, observation, question, response, subgoals):
        """
        根据用户回答，调用high_level_goal_planning prompt重新规划subgoals。
        """
        prompt_cfg = self.config.get("high_level_goal_planning")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        usertext = usertext.format(
            taskname=taskname,
            observation=observation or "",
            question=question or "",
            response=response or "",
            subgoals='\n'.join(subgoals) if subgoals else ""
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        matches = parse_xml_tags(result, "Subgoal")
        new_subgoals = [content for _, content in matches]
        self.subgoals = new_subgoals
        return new_subgoals

    def replan_subtasks_based_on_user_response(self, taskname, observation, qa_history, subtasks):
        """
        根据用户问答历史，重新规划subtasks，确保考虑用户的具体要求。
        
        Args:
            taskname: 任务名称
            observation: 环境观察
            qa_history: 问答历史字符串，格式为 "Q: ... A: ..."
            subtasks: 原始子任务列表
            
        Returns:
            list: 重新规划后的子任务列表
        """
        prompt_cfg = self.config.get("replan_subtasks_based_on_user_response")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        
        # 格式化原始计划
        subtasks_str = '\n'.join([f"- {task}" for task in subtasks]) if subtasks else ""
        
        # 从qa_history中提取最新的问答对
        latest_question = ""
        latest_response = ""
        if qa_history:
            qa_pairs = qa_history.split('\n')
            if len(qa_pairs) >= 2:
                # 获取最后一对问答
                for i in range(len(qa_pairs)-1, -1, -1):
                    if qa_pairs[i].startswith('Q: '):
                        latest_question = qa_pairs[i][3:]  # 去掉 "Q: " 前缀
                        if i+1 < len(qa_pairs) and qa_pairs[i+1].startswith('A: '):
                            latest_response = qa_pairs[i+1][3:]  # 去掉 "A: " 前缀
                        break
        
        usertext = usertext.format(
            taskname=taskname,
            environment_description=observation or "",
            question=latest_question,
            response=latest_response,
            subtasks=subtasks_str
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        matches = parse_xml_tags(result, "Subtask")
        new_subtasks = [content for _, content in matches]
        self.subtasks = new_subtasks
        return new_subtasks

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
        for subgoal in subgoals:
            # Decompose each subgoal into executable subtasks
            subtasks = self.plan_executable_subtasks(subgoal, all_subtasks, context=context, mode='goals')
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

    def decompose_high_level_action(self, action, object_type, context=""):
        """
        将高级动作(如clean, cook, heat)分解为原子动作序列
        
        Args:
            action: 高级动作名称 (如 "clean", "cook", "heat")
            object_type: 目标物体类型
            context: 额外上下文信息
            
        Returns:
            list: 原子动作序列
        """
        # 定义哪些动作需要分解
        high_level_actions = [
            "clean", "cook", "heat", "cool", "freeze", "wash", "rinse", 
            "prepare", "serve", "store", "organize", "arrange"
        ]
        
        if action.lower() not in high_level_actions:
            # 如果不是高级动作，返回原始动作
            return [{
                "action": action,
                "objectType": object_type,
                "targetObject": None,
                "decisionmaking": f"{action} {object_type}"
            }]
        
        # 准备支持的原子动作列表
        supported_actions = [
            "search", "navigate", "open", "close", "break", "cook", "slice", 
            "toggle_on", "toggle_off", "dirty", "clean", "fill", "empty", 
            "use_up", "pick_up", "put"
        ]
        
        # 准备prompt变量
        prompt_cfg = self.config.get("high_level_action_decomposition", {})
        systext = prompt_cfg.get("systext", "")
        usertext = prompt_cfg.get("usertext", "").format(
            action=action,
            object_type=object_type,
            context=context,
            supported_actions=", ".join(supported_actions)
        )
        
        # 调用VLM获取分解结果
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        
        # 解析VLM输出
        matches = parse_xml_tags(result, "Action")
        
        # 转换为decisions格式
        decisions = []
        for _, content in matches:
            parts = content.strip().split()
            if not parts:
                continue
                
            atomic_action = parts[0]
            args = parts[1:]
            
            if atomic_action in supported_actions:
                atomic_object_type = args[0] if len(args) > 0 else None
                target_object = args[1] if len(args) > 1 else None
                
                decision = {
                    "action": atomic_action,
                    "objectType": atomic_object_type,
                    "targetObject": target_object,
                    "decisionmaking": " ".join(parts)
                }
                decisions.append(decision)
        
        logging.info(f"[DECOMPOSE] {action} {object_type} -> {len(decisions)} atomic actions")
        for i, decision in enumerate(decisions, 1):
            logging.info(f"  {i}. {decision['decisionmaking']}")
            
        return decisions

    def subtasks_to_decisions(self, subtasks, qa_history=""):
        """
        将一组subtasks一次性转换为可执行的decisions序列。
        这个方法会考虑整体任务上下文，生成完整的执行计划。

        Args:
            subtasks: 子任务列表，每个子任务是一个字符串
            qa_history: 问答历史，用于优化决策生成

        Returns:
            list: 可执行的decisions列表
        """
        if not subtasks:
            return []

        # 1. 准备支持的动作列表
        supported_actions = [
            "search", "navigate", "open", "close", "break", "cook", "slice", "toggle_on", "toggle_off",
            "dirty", "clean", "fill", "empty", "use_up", "pick_up", "put"
        ]

        # 2. 准备prompt变量
        prompt_cfg = self.config.get("subtasks_to_decisions", {})
        systext = prompt_cfg.get("systext", "")
        usertext = prompt_cfg.get("usertext", "").format(
            subtasks="\n".join(f"- {task}" for task in subtasks),
            supported_actions=", ".join(supported_actions),
            qa_history=qa_history if qa_history else "No previous Q&A interactions"
        )

        # 3. 调用VLM获取执行计划
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)

        # 4. 解析VLM输出
        matches = parse_xml_tags(result, "Task")

        # 5. 转换为decisions格式，并处理高级动作分解
        decisions = []
        seen_actions = set()  # 用于去重
        
        for _, content in matches:
            parts = content.strip().split()
            if not parts:
                continue

            action = parts[0]
            args = parts[1:]
            objectType = args[0] if len(args) > 0 else None
            targetObject = args[1] if len(args) > 1 else None

            # 检查是否是高级动作，需要分解
            high_level_actions = [
                "clean", "cook", "heat", "cool", "freeze", "wash", "rinse", 
                "prepare", "serve", "store", "organize", "arrange"
            ]
            
            if action.lower() in high_level_actions:
                # 分解高级动作为原子动作序列
                logging.info(f"[HIGH-LEVEL] Decomposing {action} {objectType}")
                context = f"Current subtasks: {subtasks}"
                atomic_decisions = self.decompose_high_level_action(action, objectType, context)
                
                # 将分解后的原子动作添加到决策列表中（带去重）
                for atomic_decision in atomic_decisions:
                    atomic_action = atomic_decision["action"]
                    atomic_objectType = atomic_decision["objectType"]
                    atomic_targetObject = atomic_decision["targetObject"]
                    
                    # 创建去重键
                    if atomic_action == "put":
                        dedup_key = (atomic_action, atomic_objectType, atomic_targetObject)
                    else:
                        dedup_key = (atomic_action, atomic_objectType)
                    
                    # 检查是否重复
                    if dedup_key not in seen_actions:
                        decisions.append(atomic_decision)
                        seen_actions.add(dedup_key)
                    else:
                        logging.debug(f"[DEDUP] Skipping duplicate atomic action: {atomic_decision['decisionmaking']}")
            
            elif action in supported_actions:
                # 处理普通原子动作
                # 创建去重键
                if action == "put":
                    dedup_key = (action, objectType, targetObject)
                else:
                    dedup_key = (action, objectType)
                
                # 检查是否重复
                if dedup_key not in seen_actions:
                    decision = {
                        "action": action,
                        "objectType": objectType,
                        "targetObject": targetObject,
                        "decisionmaking": " ".join(parts)
                    }
                    decisions.append(decision)
                    seen_actions.add(dedup_key)
                else:
                    logging.debug(f"[DEDUP] Skipping duplicate action: {' '.join(parts)}")
            else:
                logging.warning(f"[UNKNOWN] Action {action} not in supported actions list")

        logging.info(f"[DECISIONS] Generated {len(decisions)} unique actions from {len(matches)} total actions")
        return decisions

    def judge_replan_need(self, taskname, plan, user_response):
        """
        判断是否需要重新规划
        返回 (need_replan: bool, reason: str)
        """
        prompt_cfg = self.config.get("user_response_replan_judge")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]

        plan_str = "\n".join([str(p) for p in plan]) if isinstance(plan, list) else str(plan)
        
        usertext = usertext.format(
            taskname=taskname,
            plan=plan_str,
            user_response=user_response
        )
        
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        
        def parse_replan_result(result):
            # 1. 先找所有 REPLAN: yes/no（允许前后有空格、大小写、换行）
            matches = re.findall(r'REPLAN\s*:\s*(yes|no)', result, re.IGNORECASE)
            if matches:
                return matches[0].strip().lower()
            # 2. 兜底：只要有yes/no字样，且不是reason里的
            result_lower = result.lower()
            lines = [line.strip() for line in result_lower.splitlines()]
            for line in lines:
                if line.startswith('replan') and 'yes' in line:
                    return 'yes'
                if line.startswith('replan') and 'no' in line:
                    return 'no'
            # 3. 再兜底：全文只要有yes/no
            if 'replan' in result_lower and 'yes' in result_lower:
                return 'yes'
            if 'replan' in result_lower and 'no' in result_lower:
                return 'no'
            # 4. 实在不行返回None
            return None
            
        replan_value = parse_replan_result(result)
        need_replan = replan_value == "yes"
        reason_m = re.search(r'REASON:\s*(.*)', result)
        reason = reason_m.group(1).strip() if reason_m else result.strip()
        return need_replan, reason

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

class QuestionAnswerHandler:
    """统一的问答处理类，集成问题生成、用户回答处理和重规划判断功能"""
    
    def __init__(self, model, taskname=None, plan=None, config=None):
        self.model = model
        self.taskname = taskname
        self.plan = plan
        self.config = config or PROMPT_CONFIG
        self.last_question = None
        
    def update_context(self, taskname=None, plan=None):
        """更新上下文信息"""
        if taskname is not None:
            self.taskname = taskname
        if plan is not None:
            self.plan = plan

    def generate_general_question_for_plan(self, taskname, subtasks, observation=None):
        """
        针对初始任务规划（subgoals）和observation，自动提出一个general类型的问题。
        """
        prompt_cfg = self.config.get("general_plan_question")
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        subtasks_str = "\n".join([f"- {g}" for g in subtasks])
        usertext = usertext.format(taskname=taskname, subtasks=subtasks_str, observation=observation or "")
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        m = re.search(r'QUESTION:\s*(.*)', result)
        question = m.group(1).strip() if m else result.strip()
        self.last_question = question
        return question

    def generate_clarification_question(self, taskname, current_step, issue_description):
        """
        生成澄清问题，用于在执行过程中遇到问题时询问用户
        """
        prompt_cfg = self.config.get("clarification_question", {})
        systext = prompt_cfg.get("systext", "Generate a clarification question based on the current situation.")
        usertext = prompt_cfg.get("usertext", "Task: {taskname}\nCurrent step: {current_step}\nIssue: {issue_description}\nGenerate a clarification question:")
        
        usertext = usertext.format(
            taskname=taskname,
            current_step=current_step,
            issue_description=issue_description
        )
        
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        m = re.search(r'QUESTION:\s*(.*)', result)
        question = m.group(1).strip() if m else result.strip()
        self.last_question = question
        return question

    def get_user_response(self, question):
        """获取用户回答并记录到历史中"""
        if question:
            print(f"🤖：{question}")
        user_response = input("😁：请输入你的回答：")
        
        return user_response

    def get_user_response_with_history(self, question):
        """
        获取用户回答并记录到历史中（不包含重规划判断）
        返回用户回答
        """
        user_response = self.get_user_response(question)
        return user_response

    def should_ask_question_for_decision(self, taskname, decision, remaining_decisions, navigable_objects=None, qa_history=""):
        """
        判断是否需要针对当前决策提问
        
        Args:
            taskname: 任务名称
            decision: 当前要执行的决策
            remaining_decisions: 剩余的决策列表
            navigable_objects: 可导航的对象列表
            qa_history: 问答历史，从外部传入
            
        Returns:
            tuple: (should_ask: bool, reason: str)
        """
        # 使用传入的qa_history，如果为空则使用空字符串
        if not qa_history:
            qa_history = ""
        
        # 准备prompt配置
        prompt_cfg = self.config.get("decision_question_judge", {})
        systext = prompt_cfg.get("systext", "You are a robot assistant. Your job is to decide whether you need to ask the user a question before executing a specific action.")
        usertext = prompt_cfg.get("usertext", "")
        
        # 格式化参数
        navigable_objects_str = ", ".join(navigable_objects) if navigable_objects else "None available"
        remaining_str = "\n".join([f"- {d.get('decisionmaking', d.get('action', '') + ' ' + d.get('objectType', ''))}" for d in remaining_decisions[:3]])
        
        usertext = usertext.format(
            taskname=taskname,
            decision=decision.get("decisionmaking", decision.get("action", "") + " " + decision.get("objectType", "")),
            remaining_decisions=remaining_str,
            navigable_objects=navigable_objects_str,
            qa_history=qa_history
        )
        
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        
        # 解析结果
        ask_match = re.search(r'ASK:\s*(yes|no)', result, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*(.*)', result, re.DOTALL)
        
        should_ask = ask_match and ask_match.group(1).strip().lower() == "yes" if ask_match else False
        reason = reason_match.group(1).strip() if reason_match else "No reason provided"
        
        return should_ask, reason
    
    def generate_decision_question(self, taskname, decision, remaining_decisions, navigable_objects=None):
        """
        为当前决策生成具体的问题
        
        Args:
            taskname: 任务名称
            decision: 当前决策
            remaining_decisions: 剩余决策列表
            navigable_objects: 可导航的对象列表
            
        Returns:
            str: 生成的问题
        """
        qa_history = self.get_qa_history()
        
        # 准备prompt配置
        prompt_cfg = self.config.get("decision_specific_question", {
            "systext": "You are a robot assistant. Your job is to generate a specific question about the current action to help clarify how to proceed.",
            "usertext": "You are working on the task: {taskname}\n\nYou are about to execute: {decision}\n\nRemaining actions: {remaining_decisions}\n\nAvailable objects: {navigable_objects}\n\nPrevious Q&A history:\n{qa_history}\n\nGenerate a specific question to ask the user about this action. The question should help clarify:\n- How to approach this specific action\n- Which objects to prioritize\n- Any preferences or special requirements\n\nPlease provide your question in the format:\nQUESTION: [your specific question]"
        })
        
        systext = prompt_cfg["systext"]
        usertext = prompt_cfg["usertext"]
        
        # 格式化参数
        navigable_objects_str = ", ".join(navigable_objects) if navigable_objects else "None available"
        remaining_str = "\n".join([f"- {d.get('decisionmaking', d.get('action', '') + ' ' + d.get('objectType', ''))}" for d in remaining_decisions[:3]])
        
        usertext = usertext.format(
            taskname=taskname,
            decision=decision.get("decisionmaking", decision.get("action", "") + " " + decision.get("objectType", "")),
            remaining_decisions=remaining_str,
            navigable_objects=navigable_objects_str,
            qa_history=qa_history
        )
        
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        
        # 提取问题
        question_match = re.search(r'QUESTION:\s*(.*)', result, re.DOTALL)
        if question_match:
            return question_match.group(1).strip()
        return result.strip()


class TaskVerificationHandler:
    """
    处理任务完成验证的类
    """
    
    def __init__(self, controller, model, observation_generator, origin_path):
        """
        初始化任务验证处理器
        
        Args:
            controller: AI2Thor控制器实例
            model: 使用的模型名称
            observation_generator: 观察生成器实例
            origin_path: 数据保存的根路径
        """
        self.controller = controller
        self.model = model
        self.observation_generator = observation_generator
        self.origin_path = origin_path
    
    def verify_task_completion(self, taskname, original_plan, image_path=None):
        """
        使用VLM验证任务是否成功完成
        
        Args:
            taskname: 任务名称
            original_plan: 原始计划列表
            image_path: 验证图片路径，如果为None则自动截图
        
        Returns:
            tuple: (is_success: bool, reason: str, confidence: str)
        """
        try:
            # 如果没有提供图片路径，则自动截图
            if image_path is None:
                verification_dir = f"{self.origin_path}/verification"
                os.makedirs(verification_dir, exist_ok=True)
                image_path = f"{verification_dir}/final_verification.png"
                save_image(self.controller.last_event, image_path)
                logging.info(f"[VERIFY] Saved verification image: {image_path}")
            
            # 准备prompt参数
            prompt_cfg = self.observation_generator.config.get("task_verification", {})
            systext = prompt_cfg.get("systext", "")
            usertext = prompt_cfg.get("usertext", "").format(
                taskname=taskname,
                original_plan="\n".join([f"- {plan}" for plan in original_plan])
            )
            
            # 调用VLM进行验证
            llmapi = VLMAPI(self.model)
            result = llmapi.vlm_request(systext, usertext, image_path)
            
            # 解析VLM返回结果
            success_match = re.search(r'SUCCESS:\s*(yes|no)', result, re.IGNORECASE)
            reason_match = re.search(r'REASON:\s*(.*?)(?=\nCONFIDENCE:|$)', result, re.DOTALL)
            confidence_match = re.search(r'CONFIDENCE:\s*(high|medium|low)', result, re.IGNORECASE)
            
            is_success = success_match and success_match.group(1).strip().lower() == "yes" if success_match else False
            reason = reason_match.group(1).strip() if reason_match else "No reason provided"
            confidence = confidence_match.group(1).strip().lower() if confidence_match else "unknown"
            
            logging.info(f"[VERIFY] Task verification result: SUCCESS={is_success}, CONFIDENCE={confidence}")
            logging.info(f"[VERIFY] Reason: {reason}")
            
            return is_success, reason, confidence
            
        except Exception as e:
            logging.error(f"[VERIFY] Error during task verification: {e}")
            return False, f"Verification failed due to error: {e}", "low"
    
    def save_verification_result(self, taskname, is_success, reason, confidence, verification_data=None):
        """
        保存验证结果到文件
        
        Args:
            taskname: 任务名称
            is_success: 是否成功
            reason: 验证原因
            confidence: 置信度
            verification_data: 其他验证数据
        """
        try:
            verification_dir = f"{self.origin_path}/verification"
            os.makedirs(verification_dir, exist_ok=True)
            
            result_data = {
                "task_name": taskname,
                "success": is_success,
                "reason": reason,
                "confidence": confidence,
                "timestamp": self._get_current_timestamp()
            }
            
            if verification_data:
                result_data.update(verification_data)
            
            result_file = f"{verification_dir}/verification_result.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            logging.info(f"[VERIFY] Saved verification result to: {result_file}")
            
        except Exception as e:
            logging.error(f"[VERIFY] Error saving verification result: {e}")
    
    def _get_current_timestamp(self):
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class RobotController:
    def __init__(self, controller, metadata, model, origin_path, config=None):
        self.controller = controller
        self.metadata = metadata
        self.model = model
        self.origin_path = origin_path
        self.config = config
        self.observation_generator = ObservationGenerator(model, config)
        self.task_planner = TaskPlanner(model, config)
        self.qa_handler = QuestionAnswerHandler(model, config=config)
        self.verification_handler = TaskVerificationHandler(controller, model, self.observation_generator, origin_path)
        
        # 初始化SessionManager - 统一管理所有会话数据
        session_save_path = os.path.join(origin_path, "session_logs") if origin_path else None
        self.session_manager = SessionManager(save_path=session_save_path)
        
        # 添加navigable_list相关属性
        self.navigable_list = []
        self.round = 1
        self.his_objects_list = []
        # 添加提问相关属性
        self.failed_attempts = 0
        self.rocAgent=RocAgent(controller)
        self.recent_interactions = {}  # 记录最近交互的对象ID，格式: {object_type: object_id}
        self.opened_containers_for_search = []  # 记录为搜索而打开的容器，需要在适当时机关闭

    # ==================== SessionManager 统一写入接口 ====================
    
    def add_qa_record(self, question: str, answer: str, context: str = None, question_type: str = "general") -> None:
        """统一的问答记录写入接口"""
        self.session_manager.add_qa_record(question, answer, context, question_type)
    
    def log_action_execution(self, action_type: str, action_params: dict, result: str, 
                           success: bool, object_id: str = None, scene_info: dict = None,
                           execution_time_ms: int = None) -> None:
        """统一的执行记录写入接口"""
        self.session_manager.add_execution_record(
            action_type=action_type,
            action_params=action_params,
            result=result,
            success=success,
            object_id=object_id,
            scene_info=scene_info,
            execution_time_ms=execution_time_ms
        )
    
    def log_failure(self, failure_type: str, description: str, context: dict, 
                   recovery_attempted: bool = False, recovery_successful: bool = False) -> None:
        """统一的失败记录写入接口"""
        self.session_manager.add_failure_record(
            failure_type=failure_type,
            description=description,
            context=context,
            recovery_attempted=recovery_attempted,
            recovery_successful=recovery_successful
        )
    
    def get_execution_history_summary(self, max_actions: int = 10) -> str:
        """获取执行历史摘要"""
        return self.session_manager.get_execution_history_summary(max_actions)
    
    def start_new_round(self) -> None:
        """开始新的执行轮次"""
        self.session_manager.start_new_round()
        self.round = self.session_manager.current_round

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

    def plan_high_level_goals(self, taskname, environment_description, memory_text=None):
        """首次任务规划：将任务分解为子任务，不使用memory"""
        subgoals = self.task_planner.plan_high_level_goals(
            taskname, environment_description, memory_text=memory_text
        )
        return subgoals
    
    def plan_high_level_tasks(self, taskname, environment_description):
        """
        首次任务规划：将任务分解为自然语言subtasks。
        """
        subtasks = self.task_planner.plan_high_level_tasks(
            taskname, environment_description
        )
        return subtasks

    def get_navigable_list(self):
        """获取可导航列表"""
        return self.navigable_list

    def ask_general_question_for_plan(self, taskname, subtasks, observation=None):
        """
        针对初始任务规划和observation，自动提出general类型的问题。
        """
        self.qa_handler.update_context(taskname=taskname, plan=subtasks)
        question = self.qa_handler.generate_general_question_for_plan(taskname, subtasks, observation=observation)
        if question:
            logging.info("[GENERAL QUESTION] %s", question)
        return question

    def process_user_response(self, question, subtasks, taskname=None):
        """
        处理完整的用户问答交互流程
        返回 (user_response, need_replan, reason)
        """
        # 获取用户回答并记录到SessionManager
        user_response = self.qa_handler.get_user_response_with_history(question)
        self.add_qa_record(question, user_response, context="decision_making", question_type="decision_clarification")
        logging.info("[USER RESPONSE] %s", user_response)
        
        # 使用TaskPlanner判断是否需要重规划
        need_replan, reason = self.task_planner.judge_replan_need(
            taskname=taskname,
            plan=subtasks,
            user_response=user_response
        )
        
        return user_response, need_replan, reason

    def get_qa_history(self):
        """
        获取问答历史，格式化为字符串。
        """
        return self.session_manager.get_qa_history_string()

    def ask_clarification_question(self, taskname, current_step, issue_description):
        """
        生成并处理澄清问题，返回用户回答
        """
        self.qa_handler.update_context(taskname=taskname, plan=None)
        question = self.qa_handler.generate_clarification_question(taskname, current_step, issue_description)
        if question:
            logging.info("[CLARIFICATION QUESTION] %s", question)
            # 获取用户回答并记录到SessionManager
            user_response = self.qa_handler.get_user_response_with_history(question)
            self.add_qa_record(question, user_response, context=f"clarification_{current_step}", question_type="clarification")
            logging.info("[CLARIFICATION RESPONSE] %s", user_response)
            return user_response
        return None

    def should_ask_question_for_decision(self, taskname, decision, remaining_decisions, qa_history=""):
        """
        判断是否需要针对当前决策提问
        
        Args:
            taskname: 任务名称
            decision: 当前要执行的决策
            remaining_decisions: 剩余的决策列表
            qa_history: 问答历史，用于判断是否需要提问
            
        Returns:
            bool: 是否需要提问
        """
        navigable_list = self.get_navigable_list()
        navigable_objects = [item["objectType"] for item in navigable_list]
        
        should_ask, reason = self.qa_handler.should_ask_question_for_decision(
            taskname, decision, remaining_decisions, navigable_objects, qa_history
        )
        
        if should_ask:
            logging.info(f"[DECISION QUESTION] Will ask question for decision '{decision.get('decisionmaking')}'. Reason: {reason}")
        
        return should_ask

    def generate_decision_question(self, taskname, decision, remaining_decisions):
        """
        为当前决策生成具体的问题
        
        Args:
            taskname: 任务名称
            decision: 当前决策
            remaining_decisions: 剩余决策列表
            
        Returns:
            str: 生成的问题
        """
        navigable_list = self.get_navigable_list()
        navigable_objects = [item["objectType"] for item in navigable_list]
        
        question = self.qa_handler.generate_decision_question(
            taskname, decision, remaining_decisions, navigable_objects
        )
        
        logging.info(f"[DECISION QUESTION] Generated question for '{decision.get('decisionmaking')}': {question}")
        return question

    def rank_possible_placement_locations(self, taskname, target, navigable_list, qa_history="", place_num=3):
        """
        输入目标、环境描述、可导航物体列表，调用VLM/LLM排序最有可能放置目标的位置
        返回排序后的objectType列表，长度不超过place_num
        """
        categories = list(set([item["objectType"] for item in navigable_list]))
        prompt_cfg = self.observation_generator.config.get("placement_ranking", {})
        systext_template = prompt_cfg.get("systext", "")
        systext = systext_template.format(
            taskname=taskname,
            target=target,
        )
        usertext_template = prompt_cfg.get("usertext", "")
        usertext = usertext_template.format(
            target=target,
            categories=", ".join(categories),
            place_num=place_num,
            qa_history=qa_history
        )
        llmapi = VLMAPI(self.model)
        result = llmapi.vlm_request(systext, usertext)
        
        import ast
        cleaned_result = result.strip()
        # 移除 markdown 代码块
        if cleaned_result.startswith("```") and cleaned_result.endswith("```"):
            cleaned_result = re.sub(r'```(json|python)?\s*\n', '', cleaned_result)
            cleaned_result = cleaned_result.strip('`\n ')

        possible_list = []
        try:
            # 最安全的方式：解析为 Python 字面量
            parsed_list = ast.literal_eval(cleaned_result)
            if isinstance(parsed_list, list):
                possible_list = [str(item).strip() for item in parsed_list if str(item).strip() in categories]
        except (ValueError, SyntaxError):
            # 兜底1: 正则表达式查找方括号内的内容，处理 [A,B,C] 格式
            match = re.search(r'\[(.*?)\]', cleaned_result)
            if match:
                content = match.group(1)
                # 处理带引号和不带引号的元素
                possible_list = [item.strip().strip("'\"") for item in content.split(',') if item.strip().strip("'\"") in categories]
            else:
                # 兜底2: 直接用逗号分割
                possible_list = [item.strip().strip("'\"") for item in cleaned_result.split(',') if item.strip().strip("'\"") in categories]

        return possible_list[:place_num]

    def verify_task_completion(self, taskname, original_plan, image_path=None):
        """
        使用VLM验证任务是否成功完成
        Args:
            taskname: 任务名称
            original_plan: 原始计划列表
            image_path: 验证图片路径，如果为None则自动截图
        Returns:
            tuple: (is_success: bool, reason: str, confidence: str)
        """
        return self.verification_handler.verify_task_completion(taskname, original_plan, image_path)

    def navigate_to_object(self, object_id):
        """
        导航到指定objectId的位置。假设有RocAgent或controller的navigate方法。
        """
        # 这里假设你有RocAgent或类似API
        # 你可以根据实际情况替换为你的底层导航实现
        target_object = next((item for item in self.metadata["objects"] if item["objectId"] == object_id), None)
        if target_object is None:
            logging.warning(f"[NAVIGATION] ObjectId {object_id} not found in metadata.")
            return False
        # 假设有self.rocAgent
        if hasattr(self, "rocAgent"):
            self.rocAgent.navigate(target_object)
        else:
            # 如果没有rocAgent，可以在此处集成controller的导航API
            logging.info(f"[NAVIGATION] Navigating to object {object_id} (type: {target_object['objectType']})")
            # 伪代码：self.controller.step(action="Navigate", objectId=object_id)
        return True

    def update_metadata(self):
        """
        更新并获取最新的场景状态。
        """
        # 强制执行一个空步骤来刷新场景
        self.controller.step(action="Pass")
        self.metadata = self.controller.last_event.metadata
        return self.metadata

    def search_for_object(self, taskname, target, max_num=1, qa_history=None):
        """
        搜索目标物体的位置。
        Args:
            taskname: 当前任务名称
            target: 目标物体类型
            max_num: 最大搜索位置数量
            qa_history: 问答历史记录，用于上下文理解
        Returns:
            bool: 是否找到目标物体
        """
        if qa_history is None:
            qa_history = self.get_qa_history()

        # 1. 首先检查当前视野中是否已经可见
        if self.update_metadata() and "objects" in self.metadata:
            for obj in self.metadata["objects"]:
                if obj["objectType"].lower() == target.lower() and obj.get("visible", True):
                    logging.info(f"[SEARCH] Found visible {target} in current view")
                    return True

        # 2. 获取可能的位置列表
        navigable_list = self.get_navigable_list()
        possible_locations = self.rank_possible_placement_locations(
            taskname=taskname,
            target=target,
            navigable_list=navigable_list,
            qa_history=qa_history,
            place_num=max_num
        )

        if not possible_locations:
            logging.warning(f"[SEARCH] No possible locations found for {target}")
            return False

        # 3. 检查每个可能位置
        for object_type in possible_locations:
            logging.info(f"[SEARCH] Checking {object_type}")
            # 3.1 获取位置对象
            object_id = next((item["objectId"] for item in navigable_list if item["objectType"].lower() == object_type.lower()), None)
            if not object_id:
                continue

            # 3.2 导航到位置
            self.navigate_to_object(object_id)
            # 更新metadata以获取导航后的最新状态
            self.update_metadata()

            # 3.3 如果是可打开的容器且是关闭状态，则打开
            container_opened_for_search = False
            if "objects" in self.metadata:
                meta_obj = next((obj for obj in self.metadata["objects"] if obj["objectId"] == object_id), None)
                if meta_obj and meta_obj.get("openable", False) and not meta_obj.get("isOpen", False):
                    logging.info(f"[SEARCH] {object_type} is closed, opening for search...")
                    if hasattr(self, "rocAgent"):
                        self.rocAgent.interact(meta_obj, "open")
                        if self.controller.last_event.metadata.get("lastActionSuccess", False):
                            # 记录这个容器是为搜索而打开的
                            container_info = {
                                "objectId": object_id,
                                "objectType": object_type,
                                "opened_for_target": target
                            }
                            self.opened_containers_for_search.append(container_info)
                            container_opened_for_search = True
                            logging.info(f"[SEARCH] Successfully opened {object_type} for searching {target}")
                        else:
                            logging.warning(f"[SEARCH] Failed to open {object_type}")
                        # 更新metadata以获取打开容器后的最新状态
                        self.update_metadata()

            # 3.4 检查是否找到目标物体
            # 再次更新metadata以确保获取最新状态
            metadata = self.update_metadata()
            if metadata and "objects" in metadata:
                # 添加调试信息
                visible_objects = [obj["objectType"] for obj in metadata["objects"] if obj.get("visible", True)]
                logging.debug(f"[DEBUG] Current visible objects: {visible_objects}")
                
                for obj in metadata["objects"]:
                    if obj["objectType"].lower() == target.lower() and obj.get("visible", True):
                        logging.info(f"[SEARCH] Found visible {target} in/on {object_type}")
                        return True  # 找到目标，保持容器打开状态供后续操作使用
                # 如果遍历完所有物体都没找到，输出信息
                logging.info(f"[SEARCH] Could not find visible {target} in/on {object_type}")
                
                # 如果在当前容器中没找到目标，且这个容器是为搜索而打开的，立即关闭它
                if container_opened_for_search:
                    self._close_container_immediately(container_info)

        # 如果所有可能位置都检查完还没找到，输出最终信息并返回False
        logging.warning(f"[SEARCH] Could not find visible {target} after checking all possible locations")
        return False

    def _close_container_immediately(self, container_info):
        """立即关闭指定的容器（搜索失败时使用）"""
        try:
            self.update_metadata()
            if "objects" in self.metadata:
                current_obj = next((obj for obj in self.metadata["objects"] if obj["objectId"] == container_info["objectId"]), None)
                if current_obj and current_obj.get("isOpen", False):
                    logging.info(f"[SEARCH] Closing {container_info['objectType']} immediately (target not found)")
                    if hasattr(self, "rocAgent"):
                        self.rocAgent.interact(current_obj, "close")
                        if self.controller.last_event.metadata.get("lastActionSuccess", False):
                            logging.info(f"[SEARCH] Successfully closed {container_info['objectType']}")
                            # 从待关闭列表中移除
                            if container_info in self.opened_containers_for_search:
                                self.opened_containers_for_search.remove(container_info)
                        else:
                            logging.warning(f"[SEARCH] Failed to close {container_info['objectType']}")
        except Exception as e:
            logging.error(f"[SEARCH] Error closing {container_info['objectType']}: {e}")

    def close_search_opened_containers(self):
        """关闭所有为搜索而打开且仍然打开的容器（在相关操作完成后调用）"""
        if not self.opened_containers_for_search:
            return
            
        logging.info(f"[SEARCH CLEANUP] Closing {len(self.opened_containers_for_search)} containers that were opened for search")
        containers_to_close = self.opened_containers_for_search.copy()
        
        for container_info in containers_to_close:
            try:
                self.update_metadata()
                if "objects" in self.metadata:
                    current_obj = next((obj for obj in self.metadata["objects"] if obj["objectId"] == container_info["objectId"]), None)
                    if current_obj and current_obj.get("isOpen", False):
                        logging.info(f"[SEARCH CLEANUP] Closing {container_info['objectType']} (ID: {container_info['objectId']})")
                        if hasattr(self, "rocAgent"):
                            self.rocAgent.interact(current_obj, "close")
                            if self.controller.last_event.metadata.get("lastActionSuccess", False):
                                logging.info(f"[SEARCH CLEANUP] Successfully closed {container_info['objectType']}")
                            else:
                                logging.warning(f"[SEARCH CLEANUP] Failed to close {container_info['objectType']}")
                    else:
                        logging.debug(f"[SEARCH CLEANUP] {container_info['objectType']} is already closed or not found")
                        
                # 无论成功还是失败，都从列表中移除
                if container_info in self.opened_containers_for_search:
                    self.opened_containers_for_search.remove(container_info)
                    
            except Exception as e:
                logging.error(f"[SEARCH CLEANUP] Error closing {container_info['objectType']}: {e}")
                
        # 最后更新一次metadata
        self.update_metadata()

    def execute_decisions(self, taskname, decisions):
        """
        执行决策序列，支持"走一步看一步"模式。
        在每个决策执行前判断是否需要提问，根据用户回答可能重新规划。
        
        Args:
            taskname: 当前任务名称
            decisions: 决策列表
        """
        navigable_list = self.get_navigable_list()
        qa_history = self.get_qa_history()
        
        decision_index = 0
        while decision_index < len(decisions):
            decision = decisions[decision_index]
            remaining_decisions = decisions[decision_index + 1:]
            
            # 步骤1: 判断是否需要针对当前决策提问
            qa_history = self.get_qa_history()
            if self.should_ask_question_for_decision(taskname, decision, remaining_decisions, qa_history):
                # 生成具体问题
                question = self.generate_decision_question(taskname, decision, remaining_decisions)
                
                # 处理用户交互
                user_response, need_replan, reason = self.process_user_response(question, decisions, taskname)
                logging.info(f"[DECISION QA] User response: {user_response}")
                logging.info(f"[DECISION QA] Need replan: {need_replan}, Reason: {reason}")
                
                if need_replan:
                    # 步骤2: 根据用户回答重新规划剩余的decisions
                    logging.info("[DECISION REPLAN] Replanning remaining decisions based on user response...")
                    
                    # 将剩余的decisions转换为subtasks格式进行重新规划
                    remaining_subtasks = [d.get("decisionmaking", f"{d.get('action', '')} {d.get('objectType', '')}") 
                                        for d in remaining_decisions]
                    remaining_subtasks.insert(0, decision.get("decisionmaking", f"{decision.get('action', '')} {decision.get('objectType', '')}"))  # 包含当前决策
                    
                    qa_history_for_replan = self.get_qa_history()
                    new_subtasks = self.task_planner.replan_subtasks_based_on_user_response(
                        taskname, "", qa_history_for_replan, remaining_subtasks
                    )
                    
                    # 将新的subtasks转换为decisions格式
                    qa_history = self.get_qa_history()
                    new_decisions = self.task_planner.subtasks_to_decisions(new_subtasks, qa_history)
                    
                    # 步骤3: 更新decisions列表
                    # 保留已执行的decisions + 新规划的decisions
                    decisions = decisions[:decision_index] + new_decisions
                    logging.info(f"[DECISION REPLAN] Updated decisions: {[d.get('decisionmaking', '') for d in new_decisions]}")
                    
                    # 继续执行当前索引的决策（可能已被重新规划）
                    if decision_index >= len(decisions):
                        logging.info("[DECISION REPLAN] All decisions completed after replanning")
                        break
                    
                    # 重新获取当前决策（可能已被更新）
                    decision = decisions[decision_index]
            
            # 步骤4: 执行当前决策
            action = decision["action"].lower()
            object_type = decision["objectType"]
            decisionmaking = decision["decisionmaking"]
            logging.info(f"[EXECUTE] {decisionmaking}")

            # 1. 搜索类动作
            if action in ["search", "find"]:
                found = self.search_for_object(taskname=taskname,
                                           target=object_type,
                                           max_num=5,
                                           qa_history=qa_history)
                if not found:
                    logging.error(f"[ERROR] Search failed for {object_type}, stopping execution.")
                    break

            # 2. 导航类动作
            elif action in ["navigate", "navigate to", "goto", "go to", "move to"]:
                object_id = next((item["objectId"] for item in navigable_list if item["objectType"].lower() == object_type.lower()), None)
                if object_id:
                    self.navigate_to_object(object_id)
                    self.update_metadata()
                else:
                    logging.warning(f"[WARNING] Cannot navigate to {object_type}, as it is not in the navigable list.")

            # 3. 交互类动作
            elif action in ["pickup", "pick up", "pick_up", "open", "close", "toggle", "toggle_on", "toggle_off", 
                           "clean", "dirty", "fill", "empty", "slice", "cook", "break", "use_up"]:
                # 3.1 获取目标物体
                object_id = None
                metadata = self.update_metadata()
                logging.info(f"[DEBUG] Looking for {object_type} to {action}")
                
                if metadata and "objects" in metadata:
                    # 调试信息：显示所有可见对象
                    visible_objects = [f"{obj['objectType']}({obj['objectId']})" for obj in metadata["objects"] if obj.get("visible", True)]
                    logging.info(f"[DEBUG] Visible objects: {visible_objects}")
                    
                    # 智能对象选择：根据动作类型选择最合适的对象
                    matching_objects = []
                    for obj in metadata["objects"]:
                        if obj["objectType"].lower() == object_type.lower() and obj.get("visible", True):
                            matching_objects.append(obj)
                    
                    if matching_objects:
                        selected_obj = None
                        
                        # 首先检查是否有最近交互的对象，优先使用相同的对象
                        recent_object_id = self.recent_interactions.get(object_type.lower())
                        if recent_object_id:
                            recent_obj = next((obj for obj in matching_objects if obj["objectId"] == recent_object_id), None)
                            if recent_obj:
                                logging.info(f"[DEBUG] Found recently interacted {object_type} (ID: {recent_object_id})")
                                # 检查该对象是否适合当前动作
                                if action == "open" and not recent_obj.get("isOpen", False):
                                    selected_obj = recent_obj
                                    logging.info(f"[DEBUG] Using recently interacted closed {object_type} for opening")
                                elif action == "close" and recent_obj.get("isOpen", False):
                                    selected_obj = recent_obj
                                    logging.info(f"[DEBUG] Using recently interacted open {object_type} for closing")
                                elif action not in ["open", "close"]:
                                    selected_obj = recent_obj
                                    logging.info(f"[DEBUG] Using recently interacted {object_type} for {action}")
                        
                        # 如果没有找到合适的最近交互对象，按照原来的逻辑选择
                        if selected_obj is None:
                            if action == "open":
                                # 对于open动作，优先选择关闭的对象
                                closed_objects = [obj for obj in matching_objects if not obj.get("isOpen", False)]
                                if closed_objects:
                                    selected_obj = closed_objects[0]  # 选择第一个关闭的对象
                                    logging.info(f"[DEBUG] Selected closed {object_type} for opening (ID: {selected_obj['objectId']})")
                                else:
                                    selected_obj = matching_objects[0]  # 如果都是打开的，选择第一个
                                    logging.info(f"[DEBUG] All {object_type} are already open, selected first one (ID: {selected_obj['objectId']})")
                                    
                            elif action == "close":
                                # 对于close动作，检查是否有多个打开的对象
                                open_objects = [obj for obj in matching_objects if obj.get("isOpen", False)]
                                if len(open_objects) > 1:
                                    # 如果有多个打开的对象，询问是否要关闭所有
                                    logging.info(f"[DEBUG] Found {len(open_objects)} open {object_type} objects. Will close all of them.")
                                    # 这里我们将处理所有打开的对象，而不仅仅是第一个
                                    selected_obj = open_objects[0]  # 先选择第一个，后面会循环处理所有
                                    logging.info(f"[DEBUG] Will close all {len(open_objects)} open {object_type} objects")
                                elif len(open_objects) == 1:
                                    selected_obj = open_objects[0]
                                    logging.info(f"[DEBUG] Selected open {object_type} for closing (ID: {selected_obj['objectId']})")
                                else:
                                    selected_obj = matching_objects[0]  # 如果都是关闭的，选择第一个
                                    logging.info(f"[DEBUG] All {object_type} are already closed, selected first one (ID: {selected_obj['objectId']})")
                            else:
                                # 对于其他动作，选择第一个匹配的对象
                                selected_obj = matching_objects[0]
                                logging.info(f"[DEBUG] Selected first matching {object_type} (ID: {selected_obj['objectId']})")
                        
                        object_id = selected_obj["objectId"]
                        logging.info(f"[DEBUG] Final selected object: {selected_obj['objectType']} (ID: {object_id})")
                        
                        # 显示所有匹配对象的状态信息
                        if action in ["open", "close"] and len(matching_objects) > 1:
                            logging.info(f"[DEBUG] Found {len(matching_objects)} {object_type} objects:")
                            for i, obj in enumerate(matching_objects):
                                status = "SELECTED" if obj["objectId"] == object_id else "ignored"
                                logging.info(f"[DEBUG]   {i+1}. ID: {obj['objectId']}, openable: {obj.get('openable', False)}, isOpen: {obj.get('isOpen', False)} ({status})")
                    else:
                        object_id = None

                # 3.2 如果物体不可见，则报错并停止
                if not object_id:
                    logging.error(f"[ERROR] Cannot interact with {object_type} as it is not visible. Please use 'search' first.")
                    break

                # 3.3 执行交互动作
                meta_obj = next((obj for obj in metadata["objects"] if obj["objectId"] == object_id), None)
                if meta_obj and hasattr(self, "rocAgent"):
                    # 检查动作是否支持
                    if action in ["open", "close"] and not meta_obj.get("openable", False):
                        logging.error(f"[ERROR] {object_type} is not openable (openable={meta_obj.get('openable', False)}), stopping execution.")
                        break
                    elif action in ["pickup", "pick up", "pick_up"] and not meta_obj.get("pickupable", False):
                        logging.error(f"[ERROR] {object_type} is not pickupable, stopping execution.")
                        break

                    # 对于 close 动作，检查当前状态
                    if action == "close":
                        if not meta_obj.get("isOpen", False):
                            logging.warning(f"[WARNING] {object_type} is already closed (isOpen={meta_obj.get('isOpen', False)})")
                            # 继续执行，因为有时状态可能不准确
                        else:
                            logging.info(f"[INFO] Closing {object_type} (current state: isOpen={meta_obj.get('isOpen', True)})")

                    logging.info(f"[EXECUTE] Executing {action} on {object_type} (ID: {object_id})")
                    self.rocAgent.interact(meta_obj, action)
                    
                    # Check controller's last action success instead of relying on return value
                    if not self.controller.last_event.metadata.get("lastActionSuccess", False):
                        error_message = self.controller.last_event.metadata.get("errorMessage", "Unknown error")
                        logging.error(f"[ERROR] Action {action} failed on {object_type}. Error: {error_message}")
                        break
                    else:
                        logging.info(f"[SUCCESS] {action} on {object_type} completed successfully")
                        # 记录成功交互的对象ID，以便后续操作使用相同对象
                        self.recent_interactions[object_type.lower()] = object_id
                        logging.info(f"[DEBUG] Recorded recent interaction: {object_type.lower()} -> {object_id}")
                        
                        # 如果是 pickup 动作成功，关闭为搜索而打开的容器
                        if action in ["pickup", "pick up", "pick_up"]:
                            self.close_search_opened_containers()
                    self.update_metadata()
                else:
                    logging.error(f"[ERROR] Failed to get metadata for {object_type}, stopping execution.")
                    break

            # 4. Put 动作 - 需要特殊处理，因为涉及两个物体
            elif action == "put":
                # 4.1 检查是否有物体被拾取
                held_object = None
                metadata = self.update_metadata()
                if metadata and "objects" in metadata:
                    for obj in metadata["objects"]:
                        if obj.get("isPickedUp", False):
                            held_object = obj
                            break
                
                if not held_object:
                    logging.error(f"[ERROR] Cannot put object - no object is currently held.")
                    break
                
                # 4.2 获取目标容器/位置
                target_object_id = None
                target_object_type = decision.get("targetObject", object_type)  # 使用targetObject或fallback到objectType
                
                if metadata and "objects" in metadata:
                    for obj in metadata["objects"]:
                        if obj["objectType"].lower() == target_object_type.lower() and obj.get("visible", True):
                            # 检查是否是receptacle或可放置的表面
                            receptacle_types = [
                                "table", "countertop", "plate", "bowl", "cabinet", "drawer", "shelf", 
                                "fridge", "microwave", "sink", "stove", "oven", "dishwasher", "trash",
                                "box", "container", "basket", "bag", "cup", "mug", "pan", "pot"
                            ]
                            if obj.get("receptacle", False) or obj["objectType"].lower() in receptacle_types:
                                target_object_id = obj["objectId"]
                                break
                
                if not target_object_id:
                    logging.error(f"[ERROR] Cannot find receptacle {target_object_type} to put object on/in.")
                    break
                
                # 4.3 导航到目标位置
                self.navigate_to_object(target_object_id)
                self.update_metadata()
                
                # 4.3.5 如果目标容器是可开关的且当前是关闭状态，先打开它
                target_meta_obj = next((obj for obj in self.metadata["objects"] if obj["objectId"] == target_object_id), None)
                if target_meta_obj and target_meta_obj.get("openable", False) and not target_meta_obj.get("isOpen", False):
                    logging.info(f"[EXECUTE] Opening {target_meta_obj['objectType']} before putting object inside")
                    self.rocAgent.interact(target_meta_obj, "open")
                    if not self.controller.last_event.metadata.get("lastActionSuccess", False):
                        logging.error(f"[ERROR] Failed to open {target_meta_obj['objectType']}, stopping execution.")
                        break
                    self.update_metadata()
                    # Update target_meta_obj after opening
                    target_meta_obj = next((obj for obj in self.metadata["objects"] if obj["objectId"] == target_object_id), None)
                
                # 4.4 执行put动作
                target_meta_obj = next((obj for obj in self.metadata["objects"] if obj["objectId"] == target_object_id), None)
                if target_meta_obj and hasattr(self, "rocAgent"):
                    logging.info(f"[EXECUTE] Putting {held_object['objectType']} on/in {target_meta_obj['objectType']}")
                    self.rocAgent.interact(target_meta_obj, "put")
                    
                    # Check controller's last action success
                    if not self.controller.last_event.metadata.get("lastActionSuccess", False):
                        logging.error(f"[ERROR] Put action failed, stopping execution.")
                        break
                    else:
                        logging.info(f"[SUCCESS] Put action completed successfully")
                        # Put 动作成功后，关闭所有为搜索而打开的容器
                        self.close_search_opened_containers()
                    self.update_metadata()
                else:
                    logging.error(f"[ERROR] Failed to get target object metadata for put action.")
                    break

            # 4. 未知动作
            else:
                logging.warning(f"[SKIP] Action {action} not recognized for auto-execution.")
            
            # 步骤5: 递增决策索引，继续下一个决策
            decision_index += 1


def main():
    """
    Robot Task Planner Main Program
    
    测试任务配置说明：
    1. USE_TEST_TASKS = True: 使用 test_tasks.json 中的测试任务
    USE_TEST_TASKS = False: 使用手动指定的任务（见 manual_task）
    
    2. 当 USE_TEST_TASKS = True 时：
    - RUN_ALL_TEST_TASKS = True: 依次运行所有测试任务
    - RUN_ALL_TEST_TASKS = False: 运行 TEST_TASK_ID 指定的单个任务
    
    3. 可用的测试任务 ID（见 test_tasks.json）：
    test_001: put tomato on plate
    test_002: put apple in cabinet  
    test_003: put bread in fridge
    test_004: clean tomato and put on plate
    test_005: put knife in drawer
    ... 等等
    
    使用示例：
    - 运行单个测试任务: USE_TEST_TASKS=True, TEST_TASK_ID="test_001", RUN_ALL_TEST_TASKS=False
    - 运行所有测试任务: USE_TEST_TASKS=True, RUN_ALL_TEST_TASKS=True
    - 使用手动任务: USE_TEST_TASKS=False
    """
    env="taskgenerate"
    model = "qwen2.5vl:32b" # use gpt-4o to generate trajectories
    # you can set timeout for AI2THOR init here.        

    ###### step1. choose the task type here ####################
    tasktype="pickup_and_put"
    room = 'kitchens'
    scene = 'FloorPlan3'
    
    # 测试任务配置
    USE_TEST_TASKS = True  # 设为 True 使用测试任务，False 使用手动指定的任务
    TEST_TASK_ID = "test_001"  # 指定要运行的测试任务ID
    RUN_ALL_TEST_TASKS = False  # 设为 True 运行所有测试任务
    
    # 设置日志配置，保存到文件
    import os
    task_planner_log_dir = os.path.join(get_task_planner_path(), f"logs/{scene}_{tasktype}")
    os.makedirs(task_planner_log_dir, exist_ok=True)
    log_file = os.path.join(task_planner_log_dir, f"robot_execution_{scene}.log")
    setup_logging(log_file)
    
    # 创建场景管理器
    scene_manager = SceneManager()
    
    # 获取场景相关路径
    paths = scene_manager.get_scene_paths(env, room, scene, tasktype)
    metadata_path = paths['metadata_path']
    origin_pos_path = paths['origin_pos_path']
    
    logging.info("metadata_path: %s", metadata_path)
    
    # 加载场景元数据
    metadata = scene_manager.load_scene_metadata(metadata_path)
    
    # 根据配置选择任务来源
    logging.info(f"Task configuration - USE_TEST_TASKS: {USE_TEST_TASKS}, TEST_TASK_ID: {TEST_TASK_ID}, RUN_ALL_TEST_TASKS: {RUN_ALL_TEST_TASKS}")
    
    if USE_TEST_TASKS:
        if RUN_ALL_TEST_TASKS:
            # 运行所有测试任务
            test_tasks = scene_manager.load_test_tasks()
            logging.info(f"Will run all {len(test_tasks)} test tasks")
        elif TEST_TASK_ID:
            # 运行指定的测试任务
            logging.info(f"Looking for test task: {TEST_TASK_ID}")
            test_task = scene_manager.get_test_task_by_id(TEST_TASK_ID)
            logging.info(f"Test task search result: {test_task is not None}")
            if test_task:
                test_tasks = [test_task]
                logging.info(f"Will run test task: {TEST_TASK_ID}")
            else:
                logging.error(f"Test task {TEST_TASK_ID} not found, exiting")
                exit(1)
        else:
            logging.error("USE_TEST_TASKS is True but no task specified")
            exit(1)
    else:
        # 使用手动指定的任务
        manual_task = {
            "id": "manual_task",
            "taskname": "put tomato on the plate",  # 手动指定任务名称
            "description": "Manually specified task",
            "scene": scene,
            "room": room,
            "tasktype": tasktype
        }
        test_tasks = [manual_task]
        logging.info("Using manually specified task")
    
    # 执行任务
    for task_idx, task in enumerate(test_tasks):
        taskname = task["taskname"]
        task_id = task.get("id", f"task_{task_idx}")
        
        logging.info("\n\n*********************************************************************")
        logging.info(f"Running Task ID: {task_id}")
        logging.info(f"Scene:{scene} Task_Type: {tasktype} Task: {taskname}")
        logging.info("*********************************************************************\n")

        logging.info("taskname: %s", taskname)
        

        origin_path = os.path.join(get_task_planner_path(), f"data/data_{tasktype}/{scene}_{tasktype}_{task_idx}")
        
        # 计算场景对角线距离
        scene_diagonal = scene_manager.calculate_scene_diagonal(metadata)
        
        max_retries=2
        error_paths = []
        
        # 只初始化一次场景，在所有attempt中复用
        controller, metadata = scene_manager.run_initial_scene(scene_diagonal, origin_pos_path, scene)
        
        for attempt in range(max_retries + 1): 
            try:
                # 每次attempt开始时都重置机器人到初始位置，确保状态一致性
                logging.info(f"[ATTEMPT {attempt + 1}/{max_retries + 1}] Starting task attempt")
                
                # 重置到初始位置
                pos = load_json(origin_pos_path)
                position = pos["position"]
                rotation = pos["rotation"]  
                horizon = pos["cameraHorizon"]   
                
                # 执行位置重置
                reset_result = controller.step(
                    action="Teleport",
                    position=position,
                    rotation=rotation,
                    horizon=horizon,
                    standing=True
                )
                
                if not reset_result.metadata["lastActionSuccess"]:
                    logging.warning(f"[RESET] Failed to reset robot position on attempt {attempt + 1}")
                else:
                    logging.info(f"[RESET] Successfully reset robot to initial position: {position}")
                
                # 确保机器人处于站立状态
                controller.step(action="Stand")
                
                # 更新metadata
                metadata = controller.last_event.metadata
                
                # 如果有物体被拿着，放下它们
                for obj in metadata["objects"]:
                    if obj["isPickedUp"]:
                        logging.info(f"[RESET] Dropping held object: {obj['objectId']}")
                        controller.step(action="DropHandObject", forceAction=True)

                # 封装后的机器人控制器
                robot_controller = RobotController(controller, metadata, model, origin_path)
                
                # 步骤1：保存初始观察图片
                init_image_path = robot_controller.observation_generator.save_initial_observation_image(robot_controller.controller, robot_controller.origin_path)
                
                # 步骤2：生成observation
                observation = robot_controller.generate_observation(init_image_path)
                logging.info("[OBSERVATION] %s", observation)
                
                # 步骤3：高层任务规划（只用高层taskname和observation）
                # taskname已经在上面直接指定了，不需要从task对象中提取
                subtasks = robot_controller.plan_high_level_tasks(taskname, observation)
                logging.info("[INITIAL TASK PLANNING] %s", str(subtasks))
                
                # 检查是否需要提问
                question = robot_controller.ask_general_question_for_plan(taskname, subtasks)
                
                if question:
                    # 处理用户问答交互
                    user_response, need_replan, reason = robot_controller.process_user_response(question, subtasks, taskname)
                    logging.info("[RE-PLANNING BASED ON USER RESPONSE]")
                    logging.info('REPLAN?: %s', need_replan)
                    logging.info('Reason: %s', reason)
                    if need_replan:
                        # old_subgoals = robot_controller.task_planner.subgoals
                        qa_history = robot_controller.get_qa_history()
                        new_subtasks = robot_controller.task_planner.replan_subtasks_based_on_user_response(
                            taskname, observation, qa_history, subtasks
                        )
                        robot_controller.task_planner.subgoals = new_subtasks
                        logging.info("[REPLAN] Old subtasks: %s", subtasks)
                        logging.info("[REPLAN] New subtasks: %s", new_subtasks)
                        subtasks = new_subtasks
                        # 你可以在此处继续后续执行新规划的逻辑
                    else:
                        logging.info("[NO REPLAN NEEDED] Reason: %s", reason)


                # 步骤4：底层任务规划：把subtask细化为可执的 decisions
                qa_history = robot_controller.get_qa_history()
                decisions = robot_controller.task_planner.subtasks_to_decisions(subtasks, qa_history)
                # decisions = subtasks
                logging.info("[SUBTASKS WITH DECISION] %s", decisions)
                robot_controller.execute_decisions(taskname, decisions)
                
                # 步骤5：验证任务是否成功完成
                logging.info("[VERIFICATION] Starting task verification...")
                is_success, reason, confidence = robot_controller.verify_task_completion(
                    taskname=taskname,
                    original_plan=subtasks
                )
                
                if is_success:
                    logging.info(f"[VERIFICATION] ✓ Task completed successfully! (Confidence: {confidence})")
                    logging.info(f"[VERIFICATION] Reason: {reason}")
                else:
                    logging.warning(f"[VERIFICATION] ✗ Task may not be completed. (Confidence: {confidence})")
                    logging.warning(f"[VERIFICATION] Reason: {reason}")
                    
                # 保存验证结果到元数据
                verification_result = {
                    "task": taskname,
                    "success": is_success,
                    "reason": reason,
                    "confidence": confidence,
                    "original_plan": subtasks
                }
                
                # 创建验证结果文件
                import json
                verification_file = f"{origin_path}/verification_result.json"
                with open(verification_file, 'w', encoding='utf-8') as f:
                    json.dump(verification_result, f, ensure_ascii=False, indent=2)
                logging.info(f"[VERIFICATION] Verification result saved to: {verification_file}")
                
                # 如果验证成功，退出重试循环
                if is_success and confidence in ['high', 'medium']:
                    logging.info("[VERIFICATION] Task completed successfully, exiting retry loop.")
                    break

            except Exception as e:
                logging.error("[ERROR] %s, try again.", e)
                clear_folder(origin_path)
            
                if attempt == max_retries - 1: 
                    logging.warning("[RETRY %d TIMES, JUMP THE TASK]", max_retries)
                    error_paths.append(origin_path)  
                    save_data_to_json(error_paths, os.path.join(get_task_planner_path(), "wrong_generte_path_list.json"))
                    break  # Exit the retry loop for this task
        
        # Stop the controller after all attempts for this task
        controller.stop()
        logging.info(f"[TASK COMPLETE] Finished task {task_id}: {taskname}")
    
    # All tasks completed
    logging.info("All tasks completed successfully!")
    logging.info(f"Error paths saved to: ./wrong_generte_path_list.json")


if __name__=="__main__":
    main()