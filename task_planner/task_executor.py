"""
Task Executor Module

提供简洁优雅的任务执行功能，可被其他文件调用
"""

import os
import json
import logging
import sys
from typing import Dict, Any, Tuple

# Add data_engine path to sys.path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
data_engine_path = os.path.join(os.path.dirname(current_dir), 'data_engine')
if data_engine_path not in sys.path:
    sys.path.insert(0, data_engine_path)

from utils import load_json, clear_folder, save_data_to_json


def get_task_planner_path():
    """获取task_planner目录的绝对路径"""
    return os.path.dirname(os.path.abspath(__file__))


def execute_task(
    task: Dict[str, Any],
    task_idx: int,
    scene_manager,
    model,
    origin_pos_path: str,
    scene: str,
    metadata: Dict[str, Any],
    max_retries: int = 2,
    RobotController=None
) -> Tuple[bool, str]:
    """
    执行单个任务
    
    Args:
        task: 任务字典，包含taskname, id等信息
        task_idx: 任务索引
        scene_manager: 场景管理器
        model: AI模型
        origin_pos_path: 初始位置文件路径
        scene: 场景名称
        metadata: 场景元数据
        max_retries: 最大重试次数
        RobotController: RobotController类，避免循环导入
    
    Returns:
        Tuple[bool, str]: (是否成功, 错误信息或成功信息)
    """
    if RobotController is None:
        raise ValueError("RobotController class must be provided to avoid circular imports")
    taskname = task["taskname"]
    task_id = task.get("id", f"task_{task_idx}")
    tasktype = task.get("tasktype", "unknown")
    
    logging.info("\n\n*********************************************************************")
    logging.info(f"Running Task ID: {task_id}")
    logging.info(f"Scene:{scene} Task_Type: {tasktype} Task: {taskname}")
    logging.info("*********************************************************************\n")

    origin_path = os.path.join(get_task_planner_path(), f"data/data_{tasktype}/{scene}_{tasktype}_{task_idx}")
    
    # 计算场景对角线距离
    scene_diagonal = scene_manager.calculate_scene_diagonal(metadata)
    
    # 初始化场景
    controller, metadata = scene_manager.run_initial_scene(scene_diagonal, origin_pos_path, scene)
    
    try:
        for attempt in range(max_retries + 1):
            try:
                logging.info(f"[ATTEMPT {attempt + 1}/{max_retries + 1}] Starting task attempt")
                
                # 重置机器人状态
                if not _reset_robot_state(controller, origin_pos_path, metadata):
                    logging.warning(f"[RESET] Failed to reset robot position on attempt {attempt + 1}")
                
                # 创建机器人控制器
                robot_controller = RobotController(controller, metadata, model, origin_path)
                
                # 执行任务流程
                success = _execute_task_flow(robot_controller, taskname)
                
                if success:
                    logging.info("[VERIFICATION] Task completed successfully, exiting retry loop.")
                    return True, "Task completed successfully"
                    
            except Exception as e:
                logging.error("[ERROR] %s, try again.", e)
                clear_folder(origin_path)
                
                if attempt == max_retries:
                    error_path = origin_path
                    save_data_to_json([error_path], os.path.join(get_task_planner_path(), "wrong_generte_path_list.json"))
                    return False, f"Task failed after {max_retries + 1} attempts: {str(e)}"
        
        return False, f"Task failed after {max_retries + 1} attempts"
        
    finally:
        controller.stop()
        logging.info(f"[TASK COMPLETE] Finished task {task_id}: {taskname}")


def _reset_robot_state(controller, origin_pos_path: str, metadata: Dict[str, Any]) -> bool:
    """重置机器人到初始状态"""
    try:
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
            return False
        
        # 确保机器人处于站立状态
        controller.step(action="Stand")
        
        # 放下任何被拿着的物品
        metadata = controller.last_event.metadata
        for obj in metadata["objects"]:
            if obj["isPickedUp"]:
                logging.info(f"[RESET] Dropping held object: {obj['objectId']}")
                controller.step(action="DropHandObject", forceAction=True)
        
        logging.info(f"[RESET] Successfully reset robot to initial position: {position}")
        return True
        
    except Exception as e:
        logging.error(f"[RESET] Failed to reset robot state: {e}")
        return False


def _execute_task_flow(robot_controller, taskname: str) -> bool:
    """执行完整的任务流程"""
    try:
        # 1. 保存初始观察图片
        init_image_path = robot_controller.observation_generator.save_initial_observation_image(
            robot_controller.controller, robot_controller.origin_path
        )
        
        # 2. 生成observation
        observation = robot_controller.generate_observation(init_image_path)
        logging.info("[OBSERVATION] %s", observation)
        
        # 3. 高层任务规划
        subtasks = robot_controller.plan_high_level_tasks(taskname, observation)
        logging.info("[INITIAL TASK PLANNING] %s", str(subtasks))
        
        # 4. 处理用户问答交互
        subtasks = _handle_user_interaction(robot_controller, taskname, subtasks, observation)
        
        # 5. 底层任务规划
        qa_history = robot_controller.get_qa_history()
        decisions = robot_controller.task_planner.subtasks_to_decisions(subtasks, qa_history)
        logging.info("[SUBTASKS WITH DECISION] %s", decisions)
        
        # 6. 执行决策
        robot_controller.execute_decisions(taskname, decisions)
        
        # 7. 验证任务完成
        return _verify_task_completion(robot_controller, taskname, subtasks)
        
    except Exception as e:
        logging.error(f"[TASK FLOW] Error in task execution flow: {e}")
        return False


def _handle_user_interaction(robot_controller, taskname: str, subtasks: list, observation: str) -> list:
    """处理用户交互和重新规划"""
    question = robot_controller.ask_general_question_for_plan(taskname, subtasks)
    
    if question:
        need_replan, reason = robot_controller.process_user_response(question, subtasks, taskname)
        logging.info("[RE-PLANNING BASED ON USER RESPONSE]")
        logging.info('REPLAN?: %s', need_replan)
        logging.info('Reason: %s', reason)
        
        if need_replan:
            qa_history = robot_controller.get_qa_history()
            new_subtasks = robot_controller.task_planner.replan_subtasks_based_on_user_response(
                taskname, observation, qa_history, subtasks
            )
            robot_controller.task_planner.subgoals = new_subtasks
            logging.info("[REPLAN] Old subtasks: %s", subtasks)
            logging.info("[REPLAN] New subtasks: %s", new_subtasks)
            return new_subtasks
        else:
            logging.info("[NO REPLAN NEEDED] Reason: %s", reason)
    
    return subtasks


def _verify_task_completion(robot_controller, taskname: str, subtasks: list) -> bool:
    """验证任务完成状态"""
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
        
        # 处理验证失败
        is_success = _handle_verification_failure(robot_controller, taskname, subtasks, reason, confidence)
    
    # 保存验证结果
    _save_verification_result(robot_controller.origin_path, taskname, is_success, reason, confidence, subtasks)
    
    return is_success and confidence in ['high', 'medium']


def _handle_verification_failure(robot_controller, taskname: str, subtasks: list, 
                                reason: str, confidence: str) -> bool:
    """处理验证失败的情况"""
    error_info = {
        "error_type": "task_verification_failed",
        "error_message": f"Task verification indicates the task may not be completed successfully. Confidence: {confidence}",
        "context": f"Verification reason: {reason}. The system checked the final state but detected potential issues with task completion."
    }
    
    recovery_info = robot_controller.handle_execution_error(
        error_info, taskname,
        current_step="task verification",
        remaining_actions=[]
    )
    
    # 根据用户反馈处理
    if recovery_info and recovery_info.get('strategy') == 'retry':
        logging.info("[VERIFICATION] User requested retry, re-running verification...")
        is_success, _, _ = robot_controller.verify_task_completion(
            taskname=taskname,
            original_plan=subtasks
        )
        return is_success
    elif recovery_info and recovery_info.get('strategy') == 'accept':
        logging.info("[VERIFICATION] User confirmed task completion despite verification concerns")
        return True
    
    return False


def _save_verification_result(origin_path: str, taskname: str, is_success: bool, 
                             reason: str, confidence: str, subtasks: list):
    """保存验证结果到文件"""
    verification_result = {
        "task": taskname,
        "success": is_success,
        "reason": reason,
        "confidence": confidence,
        "original_plan": subtasks
    }
    
    verification_file = f"{origin_path}/verification_result.json"
    with open(verification_file, 'w', encoding='utf-8') as f:
        json.dump(verification_result, f, ensure_ascii=False, indent=2)
    logging.info(f"[VERIFICATION] Verification result saved to: {verification_file}")