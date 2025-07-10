from ai2thor.controller import Controller
import random
import math
import re
import time
import threading
import copy
from PIL import Image
from vlmCall import VLMAPI
from utils import save_data_to_json,save_image,clear_folder,load_json,get_volume_distance_rate

from baseAction import BaseAction
from RocAgent import RocAgent

   
modes=['test','generate']
mode=modes[0]


max_round=5

class O1StyleGenerate_ordered:
    """
    For a scene, generate a basic image-thought-action trajectories for more complex ordered task.
    """
    def __init__(
                self,
                controller,
                scene,
                origin_path,                        # {env}/{room}/{scene}
                metadata,
                task,                               # task from TaskGenerate
                round = 1,                          # current round
                model = "gpt-4o-2024-11-20"
                 ):

        self.plan_objects_list=[]          
        self.wrong_time=0
        self.his_objects_list=[]          
        self.navigable_list=[]              
        self.metadata=metadata
        self.task=task     
        self.subtask1 = ""
        self.subtask2 = ""
        self.current_subtask=""
        self.model=model
        self.generate_o1style_data={
            "scene":"",
            "tasktype":"",
            "instruction_idx":"",
            "taskname":self.task["taskname"],
            "trajectory":[],
            "images":[],
            # "round_metadata":[],
            "flag":"",
            "time":0,
            # "task_metadata":{},
            # "round_navigable_list":[]
            }      

        self.current_action={}             
        self.next_action={}        
        
        self.rocAgent=RocAgent(controller)           
        self.controller=controller
        self.reward=0                      
        self.round=round                  
        
        self.baseAction=BaseAction()

        self.origin_path=origin_path                 
        self.scene=scene
        self.current_object=""                      
        return
    
    
    def initial_navigable_list(self):
        self.metadata=self.controller.last_event.metadata
        list=get_volume_distance_rate(self.metadata)
        for item in list:
            if item["isnavigable"] and item["objectType"]!="Floor":
                objectType=item["objectType"]
                objectId=item["objectId"]
                visibleTimes=1
                choseTimes=0
                obj_navigable={
                    "objectType":objectType,
                    "objectId":objectId,
                    "visibleTimes":visibleTimes,
                    "choseTimes":choseTimes
                }
                self.navigable_list.append(obj_navigable)
        
        # path=f"nvrecord/{self.origin_path}/initial_navigable_list.json"
        # save_data_to_json(self.navigable_list,path)
        return  
    
    def update_navigable_list_vtime(self):
        self.metadata=self.controller.last_event.metadata
        list = get_volume_distance_rate(self.metadata)
        for item in list:
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
                                
        # print("update",self.navigable_list)
        # path=f"nvrecord/{self.origin_path}/update_navigable_list.json"
        # save_data_to_json(self.navigable_list,path)
        return self.navigable_list
      
           
    def generate_selfObs(self,image_path):
        print("\n****** begin generate selfobservation ******")
        navigable_categories=self.get_object_types_from_navigable_list()
        print("round:",self.round-1," ",navigable_categories)
        systext=f"""
        You are a mobile robot located in a room. Your task is to describe the visible objects in front of you, based on the current view.
        """
        usertext=f""""
        Please observe the image, briefly describe the main visible objects in the room and their spatial relationships.
        Only include objects from the following categories: {navigable_categories}.
        Note: Only describe objects from the provided categories, do not include others.
        Avoid mentioning the number of objects.
        Ensure the description is in the first person and remains concise, within 100 words.
        Follow the format: <Observation> ...... </Observation>
        """
        llmapi=VLMAPI(self.model)
        selfobservation=llmapi.vlm_request(systext,usertext,image_path)
        self.generate_o1style_data["trajectory"].append(selfobservation)
        self.generate_o1style_data["images"].append(image_path)
        print("****** end generate selfobservation ******\n")
        return selfobservation
    
    def check_objId_in_navigable_list(self, current_action):
        current_objectType = current_action["objectType"]
        current_objectId = current_action["objectId"]
        type_exists = False
        id_exists = False
        for obj in self.navigable_list:
            if obj["objectType"] == current_objectType:
                type_exists = True 
            if obj["objectId"] == current_objectId:
                id_exists = True 
        
        return type_exists, id_exists

    def choose_r1_posible_object(self,random_number,categories):
        if random_number==0:
            return []
        categories_t=categories
        remove_list=[]
        scene_number = int(scene[9:])
 
        if 201 <= scene_number <= 229:
            remove_list.append("Shelf")  
  
        for obj in self.metadata['objects']:
            if obj['receptacle']==False:
                remove_list.append(obj["objectType"])
                
        for item in remove_list:
            if item in categories_t:
                categories_t.remove(item)  

        posible_list = set() 
        for objtype in categories_t:  
            print(objtype)
            if self.current_action["relatedObject"] is not None and len(self.current_action["relatedObject"])>1 and objtype==self.current_action["relatedObject"][-1].split('|')[0]:
                continue
            for obj in self.metadata["objects"]:
                if objtype == obj["objectType"] and obj["receptacle"] == True:  
                    pRs = obj["parentReceptacles"]
                    if pRs is None:
                        posible_list.add(objtype)
                    elif len(pRs) != 0:
                        for pR in pRs:
                            if pR.split('|')[0] == "Floor":
                                posible_list.add(objtype)

        if posible_list is not None:
            if len(posible_list)>=random_number:
                random_number=random_number
            elif len(posible_list)<random_number:
                random_number=len(posible_list)
                
        systext = f"""You are a mobile robot located in a room. Your task is {self.task['taskname']}. """
        
        if self.current_subtask!="":
            systext+=f" At this stage, your current subtask is: {self.current_subtask}."
            
        systext+=f"Based on the task requirements, the objects you need to find now are: {self.current_action['relatedObject'][-1].split('|')[0]}"

        usertext = f"""Please select the most likely locations for {random_number} objects from the provided categories. These objects should be most relevant to the current task.
        Categories: {posible_list}
        Make sure to select only from the provided categories, and ensure no objects outside the categories appear in the output.
        Your response should be a list of {random_number} objects.
        Make sure the output is formatted as [...]"""
        llmapi=VLMAPI(self.model)
        posible_list=llmapi.vlm_request(systext,usertext)

        posible_list=posible_list.strip('[]')
        posible_list = posible_list.replace(" ", "")  
        posible_list = posible_list.replace("'", "") 
        posible_list = posible_list.replace('"', "")  
        posible_list=posible_list.split(',')
        print("posible_list",posible_list)
        
        return posible_list
       
    def choose_posible_object(self,categories):
        """
        """
        categories_t=categories
        remove_list=[]
        if self.scene=='FloorPlan201':
            remove_list.append("Shelf")
            if obj["openable"]==True:
                remove_list.append(obj["objectType"])
        his_list = [item['objectType'] for item in self.his_objects_list]
        his_list = list(set(his_list))
        items_to_remove = his_list + remove_list
        for item in items_to_remove:
            if item in categories_t:
                categories_t.remove(item)
                
        for obj in self.metadata["objects"]:
            if obj["objectId"]==self.current_action["objectId"]:
                posx=obj["axisAlignedBoundingBox"]["center"]["x"]
                posz=obj["axisAlignedBoundingBox"]["center"]["z"]
        
        distance_dict = {}

        for objtype in categories_t:
                for obj in self.metadata["objects"]:
                    if objtype == obj["objectType"] and obj["receptacle"] == True:
                        pRs = obj["parentReceptacles"]
                        if pRs is None:
                            distance = math.sqrt(
                                (posx - obj["axisAlignedBoundingBox"]["center"]["x"]) ** 2 +
                                (posz - obj["axisAlignedBoundingBox"]["center"]["z"]) ** 2
                            )
                            distance_dict[obj["objectId"]] = distance 

                        elif len(pRs) != 0:
                            for pR in pRs: 
                                if pR.split('|')[0] == "Floor":
                                    distance = math.sqrt(
                                        (posx - obj["axisAlignedBoundingBox"]["center"]["x"]) ** 2 +
                                        (posz - obj["axisAlignedBoundingBox"]["center"]["z"]) ** 2
                                    )
                                    distance_dict[obj["objectId"]] = distance 

        if distance_dict:
            farthest_object_id = min(distance_dict, key=distance_dict.get)
            farthest_object = next(obj for obj in self.metadata["objects"] if obj["objectId"] == farthest_object_id)
        return farthest_object
 
    def generate_r1_plan_thinking(self,selfobservation,current_image_path,think_plan_num,plan_num,correct_num):
        print("\n****** begin generate r1 plan, plan object num:",plan_num,"******")

        current_action=self.current_action  
        current_objectType=current_action["objectType"] 
        current_objectId=current_action["objectId"]

        navigable_categories=self.get_object_types_from_navigable_list()
        type_exists, id_exists=self.check_objId_in_navigable_list(current_action)
        if type_exists or id_exists:
            navigable_categories.remove(current_objectType)
            navigable_categories_without = navigable_categories
            if correct_num is not None:
                posible_list=self.choose_r1_posible_object(plan_num-1,navigable_categories_without)
            else:
                posible_list=self.choose_r1_posible_object(plan_num,navigable_categories_without)
            # print("r1_choice_possible_list",posible_list)
            if correct_num is not None:
                posible_list.insert(correct_num, current_objectType)
        
        elif type_exists and not id_exists:
            navigable_categories.remove(current_objectType)
            navigable_categories_without = navigable_categories
            posible_list=self.choose_r1_posible_object(plan_num,navigable_categories_without)
            # print("r1_final_choice_list",posible_list)
            
        elif not type_exists and not id_exists:
            navigable_categories_without=navigable_categories
            posible_list=self.choose_r1_posible_object(plan_num,navigable_categories_without)
            
        print("****** r1_init_plan_object_list: ",posible_list,"correct type:",current_objectType)    
        
        systext=f"You are a mobile robot located in a room. Your overall task is {self.task['taskname']}"
        # usertext_num=random.choice([1,2])
        if self.current_subtask!="":
            systext+=f" At this stage, your current subtask is: {self.current_subtask}."
        #### Planning
        usertext1=f"""To complete the task, you first observed the scene in the image: {selfobservation}, and based on your observation, you have determined the possible search order: {posible_list}.
        However, you need to supplement the thought process that led to determining the search order: <Planning>.
        In the <Planning> section, you need to briefly describe the overall task, then you need to supplement your thought process by combining the image with both the overall task and the current subtask, briefly describe your plan based on the order of {posible_list}.
        Note: The <Planning> should focus on the selection of search locations, not the methods or details of the search, and the objects to be found are placed on the surfaces of other containers.
        Note that the objects in the search order are either those you have seen before or those currently visible in the image.
        Ensure the description is in the first person, concise, and within 100 words.
        Ensure a smooth connection between the <Observation> and <Planning>sections.
        Output must follow the format: <Planning>...</Planning>
        """
        #### Thinking-Planning
        usertext2=f"""To complete the task, you first observed the scene in the image: {selfobservation}, and based on your observation, you have determined the possible search order: {posible_list}.
        However, you need to supplement the thought process that led to determining the search order: <Thinking> and <Planning>.
        In the <Thinking> section, first, you need to briefly describe overall task, then you need to supplement your thought process by combining the image with both the overall task and the current subtask.
        In the <Planning> section, you need to briefly describe your plan based on the order of {posible_list}.
        Note: The <Thinking> and <Planning> should focus on the selection of search locations, not the methods or details of the search, and the objects to be found are placed on the surfaces of other containers.
        Note that the objects in the search order are either those you have seen before or those currently visible in the image.
        Ensure the description is in the first person, concise, and within 150 words.
        Ensure a smooth connection between the <Observation>, <Thinking>, and <Planning> sections.
        Output must follow the format: <Thinking>...</Thinking>, <Planning>...</Planning>
        """

        if think_plan_num==1:usertext=usertext1 
        else: usertext=usertext2
        llmapi=VLMAPI(self.model)
        current_image_path=f"{current_image_path}"
        r1_plan=llmapi.vlm_request(systext,usertext,current_image_path)
        if think_plan_num==1:
            self.generate_o1style_data["trajectory"].append(r1_plan)
        else:             
            thinking_matches = re.findall(r'<Thinking>(.*?)</Thinking>', r1_plan,re.DOTALL)
            planning_matches = re.findall(r'<Planning>(.*?)</Planning>', r1_plan,re.DOTALL)
            thinking_str = thinking_matches[0] if thinking_matches else ''
            planning_str = planning_matches[0] if planning_matches else ''

            self.generate_o1style_data["trajectory"].append("<Thinking>"+thinking_str+"</Thinking>")
            self.generate_o1style_data["trajectory"].append("<Planning>"+planning_str+"</Planning>")
            # print(thinking_str,planning_str)
        # print(r1_plan)
        print("****** end generate r1 plan ******* \n")

        return posible_list
           
     
    def generate_thinking(self,last_targetobjId,feedback,image_path_1="",image_path_2="",image_path_3=""):
        print("********* start generate thinking",self.round,"********")        
        print("************ current plan object list:",self.plan_objects_list)
        
        systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
        
        if self.current_subtask!="":
            systext+=f" At this stage, your current subtask is: {self.current_subtask}."
        num=random.choice([1,2])
            
        if self.current_action["action"]=="navigate to":   
            decision_making=f"navigate to {self.plan_objects_list[0]}"
        elif self.current_action["action"] in  ["pickup","put","toggle","open","close","slice"]:
            decision_making=f"{self.current_action['action']} {self.current_action['objectType']}"
        elif self.current_action["action"] in ["observe","move forward","end"]:
            decision_making=f"{self.current_action['action']}"


        usertext1=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
        After completing the last action, you gained a new perspective, and the feedback is: {feedback}.
        You plan to take the next action as {decision_making}, but you need to provide a reasoning process that supports this decision. Ensure your reasoning aligns naturally with the observations and history without treating next action as a given.
        In the <Planning> section, first, you need to describe the image and think about the next plan, then, update the plan based on the pending search list {self.plan_objects_list}.
        Attention: Do not include any references to feedback or the pending search list {self.plan_objects_list} in your output. These elements are merely potential hints and should not be explicitly mentioned or referenced in your analysis. Your reasoning and plans must be based solely on observations and logical inference, ensuring that the outcomes naturally align with the feedback and pending search list.
        Note: The objects to be found are placed on the surfaces of other objects, and the <Planning> should focus on the selection of search locations, not the methods or details of the search. 
        Note that the objects and containers in the search list and next action are either those you have seen before or those currently visible in the image.
        The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
        The output should be limited to 100 words.
        Output must follow the format: <Planning>...</Planning>""" 
        
        usertext2=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
        After completing the last action, you gained a new perspective, and the feedback is: {feedback}.
        You plan to take the next action as {decision_making}, but you need to provide a reasoning process that supports this decision. Ensure your reasoning aligns naturally with the observations and history without treating next action as a given.
        In the <Thinking> section, base on your last plan, you need to describe the image and think about the next plan.
        In the <Planning> section, you need to combine the thinking with the pending search list {self.plan_objects_list} and provide a new plan description.
        Attention: Do not include any references to feedback or the pending search list {self.plan_objects_list} in your output. These elements are merely potential hints and should not be explicitly mentioned or referenced in your analysis. Your reasoning and plans must be based solely on observations and logical inference, ensuring that the outcomes naturally align with the feedback and pending search list.
        Note: The objects to be found are placed on the surfaces of other objects, and the <Thinking> and <Planning> should focus on the selection of search locations, not the methods or details of the search. 
        Note that the objects and containers in the search list and next action are either those you have seen before or those currently visible in the image.
        The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
        The output should be limited to 150 words.
        Output must follow the format: <Thinking>...</Thinking>, <Planning>...</Planning>"""    
        llmapi=VLMAPI(self.model)
        if num==1:usertext=usertext1
        else: usertext=usertext2
        thinking="<Thinking></Thinking>"
        if last_targetobjId!="":
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            thinking=llmapi.vlm_request(systext,usertext,image_path)
        elif image_path_1!="" and image_path_2!="":
            thinking=llmapi.vlm_request(systext,usertext,image_path_1,image_path_2,image_path_3)
        if num==1:
            self.generate_o1style_data["trajectory"].append(thinking)
        else:
            thinking_matches = re.findall(r'<Thinking>(.*?)</Thinking>', thinking,re.DOTALL)
            planning_matches = re.findall(r'<Planning>(.*?)</Planning>', thinking,re.DOTALL)
            thinking_str = thinking_matches[0] if thinking_matches else ''
            planning_str = planning_matches[0] if planning_matches else ''
            self.generate_o1style_data["trajectory"].append("<Thinking>"+thinking_str+"</Thinking>")
            self.generate_o1style_data["trajectory"].append("<Planning>"+planning_str+"</Planning>")
            # print(thinking_str,planning_str)
       
        decision_making_1="<DecisionMaking>"+decision_making+"</DecisionMaking>"
        self.generate_o1style_data["trajectory"].append(decision_making_1)
       
        return decision_making


    def consistent_check(self,content1,content2):
        systext=f"The user has provided a description of the task with two sentences. Your task is to analyze whether the two sentences are consistent in describing the task's success."
        usertext=f"Are the two sentences describing the task's execution success consistent? Sentence 1 is: \"{content1}\". Sentence 2 is: \"{content2}\" only output \"Yes\" or \"No\""
        llmapi=VLMAPI(self.model)
        consistent=llmapi.vlm_request(systext,usertext)
        print("verification consistent: ",consistent,'\n',content1,'\n',content2)
        if consistent=='No':
            self.generate_o1style_data["flag"]+="verify wrong"
        return
    
    def generate_thinking_verify(self,last_targetobjId,feedback):
        print("*************** start verification *****************")
        current_action=self.current_action 
        current_objectType=current_action["objectType"]
        current_objectId=current_action["objectId"]
        
        print(self.plan_objects_list)
        if self.task["tasktype"] in [
            "single_search",
            "single_toggle",
            "single_pickup",
            "single_search_from_closerep",
            "single_pickup_from_closerep",
            "search_and_slice",
            "pickup_and_put_in_closerep"
            ]:
            num = random.choices([0, 1, 2], weights=[1, 0, 0], k=1)[0]
        else:
            num = random.choices([0, 1, 2], weights=[0.4, 0.4, 0.2], k=1)[0]
        
        if num==0:
            feedback1="Your task seems to be completed."
            systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
            usertext=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
            After completing the last action, you gained a new perspective, and the feedback was {feedback1}.
            You need to consider the history of previous rounds and the current perspective to evaluate whether all subtasks have been completed and if the overall task is fully accomplished.           
            Note: feedback is a hint and must not be referenced in your response. However, ensure your description aligns with the feedback's outcome while reasoning through observations and history.
            Note: do not include descriptions like 'based on feedback' in the output.
            The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
            The output should be limited to 100 words.
            The output format must be: <Thinking>...</Thinking>"""    
            llmapi=VLMAPI(self.model)
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            thinking_verify=llmapi.vlm_request(systext,usertext,image_path)
            self.generate_o1style_data["trajectory"].append(thinking_verify)

        
        elif num==1:
            feedback1="Your subtask seems to be completed. You can move to change your perspective and observe again for confirmation."
            systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
            usertext=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
            After completing the last action, you gained a new perspective, and the feedback was {feedback1}. Based on the current perspective, you decided to re-observe for verification, but you need to elaborate on your thought process.
            In the <Verification> section, analyze the current perspective, combine it with the task history, think about whether the subtask has been completed, and describe your thought process for re-observing.           
            Note: feedback is a hint and must not be referenced in your response. However, ensure your description aligns with the feedback's outcome while reasoning through observations and history.
            Note: do not include descriptions like 'based on feedback' in the output.
            The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds. The output should be limited to 80 words.
            The output format must be: <Verification>...</Verification>"""    
            llmapi=VLMAPI(self.model)
            # print(usertext)
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            thinking_verify=llmapi.vlm_request(systext,usertext,image_path)
            # print(thinking_verify)
            self.generate_o1style_data["trajectory"].append(thinking_verify)
            
            
            decision="<DecisionMaking>move forward</DecisionMaking>"
            self.generate_o1style_data["trajectory"].append(decision)
            
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}_verify.png"
            if self.task["tasktype"] == ["pickup_and_put_in_closerep","single_search_from_closerep","ordered_pickup_two_object_and_put0001"]:
                image_path1=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
                self.crop_and_save(image_path1,image_path)
            else:
                self.rocAgent.move_forward(0.3)
                save_image(self.controller.last_event,image_path)
            
            self.generate_o1style_data["images"].append(image_path)
            self.save_metadata_navigable_list("_verify") 
            
            
            feedback1="Your overall task seems to be completed."
            systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
            usertext=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
            After completing the last action, you gained a new perspective, and the feedback was {feedback1}.
            You need to consider the history of previous rounds and the current perspective to evaluate whether all subtasks have been completed and if the overall task is fully accomplished.           
            Note: feedback is a hint and must not be referenced in your response. However, ensure your description aligns with the feedback's outcome while reasoning through observations and history.
            Note: do not include descriptions like 'based on feedback' in the output.
            The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
            The output should be limited to 100 words.
            The output format must be: <Thinking>...</Thinking>"""    
            llmapi=VLMAPI(self.model)
            # print(usertext)
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            thinking_verify=llmapi.vlm_request(systext,usertext,image_path)
            # print(thinking_verify)
            self.generate_o1style_data["trajectory"].append(thinking_verify)

        elif num==2:
            feedback1="Your subtask seems to be completed. You can move to change your perspective and observe again for confirmation."
            systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
            usertext=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
            After completing the last action, you gained a new perspective, and the feedback was {feedback1}.
            Based on the current perspective, you can re-observe for verification. 
            In the <Thinking> section, combine with the task history, analyze the current perspective and the current status of task execution.  
            In the <Verification> section, based on the task and Thinking, briefly describe your reasonning for re-observing.            
            Note: Feedback is a hint and must not be referenced in your response. However, ensure your description aligns with the feedback's outcome while reasoning through observations and history.
            Note: do not include descriptions like 'based on feedback' in the output.
            The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
            The output should be limited to 150 words.
            The output format must be: <Thinking>...</Thinking>, <Verification>...</Verification>"""    
            llmapi=VLMAPI(self.model)
            # print(usertext)
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            thinking_verify=llmapi.vlm_request(systext,usertext,image_path)
            
            thinking_matches = re.findall(r'<Thinking>(.*?)</Thinking>', thinking_verify,re.DOTALL)
            verfication_matches = re.findall(r'<Verification>(.*?)</Verification>', thinking_verify,re.DOTALL)
            thinking_str = thinking_matches[0] if thinking_matches else ''
            verification_str = verfication_matches[0] if verfication_matches else ''
            self.generate_o1style_data["trajectory"].append("<Thinking>"+thinking_str+"</Thinking>")
            self.generate_o1style_data["trajectory"].append("<Verification>"+verification_str+"</Verification>")
            # print(thinking_str,verification_str)
            
            
            decision="<DecisionMaking>move forward</DecisionMaking>"
            self.generate_o1style_data["trajectory"].append(decision)
            
            
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}_verify.png"
            if self.task["tasktype"] == "pickup_and_put_in_closerep":
                image_path1=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
                self.crop_and_save(image_path1,image_path)
            else:
                self.rocAgent.move_forward(0.3)
                
                save_image(self.controller.last_event,image_path)
            
            self.generate_o1style_data["images"].append(image_path)
            self.save_metadata_navigable_list("_verify")            
            
            feedback1="Your overall task seems to be completed."
            systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
            usertext=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
            After completing the last action, you gained a new perspective, and the feedback was {feedback1}.
            You need to consider the history of previous rounds and the current perspective to evaluate whether all subtasks have been completed and if the overall task is fully accomplished.           
            Note: The feedback here serves as a potential hint and should not be explicitly treated as known information in your analysis. 
            However, ensure your description aligns with the feedback's outcome while reasoning through observations and plans.
            The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
            The output should be limited to 90 words.
            The output format must be: <Thinking>...</Thinking>"""    
            llmapi=VLMAPI(self.model)
            # print(usertext)
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            thinking_verify=llmapi.vlm_request(systext,usertext,image_path)
            # print(thinking_verify)
            self.generate_o1style_data["trajectory"].append(thinking_verify)
            
        print("*************** end verification *****************")
        
        # 一致性检查
        content1=thinking_verify
        content2=f"Your task is {self.task['taskname']}. After completing the last action, your task seems to be completed."
        self.consistent_check(content1,content2)
        return thinking_verify

    def generate_reflection(self,last_targetobjId,feedback,image_path_1="",image_path_2="",image_path_3=""):

        print("********* start generate reflection",self.round,"********")
        
        if self.current_action["action"]=="navigate to":
            decision_making=f"navigate to {self.plan_objects_list[0]}"
        elif self.current_action["action"] in  ["pickup","put","toggle","open","close","slice"]:
            decision_making=f"{self.current_action['action']} {self.current_action['objectType']}"
        elif self.current_action["action"] in ["observe","move forward","end"]:
            decision_making=f"{self.current_action['action']}"
        
        
        systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
        if self.current_subtask!="":
            systext+=f" At this stage, your current subtask is: {self.current_subtask}."

        num=random.choice([1,2])
  
        usertext1=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
        After completing the last action, you gained a new perspective. The feedback is: {feedback}, the pending search list is: {self.plan_objects_list}.
        You plan to take the next action as {decision_making}, but you need to provide a reasoning process that supports this decision. Ensure your reasoning aligns naturally with the observations and task history without treating {decision_making} as a given.
        In the <Reflection> section, first, you need to describe the image, and reflect on the existing plan, then combine the reflection with the pending search list and provide a new plan description.
        Attention: Do not include any references to feedback or the pending search list {self.plan_objects_list} in your output. These elements are merely potential hints and should not be explicitly mentioned or referenced in your analysis. Your reasoning and plans must be based solely on observations and logical inference, ensuring that the outcomes naturally align with the feedback and pending search list.
        Note: The objects to be found are placed on the surfaces of other objects, and the <Reflection> should focus on the selection of search locations, not the methods or details of the search.
        Note that the objects and containers in the search list and next action are either those you have seen before or those currently visible in the image.
        The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
        The output should be limited to 120 words.
        Output must follow the format: <Reflection>...</Reflection>""" 
        
        usertext2=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
        After completing the last action, you gained a new perspective. The feedback is: {feedback}, the pending search list is: {self.plan_objects_list}.
        You plan to take the next action as {decision_making}, but you need to provide a reasoning process that supports this decision. Ensure your reasoning aligns naturally with the observations and task history without treating {decision_making} as a given.
        In the <Reflection> section, you need to describe the image, and reflect on the existing plan.
        In the <Planning> section, you need to combine the <Reflection> and the previous plan to provide a new plan description.
        Attention: Do not include any references to feedback or the pending search list {self.plan_objects_list} in your output. These elements are merely potential hints and should not be explicitly mentioned or referenced in your analysis. Your reasoning and plans must be based solely on observations and logical inference, ensuring that the outcomes naturally align with the feedback and pending search list.        
        Note: The objects to be found are placed on the surfaces of other objects, and the <Reflection> and <Planning> should focus on the selection of search locations, not the methods or details of the search.
        Note that the objects and containers in the search list and next action are either those you have seen before or those currently visible in the image.
        The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
        The output should be limited to 180 words.
        Output must follow the format: <Reflection>...</Reflection>, <Planning>...</Planning>"""    
        llmapi=VLMAPI(self.model)
        # print(usertext)
        if num==1:usertext=usertext1
        else: usertext=usertext2
        reflection="<Reflection></Reflection>"
        if last_targetobjId!="":
            image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
            reflection=llmapi.vlm_request(systext,usertext,image_path)
        elif image_path_1!="" and image_path_2!="":
            reflection=llmapi.vlm_request(systext,usertext,image_path_1,image_path_2,image_path_3)            

        if num==1:
            self.generate_o1style_data["trajectory"].append(reflection)
        else:
            reflection_matches = re.findall(r'<Reflection>(.*?)</Reflection>', reflection,re.DOTALL)
            planning_matches = re.findall(r'<Planning>(.*?)</Planning>', reflection,re.DOTALL)
            reflection_str = reflection_matches[0] if reflection_matches else ''
            planning_str = planning_matches[0] if planning_matches else ''

            self.generate_o1style_data["trajectory"].append("<Reflection>"+reflection_str+"</Reflection>")
            self.generate_o1style_data["trajectory"].append("<Planning>"+planning_str+"'/<Planning>")
            # print(reflection_str,planning_str)
        
        print("********* end generate reflection",self.round,"********")        
        
        decision_making_1="<DecisionMaking>"+decision_making+"</DecisionMaking>"
        self.generate_o1style_data["trajectory"].append(decision_making_1)

        return decision_making 
    
    def generate_observe(self,last_targetobjId):
        print("********* start generate reflection",self.round,"********")
        current_action=self.current_action 
        current_objectType=current_action["objectType"]
        current_objectId=current_action["objectId"]

        systext=f"You are a mobile robot located in a room.  Your task is {self.task['taskname']}"
        if self.current_subtask!="":
            systext+=f" At this stage, your current subtask is: {self.current_subtask}."
        
        num=random.choice([1,2])

        feedback="The target object was not found. You may re-observe the room to gather more information about the room."
        
        usertext1=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
        After completing the last action, you gained a new perspective.
        Based on the history and observations, you realized that your previous observation of the room was not thorough enough, so you have made the decision to observe the surroundings again.
        In the <Reflection> section, combined with the history, you need to elaborate on the thought process behind your decision to observe the surroundings.
        Note: feedback is a hint and must not be referenced in your response. However, ensure your description aligns with the feedback's outcome while reasoning through observations and plans.
        Note: The objects to be found are placed on the surfaces of other objects, and the <Reflection> should focus on the selection of search locations, not the methods or details of the search.
        The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
        The output should be limited to 80 words.
        Output must follow the format: <Reflection>...</Reflection>""" 
        
        usertext2=f"""The current task has been carried out for {self.round-1} rounds. Below is the history of your observesion, thinking, reflection, and decision-making in previous rounds: {self.generate_o1style_data["trajectory"]}.
        After completing the last action, you gained a new perspective. The feedback from the action is: {feedback}.
        Based on the history and observations, you realized that your previous observation of the room was not thorough enough, so you have made the decision to observe the surroundings again.
        In the <Reflection> section, you need to describe the image, and reflect on the existing plan.
        In the <Planning> section, combined with the history and the Reflection, you need to elaborate on the thought process behind your decision to observe the surroundings.
        Note: feedback is a hint and must not be referenced in your response. However, ensure your description aligns with the feedback's outcome while reasoning through observations and plans.
        Note: The objects to be found are placed on the surfaces of other objects, and the <Reflection> and <Planning> should focus on the selection of search locations, not the methods or details of the search.
        The output should use the first-person perspective, be concise and fluent, and smoothly connect with the previous rounds.
        The output should be limited to 100 words.
        Output must follow the format: <Reflection>...</Reflection>, <Planning>...</Planning>"""    
        llmapi=VLMAPI(self.model)
        # print(usertext)
        if num==1:usertext=usertext1
        else: usertext=usertext2
        
        image_path=f"{self.origin_path}/{self.round-1}_{last_targetobjId}.png"
        reflection=llmapi.vlm_request(systext,usertext,image_path)
        # print(reflection)
        
        
        if num==1:
            self.generate_o1style_data["trajectory"].append(reflection)
        else:
            reflection_matches = re.findall(r'<Reflection>(.*?)</Reflection>', reflection,re.DOTALL)
            planning_matches = re.findall(r'<Planning>(.*?)</Planning>', reflection,re.DOTALL)
            reflection_str = reflection_matches[0] if reflection_matches else ''
            planning_str = planning_matches[0] if planning_matches else ''
            
            self.generate_o1style_data["trajectory"].append("<Reflection>"+reflection_str+"</Reflection>")
            self.generate_o1style_data["trajectory"].append("<Planning>"+planning_str+"</Planning>")
            print(reflection_str,planning_str)
        
        print("********* end generate reflection",self.round,"********") 
        decision_making="<DecisionMaking>"+"observe"+"</DecisionMaking>"
        self.generate_o1style_data["trajectory"].append(decision_making)
        return decision_making
        
    
    def excute(self,decision_making):
        target_objectId=""
        image_path_1=""
        image_path_2=""
        image_path_3=""
        if "navigate to" in decision_making:
            if len(self.plan_objects_list)!=0:
                target_objectType=self.plan_objects_list[0]
                target_objectId=self.target_objectType_navigate(target_objectType)
                self.his_objects_list.append({"objectType":target_objectType,"objectId":target_objectId})
      
                self.update()
                           
        if "pickup" in decision_making:
            target_objectType=decision_making.replace("pickup", "").replace(" ", "")
            # print("pickup",target_objectType)
            current_action=self.current_action 
            current_objectType=current_action["objectType"]
            current_objectId=current_action["objectId"]
            interact_action=current_action["baseaction"]
            if target_objectType==current_objectType and current_action["action"]=="pickup":
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==current_objectId), None)
                target_objectId=current_objectId  
                self.rocAgent.interact(target_object,"pick_up") 
                self.update()
                image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
                self.generate_o1style_data["images"].append(image_path)    
            else:
                target_objectId=""
            
            if self.metadata["errorMessage"]!="":
                self.generate_o1style_data["flag"]=self.metadata["errorMessage"]
            self.save_metadata_navigable_list()
            self.round+=1 
            
        if "put" in decision_making:
            target_objectType=decision_making.replace("put", "").replace(" ", "")
            current_action=self.current_action 
            current_objectType=current_action["objectType"]
            current_objectId=current_action["objectId"]
            interact_action=current_action["baseaction"]
            if target_objectType==current_objectType and current_action["action"]=="put": 
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==current_objectId), None)
                target_objectId=current_objectId  
                self.rocAgent.interact(target_object,"put")  
                self.update()
                image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
                self.generate_o1style_data["images"].append(image_path) 
                 
            else: 
                target_objectId=""
            
            if self.metadata["errorMessage"]!="":
                self.generate_o1style_data["flag"]=self.metadata["errorMessage"]
            
            self.save_metadata_navigable_list()
            self.round+=1 
              
        if "toggle" in decision_making:
            target_objectType=decision_making.replace("toggle", "").replace(" ", "")
            print("toggle",target_objectType)
            current_action=self.current_action 
            current_objectType=current_action["objectType"]
            current_objectId=current_action["objectId"]

            if target_objectType==current_objectType and current_action["action"]=="toggle":
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==current_objectId), None)
                target_objectId=current_objectId  
                if target_object["isToggled"]==True:
                    self.rocAgent.interact(target_object,"toggle_off") 
                elif target_object["isToggled"]==False:
                    self.rocAgent.interact(target_object,"toggle_on") 
                self.update()
                image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
                self.generate_o1style_data["images"].append(image_path)                 
  
            else: 
                target_objectId=""
            
            if self.metadata["errorMessage"]!="":
                self.generate_o1style_data["flag"]=self.metadata["errorMessage"]            
            self.save_metadata_navigable_list()    
            self.round+=1 
                 
        if "open" in decision_making:
            target_objectType=decision_making.replace("open", "").replace(" ", "")
            current_action=self.current_action 
            current_objectType=current_action["objectType"]
            current_objectId=current_action["objectId"]
            if target_objectType==current_objectType and current_action["action"]=="open":  
                target_objectId=current_objectId 
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==current_objectId), None)  
            elif target_objectType!=current_objectType:   
                target_objectId = next((item["objectId"] for item in self.navigable_list if item["objectType"] == target_objectType), None)           
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==target_objectId), None)
            
            self.rocAgent.interact(target_object,"open")  
            
            self.update()
            image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
            save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
            self.generate_o1style_data["images"].append(image_path)
            
            if self.metadata["errorMessage"]!="":
                self.generate_o1style_data["flag"]=self.metadata["errorMessage"]

            self.save_metadata_navigable_list()               
            self.round+=1 
            
        if "close" in decision_making:
            target_objectType=decision_making.replace("close", "").replace(" ", "")

            current_action=self.current_action 
            current_objectType=current_action["objectType"]
            current_objectId=current_action["objectId"]
            if target_objectType==current_objectType and current_action["action"]=="close": 
                target_objectId=current_objectId 
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==current_objectId), None)
  
            elif target_objectType!=current_objectType:   
                target_objectId = next((item["objectId"] for item in self.navigable_list if item["objectType"] == target_objectType), None)           
                target_object = next((item for item in self.metadata["objects"] if item["objectId"]==target_objectId), None)


            self.rocAgent.interact(target_object,"close")   
                
            self.update()
            image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
            save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
            self.generate_o1style_data["images"].append(image_path) 
            
            if self.metadata["errorMessage"]!="":
                self.generate_o1style_data["flag"]=self.metadata["errorMessage"]

            self.save_metadata_navigable_list()                
            self.round+=1 
            

        if "observe" in decision_making:
            degrees=self.metadata["agent"]["cameraHorizon"]
            isStanding=self.metadata["agent"]["isStanding"]
            self.update()
            # print(degrees)
            if abs(degrees)>0:
                if degrees<0:
                    # print("degrees<0",self.metadata["agent"]["cameraHorizon"])
                    self.baseAction.look_down(self.controller,degrees=int(abs(degrees)))
                    self.update()
                    # print(self.metadata["agent"]["cameraHorizon"])
                elif degrees>0:
                    # print("degrees>0",self.metadata["agent"]["cameraHorizon"])
                    degrees
                    self.baseAction.look_up(self.controller,degrees=int(abs(degrees)))
                    # print(self.controller.last_event)
                    self.update()
                    # print(self.metadata["agent"]["cameraHorizon"])
            
            degree=10       
            self.baseAction.look_down(self.controller,degrees=degree)
            
            if isStanding==False: 
                    self.rocAgent.action.stand(self.controller)
                    
            
            self.rocAgent.observe_once("left",90)
            self.update()
            if self.metadata["errorMessage"]=="":
                image_path_1=f"{self.origin_path}/{self.round}_left_90_observe.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path_1)
                self.generate_o1style_data["images"].append(image_path_1) 
                self.save_metadata_navigable_list("_left_90_observe")
            
            self.rocAgent.observe_once("right",180)
            self.update()
            if self.metadata["errorMessage"]=="":
                image_path_2=f"{self.origin_path}/{self.round}_right_90_observe.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path_2)
                self.generate_o1style_data["images"].append(image_path_2)
                self.save_metadata_navigable_list("_left_180_observe")
            
            self.rocAgent.observe_once("left",270)
            self.update()
            if self.metadata["errorMessage"]=="":
                image_path_3=f"{self.origin_path}/{self.round}_left_180_observe.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path_3)
                self.generate_o1style_data["images"].append(image_path_3)
                self.save_metadata_navigable_list("_left_270_observe")
            
            self.rocAgent.observe_once("left",90)
            self.update()          
            self.round+=1     

        if "move forward" in decision_making:
            distance=1
            self.rocAgent.move_forward(distance)
            image_path=f"{self.origin_path}/{self.round}_move_forward.png"
            save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
            self.generate_o1style_data["images"].append(image_path) 
            
        if "end" in decision_making:
            return "end"
        

        return target_objectId,image_path_1,image_path_2,image_path_3
    
    

    def update(self):
        self.metadata=self.controller.last_event.metadata
        self.navigable_list=self.update_navigable_list_vtime()
     
    def get_object_types_from_navigable_list(self):
        object_types = [item['objectType'] for item in self.navigable_list]
        # print("current_find",self.current_action["relatedObject"][-1].split('|')[0])
        if self.current_action["relatedObject"] is not None and len(self.current_action["relatedObject"])>1 and self.current_action["relatedObject"][-1].split('|')[0] in object_types and self.current_action["action"]=="navigate to":
            object_types.remove(self.current_action["relatedObject"][-1].split('|')[0])
        unique_object_types = list(set(object_types))
        return unique_object_types
    
    
    def crop_and_save(self,image_path1, image_path2, crop_margin=150):
        try:
            img = Image.open(image_path1)
            width, height = img.size
            left = crop_margin
            top = crop_margin
            right = width - crop_margin
            bottom = height - crop_margin
            if left < 0 or top < 0 or right > width or bottom > height:
                raise ValueError("error")
            cropped_img = img.crop((left, top, right, bottom))
            cropped_img.save(image_path2)
            print(f"image save {image_path2}")
        
        except Exception as e:
            self.generate_o1style_data["flag"]="verify image"
     
    def target_objectType_navigate(self,target_objectType):
        current_action=self.current_action  
        current_objectType=current_action["objectType"]
        current_objectId=current_action["objectId"]
        if target_objectType==current_objectType:   
            target_objectId=current_objectId
            target_object = next((item for item in self.metadata["objects"] if item["objectId"]==current_objectId), None)
            self.rocAgent.navigate(target_object)
            image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
            save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
            self.generate_o1style_data["images"].append(image_path)

            self.save_metadata_navigable_list()
            self.round+=1
              
        if target_objectType!=current_objectType:   
            target_objectId = next((item["objectId"] for item in self.navigable_list if item["objectType"] == target_objectType), None)           
            target_object = next((item for item in self.metadata["objects"] if item["objectId"]==target_objectId), None)
            
            if target_object["openable"]==True and target_object["isOpen"]==False:
                self.rocAgent.navigate(target_object)
                image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
                self.generate_o1style_data["images"].append(image_path)
                
                self.save_metadata_navigable_list()
                self.round+=1

                true_current_action = copy.deepcopy(self.current_action)
                feedback=f"You are now near the {target_objectType}, but the object is closed. It seems you need to open the object to check its interior."
                self.current_action["action"]="open"
                self.current_action["objectType"]=target_object["objectType"]
                self.current_action["objectId"]=target_object["objectId"]

                fake_decision_making=self.generate_thinking(target_objectId,feedback)
                self.excute(fake_decision_making)
                
                feedback=f"You have now opened the {target_objectType} and found that it seems not to contain what you were looking for. You need to close the {target_objectType}."
                self.current_action["action"]="close"
                self.current_action["objectType"]=target_object["objectType"]
                
                fake_decision_making=self.generate_reflection(target_objectId,feedback)
                self.excute(fake_decision_making)  

                self.current_action = copy.deepcopy(true_current_action)           
            else:
                self.rocAgent.navigate(target_object)
                image_path=f"{self.origin_path}/{self.round}_{target_objectId}.png"
                save_image(o1Stylegenerate_ordered.controller.last_event,image_path)
                self.generate_o1style_data["images"].append(image_path)
                self.save_metadata_navigable_list()
                self.round+=1
                
        self.plan_objects_list.remove(target_objectType)   

        return target_objectId
    
    def save_metadata_navigable_list(self,tag=""):
        self.update()
        if tag=="_verify":
            json_path=f"{self.origin_path}/metadata/{self.round-1}_metadata{tag}.json"
        else:
            json_path=f"{self.origin_path}/metadata/{self.round}_metadata{tag}.json"
        # self.generate_o1style_data["round_metadata"].append(json_path)
        # save_data_to_json(self.metadata,json_path)
        # self.generate_o1style_data["round_navigable_list"].append(self.navigable_list)
        return
    
    
    
    #########################################################
    ###### generate o1 style trajectory(ordered task) #######
    #########################################################    
    def generate_one_o1style_data(self,plan_num,correct_num):

        ############## r1 init ##############
        
        self.metadata=self.controller.last_event.metadata
        event=self.controller.last_event

        self.current_action=copy.deepcopy(self.task["actions"][0])
        self.next_action=copy.deepcopy(self.task["actions"][1])
        
        #### r1-observation
        init_image_path=f"{self.origin_path}/{self.round-1}_init_observe.png"
        save_image(event, init_image_path)   
        selfobservation=self.generate_selfObs(init_image_path)

        pattern = r"First,\s+(.*?),\s+then,\s+(.*?)\."
        match = re.search(pattern, self.task['taskname'], flags=re.IGNORECASE)

        # sub task
        if match:
            self.subtask1 = match.group(1).strip()
            self.subtask2 = match.group(2).strip()
        else:
            self.subtask1, self.subtask2 = None, None
            
        self.current_subtask=self.subtask1
        
        think_plan_num=random.choice([1])
        posible_list=self.generate_r1_plan_thinking(selfobservation,init_image_path,think_plan_num,plan_num,correct_num)

        r1_decision_making=f"<DecisionMaking>navigate to {posible_list[0]}</DecisionMaking>"
        self.generate_o1style_data["trajectory"].append(r1_decision_making)

        self.plan_objects_list=posible_list

        target_objectType=posible_list[0] 
        target_objectId=self.target_objectType_navigate(target_objectType)

        self.update()
        last_reward=self.reward
        self.reward,success,feedback=self.round_reward(target_objectId,r1_decision_making) 
        print("round:",self.round,"last_reward:",last_reward,"new_reward:",self.reward) 
        
        last_targetobjId=target_objectId  
        image_path_1="" 
        image_path_2="" 
        image_path_3="" 

        
        while(self.reward<self.task["totalreward"]): 
            if self.round>=25:
                self.generate_o1style_data["flag"]='too many round'
                print("******",self.generate_o1style_data["flag"])
                return
             
            if self.generate_o1style_data["flag"]!="":
                print("******",self.generate_o1style_data["flag"])
                return

            if self.reward==self.task["totalreward"]-1:
                target_objectId=""
                thinking_verify=self.generate_thinking_verify(last_targetobjId,feedback)
                print("last_reward:",last_reward,"new_reward:",self.reward)
                break

            elif (
                (self.wrong_time>=3 and self.current_action["action"]=="navigate to")
                or (last_reward==self.reward and len(self.plan_objects_list)==0 and self.current_action["action"]=="navigate to")
            ):
                if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                    self.plan_objects_list=[self.current_action["objectType"]]
                    decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)

                    target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)

                    last_reward=self.reward             
                    last_targetobjId=target_objectId

                    self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                    print("last_reward:",last_reward,"new_reward:",self.reward)
                    if success==True:
                        break  
                else:    
                    decision_making=self.generate_observe(last_targetobjId)
                    target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)     
                    self.update()       
                    last_targetobjId=target_objectId
                    if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                        
                        self.plan_objects_list=[self.current_action["objectType"]]
                        decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                        
                        target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                        self.update()
                        if target_objectId=="end":
                            if self.reward==self.task["totalreward"]-1:
                                break
                            self.generate_o1style_data["flag"]="error end"
                            print("************ error end **************")

                        last_reward=self.reward             
                        last_targetobjId=target_objectId
                       
                        self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                        print("last_reward:",last_reward,"new_reward:",self.reward)
                        if success==True:
                            break
                    else:
                        categories=self.get_object_types_from_navigable_list()
                        obj=self.choose_posible_object(categories)
                        self.plan_objects_list=[obj["objectType"]]
                        decision_making=self.generate_reflection(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                      
                        target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                        if target_objectId=="end":
                            if self.reward==self.task["totalreward"]-1:
                                break
                            self.generate_o1style_data["flag"]="error end"
                            print("************ error end **************")
                       
                        last_reward=self.reward             
                        last_targetobjId=target_objectId
                       
                        self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                        print("last_reward:",last_reward,"new_reward:",self.reward)
                        if success==True:
                            break

                        if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                           
                            self.plan_objects_list=[self.current_action["objectType"]]
                            decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                           
                            target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                            if target_objectId=="end":
                                if self.reward==self.task["totalreward"]-1:
                                    break
                                self.generate_o1style_data["flag"]="error end"
                                print("************ error end **************")
                           
                            last_reward=self.reward             
                            last_targetobjId=target_objectId
                           
                            self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                            
                            print("last_reward:",last_reward,"new_reward:",self.reward)
                            if success==True:
                                break
                        
                        else:
                            decision_making=self.generate_observe(last_targetobjId)
                            target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)            
                            last_targetobjId=target_objectId
                            self.update()
                            if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                                self.plan_objects_list=[self.current_action["objectType"]]
                                decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                                if target_objectId=="end":
                                    if self.reward==self.task["totalreward"]-1:
                                        break
                                    self.generate_o1style_data["flag"]="error end"
                                    print("************ error end **************")
                                last_reward=self.reward             
                                last_targetobjId=target_objectId
                                self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                                
                                print("last_reward:",last_reward,"new_reward:",self.reward)
                                if success==True:
                                    break 
                            else:
                                self.generate_o1style_data["flag"]="can't find"
                                print("Can't find")
                                return    

            elif last_reward<=self.reward and self.wrong_time==0 and self.current_action["action"]=="navigate to":         
                if len(self.current_action["relatedObject"])==1:
                    if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                        self.plan_objects_list=[self.current_action["objectType"]]
                        decision_making=self.generate_thinking(last_targetobjId,feedback)
                        target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                        if target_objectId=="end":
                            if self.reward==self.task["totalreward"]-1:
                                break
                            self.generate_o1style_data["flag"]="error end"
                            print("************ error end **************")
                        last_reward=self.reward             
                        last_targetobjId=target_objectId
                        self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                        
                        print("last_reward:",last_reward,"new_reward:",self.reward)
                        if success==True:
                            break                          
                    else:    
                        decision_making=self.generate_observe(last_targetobjId)
                        target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)            
                        last_targetobjId=target_objectId
                        self.update()
                        if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                            self.plan_objects_list=[self.current_action["objectType"]]
                            decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                            target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                            if target_objectId=="end":
                                if self.reward==self.task["totalreward"]-1:
                                    break
                                self.generate_o1style_data["flag"]="error end"
                                print("************ error end **************")
                            last_reward=self.reward             
                            last_targetobjId=target_objectId
                            self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                            
                            print("last_reward:",last_reward,"new_reward:",self.reward)
                            if success==True:
                                break
                        
                        else:
                            categories=self.get_object_types_from_navigable_list()
                            obj=self.choose_posible_object(categories)
                            self.plan_objects_list=[obj["objectType"]]
                            decision_making=self.generate_reflection(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                           
                            target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                            if target_objectId=="end":
                                if self.reward==self.task["totalreward"]-1:
                                    break
                                self.generate_o1style_data["flag"]="error end"
                                print("************ error end **************")
                            
                            last_reward=self.reward             
                            last_targetobjId=target_objectId
                            
                            self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                            
                            print("last_reward:",last_reward,"new_reward:",self.reward)
                            if success==True:
                                break
                            
                            if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                                self.plan_objects_list=[self.current_action["objectType"]]
                                decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                                if target_objectId=="end":
                                    if self.reward==self.task["totalreward"]-1:
                                        break
                                    self.generate_o1style_data["flag"]="error end"
                                    print("************ error end **************")
                                last_reward=self.reward             
                                last_targetobjId=target_objectId
                                self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                                print("last_reward:",last_reward,"new_reward:",self.reward)
                                if success==True:
                                    break
                            
                            
                            else:
                                decision_making=self.generate_observe(last_targetobjId)
                                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)     
                                self.update()       
                                last_targetobjId=target_objectId
                                self.navigable_list=self.update_navigable_list_vtime()

                                if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                                    self.plan_objects_list=[self.current_action["objectType"]]
                                    decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                                    target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                                    if target_objectId=="end":
                                        if self.reward==self.task["totalreward"]-1:
                                            break
                                        self.generate_o1style_data["flag"]="error end"
                                        print("************ error end **************")
                                    last_reward=self.reward             
                                    last_targetobjId=target_objectId
                                    self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                                    
                                    print("last_reward:",last_reward,"new_reward:",self.reward)
                                    if success==True:
                                        break
                                    
                                else:
                                    self.generate_o1style_data["flag"]="can't find"
                                    print("Can't find")
                                    return    

                elif len(self.current_action["relatedObject"])>1:
                    correct_num = random.choice([1])
                    if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                        current_action=self.current_action 
                        current_objectType=current_action["objectType"] 
                        current_objectId=current_action["objectId"]

                        navigable_categories=self.get_object_types_from_navigable_list()
                        type_exists, id_exists=self.check_objId_in_navigable_list(current_action)
                        if type_exists and id_exists:
                            navigable_categories.remove(current_objectType)
                            navigable_categories_without = navigable_categories
                            posible_list=self.choose_r1_posible_object(plan_num-1,navigable_categories_without)
                            print("insert1",correct_num,posible_list)
                            posible_list.insert(correct_num, current_objectType)
                  
                        elif type_exists and not id_exists:
                            navigable_categories.remove(current_objectType)
                            navigable_categories_without = navigable_categories
                            posible_list=self.choose_r1_posible_object(plan_num-1,navigable_categories_without)
                            posible_list.insert(correct_num, current_objectType)
                        self.plan_objects_list=posible_list
                        decision_making=self.generate_thinking(last_targetobjId,feedback)
                        target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                        last_reward=self.reward             
                        last_targetobjId=target_objectId
                        self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                        
                        print("last_reward:",last_reward,"new_reward:",self.reward)
                        if success==True:
                            break
                    else:    
                        decision_making=self.generate_observe(last_targetobjId)
                       
                        target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)            
                        last_targetobjId=target_objectId
                        self.update()
                        if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                            self.plan_objects_list=[self.current_action["objectType"]]
                            decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                            target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                            if target_objectId=="end":
                                if self.reward==self.task["totalreward"]-1:
                                    break
                                self.generate_o1style_data["flag"]="error end"
                                print("************ error end **************")
                            last_reward=self.reward             
                            last_targetobjId=target_objectId
                            self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                            
                            print("last_reward:",last_reward,"new_reward:",self.reward)
                            if success==True:
                                break
                        else:
                            categories=self.get_object_types_from_navigable_list()
                            obj=self.choose_posible_object(categories)
                            self.plan_objects_list=[obj["objectType"]]
                            decision_making=self.generate_reflection(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                            target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                            if target_objectId=="end":
                                if self.reward==self.task["totalreward"]-1:
                                    break
                                self.generate_o1style_data["flag"]="error end"
                                print("************ error end **************")

                            last_reward=self.reward             
                            last_targetobjId=target_objectId
                            self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                            
                            print("last_reward:",last_reward,"new_reward:",self.reward)
                            if success==True:
                                break
                            if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                                self.plan_objects_list=[self.current_action["objectType"]]
                                decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                                if target_objectId=="end":
                                    if self.reward==self.task["totalreward"]-1:
                                        break
                                    self.generate_o1style_data["flag"]="error end"
                                    print("************ error end **************")
                                last_reward=self.reward             
                                last_targetobjId=target_objectId
                                self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                                
                                print("last_reward:",last_reward,"new_reward:",self.reward)
                                if success==True:
                                    break
                            else:
                                decision_making=self.generate_observe(last_targetobjId)
                                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)            
                                last_targetobjId=target_objectId
                                if any(item["objectType"] == self.current_action["objectType"] for item in self.navigable_list):
                                    self.plan_objects_list=[self.current_action["objectType"]]
                                    decision_making=self.generate_thinking(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                                    target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                                    if target_objectId=="end":
                                        if self.reward==self.task["totalreward"]-1:
                                            break
                                        self.generate_o1style_data["flag"]="error end"
                                        print("************ error end **************")
                                    last_reward=self.reward             
                                    last_targetobjId=target_objectId
                                    self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                                    
                                    print("last_reward:",last_reward,"new_reward:",self.reward)
                                    if success==True:
                                        break
                                    
                                else:
                                    self.generate_o1style_data["flag"]="can't find"
                                    print("Can't find")
                                    return    
                image_path_1=""
                image_path_2=""   

            elif last_reward==self.reward:
            
                decision_making=self.generate_reflection(last_targetobjId,feedback,image_path_1,image_path_2,image_path_3)
                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                if target_objectId=="end":
                    if self.reward==self.task["totalreward"]-1:
                        break
                    self.generate_o1style_data["flag"]="error end"
                    print("************ error end **************")
                
                last_reward=self.reward             
                last_targetobjId=target_objectId
              
                self.reward,success,feedback=self.round_reward(target_objectId,decision_making) 
                   
                print("last_reward:",last_reward,"new_reward:",self.reward)
                if success==True:
                    break
                
            elif last_reward<=self.reward:
                decision_making=self.generate_thinking(last_targetobjId,feedback)
                target_objectId,image_path_1,image_path_2,image_path_3=self.excute(decision_making)
                if target_objectId=="end":
                    if self.reward==self.task["totalreward"]-1:
                        break
                    self.generate_o1style_data["flag"]="error end"
                    print("************ error end **************")

                last_reward=self.reward             
                last_targetobjId=target_objectId
                self.reward,success,feedback=self.round_reward(target_objectId,decision_making)   
                print("last_reward:",last_reward,"new_reward:",self.reward)
                if success==True:
                    break
                


        print("******* Success!")
        return
        
    ###############################
    ###### reward  ##############
    ###############################
    def maybe_find(self,objectId):
        self.update()
        for obj in self.metadata["objects"]:
            if obj["objectId"]==objectId and obj["visible"]==True:
                agentx=self.metadata["agent"]["position"]["x"]
                agentz=self.metadata["agent"]["position"]["z"]
                objectx=obj["axisAlignedBoundingBox"]["center"]["x"]
                objectz=obj["axisAlignedBoundingBox"]["center"]["z"]
                distance = math.sqrt((objectx - agentx) ** 2 + (objectz - agentz) ** 2)
                if distance<0.8:
                    return True
        return False
    
    def is_same_objectType_show(self,objectId,find_objectId):
        self.update()
        for obj in self.metadata["objects"]:
            if obj["objectId"]==objectId:
                if obj["receptacleObjectIds"] is not None:
                    for repobjectId in obj["receptacleObjectIds"]:
                        if repobjectId.split("|")[0]==find_objectId.split("|")[0]:
                            return True
        return False
                
    
    
    
    def round_reward_ordered_pickup_two_object_and_put0000(self,objectId,decisionmaking):
        success=False
        feedback=""
        if self.reward==0:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The first target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][1])
                self.next_action=copy.deepcopy(self.task["actions"][2])
            else:
                self.wrong_time+=1
                feedback="The first target object seems not to have been found successfully."
                
        elif self.reward==1:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The first target object seems to have been successfully picked up, now, you can look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][2])
                    self.next_action=copy.deepcopy(self.task["actions"][3])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==2:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1]  or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="You seem to be picking up the first target object, and the container to place it in seems to have been successfully found."
                
                self.current_action=copy.deepcopy(self.task["actions"][3])
                self.next_action=copy.deepcopy(self.task["actions"][4])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
              
        elif self.reward==3:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The first target object seems to have been successfully placed, you can now proceed to find the second target object."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][4]) 
                    self.next_action=copy.deepcopy(self.task["actions"][5])
                    
                    
                    self.current_subtask=self.subtask2
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
        
        elif self.reward==4:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The second target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][5])
                self.next_action=copy.deepcopy(self.task["actions"][6])
                
            else:
                self.wrong_time+=1
                feedback="The second target object seems not to have been found successfully."
                
        elif self.reward==5:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The second target object seems to have been successfully picked up, now, you can look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][6])
                    self.next_action=copy.deepcopy(self.task["actions"][7])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==6:
            
            if (
                (objectId==self.current_action["objectId"]) 
                or (objectId==self.current_action["relatedObject"][-1])
                or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
                ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="You seem to be picking up the second target object, and the container to place it in seems to have been successfully found."
                
                self.current_action=copy.deepcopy(self.task["actions"][7])
                self.next_action=copy.deepcopy(self.task["actions"][8])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
              
        elif self.reward==7:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The second target object seems to have been successfully placed, and the task seems to have been successfully completed."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][8]) 
                    self.next_action=""
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
        
        return self.reward,success,feedback
    
    def round_reward_ordered_pickup_two_object_and_put0001(self,objectId,decisionmaking):
        success=False
        feedback=""
        if self.reward==0:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The first target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][1])
                self.next_action=copy.deepcopy(self.task["actions"][2])
            else:
                self.wrong_time+=1
                feedback="The first target object seems not to have been found successfully."
                
        elif self.reward==1:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The first target object seems to have been successfully picked up, you can now look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][2])
                    self.next_action=copy.deepcopy(self.task["actions"][3])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==2:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1]  or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="You seem to be picking up the first target object, and the target container to place it in seems to have been successfully found."
                
                self.current_action=copy.deepcopy(self.task["actions"][3])
                self.next_action=copy.deepcopy(self.task["actions"][4])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
              
        elif self.reward==3:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The first target object seems to have been successfully placed, you can now proceed to find the second target object."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][4]) 
                    self.next_action=copy.deepcopy(self.task["actions"][5])
                    
                    
                    self.current_subtask=self.subtask2
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
        
        elif self.reward==4:
            # 
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The second target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][5])
                self.next_action=copy.deepcopy(self.task["actions"][6])
                
            else:
                self.wrong_time+=1
                feedback="The second target object seems not to have been found successfully."
                
        elif self.reward==5:
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The second target object seems to have been successfully picked up, you can look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][6])
                    self.next_action=copy.deepcopy(self.task["actions"][7])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==6:
            
            if (
                (objectId==self.current_action["objectId"]) 
                or (objectId==self.current_action["relatedObject"][-1])
                or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
                ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The container seems to have been successfully located. You are now holding the target object and can proceed to place it in the container, but you need to open the container."                    
                
                self.current_action=copy.deepcopy(self.task["actions"][7])
                self.next_action=copy.deepcopy(self.task["actions"][8])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
                    
        elif self.reward==7:
            
            if "open" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container seems to have been successfully opened. You can now place the object you are holding inside."                        
                    self.current_action=copy.deepcopy(self.task["actions"][8])
                    self.next_action=copy.deepcopy(self.task["actions"][9])
                    
                        
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be opened."        
                   
        elif self.reward==8:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The second target object seems to have been successfully placed, and the task seems to have been successfully completed."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][9]) 
                    self.next_action=""
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
        
        return self.reward,success,feedback
    
    def round_reward_ordered_pickup_two_object_and_put0010(self,objectId,decisionmaking):
        success=False
        feedback=""
        if self.reward==0:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The first target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][1])
                self.next_action=copy.deepcopy(self.task["actions"][2])
            else:
                self.wrong_time+=1
                feedback="The first target object seems not to have been found successfully."
                
        elif self.reward==1:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The first target object seems to have been successfully picked up, you can look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][2])
                    self.next_action=copy.deepcopy(self.task["actions"][3])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==2:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1]  or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="You seem to be picking up the first target object, and the container to place it in seems to have been successfully found"
                
                self.current_action=copy.deepcopy(self.task["actions"][3])
                self.next_action=copy.deepcopy(self.task["actions"][4])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
              
        elif self.reward==3:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The first target object seems to have been successfully placed, you can now proceed to find the second target object."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][4]) 
                    self.next_action=copy.deepcopy(self.task["actions"][5])
                       
                    
                    self.current_subtask=self.subtask2
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."

        elif self.reward==4:
           
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1] or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="A container seems to have been located. You can now open it to check if the second target object is inside."
                
                
                self.current_action=copy.deepcopy(self.task["actions"][5])
                self.next_action=copy.deepcopy(self.task["actions"][6])
                
                
                self.plan_objects_list=[]
            else:
                self.wrong_time+=1
                feedback="The target object seems not to have been found successfully."
             
        elif self.reward==5:
            
            if "open" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container seems to have been successfully opened, and the second object seems to be inside. You can now pick up the second target object inside."                      
                    self.current_action=copy.deepcopy(self.task["actions"][6])
                    self.next_action=copy.deepcopy(self.task["actions"][7])
                    
                        
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be opened."
          
        elif self.reward==6:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The second target object has been successfully picked up. You can now close the container and proceed to the next location to place the object."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][7])
                    self.next_action=copy.deepcopy(self.task["actions"][8])
                    
                else:
                    self.wrong_time+=1
                    print("****pickup wrong object****")
                    feedback="It seems that the wrong object was picked up."
            else:
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up." 
                    
        elif self.reward==7:
            
            if "close" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container appears to have been successfully closed, and you are currently holding the second target object. You can now proceed to the next location to place it."
                    self.current_action=copy.deepcopy(self.task["actions"][8])
                    self.next_action=copy.deepcopy(self.task["actions"][9])
                           
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be closed."                   
                        
        elif self.reward==8:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1] or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                
                
                 
                feedback="The target container seems to have been successfully located. You are now holding the target object and can proceed to place it on the container."
                
                self.current_action=copy.deepcopy(self.task["actions"][9])
                self.next_action=copy.deepcopy(self.task["actions"][10])
                
                
                self.plan_objects_list=[]
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
                        
        elif self.reward==9:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The second target object in hand seems to have been successfully placed, and the task seems to have been successfully completed."
                    self.current_action=copy.deepcopy(self.task["actions"][10])
                    self.next_action=""                       
                        
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
    
        return self.reward,success,feedback
    
   
    def round_reward_ordered_pickup_two_object_and_put0100(self,objectId,decisionmaking):
        success=False
        feedback=""
        if self.reward==0:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The first target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][1])
                self.next_action=copy.deepcopy(self.task["actions"][2])
            else:
                self.wrong_time+=1
                feedback="The first target object seems not to have been found successfully."
                
        elif self.reward==1:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The first target object seems to have been successfully picked up, now, you can look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][2])
                    self.next_action=copy.deepcopy(self.task["actions"][3])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
              
        elif self.reward==2:
            
            if (
                (objectId==self.current_action["objectId"]) 
                or (objectId==self.current_action["relatedObject"][-1])
                or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
                ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The container seems to have been successfully located. You are now holding the first target object and can proceed to place it in the container, but you need to open the container."                    
                
                self.current_action=copy.deepcopy(self.task["actions"][3])
                self.next_action=copy.deepcopy(self.task["actions"][4])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
                    
        elif self.reward==3:
            
            if "open" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container seems to have been successfully opened. You can now place the object you are holding inside."                        
                    self.current_action=copy.deepcopy(self.task["actions"][4])
                    self.next_action=copy.deepcopy(self.task["actions"][5])
                    
                        
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be opened."        

        elif self.reward==4:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The first target object seems to have been successfully placed. You can now close the container."
                                        
                    self.current_action=copy.deepcopy(self.task["actions"][5]) 
                    self.next_action=copy.deepcopy(self.task["actions"][6]) 
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
      
        elif self.reward==5:
            
            if "close" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container appears to have been successfully closed. You can now proceed to search for the next target object."
                    self.current_action=copy.deepcopy(self.task["actions"][6])
                    self.next_action=copy.deepcopy(self.task["actions"][7])
                    
                    
                    self.current_subtask=self.subtask2
                             
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be closed."                   

      
        elif self.reward==6:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The second target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][7])
                self.next_action=copy.deepcopy(self.task["actions"][8])
            else:
                self.wrong_time+=1
                feedback="The second target object seems not to have been found successfully."
                
        elif self.reward==7:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The second target object seems to have been successfully picked up, you can now look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][8])
                    self.next_action=copy.deepcopy(self.task["actions"][9])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==8:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1]  or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="You seem to be picking up the second target object, and the target container to place it in seems to have been successfully found."
                
                self.current_action=copy.deepcopy(self.task["actions"][9])
                self.next_action=copy.deepcopy(self.task["actions"][10])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
              
        elif self.reward==9:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The second target object seems to have been successfully placed, and the task seems to have been successfully completed."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][10]) 
                    self.next_action=""
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."

        
        
        return self.reward,success,feedback
    
    
    def round_reward_ordered_pickup_two_object_and_put1000(self,objectId,decisionmaking):
        success=False
        feedback=""       

        if self.reward==0:
           
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1] or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="A container seems to have been located. You can now open it to check if the first target object is inside."
                
                
                self.current_action=copy.deepcopy(self.task["actions"][1])
                self.next_action=copy.deepcopy(self.task["actions"][2])
                
                
                self.plan_objects_list=[]
            else:
                self.wrong_time+=1
                feedback="The target object seems not to have been found successfully."
             
        elif self.reward==1:
            
            if "open" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container seems to have been successfully opened, and the object seems to be inside. You can now pick up the target object."                      
                    self.current_action=copy.deepcopy(self.task["actions"][2])
                    self.next_action=copy.deepcopy(self.task["actions"][3])
                                  
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be opened."
          
        elif self.reward==2:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The first target object has been successfully picked up. You can now close the container."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][3])
                    self.next_action=copy.deepcopy(self.task["actions"][4])
                    
                else:
                    self.wrong_time+=1
                    print("****pickup wrong object****")
                    feedback="It seems that the wrong object was picked up."
            else:
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up." 
                    
        elif self.reward==3:
            
            if "close" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The container appears to have been successfully closed, and you are currently holding the target object. You can now proceed to the next location to place it."
                    self.current_action=copy.deepcopy(self.task["actions"][4])
                    self.next_action=copy.deepcopy(self.task["actions"][5])
                           
                else:
                    self.wrong_time+=1
                    print("****open wrong object****")
                    feedback="It seems that the wrong container was chosen to be closed."                   
                        
        elif self.reward==4:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1] or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                
                
                 
                feedback="The target container seems to have been successfully located. You are now holding the target object and can proceed to place it on the container."
                
                self.current_action=copy.deepcopy(self.task["actions"][5])
                self.next_action=copy.deepcopy(self.task["actions"][6])
                
                
                self.plan_objects_list=[]
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
                
        elif self.reward==5:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The first target object in hand seems to have been successfully placed, you can now proceed to find the second target object."
                    self.current_action=copy.deepcopy(self.task["actions"][6])
                    self.next_action=copy.deepcopy(self.task["actions"][7]) 
                    
                    
                    self.current_subtask=self.subtask2                      
                        
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
       
       
        elif self.reward==6:
           
            if (
                (objectId==self.current_action["objectId"])
            or (objectId==self.current_action["relatedObject"][-1])
            or (self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]))
            ):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="The target object seems to have been successfully found, you can pick up the target object."                
                
                self.current_action=copy.deepcopy(self.task["actions"][7])
                self.next_action=copy.deepcopy(self.task["actions"][8])
            else:
                self.wrong_time+=1
                feedback="The target object seems not to have been found successfully."
                
        elif self.reward==7:
            
            if "pickup" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                     
                    feedback="The target object seems to have been successfully picked up, you can look for the target container to place it."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][8])
                    self.next_action=copy.deepcopy(self.task["actions"][9])
                    
                else:
                    
                    self.wrong_time+=1
                    feedback="It seems that the wrong object was picked up."
            else:
                
                self.wrong_time+=1
                feedback="The target object seems not to have been successfully picked up."                    
                    
        elif self.reward==8:
            
            if objectId==self.current_action["objectId"] or objectId==self.current_action["relatedObject"][-1]  or self.is_same_objectType_show(objectId,self.current_action["relatedObject"][-1]):
                self.wrong_time=0
                self.reward=self.reward+1
                 
                feedback="You seem to be picking up the first target object, and the container to place it in seems to have been successfully found."
                
                self.current_action=copy.deepcopy(self.task["actions"][9])
                self.next_action=copy.deepcopy(self.task["actions"][10])
                
            else:
                self.wrong_time+=1
                feedback="The container seems not to have been found successfully."
              
        elif self.reward==9:
            
            if "put" in decisionmaking:
                if self.current_action["objectType"] in decisionmaking:
                    self.wrong_time=0
                    self.reward=self.reward+1
                    
                    feedback="The second target object seems to have been successfully placed, and the task seems to have been successfully completed."
                    
                    self.current_action=copy.deepcopy(self.task["actions"][10]) 
                    self.next_action=""
                       
                             
                else:
                    self.wrong_time+=1
                    print("****put wrong object****")
                    feedback="It seems that the wrong container was chosen for placement."
            else:
                self.wrong_time+=1
                feedback="The placement location was found before, but it seems that placement was not chosen."
             
                
                
                
                
        return self.reward,success,feedback 
    
     
    
    
    def round_reward(self,objectId,decisionmaking):
        success=False
        feedback="" 
  
        if self.task['tasktype']=="ordered_pickup_two_object_and_put0000":
            self.reward,success,feedback=self.round_reward_ordered_pickup_two_object_and_put0000(objectId,decisionmaking)
            return self.reward,success,feedback

        elif self.task['tasktype']=="ordered_pickup_two_object_and_put0001":
            self.reward,success,feedback=self.round_reward_ordered_pickup_two_object_and_put0001(objectId,decisionmaking)
            return self.reward,success,feedback

        elif self.task['tasktype']=="ordered_pickup_two_object_and_put0010":
            self.reward,success,feedback=self.round_reward_ordered_pickup_two_object_and_put0010(objectId,decisionmaking)
            return self.reward,success,feedback
        
        elif self.task['tasktype']=="ordered_pickup_two_object_and_put0100":
            self.reward,success,feedback=self.round_reward_ordered_pickup_two_object_and_put0100(objectId,decisionmaking)
            return self.reward,success,feedback       
  
        elif self.task['tasktype']=="ordered_pickup_two_object_and_put1000":
            self.reward,success,feedback=self.round_reward_ordered_pickup_two_object_and_put1000(objectId,decisionmaking)
            return self.reward,success,feedback 

        return self.reward,success,feedback


    



        

def initialize_scene(scene_diagonal,origin_pos_path):

    controller=Controller( 
        agentMode="default",                
        visibilityDistance=scene_diagonal, 
        scene=scene,
        gridSize=0.1,                      
        snapToGrid=True,                   
        rotateStepDegrees=90,               
        renderDepthImage=False,            
        renderInstanceSegmentation=False,   
        width=1600,  
        height=900, 
        fieldOfView=90,                    
    )
    
    if scene!='FloorPlan22':
        pos=load_json(origin_pos_path)
        position=pos["position"]
        rotation=pos["rotation"]  
        horizon=pos["cameraHorizon"]   
        
        controller.step(
            action="Teleport",
            position=position,
            rotation=rotation,
            horizon=horizon,
            standing=True
        )
        
    if scene=='FloorPlan6':
        controller.step(action='MoveLeft',moveMagnitude=0.2)
        controller.step(action='MoveAhead',moveMagnitude=1.5)
        controller.step(action='RotateRight',degrees=90)
        controller.step(action='MoveAhead',moveMagnitude=1.5)
        controller.step(action='MoveAhead',moveMagnitude=2)
        controller.step(action='RotateRight',degrees=90)
        controller.step(action='MoveAhead',moveMagnitude=1.5)
        controller.step(action='MoveAhead',moveMagnitude=2)
        controller.step(action='RotateRight',degrees=120)
    if scene=='FloorPlan22':
        controller.step(action='MoveAhead',moveMagnitude=1.5)
        controller.step(action='RotateRight',degrees=90)
        controller.step(action='MoveAhead',moveMagnitude=1.5)
        controller.step(action='MoveAhead',moveMagnitude=1)
        controller.step(action='RotateRight',degrees=150)
    if scene=='FloorPlan12':
        controller.step(action='RotateRight',degrees=180)
    if scene=='FloorPlan21':
        controller.step(action='RotateRight',degrees=180)
    if scene=='FloorPlan15':
        controller.step(action='MoveRight',moveMagnitude=0.7)
        controller.step(action='MoveAhead',moveMagnitude=1.3)
        controller.step(action='RotateRight',degrees=180)
    if scene=='FloorPlan17':
        controller.step(action='MoveAhead',moveMagnitude=1)
        controller.step(action='RotateRight',degrees=180)  
    if scene=='FloorPlan25':
        controller.step(action='MoveBack',moveMagnitude=1)
    if scene=="FloorPlan26":
        controller.step(action='RotateLeft',degrees=90)    
    
    metadata=controller.last_event.metadata
    
    return controller, metadata


def run_initial_scene(timeout, scene_diagonal, origin_pos_path, retry_limit=3):
    controller = None
    metadata = None
    retry_count = 0

    def init_task():
        nonlocal controller
        nonlocal metadata
        controller, metadata = initialize_scene(scene_diagonal, origin_pos_path) 
        
    init_thread = threading.Thread(target=init_task)

    init_thread.start()

    init_thread.join(timeout) 

    if init_thread.is_alive():
        print(f"Initialization exceeded {timeout} seconds, retrying...")
        retry_count += 1
        controller, metadata = initialize_scene(scene_diagonal, origin_pos_path)
        return controller, metadata
    else:
        print("Initialization succeeded") 
        return controller, metadata 
 


if __name__=="__main__":
    env="taskgenerate"
    model = "gpt-4o-2024-11-20" # use gpt-4o to generate trajectories
    # you can set timeout for AI2THOR init here.
    timeout=40           
    
    # the complexity level of the trajectory. Generally, c represents the most complex level,  
    # b represents the simplest level, and a represents the intermediate level.
    random_types=[
        {"mode":"0","plan_num":1,"correct_num":None},
        {"mode":"1","plan_num":1,"correct_num":0},
        {"mode":"10","plan_num":2,"correct_num":0},
        {"mode":"01","plan_num":2,"correct_num":1},
        {"mode":"00","plan_num":2,"correct_num":None},
        {"mode":"100","plan_num":3,"correct_num":0},
        {"mode":"010","plan_num":3,"correct_num":1},
        {"mode":"001","plan_num":3,"correct_num":2},
        {"mode":"000","plan_num":3,"correct_num":None},
    ]
    trajectory_types=[
        {"trajectory_idx":"b","random_types":[1,2,5]},
    ]
    
    
    ###### step1. choose the task type here(ordered) ####################
    # Ordered picking and placing
    # xxxx 0/1 indicates whether open-close is needed
    # The order is as follows: objectA_rep, objectA_new_rep, objectB_rep, objectB_new_rep
    tasktypes=[
        "ordered_pickup_two_object_and_put0000",
        "ordered_pickup_two_object_and_put0001",
        "ordered_pickup_two_object_and_put0010",    #kitchens
        "ordered_pickup_two_object_and_put0100",
        "ordered_pickup_two_object_and_put1000",    #kitchens
    ]
    
    tasktype="ordered_pickup_two_object_and_put1000"
    

    room_type = ['kitchens','living_rooms','bedrooms','bathrooms']
    for room in room_type:
        if room == 'kitchens':
            floorplans = [f"FloorPlan{i}" for i in range(1,31) if i != 8 and i!=21]
        if room == 'living_rooms':
            floorplans = [f"FloorPlan{200 + i}" for i in range(1,31)]
        if room == 'bedrooms':
            floorplans = [f"FloorPlan{300 + i}" for i in range(1, 31)]
        if room == 'bathrooms':
            floorplans = [f"FloorPlan{400 + i}" for i in range(1, 31)]

        #### generate trajectories ##########
        for trajectory_type in trajectory_types:
            trajectory_idx=trajectory_type["trajectory_idx"]
            random_type_num=random.choice(trajectory_type["random_types"])
            random_type=random_types[random_type_num]
            plan_num=random_type["plan_num"]
            correct_num=random_type["correct_num"]
            
            for scene in floorplans: 
                metadata_path=f"{env}/{room}/{scene}/metadata.json"
                print("metadata_path:",metadata_path)

                generate_task=f"ordered/{tasktype}_task_metadata/{scene}.json"
                print("task_metadata_path:",generate_task)
                
                ###### get metadata
                metadata=load_json(metadata_path)
                metadata=metadata[0]

                tasks=load_json(generate_task)
                if not tasks:
                    continue

                for instruction_idx, task in enumerate(tasks, start=0):
                    
                    print("\n\n*********************************************************************")
                    print(f"Scene:{scene} Task_Type: {tasktype} Processing_Task: {instruction_idx} Trajectory_idx: {trajectory_idx}")
                    print("*********************************************************************\n")
                    # instruction_idx=0
                    
                    task=tasks[instruction_idx]
                    print("task:",task["taskname"])                    

                    start_time = time.time()
                    origin_path=f"data_{task['tasktype']}/{scene}_{task['tasktype']}_{instruction_idx}_{trajectory_idx}"
                    
                    scene_size= metadata["sceneBounds"]["size"]
                    scene_diagonal = math.sqrt(scene_size["x"]**2 + scene_size["z"]**2)
                    origin_pos_path=f"{env}/{room}/{scene}/originPos.json" 
  
                    max_retries=2
                    error_paths = [] 
                    for attempt in range(max_retries + 1):  
                        try:
                            controller, metadata=run_initial_scene(timeout, scene_diagonal, origin_pos_path)
                            o1Stylegenerate_ordered=O1StyleGenerate_ordered(
                                controller,scene,origin_path,metadata,task,model=model
                            )

                            o1Stylegenerate_ordered.initial_navigable_list()
 
                            # json_path=f"{origin_path}/metadata/0_metadata.json"
                            # o1Stylegenerate_ordered.generate_o1style_data["round_metadata"].append(json_path)
                            # save_data_to_json(o1Stylegenerate_ordered.metadata,json_path)
                            # o1Stylegenerate_ordered.generate_o1style_data["round_navigable_list"].append(o1Stylegenerate_ordered.navigable_list)

                            
                            o1Stylegenerate_ordered.generate_o1style_data["task_metadata"]=task

                            o1Stylegenerate_ordered.generate_o1style_data["scene"]=scene
                            o1Stylegenerate_ordered.generate_o1style_data["tasktype"]=tasktype 
                            o1Stylegenerate_ordered.generate_o1style_data["instruction_idx"]=instruction_idx

                            o1Stylegenerate_ordered.generate_one_o1style_data(plan_num,correct_num)

                            end_time = time.time()

                            execution_time = end_time - start_time
                            print(f"Execution time: {execution_time:.4f} seconds") 
                            
                            o1Stylegenerate_ordered.generate_o1style_data["time"]=execution_time

                            path=f"{origin_path}/{scene}_{task['tasktype']}_{instruction_idx}_{trajectory_idx}.json"
                            
                            save_data_to_json(o1Stylegenerate_ordered.generate_o1style_data,path)
                            print("generate_o1style_data save:",{path})
                            
                            controller.stop()
                            break

                        except Exception as e:
                            print(f"Error: {e}, try again...")
                            clear_folder(origin_path)
                        
                            if attempt == max_retries - 1: 
                                error_paths.append(origin_path)  
                                save_data_to_json(error_paths,"./wrong_generte_path_list.json")
                                continue

