import math
try:
    from utils import *
except Exception as e:
    print(e)
try:
    from .utils import add_text_to_image, add_border, EventObject
except Exception as e:
    print(e)

from .baseAgent import BaseAgent
from tqdm import tqdm
import numpy as np
import cv2, json

class RocAgent(BaseAgent):
    STATE_OBSERVATION = "observation"
    STATE_PLANNING = "planning"
    STATE_THINKING = "thinking"
    STATE_REFLECTION = "reflection"
    STATE_DECISION_MAKING_STATE = "decision_making"
    STATE_VERIFICATION = "verification"
    STATE_END = "end"
    def __init__(self, controller, save_path="./data/", scene="FloorPlan203", 
                 visibilityDistance=1.5, gridSize=0.25, fieldOfView=90, target_objects=[], related_objects=[], navigable_objects=[], taskid=0,platform_type="GPU"):
        super().__init__(controller, scene, visibilityDistance, gridSize, fieldOfView,platform_type)
        self.env, self.executor, self.monitor, self.planner = self.build_agent()
        self.pre_navigate_location=""
        self.agent_state = []
        self.object_state = {}
        self.target_objects = []
        self.navigale_objects = {}
        self.state = ""
        self.result_dir = f"{save_path}"
        self.navigable_objects = {}
        self.legal_interactions = {}
        self.current_container = None
        self.objecttype2object={} # 可导航物体的type2obj
        self.action_space = {
            "init": self.init_agent_corner,
            "navigate to": self.navigate,
            "pickup": self.pick_up,
            "put": self.put_in,
            "put in":self.put_in,   # for MODE=API
            "toggle": self.toggle,
            "open": self.open,
            "close": self.close,
            "observe": self.observe,
            "move forward": self.move_forward,
            "end": "end",
        }
        self.related_objects=related_objects
        self.target_item_type2obj_id = {}
        for target_obj in target_objects:
            if target_obj.split("|")[0] not in self.target_item_type2obj_id:
                self.target_item_type2obj_id[target_obj.split("|")[0]] = []
            self.target_item_type2obj_id[target_obj.split("|")[0]].append(target_obj)
        
        for obj in self.controller.last_event.metadata['objects']:
            if obj['objectType'] not in self.objecttype2object:
                self.objecttype2object[obj['objectType']]=[]
            self.objecttype2object[obj['objectType']].append(obj)
        
        for navigable_obj in navigable_objects:
            if navigable_obj not in self.navigable_objects:
                self.navigable_objects[navigable_obj] = 0
            self.navigable_objects[navigable_obj] += 1
        self.taskid = str(taskid)
        self.objid2position={}
        with open("./data/agent_positions.json") as f:
            custom_position_data = json.load(f)
        for taskid in custom_position_data:
            temp_data = custom_position_data[taskid]
            for objid in temp_data:
                if objid != "scene" and objid != "tasktype" and objid != "taskname":
                    self.objid2position[objid] = temp_data[objid]

        # if self.taskid in custom_position_data:
        #     self.objid2position = custom_position_data[self.taskid]
        # self.init_agent_corner()
        
    def build_agent(self):
        return None, None, None, None
    
    def predict_next_action(self, task):
        if self.state==RocAgent.STATE_OBSERVATION:
            # 初始状态，根据观察和任务，状态转换为规划状态/思考状态
            pass
        if self.state==RocAgent.STATE_PLANNING:
            # 规划后，状态转换为决策状态
            pass
        if self.state==RocAgent.STATE_THINKING:
            # 1.思考后，重新规划，状态转换为规划状态
            # 2.思考后，不需要规划，状态转换为决策状态
            # 3.思考任务已经执行完成，转为验证状态
            pass
        if self.state==RocAgent.STATE_REFLECTION:
            # 1.反思后可直接决策，状态转换为决策状态
            # 2.反思后继续规划，状态转换为规划状态
            pass
        if self.state==RocAgent.STATE_DECISION_MAKING_STATE:
            # 1.如果决策失败，状态转换为反思状态
            # 2.如果决策成功，状态转换为思考状态
            pass
        if self.state==RocAgent.STATE_VERIFICATION:
            # 1.验证成功后，状态转换为结束状态
            # 2.验证失败，状态转换为反思状态
            pass
        if self.state==RocAgent.STATE_END:
            # 结束状态
            pass
    
    # 向目标物体走几个身位
    def move_observation(self, target_item):
        # 1. 调整agent的方向，使其前方存在目标物体
        self.adjust_view(target_item)
        # 2. 计算物体和agent的距离，调整agent的位置
        distance = target_item["distance"]
        # 2. 往目标物体移动几个身位
        # 移动1/3的距离
        self.action.action_mapping["moveAhead"](self.controller, round(distance/3, 1))
        self.update_event()
        # 3. 调整agent的视野范围
        self.adjust_agent_fieldOfView(120)
        self.update_event()
        self.update_legal_location()


    def init_agent_corner(self):
        scene_bounds2 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][2]
        scene_bounds3 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][3]
        scene_bounds6 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][6]
        scene_bounds7 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][7]

        # 3. 获取agent可达位置
        event = self.controller.step(dict(action='GetReachablePositions'))
        reachable_positions = event.metadata['actionReturn']
        pre_target_positions = []
        # 4. 计算与四个点最近的可达位置
        min_distance = float("inf")
        for i, scene_bounds in enumerate([scene_bounds2, scene_bounds3, scene_bounds6, scene_bounds7]):
            for position in reachable_positions:
                distance = math.sqrt((position['x']-scene_bounds[0])**2 + (position['z']-scene_bounds[2])**2)
                if distance < min_distance:
                    min_distance = distance
                    target_position = position
                    index = i
        # 5. 设置agent的旋转角度
        if index == 0:
            # 180, 270
            target_rotation = dict(x=0, y=225, z=0)
        elif index == 1:
            # 270, 360
            target_rotation = dict(x=0, y=315, z=0)
        elif index == 2:
            # 90,180
            target_rotation = dict(x=0, y=135, z=0)
        else:
            # 0,90
            target_rotation = dict(x=0, y=45, z=0)
        
        # 6. agent导航到可达位置
        while True:
            event = self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation, horizon=0)
            self.update_event()
            if event.metadata['lastActionSuccess']:
                break
            else:
                pre_target_positions.append(target_position)
                event = self.controller.step(dict(action='GetReachablePositions'))
                reachable_positions = event.metadata['actionReturn']
                
                # 4. 计算与四个点最近的可达位置
                min_distance = float("inf")
                for i, scene_bounds in enumerate([scene_bounds2, scene_bounds3, scene_bounds6, scene_bounds7]):
                    for position in reachable_positions:
                        if position in pre_target_positions:
                            continue
                        distance = math.sqrt((position['x']-scene_bounds[0])**2 + (position['z']-scene_bounds[2])**2)
                        if distance < min_distance:
                            min_distance = distance
                            target_position = position
                            index = i
                # 5. 设置agent的旋转角度
                if index == 0:
                    # 180, 270
                    target_rotation = dict(x=0, y=225, z=0)
                elif index == 1:
                    # 270, 360
                    target_rotation = dict(x=0, y=315, z=0)
                elif index == 2:
                    # 90,180
                    target_rotation = dict(x=0, y=135, z=0)
                else:
                    # 0,90
                    target_rotation = dict(x=0, y=45, z=0)
                print("Teleport failed, retrying...")
        self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation, horizon=0)
        self.update_event()
        # self.save_frame({"action": "init_agent_view"}, prefix_save_path="./data/init_scene_image")
        # self.action.action_mapping["rotate_right"](self.controller, 30)
        # self.update_legal_location()
        # self.save_frame({"action": "init_view2"}, prefix_save_path="./data/init_scene_image")
        image_fp, legal_navigations, legal_interactions = None, None, None
        image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "init",},
                                    prefix_save_path=self.result_dir)
        legal_navigations = self.get_legal_navigations()
        legal_interactions = self.get_legal_interactions()
        return image_fp, legal_navigations, legal_interactions

    def navigate(self, itemtype):
        image_fp, legal_navigations, legal_interactions = None, None, None
    
        # 如果item是歧义物体
        if itemtype in self.target_item_type2obj_id:
            if self.taskid=="84" or self.taskid=="85":
                if self.controller.last_event.metadata["inventoryObjects"] == []:
                    obj_id = self.target_item_type2obj_id[itemtype][0]
                else:
                    obj_id = self.target_item_type2obj_id[itemtype][1]
            else:
                obj_id = self.target_item_type2obj_id[itemtype][0]
            item = self.eventobject.get_object_by_id(self.controller.last_event, obj_id)
        else:
            item = self.objecttype2object[itemtype][0]
        
        # 存储itemtype-非直接导航到的物品
        navigate_obj_type=item["objectType"]
        
        # 如果item是容器，如果容器上存在相关物体，并且容器是非封闭的状态，直接导航到该物体 "openable": 0, "isOpen": 0, 
        if item.get("receptacle", False) and (not item["openable"]):
            for related_object in self.related_objects:
                if related_object in item['receptacleObjectIds']:
                    item = self.eventobject.get_object_by_id(self.controller.last_event, related_object)
                    break
        
        # while(item['name'] == self.pre_navigate_location and len(self.objecttype2object[item['objectType']])>1):
        #     item = random.choice(self.objecttype2object[item['objectType']])
        # self.pre_navigate_location = item['name']
        # 如果容器没打开，然后里面存在目标物体，就不能直接导航到目标物体
        if item["objectId"] in self.objid2position:
            target_position = self.objid2position[item["objectId"]]["agent_teleport_position"]
            target_rotation = self.objid2position[item["objectId"]]["agent_rotation"]
            horizon = self.objid2position[item["objectId"]]["agent_cameraHorizon"]
            print("设定位置", self.objid2position)
        else:
            target_position, target_rotation = self.compute_position_8(item, pre_target_positions=[])
            horizon = 60
        # self.arm_reset()
        if target_position is None:
            print("teleport failed, no reachable positions")
            return image_fp, legal_navigations, legal_interactions
        event = self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation, horizon=horizon)
        # 判断是否成功
        pre_target_positions = []
        index = 0
        while not event.metadata['lastActionSuccess']:
            index += 1
            print(f"teleport failed, retrying...{index}")
            pre_target_positions.append(target_position)
            target_position, target_rotation = self.compute_position_8(item, pre_target_positions)
            event = self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation)
            self.update_event()
        
        if item["objectId"] not in self.objid2position:
            self.adjust_height(item)
            self.adjust_view(item)

        image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "navigate",
                                    "item": navigate_obj_type},
                                    prefix_save_path=self.result_dir)
        
        
        if item.get("receptacle", False) and "receptacleObjectIds" in item and (item['receptacleObjectIds'] != [] or item['receptacleObjectIds'] is not None):
            self.current_container = item
        
        legal_navigations = self.get_legal_navigations()
        legal_interactions = self.get_legal_interactions()
        
        # self.update_legal_location()
        return image_fp, legal_navigations, legal_interactions
    
    def observe(self):
        image_fp, legal_navigations, legal_interactions = [], None, None
        for i in range(3):
            self.action.action_mapping["rotate_left"](self.controller, 90)
            
            image_fp.append(self.save_frame({"step_count": str(self.step_count),
                                        "i": str(i),
                                        "action": "observe"},
                                        prefix_save_path=self.result_dir))
            legal_navigations = self.get_legal_navigations()

        for i in range(3):
            images = [cv2.imread(path) for path in image_fp]
            img1 = add_text_to_image(images[0], "left view", (10, images[0].shape[0] - 20))
            img2 = add_text_to_image(images[1], "back view", (10, images[1].shape[0] - 20))
            img3 = add_text_to_image(images[2], "right view", (10, images[2].shape[0] - 25))
            # 为图片添加边框（注意：只给中间的图片添加左右边框）
            img2_with_border = add_border(img2, 5, (0, 0, 0))
            # 水平拼接
            img_h_concat = np.concatenate((img1, img2_with_border, img3), axis=1)
            # 保存结果
            output_path = self.save_frame({"step_count": str(self.step_count),
                                            # "i": str(i),
                                            "action": "observe"},
                                            prefix_save_path=self.result_dir)
            try:
                cv2.imwrite(output_path, img_h_concat)
                break
            except Exception as e:
                print("try_save_image")
                print(e)
        
        self.action.action_mapping["rotate_left"](self.controller, 90)
        legal_interactions = self.get_legal_interactions()
        
        return output_path, legal_navigations, legal_interactions
        
    def move_forward(self, distance=0.5):
        
        image_fp, legal_navigations, legal_interactions = None, None, None
        # 寻找周围8个方向 哪个方向可探索的位置最多
        # reachablePositions=self.controller.step(action="GetReachablePositions")
        
        # 转回0
        # current_rotate=self.controller.last_event.metadata["agent"]["rotation"]["y"]
        # if current_rotate<0:
        #     self.action.action_mapping["rotate_right"](self.controller,degrees=abs(current_rotate))
        # if current_rotate>0:
        #     self.action.action_mapping["rotate_left"](self.controller,degrees=current_rotate)
        
        self.action.action_mapping["move_ahead"](self.controller, distance)
        print("RocAgent",self.controller.last_event)
        if self.controller.last_event.metadata["errorMessage"]=="":
            image_fp = self.save_frame({"step_count": str(self.step_count),
                                        "action": "move_forward"},
                                        prefix_save_path=self.result_dir)
            legal_navigations = self.get_legal_navigations()
            legal_interactions = self.get_legal_interactions()
            return image_fp, legal_navigations, legal_interactions
        else:
            # 左平移或者右平移 随机？
            # 根据那个位置离目标物体更近
            # import pdb;pdb.set_trace()
            if self.related_objects:
                distance_right_list = []
                distance_left_list = []
                
                # move_r_or_l=random.choice(["move_right","move_left"])
                self.action.action_mapping["move_right"](self.controller, distance)
                print("RocAgent",self.controller.last_event)
                errorMessage1=self.controller.last_event.metadata["errorMessage"]
                agentxright=self.controller.last_event.metadata["agent"]["position"]["x"]
                agentzright=self.controller.last_event.metadata["agent"]["position"]["z"]  

                if errorMessage1=="":
                    self.action.action_mapping["move_left"](self.controller, distance)#回到原位
                    
                self.action.action_mapping["move_left"](self.controller, distance)#左移动
                print("RocAgent",self.controller.last_event)
                errorMessage2=self.controller.last_event.metadata["errorMessage"]
                agentxleft=self.controller.last_event.metadata["agent"]["position"]["x"]
                agentzleft=self.controller.last_event.metadata["agent"]["position"]["z"] 
                
                if errorMessage2=="":
                    self.action.action_mapping["move_right"](self.controller, distance)#回到原位
                
                for obj_id in self.related_objects:
                    item = self.eventobject.get_object_by_id(self.controller.last_event,obj_id)
                    if item["visible"]==True:
                        itemx=item["position"]["x"]
                        itemz=item["position"]["z"]
                        
                        # 计算右侧移动后的距离
                        distance_right = math.sqrt((agentxright - itemx) ** 2 + (agentzright - itemz) ** 2)
                        distance_right_list.append(distance_right)
                        # 计算左侧移动后的距离
                        distance_left = math.sqrt((agentxleft - itemx) ** 2 + (agentzleft - itemz) ** 2)
                        distance_left_list.append(distance_left)
                   
                if errorMessage1=="" and errorMessage2=="" and distance_right_list and distance_left_list:# 左右都能移动，选择移动后距离目标物体最近的方向
                    # 1. 选择平均距离所有目标物体最小的方向
                    # avg_distance_right = sum(distance_right_list) / len(distance_right_list)
                    # avg_distance_left = sum(distance_left_list) / len(distance_left_list)
                    # if avg_distance_right < avg_distance_left:
                    #     direction = "move_right"
                    # else:
                    #     direction = "move_left"
                    
                    # 2. 选择使最近物体距离最小的方向
                    
                    min_distance_right = min(distance_right_list)
                    min_distance_left = min(distance_left_list)
                    
                    if min_distance_right < min_distance_left:
                        direction = "move_right"
                    else:
                        direction = "move_left"
                    
                    #向direction侧移动后 距离n个目标物体中 其中1个最近 
                    self.action.action_mapping[direction](self.controller, distance)
                    if self.controller.last_event.metadata["errorMessage"]=="":
                        image_fp = self.save_frame({"step_count": str(self.step_count),
                                                "action": "move_forward"},
                                                prefix_save_path=self.result_dir)
                        legal_navigations = self.get_legal_navigations()
                        legal_interactions = self.get_legal_interactions()
                        return image_fp, legal_navigations, legal_interactions  
                    
                elif errorMessage1=="" or errorMessage2=="":  # 左右有一个方向能够移动，选择能够移动的方向
                    if errorMessage1=="":
                        self.action.action_mapping["move_right"](self.controller, distance)
                        
                    elif errorMessage2=="":
                        self.action.action_mapping["move_left"](self.controller, distance)
                    
                    print("RocAgent",self.controller.last_event)                  
                    if self.controller.last_event.metadata["errorMessage"]=="":
                        image_fp = self.save_frame({"step_count": str(self.step_count),
                                                "action": "move_forward"},
                                                prefix_save_path=self.result_dir)
                        legal_navigations = self.get_legal_navigations()
                        legal_interactions = self.get_legal_interactions()
                        return image_fp, legal_navigations, legal_interactions
                
                else:
                    self.action.action_mapping["move_back"](self.controller, distance)  # 向后移动
                    print("RocAgent",self.controller.last_event)
                    if self.controller.last_event.metadata["errorMessage"]=="":
                        image_fp = self.save_frame({"step_count": str(self.step_count),
                                        "action": "move_forward"},
                                        prefix_save_path=self.result_dir)
                        legal_navigations = self.get_legal_navigations()
                        legal_interactions = self.get_legal_interactions()
                        return image_fp, legal_navigations, legal_interactions
                    
                    else:
                        self.action.action_mapping["rotate_right"](self.controller,degrees=90)
                        errorMessage_rotate_right=self.controller.last_event.metadata["errorMessage"]
                        self.action.action_mapping["move_ahead"](self.controller, distance)
                        print("RocAgent",self.controller.last_event)
                        if self.controller.last_event.metadata["errorMessage"]=="":
                            image_fp = self.save_frame({"step_count": str(self.step_count),
                                        "action": "move_forward"},
                                        prefix_save_path=self.result_dir)
                            legal_navigations = self.get_legal_navigations()
                            legal_interactions = self.get_legal_interactions()
                            return image_fp, legal_navigations, legal_interactions
                        else:
                            if errorMessage_rotate_right=="":#向左转
                                self.action.action_mapping["rotate_left"](self.controller,degrees=180)
                            self.action.action_mapping["move_ahead"](self.controller, distance)
                            print("RocAgent",self.controller.last_event)
                            if self.controller.last_event.metadata["errorMessage"]=="":
                                image_fp = self.save_frame({"step_count": str(self.step_count),
                                        "action": "move_forward"},
                                        prefix_save_path=self.result_dir)
                                legal_navigations = self.get_legal_navigations()
                                legal_interactions = self.get_legal_interactions()
                                return image_fp, legal_navigations, legal_interactions
                    
            else:
                self.action.action_mapping["move_right"](self.controller, distance)
                                    
                if self.controller.last_event.metadata["errorMessage"]=="":
                    image_fp = self.save_frame({"step_count": str(self.step_count),
                                            "action": "move_forward"},
                                            prefix_save_path=self.result_dir)
                    legal_navigations = self.get_legal_navigations()
                    legal_interactions = self.get_legal_interactions()
                    return image_fp, legal_navigations, legal_interactions

                else:
                    self.action.action_mapping["move_left"](self.controller, distance)
                                        
                    if self.controller.last_event.metadata["errorMessage"]=="":
                        image_fp = self.save_frame({"step_count": str(self.step_count),
                                                "action": "move_forward"},
                                                prefix_save_path=self.result_dir)
                        legal_navigations = self.get_legal_navigations()
                        legal_interactions = self.get_legal_interactions()
                        return image_fp, legal_navigations, legal_interactions
                    else:
                        # # 左平移
                        # self.action.action_mapping["move_left"](self.controller, distance)
                        # print("RocAgent",self.controller.last_event)
                        # if self.controller.last_event.metadata["errorMessage"]=="":
                        #     image_fp = self.save_frame({"step_count": str(self.step_count),
                        #                             "action": "move_forward"},
                        #                             prefix_save_path=self.result_dir)
                        #     legal_navigations = self.get_legal_navigations()
                        #     legal_interactions = self.get_legal_interactions()
                        #     return image_fp, legal_navigations, legal_interactions
                        self.action.action_mapping["move_back"](self.controller, distance)  # 向后移动
                        print("RocAgent",self.controller.last_event)
                        if self.controller.last_event.metadata["errorMessage"]=="":
                            image_fp = self.save_frame({"step_count": str(self.step_count),
                                            "action": "move_forward"},
                                            prefix_save_path=self.result_dir)
                            legal_navigations = self.get_legal_navigations()
                            legal_interactions = self.get_legal_interactions()
                            return image_fp, legal_navigations, legal_interactions
                        
                        else:
                            self.action.action_mapping["rotate_right"](self.controller,degrees=90)
                            errorMessage_rotate_right=self.controller.last_event.metadata["errorMessage"]
                            self.action.action_mapping["move_ahead"](self.controller, distance)
                            print("RocAgent",self.controller.last_event)
                            if self.controller.last_event.metadata["errorMessage"]=="":
                                image_fp = self.save_frame({"step_count": str(self.step_count),
                                            "action": "move_forward"},
                                            prefix_save_path=self.result_dir)
                                legal_navigations = self.get_legal_navigations()
                                legal_interactions = self.get_legal_interactions()
                                return image_fp, legal_navigations, legal_interactions
                            else:
                                if errorMessage_rotate_right=="":#向左转
                                    self.action.action_mapping["rotate_left"](self.controller,degrees=180)
                                self.action.action_mapping["move_ahead"](self.controller, distance)
                                print("RocAgent",self.controller.last_event)
                                if self.controller.last_event.metadata["errorMessage"]=="":
                                    image_fp = self.save_frame({"step_count": str(self.step_count),
                                            "action": "move_forward"},
                                            prefix_save_path=self.result_dir)
                                    legal_navigations = self.get_legal_navigations()
                                    legal_interactions = self.get_legal_interactions()
                                    return image_fp, legal_navigations, legal_interactions
                    
        print("RocAgent",self.controller.last_event)
        return image_fp, legal_navigations, legal_interactions

    def pick_up(self, itemtype):
        
        if itemtype in self.target_item_type2obj_id:
            obj_id = self.target_item_type2obj_id[itemtype][0]
            item = self.eventobject.get_object_by_id(self.controller.last_event, obj_id)
        else:
            item = self.objecttype2object[itemtype][0]
        
        image_fp, legal_navigations, legal_interactions = None, None, None
        self.action.action_mapping["pick_up"](self.controller, item['objectId'])
        image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "pick_up",
                                    "item": item["objectType"]},
                                    prefix_save_path=self.result_dir)
        legal_navigations = self.get_legal_navigations()
        legal_interactions = self.get_legal_interactions()
        return image_fp, legal_navigations, legal_interactions

    def put_in(self, itemtype):
        if itemtype in self.target_item_type2obj_id:
            obj_id = self.target_item_type2obj_id[itemtype][0]
            item = self.eventobject.get_object_by_id(self.controller.last_event, obj_id)
        else:
            item = self.objecttype2object[itemtype][0]
        
        image_fp, legal_navigations, legal_interactions = None, None, None
        self.action.action_mapping["put_in"](self.controller, item['objectId'])
        image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "put_in",
                                    "item": item["objectType"]},
                                    prefix_save_path=self.result_dir)
        legal_navigations = self.get_legal_navigations()
        legal_interactions = self.get_legal_interactions()
        return image_fp, legal_navigations, legal_interactions

    def toggle(self, itemtype):
        if itemtype in self.target_item_type2obj_id:
            obj_id = self.target_item_type2obj_id[itemtype][0]
            item = self.eventobject.get_object_by_id(self.controller.last_event, obj_id)
        else:
            item = self.objecttype2object[itemtype][0]
        # 本身是打开的状态
        if item["isToggled"]==True:
            image_fp, legal_navigations, legal_interactions = None, None, None
            self.action.action_mapping["toggle_off"](self.controller, item['objectId'])
            image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "toggle",
                                    "item": item["objectType"]},
                                    prefix_save_path=self.result_dir)
            legal_navigations = self.get_legal_navigations()
            legal_interactions = self.get_legal_interactions()
            return image_fp, legal_navigations, legal_interactions
        else:
            image_fp, legal_navigations, legal_interactions = None, None, None
            self.action.action_mapping["toggle_on"](self.controller, item['objectId'])
            image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "toggle",
                                    "item": item["objectType"]},
                                    prefix_save_path=self.result_dir)
            legal_navigations = self.get_legal_navigations()
            legal_interactions = self.get_legal_interactions()
            return image_fp, legal_navigations, legal_interactions

    def open(self, itemtype):
        if itemtype in self.target_item_type2obj_id:
            obj_id = self.target_item_type2obj_id[itemtype][0]
            item = self.eventobject.get_object_by_id(self.controller.last_event, obj_id)
        else:
            item = self.objecttype2object[itemtype][0]
        
        image_fp, legal_navigations, legal_interactions = None, None, None
        self.action.action_mapping["open"](self.controller, item['objectId'])
        image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "open",
                                    "item": item["objectType"]},
                                    prefix_save_path=self.result_dir)
        legal_navigations = self.get_legal_navigations()
        legal_interactions = self.get_legal_interactions()
        return image_fp, legal_navigations, legal_interactions
    
    def close(self, itemtype):
        if itemtype in self.target_item_type2obj_id:
            obj_id = self.target_item_type2obj_id[itemtype][0]
            item = self.eventobject.get_object_by_id(self.controller.last_event, obj_id)
        else:
            item = self.objecttype2object[itemtype][0]
        
        image_fp, legal_navigations, legal_interactions = None, None, None
        self.action.action_mapping["close"](self.controller, item['objectId'])
        image_fp = self.save_frame({"step_count": str(self.step_count),
                                    "action": "close",
                                    "item": item["objectType"]},
                                    prefix_save_path=self.result_dir)
        legal_navigations = self.get_legal_navigations()
        legal_interactions = self.get_legal_interactions()
        return image_fp, legal_navigations, legal_interactions


    def get_all_item_image(self):
        res = []
        for item in tqdm(self.eventobject.get_objects(self.controller.last_event)[0]):
            # print(item["name"],self.eventobject.get_item_surface_area(item['name']))
            if item["name"] == "DiningTable_806ce8fd":#Book_e173324d Box_8e5b2c6b CellPhone_b8be2958
            # # print(item["name"],":",round(item["rotation"]['y']))
                succeess, _ ,_ = self.navigate(item)
                self.save_frame({"item": item["name"]})
                dic = {
                    "scene": self.scene,
                    "item": item["name"],
                    "agent":{
                        "agentMode": "arm",
                        "position": self.get_agent_position(),
                        "rotation": self.get_agent_rotation(),
                    },
                    "camera":{
                        "position": self.get_camera_position(),
                        "rotation": self.get_camera_rotation(),
                    },
                    "fieldOfView":90,
                    "gridSize":0.1,
                    "visibilityDistance": 10,
                    "image_path": f"./data/item_image/{self.scene}_{item['name']}.png"
                }
                res.append(dic)
                self.controller.reset(self.scene)
        with open(f"./data/{self.scene}_objects.jsonl", "w") as f:
            import json
            for item in res:
                f.write(json.dumps(item, ensure_ascii=False)+"\n")

    def get_navigate_path(self):
        res = []
        
        for item in tqdm(self.eventobject.get_objects(self.controller.last_event)[0]):
            # print(item["name"],self.eventobject.get_item_surface_area(item['name']))
            # if item["name"] == "DiningTable_806ce8fd":#Book_e173324d Box_8e5b2c6b CellPhone_b8be2958
            # # print(item["name"],":",round(item["rotation"]['y']))
            # if item["name"] in self.legal_location:
                import copy
                legal_location = copy.deepcopy(self.legal_location)
                succeess, _ ,_ = self.navigate(item)
                visible_objects = []
                obj_names, objs = self.eventobject.get_visible_objects(self.controller.last_event)
                for obj_name, obj in zip(obj_names, objs):
                    volume = self.eventobject.get_item_volume(self.controller.last_event, obj_name)
                    if volume <= 0.1:
                        if obj["distance"] <= 1.5:
                            visible_objects.append(obj["name"])
                    elif volume <= 0.5:
                        if obj["distance"] <= 2.5:
                            visible_objects.append(obj["name"])
                    elif volume <= 1:
                        if obj["distance"] <= 5.0:
                            visible_objects.append(obj["name"])
                    else:
                        if obj["distance"] <= 10.0:
                            visible_objects.append(obj["name"])
                for obj_name in visible_objects:
                    if obj_name not in legal_location.keys():
                        legal_location[obj_name] = 1
                    else:
                        legal_location[obj_name] += 1

                self.save_frame({"item": item["name"]})
                dic = {
                    "scene": self.scene,
                    "init_legal_location": legal_location,
                    "object": {
                        "name":item["name"],
                        "position": item["position"],
                        "rotation": item["rotation"],
                    },
                    "agent":{
                        "agentMode": "default",
                        "position": self.get_agent_position(),
                        "rotation": self.get_agent_rotation(),
                    },
                    "camera":{
                        "position": self.get_camera_position(),
                        "rotation": self.get_camera_rotation(),
                    },
                    "fieldOfView":90,
                    "gridSize":0.1,
                    "visibilityDistance": 10,
                    "image_path": f"./data/item_image/{self.scene}_{item['name']}.png"
                }
                res.append(dic)
                self.controller.reset(self.scene)

        with open(f"./data/{self.scene}_objects.jsonl", "w") as f:
            import json
            for line in res:
                f.write(json.dumps(line, ensure_ascii=False)+"\n")

    def example(self):
        for item in tqdm(self.eventobject.get_objects(self.controller.last_event)[0]):
            if item["name"] == "DiningTable_0beb798c": # Book_e173324d Box_8e5b2c6b CellPhone_b8be2958
                self.navigate(item)
                self.move_observation(item)
                self.adjust_agent_fieldOfView(150)
                self.save_frame({"item": item["name"], "action": "pick_up"})
        
        pass
    
    def test_visibility(self):
        self.init()
        volumes = {
            "0-0.01": [],
            "0.01-0.05": [],
            "0.05-0.1": [],
            "0.1-0.5": [],
            "0.5-1.0": [],
            "1.0+": []
        }
        import json
        with open("./data/visible_objects_f.jsonl") as f:
            data = [json.loads(line) for line in f.readlines()]
        visible_objects = []
        for d in data:
            visible_objects.extend(d["visible_objects"])
            for obj in d["objects"]:
                if not obj["name"].startswith("Floor_"):
                    volume = obj.get("volum")  # 使用 get 方法避免 KeyError
                    if volume is not None:  # 确保体积存在
                        if 0 <= volume < 0.01:
                            volumes["0-0.01"].append(obj["name"])   
                        elif 0.01 <= volume < 0.05: 
                            volumes["0.01-0.05"].append(obj["name"]) 
                        elif 0.05 <= volume < 0.1:
                            volumes["0.05-0.1"].append(obj["name"])
                        elif 0.1 <= volume < 0.5:
                            volumes["0.1-0.5"].append(obj["name"])
                        elif 0.5 <= volume < 1.0:
                            volumes["0.5-1.0"].append(obj["name"])
                        else:
                            volumes["1.0+"].append(obj["name"])
        
        with open("./data/visible_objects.jsonl", "a") as f:
            import json
            visible_objects = []
            item_names, items = self.eventobject.get_visible_objects(self.controller.last_event)
            for item_name, item in zip(item_names, items):
                volume = self.eventobject.get_item_volume(self.controller.last_event, item_name)
                surface_area = self.eventobject.get_item_surface_area(self.controller.last_event, item_name)
                if volume <= 0.1:
                    if item["distance"] <= 1.5:
                        visible_objects.append(item["name"])
                    elif surface_area > 1:
                        visible_objects.append(item["name"])
                elif volume <= 0.5:
                    if item["distance"] <= 2.5:
                        visible_objects.append(item["name"])
                    elif surface_area > 1:
                        visible_objects.append(item["name"])
                elif volume <= 1:
                    if item["distance"] <= 5.0:
                        visible_objects.append(item["name"])
                    elif surface_area > 1:
                        visible_objects.append(item["name"])
                else:
                    if item["distance"] <= 10.0:
                        visible_objects.append(item["name"])
                        
            dic = {
                "scene": self.scene,
                "objects":[
                    {"name": item["name"], 
                     "visible": item["visible"],
                     "volum": self.eventobject.get_item_volume(self.controller.last_event, item['name']),
                     "surface_area": self.eventobject.get_item_surface_area(self.controller.last_event, item['name']),
                     "distance": item["distance"],
                    }
                for item in self.eventobject.get_objects(self.controller.last_event)[0]
                ],
                "visible_objects": visible_objects,
            }
            f.write(json.dumps(dic, ensure_ascii=False)+"\n")
    
    def get_navigate_location(self):
        metadata = self.controller.last_event.metadata
        volumes = []
        objectid2object={}
        for obj in metadata["objects"]:
            objectid2object[obj["objectId"]]=obj
            if obj["objectType"]!="Floor":#去掉地板
                size=obj["axisAlignedBoundingBox"]["size"]
                # print(size)
                v=size["x"]*size["y"]*size["z"]
                dx=obj["axisAlignedBoundingBox"]["center"]["x"]
                dz=obj["axisAlignedBoundingBox"]["center"]["z"]
                agentx=metadata["agent"]["position"]["x"]
                agentz=metadata["agent"]["position"]["z"]
                d=math.sqrt((dx-agentx)**2+(dz-agentz)**2)
                
                # 计算横面积
                sxz = size["x"] * size["z"]

                # 计算纵向1面积
                sxy = size["x"] * size["y"]

                # 计算纵向2面积
                szy = size["y"] * size["z"]

                # 选择最大的面积作为 s
                s = max(sxz, sxy, szy)
                
                # 计算体积与距离的比率
                if d != 0:  # 防止除以零
                    rate = v / d
                else:
                    rate = 0
                    print(obj["objectId"],"d=0")  
                rate=v/d
                isnavigable=False
                if obj["visible"]==True:#没有被挡住的情况下
                    if v<0.01:#物体体积很小
                        isnavigable=False
                        #体积虽然小，但面积较大，且距离足够近
                        # 1. s>0.5 10米内
                        # 2. s>0.15 4米内
                        # 3. s>0.08 2.5米内
                        # 4. v>0.005 2米内
                        if s>0.5 and d<10:
                            isnavigable=True
                        elif s>0.15 and d<4:
                            isnavigable=True
                        elif s>0.08 and d<2.5:
                            isnavigable=True 
                        elif v>0.005 and d<2:
                            isnavigable=True 
                        elif v>0.001 and d<1.5:
                            isnavigable=True
                        elif d<1:#体积虽然小，但距离足够近
                            isnavigable=True
                    else:
                        isnavigable=True
                        if rate<=0.02:#体积虽然大，但是距离太远v/d
                            isnavigable=False
                            if s>0.5 and d<10:# 排除面积的影响
                                isnavigable=True
                            elif s>0.15 and d<4:
                                isnavigable=True
                            elif s>0.08 and d<2.5:
                                isnavigable=True 
                            elif v>0.005 and d<2:
                                isnavigable=True 
                            elif v>0.001 and d<1.5:
                                isnavigable=True
                            elif d<1:#体积虽然小，但距离足够近
                                isnavigable=True
                                
                volumes.append({
                    "objectId":obj["objectId"],
                    "objectType":obj["objectType"],
                    "visible":obj["visible"],
                    "volume":v,
                    "s":s,
                    "distance":d,
                    "rate":rate,
                    "isnavigable":isnavigable
                })
                sorted_volumes = sorted(volumes, key=lambda v: v["rate"])

        res = {}
        for item in sorted_volumes:
            res[item["objectId"]] = item
        #     if item['isnavigable']:
        #         if item["objectType"] not in self.objecttype2object:
        #             self.objecttype2object[item["objectType"]] = [objectid2object[item["objectId"]]]
        #         else:
        #             itemname = objectid2object[item["objectId"]]['name']
        #             if itemname not in [obj['name'] for obj in self.objecttype2object[item["objectType"]]]:
        #                 self.objecttype2object[item["objectType"]].append(objectid2object[item["objectId"]])
                
        return res
    
    # 全局可达位置
    def get_legal_navigations(self):
        objects = self.get_navigate_location()
        for objectId, obj in objects.items():
            if obj["isnavigable"]:
                if obj["objectType"] not in self.navigable_objects:
                    self.navigable_objects[obj["objectType"]] = 0
                self.navigable_objects[obj["objectType"]] += 1
        
        return list(self.navigable_objects.keys())

    def get_current_container_obj(self):
        if self.current_container is not None:
            objects = [obj.split("|")[0] for obj in self.current_container["receptacleObjectIds"]]
            # print(objects)
            return objects
        else:
            return []

    # 全局可交互位置
    def get_legal_interactions(self):
        legal_interactions = {}
        objects = self.get_navigate_location()
        for objectId, obj in objects.items():
            if (obj["visible"] and obj["objectType"] in self.get_current_container_obj()) or obj["isnavigable"]:
                if obj["objectType"] not in legal_interactions:
                    legal_interactions[obj["objectType"]] = 0
                legal_interactions[obj["objectType"]] += 1
        
        self.legal_interactions = legal_interactions
        return list(self.legal_interactions.keys())

    def action_meta(self, navigate_locations, item, action="obervation"):
        if action =="init":
            self.init_agent_corner()
            navigate_location = self.get_navigate_location()
            for k, item in navigate_location.items():
                if item["objectId"] not in navigate_locations:
                    navigate_locations[item["objectId"]] = item
        
        elif action == "obervation":
            for i in range(3):
                self.action.action_mapping["rotate_left"](self.controller, 90)
                navigate_location = self.get_navigate_location()
                for k, item in navigate_location.items():
                    if item["objectId"] not in navigate_locations:
                        navigate_locations[item["objectId"]] = item
        
        elif action == "navigate":
            self.navigate(item)
            navigate_location = self.get_navigate_location()
            for k, item in navigate_location.items():
                if item["objectId"] not in navigate_locations:
                    navigate_locations[item["objectId"]] = item
        
        elif action == "move":
            self.move_forward(0.5)
            navigate_location = self.get_navigate_location()
            for k, item in navigate_location.items():
                if item["objectId"] not in navigate_locations:
                    navigate_locations[item["objectId"]] = item
        
        
        return navigate_locations, navigate_location
    
    def exec(self, action, item=None):
        # for itemtype in self.eventobject.get_objects_type(self.controller.last_event):
        #     if itemtype not in self.navigable_objects:
        #         self.navigable_objects[itemtype] = 0
        #     self.navigable_objects[itemtype] += 1
        #     if itemtype not in self.legal_interactions:
        #         self.legal_interactions[itemtype] = 0
        #     self.legal_interactions[itemtype] += 1
        self.navigable_objects
        image_fp, legal_locations, legal_objects = None, list(self.navigable_objects.keys()), list(self.legal_interactions.keys())
        # image_fp, legal_locations, legal_objects = None, self.eventobject.get_objects_type(self.controller.last_event), list(self.legal_interactions.keys())
        self.step_count += 1
        for action_name in self.action_space:
            if action_name in action:
                if action_name == "observe" or action_name == "init":
                    image_fp, legal_locations, legal_objects = self.action_space[action_name]()
                    if self.controller.last_event.metadata["errorMessage"]!="":
                        success=False
                    else:
                        success=True
                    return success, image_fp, legal_locations, legal_objects
                elif action_name == "move forward":
                    image_fp, legal_locations, legal_objects = self.action_space[action_name](distance=0.5)
                    if self.controller.last_event.metadata["errorMessage"]!="":
                        success=False
                    else:
                        success=True
                    return success, image_fp, legal_locations, legal_objects
                else:
                    if item is None:
                        return False, None, list(self.navigable_objects.keys()), list(self.legal_interactions.keys())
                    else:
                        # 导航动作
                        if action_name == "navigate to" and item in self.navigable_objects:
                            image_fp, legal_locations, legal_objects = self.action_space[action_name](item)
                            return True, image_fp, legal_locations, legal_objects
                        # 交互动作 # "put in" for MODE=API
                        if action_name in ["pickup", "put", "put in","toggle", "open", "close"] and item in self.legal_interactions:
                            image_fp, legal_locations, legal_objects = self.action_space[action_name](item)
                            if self.controller.last_event.metadata["errorMessage"]!="":
                                success=False
                            else:
                                success=True
                            return success, image_fp, legal_locations, legal_objects
                
        
        return False, image_fp, legal_locations, legal_objects


if __name__ == "__main__":
    autogn = RocAgent("", visibilityDistance=10, fieldOfView=90)
    autogn.get_all_item_image()
    autogn.example()
    autogn.init_agent_corner()
    autogn.test_visibility()
    autogn.get_navigate_path()
    autogn.controller.stop()
    