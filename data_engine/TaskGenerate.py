import random

from utils import save_data_to_json,get_scene_metadata,load_json

class TaskGenerate:
    def __init__(
        self,
        metadata,
        generate_task_path,
        metadata_path="",
        ):
        """
        This initializer generates different types of tasks for each piece of scene metadata from AI2THOR.
        metadata: The scene metadata from AI2THOR
        generate_task_path: The directory path where the generated task templates will be stored
        metadata_path: The file path for logging or referencing the metadata
        """
        self.metadata=metadata
        self.metadata_path=metadata_path
        self.generate_task_path=generate_task_path  
        
    def delete_re_object(self):
        unique_type_list=[]
        unique_objects=[]
        for obj in self.metadata['objects']: 
            obj_type=obj['objectType']
            if obj_type not in unique_type_list:
                unique_type_list.append(obj_type)
                unique_objects.append(obj)
        return unique_objects,unique_type_list
   
    def is_pickupable(self, obj):
        """
        Whether the object can be pick up.
        """
        return obj.get("pickupable", None)
    
    def is_toggleable(self, obj):
        """
        Whether the object can be toggled.
        """
        return obj.get("toggleable", None)
    
    def is_openable(self,obj):
        """
        Whether the object can be opened.
        """
        return obj.get("openable", False) and not obj.get("isOpen", False)
    
    def is_receptacle(self,obj):
        """
        Whether the object is a container.
        """
        return obj.get("receptacle", False) 

    def is_parent_receptacle_openable(self, obj):
        """
        Whether the object's parent container can be opened.
        """
        parent_receptacles = obj.get("parentReceptacles", [])
        if not parent_receptacles:
            return False   
        first_parent_id = parent_receptacles[-1]  
        
        objects=self.metadata["objects"]
        for obj in objects:
            if obj.get("objectId") == first_parent_id:
                if obj.get("openable", False) and not obj.get("isOpen", False):
                    return True
        return False
    
    def is_parent_floor_or_null(self, obj):
        """
        Whether the object's parent container is Floor or null.
        """
        parent_receptacles = obj.get("parentReceptacles", [])
        if not parent_receptacles:
            return True  

        for parent_id in parent_receptacles:
            if parent_id and parent_id.startswith("Floor"):
                return True
        return False
    
    def is_parent_floor(self, obj):
        """
        Whether the object's parent container is Floor 
        """
        parent_receptacles = obj.get("parentReceptacles", [])
        if not parent_receptacles:
            return False 

        for parent_id in parent_receptacles:
            if parent_id and parent_id.startswith("Floor"):
                return True
        return False

    def is_grandparent_floor_or_null(self, obj):
        """
        Whether the parent container of the object's parent container container is Floor or null.
        """
        parent_receptacles = obj.get("parentReceptacles", [])
        if not parent_receptacles:
            return None 

        first_parent_id = parent_receptacles[-1]
        # print(first_parent_id)

        objects=self.metadata["objects"]
        for obj in objects:
            if obj.get("objectId") == first_parent_id:
                grandparent_receptacles = obj.get("parentReceptacles", [])
                if grandparent_receptacles is None:
                    return True
                if grandparent_receptacles is not None:
                    for grandparent_id in grandparent_receptacles:
                        if grandparent_id and grandparent_id.startswith("Floor"):
                            return True
                    # grandparent_receptacle=grandparent_receptacles[-1]
                    # if grandparent_receptacle.startswith("Floor"):
                    #     return True
        return None

    def extract_parent_receptacles(self,parent_receptacles):
        """
        get parent receptacles'[{"objectType","obejctId"},...]
        """
        result = []
        for parentid in parent_receptacles:
            parent_type = parentid.split('|')[0]
            result.append({"type":parent_type, "id":parentid})
        return result

   
    #############################
    ## generate task type #######
    # {"action":"navigate to",
    # "objectId":obj_parent_id,
    # "objectType":obj_parent_type,
    # "baseaction":"", # todo.for next version
    # "reward":1,
    # "relatedObject":[obj_parent_id,obj_id]}
    #############################
                 
    def single_search(self,num=1):
        """
        tasktype: search
        subtasktype: Exposed Object Search
        """
        generate_task=[]
        task_type="single_search"
        
        metadata=self.metadata
        objects=metadata["objects"]
        for obj in objects:
            if self.is_pickupable(obj) and not self.is_parent_floor_or_null(obj):
                if  not self.is_parent_receptacle_openable(obj):
                    if  self.is_grandparent_floor_or_null(obj):
                        obj_type=obj["objectType"]
                        obj_id=obj["objectId"]
                        
                        parent_reps=self.extract_parent_receptacles(obj["parentReceptacles"])
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]
                        
                        expressions = [
                            f"Find the {obj_type} in the room.",
                            f"Locate the {obj_type} in the room.",
                            f"Identify the {obj_type} in the room.",
                            f"Look for the {obj_type} in the room.",
                            f"Search the room for the {obj_type}.",
                            f"Could you please find the {obj_type} in the room?",
                            f"Would you mind locating the {obj_type} in the room?",
                            f"Can you identify the {obj_type} in the room, please?",
                            f"Have a look for the {obj_type} in the room.",
                            f"Check out the room and find the {obj_type}.",
                            f"See if you can spot the {obj_type} in the room."
                        ]

                        # Randomly choose one expression
                        task_name = random.choice(expressions)
                        metadatapath=self.metadata_path
                        
                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"end",
                            "objectId":"",
                            "objectType":"",
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )

                        totalreward=2
                        
                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break
        
        save_data_to_json(generate_task,self.generate_task_path)
        
        return 
    
    def single_search_from_closerep(self,num=1):
        """
        tasktype: search
        subtasktype: Enclosed Object Search
        """
        generate_task=[]
        task_type="single_search_from_closerep"
        
        delete_closerep=['Toilet']

        no_re_obj,on_re_obj_list=self.delete_re_object()
        
        metadata=self.metadata
        objects=metadata["objects"]
        for obj in no_re_obj:
            if self.is_pickupable(obj):
                # print("is_pickupable",obj["objectId"])
                if  self.is_parent_receptacle_openable(obj):
                    # print("is_first_parent_receptacle_openable",obj["objectId"])
                    
                    # print(single_search_obj)
                    obj_type=obj["objectType"]
                    obj_id=obj["objectId"]
                    
                    parent_reps=self.extract_parent_receptacles(obj["parentReceptacles"])
                    obj_parent_type=parent_reps[-1]["type"]
                    obj_parent_id=parent_reps[-1]["id"]
                    
                    for obj in objects:
                        if obj["objectId"]==obj_parent_id and self.is_parent_floor_or_null(obj) and obj["objectType"] not in delete_closerep:
                            expressions = [
                                f"Find the {obj_type} in the room.",
                                f"Locate the {obj_type} in the room.",
                                f"Identify the {obj_type} in the room.",
                                f"Look for the {obj_type} in the room.",
                                f"Search the room for the {obj_type}.",
                                f"Could you please find the {obj_type} in the room?",
                                f"Would you mind locating the {obj_type} in the room?",
                                f"Can you identify the {obj_type} in the room, please?",
                                f"Have a look for the {obj_type} in the room.",
                                f"Check out the room and find the {obj_type}.",
                                f"See if you can spot the {obj_type} in the room."
                            ]
                            
                            task_name=random.choice(expressions)
                            metadatapath=self.metadata_path
                            
                            updated_actions = []
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":obj_parent_id,
                                "objectType":obj_parent_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id,obj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"open",
                                "objectId":obj_parent_id,
                                "objectType":obj_parent_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id]
                                }
                            )
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id,obj_id]
                                }
                            )
                            totalreward=3

                            task = {
                                "taskname": task_name,
                                "tasktype": task_type,
                                "metadatapath": metadatapath,
                                "actions": updated_actions,
                                "totalreward":totalreward,
                            }
                            generate_task.append(task)
                            
                            if len(generate_task) >= num:
                                break
        
        save_data_to_json(generate_task,self.generate_task_path)
        
        return 
        
    def single_pickup(self,num=1):
        """
        tasktype: manipulate
        subtasktype: Exposed Object Grasping
        """
        generate_task=[]
        task_type="single_pickup"
        no_re_obj,on_re_obj_list=self.delete_re_object()

        metadata=self.metadata
        objects=metadata["objects"]
        for obj in no_re_obj:
            if self.is_pickupable(obj) and not self.is_parent_floor_or_null(obj):
                if  not self.is_parent_receptacle_openable(obj):
                    if  self.is_grandparent_floor_or_null(obj):
                        obj_type=obj["objectType"]
                        obj_id=obj["objectId"]

                        parent_reps=self.extract_parent_receptacles(obj["parentReceptacles"])
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]
                        
                        expressions = [
                            f"Take a {obj_type} from the room.",
                            f"Grab a {obj_type} from the room.",
                            f"Pick up a {obj_type} from the room.",
                            f"Retrieve a {obj_type} from the room.",
                            f"Get a {obj_type} from the room.",
                            f"Fetch a {obj_type} from the room.",
                            f"Take one {obj_type} from the room.",
                            f"Collect a {obj_type} from the room.",
                        ]

                        # Randomly choose one expression
                        task_name = random.choice(expressions)
                        metadatapath=self.metadata_path
                        
                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":obj_id,
                            "objectType":obj_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"end",
                            "objectId":"",
                            "objectType":"",
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )

                        totalreward=3

                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break
        
        save_data_to_json(generate_task,self.generate_task_path)
        
        return 
 
    def single_pickup_from_closerep(self,num=1):
        """
        tasktype: manipulate
        subtasktype: Enclosed Object Grasping
        """
        generate_task=[]
        task_type="single_pickup_from_closerep"
        metadata=self.metadata
        objects=metadata["objects"]
        no_re_obj,on_re_obj_list=self.delete_re_object()
        for obj in no_re_obj:
            if self.is_pickupable(obj):
                if  self.is_parent_receptacle_openable(obj):
                    obj_type=obj["objectType"]
                    obj_id=obj["objectId"]

                    parent_reps=self.extract_parent_receptacles(obj["parentReceptacles"])
                    obj_parent_type=parent_reps[-1]["type"]
                    obj_parent_id=parent_reps[-1]["id"]
                    
                    for obj in objects:
                        if obj["objectId"]==obj_parent_id and self.is_parent_floor_or_null(obj):
                            
                            expressions = [
                                f"Take a {obj_type} from the room.",
                                f"Grab a {obj_type} from the room.",
                                f"Pick up a {obj_type} from the room.",
                                f"Retrieve a {obj_type} from the room.",
                                f"Get a {obj_type} from the room.",
                                f"Fetch a {obj_type} from the room.",
                                f"Take one {obj_type} from the room.",
                                f"Collect a {obj_type} from the room.",
                            ]
                            
                            task_name=random.choice(expressions)
                            metadatapath=self.metadata_path
                            updated_actions = []
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":obj_parent_id,
                                "objectType":obj_parent_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id]
                                }
                            )
                            updated_actions.append({
                                "action":"open",
                                "objectId":obj_parent_id,
                                "objectType":obj_parent_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id]
                                }
                            )
                            updated_actions.append({
                                "action":"pickup",
                                "objectId":obj_id,
                                "objectType":obj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_id]
                                }
                            )    
                            updated_actions.append({
                                "action":"close",
                                "objectId":obj_parent_id,
                                "objectType":obj_parent_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id]
                                }
                            )                     
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[obj_parent_id,obj_id]
                                }
                            )
                            totalreward=5
                            # totalreward=4
                            task = {
                                "taskname": task_name,
                                "tasktype": task_type,
                                "metadatapath": metadatapath,
                                "actions": updated_actions,
                                "totalreward":totalreward,
                            }
                            generate_task.append(task)
                            
                            if len(generate_task) >= num:
                                break
        save_data_to_json(generate_task,self.generate_task_path)
        
        return 
    
    def single_toggle(self,num=1):
        """
        tasktype: manipulate
        subtasktype: Exposed Object Toggle
        """
        generate_task=[]
        task_type="single_toggle"
        his_object_type=[]
        metadata=self.metadata
        objects=metadata["objects"]
        for obj in objects:
            if obj["objectType"] in his_object_type:
                continue
            if obj["objectType"] in ["Candle","LightSwitch","StoveBurner","StoveKnob"]:
                continue
            if self.is_toggleable(obj) and not self.is_parent_floor_or_null(obj):
                if  not self.is_parent_receptacle_openable(obj):
                    if  self.is_grandparent_floor_or_null(obj):
                        obj_type=obj["objectType"]
                        obj_id=obj["objectId"]
                        parent_reps=self.extract_parent_receptacles(obj["parentReceptacles"])
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]
                        
                        if obj["isToggled"]==True:
                            expressions = [
                                f"Turn off the switch of the {obj_type}.",
                                f"Switch off the {obj_type}.",
                                f"Flip the switch of the {obj_type} off.",
                                f"Deactivate the switch of the {obj_type}.",
                                f"Power off the {obj_type}.",
                                f"Turn the {obj_type}'s switch off.",
                                f"Switch the {obj_type} off.",
                                f"Turn the switch for the {obj_type} off.",
                                f"Disengage the {obj_type}'s switch.",
                                f"Press the {obj_type} switch to turn it off."
                            ]
                            task_name = random.choice(expressions)
                            
                        elif obj["isToggled"]==False:
                            expressions = [
                                f"Turn on the switch of the {obj_type}.",
                                f"Switch on the {obj_type}.",
                                f"Flip the switch of the {obj_type}.",
                                f"Activate the switch of the {obj_type}.",
                                f"Power on the {obj_type}.",
                                f"Turn the {obj_type}'s switch on.",
                                f"Switch the {obj_type} on.",
                                f"Turn the switch for the {obj_type} on.",
                                f"Engage the {obj_type}'s switch.",
                                f"Press the {obj_type} switch to turn it on."
                            ]
                            task_name = random.choice(expressions)   
                        metadatapath=self.metadata_path

                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )
                        
                        updated_actions.append({
                            "action":"toggle",
                            "objectId":obj_id,
                            "objectType":obj_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"end",
                            "objectId":"",
                            "objectType":"",
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )

                        totalreward=3
                        his_object_type.append(obj_type)
                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break   
        save_data_to_json(generate_task,self.generate_task_path)
        
        return
    
    def pickup_and_put(self,num=1):
        """
        tasktype: transport
        subtasktype: Exposed-to-Exposed Object Transfer
        """
        obj_parent_type='' 
        obj_parent_id=''
        all_obj=[] 
        task_type="pickup_and_put"
        metadata=self.metadata
        objects=metadata["objects"]
        generate_task=[]
        for_obj_select_can_put={} 
        select_can_put=load_json('taskgenerate/pick_up_and_put.json')
        unique_objects,unique_type_list=self.delete_re_object()
        
        for obj_list in select_can_put: 
            for key, value in obj_list.items():
                for i in unique_objects:
                    if i['objectType']==key:
                        for_obj_select_can_put[key] = value 
                        all_obj.append(key)
        
        for obj in unique_objects:
            if self.is_pickupable(obj) and obj['objectType'] in all_obj:
                if  not self.is_parent_receptacle_openable(obj) and obj["parentReceptacles"] is not None:
                    new_obj_parentReceptacles=[]
                    for item in obj["parentReceptacles"]:
                        if obj['objectType'] not in item:
                            new_obj_parentReceptacles.append(item)
                    obj_type=obj['objectType'] 
                    obj_id=obj["objectId"]
                    parent_reps=self.extract_parent_receptacles(new_obj_parentReceptacles)
                    if parent_reps!=[]:
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]
                        
                    can_put_list_new=[]
                    can_put_list=[]
                    for i in for_obj_select_can_put[obj['objectType']]:
                        for j in objects: 
                            if j['objectType']==i:
                                can_put_list.append(i) 
                                break
                                
                    if obj_parent_type=='Sink':
                        obj_parent_type='SinkBasin'
                    if can_put_list!=[] and obj_parent_type in can_put_list:
                        can_put_list.remove(obj_parent_type)
                    for rep in can_put_list: 
                        for i in objects:
                            if i['objectType']==rep:
                                if not self.is_openable(i) and self.is_receptacle(i) :
                                    parent=i['parentReceptacles'] 
                                    if parent!=None: 
                                        parent=i['parentReceptacles'][0]
                                        for j in objects:
                                            if j['objectId']==parent:
                                                if j['openable']!=True:
                                                    can_put_list_new.append(rep)
                                                    break
                                        break
                                    else:
                                        can_put_list_new.append(rep)
                                        break
                                    
                    putobj_2=''
                    if len(can_put_list_new)!=0:
                        putobj_1=random.choice(can_put_list_new)
                        for j in objects:
                            if j.get("objectType") == putobj_1:
                                putobj_2=j 
                                break
                        putobj_type=putobj_2["objectType"] 
                        putobj_id=putobj_2["objectId"]  
                        
                        task_name=f"put the {obj_type} in the {putobj_type}"
                        
                        metadatapath=self.metadata_path
                        
                        putobj_id_reps=next(obj["parentReceptacles"] for obj in objects if obj["objectId"]==putobj_id)

                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id]))
                            }
                        )
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":obj_id,
                            "objectType":obj_type,
                            "baseaction":"pickup",
                            "reward":1,
                            "relatedObject":list(dict.fromkeys([obj_id]))
                            }
                        )
                        if putobj_id_reps is None:
                            putobj_id_reps=""
                        for item in putobj_id_reps:
                            if item.split('|')[0]=="Floor":
                                putobj_id_reps=""
                                
                        if putobj_id_reps=="":  
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys([putobj_id]))
                                }
                            )
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys([putobj_id]))
                                }
                            )
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id,putobj_id]))
                                }
                            )
                        else:
                            objectId=putobj_id_reps[-1]
                            objectType=putobj_id_reps[-1].split('|')[0]
                            putobj_id_reps.append(putobj_id)
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objectId,
                                "objectType":objectType,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id_reps[-1],
                                "objectType":putobj_id_reps[-1].split('|')[0],
                                "baseaction":"put",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            putobj_id_reps_new=[]
                            putobj_id_reps_new.append(obj_parent_id)
                            putobj_id_reps_new.append(obj_id)
                            for o in putobj_id_reps:
                                putobj_id_reps_new.append(o)
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps_new))
                                }
                            )
                        
                        totalreward=5
                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break       
        save_data_to_json(generate_task,self.generate_task_path) 
        return  
  
    def pickup_from_closerep_and_put(self,num=1):
        """
        tasktype: transport
        subtasktype: Enclosed-to-Exposed Object Transfer
        """
        obj_parent_type='' 
        obj_parent_id='' 
        all_obj=[] 
        task_type="pickup_from_closerep_and_put"
        metadata=self.metadata
        objects=metadata["objects"]
        generate_task=[]
        for_obj_select_can_put={} 
        select_can_put=load_json('taskgenerate/pick_up_and_put.json')
        unique_objects,unique_type_list=self.delete_re_object()
        
        for obj_list in select_can_put: 
            for key, value in obj_list.items():
                for i in unique_objects:
                    if i['objectType']==key:
                        for_obj_select_can_put[key] = value 
                        all_obj.append(key)
        for obj in unique_objects:
            if self.is_pickupable(obj) and obj['objectType'] in all_obj:
                if  self.is_parent_receptacle_openable(obj) and obj["parentReceptacles"] is not None:
                    new_obj_parentReceptacles=[]
                    for item in obj["parentReceptacles"]:
                        if obj['objectType'] not in item:
                            new_obj_parentReceptacles.append(item)
                    obj_type=obj['objectType'] 
                    obj_id=obj["objectId"] 
                    parent_reps=self.extract_parent_receptacles(new_obj_parentReceptacles)
                    if parent_reps!=[]:
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]
                        
                    can_put_list_new=[]
                    can_put_list=[]
                    for i in for_obj_select_can_put[obj['objectType']]:
                        for j in objects: 
                            if j['objectType']==i:
                                can_put_list.append(i) 
                                break

                    if obj_parent_type=='Sink':
                        obj_parent_type='SinkBasin'
                    if can_put_list!=[] and obj_parent_type in can_put_list:
                        can_put_list.remove(obj_parent_type)
                    for rep in can_put_list: 
                        for i in objects:
                            if i['objectType']==rep:
                                if not self.is_openable(i) and self.is_receptacle(i) :
                                    parent=i['parentReceptacles']
                                    if parent!=None: 
                                        parent=i['parentReceptacles'][0]
                                        for j in objects:
                                            if j['objectId']==parent:
                                                if j['openable']!=True:
                                                    can_put_list_new.append(rep)
                                                    break
                                        break
                                    else:
                                        can_put_list_new.append(rep)
                                        break
                    putobj_2=''
                    if len(can_put_list_new)!=0:
                        putobj_1=random.choice(can_put_list_new)
                        for j in objects:
                            if j.get("objectType") == putobj_1:
                                putobj_2=j 
                                break
                        putobj_type=putobj_2["objectType"] 
                        putobj_id=putobj_2["objectId"]
                        
                        task_name=f"put the {obj_type} in the {putobj_type}"
                        metadatapath=self.metadata_path
                        putobj_id_reps=next(obj["parentReceptacles"] for obj in objects if obj["objectId"]==putobj_id)

                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id]))
                            }
                        )
                        updated_actions.append({
                            "action":"open",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id]
                            }
                        )
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":obj_id,
                            "objectType":obj_type,
                            "baseaction":"pickup",
                            "reward":1,
                            "relatedObject":[obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"close",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"pickup",
                            "reward":1,
                            "relatedObject":[obj_parent_id]
                            }
                        )
                        if putobj_id_reps is None:
                            putobj_id_reps=""
                        for item in putobj_id_reps:
                            if item.split('|')[0]=="Floor":
                                putobj_id_reps=""
                                
                        if putobj_id_reps=="":  
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            ) 
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id,putobj_id]))
                                }
                            )
                        else:
                            objectId=putobj_id_reps[-1]
                            objectType=putobj_id_reps[-1].split('|')[0]
                            putobj_id_reps.append(putobj_id)
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objectId,
                                "objectType":objectType,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id_reps[-1],
                                "objectType":putobj_id_reps[-1].split('|')[0],
                                "baseaction":"put",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            putobj_id_reps_new=[]
                            putobj_id_reps_new.append(obj_parent_id)
                            putobj_id_reps_new.append(obj_id)
                            for o in putobj_id_reps:
                                putobj_id_reps_new.append(o)
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps_new))
                                }
                            )
                        totalreward=7
                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break       
        save_data_to_json(generate_task,self.generate_task_path) 
        return  
        
    def pickup_and_put_in_closerep(self,num=1):
        """
        tasktype: transport
        subtasktype: Exposed-to-Enclosed Object Transfer
        """
        obj_parent_type='' 
        obj_parent_id='' 
        all_obj=[] 
        task_type="pickup_and_put_in_closerep"
        metadata=self.metadata
        objects=metadata["objects"]
        generate_task=[]
        for_obj_select_can_put={} 
        select_can_put=load_json('taskgenerate/pick_up_and_put.json')
        unique_objects,unique_type_list=self.delete_re_object()
        
        for obj_list in select_can_put:
            for key, value in obj_list.items():
                for i in unique_objects:
                    if i['objectType']==key:
                        for_obj_select_can_put[key] = value
                        all_obj.append(key)
        for obj in unique_objects:
            if self.is_pickupable(obj) and obj['objectType'] in all_obj:
                if  not self.is_parent_receptacle_openable(obj) and obj["parentReceptacles"] is not None:
                    new_obj_parentReceptacles=[]
                    for item in obj["parentReceptacles"]:
                        if obj['objectType'] not in item:
                            new_obj_parentReceptacles.append(item)
                    obj_type=obj['objectType'] 
                    obj_id=obj["objectId"]
                    parent_reps=self.extract_parent_receptacles(new_obj_parentReceptacles)
                    if parent_reps!=[]:
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]

                    can_put_list_new=[]
                    can_put_list=[]
                    for i in for_obj_select_can_put[obj['objectType']]:
                        for j in objects: 
                            if j['objectType']==i:
                                can_put_list.append(i)
                                break

                    if obj_parent_type=='Sink':
                        obj_parent_type='SinkBasin'
                    if can_put_list!=[] and obj_parent_type in can_put_list:
                        can_put_list.remove(obj_parent_type)
                    for rep in can_put_list: 
                        for i in objects:
                            if i['objectType']==rep:
                                if self.is_openable(i) and self.is_receptacle(i) :
                                    parent=i['parentReceptacles'] 
                                    if parent!=None: 
                                        parent=i['parentReceptacles'][0]
                                        for j in objects:
                                            if j['objectId']==parent:
                                                if j['openable']!=True:
                                                    can_put_list_new.append(rep)
                                                    break
                                        break
                                    else:
                                        can_put_list_new.append(rep)
                                        break
                    putobj_2=''
                    if len(can_put_list_new)!=0:
                        putobj_1=random.choice(can_put_list_new)
                        for j in objects:
                            if j.get("objectType") == putobj_1:
                                putobj_2=j 
                                break
                        putobj_type=putobj_2["objectType"]
                        putobj_id=putobj_2["objectId"]
                        
                        task_name=f"put the {obj_type} in the {putobj_type}"
                        metadatapath=self.metadata_path
                        putobj_id_reps=next(obj["parentReceptacles"] for obj in objects if obj["objectId"]==putobj_id)

                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id,obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":obj_id,
                            "objectType":obj_type,
                            "baseaction":"pickup",
                            "reward":1,
                            "relatedObject":[obj_id]
                            }
                        )
                        if putobj_id_reps is None:
                            putobj_id_reps=""
                        for item in putobj_id_reps:
                            if item.split('|')[0]=="Floor":
                                putobj_id_reps=""
                                
                        if putobj_id_reps=="":  
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"open",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id,putobj_id]))
                                }
                            )
                        else:
                            objectId=putobj_id_reps[-1]
                            objectType=putobj_id_reps[-1].split('|')[0]
                            putobj_id_reps.append(putobj_id)
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objectId,
                                "objectType":objectType,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            updated_actions.append({
                                "action":"open",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id_reps[-1],
                                "objectType":putobj_id_reps[-1].split('|')[0],
                                "baseaction":"put",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            putobj_id_reps_new=[]
                            putobj_id_reps_new.append(obj_parent_id)
                            putobj_id_reps_new.append(obj_id)
                            for o in putobj_id_reps:
                                putobj_id_reps_new.append(o)
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps_new))
                                }
                            )
                        totalreward=6
                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break      
        save_data_to_json(generate_task,self.generate_task_path) 
        return  

    def pickup_from_closerep_and_put_in_closerep(self,num=1):
        """
        tasktype: transport
        subtasktype: Enclosed-to-Enclosed Object Transfer
        """
        obj_parent_type=''
        obj_parent_id=''
        all_obj=[] 
        task_type="pickup_from_closerep_and_put_in_closerep"
        metadata=self.metadata
        objects=metadata["objects"]
        generate_task=[]
        for_obj_select_can_put={} 
        select_can_put=load_json('taskgenerate/pick_up_and_put.json')
        unique_objects,unique_type_list=self.delete_re_object()
        
        for obj_list in select_can_put: 
            for key, value in obj_list.items():
                for i in unique_objects:
                    if i['objectType']==key:
                        for_obj_select_can_put[key] = value 
                        all_obj.append(key)
        for obj in unique_objects:
            if self.is_pickupable(obj) and obj['objectType'] in all_obj:
                if   self.is_parent_receptacle_openable(obj) and obj["parentReceptacles"] is not None:
                    new_obj_parentReceptacles=[]
                    for item in obj["parentReceptacles"]:
                        if obj['objectType'] not in item:
                            new_obj_parentReceptacles.append(item)
                    obj_type=obj['objectType']
                    obj_id=obj["objectId"]
                    parent_reps=self.extract_parent_receptacles(new_obj_parentReceptacles)
                    if parent_reps!=[]:
                        obj_parent_type=parent_reps[-1]["type"]
                        obj_parent_id=parent_reps[-1]["id"]
    
                    can_put_list_new=[]
                    can_put_list=[]

                    for i in for_obj_select_can_put[obj['objectType']]:
                        for j in objects: 
                            if j['objectType']==i:
                                can_put_list.append(i) 
                                break

                    if obj_parent_type=='Sink':
                        obj_parent_type='SinkBasin'
                    if can_put_list!=[] and obj_parent_type in can_put_list:
                        can_put_list.remove(obj_parent_type)
                    for rep in can_put_list: 
                        for i in objects:
                            if i['objectType']==rep:
                                if self.is_openable(i) and self.is_receptacle(i) :
                                    parent=i['parentReceptacles'] 
                                    if parent!=None: 
                                        parent=i['parentReceptacles'][0]
                                        for j in objects:
                                            if j['objectId']==parent:
                                                if j['openable']!=True:
                                                    can_put_list_new.append(rep)
                                                    break
                                        break
                                    else:
                                        can_put_list_new.append(rep)
                                        break
                    putobj_2=''
                    if len(can_put_list_new)!=0:
                        putobj_1=random.choice(can_put_list_new)
                        for j in objects:
                            if j.get("objectType") == putobj_1:
                                putobj_2=j
                                break
                        putobj_type=putobj_2["objectType"] 
                        putobj_id=putobj_2["objectId"]
                        
                        task_name=f"put the {obj_type} in the {putobj_type}"
                        metadatapath=self.metadata_path
                        putobj_id_reps=next(obj["parentReceptacles"] for obj in objects if obj["objectId"]==putobj_id)
                        
                        updated_actions = []
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id]))
                            }
                        )
                        updated_actions.append({
                            "action":"open",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id]
                            }
                            )
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":obj_id,
                            "objectType":obj_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_id]
                            }
                        )
                        updated_actions.append({
                            "action":"close",
                            "objectId":obj_parent_id,
                            "objectType":obj_parent_type,
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[obj_parent_id]
                            }
                        )
                        if putobj_id_reps is None:
                            putobj_id_reps=""
                        for item in putobj_id_reps:
                            if item.split('|')[0]=="Floor":
                                putobj_id_reps=""
                                
                        if putobj_id_reps=="":  
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"open",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )                           
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys([obj_parent_id,obj_id,putobj_id]))
                                }
                            )
                        else:
                            objectId=putobj_id_reps[-1]
                            objectType=putobj_id_reps[-1].split('|')[0]
                            putobj_id_reps.append(putobj_id)
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objectId,
                                "objectType":objectType,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            updated_actions.append({
                                "action":"open",
                                "objectId":putobj_id,
                                "objectType":putobj_type,
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[putobj_id]
                                }
                            )
                            updated_actions.append({
                                "action":"put",
                                "objectId":putobj_id_reps[-1],
                                "objectType":putobj_id_reps[-1].split('|')[0],
                                "baseaction":"put",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps))
                                }
                            )
                            putobj_id_reps_new=[]
                            putobj_id_reps_new.append(obj_parent_id)
                            putobj_id_reps_new.append(obj_id)
                            for o in putobj_id_reps:
                                putobj_id_reps_new.append(o)
                            updated_actions.append({
                                "action":"end",
                                "objectId":"",
                                "objectType":"",
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":list(dict.fromkeys(putobj_id_reps_new))
                                }
                            )
                        totalreward=8
                        task = {
                            "taskname": task_name,
                            "tasktype": task_type,
                            "metadatapath": metadatapath,
                            "actions": updated_actions,
                            "totalreward":totalreward,
                        }
                        generate_task.append(task)
                        
                        if len(generate_task) >= num:
                            break     
        save_data_to_json(generate_task,self.generate_task_path) 
        return
    
    def check_object_type_uniqueness(self, object_type):
        """
        Check whether objectType is unique in metadata
        """
        uniqueness_result = False
        count = sum(1 for obj in self.metadata["objects"] if obj["objectType"] == object_type)
        uniqueness_result = (count == 1)
        return uniqueness_result
    
    def select_new_container(self,obj, obj_rep, pickup_rep_match, rep_list):
        """
        choose a new container.
        1. The new container is not objA_rep['objectType'].
        2. objA['objectType'] and the new container meet the matching rules of pickup_rep_match.
        Args:
            objA (dict): object A containing objectType.
            objA_rep (dict): original container information of object A containing the original container type.
            pickup_rep_match (list): mapping of objectType and compatible containers.
            rep_list (list): available container list.
        Returns:
            str: new selected container type, if no suitable container is found, return None.
        """
        obj_type = obj['objectType']
        compatible_containers = []
        for match in pickup_rep_match:
            if obj_type in match:
                compatible_containers = match[obj_type]
                break
        obj_rep_type="" 
        if obj['parentReceptacles']:
            for obj_repid in obj['parentReceptacles']:
                obj_rep_type=obj_repid.split('|')[0]
                for container in compatible_containers:
                    compatible_containers = [container for container in compatible_containers if container != obj_rep_type]
        # obj_rep_rep_type="" 
        # if obj_rep['parentReceptacles']:
        #     for obj_rep_repid in obj_rep['parentReceptacles']:
        #         obj_rep_rep_type=obj_rep_repid.split('|')[0]
        #         for container in compatible_containers:           
        #             print("0",obj_rep_rep_type)
        #             if obj_rep_rep_type in compatible_containers:
        #                 print('obj_rep_rep_type',obj_rep_rep_type)
        #                 compatible_containers.remove(obj_rep_rep_type)
        
        # print("3",compatible_containers)           
                                        
        compatible_containers = list(set(compatible_containers))   
        valid_containers = []                
        for container in compatible_containers:
            if container!=obj_rep['objectType'] and container in rep_list:
                if obj_rep.get('parentReceptacles'):
                    parent_receptacle_types = [parent.split('|')[0] for parent in obj_rep['parentReceptacles']]
                    if container not in parent_receptacle_types:
                        valid_containers.append(container)
                else:
                    valid_containers.append(container)
        for valid_container in valid_containers:
            valid_container_obj = next((obj for obj in self.metadata["objects"] if obj["objectType"] == valid_container), None)
            if valid_container_obj and valid_container_obj['parentReceptacles']:
                for rep in valid_container_obj['parentReceptacles']:
                    for o in self.metadata["objects"]:
                        if o["objectId"]==rep and o['openable']==True and valid_container in valid_containers:
                            valid_containers.remove(valid_container)
        for valid_container in valid_containers:
            valid_container_obj = next((obj for obj in self.metadata["objects"] if obj["objectType"] == valid_container), None)
            if valid_container_obj and valid_container_obj['parentReceptacles']:
                for obj_id in valid_container_obj['parentReceptacles']:
                    obj_type = obj_id.split('|')[0]
                    if obj_type==obj_rep['objectType']:
                        valid_containers.remove(valid_container)
        if valid_containers:
            selected_container = random.choice(valid_containers)
            selected_metadata_obj = next((obj for obj in self.metadata["objects"] if obj["objectType"] == selected_container), None)
            if selected_metadata_obj and selected_metadata_obj["openable"] == True and selected_metadata_obj["isOpen"] == False:
                is_openable = '1'
            else:
                is_openable = '0'
            return selected_container, is_openable
        else:
            return None, None
            

    def ordered_pickup_two_object_and_put(self,room_type,num=1):
        """
        tasktype: composite
        subtasktype: Sequential Object Transfer
        
        Place objectA into container1, and place objectB into container2
		objectA and objectB are placed on another container
        First, place objectA into container1, then place objectB into container2
        """
        metadata=self.metadata
        objects=metadata["objects"]
        metadatapath=self.metadata_path

        kitchens_pickup_list=[
            'Apple','Bowl','Bread','ButterKnife',
            'Cup','DishSponge','Egg','Fork','Knife',
            'Lettuce','Mug','Pan','PepperShaker','Plate',
            'Pot','Potato','SaltShaker','SoapBottle','Spatula',
            'Spoon','Tomato'
        ]
        kitchens_pickup_rep_match=[
            {'Apple':['Pot', 'Pan', 'Bowl', 'Microwave', 'Fridge', 'Plate', 'SinkBasin', 'CounterTop', 'GarbageCan']},
            {'Bowl': ['Microwave', 'Fridge', 'SinkBasin', 'CounterTop', 'GarbageCan', 'Plate']},
            {'Bread': ['Pan', 'Microwave', 'Fridge', 'Plate', 'CounterTop', 'GarbageCan']},
            {'ButterKnife': ['Pot', 'Pan', 'Plate', 'SinkBasin', 'CounterTop', 'GarbageCan']},
            {'Cup': ['Microwave', 'Fridge', 'SinkBasin', 'CounterTop', 'GarbageCan']},
            {'DishSponge': ['Pot', 'Pan', 'Bowl', 'SinkBasin', 'CounterTop', 'GarbageCan']},
            {'Egg': ['Pot', 'Pan', 'Bowl', 'Microwave', 'Fridge', 'Plate', 'SinkBasin', 'CounterTop', 'GarbageCan']},
            {'Fork': ['Pot', 'Pan',  'SinkBasin', 'CounterTop']},
            {'Knife': ['Pot', 'Pan',  'SinkBasin', 'CounterTop']},
            {'Lettuce': ['SinkBasin', 'CounterTop', 'GarbageCan']},
            {'Mug': ['SinkBasin', 'CounterTop']},
            {'Pan': ['CounterTop', 'SinkBasin', 'Cabinet', 'Fridge', 'Microwave']},
            {'PepperShaker': ['CounterTop', 'Cabinet']},
            {'Plate': [ 'SinkBasin', 'CounterTop', 'Cabinet', 'Fridge']},
            {'Pot': ['SinkBasin', 'CounterTop', 'Cabinet', 'Fridge', 'Microwave']},
            {'Potato': ['Pot', 'Pan', 'Bowl', 'Microwave', 'Fridge', 'Plate', 'SinkBasin', 'CounterTop', 'GarbageCan']},
            {'SaltShaker': ['CounterTop', 'Cabinet']},
            {'SoapBottle': ['SinkBasin', 'CounterTop', 'Cabinet']},
            {'Spatula': ['Pot', 'Pan',  'Plate', 'SinkBasin', 'CounterTop']},
            {'Spoon': ['Pot', 'Pan', 'Plate', 'SinkBasin', 'CounterTop']},
            {'Tomato': ['Pot', 'Pan', 'Bowl', 'Plate', 'SinkBasin', 'CounterTop', 'GarbageCan', 'Fridge']}        
        ]
        kitchens_rep_list=[
            'Bowl','CounterTop',
            'GarbageCan','Pan','Plate',
            'Pot','SinkBasin',
            'Cabinet','Fridge','Microwave'
        ]
        
        living_rooms_pickup_list = [
            'Book','Bowl',
            'CellPhone',
            'CreditCard', 'KeyChain', 'Laptop',
            'Newspaper','Pen','Pencil',
            'Pillow','Plate','RemoteControl',
            'TissueBox','Vase',
            'Watch'
        ]
        living_rooms_pickup_rep_match = [
            {'Book': ['Sofa', 'ArmChair', 'Box', 'Dresser', 'Desk', 'Bed', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']},
            {'Bowl': ['Microwave', 'Fridge', 'Dresser', 'Desk', 'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']},
            {'Box': ['Sofa', 'ArmChair', 'Dresser', 'Desk', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Ottoman']},
            {'CellPhone': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'Safe']},
            {'CreditCard': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer']},
            {'KeyChain': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'Safe']},
            {'Laptop': ['Sofa', 'ArmChair', 'Ottoman', 'Desk', 'Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop']},
            {'Newspaper': ['Sofa', 'ArmChair', 'Ottoman', 'Dresser', 'Desk', 'Bed', 'Toilet', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'Pen': ['Mug', 'Box', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'Pencil': ['Mug', 'Box', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'Pillow': ['Sofa', 'ArmChair', 'Ottoman', 'Bed']},
            {'Plate': ['Microwave', 'Fridge', 'Dresser', 'Desk', 'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']},
            {'RemoteControl': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer']},
            {'TissueBox': ['Box', 'Dresser', 'Desk', 'Toilet', 'Cart', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'GarbageCan']},
            {'Vase': ['Box', 'Dresser', 'Desk', 'Cart', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Safe']},
            {'Watch': ['Box', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'Safe']},
            {'WateringCan': ['Desk', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']}
        ]
        living_rooms_rep_list=[
           'ArmChair', 'Bowl','Box',
            'Cabinet','CoffeeTable','Desk',
            'DiningTable','Drawer','Dresser',
            'GarbageCan','Plate',
            'Safe','Sofa',
            'TVStand'
        ]
        
        bedrooms_pickup_list = [
            'AlarmClock', 'BaseballBat', 'BasketBall',
            'Book', 'Bowl',
            'Box', 'CellPhone', 'Cloth',
            'CreditCard', 'KeyChain',
            'Laptop', 'Mug', 'Pen',
            'Pencil', 'Pillow', 'RemoteControl',
            'Statue', 'TeddyBear',
            'TennisRacket', 'TissueBox', 'Vase'
        ]
        bedrooms_pickup_rep_match = [
            {'AlarmClock': ['Box', 'Dresser', 'Desk', 'SideTable', 'DiningTable', 'TVStand', 'CoffeeTable', 'CounterTop', 'Shelf']},
            {'BaseballBat': ['Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'Desk', 'CounterTop']},
            {'BasketBall': ['Sofa', 'ArmChair', 'Dresser', 'Desk', 'Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop']},
            {'Book': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'Bed', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']},
            {'Bowl': ['Microwave', 'Fridge', 'Dresser', 'Desk',  'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']},
            {'Box': ['Sofa', 'ArmChair', 'Cabinet', 'DiningTable', 'CounterTop']},
            {'CellPhone': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'Safe']},
            {'Cloth': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'LaundryHamper', 'Desk', 'Toilet', 'Cart', 'BathtubBasin', 'Bathtub',  'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'CreditCard': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'Safe']},
            {'KeyChain': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'Safe']},
            {'Laptop': ['Sofa', 'ArmChair', 'Ottoman', 'Dresser', 'Desk', 'Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop']},
            {'Mug': ['SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf']},
            {'Pen': ['Mug', 'Box', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'Pencil': ['Mug', 'Box', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'Pillow': ['Sofa', 'ArmChair', 'Bed']},
            {'RemoteControl': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'Desk', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer']},
            {'Statue': ['Box', 'Dresser', 'Desk', 'Cart', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Safe']},
            {'TeddyBear': ['Bed', 'Sofa', 'ArmChair', 'Desk', 'DiningTable', 'CoffeeTable', 'SideTable', 'CounterTop', 'Safe']},
            {'TennisRacket': ['Desk', 'Bed', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop']},
            {'TissueBox': ['Box', 'Dresser', 'Desk', 'Toilet', 'Cart', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf',  'GarbageCan']},
            {'Vase': ['Box', 'Dresser', 'Desk', 'Cart', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Safe']}
        ]
        bedrooms_rep_list = [
            'ArmChair', 'Bed', 'Bowl',
            'Box', 'Cabinet', 'CoffeeTable',
            'CounterTop', 'Desk', 'Drawer',
            'Dresser', 'GarbageCan', 'LaundryHamper',
            'Mug', 'Safe', 'Shelf',
            'SideTable', 'Sofa'
        ]

        bathrooms_pickup_list = [
            'Cloth', 'DishSponge', 'HandTowel',
            'Plunger', 'ScrubBrush',
            'SoapBar', 'SoapBottle', 'SprayBottle',
            'TissueBox', 'ToiletPaper', 'Towel'
        ]
        bathrooms_pickup_rep_match = [
            {'Cloth': ['Sofa', 'ArmChair', 'Box', 'Ottoman', 'Dresser', 'LaundryHamper', 'Desk', 'Toilet', 'Cart', 'BathtubBasin', 'Bathtub', 'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'DishSponge': ['Pot', 'Pan', 'Bowl', 'Plate', 'Box', 'Toilet', 'Cart', 'BathtubBasin', 'Bathtub',  'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'HandTowel': ['HandTowelHolder']},
            {'Plunger': ['Cabinet']},
            {'ScrubBrush': ['Toilet', 'Cart', 'Bathtub', 'BathtubBasin',  'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'SoapBar': ['Toilet', 'Cart', 'Bathtub', 'BathtubBasin', 'SinkBasin', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'SoapBottle': ['Dresser', 'Desk', 'Toilet', 'Cart', 'Bathtub',  'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'SprayBottle': ['Dresser', 'Desk', 'Toilet', 'Cart', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'TissueBox': ['Box', 'Dresser', 'Desk', 'Toilet', 'Cart', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'ToiletPaper': ['Dresser', 'Desk', 'Toilet', 'ToiletPaperHanger', 'Cart', 'Bathtub', 'Cabinet', 'DiningTable', 'TVStand', 'CoffeeTable', 'SideTable', 'CounterTop', 'Shelf', 'Drawer', 'GarbageCan']},
            {'Towel': ['TowelHolder']}
        ]
        bathrooms_rep_list = [
            'BathtubBasin', 'Cabinet',
            'CounterTop', 'Drawer', 'Dresser',
            'GarbageCan', 'HandTowelHolder', 'Shelf',
            'SideTable', 'SinkBasin',
            'Toilet', 'ToiletPaperHanger', 'TowelHolder'
        ]

        if room_type=="kitchens":
            pickup_list=kitchens_pickup_list
            pickup_rep_match=kitchens_pickup_rep_match
            rep_list=kitchens_rep_list
        elif room_type=="living_rooms":
            pickup_list=living_rooms_pickup_list
            pickup_rep_match=living_rooms_pickup_rep_match
            rep_list=living_rooms_rep_list
        elif room_type=="bedrooms":
            pickup_list=bedrooms_pickup_list
            pickup_rep_match=bedrooms_pickup_rep_match
            rep_list=bedrooms_rep_list
        elif room_type=="bathrooms":
            pickup_list=bathrooms_pickup_list
            pickup_rep_match=bathrooms_pickup_rep_match
            rep_list=bathrooms_rep_list
            
        reward=0
        generate_task=[]
        task_type="ordered_pickup_two_object_and_put"
        task_name=""
        generate_task_path=""
        updated_actions=[]

        for objtype in pickup_list:
            task_name=""
            task_type="ordered_pickup_two_object_and_put"
            if len(generate_task) >= num:
                return 
            if self.check_object_type_uniqueness(objtype)==True:                
                objA = None
                objA_rep = None
                objA_putrep = None
                objB = None
                objB_rep = None
                objB_putrep = None
                objBtype = None
                for obj in objects:
                    if obj['objectType']==objtype:
                        if obj['parentReceptacles'] is not None and not any(item.startswith('Floor') for item in obj['parentReceptacles']):
                            objA=obj
                            objA_repid=obj['parentReceptacles'][-1] 
                if objA is None:
                    reward=0
                    task_name=""
                    updated_actions=[]
                    continue
                for obj in objects: 
                    if obj['objectId']== objA_repid:
                        objA_rep=obj        
                if objA_rep['openable']==False:
                    task_type=task_type+'0'      
                    if objA_rep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objA_rep['parentReceptacles']):
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":objA_rep['objectId'],
                            "objectType":objA_rep['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep['objectId'],objA['objectId']]
                        })
                        reward=reward+1
                        
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":objA['objectId'],
                            "objectType":objA['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA['objectId']]
                        })
                        reward=reward+1
  
                    elif objA_rep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objA_rep['parentReceptacles']):
                        objA_rep_repid=objA_rep['parentReceptacles'][-1]
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":objA_rep_repid,
                            "objectType":objA_rep_repid.split('|')[0],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep_repid,objA_rep['objectId']]
                        })
                        reward=reward+1

                        updated_actions.append({
                            "action":"pickup",
                            "objectId":objA['objectId'],
                            "objectType":objA['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA['objectId']]
                        })
                        reward=reward+1        
                       
                elif objA_rep['openable']==True and objA_rep['isOpen']==False:
                    task_type=task_type+'1'    
                    if objA_rep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objA_rep['parentReceptacles']):
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":objA_rep['objectId'],
                            "objectType":objA_rep['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep['objectId']]
                        })
                        reward=reward+1
                        
                        updated_actions.append({
                            "action":"open",
                            "objectId":objA_rep['objectId'],
                            "objectType":objA_rep['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep['objectId']]
                        })
                        reward=reward+1
                        
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":objA['objectId'],
                            "objectType":objA['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA['objectId']]
                        })
                        reward=reward+1  
                        
                        updated_actions.append({
                            "action":"close",
                            "objectId":objA_rep['objectId'],
                            "objectType":objA_rep['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep['objectId']]
                        })
                        reward=reward+1
 
                    elif objA_rep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objA_rep['parentReceptacles']):
                        objA_rep_repid=objA_rep['parentReceptacles'][-1]
                        
                        updated_actions.append({
                            "action":"navigate to",
                            "objectId":objA_rep_repid,
                            "objectType":objA_rep_repid.split('|')[0],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep_repid,objA_rep['objectId']]
                        })
                        reward=reward+1
                        
                        updated_actions.append({
                            "action":"open",
                            "objectId":objA_rep['objectId'],
                            "objectType":objA_rep['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep['objectId']]
                        })
                        reward=reward+1
                        
                        updated_actions.append({
                            "action":"pickup",
                            "objectId":objA['objectId'],
                            "objectType":objA['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA['objectId']]
                        })
                        reward=reward+1  
                        
                        updated_actions.append({
                            "action":"close",
                            "objectId":objA_rep['objectId'],
                            "objectType":objA_rep['objectType'],
                            "baseaction":"",
                            "reward":1,
                            "relatedObject":[objA_rep['objectId']]
                        })
                        reward=reward+1

                
                # Select a new container for objA to be placed in
                objA_putrep_type, is_openable=self.select_new_container(objA, objA_rep, pickup_rep_match, rep_list)
                if objA_putrep_type is None:
                    reward=0
                    task_name=""
                    updated_actions=[]
                    continue
                    
                elif objA_putrep_type is not None:
                    for obj in objects:
                        if obj["objectType"]==objA_putrep_type:
                            objA_putrep=obj
                    
                    if objA_putrep is None:
                        reward=0
                        task_name=""
                        updated_actions=[]
                        continue

                    if is_openable=='0':
                        task_type=task_type+'0'      
                        if objA_putrep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objA_putrep['parentReceptacles']):
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1

                            updated_actions.append({
                                "action":"put",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1   
                            
                        if objA_putrep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objA_putrep['parentReceptacles']):
                            objA_putrep_repid=objA_putrep['parentReceptacles'][-1]
                            
                            for obj in objects:
                                if obj['objectId']==objA_putrep_repid:
                                    objA_putrep_rep=obj
                                    
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objA_putrep_rep['objectId'],
                                "objectType":objA_putrep_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep_rep['objectId'],objA_putrep['objectId']]
                            })
                            reward=reward+1

                            updated_actions.append({
                                "action":"put",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1                                                

                    elif is_openable=='1':
                        task_type=task_type+'1'
                        if objA_putrep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objA_putrep['parentReceptacles']):
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1
    
                            updated_actions.append({
                                "action":"open",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1

                            updated_actions.append({
                                "action":"put",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1
    
                            updated_actions.append({
                                "action":"close",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
    
                            reward=reward+1  
            
                        if objA_putrep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objA_putrep['parentReceptacles']):
                            objA_putrep_repid=objA_putrep['parentReceptacles'][-1]
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objA_putrep_repid,
                                "objectType":objA_putrep_repid.split('|')[0],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep_repid]
                            })
                            reward=reward+1
    
                            updated_actions.append({
                                "action":"open",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1

                            updated_actions.append({
                                "action":"put",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
                            reward=reward+1
    
                            updated_actions.append({
                                "action":"close",
                                "objectId":objA_putrep['objectId'],
                                "objectType":objA_putrep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objA_putrep['objectId']]
                            })
    
                            reward=reward+1                                               

                    task_name+=f"First, place {objA['objectType']} on {objA_putrep['objectType']}, "
                    
                pickup_list.remove(objA['objectType'])  
                unique_list=[]
                for obj in pickup_list:
                    if obj!=objA['objectType']:
                        if self.check_object_type_uniqueness(obj)==True:
                            unique_list.append(obj)
                
                if objA['objectType'] in rep_list:
                    rep_list.remove(objA['objectType'])
        
                if not unique_list:
                    reward=0
                    task_name=""
                    updated_actions=[]
                    continue
                  
                else:
                    objBtype=random.choice(unique_list)   
                    for obj in objects:
                        if obj['objectType']==objBtype:
                            if obj['parentReceptacles'] is not None and not any(item.startswith('Floor') for item in obj['parentReceptacles']):
                                objB=obj
                                objB_repid=obj['parentReceptacles'][-1]  
                                
                    if objB is None:
                        reward=0
                        task_name=""
                        updated_actions=[]
                        continue
                    for obj in objects: 
                        if obj['objectId']== objB_repid:
                            objB_rep=obj 
                                  
                    if objB_rep['openable']==False:
                        task_type=task_type+'0'     
                        if objB_rep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objB_rep['parentReceptacles']):
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objB_rep['objectId'],
                                "objectType":objB_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep['objectId'],objB['objectId']]
                            })
                            reward=reward+1

                            updated_actions.append({
                                "action":"pickup",
                                "objectId":objB['objectId'],
                                "objectType":objB['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB['objectId']]
                            })
                            reward=reward+1 
                        elif objB_rep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objB_rep['parentReceptacles']):
                            objB_rep_repid=objB_rep['parentReceptacles'][-1]
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objB_rep_repid,
                                "objectType":objB_rep_repid.split('|')[0],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep_repid,objB_rep['objectId']]
                            })
                            reward=reward+1

                            updated_actions.append({
                                "action":"pickup",
                                "objectId":objB['objectId'],
                                "objectType":objB['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB['objectId']]
                            })
                            reward=reward+1        
                          
                    elif objB_rep['openable']==True and objB_rep['isOpen']==False:
                        task_type=task_type+'1'       
                        if objB_rep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objB_rep['parentReceptacles']):
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objB_rep['objectId'],
                                "objectType":objB_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep['objectId']]
                            })
                            reward=reward+1
                            
                            updated_actions.append({
                                "action":"open",
                                "objectId":objB_rep['objectId'],
                                "objectType":objB_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep['objectId']]
                            })
                            reward=reward+1
                            
                            updated_actions.append({
                                "action":"pickup",
                                "objectId":objB['objectId'],
                                "objectType":objB['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB['objectId']]
                            })
                            reward=reward+1  
                            
                            updated_actions.append({
                                "action":"close",
                                "objectId":objB_rep['objectId'],
                                "objectType":objB_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep['objectId']]
                            })
                            reward=reward+1
                            
                        elif objB_rep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objB_rep['parentReceptacles']):
                            objB_rep_repid=objB_rep['parentReceptacles'][-1]
                            
                            updated_actions.append({
                                "action":"navigate to",
                                "objectId":objB_rep_repid,
                                "objectType":objB_rep_repid.split('|')[0],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep_repid,objB_rep['objectId']]
                            })
                            reward=reward+1
                            
                            updated_actions.append({
                                "action":"open",
                                "objectId":objB_rep['objectId'],
                                "objectType":objB_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep['objectId']]
                            })
                            reward=reward+1
                            
                            updated_actions.append({
                                "action":"pickup",
                                "objectId":objB['objectId'],
                                "objectType":objB['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB['objectId']]
                            })
                            reward=reward+1  
                            
                            updated_actions.append({
                                "action":"close",
                                "objectId":objB_rep['objectId'],
                                "objectType":objB_rep['objectType'],
                                "baseaction":"",
                                "reward":1,
                                "relatedObject":[objB_rep['objectId']]
                            })
                            reward=reward+1
                            
                    objB_putrep_type, is_openable=self.select_new_container(objB, objB_rep, pickup_rep_match, rep_list)
                    
                    if objB_putrep_type is None:
                        reward=0
                        task_name=""
                        updated_actions=[]
                        continue
                        
                    elif objB_putrep_type is not None:
                        for obj in objects:
                            if obj["objectType"]==objB_putrep_type:
                                objB_putrep=obj
                        
                        if objB_putrep is None:
                            reward=0
                            task_name=""
                            updated_actions=[]
                            continue

                        if is_openable=='0':
                            task_type=task_type+'0'      
                            if objB_putrep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objB_putrep['parentReceptacles']):
                                updated_actions.append({
                                    "action":"navigate to",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1

                                updated_actions.append({
                                    "action":"put",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1   

                            if objB_putrep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objB_putrep['parentReceptacles']):
                                objB_putrep_repid=objB_putrep['parentReceptacles'][-1]
                                
                                for obj in objects:
                                    if obj['objectId']==objB_putrep_repid:
                                        objB_putrep_rep=obj
                                        
                                updated_actions.append({
                                    "action":"navigate to",
                                    "objectId":objB_putrep_rep['objectId'],
                                    "objectType":objB_putrep_rep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep_rep['objectId'],objB_putrep['objectId']]
                                })
                                reward=reward+1

                                updated_actions.append({
                                    "action":"put",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1                                                

                        elif is_openable=='1':
                            task_type=task_type+'1'

                            if objB_putrep['parentReceptacles'] is None or any(rep.startswith("Floor") for rep in objB_putrep['parentReceptacles']):
                                updated_actions.append({
                                    "action":"navigate to",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1
        
                                updated_actions.append({
                                    "action":"open",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1

                                updated_actions.append({
                                    "action":"put",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1
                                
                            if objB_putrep['parentReceptacles'] is not None and not any(rep.startswith("Floor") for rep in objB_putrep['parentReceptacles']):
                                objB_putrep_repid=objB_putrep['parentReceptacles'][-1]
                                updated_actions.append({
                                    "action":"navigate to",
                                    "objectId":objB_putrep_repid,
                                    "objectType":objB_putrep_repid.split('|')[0],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep_repid]
                                })
                                reward=reward+1
        
                                updated_actions.append({
                                    "action":"open",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1

                                updated_actions.append({
                                    "action":"put",
                                    "objectId":objB_putrep['objectId'],
                                    "objectType":objB_putrep['objectType'],
                                    "baseaction":"",
                                    "reward":1,
                                    "relatedObject":[objB_putrep['objectId']]
                                })
                                reward=reward+1

                        task_name+=f"then, place {objB['objectType']} on {objB_putrep['objectType']}. "

                updated_actions.append({
                    "action":"end",
                    "objectId":"",
                    "objectType":"",
                    "baseaction":"",
                    "reward":1,
                    "relatedObject":[]
                    }
                )
                reward=reward+1

                task = {
                    "taskname": task_name,
                    "tasktype": task_type,
                    "metadatapath": metadatapath,
                    "actions": updated_actions,
                    "totalreward":reward,
                }
                generate_task_path=f"ordered/{task_type}_task_metadata/{scene}.json"
                save_data_to_json(task,generate_task_path)           
                reward=0
                generate_task.append(task)
                updated_actions=[]
                task_type="ordered_pickup_two_object_and_put"
                task_name=""  
            else:
                reward=0
                task_type=""
                task_name=""
                updated_actions=[]
                continue
        return
    
    
def collect_metadata():
    """
    get scene metadata from AI2THOR
    """
    room_type = ['kitchens','living_rooms','bedrooms','bathrooms']
    for room in room_type:
        if room == 'kitchens':
            floorplans = [f"FloorPlan{i}" for i in range(1, 31)]
        elif room == 'living_rooms':
            floorplans = [f"FloorPlan{200 + i}" for i in range(1, 31)]
        elif room == 'bedrooms':
            floorplans = [f"FloorPlan{300 + i}" for i in range(1, 31)]
        elif room == 'bathrooms':
            floorplans = [f"FloorPlan{400 + i}" for i in range(1, 31)]
        
        for scene in floorplans: 
            metadata_path=f"taskgenerate/{room}/{scene}/metadata.json"
            get_scene_metadata(scene,metadata_path)         
        

if __name__ == "__main__":
    ###### step1. get the metadata of 120 scenes from ai2thor ####################
    #### save in the taskgenerate/
    # collect_metadata()
    
    ###### step1. choose a task type from task_types #############################
    task_types=[
        "single_search",                            # tasktype: search subtasktype: Exposed Object Search
        "single_search_from_closerep",              # tasktype: search subtasktype: Enclosed Object Search
        "single_pickup",                            # tasktype: manipulate subtasktype: Exposed Object Grasping
        "single_pickup_from_closerep",              # tasktype: manipulate subtasktype: Enclosed Object Grasping
        "single_toggle",                            # tasktype: manipulate subtasktype: Exposed Object Toggle
        "pickup_and_put",                           # tasktype: transport subtasktype: Exposed-to-Exposed Object Transfer
        "pickup_and_put_in_closerep",               # tasktype: transport subtasktype: Exposed-to-Enclosed Object Transfer
        "pickup_from_closerep_and_put",             # tasktype: transport subtasktype: Enclosed-to-Exposed Object Transfer
        "pickup_from_closerep_and_put_in_closerep", # tasktype: transport subtasktype: Enclosed-to-Enclosed Object Transfer
        "ordered_pickup_two_object_and_put"         # tasktype: composite subtasktype: Sequential Object Transfer
    ]
    # task_type="single_search"
    task_type="pickup_and_put"
    
    ##### step2. set the number of tasks to generate for each scene #############
    num=1
    
    room_type = ['kitchens','living_rooms','bedrooms','bathrooms']
    for room in room_type: 
        if room == 'kitchens':
            floorplans = [f"FloorPlan{i}" for i in range(1,31) if i!=8]
        elif room == 'living_rooms':
            floorplans = [f"FloorPlan{200 + i}" for i in range(1,31)]
        elif room == 'bedrooms':
            floorplans = [f"FloorPlan{300 + i}" for i in range(1,31)]
        elif room == 'bathrooms':
            floorplans = [f"FloorPlan{400 + i}" for i in range(1,31)]

        for scene in floorplans:  
            
            metadata_path=f"taskgenerate/{room}/{scene}/metadata.json"
            print(metadata_path)
            metadata=load_json(metadata_path)
            metadata=metadata[0]
            generate_task_path=f"{task_type}_task_metadata/{scene}.json"
            if task_type=="ordered_pickup_two_object_and_put":
                generate_task_path=f"ordered/{task_type}_task_metadata/{scene}.json"
            taskgenerate=TaskGenerate(metadata,generate_task_path,metadata_path)

            if task_type=="single_search":
                taskgenerate.single_search(num)
            elif task_type=="single_search_from_closerep":
                taskgenerate.single_search_from_closerep(num)
            elif task_type=="single_pickup":
                taskgenerate.single_pickup(num)
            elif task_type=="single_pickup_from_closerep":
                taskgenerate.single_pickup_from_closerep(num)
            elif task_type=="single_toggle":
                taskgenerate.single_toggle(num)
            elif task_type=="pickup_and_put":
                taskgenerate.pickup_and_put(num)
            elif task_type=="pickup_and_put_in_closerep":
                taskgenerate.pickup_and_put_in_closerep(num)
            elif task_type=="pickup_from_closerep_and_put":
                taskgenerate.pickup_from_closerep_and_put(num)
            elif task_type=="pickup_from_closerep_and_put_in_closerep":
                taskgenerate.pickup_from_closerep_and_put_in_closerep(num)
            elif task_type=="ordered_pickup_two_object_and_put":
                taskgenerate.ordered_pickup_two_object_and_put(room,num)