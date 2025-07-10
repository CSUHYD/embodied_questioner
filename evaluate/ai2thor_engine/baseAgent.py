from .utils import EventObject
from .components.Action import BaseAction
import math
import time
from PIL import Image
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering
from abc import ABC, abstractmethod

import threading
class BaseAgent(ABC):

    def __init__(self, controller: Controller, scene="FloorPlan203", 
                 visibilityDistance=1.5, gridSize=0.1, fieldOfView=90,platform_type="GPU"):
        
        # retries = 0
        # while retries < MAX_RETRIES:
        #     try:
        #         self.init_controller_with_timeout(scene, visibilityDistance, gridSize, fieldOfView)
        #         break  # 如果成功初始化，则跳出循环
        #     except TimeoutException as te:
        #         print(f"controller init error: {te}, retry({retries + 1}/{MAX_RETRIES})...")
        #         retries += 1
        #         time.sleep(1)  # 可以在此处等待一段时间再重试
        # else:
        #     # 达到最大重试次数后仍未成功初始化
        #     raise RuntimeError("Failed to initialize Controller after multiple attempts.")   

        # self.controller = Controller(
        #     platform=CloudRendering, # 无头模式
        #     snapToGrid=False,
        #     # headless=True,
        #     # gpu_device=1,
        #     quality='Medium', # 设置渲染质量 Medium
        #     agentMode="default", # 设置机器人模式 arm default drone locobot
        #     massThreshold=None, # 设置质量阈值
        #     scene=scene, # 设置场景
        #     visibilityDistance=visibilityDistance, # 设置可见距离
        #     gridSize=gridSize, # 设置网格大小
        #     renderDepthImage=False, # 设置是否渲染深度图像
        #     renderInstanceSegmentation=False, # 设置是否渲染实例分割图像
        #     width=800, # 设置窗口宽度
        #     height=450, # 设置窗口高度
        #     fieldOfView=fieldOfView, # 设置视野
        # )
        
        self.scene = scene
        self.visibilityDistance = visibilityDistance
        self.gridSize = gridSize
        self.fieldOfView = fieldOfView
        if platform_type=="GPU":
            controller.reset(
                # platform=CloudRendering,
                snapToGrid=False,
                quality='Medium',
                agentMode="default",
                massThreshold=None,
                scene=scene,
                visibilityDistance=visibilityDistance,
                # gridSize=gridSize,
                renderDepthImage=False,
                renderInstanceSegmentation=False,
                width=800,
                height=450,
                fieldOfView=fieldOfView,
            )
        else: 
            controller.reset(
                snapToGrid=False,
                quality='Medium',
                agentMode="default",
                massThreshold=None,
                scene=scene,
                visibilityDistance=visibilityDistance,
                # gridSize=gridSize,
                renderDepthImage=False,
                renderInstanceSegmentation=False,
                width=800,
                height=450,
                fieldOfView=fieldOfView,
            )   
        
        self.controller = controller
        # self.controller = Controller(
        #     platform=CloudRendering, # 无头模式
        #     snapToGrid=False,
        #     # headless=True,
        #     # gpu_device=1,
        #     quality='Medium', # 设置渲染质量 Medium
        #     agentMode="default", # 设置机器人模式 arm default drone locobot
        #     massThreshold=None, # 设置质量阈值
        #     scene=scene, # 设置场景
        #     visibilityDistance=visibilityDistance, # 设置可见距离
        #     gridSize=gridSize, # 设置网格大小
        #     renderDepthImage=False, # 设置是否渲染深度图像
        #     renderInstanceSegmentation=False, # 设置是否渲染实例分割图像
        #     width=800, # 设置窗口宽度
        #     height=450, # 设置窗口高度
        #     fieldOfView=fieldOfView, # 设置视野
        # )
        self.eventobject = EventObject()
        self.step_count = 0
        self.last_action = "INIT"
        self.mermory = []
        self.action = BaseAction()
        self.legal_location = {} # 导航/交互的合法位置 (object_name, count)        
        # self.arm_reset()
        self.update_event()

    @abstractmethod
    def predict_next_action(self):
        pass

    def log_step_time_action(self, msg):
        print(f"time: {round(time.time())} step count: {self.step_count} setp: {self.controller.last_event.metadata}, action: {msg}")

    def loop(self):
        pass

    def update_event(self):
        pass
        
    def update_legal_location(self):
        visible_objects = []
        item_names, items = self.eventobject.get_visible_objects(self.controller.last_event)
        for item_name, item in zip(item_names, items):
            volume = self.eventobject.get_item_volume(self.controller.last_event, item_name)
            if volume <= 0.1:
                if item["distance"] <= 1.5:
                    visible_objects.append(item["name"])
            elif volume <= 0.5:
                if item["distance"] <= 2.5:
                    visible_objects.append(item["name"])
            elif volume <= 1:
                if item["distance"] <= 5.0:
                    visible_objects.append(item["name"])
            else:
                if item["distance"] <= 10.0:
                    visible_objects.append(item["name"])
        for item_name in visible_objects:
            if item_name not in self.legal_location.keys():
                self.legal_location[item_name] = 1
            else:
                self.legal_location[item_name] += 1

    def get_agent_position(self):
        return self.controller.last_event.metadata['agent']['position']
    
    def get_agent_rotation(self):
        return self.controller.last_event.metadata['agent']['rotation']
    
    def get_agent_horizon(self):
        return self.controller.last_event.metadata['agent']['cameraHorizon']
    
    def get_camera_position(self):
        return self.controller.last_event.metadata['cameraPosition']

    def get_camera_rotation(self):
        return self.controller.last_event.pose_discrete[3]

    def save_frame(self, kargs={}, prefix_save_path="./data/item_image"):
        import os
        if prefix_save_path != "./data/item_image":
            path = prefix_save_path
        else:
            path = os.path.join(prefix_save_path, self.scene)
        if not os.path.exists(path):
            os.makedirs(path)
        
        image_name = ""
        for key in kargs.keys():
            if key != "third_party_camera_frames" and key != "no_agent_view":
                image_name += f"_{kargs[key]}"
                
        # 获取第三方相机的图像
        if "third_party_camera_frames" in kargs.keys():
            image = Image.fromarray(self.controller.last_event.third_party_camera_frames[-1])
            # current_path = os.getcwd()
            # full_path = os.path.join(current_path, path)
            # full_path = os.path.normpath(full_path)
            image.save(f"{path}/{self.scene}_third_party{image_name}.png", format="PNG")
            kargs.pop("third_party_camera_frames")
        
        if "no_agent_view" not in kargs.keys():
            image = Image.fromarray(self.controller.last_event.frame)
            # current_path = os.getcwd()
            # full_path = os.path.join(current_path, path)
            # full_path = os.path.normpath(full_path)
            image.save(f"{path}/{self.scene}{image_name}.png", format="PNG")

        return f"{path}/{self.scene}{image_name}.png"

    def arm_reset(self):
        try:
            self.controller.step(
                action="MoveArm",
                position=dict(x=0, y=0, z=-1),
                coordinateSpace="armBase",
                restrictMovement=False,
                speed=1,
                returnToStart=True,
                fixedDeltaTime=0.02
            )
        except Exception as e:
            print(e)

    # 调整agent的视野范围
    def adjust_agent_fieldOfView(self, fieldOfView):
        self.backup()
        self.controller.reset(self.scene, fieldOfView=fieldOfView)
        self.recover()

    # 备份agent和object的状态
    def backup(self):
        # agent 记录当前状态
        angent_position = self.get_agent_position()
        angent_rotation = self.get_agent_rotation()
        agent_horizon = self.get_agent_horizon()
        self.agent_state.append([angent_position, angent_rotation, agent_horizon])
        # object 记录当前状态
        for item in self.eventobject.get_objects(self.controller.last_event)[0]:
            self.object_state[item["name"]] = item

    # 恢复最近一次agent和object的状态    
    def recover(self):
        # 恢复agent状态
        angent_position = self.agent_state[-1][0]
        angent_rotation = self.agent_state[-1][1]
        agent_horizon = self.agent_state[-1][2]
        self.action.action_mapping["teleport"](self.controller, position=angent_position, rotation=angent_rotation, horizon=agent_horizon)
        self.update_event()
        # 恢复object状态

    def compute_position(self, item):
        target_position = None
        target_rotation = None
        event = self.controller.step(dict(action='GetInteractablePoses', objectId=item['objectId']))
        reachable_positions = event.metadata['actionReturn']
        # 如果该物品找不到交互位置，可能是物品被包含，或者物品没有交互位置，不保存该物品视觉信息
        if len(reachable_positions) == 0:
            print("No reachable positions found.")
            return target_position, target_rotation
        # 从候选位置中选择最合适的位置
        front_positions=[]
        side_positions=[]
        
        for position in reachable_positions:
            # 1.是否存在正面位置（方向和物体方向相向）
            if round(abs(position['rotation'] - item['rotation']['y'])) == 180:
                front_positions.append(position)
            # 2.是否存在侧面位置（方向和物体方向夹角90）
            elif round(abs(position['rotation'] - item['rotation']['y'])) == 90:
                side_positions.append(position)
        
        # 如果存在正面位置，选择最远的正面位置
        if len(front_positions) > 0:
            max_distance = 0
            for position in front_positions:
                distance = math.sqrt((position['x'] - item['position']['x'])**2 + (position['z'] - item['position']['z'])**2)
                if distance > max_distance:
                    max_distance = distance
                    target_position = position
        
        # 如果不存在正面位置，选择最远的侧面位置
        if target_position is None and len(side_positions) > 0:
            max_distance = 0
            for position in side_positions:
                distance = math.sqrt((position['x'] - item['position']['x'])**2 + (position['z'] - item['position']['z'])**2)
                if distance > max_distance:
                    max_distance = distance
                    target_position = position
        
        # 如果不存在正面位置和侧面位置，选择最远的位置
        if target_position is None:
            max_distance = 0
            for position in reachable_positions:
                distance = math.sqrt((position['x'] - item['position']['x'])**2 + (position['z'] - item['position']['z'])**2)
                if distance > max_distance:
                    max_distance = distance
                    target_position = position

        return target_position, dict(x=0, y=target_position['rotation'], z=0)

    def compute_position_1(self, item, reachable_positions):
        target_position = None
        target_rotation = None
        min_distance = float('inf')
        for position in reachable_positions:
            distance = math.sqrt((position['x'] - item['position']['x'])**2 + (position['z'] - item['position']['z'])**2)
            if distance < min_distance:
                min_distance = distance
                target_position = position
        rotation = target_position['rotation'] if "rotation" in target_position.keys() else 0
        return target_position, dict(x=0, y=rotation, z=0)

    def compute_position_8(self, item, pre_target_positions):
        target_position = None
        target_rotation = None
        event = self.controller.step(dict(action='GetInteractablePoses', objectId=item['objectId']))
        # event = self.controller.step(dict(action='GetReachablePositions'))
        reachable_positions = event.metadata['actionReturn']
        reachable_positions = [position for position in reachable_positions if math.sqrt((position['x'] - item['position']['x'])**2 + (position['z'] - item['position']['z'])**2) <= 1.5]
        if len(reachable_positions) == 0:
            print("No reachable positions found.")
            return target_position, target_rotation
        if pre_target_positions != []:
            reachable_positions = [position for position in reachable_positions \
                               if position not in pre_target_positions]
        # 如果物体体积小于0.01，选择距离最近的位置
        if self.eventobject.get_item_volume(self.controller.last_event, item['name']) <= 0.1 and self.eventobject.get_item_surface_area(self.controller.last_event, item['name']) <= 1:
            target_position, target_rotation = self.compute_position_1(item, reachable_positions)
            return target_position, target_rotation
        # Possible angles to choose from
        angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
        # 四舍五入(item["rotation"]['y'])
        item_rotation = min(angles, key=lambda angle: abs(angle - round(item["rotation"]['y'])))
        item_rotation = 0 if item_rotation == 360 else item_rotation
        target_position = None
        target_rotation = None
        candidate_positions = []

        if item_rotation == 180: # agent x最接近/相等，z比item小
            target_rotation = dict(x=0, y=0, z=0)
            # 将agent的x坐标与item的x坐标相等的位置,或者x坐标位置小于最小距离的位置, 
            for tolerance in [0.1, 0.2, 0.3, 0.4, 0.5]:
                if len(candidate_positions) == 0:
                    candidate_positions = [position for position in reachable_positions if abs(position['x'] - item['position']['x']) <= tolerance]
                else:
                    break
            front_positions = []
            back_positions = []         
            for position in candidate_positions:
                if position['z'] < item['position']['z']:
                    front_positions.append(position)
                elif position['z'] > item['position']['z']:
                    back_positions.append(position)

            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)
            
            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_rotation is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=180, z=0)
                target_position = self.compute_closest_positions(item, back_positions)

        elif item_rotation == 270: # agent z最接近/相等，x比item小
            target_rotation = dict(x=0, y=90, z=0)
            # 将agent的z坐标与item的z坐标相等的位置,或者z坐标位置小于最小距离的位置,
            for tolerance in [0.1, 0.2, 0.3, 0.4, 0.5]:
                if len(candidate_positions) == 0:
                    candidate_positions = [position for position in reachable_positions if abs(position['z'] - item['position']['z']) <= tolerance]
                else:
                    break
            front_positions = []
            back_positions = []
            for position in candidate_positions:
                if position['x'] < item['position']['x']:
                    front_positions.append(position)
                elif position['x'] > item['position']['x']:
                    back_positions.append(position)

            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)
            
            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_position is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=270, z=0)
                target_position = self.compute_closest_positions(item, back_positions)
            
        elif item_rotation == 0: # agent x最接近/相等，z比item大
            target_rotation = dict(x=0, y=180, z=0)
            # 将agent的x坐标与item的x坐标相等的位置,或者x坐标位置小于最小距离的位置
            for tolerance in [0.1, 0.2, 0.3, 0.4, 0.5]:
                if len(candidate_positions) == 0:
                    candidate_positions = [position for position in reachable_positions if abs(position['z'] - item['position']['z']) <= tolerance]
                else:
                    break

            front_positions = []
            back_positions = []
            for position in candidate_positions:
                if position['z'] > item['position']['z']:
                    front_positions.append(position)
                elif position['z'] < item['position']['z']:
                    back_positions.append(position)
            
            # 如果正面位置存在，选择夹角最小的位置
            target_position_front=None
            if len(front_positions) > 0:
                target_position_front = self.compute_closest_positions(item, front_positions)
            
            # 如果正面位置不存在，选择夹角最小的背面位置
            target_position_back=None
            if len(back_positions) > 0:
                target_rotation = dict(x=0, y=0, z=0)
                target_position_back = self.compute_closest_positions(item, back_positions)

            # 选择和物品距离最近的位置
            if target_position_front is not None and target_position_back is not None:
                distance_front = math.sqrt((target_position_front['x'] - item['position']['x'])**2 + (target_position_front['z'] - item['position']['z'])**2)
                distance_back = math.sqrt((target_position_back['x'] - item['position']['x'])**2 + (target_position_back['z'] - item['position']['z'])**2)
                if distance_front < distance_back:
                    target_position = target_position_front
                else:
                    target_position = target_position_back
            elif target_position_front is not None:
                target_position = target_position_front
            elif target_position_back is not None:
                target_position = target_position_back

        elif item_rotation == 90: # agent z最接近/相等，x比item大
            target_rotation = dict(x=0, y=270, z=0)
            # 将agent的z坐标与item的z坐标相等的位置,或者z坐标位置小于最小距离的位置, 
            for tolerance in [0.1, 0.2, 0.3, 0.4, 0.5]:
                if len(candidate_positions) == 0:
                    candidate_positions = [position for position in reachable_positions if abs(position['z'] - item['position']['z']) <= tolerance]
                else:
                    break
            front_positions = []
            back_positions = []
            for position in candidate_positions:
                if position['x'] > item['position']['x']:
                    front_positions.append(position)
                elif position['x'] < item['position']['x']:
                    back_positions.append(position)
            
            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)
            
            # 如果正面位置不存在，选择夹角最小的背面位置
            elif len(back_positions) > 0:
                target_rotation = dict(x=0, y=90, z=0)
                target_position = self.compute_closest_positions(item, back_positions)

        elif item_rotation == 45: # agent x比item大，z比item大
            target_rotation = dict(x=0, y=225, z=0)
            front_positions = []
            back_positions = []
            for position in reachable_positions:
                # 将agent的x坐标大于item的x坐标的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if position['x'] > item['position']['x'] and position['z'] > item['position']['z']:
                    front_positions.append(position)
                elif position['x'] < item['position']['x'] and position['z'] < item['position']['z']:
                    back_positions.append(position)
            
            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)

            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_position is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=45, z=0)
                target_position = self.compute_closest_positions(item, back_positions)

        elif item_rotation == 135: # agent x比item大，z比item小
            target_rotation = dict(x=0, y=315, z=0)
            front_positions = []
            back_positions = []
            front_side_positions = []
            back_side_positions = []
            for position in reachable_positions:
                # 将agent的x坐标小于item的x坐标的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if position['x'] > item['position']['x'] and position['z'] < item['position']['z']:
                    front_positions.append(position)
                elif position['x'] < item['position']['x'] and position['z'] > item['position']['z']:
                    back_positions.append(position)
                # 侧边位置x坐标大于item的x坐标的位置且z坐标大于item的z坐标
                elif position['x'] > item['position']['x'] and position['z'] > item['position']['z']:
                    front_side_positions.append(position)
                # 侧边
                elif position['x'] < item['position']['x'] and position['z'] < item['position']['z']:
                    back_side_positions.append(position)
            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)
            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_position is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=135, z=0)
                target_position = self.compute_closest_positions(item, back_positions)
            # 如果正面位置和背面位置都不存在，选择侧边位置
            if target_position is None and len(front_side_positions) > 0:
                target_rotation = dict(x=0, y=225, z=0)
                target_position = self.compute_closest_positions(item, front_side_positions)
            if target_position is None and len(back_side_positions) > 0:
                target_rotation = dict(x=0, y=45, z=0)
                target_position = self.compute_closest_positions(item, back_side_positions)

        elif item_rotation == 225: # agent x比item小，z比item小
            target_rotation = dict(x=0, y=45, z=0)
            front_positions = []
            back_positions = []
            for position in reachable_positions:
                # 将agent的x坐标小于item的x坐标的位置, 以及agent的z坐标小于item的z坐标的位置加入候选位置
                if position['x'] < item['position']['x'] and position['z'] < item['position']['z']:
                    front_positions.append(position)
                elif position['x'] > item['position']['x'] and position['z'] > item['position']['z']:
                    back_positions.append(position)

            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)
            
            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_position is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=225, z=0)
                target_position = self.compute_closest_positions(item, back_positions)
                
        elif item_rotation == 315: # agent x比item小，z比item大
            target_rotation = dict(x=0, y=135, z=0)
            front_positions = []
            back_positions = []
            for position in reachable_positions:
                # 将agent的x坐标大于item的x坐标的位置, 以及agent的z坐标小于item的z坐标的位置加入候选位置
                if position['x'] < item['position']['x'] and position['z'] > item['position']['z']:
                    front_positions.append(position)
                elif position['x'] > item['position']['x'] and position['z'] < item['position']['z']:
                    back_positions.append(position)
            
            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                target_position = self.compute_closest_positions(item, front_positions)

            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_position is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=315, z=0)
                target_position = self.compute_closest_positions(item, back_positions)

        if target_position is None:
            target_position, target_rotation = self.compute_position_1(item, reachable_positions)
        return target_position, target_rotation
    
    def compute_closest_positions_xxx(self, item, candidate_positions, gap=0.1):
        item_position = item["position"]
        item_volume = self.eventobject.get_item_volume(self.controller.last_event, item['name'])
        item_surface_area = self.eventobject.get_item_surface_area(self.controller.last_event, item['name'])
        target_position = None
        A = 1
        B = -math.tan(math.radians(item['rotation']['y']))
        C = -item_position['x'] - B * item_position['z']
        # 0. 大物体优先考虑方向，小物体优先考虑远近
        if item_surface_area > 0.5 or item_volume>0.5:
            # 2.2 计算最接近直线的候选点（0.1）
            min_dinstance = float('inf')
            closest_points = []
            for position in candidate_positions:
                x0 = position['x']
                z0 = position['z']
                numerator = abs(A * z0 + B * x0 + C)
                denominator = math.sqrt(A**2 + B**2)
                distance =  numerator / denominator
                if distance <= min_dinstance + gap:
                    if distance < min_dinstance:
                        min_dinstance = distance
                    closest_points.append(position)
            
            closest_points = sorted(closest_points, key=lambda position: math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2))
            # 根据物体体积和表面积，选择合适的距离
            if item_surface_area <= 1:
                target_position = closest_points[0] if len(closest_points) != 0 else None
            elif item_surface_area <= 2:
                closest_points = [position for position in candidate_positions
                                if 0.5<=math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1]
                target_position = closest_points[0] if len(closest_points) != 0 else None
            # 1.3.体积在1-～之间，先将距离物体小于2m的点加入候选点，从最接近直线的候选点中选择距离最远的点
            else:
                closest_points = [position for position in candidate_positions
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1]
                target_position = closest_points[len(closest_points)//2] if len(closest_points) != 0 else None

            # else:
            #     closest_points = [position for position in candidate_positions 
            #                     if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1.5]
            #     target_position = closest_points[-1] if len(closest_points) != 0 else None
            return target_position
        else:
            # 1.优先考虑距离物体的远近，再考虑距离正面的远近
            closest_points = []
            # 根据物体体积和表面积，选择合适的距离
            # 1.1体积在0-0.2之间，表面积在0.5以内选择距离小于0.5米的点
            
            if item_volume <= 0.2 and item_surface_area <=0.5:
                closest_points = [position for position in candidate_positions 
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 0.5]
            
            # 1.2.体积在0.5-1之间，先将距离物体小于1m的点加入候选点，然后选择最大距离和最小距离中间的点,按照距离排序，选择中间的点
            elif item_volume <= 1 and item_surface_area <= 1:
                closest_points = [position for position in candidate_positions 
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1]
            
            # 1.3.体积在1-～之间，先将距离物体小于2m的点加入候选点，从最接近直线的候选点中选择距离最远的点
            elif item_volume <= 2 and item_surface_area <= 2:
                closest_points = [position for position in candidate_positions 
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1.5]
            else:
                closest_points = [position for position in candidate_positions 
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 2]

            # closest_points = sorted(closest_points, key=lambda position: math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2))
            # closest_points = closest_points[len(closest_points)//2:]
            # 2.1 直线方程 AX+BZ+C=0
            
            # 2.2 计算最接近直线的候选点（0.1）
            min_dinstance = float('inf')
            for position in closest_points:
                x0 = position['x']
                z0 = position['z']
                numerator = abs(A * z0 + B * x0 + C)
                denominator = math.sqrt(A**2 + B**2)
                distance =  numerator / denominator
                if distance < min_dinstance:
                    min_dinstance = distance
                    target_position = position
            
            return target_position

    def compute_closest_positions(self, item, candidate_positions, gap=0.1):
        item_position = item["position"]
        item_volume = self.eventobject.get_item_volume(self.controller.last_event, item['name'])
        item_surface_area = self.eventobject.get_item_surface_area(self.controller.last_event, item['name'])
        # 2.1 直线方程 AX+BZ+C=0
        A = 1
        B = -math.tan(math.radians(item['rotation']['y']))
        C = -item_position['x'] - B * item_position['z']
        
        # 2.2 计算最接近直线的候选点（0.1）
        min_dinstance = float('inf')
        closest_points = []
        for position in candidate_positions:
            x0 = position['x']
            z0 = position['z']
            numerator = abs(A * z0 + B * x0 + C)
            denominator = math.sqrt(A**2 + B**2)
            distance =  numerator / denominator
            if distance <= min_dinstance + gap:
                if distance < min_dinstance:
                    min_dinstance = distance
                closest_points.append(position)

        # 根据物体体积和表面积，选择合适的距离
        # 1.体积在0-0.1之间，选择距离最近的点
        if item_volume <= 0.2 and item_surface_area <=0.5:
            min_distance = float('inf')
            for position in closest_points:
                distance = math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2)
                if distance < min_distance:
                    min_distance = distance
                    target_position = position
            return target_position
        
        # 2.体积在0.5-1之间，选择最大距离和最小距离中间的点,按照距离排序，选择中间的点
        elif item_volume <= 1 and item_surface_area <= 1:
            closest_points = [position for position in closest_points
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1]
            closest_points = sorted(closest_points, key=lambda position: math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2))
            
            return closest_points[len(closest_points)//2] if len(closest_points) != 0 else None
        # 3.体积在1-～之间，选择距离最远的点
        # 从最接近直线的候选点中选择距离最远的点
        else:
            max_distance = 0
            target_position = None
            closest_points = [position for position in closest_points
                                if math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2) <= 1]
            for position in closest_points:
                distance = math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2)
                if distance > max_distance:
                    max_distance = distance
                    target_position = position
        
        return target_position
    
    def compute_position_(self, item):
        target_position = None
        target_rotation = None
        event = self.controller.step(dict(action='GetInteractablePoses', objectId=item['objectId']))
        # event = self.controller.step(dict(action='GetReachablePositions'))
        reachable_positions = event.metadata['actionReturn']
        if len(reachable_positions) == 0:
            print("No reachable positions found.")
            return target_position, target_rotation
        
        item_position = item["position"]
        
        # Possible angles to choose from
        angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
        # 四舍五入(item["rotation"]['y'])
        item_rotation = min(angles, key=lambda angle: abs(angle - round(item["rotation"]['y'])))
        item_rotation = 0 if item_rotation == 360 else item_rotation
        target_position = None
        target_rotation = None
        # min_distance_z = float('inf')
        # min_distance_x = float('inf')
        candidate_positions = []
        max_distance_z = 0
        max_distance_x = 0
        if item_rotation == 180: # agent x最接近/相等，z比item小
            target_rotation = dict(x=0, y=0, z=0)
            for position in reachable_positions:
                # 将agent的x坐标与item的x坐标相等的位置,或者x坐标位置小于最小距离的位置, 以及agent的z坐标小于item的z坐标的位置加入候选位置
                if abs(position['x'] - item['position']['x'])<=0.05: # or abs(position['x'] - item['position']['x']) < min_distance_x) and (position['z'] < item['position']['z']
                    candidate_positions.append(position)
                    # min_distance_x = min(abs(position['x'] - item['position']['x']), min_distance_x)
                # elif abs(position['z'] - item['position']['z']) < min_distance_z:
                #     candidate_positions.append(position) if len(candidate_positions)==0 else candidate_positions[-1] = position
                #     min_distance_z = abs(position['z'] - item['position']['z'])
                        
            for position in candidate_positions:
                if position['z'] < item['position']['z'] and max_distance_z < abs(position['z'] - item['position']['z']):
                    target_position = position
                    max_distance_z = abs(position['z'] - item['position']['z'])
            
            if target_position is None:
                for position in candidate_positions:
                    if position['z'] > item['position']['z'] and max_distance_z < abs(position['z'] - item['position']['z']):
                        target_position = position
                        max_distance_z = abs(position['z'] - item['position']['z'])        
                target_rotation = dict(x=0, y=180, z=0)
            
            
            #     distance_x = abs(position['x'] - item['position']['x'])
            #     distance_z = abs(position['z'] - item['position']['z'])
            #     if distance_x==min_distance_x and distance_z <= min_distance_z:
            #         min_distance_z = distance_z
            #         target_position = position

        elif item_rotation == 270: # agent z最接近/相等，x比item小
            target_rotation = dict(x=0, y=90, z=0)
            for position in reachable_positions:
                # 将agent的z坐标与item的z坐标相等的位置,或者z坐标位置小于最小距离的位置, 以及agent的x坐标小于item的x坐标的位置加入候选位置
                if abs(position['z'] - item['position']['z'])<=0.05:
                    candidate_positions.append(position)

            for position in candidate_positions:
                if position['x'] < item['position']['x'] and max_distance_x < abs(position['x'] - item['position']['x']):
                    target_position = position
                    max_distance_x = abs(position['x'] - item['position']['x'])

            if target_position is None:
                for position in candidate_positions:
                    if position['x'] > item['position']['x'] and max_distance_x < abs(position['x'] - item['position']['x']):
                        target_position = position
                        max_distance_x = abs(position['x'] - item['position']['x'])
                target_rotation = dict(x=0, y=270, z=0)
                
        elif item_rotation == 0: # agent x最接近/相等，z比item大
            target_rotation = dict(x=0, y=180, z=0)
            for position in reachable_positions:
                # 将agent的x坐标与item的x坐标相等的位置,或者x坐标位置小于最小距离的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if abs(position['x'] - item['position']['x'])<=0.05:
                    candidate_positions.append(position)

            for position in candidate_positions:
                if position['z'] > item['position']['z'] and max_distance_z < abs(position['z'] - item['position']['z']):
                    target_position = position
                    max_distance_z = abs(position['z'] - item['position']['z'])
            
            if target_position is None:
                for position in candidate_positions:
                    if position['z'] < item['position']['z'] and max_distance_z < abs(position['z'] - item['position']['z']):
                        target_position = position
                        max_distance_z = abs(position['z'] - item['position']['z'])
                target_rotation = dict(x=0, y=0, z=0)
        
        elif item_rotation == 90: # agent z最接近/相等，x比item大
            target_rotation = dict(x=0, y=270, z=0)
            for position in reachable_positions:
                # 将agent的z坐标与item的z坐标相等的位置,或者z坐标位置小于最小距离的位置, 
                if abs(position['z'] - item['position']['z'])<=0.05:
                    candidate_positions.append(position)
            
            # agent的x坐标大于item的x坐标的位置加入候选位置
            for position in candidate_positions:
                if position['x'] > item['position']['x'] and max_distance_x < abs(position['x'] - item['position']['x']):
                    target_position = position
                    max_distance_x = abs(position['x'] - item['position']['x'])

            if target_position is None:
                for position in candidate_positions:
                    if position['x'] < item['position']['x'] and max_distance_x < abs(position['x'] - item['position']['x']):
                        target_position = position
                        max_distance_x = abs(position['x'] - item['position']['x'])
                target_rotation = dict(x=0, y=90, z=0)        

        elif item_rotation == 45: # agent x比item大，z比item大
            target_rotation = dict(x=0, y=225, z=0)
            front_positions = []
            back_positions = []
            for position in reachable_positions:
                # 将agent的x坐标大于item的x坐标的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if position['x'] > item['position']['x'] and position['z'] > item['position']['z']:
                    front_positions.append(position)
                elif position['x'] < item['position']['x'] and position['z'] < item['position']['z']:
                    back_positions.append(position)
            
            # 如果正面位置存在，选择夹角最小的位置
            if len(front_positions) > 0:
                # 2. 根据item的位置，过滤合适的可达位置
                # 2.1 直线方程 AX+BZ+C=0
                A = 1
                B = -math.tan(math.radians(item['rotation']['y']))
                C = -item_position['x'] - B * item_position['z']
                
                # 2.2 计算最接近直线的候选点（0.1）
                min_dinstance = float('inf')
                closest_points = []
                for position in front_positions:
                    x0 = position['x']
                    z0 = position['z']
                    numerator = abs(A * z0 + B * x0 + C)
                    denominator = math.sqrt(A**2 + B**2)
                    distance =  numerator / denominator
                    if distance <= min_dinstance + 0.1:
                        if distance < min_dinstance:
                            min_dinstance = distance
                        closest_points.append(position)

                # 从最接近直线的候选点中选择距离最远的点
                max_distance = 0
                for position in closest_points:
                    distance = math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2)
                    if distance > max_distance:
                        max_distance = distance
                        target_position = position

            # 如果正面位置不存在，选择夹角最小的背面位置
            if target_position is None and len(back_positions) > 0:
                target_rotation = dict(x=0, y=45, z=0)
                max_distance = 0
                for position in back_positions:
                    distance = math.sqrt((position['x'] - item['position']['x'])**2 + (position['z'] - item['position']['z'])**2)
                    if distance > max_distance:
                        max_distance = distance
                        target_position = position

        elif item_rotation == 135: # agent x比item小，z比item大
            target_rotation = dict(x=0, y=315, z=0)
            front_positions = []
            back_positions = []
            for position in reachable_positions:
                # 将agent的x坐标小于item的x坐标的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if position['x'] < item['position']['x'] and position['z'] > item['position']['z']:
                    front_positions.append(position)
                elif position['x'] > item['position']['x'] and position['z'] < item['position']['z']:
                    back_positions.append(position)


        elif item_rotation >0 and item_rotation < 90: # agent x比item大，z比item大
            for position in reachable_positions:
                # 将agent的x坐标大于item的x坐标的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if position['x'] > item['position']['x'] and position['z'] > item['position']['z']:
                    candidate_positions.append(position)
            
            # 角度最接近item_rotation的位置
            min_rotation_gap = float('inf')
            for position in candidate_positions:
                dz = position['z'] - item_position['z']
                dx = position['x'] - item_position['x']
                angle_radians = math.atan2(dz, dx)
                angle_degrees = math.degrees(angle_radians)+180
                if abs(angle_degrees - item_rotation) < min_rotation_gap:
                    min_rotation_gap = abs(angle_degrees - item_rotation)
                    target_position = position

            target_rotation = dict(x=0, y=angle_degrees, z=0)#...............

        elif item_rotation >90 and item_rotation < 180: # agent x比item大，z比item小

            for position in reachable_positions:
                # 将agent的x坐标大于item的x坐标的位置, 以及agent的z坐标小于item的z坐标的位置加入候选位置
                if position['x'] > item['position']['x'] and position['z'] < item['position']['z']:
                    candidate_positions.append(position)
            
            # 角度最接近item_rotation的位置
            for position in candidate_positions:
                dz = position['z'] - item_position['z']
                dx = position['x'] - item_position['x']
                angle_radians = math.atan2(dz, dx)
                angle_degrees = math.degrees(angle_radians)+360
                if abs(angle_degrees - item_rotation) < min_rotation_gap:
                    min_rotation_gap = abs(angle_degrees - item_rotation)
                    target_position = position

            target_rotation = dict(x=0, y=angle_degrees, z=0)#...............

        elif item_rotation >180 and item_rotation < 270: # agent x比item小，z比item小

            for position in reachable_positions:
                # 将agent的x坐标小于item的x坐标的位置, 以及agent的z坐标小于item的z坐标的位置加入候选位置
                if position['x'] < item['position']['x'] and position['z'] < item['position']['z']:
                    candidate_positions.append(position)

            # 角度最接近item_rotation的位置
            for position in candidate_positions:
                dz = position['z'] - item_position['z']
                dx = position['x'] - item_position['x']
                angle_radians = math.atan2(dz, dx)
                angle_degrees = math.degrees(angle_radians)
                if abs(angle_degrees - item_rotation) < min_rotation_gap:
                    min_rotation_gap = abs(angle_degrees - item_rotation)
                    target_position = position
            
            target_rotation = dict(x=angle_degrees, y=180, z=0)#...............
        
        elif item_rotation >270 and item_rotation < 360: # agent x比item小，z比item大
            
            for position in reachable_positions:
                # 将agent的x坐标小于item的x坐标的位置, 以及agent的z坐标大于item的z坐标的位置加入候选位置
                if position['x'] < item['position']['x'] and position['z'] > item['position']['z']:
                    candidate_positions.append(position)

            # 角度最接近item_rotation的位置
            for position in candidate_positions:
                dz = position['z'] - item_position['z']
                dx = position['x'] - item_position['x']
                angle_radians = math.atan2(dz, dx)
                angle_degrees = math.degrees(angle_radians)+180
                if abs(angle_degrees - item_rotation) < min_rotation_gap:
                    min_rotation_gap = abs(angle_degrees - item_rotation)
                    target_position = position

            target_rotation = dict(x=0, y=angle_degrees, z=0)#...............
        # target_position = reachable_positions[0] if target_position is None else target_position
        # target_rotation = dict(x=0, y=target_position['rotation'], z=0)
        if target_position is None:
            ###############################################################################################
            # 1. 根据item的方向，过滤合适的可达位置
            # if round(item["rotation"]['y']) in [0, 180]:
            #     agent px应该大于item px
                # reachable_positions = [position for position in reachable_positions if position['x'] >= item_position['x']]
            # elif round(item["rotation"]['y']) in [180, 360]:
            #     agent px应该小于item px
            #     reachable_positions = [position for position in reachable_positions if position['x'] <= item_position['x']]

            # 2. 根据item的位置，过滤合适的可达位置
            # 2.1 直线方程 AX+BZ+C=0
            A = 1
            B = -math.tan(math.radians(item['rotation']['y']))
            C = -item_position['x'] - B * item_position['z']
            
            # # 2.2 计算最近的点
            min_dinstance = float('inf')
            closest_point = None
            for position in reachable_positions:
                x0 = position['x']
                z0 = position['z']
                numerator = abs(A * z0 + B * x0 + C)
                denominator = math.sqrt(A**2 + B**2)
                distance =  numerator / denominator
                if distance <= min_dinstance:
                    min_dinstance = distance
                    closest_point = position

            # 3. 计算agent合适的方向
            dz = closest_point['z'] - item_position['z']
            dx = closest_point['x'] - item_position['x']
            angle_radians = math.atan2(dz, dx)
            angle_degrees = math.degrees(angle_radians)
            angle_degrees = angle_degrees + 360 if angle_degrees < 0 else angle_degrees

            rotation = dict(x=0, y=closest_point['rotation'], z=0) if 'rotation' in closest_point.keys() else dict(x=0, y=angle_degrees, z=0)
            # ##################################################################################

            return closest_point, rotation
        
        
        return target_position, target_rotation



        
        
        # item_position = item["position"]
        # agent_position = self.get_agent_position()

        
        # for position in reachable_positions:
        #     distance = abs(position['z'] - item_position['z'])
        #     if distance < min_distance_z:
        #         min_distance_z = distance
        # positions = []
        # for position in reachable_positions:
        #     if abs(position['z'] - item_position['z']) == min_distance_z:
        #         positions.append(position)
        # target_position = None
        # min_distance = float('inf')
        # for position in positions:
        #     distance = math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2)
        #     if abs(distance-0.5) < min_distance:
        #         min_distance = distance
        #         target_position = position

        # return target_position
    
        # Find the closest reachable position to the item and close to the agent
        # closest_position = None
        # closest_position_2 = None
        # min_distance_item_target = float('inf')
        # min_distance_item_target_2 = float('inf')
        # for position in reachable_positions:
        #     distance = math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2)
        #     # if (position['x']>=item_position['x'] and position['z']>=item_position['z']) or (position['x']<item_position['x'] and position['z']<item_position['z']):
        #     if distance < min_distance_item_target:
        #         min_distance_item_target = distance
        #         closest_position = position
            # else:
            #     if distance < min_distance_item_target_2:
            #         min_distance_item_target_2 = distance
            #         closest_position_2 = position

        # min_distance_agent_target = float('inf')
        
        # for position in reachable_positions:
        #     distance_item_target = math.sqrt((position['x'] - item_position['x'])**2 + (position['z'] - item_position['z'])**2)
        #     distance_agent_target = math.sqrt((position['x'] - agent_position['x'])**2 + (position['z'] - agent_position['z'])**2)
        #     if distance_item_target == min_distance_item_target and distance_agent_target < min_distance_agent_target:
        #         min_distance_agent_target = distance_agent_target
        #         closest_position = position
        
        # return closest_position if closest_position is not None else closest_position_2

    def calculate_best_view_angles(self, item):
        # 提取坐标
        import numpy as np
        # 计算 LookAt 向量
        camera_position = self.get_camera_position()
        # look_vector = np.array([
        #     item["position"]["x"] - camera_position["x"],
        #     item["position"]["y"] - camera_position["y"],
        #     item["position"]["z"] - camera_position["z"]
        # ])
        look_vector = np.array([
            item["axisAlignedBoundingBox"]["center"]["x"] - camera_position["x"],
            item["axisAlignedBoundingBox"]["center"]["y"] - camera_position["y"],
            item["axisAlignedBoundingBox"]["center"]["z"] - camera_position["z"]
        ])

        # 归一化 LookAt 向量
        norm = np.linalg.norm(look_vector)
        look_vector = look_vector / norm if norm != 0 else look_vector

        # 计算欧拉角
        yaw = np.arctan2(look_vector[0], look_vector[2])  # 水平角
        pitch = np.arcsin(look_vector[1])  # 俯仰角

        return np.degrees(yaw), np.degrees(pitch)


    # 调整agent的上下和左右视角使其看向物体
    def adjust_view(self, item):
        if item["objectId"] not in self.objid2position:

            yaw_degrees, pitch_degrees = self.calculate_best_view_angles(item)
            
            camera_yaw = -self.get_camera_rotation() # -60下视角（-60，30）

            if int(pitch_degrees) > 0:
                target_yaw = min(30, int(pitch_degrees)) # look up
            else:
                target_yaw = max(-60, int(pitch_degrees)) # look down

            # -51 -60
            if target_yaw - camera_yaw > 0: # look up 80
                self.action.action_mapping["look_up"](self.controller, target_yaw - camera_yaw)
            # 0, 30
            elif target_yaw - camera_yaw <0:
                self.action.action_mapping["look_down"](self.controller, camera_yaw - target_yaw)

            self.update_event()

            if int(yaw_degrees) < 0:
                yaw_degrees = 360 + yaw_degrees
            
            angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]
            # 四舍五入(item["rotation"]['y'])
            yaw_rotation = min(angles, key=lambda angle: abs(angle - round(yaw_degrees)))
            yaw_rotation = 0 if yaw_rotation == 360 else yaw_rotation
            # if item['name'] not in self.eventobject.get_visible_objects()[0]:
            self.action.action_mapping["rotate_left"](self.controller, self.get_agent_rotation()['y']-yaw_rotation)
            self.update_event()

    # 调整agent的高度使其与物体对齐
    def adjust_height(self, item):
        if item["objectId"] in self.objid2position:
            agent_isstanding = self.objid2position[item["objectId"]]["agent_isstanding"]
            if agent_isstanding:
                if (self.controller.last_event.metadata["agent"]["isStanding"]==False):
                    self.action.action_mapping["stand"](self.controller)
            else:
                if (self.controller.last_event.metadata["agent"]["isStanding"]==True):
                    self.action.action_mapping["crouch"](self.controller)
        else:
            # 如果agent比物体高0.22米，则让agent蹲下
            if self.get_agent_position()['y'] > item['axisAlignedBoundingBox']['cornerPoints'][0][1] + 0.44:
                self.action.action_mapping["crouch"](self.controller)
            # 如果agent比物体低，则让agent站起来
            else:
                self.action.action_mapping["stand"](self.controller)
            
            self.update_event()
            if item['name'] not in self.eventobject.get_visible_objects(self.controller.last_event)[0]:
                self.action.action_mapping["stand"](self.controller)
                self.update_event()

    # 获取初始化边界agent视角帧
    def get_edge_init_view(self):
        # 计算合适的位置
        # 1. 房间最长边界的中心位置
        scene_bounds2 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][2]
        scene_bounds3 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][3]
        scene_bounds6 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][6]
        scene_bounds7 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][7]
        edge23 = math.sqrt((scene_bounds2[0]-scene_bounds3[0])**2 + (scene_bounds2[2]-scene_bounds3[2])**2)
        edge26 = math.sqrt((scene_bounds2[0]-scene_bounds6[0])**2 + (scene_bounds2[2]-scene_bounds6[2])**2)
        edge37 = math.sqrt((scene_bounds3[0]-scene_bounds7[0])**2 + (scene_bounds3[2]-scene_bounds7[2])**2)
        edge67 = math.sqrt((scene_bounds6[0]-scene_bounds7[0])**2 + (scene_bounds6[2]-scene_bounds7[2])**2)
        
        # 2. 计算最大边的中心位置
        min_edge = max(edge23, edge26, edge37, edge67)
        if min_edge == edge23:
            center = [(scene_bounds2[0]+scene_bounds3[0])/2, (scene_bounds2[1]+scene_bounds3[1])/2, (scene_bounds2[2]+scene_bounds3[2])/2]
            # 180-360
            target_rotation = dict(x=0, y=225, z=0)
            # target_position = dict(x=0, y=315, z=0)
        elif min_edge == edge26:
            center = [(scene_bounds2[0]+scene_bounds6[0])/2, (scene_bounds2[1]+scene_bounds6[1])/2, (scene_bounds2[2]+scene_bounds6[2])/2]
            # 90-270
            target_position = dict(x=0, y=135, z=0)
            # target_rotation = dict(x=0, y=225, z=0)
        elif min_edge == edge37:
            center = [(scene_bounds3[0]+scene_bounds7[0])/2, (scene_bounds3[1]+scene_bounds7[1])/2, (scene_bounds3[2]+scene_bounds7[2])/2]
            # 0-90；270-360
            target_rotation = dict(x=0, y=45, z=0)
            # target_position = dict(x=0, y=315, z=0)
        else:
            # 0-90-180
            target_rotation = dict(x=0, y=45, z=0)
            # target_position = dict(x=0, y=135, z=0)
            center = [(scene_bounds6[0]+scene_bounds7[0])/2, (scene_bounds6[1]+scene_bounds7[1])/2, (scene_bounds6[2]+scene_bounds7[2])/2]
        
        # 3. 获取agent可达位置
        event = self.controller.step(dict(action='GetReachablePositions'))
        reachable_positions = event.metadata['actionReturn']
        # 4. 计算与center最近的可达位置
        min_distance = float("inf")
        for position in reachable_positions:
            distance = math.sqrt((position['x']-center[0])**2 + (position['z']-center[2])**2)
            if distance < min_distance:
                min_distance = distance
                target_position = position

        # 5. 设置agent的旋转角度
        
        # 6. agent导航到可达位置
        self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation, horizon=0)
        
        self.save_frame({"action": "init_view1"}, prefix_save_path="./data/init_scene_image")
        self.action.action_mapping["rotate_right"](self.controller, 90)
        self.save_frame({"action": "init_view2"}, prefix_save_path="./data/init_scene_image")
        pass
    