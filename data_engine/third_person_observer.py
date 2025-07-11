import cv2
import time
import math
import numpy as np
import threading
from typing import Optional, Dict, Any, Callable
from ai2thor.controller import Controller
from RocAgent import RocAgent
import pyautogui

class CameraManager:
    """摄像头管理类"""
    def __init__(self, controller: Controller, observer=None):
        self.controller = controller
        self.observer = observer
        self.window_name_fp = "AI2-THOR First Person View"
        self.window_name_tp = "AI2-THOR Top-down Camera"
        # 明确窗口初始化位置和大小
        self.fp_window_x = 100
        self.fp_window_y = 100
        self.fp_window_w = self.controller.width if hasattr(self.controller, 'width') else 400
        self.fp_window_h = self.controller.height if hasattr(self.controller, 'height') else 400
        # 鼠标中心补偿量（如发现鼠标不在画面中心可微调）
        self.offset_x = -100  # 鼓励你尝试+10, -10等
        self.offset_y = 125
        self._setup_windows()
        self.last_mouse_pos = None
        self.ignore_next_mouse_event = False
        cv2.setMouseCallback(self.window_name_fp, self.mouse_callback)
    
    def _setup_windows(self) -> None:
        """设置显示窗口"""
        cv2.namedWindow(self.window_name_fp)
        cv2.moveWindow(self.window_name_fp, self.fp_window_x, self.fp_window_y)
        cv2.namedWindow(self.window_name_tp)
        cv2.moveWindow(self.window_name_tp, 950, 100)
    
    def setup_third_person_camera(self) -> None:
        """设置第三人称摄像头"""
        scene_bounds = self.controller.last_event.metadata['sceneBounds']
        corner_points = [
            scene_bounds['cornerPoints'][2], 
            scene_bounds['cornerPoints'][3], 
            scene_bounds['cornerPoints'][6], 
            scene_bounds['cornerPoints'][7]
        ]
        
        reachable_positions = self.controller.step(
            dict(action='GetReachablePositions')
        ).metadata['actionReturn']
        
        min_distance = float('inf')
        target_position = None
        
        for scene_bounds_corner in corner_points:
            for position in reachable_positions:
                distance = ((position['x'] - scene_bounds_corner[0]) ** 2 + 
                          (position['z'] - scene_bounds_corner[2]) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    target_position = position
        
        center = scene_bounds['center']
        dx = center['x'] - target_position['x']
        dz = center['z'] - target_position['z']
        yaw = (math.degrees(math.atan2(dx, dz))) % 360
        
        third_person_camera_position = {
            'x': target_position['x'],
            'y': target_position['y'] + 1.5,
            'z': target_position['z']
        }
        third_person_camera_rotation = {'x': 45, 'y': yaw, 'z': 0}
        third_person_camera_fov = 90
        
        self.controller.step(dict(
            action='AddThirdPartyCamera',
            position=third_person_camera_position,
            rotation=third_person_camera_rotation,
            fieldOfView=third_person_camera_fov
        ))
    
    def update_display(self) -> str:
        """更新显示画面，并返回光标中心捕获到的objectId（如有）"""
        # 获取当前第三人称视角画面
        frame = self.controller.last_event.frame
        # 保证frame为np.ndarray
        if hasattr(frame, 'copy') and isinstance(frame, np.ndarray):
            frame_bgr = frame[:, :, ::-1].copy()
        else:
            # 兼容PIL.Image等
            frame_np = np.array(frame)
            if frame_np.shape[-1] == 3:
                frame_bgr = frame_np[:, :, ::-1].copy()
            else:
                frame_bgr = frame_np.copy()

        # 1. 画面中心显示十字光标
        h, w, _ = frame_bgr.shape
        center_x, center_y = w // 2, h // 2
        cross_len = 10
        color = (255, 255, 255)
        thickness = 2
        # 画横线
        cv2.line(frame_bgr, (center_x - cross_len, center_y), (center_x + cross_len, center_y), color, thickness)
        # 画竖线
        cv2.line(frame_bgr, (center_x, center_y - cross_len), (center_x, center_y + cross_len), color, thickness)

        # 2. 检查中心点是否有可见物体，显示物体名称
        object_name = None
        object_id_at_center = None
        # 获取所有可见物体
        objects = self.controller.last_event.metadata.get("objects", [])
        instance_masks = getattr(self.controller.last_event, "instance_masks", None)
        if instance_masks:
            # 只需遍历一次所有mask，找到中心点为True的objectId
            for obj_id, mask in instance_masks.items():
                if mask.shape == (h, w) and mask[center_y, center_x]:
                    object_id_at_center = obj_id
                    break
            if object_id_at_center:
                # 用dict加速objectId到object的查找
                obj_map = {obj["objectId"]: obj for obj in objects}
                obj = obj_map.get(object_id_at_center)
                if obj and obj.get("visible", False):
                    object_name = obj.get("objectType") or obj.get("name")
        # 如果没有 instance_masks，尝试 segmentation_frame
        elif hasattr(self.controller.last_event, "segmentation_frame"):
            seg = self.controller.last_event.segmentation_frame
            if seg.shape[:2] == (h, w):
                seg_pixel = tuple(seg[center_y, center_x])
                # 预构建colorId到object的映射
                color_map = {tuple(obj.get("colorId")): obj for obj in objects if obj.get("colorId") and obj.get("visible", False)}
                obj = color_map.get(seg_pixel)
                if obj:
                    object_name = obj.get("objectType") or obj.get("name")
                    object_id_at_center = obj.get("objectId")
        # 显示物体名称
        if object_name:
            # 计算文本宽度，实现居中
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            text_size, _ = cv2.getTextSize(object_name, font, font_scale, thickness)
            text_width = text_size[0]
            text_x = center_x - text_width // 2
            text_y = center_y + cross_len + 30
            cv2.putText(frame_bgr, object_name, (text_x, text_y),
                        font, font_scale, (255,255,255), thickness, cv2.LINE_AA)

        cv2.imshow(self.window_name_fp, frame_bgr)

        # 获取第三人称摄像头画面（俯视）
        if (hasattr(self.controller.last_event, 'third_party_camera_frames') and 
            len(self.controller.last_event.third_party_camera_frames) > 0):
            tp_frame = self.controller.last_event.third_party_camera_frames[0]
            tp_frame_bgr = tp_frame[:, :, ::-1]
            cv2.imshow(self.window_name_tp, tp_frame_bgr)
        return object_id_at_center

    def get_window_center(self):
        # 获取窗口中心坐标（相对于窗口）
        return self.fp_window_w // 2, self.fp_window_h // 2

    def get_window_absolute_center(self):
        # 动态获取窗口左上角，保证窗口被移动时也正确
        try:
            x, y, w, h = cv2.getWindowImageRect(self.window_name_fp)
            center_x = x + w // 2
            center_y = y + h // 2
            # 加上补偿量
            return center_x + self.offset_x, center_y + self.offset_y
        except Exception:
            return self.fp_window_x + self.fp_window_w // 2, self.fp_window_y + self.fp_window_h // 2

    def mouse_callback(self, event, x, y, flags, param):
        if self.ignore_next_mouse_event:
            self.ignore_next_mouse_event = False
            return
        if event == cv2.EVENT_MOUSEMOVE:
            center_x, center_y = self.get_window_center()
            dx = x - center_x
            dy = y - center_y
            if (dx != 0 or dy != 0) and self.observer is not None:
                self.observer.handle_mouse_move(dx, dy)
                # 重置鼠标到窗口内中心（屏幕坐标）
                abs_x, abs_y = self.get_window_absolute_center()
                self.ignore_next_mouse_event = True
                pyautogui.moveTo(abs_x, abs_y)
                # 调试输出
                # print(f"[DEBUG] moveTo({abs_x}, {abs_y})")
                # print(f"[DEBUG] pyautogui.position(): {pyautogui.position()}")


class InputHandler:
    """输入处理类"""
    
    def __init__(self, agent: RocAgent, observer=None):
        self.agent = agent
        self.gathering_images = False
        self.observer = observer  # 用于访问当前捕获物体id
        self.gather_thread = None # 新增：保存图片采集线程引用
        self._setup_key_mapping()
    
    def _setup_key_mapping(self) -> None:
        """设置键盘映射"""
        self.key_action_map = {
            ord('w'): lambda: self.agent.action.action_mapping["move_ahead"](self.agent.controller, 0.15),
            ord('a'): lambda: self.agent.action.action_mapping["move_left"](self.agent.controller, 0.15),
            ord('d'): lambda: self.agent.action.action_mapping["move_right"](self.agent.controller, 0.15),
            ord('s'): lambda: self.agent.action.action_mapping["move_back"](self.agent.controller, 0.15),
            ord('q'): "quit",
            ord('i'): "get_all_item_image",
            # 视角控制
            ord('8'): lambda: self.agent.action.action_mapping["look_up"](self.agent.controller, 2),
            ord('2'): lambda: self.agent.action.action_mapping["look_down"](self.agent.controller, 2),
            ord('4'): lambda: self.agent.action.action_mapping["rotate_left"](self.agent.controller, 2),
            ord('6'): lambda: self.agent.action.action_mapping["rotate_right"](self.agent.controller, 2),
            # 物体操作
            ord('m'): "move_object",
            ord('f'): "toggle_open_close",
            ord('e'): "pickup_object",  # 拾取物体
            ord('r'): "release_object",  # 释放物体
            ord('p'): "put_in_object"   # 放入容器
        }
    
    def handle_input(self, key: int) -> bool:
        """处理键盘输入，返回是否继续运行"""
        if key not in self.key_action_map:
            return True
            
        action = self.key_action_map[key]
        
        if action == "quit":
            return False
        elif action == "get_all_item_image":
            self._handle_image_gathering()
        elif action == "move_object":
            if self.observer:
                self.observer.move_object_at_cursor()
        elif action == "toggle_open_close":
            if self.observer:
                self.observer.toggle_open_close_at_cursor()
        elif action == "put_in_object":
            if self.observer:
                self.observer.put_in_object_at_cursor()
        elif action == "pickup_object":
            if self.observer:
                self.observer.pickup_object_at_cursor()
        elif action == "release_object":
            if self.observer:
                self.observer.release_object_at_cursor()
        else:
            action()
            
        return True
    
    def _handle_image_gathering(self) -> None:
        """处理图片采集"""
        if not self.gathering_images:
            self.gather_thread = threading.Thread(target=self._gather_images_thread)
            self.gather_thread.start()
        else:
            print("采集正在进行中，请稍候……")
    
    def _gather_images_thread(self) -> None:
        """图片采集线程"""
        self.gathering_images = True
        print("正在采集所有物品图片，请稍候……")
        self.agent.get_all_item_image()
        print("采集完成！")
        self.gathering_images = False
    
    def display_status(self) -> None:
        """显示控制状态"""
        print(f"\r控制键: WASD移动 | 8246视角控制 | M移动物体 | F开关物体 | E拾取 | R释放 | P放入容器 | I采集图片 | Q退出", 
              end="", flush=True)


class ThirdPersonObserver:
    """第三人称观察器主类"""
    
    def __init__(self, scene: str = "FloorPlan3", width: int = 400, height: int = 400):
        self.width = width
        self.height = height
        self.controller = self._init_controller(scene, width, height)
        self.agent = RocAgent(self.controller)
        self.camera_manager = CameraManager(self.controller, observer=self)
        self.current_target_object_id = None
        self.input_handler = InputHandler(self.agent, observer=self)
        
        self._setup_scene()

    def handle_mouse_move(self, dx, dy):
        # 鼠标左右移动控制旋转，dx>0右转，dx<0左转
        # 鼠标上下移动控制look up/down，dy>0向下，dy<0向上
        rotate_step = 0.1  # 每像素旋转度数（可调）
        look_step = 0.1    # 每像素look度数（可调）
        if abs(dx) > 0:
            if dx > 0:
                self.agent.action.action_mapping["rotate_right"](self.controller, abs(dx) * rotate_step)
            else:
                self.agent.action.action_mapping["rotate_left"](self.controller, abs(dx) * rotate_step)
        if abs(dy) > 0:
            if dy > 0:
                self.agent.action.action_mapping["look_down"](self.controller, abs(dy) * look_step)
            else:
                self.agent.action.action_mapping["look_up"](self.controller, abs(dy) * look_step)
    
    def _init_controller(self, scene: str, width: int, height: int) -> Controller:
        """初始化AI2-THOR控制器"""
        return Controller(
            agentMode="default",
            visibilityDistance=2.0,
            scene=scene,
            gridSize=0.1,
            snapToGrid=True,
            renderDepthImage=False,
            renderInstanceSegmentation=True,  # 启用分割
            width=width,
            height=height,
            fieldOfView=90
        )

    def _setup_scene(self) -> None:
        """设置场景"""
        # 设置第三人称初始视角
        self.agent.get_corner_init_view()
        
        # 设置第三人称摄像头
        self.camera_manager.setup_third_person_camera()
    
    def run(self) -> None:
        """运行观察器"""
        print("AI2-THOR 第三人称观察器已启动")
        print("控制说明：")
        print("- WASD: 移动控制")
        print("- 8246: 视角控制")
        print("- M: 移动光标捕获物体到前方")
        print("- F: 开关光标捕获物体（如支持）")
        print("- E: 拾取光标下的物体")
        print("- R: 释放手持物体到地上")
        print("- P: 将手持物体放入光标下的容器中")
        print("- I: 采集所有物品图片")
        print("- Q: 退出")
        print()
        
        try:
            while True:
                # 更新显示，并获取当前光标捕获物体id
                object_id_at_center = self.camera_manager.update_display()
                self.current_target_object_id = object_id_at_center
                # 更新鼠标控制
                # self.mouse_controller.update_view(self.controller, self.agent) # Removed as per edit hint
                
                # 显示状态
                self.input_handler.display_status()
                
                # 处理输入
                key = cv2.waitKey(1) & 0xFF
                if not self.input_handler.handle_input(key):
                    break
                time.sleep(0.03)
        except KeyboardInterrupt:
            print("\n程序被用户中断")
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """清理资源"""
        # 等待图片采集线程结束
        if self.input_handler.gather_thread is not None:
            self.input_handler.gather_thread.join(timeout=5)
        cv2.destroyAllWindows()
        self.controller.stop()
        print("仿真结束，资源已释放。")

    def move_object_at_cursor(self):
        """将光标捕获到的物体移动到agent前方0.5米处"""
        object_id = self.current_target_object_id
        if not object_id:
            print("当前光标下没有可移动物体！")
            return
        # 获取agent当前位置和朝向
        agent_meta = self.controller.last_event.metadata["agent"]
        pos = agent_meta["position"]
        rot = agent_meta["rotation"]["y"]
        # 计算前方0.5米的新位置
        rad = math.radians(rot)
        new_x = pos["x"] + 0.5 * math.sin(rad)
        new_z = pos["z"] + 0.5 * math.cos(rad)
        new_y = pos["y"]
        # 这里暂时保留TeleportObject逻辑
        event = self.controller.step(
            action="TeleportObject",
            objectId=object_id,
            position={"x": new_x, "y": new_y, "z": new_z},
            rotation={"x": 0, "y": rot, "z": 0},
            forceAction=True
        )
        if event.metadata.get("lastActionSuccess", False):
            print(f"物体 {object_id} 已移动到前方！")
        else:
            print(f"物体 {object_id} 移动失败！")

    def toggle_open_close_at_cursor(self):
        """F键：切换光标捕获物体的开关状态（如支持openable）"""
        object_id = self.current_target_object_id
        if not object_id:
            print("当前光标下没有可开关的物体！")
            return
        # 查找物体元数据
        objects = self.controller.last_event.metadata.get("objects", [])
        obj_map = {obj["objectId"]: obj for obj in objects}
        obj = obj_map.get(object_id)
        if not obj or not obj.get("openable", False):
            print("该物体不支持开关！")
            return
        is_open = obj.get("isOpen", False)
        if is_open:
            event = self.agent.action.action_mapping["close"](self.controller, object_id)
        else:
            event = self.agent.action.action_mapping["open"](self.controller, object_id)
        if event.metadata.get("lastActionSuccess", False):
            print(f"物体 {object_id} {'已关闭' if is_open else '已打开'}！")
        else:
            print(f"物体 {object_id} 开关操作失败！")

    def put_in_object_at_cursor(self):
        """P键：将手持物体放入光标下的容器中"""
        # 获取光标下的目标物体
        object_id = self.current_target_object_id
        if not object_id:
            print("当前光标下没有目标容器！")
            return
        # 检查目标物体是否为容器类型
        objects = self.controller.last_event.metadata.get("objects", [])
        obj_map = {obj["objectId"]: obj for obj in objects}
        target_obj = obj_map.get(object_id)
        if not target_obj:
            print("无法获取目标物体信息！")
            return
        if not target_obj.get("receptacle", False):
            print(f"目标物体 {object_id} 不是容器，无法放入物体！")
            return
        event = self.agent.action.action_mapping["put_in"](self.controller, object_id)
        if event.metadata.get("lastActionSuccess", False):
            print(f"已将手持物体放入容器 {object_id}！")
        else:
            error_msg = event.metadata.get("errorMessage", "未知错误")
            print(f"放入物体到容器 {object_id} 失败！错误信息：{error_msg}")

    def pickup_object_at_cursor(self):
        """E键：拾取光标下的物体"""
        object_id = self.current_target_object_id
        if not object_id:
            print("当前光标下没有可拾取物体！")
            return
        objects = self.controller.last_event.metadata.get("objects", [])
        obj_map = {obj["objectId"]: obj for obj in objects}
        target_obj = obj_map.get(object_id)
        if not target_obj:
            print(f"无法获取物体 {object_id} 的信息！")
            return
        if not target_obj.get("pickupable", False):
            print(f"物体 {object_id} ({target_obj.get('objectType', 'Unknown')}) 不可拾取！")
            return
        event = self.agent.action.action_mapping["pick_up"](self.controller, object_id)
        if event.metadata.get("lastActionSuccess", False):
            print(f"已拾取物体 {object_id}！")
        else:
            error_msg = event.metadata.get("errorMessage", "未知错误")
            print(f"拾取物体 {object_id} 失败！错误信息：{error_msg}")

    def release_object_at_cursor(self):
        """R键：释放手持物体到地上"""
        event = self.agent.action.action_mapping["release"](self.controller)
        if event.metadata.get("lastActionSuccess", False):
            print("已释放物体到地上！")
        else:
            error_msg = event.metadata.get("errorMessage", "未知错误")
            print(f"释放物体失败！错误信息：{error_msg}")




def main():
    """主函数"""
    observer = ThirdPersonObserver(width=800, height=800)
    observer.run()


if __name__ == "__main__":
    main()