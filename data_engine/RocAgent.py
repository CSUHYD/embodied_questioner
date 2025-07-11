import math
from baseAgent import BaseAgent
from tqdm import tqdm

class RocAgent(BaseAgent):
    
    def __init__(self, controller):
        super().__init__(controller)
        self.controller=controller
        self.legal_location = {} 
        # self.logger = self._init_logger()
        self.agent_state = []
        self.object_state = {}   
    
    def observe_once(self,leftright="left",degrees="80"):
        isAgentPickup=False
        for obj in self.controller.last_event.metadata["objects"]:
            if obj["isPickedUp"]==True:
                
                isAgentPickup=True
        
        if leftright=="left":
            self.action.action_mapping["rotate_left"](self.controller,degrees=degrees)
            if isAgentPickup==True:
                self.controller.step(
                    action="MoveHeldObjectDown",
                    moveMagnitude=0.07,
                    forceVisible=False
                )
                # print(self.controller.last_event)
                self.controller.step(
                    action="MoveHeldObjectBack",
                    moveMagnitude=0.05,
                    forceVisible=False
                )
                # print(self.controller.last_event)
            
        elif leftright=="right":
            self.action.action_mapping["rotate_right"](self.controller,degrees=degrees)
            if isAgentPickup==True:
                self.controller.step(
                    action="MoveHeldObjectDown",
                    moveMagnitude=0.07,
                    forceVisible=False
                )
                # print(self.controller.last_event)
                self.controller.step(
                    action="MoveHeldObjectBack",
                    moveMagnitude=0.05,
                    forceVisible=False
                )
                # print(self.controller.last_event)
               
    
    def move_forward(self, distance=1):
        
        reachablePositions=self.controller.step(action="GetReachablePositions")
    
        self.action.action_mapping["move_ahead"](self.controller, distance)
        print("RocAgent",self.controller.last_event)
        if self.controller.last_event.metadata["errorMessage"]=="":
            return
        else:
           
            self.action.action_mapping["move_right"](self.controller, distance)
            print("RocAgent",self.controller.last_event)
            if self.controller.last_event.metadata["errorMessage"]=="":
                return
            else:
               
                self.action.action_mapping["move_left"](self.controller, distance)
                print("RocAgent",self.controller.last_event)
                if self.controller.last_event.metadata["errorMessage"]=="":
                    return
                else:
                    
                    self.action.action_mapping["move_back"](self.controller, distance)
                    print("RocAgent",self.controller.last_event)
                    if self.controller.last_event.metadata["errorMessage"]=="":
                        return
                    
                    else:
                        self.action.action_mapping["rotate_right"](self.controller,degrees=90)
                        self.action.action_mapping["move_ahead"](self.controller, distance)
                        print("RocAgent",self.controller.last_event)
                        if self.controller.last_event.metadata["errorMessage"]=="":
                            return
                        else:
                            self.action.action_mapping["rotate_left"](self.controller,degrees=180)
                            self.action.action_mapping["move_ahead"](self.controller, distance)
                            print("RocAgent",self.controller.last_event)
                            if self.controller.last_event.metadata["errorMessage"]=="":
                                return
                            else:
                                self.action.action_mapping["rotate_left"](self.controller,degrees=90)
                                self.action.action_mapping["move_ahead"](self.controller, distance)
                                print("RocAgent",self.controller.last_event)
                                if self.controller.last_event.metadata["errorMessage"]=="":
                                    return
                    
        print("RocAgent",self.controller.last_event)
        

    def navigate(self, item):
        target_position, target_rotation = self.compute_position_8(item, pre_target_positions=[])
        event = self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation)
        pre_target_positions = []
        while not event.metadata['lastActionSuccess']:
            print("teleport failed, retrying...")
            pre_target_positions.append(target_position)
            target_position, target_rotation = self.compute_position_8(item, pre_target_positions)
            event = self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation)
            self.update_event()
        
        self.adjust_view(item)
        self.adjust_height(item)
        
            
        return True, target_position, target_rotation
    

    def interact(self, item, interact_type): 
        object_id = item["objectId"]
        isAgentPickup=False
        for obj in self.controller.last_event.metadata["objects"]:
            if obj["isPickedUp"]==True:
                
                isAgentPickup=True
        if isAgentPickup==True:
            self.controller.step(
                action="MoveHeldObjectDown",
                moveMagnitude=0.07,
                forceVisible=False
            )
            # print(self.controller.last_event)
            self.controller.step(
                action="MoveHeldObjectBack",
                moveMagnitude=0.05,
                forceVisible=False
            )
        
        # change object state
        if interact_type == "open":
            self.action.action_mapping["open"](self.controller, object_id)
        elif interact_type == "close":
            self.action.action_mapping["close"](self.controller, object_id)
        elif interact_type == "break_":
            self.action.action_mapping["break_"](self.controller, object_id)
        elif interact_type == "cook":
            self.action.action_mapping["cook"](self.controller, object_id)
        elif interact_type == "slice_":
            self.action.action_mapping["slice_"](self.controller, object_id)
        elif interact_type == "toggle_on":
            self.action.action_mapping["toggle_on"](self.controller, object_id)
        elif interact_type == "toggle_off":
            self.action.action_mapping["toggle_off"](self.controller, object_id)
        elif interact_type == "dirty":
            self.action.action_mapping["dirty"](self.controller, object_id)
        elif interact_type == "clean":
            self.action.action_mapping["clean"](self.controller, object_id)
        elif interact_type == "fill":
            self.action.action_mapping["fill"](self.controller, object_id)
        elif interact_type == "empty":
            self.action.action_mapping["empty"](self.controller, object_id)
        elif interact_type == "use_up":
            self.action.action_mapping["use_up"](self.controller, object_id)
        elif interact_type == "pick_up":
            self.action.action_mapping["pick_up"](self.controller, object_id)
        elif interact_type == "put":
            self.action.action_mapping["put_in"](self.controller, object_id)
        else:
            raise ValueError(f"Interact type {interact_type} is not defined.")
        print("RocAgent",self.controller.last_event)
        

    def adjust_view(self, item):

        yaw_degrees, pitch_degrees = self.calculate_best_view_angles(item)
        
        camera_yaw = -self.get_camera_rotation() 

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
        
        yaw_rotation = min(angles, key=lambda angle: abs(angle - round(yaw_degrees)))
        yaw_rotation = 0 if yaw_rotation == 360 else yaw_rotation
        
        self.action.action_mapping["rotate_left"](self.controller, self.get_agent_rotation()['y']-yaw_rotation)
        self.update_event()
        

    def adjust_height(self, item):
        
        if self.get_agent_position()['y'] > item['axisAlignedBoundingBox']['cornerPoints'][0][1] + 0.44:
            self.action.action_mapping["crouch"](self.controller)
        
        else:
            self.action.action_mapping["stand"](self.controller)
        
        self.update_event()
        if item['name'] not in self.eventobject.get_visible_objects()[0]:
            self.action.action_mapping["stand"](self.controller)
            self.update_event()

    def adjust_agent_fieldOfView(self, fieldOfView):
        self.backup()
        self.controller.reset(self.scene, fieldOfView=fieldOfView)
        self.recover()


    def get_edge_init_view(self):

        scene_bounds2 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][2]
        scene_bounds3 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][3]
        scene_bounds6 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][6]
        scene_bounds7 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][7]
        edge23 = math.sqrt((scene_bounds2[0]-scene_bounds3[0])**2 + (scene_bounds2[2]-scene_bounds3[2])**2)
        edge26 = math.sqrt((scene_bounds2[0]-scene_bounds6[0])**2 + (scene_bounds2[2]-scene_bounds6[2])**2)
        edge37 = math.sqrt((scene_bounds3[0]-scene_bounds7[0])**2 + (scene_bounds3[2]-scene_bounds7[2])**2)
        edge67 = math.sqrt((scene_bounds6[0]-scene_bounds7[0])**2 + (scene_bounds6[2]-scene_bounds7[2])**2)
        

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
        

        event = self.controller.step(dict(action='GetReachablePositions'))
        reachable_positions = event.metadata['actionReturn']
      
        min_distance = float("inf")
        for position in reachable_positions:
            distance = math.sqrt((position['x']-center[0])**2 + (position['z']-center[2])**2)
            if distance < min_distance:
                min_distance = distance
                target_position = position


        self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation)
        
        self.save_frame({"action": "init1"})
        self.action.action_mapping["rotate_right"](self.controller, 90)
        self.save_frame({"action": "init2"})
        pass

    def get_corner_init_view(self):
        scene_bounds2 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][2]
        scene_bounds3 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][3]
        scene_bounds6 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][6]
        scene_bounds7 = self.controller.last_event.metadata['sceneBounds']['cornerPoints'][7]

        event = self.controller.step(dict(action='GetReachablePositions'))
        reachable_positions = event.metadata['actionReturn']

        min_distance = float("inf")
        for i, scene_bounds in enumerate([scene_bounds2, scene_bounds3, scene_bounds6, scene_bounds7]):
            for position in reachable_positions:
                distance = math.sqrt((position['x']-scene_bounds[0])**2 + (position['z']-scene_bounds[2])**2)
                if distance < min_distance:
                    min_distance = distance
                    target_position = position
                    index = i

        if index == 0:
            # 180, 270
            target_rotation = dict(x=0, y=180, z=0)
        elif index == 1:
            # 270, 360
            target_rotation = dict(x=0, y=270, z=0)
        elif index == 2:
            # 90,180
            target_rotation = dict(x=0, y=90, z=0)
        else:
            # 0,90
            target_rotation = dict(x=0, y=0, z=0)
        
  
        self.action.action_mapping["teleport"](self.controller, position=target_position, rotation=target_rotation)
        self.save_frame({"action": "init3"})
        self.action.action_mapping["rotate_right"](self.controller, 90)
        self.save_frame({"action": "init4"})

    def get_all_item_image(self):
        res = []
        for item in tqdm(self.eventobject.get_objects()[0]):
            # print(item["name"],self.eventobject.get_item_surface_area(item['name']))
            # if item["name"] == "DiningTable_0beb798c":#Book_e173324d Box_8e5b2c6b CellPhone_b8be2958
            # # print(item["name"],":",round(item["rotation"]['y']))
                self.navigate(item)
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
                    "visibilityDistance": 1.5,
                    "image_path": f"./data/item_image/{self.scene}_{item['name']}.png"
                }
                res.append(dic)
                # self.controller.reset(self.scene)
        with open(f"./data/{self.scene}_objects.jsonl", "w") as f:
            import json
            for item in res:
                f.write(json.dumps(item, ensure_ascii=False)+"\n")

    def example(self):
        for item in tqdm(self.eventobject.get_objects()[0]):
            if item["name"] == "DiningTable_0beb798c": # Book_e173324d Box_8e5b2c6b CellPhone_b8be2958
                self.navigate(item)
                self.adjust_agent_fieldOfView(150)
                self.save_frame({"item": item["name"], "action": "pick_up"})
        
        pass
    def split_item(self, item):
         for item in tqdm(self.eventobject.get_objects()[0]):
            receptacle_item = {}

    
    
    # def move_all_breakable_to_corner(self):
    #     # 1. 获取所有breakable且pickupable的object
    #     breakable_objects = [
    #         obj for obj in self.controller.last_event.metadata["objects"]
    #         if obj.get("breakable", False) and obj.get("pickupable", False)
    #     ]
    #     print(f"找到 {len(breakable_objects)} 个可拾取的breakable物体")
        
    #     # 2. 获取角落附近的可达位置作为放置点
    #     scene_bounds = self.controller.last_event.metadata['sceneBounds']
    #     corner = scene_bounds['cornerPoints'][0]  # 选择第一个角点
    #     reachable_positions = self.controller.step(dict(action='GetReachablePositions')).metadata['actionReturn']
        
    #     # 找到距离角落最近的可达位置
    #     min_distance = float('inf')
    #     drop_position = None
    #     for position in reachable_positions:
    #         distance = ((position['x'] - corner[0]) ** 2 + (position['z'] - corner[2]) ** 2) ** 0.5
    #         if distance < min_distance:
    #             min_distance = distance
    #             drop_position = position
        
    #     if drop_position is None:
    #         print("未找到合适的放置位置")
    #         return
            
    #     print(f"选择放置位置: ({drop_position['x']:.2f}, {drop_position['y']:.2f}, {drop_position['z']:.2f})")
        
    #     # 3. 依次搬运
    #     for obj in breakable_objects:
    #         print(f"正在搬运: {obj['name']}")
    #         try:
    #             # 导航到物体
    #             self.navigate(obj)
    #             # 拾取物体
    #             self.interact(obj, "pick_up")
    #             # 检查是否成功拾取
    #             if not self.controller.last_event.metadata["lastActionSuccess"]:
    #                 print(f"拾取失败: {obj['name']}")
    #                 continue
    #             # 传送到放置位置
    #             self.action.action_mapping["teleport"](self.controller, position=drop_position, rotation={'x':0, 'y':0, 'z':0})
    #             # 放下物体
    #             self.action.action_mapping["drop_out"](self.controller)
    #             if self.controller.last_event.metadata["lastActionSuccess"]:
    #                 print(f"成功搬运: {obj['name']}")
    #             else:
    #                 print(f"放下失败: {obj['name']}")
    #         except Exception as e:
    #             print(f"搬运 {obj['name']} 时出错: {e}")
    #             continue

    def put_tomato_on_plate(self):
        """
        从冰箱取出tomato并放在plate上
        """
        print("开始执行：从冰箱取出tomato并放在plate上")
        
        # 1. 找到冰箱和tomato
        fridge = None
        tomato = None
        plate = None
        
        for obj in self.controller.last_event.metadata["objects"]:
            if "Fridge" in obj["name"]:
                fridge = obj
            elif "Tomato" in obj["name"] and obj.get("pickupable", False):
                tomato = obj
            elif "Plate" in obj["name"] and obj.get("receptacle", False):
                plate = obj
        
        if not fridge:
            print("未找到冰箱")
            return False
        if not tomato:
            print("未找到可拾取的tomato")
            return False
        if not plate:
            print("未找到可放置的plate")
            return False
            
        print(f"找到冰箱: {fridge['name']}")
        print(f"找到tomato: {tomato['name']}")
        print(f"找到plate: {plate['name']}")
        
        try:
            # 2. 导航到冰箱并打开
            print("导航到冰箱...")
            self.navigate(fridge)
            print("打开冰箱...")
            self.interact(fridge, "open")
            
            # 3. 导航到tomato并拾取
            print("导航到tomato...")
            self.navigate(tomato)
            print("拾取tomato...")
            self.interact(tomato, "pick_up")
            
            if not self.controller.last_event.metadata["lastActionSuccess"]:
                print("拾取tomato失败")
                return False
                
            print("成功拾取tomato")
            
            # 4. 导航到plate并放置
            print("导航到plate...")
            self.navigate(plate)
            print("将tomato放在plate上...")
            self.interact(plate, "put")
            
            if self.controller.last_event.metadata["lastActionSuccess"]:
                print("成功将tomato放在plate上！")
                return True
            else:
                print("放置tomato失败")
                return False
                
        except Exception as e:
            print(f"执行过程中出错: {e}")
            return False

if __name__ == "__main__":
    
    instruction = "Go to the TV stand in the living room."
    scene2count = {"FloorPlan8": 102, "FloorPlan405": 41, "FloorPlan429": 42, "FloorPlan16": 153, "FloorPlan19": 153, "FloorPlan11": 147, "FloorPlan323": 45, "FloorPlan23": 153, "FloorPlan214": 60, "FloorPlan7": 141, "FloorPlan328": 45, "FloorPlan230": 48, "FloorPlan17": 141, "FloorPlan202": 30, "FloorPlan1": 189, "FloorPlan18": 167, "FloorPlan304": 42, "FloorPlan227": 42, "FloorPlan20": 171, "FloorPlan205": 48, "FloorPlan224": 57, "FloorPlan302": 42, "FloorPlan422": 39, "FloorPlan213": 39, "FloorPlan407": 36, "FloorPlan316": 54, "FloorPlan4": 159, "FloorPlan409": 42, "FloorPlan25": 138, "FloorPlan212": 54, "FloorPlan320": 39, "FloorPlan201": 45, "FloorPlan5": 129, "FloorPlan403": 42, "FloorPlan13": 147, "FloorPlan426": 42, "FloorPlan6": 132, "FloorPlan330": 39, "FloorPlan222": 45, "FloorPlan24": 141, "FloorPlan311": 47, "FloorPlan207": 42, "FloorPlan12": 111, "FloorPlan26": 132, "FloorPlan413": 51, "FloorPlan401": 39, "FloorPlan408": 42, "FloorPlan419": 36, "FloorPlan21": 183, "FloorPlan14": 126, "FloorPlan303": 54, "FloorPlan204": 48, "FloorPlan22": 99, "FloorPlan2": 120, "FloorPlan326": 45, "FloorPlan218": 54, "FloorPlan30": 138, "FloorPlan28": 123, "FloorPlan27": 150, "FloorPlan423": 48, "FloorPlan3": 120, "FloorPlan223": 48, "FloorPlan417": 51, "FloorPlan310": 45, "FloorPlan402": 45, "FloorPlan15": 156, "FloorPlan418": 33, "FloorPlan313": 42, "FloorPlan324": 45, "FloorPlan229": 39, "FloorPlan414": 39, "FloorPlan305": 60, "FloorPlan410": 39, "FloorPlan428": 42, "FloorPlan329": 45, "FloorPlan203": 51, "FloorPlan406": 39, "FloorPlan314": 45, "FloorPlan309": 45, "FloorPlan427": 54, "FloorPlan415": 42, "FloorPlan301": 39, "FloorPlan327": 45, "FloorPlan216": 42, "FloorPlan206": 42, "FloorPlan412": 36, "FloorPlan318": 48, "FloorPlan225": 48, "FloorPlan208": 39, "FloorPlan416": 39, "FloorPlan307": 54, "FloorPlan421": 33, "FloorPlan210": 33, "FloorPlan420": 48, "FloorPlan321": 27, "FloorPlan430": 42, "FloorPlan228": 42, "FloorPlan306": 33, "FloorPlan317": 45, "FloorPlan220": 27, "FloorPlan211": 39, "FloorPlan209": 39, "FloorPlan221": 45, "FloorPlan217": 54, "FloorPlan312": 24, "FloorPlan411": 39, "FloorPlan319": 36, "FloorPlan322": 36, "FloorPlan315": 66, "FloorPlan9": 150, "FloorPlan29": 71, "FloorPlan215": 57, "FloorPlan425": 36, "FloorPlan226": 45, "FloorPlan325": 27, "FloorPlan404": 36, "FloorPlan10": 144, "FloorPlan219": 45, "FloorPlan424": 27, "FloorPlan308": 39}

    scene2count = dict(sorted(scene2count.items(), key=lambda x: -x[1]))
    for scene in scene2count:
        autogn = RocAgent("FloorPlan201")
        # autogn.get_all_item_image()
        # autogn.example()
        autogn.get_corner_init_view()
        autogn.controller.stop()
        break
    # autogn.planning(instruction)
        