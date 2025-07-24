#!/usr/bin/env python3
"""
AI2-THOR Web Application
基于现有的第三人称观察器创建Web界面，支持键盘控制代理人移动
类似于 ai2thor.allenai.org/demo 的功能
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import cv2
import numpy as np
import base64
import threading
import time
import os
import sys
import math

# 添加data_engine到Python路径
sys.path.append('data_engine')

from ai2thor.controller import Controller
from RocAgent import RocAgent

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ai2thor-web-demo'
socketio = SocketIO(app, cors_allowed_origins="*")

class AI2THORWebController:
    """AI2-THOR Web控制器"""
    
    def __init__(self, scene="FloorPlan3", width=800, height=600):
        self.width = width
        self.height = height
        self.scene = scene
        self.controller = None
        self.agent = None
        self.running = False
        self.current_frame = None
        self.current_third_person_frame = None
        self.current_target_object_id = None
        self.frame_lock = threading.Lock()
        self.view_mode = "first_person"  # "first_person" or "third_person" or "dual"
        
        # 连接状态跟踪
        self.connection_failures = 0
        self.max_connection_failures = 3
        self.last_successful_action = time.time()
        self.controller_creation_time = None
        self.action_lock = threading.Lock()  # 防止并发动作执行
        self.circuit_breaker_open_time = None  # 熔断器开启时间
        self.circuit_breaker_timeout = 30  # 熔断器30秒后重试
        
        # 性能优化
        self.frame_skip_counter = 0
        self.frame_skip_rate = 2  # 每2帧跳过1帧以提高性能
        
        # 固定机位设置
        self.current_camera_position = 0  # 当前机位索引
        self.camera_positions = [
            {
                "name": "后上方跟随",
                "offset": {"distance": 2.5, "height": 2.0, "angle": 180, "pitch": 25},
                "fov": 75
            },
            {
                "name": "右上方",
                "offset": {"distance": 3.0, "height": 2.5, "angle": 270, "pitch": 30},
                "fov": 80
            },
            {
                "name": "左上方",
                "offset": {"distance": 3.0, "height": 2.5, "angle": 90, "pitch": 30},
                "fov": 80
            },
            {
                "name": "正上方",
                "offset": {"distance": 0.1, "height": 4.0, "angle": 0, "pitch": 90},
                "fov": 90
            },
            {
                "name": "远距离俯视",
                "offset": {"distance": 4.0, "height": 3.5, "angle": 225, "pitch": 35},
                "fov": 85
            }
        ]
        
        # 初始化场景
        self._init_scene()
        
        # 启动帧更新线程
        self.frame_thread = threading.Thread(target=self._frame_update_loop, daemon=True)
        self.frame_thread.start()
    
    def _init_scene(self):
        """初始化AI2-THOR场景"""
        try:
            # 首先清理任何现有资源
            if hasattr(self, 'controller') and self.controller:
                try:
                    self.controller.stop()
                except:
                    pass
                self.controller = None
            
            if hasattr(self, 'agent'):
                self.agent = None
            
            # 创建新的控制器
            self.controller = Controller(
                agentMode="default",
                visibilityDistance=2.0,
                scene=self.scene,
                gridSize=0.1,
                snapToGrid=True,
                renderDepthImage=False,
                renderInstanceSegmentation=True,
                width=self.width,
                height=self.height,
                fieldOfView=90,
                # 第三人称视角需要显示代理人
                makeAgentsVisible=True,
                quality="Medium"  # 平衡质量和性能
            )
            
            # 验证控制器初始化
            initial_event = self.controller.step(action="Pass")
            if initial_event is None or not hasattr(initial_event, 'metadata'):
                raise Exception("Controller initialization failed - no valid initial event")
            
            self.agent = RocAgent(self.controller)
            
            # 设置初始视角
            self.agent.get_corner_init_view()
            
            # 设置第三人称摄像头
            self._setup_third_person_camera()
            
            self.running = True
            self.controller_creation_time = time.time()
            self.connection_failures = 0
            self.last_successful_action = time.time()
            print(f"AI2-THOR场景 {self.scene} 初始化成功")
            
        except Exception as e:
            print(f"初始化AI2-THOR失败: {e}")
            self.running = False
            self.connection_failures += 1
            if hasattr(self, 'controller') and self.controller:
                try:
                    self.controller.stop()
                except:
                    pass
                self.controller = None
    
    def _setup_third_person_camera(self):
        """设置第三人称摄像头 - 使用当前选中的固定机位"""
        try:
            # 获取代理人当前位置
            agent_position = self.controller.last_event.metadata["agent"]["position"]
            agent_rotation = self.controller.last_event.metadata["agent"]["rotation"]["y"]
            
            # 获取当前机位配置
            camera_config = self.camera_positions[self.current_camera_position]
            offset = camera_config["offset"]
            
            # 计算摄像头位置
            if offset["distance"] > 0.5:  # 非正上方机位
                camera_angle = math.radians(agent_rotation + offset["angle"])
                camera_x = agent_position['x'] + offset["distance"] * math.sin(camera_angle)
                camera_z = agent_position['z'] + offset["distance"] * math.cos(camera_angle)
            else:  # 正上方机位
                camera_x = agent_position['x']
                camera_z = agent_position['z']
            
            third_person_camera_position = {
                'x': camera_x,
                'y': agent_position['y'] + offset["height"],
                'z': camera_z
            }
            
            # 计算摄像头朝向
            if offset["pitch"] < 90:  # 非垂直俯视
                look_at_yaw = math.degrees(math.atan2(
                    agent_position['x'] - camera_x,
                    agent_position['z'] - camera_z
                ))
            else:  # 垂直俯视
                look_at_yaw = agent_rotation  # 与代理人方向一致
            
            third_person_camera_rotation = {
                'x': offset["pitch"], 
                'y': look_at_yaw, 
                'z': 0
            }
            
            self.controller.step(dict(
                action='AddThirdPartyCamera',
                position=third_person_camera_position,
                rotation=third_person_camera_rotation,
                fieldOfView=camera_config["fov"]
            ))
            
            print(f"设置第三人称摄像头: {camera_config['name']}")
            
        except Exception as e:
            print(f"设置第三人称摄像头失败: {e}")
    
    def _update_third_person_camera(self):
        """动态更新第三人称摄像头位置以跟随代理人 - 使用当前固定机位"""
        try:
            agent_position = self.controller.last_event.metadata["agent"]["position"]
            agent_rotation = self.controller.last_event.metadata["agent"]["rotation"]["y"]
            
            # 获取当前机位配置
            camera_config = self.camera_positions[self.current_camera_position]
            offset = camera_config["offset"]
            
            # 计算摄像头位置
            if offset["distance"] > 0.5:  # 非正上方机位
                camera_angle = math.radians(agent_rotation + offset["angle"])
                camera_x = agent_position['x'] + offset["distance"] * math.sin(camera_angle)
                camera_z = agent_position['z'] + offset["distance"] * math.cos(camera_angle)
            else:  # 正上方机位
                camera_x = agent_position['x']
                camera_z = agent_position['z']
            
            # 计算摄像头朝向
            if offset["pitch"] < 90:  # 非垂直俯视
                look_at_yaw = math.degrees(math.atan2(
                    agent_position['x'] - camera_x,
                    agent_position['z'] - camera_z
                ))
            else:  # 垂直俯视
                look_at_yaw = agent_rotation  # 与代理人方向一致
            
            # 更新第三人称摄像头位置
            self.controller.step(dict(
                action='UpdateThirdPartyCamera',
                thirdPartyCameraId=0,
                position={
                    'x': camera_x,
                    'y': agent_position['y'] + offset["height"],
                    'z': camera_z
                },
                rotation={
                    'x': offset["pitch"],
                    'y': look_at_yaw,
                    'z': 0
                }
            ))
        except Exception as e:
            # 如果更新失败，忽略错误以避免影响性能
            pass
    
    def _frame_update_loop(self):
        """帧更新循环"""
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while self.running:
            try:
                if self.controller:
                    # Skip health check initially, but do it if we've had failures
                    if consecutive_failures > 0 and not self._is_controller_healthy():
                        print("Controller unhealthy in frame loop, attempting recreation...")
                        if self._recreate_controller():
                            consecutive_failures = 0
                        else:
                            consecutive_failures += 1
                            if consecutive_failures >= max_consecutive_failures:
                                print("Too many consecutive failures, stopping frame updates")
                                break
                            time.sleep(1)
                            continue
                    
                    # 帧跳过逻辑 - 每隔frame_skip_rate帧处理一次
                    self.frame_skip_counter += 1
                    if self.frame_skip_counter % self.frame_skip_rate == 0:
                        frames = self._process_frames()
                        if frames:
                            with self.frame_lock:
                                if 'first_person' in frames:
                                    self.current_frame = frames['first_person']
                                if 'third_person' in frames:
                                    self.current_third_person_frame = frames['third_person']
                            
                            # 通过WebSocket发送帧到前端
                            socketio.emit('frame_update', frames)
                            consecutive_failures = 0  # Reset failure count on success
                        else:
                            consecutive_failures += 1
                else:
                    print("No controller available for frame update")
                    consecutive_failures += 1
                
                time.sleep(0.15)  # ~6.7 FPS for better performance
                
            except Exception as e:
                consecutive_failures += 1
                error_msg = str(e).lower()
                
                if any(keyword in error_msg for keyword in ['write to closed file', 'connection', 'broken pipe']):
                    print(f"Frame update connection error: {e}")
                    if consecutive_failures < max_consecutive_failures:
                        print("Attempting to recreate controller...")
                        if self._recreate_controller():
                            consecutive_failures = 0
                else:
                    print(f"Frame update error: {e}")
                
                if consecutive_failures >= max_consecutive_failures:
                    print("Too many consecutive frame update failures, stopping")
                    break
                    
                time.sleep(0.5)
    
    def _process_frames(self):
        """处理当前帧，支持第一人称和第三人称视角"""
        try:
            frames = {}
            
            # 处理第一人称视角
            if hasattr(self.controller.last_event, 'frame'):
                fp_frame = self._process_single_frame(
                    self.controller.last_event.frame, 
                    add_crosshair=True, 
                    view_type="第一人称"
                )
                if fp_frame:
                    frames['first_person'] = fp_frame
            
            # 处理第三人称视角
            if (hasattr(self.controller.last_event, 'third_party_camera_frames') and 
                len(self.controller.last_event.third_party_camera_frames) > 0):
                tp_frame = self._process_single_frame(
                    self.controller.last_event.third_party_camera_frames[0], 
                    add_crosshair=False, 
                    view_type="第三人称"
                )
                if tp_frame:
                    frames['third_person'] = tp_frame
            
            return frames if frames else None
            
        except Exception as e:
            print(f"处理帧时出错: {e}")
            return None
    
    def _process_single_frame(self, frame, add_crosshair=True, view_type=""):
        """处理单个帧"""
        try:
            # 转换帧格式
            if hasattr(frame, 'copy') and isinstance(frame, np.ndarray):
                frame_bgr = frame[:, :, ::-1].copy()
            else:
                frame_np = np.array(frame)
                if frame_np.shape[-1] == 3:
                    frame_bgr = frame_np[:, :, ::-1].copy()
                else:
                    frame_bgr = frame_np.copy()
            
            h, w, _ = frame_bgr.shape
            
            # 添加视角标签
            if view_type:
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.8
                thickness = 2
                label_color = (255, 255, 255)
                bg_color = (0, 0, 0)
                
                text_size, _ = cv2.getTextSize(view_type, font, font_scale, thickness)
                text_x = 10
                text_y = 30
                
                # 添加背景矩形
                cv2.rectangle(frame_bgr, 
                            (text_x - 5, text_y - text_size[1] - 5),
                            (text_x + text_size[0] + 5, text_y + 5),
                            bg_color, -1)
                
                cv2.putText(frame_bgr, view_type, (text_x, text_y),
                           font, font_scale, label_color, thickness, cv2.LINE_AA)
            
            # 为第一人称视角添加十字光标和物体检测
            if add_crosshair:
                center_x, center_y = w // 2, h // 2
                cross_len = 15
                color = (0, 255, 0)  # 绿色
                thickness = 2
                
                # 画十字光标
                cv2.line(frame_bgr, (center_x - cross_len, center_y), 
                        (center_x + cross_len, center_y), color, thickness)
                cv2.line(frame_bgr, (center_x, center_y - cross_len), 
                        (center_x, center_y + cross_len), color, thickness)
                
                # 检测中心点物体
                object_name = self._detect_object_at_center(center_x, center_y)
                if object_name:
                    # 显示物体名称
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.7
                    thickness = 2
                    text_size, _ = cv2.getTextSize(object_name, font, font_scale, thickness)
                    text_width = text_size[0]
                    text_x = center_x - text_width // 2
                    text_y = center_y + cross_len + 40
                    
                    # 添加背景矩形
                    cv2.rectangle(frame_bgr, 
                                (text_x - 5, text_y - text_size[1] - 5),
                                (text_x + text_width + 5, text_y + 5),
                                (0, 0, 0), -1)
                    
                    cv2.putText(frame_bgr, object_name, (text_x, text_y),
                               font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
            
            # 转换为base64以便传输，提高画面清晰度
            _, buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return frame_base64
            
        except Exception as e:
            print(f"处理单个帧时出错: {e}")
            return None
    
    def _detect_object_at_center(self, center_x, center_y):
        """检测中心点的物体"""
        try:
            objects = self.controller.last_event.metadata.get("objects", [])
            instance_masks = getattr(self.controller.last_event, "instance_masks", None)
            
            if instance_masks:
                h, w = list(instance_masks.values())[0].shape
                for obj_id, mask in instance_masks.items():
                    if mask.shape == (h, w) and mask[center_y, center_x]:
                        self.current_target_object_id = obj_id
                        obj_map = {obj["objectId"]: obj for obj in objects}
                        obj = obj_map.get(obj_id)
                        if obj and obj.get("visible", False):
                            return obj.get("objectType") or obj.get("name")
                        break
            
            # 如果没有instance_masks，尝试segmentation_frame
            elif hasattr(self.controller.last_event, "segmentation_frame"):
                seg = self.controller.last_event.segmentation_frame
                h, w = seg.shape[:2]
                seg_pixel = tuple(seg[center_y, center_x])
                color_map = {tuple(obj.get("colorId")): obj for obj in objects 
                           if obj.get("colorId") and obj.get("visible", False)}
                obj = color_map.get(seg_pixel)
                if obj:
                    self.current_target_object_id = obj.get("objectId")
                    return obj.get("objectType") or obj.get("name")
            
            self.current_target_object_id = None
            return None
            
        except Exception as e:
            print(f"检测物体时出错: {e}")
            return None
    
    def _is_controller_healthy(self):
        """检查控制器是否健康"""
        try:
            if not self.controller:
                return False
            
            # 检查控制器是否太旧（超过30分钟重建）
            current_time = time.time()
            if (self.controller_creation_time and 
                current_time - self.controller_creation_time > 1800):  # 30分钟
                print("Controller is too old, needs recreation")
                return False
            
            # 检查是否长时间没有成功动作
            if current_time - self.last_successful_action > 60:  # 1分钟
                print("No successful actions for too long, checking connection")
                
            # 尝试执行简单的查询来检查连接
            test_event = self.controller.step(action="Pass")
            if test_event is None:
                return False
                
            # 检查是否有有效的事件数据
            if not hasattr(test_event, 'metadata'):
                return False
            
            # 检查元数据中是否有错误
            if hasattr(test_event, 'metadata') and test_event.metadata:
                if not test_event.metadata.get("lastActionSuccess", True):
                    error_msg = test_event.metadata.get("errorMessage", "").lower()
                    if any(keyword in error_msg for keyword in ['error encountered', 'scene', 'connection']):
                        print(f"Controller metadata indicates error: {error_msg}")
                        return False
                
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ['write to closed file', 'connection', 'broken pipe', 'socket', 'error encountered']):
                print(f"Controller connection lost: {e}")
                return False
            print(f"Controller health check failed: {e}")
            return False
    
    def _recreate_controller(self):
        """重新创建控制器"""
        try:
            print("Recreating AI2-THOR controller...")
            
            # 停止现有控制器
            if self.controller:
                try:
                    self.controller.stop()
                except:
                    pass
                finally:
                    self.controller = None
            
            # 停止代理
            if self.agent:
                self.agent = None
            
            # 等待一段时间让资源释放
            time.sleep(1)
            
            # 重新初始化
            self._init_scene()
            
            if self.running and self.controller:
                print("Controller recreated successfully")
                return True
            else:
                print("Failed to recreate controller")
                return False
                
        except Exception as e:
            print(f"Error recreating controller: {e}")
            self.running = False
            return False
    
    def switch_view_mode(self, mode):
        """切换视角模式"""
        valid_modes = ["first_person", "third_person", "dual"]
        if mode in valid_modes:
            self.view_mode = mode
            print(f"View mode switched to: {mode}")
            return True
        else:
            print(f"Invalid view mode: {mode}. Valid modes are: {valid_modes}")
            return False
    
    def get_view_mode(self):
        """获取当前视角模式"""
        return self.view_mode
    
    def switch_camera_position(self, position_index=None):
        """切换第三人称摄像头机位"""
        if position_index is None:
            # 循环切换下一个机位
            self.current_camera_position = (self.current_camera_position + 1) % len(self.camera_positions)
        else:
            # 切换到指定机位
            if 0 <= position_index < len(self.camera_positions):
                self.current_camera_position = position_index
            else:
                return False
        
        # 重新设置摄像头
        self._setup_third_person_camera()
        
        current_camera = self.camera_positions[self.current_camera_position]
        print(f"切换到机位: {current_camera['name']}")
        return True
    
    def get_camera_info(self):
        """获取当前摄像头信息"""
        current_camera = self.camera_positions[self.current_camera_position]
        return {
            "current_position": self.current_camera_position,
            "current_name": current_camera["name"],
            "total_positions": len(self.camera_positions),
            "all_positions": [camera["name"] for camera in self.camera_positions]
        }
    
    def reset_connection_state(self):
        """重置连接状态，用于手动恢复"""
        with self.action_lock:
            print("Manually resetting connection state")
            self.connection_failures = 0
            self.circuit_breaker_open_time = None
            self.last_successful_action = time.time()
    
    def get_connection_status(self):
        """获取连接状态信息"""
        return {
            "running": self.running,
            "connection_failures": self.connection_failures,
            "circuit_breaker_open": self.circuit_breaker_open_time is not None,
            "last_successful_action": self.last_successful_action,
            "controller_age": time.time() - self.controller_creation_time if self.controller_creation_time else None
        }
    
    def handle_action(self, action, params=None):
        """处理动作"""
        # 使用锁防止并发动作执行
        with self.action_lock:
            if not self.agent or not self.controller:
                return False
            
            # Mark params as used to avoid warning
            _ = params
            
            # 检查熔断器状态
            current_time = time.time()
            if self.circuit_breaker_open_time:
                if current_time - self.circuit_breaker_open_time < self.circuit_breaker_timeout:
                    print(f"Circuit breaker is open, not attempting action")
                    return False
                else:
                    print("Circuit breaker timeout reached, attempting to reset")
                    self.circuit_breaker_open_time = None
                    self.connection_failures = 0
            
            # 检查连接失败次数
            if self.connection_failures >= self.max_connection_failures:
                if not self.circuit_breaker_open_time:
                    print(f"Too many connection failures ({self.connection_failures}), opening circuit breaker")
                    self.circuit_breaker_open_time = current_time
                return False
            
            # Check if controller is still valid
            if not self._is_controller_healthy():
                print("Controller is unhealthy, attempting to recreate...")
                if not self._recreate_controller():
                    print("Failed to recreate controller")
                    self.connection_failures += 1
                    return False
                
            try:
                success = False
                
                # Helper function to safely execute actions with retry
                def execute_action(action_func, *args, max_retries=2):
                    for attempt in range(max_retries + 1):
                        try:
                            # Check controller health before executing action
                            if not self._is_controller_healthy():
                                if attempt < max_retries:
                                    print(f"Controller unhealthy, recreating... (attempt {attempt + 1})")
                                    if not self._recreate_controller():
                                        continue
                                else:
                                    print("Failed to recreate controller after retries")
                                    return False
                            
                            result = action_func(*args)
                            if result is None:
                                print(f"Warning: Action returned None (attempt {attempt + 1})")
                                self.connection_failures += 1
                                if attempt < max_retries:
                                    continue
                                return False
                                
                            success = result.metadata.get("lastActionSuccess", False) if hasattr(result, 'metadata') else False
                            
                            # 如果动作成功，更新成功时间并重置失败计数
                            if success:
                                self.last_successful_action = time.time()
                                self.connection_failures = max(0, self.connection_failures - 1)  # 减少失败计数
                                # 更新第三人称摄像头位置（针对移动和旋转动作）
                                if action in ['move_forward', 'move_backward', 'move_left', 'move_right', 'turn_left', 'turn_right']:
                                    self._update_third_person_camera()
                                return True
                            
                            # If action failed due to controller issues, try again
                            if not success and attempt < max_retries:
                                error_msg = result.metadata.get("errorMessage", "").lower() if hasattr(result, 'metadata') else ""
                                if any(keyword in error_msg for keyword in ['error encountered', 'scene', 'connection']):
                                    print(f"Action failed due to controller issue, retrying... (attempt {attempt + 1})")
                                    self.connection_failures += 1
                                    time.sleep(0.5)
                                    continue
                            
                            # 动作失败但不是连接问题
                            return success
                            
                        except Exception as e:
                            error_msg = str(e).lower()
                            if any(keyword in error_msg for keyword in ['write to closed file', 'connection', 'broken pipe']):
                                print(f"Connection error detected: {e}")
                                if attempt < max_retries:
                                    print(f"Attempting to recreate controller... (attempt {attempt + 1})")
                                    if self._recreate_controller():
                                        continue
                            else:
                                print(f"Error executing action: {e}")
                            
                            if attempt == max_retries:
                                return False
                    
                    return False
                
                if action == "move_forward":
                    success = execute_action(self.agent.action.action_mapping["move_ahead"], self.controller, 0.25)
                    
                elif action == "move_backward":
                    success = execute_action(self.agent.action.action_mapping["move_back"], self.controller, 0.25)
                    
                elif action == "move_left":
                    success = execute_action(self.agent.action.action_mapping["move_left"], self.controller, 0.25)
                    
                elif action == "move_right":
                    success = execute_action(self.agent.action.action_mapping["move_right"], self.controller, 0.25)
                    
                elif action == "turn_left":
                    success = execute_action(self.agent.action.action_mapping["rotate_left"], self.controller, 30)
                    
                elif action == "turn_right":
                    success = execute_action(self.agent.action.action_mapping["rotate_right"], self.controller, 30)
                    
                elif action == "look_up":
                    success = execute_action(self.agent.action.action_mapping["look_up"], self.controller, 30)
                    
                elif action == "look_down":
                    success = execute_action(self.agent.action.action_mapping["look_down"], self.controller, 30)
                    
                elif action == "pickup":
                    if self.current_target_object_id:
                        success = execute_action(self.agent.action.action_mapping["pick_up"], self.controller, self.current_target_object_id)
                    else:
                        success = False
                        
                elif action == "drop":
                    success = execute_action(self.agent.action.action_mapping["release"], self.controller)
                    
                elif action == "interact":
                    if self.current_target_object_id:
                        # 尝试开关物体
                        try:
                            objects = self.controller.last_event.metadata.get("objects", [])
                            obj_map = {obj["objectId"]: obj for obj in objects}
                            obj = obj_map.get(self.current_target_object_id)
                            if obj and obj.get("openable", False):
                                is_open = obj.get("isOpen", False)
                                if is_open:
                                    success = execute_action(self.agent.action.action_mapping["close"], self.controller, self.current_target_object_id)
                                else:
                                    success = execute_action(self.agent.action.action_mapping["open"], self.controller, self.current_target_object_id)
                            else:
                                success = False
                        except Exception as e:
                            print(f"Error in interact action: {e}")
                            success = False
                    else:
                        success = False
                
                return success
                
            except Exception as e:
                print(f"执行动作 {action} 时出错: {e}")
                return False
    
    def get_agent_info(self):
        """获取代理人信息"""
        if not self.controller:
            return {}
            
        try:
            metadata = self.controller.last_event.metadata
            agent_meta = metadata.get("agent", {})
            
            # 获取手持物体信息
            inventory = agent_meta.get("inventoryObjects", [])
            held_object = inventory[0] if inventory else None
            
            return {
                "position": agent_meta.get("position", {}),
                "rotation": agent_meta.get("rotation", {}),
                "held_object": held_object.get("objectType") if held_object else None,
                "target_object": self.current_target_object_id
            }
            
        except Exception as e:
            print(f"获取代理人信息时出错: {e}")
            return {}
    
    def change_scene(self, new_scene):
        """切换场景"""
        try:
            self.running = False
            time.sleep(0.1)  # 等待线程停止
            
            if self.controller:
                self.controller.stop()
            
            self.scene = new_scene
            self._init_scene()
            
            return self.running
            
        except Exception as e:
            print(f"切换场景时出错: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        self.running = False
        if self.controller:
            self.controller.stop()

# 全局控制器实例
thor_controller = None

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/init', methods=['POST'])
def init_environment():
    """初始化环境"""
    global thor_controller
    
    data = request.get_json()
    scene = data.get('scene', 'FloorPlan3')
    
    try:
        if thor_controller:
            thor_controller.cleanup()
        
        thor_controller = AI2THORWebController(scene=scene)
        
        if thor_controller.running:
            return jsonify({"success": True, "message": f"场景 {scene} 初始化成功"})
        else:
            return jsonify({"success": False, "message": "初始化失败"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/action', methods=['POST'])
def handle_action():
    """处理动作"""
    global thor_controller
    
    if not thor_controller or not thor_controller.running:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    data = request.get_json()
    action = data.get('action')
    params = data.get('params', {})
    
    try:
        success = thor_controller.handle_action(action, params)
        agent_info = thor_controller.get_agent_info()
        
        return jsonify({
            "success": success,
            "agent_info": agent_info
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/agent_info')
def get_agent_info():
    """获取代理人信息"""
    global thor_controller
    
    if not thor_controller or not thor_controller.running:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    try:
        agent_info = thor_controller.get_agent_info()
        connection_status = thor_controller.get_connection_status()
        return jsonify({
            "success": True, 
            "agent_info": agent_info,
            "connection_status": connection_status
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/reset_connection', methods=['POST'])
def reset_connection():
    """重置连接状态"""
    global thor_controller
    
    if not thor_controller:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    try:
        thor_controller.reset_connection_state()
        return jsonify({"success": True, "message": "连接状态已重置"})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/connection_status')
def get_connection_status():
    """获取连接状态"""
    global thor_controller
    
    if not thor_controller:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    try:
        status = thor_controller.get_connection_status()
        return jsonify({"success": True, "status": status})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/switch_view', methods=['POST'])
def switch_view():
    """切换视角模式"""
    global thor_controller
    
    if not thor_controller:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    data = request.get_json()
    mode = data.get('mode', 'first_person')
    
    try:
        success = thor_controller.switch_view_mode(mode)
        current_mode = thor_controller.get_view_mode()
        
        return jsonify({
            "success": success, 
            "current_mode": current_mode,
            "message": f"视角已切换至: {mode}" if success else f"无效的视角模式: {mode}"
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/view_mode')
def get_view_mode():
    """获取当前视角模式"""
    global thor_controller
    
    if not thor_controller:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    try:
        mode = thor_controller.get_view_mode()
        return jsonify({"success": True, "mode": mode})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/switch_camera', methods=['POST'])
def switch_camera():
    """切换第三人称摄像头机位"""
    global thor_controller
    
    if not thor_controller:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    data = request.get_json()
    position_index = data.get('position_index', None)
    
    try:
        success = thor_controller.switch_camera_position(position_index)
        camera_info = thor_controller.get_camera_info()
        
        return jsonify({
            "success": success,
            "camera_info": camera_info,
            "message": f"切换到机位: {camera_info['current_name']}" if success else "切换机位失败"
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@app.route('/api/camera_info')
def get_camera_info():
    """获取摄像头机位信息"""
    global thor_controller
    
    if not thor_controller:
        return jsonify({"success": False, "message": "环境未初始化"})
    
    try:
        camera_info = thor_controller.get_camera_info()
        return jsonify({"success": True, "camera_info": camera_info})
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

@socketio.on('connect')
def handle_connect():
    """WebSocket连接"""
    print('客户端已连接')
    emit('connected', {'message': '已连接到AI2-THOR服务器'})

@socketio.on('disconnect')
def handle_disconnect():
    """WebSocket断开连接"""
    print('客户端已断开连接')

@socketio.on('action')
def handle_websocket_action(data):
    """通过WebSocket处理动作"""
    global thor_controller
    
    if not thor_controller or not thor_controller.running:
        emit('action_result', {"success": False, "message": "环境未初始化"})
        return
    
    action = data.get('action')
    params = data.get('params', {})
    
    try:
        success = thor_controller.handle_action(action, params)
        agent_info = thor_controller.get_agent_info()
        
        emit('action_result', {
            "success": success,
            "agent_info": agent_info
        })
        
    except Exception as e:
        emit('action_result', {"success": False, "message": str(e)})

if __name__ == '__main__':
    import math
    
    # 创建templates目录
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # 创建static目录
    if not os.path.exists('static'):
        os.makedirs('static')
    
    print("AI2-THOR Web应用正在启动...")
    print("请在浏览器中访问: http://localhost:5001")
    
    try:
        socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        print("\n正在关闭应用...")
        if thor_controller:
            thor_controller.cleanup()