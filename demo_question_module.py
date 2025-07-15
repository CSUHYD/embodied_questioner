#!/usr/bin/env python3
"""
提问模块演示脚本
展示机器人在遇到问题时如何主动向用户提问
"""

import sys
import os
import time
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data_engine'))

def demo_question_workflow():
    """演示提问工作流程"""
    print("=== 机器人提问模块演示 ===\n")
    
    # 模拟机器人控制器
    class DemoRobotController:
        def __init__(self):
            self.failed_attempts = 0
            self.navigable_list = []
            self.memory = []
            self.last_question = None
            self.user_responses = []
            self.taskname = "把番茄放进冰箱"
        
        def should_ask_question(self, current_state, error_message=None):
            """判断是否应该提问"""
            if self.failed_attempts >= 3:
                return True, "too_many_failures"
            if error_message and "error" in error_message.lower():
                return True, "error_occurred"
            if not self.navigable_list:
                return True, "no_navigable_objects"
            if current_state and any(keyword in current_state.lower() for keyword in ["ambiguous", "unclear", "confused"]):
                return True, "ambiguous_situation"
            return False, None
        
        def generate_question(self, taskname, current_state, reason):
            """生成问题"""
            if reason == "too_many_failures":
                return f"我已经尝试了{self.failed_attempts}次但仍然无法完成任务'{taskname}'。请帮助我。"
            elif reason == "error_occurred":
                return f"在执行任务'{taskname}'时遇到了问题。请指导我如何解决。"
            elif reason == "no_navigable_objects":
                return f"我找不到任何可操作的物体来完成任务'{taskname}'。请告诉我应该搜索哪里。"
            elif reason == "ambiguous_situation":
                return f"任务'{taskname}'的指令不够明确。请澄清具体要求。"
            else:
                return f"在执行任务'{taskname}'时遇到了问题。请帮助我。"
        
        def handle_problem_situation(self, taskname, current_state, error_message=None):
            """处理问题情况"""
            should_ask, reason = self.should_ask_question(current_state, error_message)
            
            if should_ask:
                question = self.generate_question(taskname, current_state, reason)
                self.last_question = question
                self.memory.append(f"Question: {question}")
                return question
            return None
        
        def receive_user_response(self, response):
            """接收用户回答"""
            self.user_responses.append({
                "question": self.last_question,
                "response": response,
                "timestamp": time.time()
            })
            self.memory.append(f"User Response: {response}")
        
        def execute_task_step(self, step_name, success=True, error_message=None):
            """执行任务步骤"""
            print(f"🤖 执行步骤: {step_name}")
            
            if not success:
                self.failed_attempts += 1
                print(f"❌ 步骤失败，尝试次数: {self.failed_attempts}")
                
                current_state = f"Failed to execute: {step_name}"
                question = self.handle_problem_situation(self.taskname, current_state, error_message)
                
                if question:
                    print(f"🤖 机器人提问: {question}")
                    return question
            
            print(f"✅ 步骤成功: {step_name}")
            return None
    
    # 创建演示机器人
    robot = DemoRobotController()
    
    # 场景1：找不到目标物体
    print("场景1: 找不到目标物体")
    print("=" * 50)
    
    robot.navigable_list = [{"objectType": "Cabinet"}, {"objectType": "Counter"}]
    robot.failed_attempts = 0
    
    # 步骤1：搜索番茄
    question = robot.execute_task_step("搜索番茄", success=False, error_message="Error: Cannot find tomato")
    
    if question:
        # 模拟用户回答
        user_response = "番茄在冰箱里，冰箱在房间的另一边"
        print(f"👤 用户回答: {user_response}")
        robot.receive_user_response(user_response)
        
        # 基于用户回答继续执行
        print("🔄 基于用户回答重新执行...")
        robot.navigable_list.append({"objectType": "Fridge"})
        robot.execute_task_step("导航到冰箱", success=True)
        robot.execute_task_step("打开冰箱", success=True)
        robot.execute_task_step("拿起番茄", success=True)
        robot.execute_task_step("关闭冰箱", success=True)
        print("🎉 任务完成！")
    
    print("\n" + "=" * 50)
    
    # 场景2：多次失败后求助
    print("场景2: 多次失败后求助")
    print("=" * 50)
    
    robot2 = DemoRobotController()
    robot2.navigable_list = [{"objectType": "Cabinet"}]
    robot2.failed_attempts = 2
    
    # 连续失败
    robot2.execute_task_step("搜索番茄", success=False)
    robot2.execute_task_step("搜索冰箱", success=False)
    question = robot2.execute_task_step("转向搜索", success=False)
    
    if question:
        # 模拟用户回答
        user_response = "让我来帮你，番茄在冰箱里，冰箱在房间的左边"
        print(f"👤 用户回答: {user_response}")
        robot2.receive_user_response(user_response)
        
        # 基于用户帮助继续执行
        print("🔄 基于用户帮助继续执行...")
        robot2.navigable_list.append({"objectType": "Fridge"})
        robot2.execute_task_step("导航到冰箱", success=True)
        robot2.execute_task_step("完成任务", success=True)
        print("🎉 任务完成！")
    
    print("\n" + "=" * 50)
    
    # 场景3：任务指令模糊
    print("场景3: 任务指令模糊")
    print("=" * 50)
    
    robot3 = DemoRobotController()
    robot3.taskname = "把东西放到合适的地方"
    robot3.navigable_list = [{"objectType": "Cabinet"}, {"objectType": "Counter"}, {"objectType": "Fridge"}]
    
    # 模糊情况
    current_state = "The task instruction is unclear about what objects to move and where to put them"
    question = robot3.handle_problem_situation(robot3.taskname, current_state)
    
    if question:
        print(f"🤖 机器人请求澄清: {question}")
        
        # 模拟用户回答
        user_response = "请把苹果放到冰箱里"
        print(f"👤 用户澄清: {user_response}")
        robot3.receive_user_response(user_response)
        
        # 基于澄清信息执行
        print("🔄 基于澄清信息执行...")
        robot3.taskname = "把苹果放到冰箱里"
        robot3.execute_task_step("搜索苹果", success=True)
        robot3.execute_task_step("导航到冰箱", success=True)
        robot3.execute_task_step("放置苹果", success=True)
        print("🎉 任务完成！")
    
    print("\n=== 演示完成 ===")

def demo_question_integration():
    """演示提问集成到任务执行流程"""
    print("\n=== 提问集成演示 ===\n")
    
    class IntegratedTaskExecutor:
        def __init__(self):
            self.failed_attempts = 0
            self.navigable_list = [{"objectType": "Cabinet"}, {"objectType": "Counter"}]
            self.memory = []
            self.taskname = "把番茄放进冰箱"
            self.current_step = 0
            self.steps = [
                "观察环境",
                "搜索番茄",
                "导航到目标",
                "执行操作",
                "完成任务"
            ]
        
        def execute_task(self):
            print(f"🚀 开始执行任务: {self.taskname}")
            print(f"📋 任务步骤: {self.steps}")
            print()
            
            for i, step in enumerate(self.steps):
                self.current_step = i
                print(f"步骤 {i+1}/{len(self.steps)}: {step}")
                
                # 模拟执行步骤
                success = self.attempt_step(step)
                
                if not success:
                    self.failed_attempts += 1
                    print(f"❌ 步骤失败，尝试次数: {self.failed_attempts}")
                    
                    # 检查是否需要提问
                    if self.should_ask_question():
                        question = self.ask_for_help()
                        print(f"🤖 机器人提问: {question}")
                        
                        # 模拟用户回答
                        user_response = self.get_user_response(step)
                        print(f"👤 用户回答: {user_response}")
                        
                        # 基于用户回答重新执行
                        print("🔄 基于用户回答重新执行...")
                        success = self.attempt_step_with_guidance(step, user_response)
                        
                        if success:
                            print(f"✅ 步骤成功: {step}")
                        else:
                            print(f"❌ 步骤仍然失败: {step}")
                            break
                    else:
                        print(f"❌ 步骤失败: {step}")
                        break
                else:
                    print(f"✅ 步骤成功: {step}")
                
                print()
            
            if self.current_step == len(self.steps) - 1:
                print("🎉 任务执行成功！")
            else:
                print("💥 任务执行失败")
        
        def attempt_step(self, step):
            # 模拟某些步骤会失败
            if step == "搜索番茄" and self.failed_attempts == 0:
                return False
            return True
        
        def attempt_step_with_guidance(self, step, guidance):
            # 模拟基于指导的执行成功
            return True
        
        def should_ask_question(self):
            return self.failed_attempts >= 1
        
        def ask_for_help(self):
            return f"我已经尝试了{self.failed_attempts}次但仍然无法完成步骤'{self.steps[self.current_step]}'。请帮助我。"
        
        def get_user_response(self, step):
            if step == "搜索番茄":
                return "番茄在冰箱里，冰箱在房间的另一边"
            elif step == "导航到目标":
                return "请转向搜索，目标可能在另一个方向"
            else:
                return "请继续尝试，我会指导你"
    
    # 执行集成演示
    executor = IntegratedTaskExecutor()
    executor.execute_task()

if __name__ == "__main__":
    demo_question_workflow()
    demo_question_integration() 