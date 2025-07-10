import random
import re
import copy
import base64
# from openai import OpenAI
import http.client
import json
import requests
from collections import OrderedDict
from prompt import MATCH_PROMPT
import os
try:
    from VLMCall import VLMAPI,VLMRequestError
except Exception as e:
    VLMAPI=None
    VLMRequestError = None
    print(e)

LOCAL_PORT = os.getenv("LOCAL_PORT")
DEPLOY_MODEL_COUNT = os.getenv("DEPLOY_MODEL_COUNT")
if DEPLOY_MODEL_COUNT is None:
    DEPLOY_MODEL_COUNT = 4 
print(f"evaluate utils:{DEPLOY_MODEL_COUNT}")
print(f"evaluate utils:{LOCAL_PORT}")

def metric(task, trajectory, key_actions):
    shortest_actions = copy.deepcopy(key_actions)
    tasktype = task["tasktype"]
    taskname = task["taskname"]
    flag=0
    total_reward = 0
    reward = 0
    pre_action=""
    for t in trajectory:
        action, item, legal_interactions, success = t["action"], t["object"], t["legal_objects"], t["success"]
        if action in ["init", "observe", "move forward", "navigate to", "error"] or success==0:
            if success:
                if item is not None:
                    pre_action = action+" "+item
                else:
                    pre_action = action
            continue
        elif "end" in action:
            
            if tasktype=="single_search":
                temp_flag = 0
                for obj in legal_interactions:
                    if obj.lower() in taskname.lower():
                        reward += 1
                        temp_flag = 1
                        break
                if temp_flag == 0:
                    if pre_action in key_actions:
                        reward += 1
                        flag=1
                    
                        break
            
            else:
                reward += 1
        
        elif item is not None:
            if action.startswith("put"):
                action = "put"
            if action+" "+item in shortest_actions:
                shortest_actions.remove(action+" "+item) 
                reward += 1
        
        if item is not None:
            pre_action = action+" "+item
        else:
            pre_action = action
    
   
    for ka in key_actions:
        if "observe" in ka or "move forward" in ka or "navigate to" in ka:
            continue
        else:
            total_reward += 1
    
   
    metric_dic = {
        "success": int(reward/total_reward),
        "efficiency": (len(key_actions)+1)/len(trajectory) if int(reward/total_reward) else 0.0,
        "completeness": reward/total_reward,
        "key_actions_success": flag
    }
    return metric_dic

def get_max_steps(task_type):
    task_steps = {
        "single_search": 22,
        "single_search_navigate_fault": 22,
        "single_search_unnecessary_repeat": 22,
        "single_search_from_closerep": 22,
        "single_search_from_closerep_open_fault": 22,
        "single_toggle": 24,
        "single_toggle_navigate_fault": 24,
        "single_toggle_unnecessary_repeat": 24,
        "single_toggle_toggle_fault":24,
        "single_pickup": 24,
        "single_pickup_unnecessary_repeat": 24,
        "single_pickup_pickup_fault": 24,
        "single_pickup_navigate_fault": 24,
        "single_pickup_from_closerep": 24,
        "pickup_and_put": 30,
        "pickup_and_put_pickup_fault": 30,
        "pickup_and_put_navigate_fault": 30,
        "'pickup_and_put_unnecessary_repeat": 30,
        "pickup_and_put_put_fault": 30,
        "pickup_and_put_in_closerep": 30,
        "pickup_from_closerep_and_put": 30,
        "pickup_from_closerep_and_put_close_fault": 30,
        "pickup_from_closerep_and_put_in_closerep": 30,
        "pickup_from_closerep_and_put_in_closerep_open_fault": 30,
        "pickup_from_closerep_and_put_in_closerep_close_fault": 30,
        "ordered_pickup_two_object_and_put": 36
    }
    
    return task_steps.get(task_type, 36)

def call_llm(messages, model,retry_limit=3):

    vlmcall=VLMAPI(model)
    content=vlmcall.vlm_request(messages)

    if content is None:
        raise VLMRequestError("VLM request failed.")
    return content

def prepare_deploy_messages(inputs_):
    inputs = copy.deepcopy(inputs_)
    images = inputs["images"]
    messages = inputs["messages"]
    image_index = 0
    for m in messages:
        if "<image>" in m["content"]:
            count = m["content"].count("<image>")
            user_text = m['content'].replace("<image>", "")
            content = []
            for i in range(count):
                content.append({"type": "image", "image": f"data:image/png;base64,{encode_image(images[image_index])}"})
                image_index += 1
            content.append({"type": "text", "text": user_text})
            m['content'] = content
    return messages

def local_model(messages, port):
    data = {
        "inputs":[{"messages": messages}]
    }
    
    url = f"http://127.0.0.1:{port}/chat"

    print("url:",url)
    response = requests.post(url, json=data, timeout=300) 
    print(response.json())
    if isinstance(response.json()["output_text"],list):
        return response.json()["output_text"][0]
    else:
        return response.json()["output_text"]

def match_item(description, objects,action_space,MODE,match_item_model="default"):
    if description.startswith("observe") or description.startswith("move forward"):
        return None
    target_obj = "No Suitable Object"
    objects_unique = list(OrderedDict.fromkeys(objects))
    
    if MODE=="LOCAL": 
        data = {
                    "s1":[description], 
                    "s2":objects_unique
                }
        try:
            response = requests.post("http://127.0.0.1:20000/match", json=data)
            target_obj = response.json()["target_obj"]
        except:
            print("embedding match failed")
        return target_obj
    
    elif MODE=="API":
        if match_item_model=="default":
            print("Please set the API model for the match item.")
            
        item=""
        for action_name in action_space: 
            
            if "put in" in description:
                item=description.replace("put in","")
                item=item.strip()
                item_lower = item.lower()
                for obj in objects_unique:
                    if obj.lower() == item_lower:
                        return obj
            if description.startswith(action_name):
                item=description.replace(action_name,"")
                item=item.strip()
                item_lower = item.lower()
                for obj in objects_unique: 
                    if obj.lower() == item_lower:
                        return obj
                    
        if item!="":# 
            target_obj = call_llm([
                    {"role": "user", 
                    "content": MATCH_PROMPT.format(objects=",".join(objects_unique), description=item)}
                ],
                model=match_item_model
                                )
        else:# 
            target_obj = call_llm([
                {"role": "user", 
                "content": MATCH_PROMPT.format(objects=",".join(objects_unique), description=description)}
            ],
            model=match_item_model
                            )

        return target_obj
        

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def prepare_api_messages(inputs_):
    inputs = copy.deepcopy(inputs_)
    images = inputs["images"]
    messages = inputs["messages"]
    image_index = 0
    for m in messages:
        if "<image>" in m["content"]:
            count = m["content"].count("<image>")
            user_text = m['content'].replace("<image>", "")
            content = []
            for i in range(count):
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(images[image_index])}"}})
                image_index += 1
            content.append({"type": "text", "text": user_text})
            m['content'] = content
    
    return messages

def invalid_action(action):
    # "put in" for MODE=API
    actions = ["init", "navigate to", "pickup", "put", "put in","toggle", "open", "close", "observe", "move forward", "end"]
    for a in actions:
        if action.startswith(a):
            return False
    
    return True

def macth_action_item(response, action_space, objects,MODE="LOCAL"):
    match = re.search(r'<DecisionMaking>(.*?)</DecisionMaking>', response)
    action = "error" # match failed
    if match:
        raw_action = match.group(1)
    else:
        return "response", "error", None

    if raw_action.startswith("end") or raw_action.startswith("observe") or raw_action.startswith("move forward") or raw_action.startswith("error"):
        item = None
    else:
        raw_item = raw_action.split(" ")[-1].strip()
        if raw_item in objects:
            item = raw_item
        else:
            item = match_item(raw_action.strip(), objects,action_space,MODE)


    for action_name in action_space:
        # !!for MODE=API: put in 
        if "put in" in raw_action:
            action="put in"
            break
        elif raw_action.startswith(action_name):
            action = action_name
            break
    
    return raw_action, action, item

def save_data_to_json(json_data, base_path):
    """
    """
    os.makedirs(os.path.dirname(base_path), exist_ok=True)

    try:
        with open(base_path, "r") as f:
            existing_data = json.load(f)
            if not isinstance(existing_data, list):
                existing_data = []
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = []

    # append
    existing_data.append(json_data)

    # write
    with open(base_path, "w") as f:
        json.dump(existing_data, f, indent=4)
    
    print("save json data to path:",base_path)