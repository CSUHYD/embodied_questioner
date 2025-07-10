import json
import random
from ai2thor_engine.RocAgent import RocAgent
from utils import *
from prompt import *
import argparse
from tqdm import tqdm
import os
import time
from ai2thor.controller import Controller
from ai2thor.platform import CloudRendering
MODE = "LOCAL" # choose ["LOCAL","API"]
PLATFORM_TYPE="GPU" 

MAX_MODEL_INFER_COUNT=3
def load_data(args):
    cache = {}
    prefix_path = f"./data/{args.model_name}"
    if os.path.exists(prefix_path):
        for pre in os.listdir(prefix_path):
            if "result.json" in os.listdir(os.path.join(prefix_path, pre)):
                cache[pre] = 1
    with open(args.input_path) as f:
        data = json.load(f)
    
    print(f"--total task count:{len(data)}")
    last_data = []
    for line in data:
        identity = f"""{line["identity"]}_{line['tasktype']}_{line["scene"]}_{line['instruction_idx']}"""
        if identity not in cache:
            last_data.append(line)
    print(f"--cache:{len(data)-len(last_data)}---remaining evaluation tasks:{len(last_data)}")
    # random.shuffle(last_data)
    per_group_count = len(last_data)//args.total_count
    group_data = [last_data[i*per_group_count: (i+1)*per_group_count if i !=args.total_count-1 else len(last_data)] for i in range(args.total_count)]
    print(f"--Current process evaluation data:{len(group_data[args.cur_count-1])}")
    group_data[args.cur_count-1].reverse()
    return group_data[args.cur_count-1]

def get_trajectory(controller, task, model, max_step=10, port=-1):
    try:
        scene = task["scene"]
        task_name = task["taskquery"]
        index = task["identity"]
        if task["tasktype"].startswith("ordered_pickup_two_object_and_put"):
            tasktype="ordered_pickup_two_object_and_put"
        else:tasktype=task["tasktype"]
        max_step=get_max_steps(tasktype)

        save_path=f"./data/{model}/{index}_{task['tasktype']}_{scene}_{task['instruction_idx']}"
        
        print(f"******** Task Name: {task_name} *** Max Steps: {max_step} ********")
        print(f"******** Task Record: {save_path} ********")
        autogn = RocAgent(controller, save_path, scene, visibilityDistance=20, gridSize=0.1, fieldOfView=90, 
                            target_objects=task["target_objects"],
                            related_objects=task["related_objects"],
                            navigable_objects=task["navigable_objects"],
                            taskid=task["identity"],
                            platform_type=PLATFORM_TYPE)
        print("RoctAgent Initialization successful!!!")
        objects = autogn.eventobject.get_objects_type(autogn.controller.last_event)
        action, pre_action = "init", "init"
        item, pre_item = None, None
        trajectory = []
        legal_locations = []
        legal_objects = []
        images = []
        response = ""
        messages = [{"role": "system","content": EMBODIED_SYSTEM_PROMPT}]
        call_model_count = 0
        con_same_action = 0
        last_step_count = autogn.step_count
        while action != "end" and autogn.step_count < max_step and call_model_count<MAX_MODEL_INFER_COUNT:
            last_step_count = autogn.step_count
            if action==pre_action and item==pre_item:
                con_same_action+=1
                if con_same_action == MAX_MODEL_INFER_COUNT:
                    dic = {
                        "response": response,
                        "action": "end",
                        "object": None,
                        "legal_locations": [],
                        "legal_objects": [],
                        "success": 0,
                        "errorInfo": "",
                        "images": []
                    }
                    trajectory.append(dic)
                    autogn.controller.stop()
                    result_dir = autogn.result_dir
                    del autogn
                    return trajectory, messages, result_dir
            else:
                con_same_action = 0
                pre_action=action
                pre_item=item
            if invalid_action(action):
                user_text = INVALID_ACTION_PROMPT.format() # action=temp_action
                dic = {
                        "response": response,
                        "action": action,
                        "object": item,
                        "legal_locations": legal_locations,
                        "legal_objects": legal_objects,
                        "success": 0,
                        "errorInfo": user_text,
                        "images": []
                    }
                trajectory.append(dic)
                messages.append({
                        "role": "user",
                        "content": user_text+USER_IMAGE_PREFIX_ERROR
                    })
            
            else:
            
                print(autogn.step_count,"****** begin exec action:",action, item ,"***")
                success, image_fp, legal_locations, legal_objects = autogn.exec(action, item)
                print(autogn.step_count,"****** end exec action:",action, item ,"***")
                user_text = ""
            
                if not success or image_fp is None or image_fp == []:
                    if "navigate to" in action:                    
                        if item=="No Suitable Object":
                            user_text = f"""<|feedback|>Action: "{action}" is illegal, the name of the navigated object doesn't quite match the obejct in the image, please try navigating to another object first.\n"""
                        else:                           
                            user_text = f"""<|feedback|>Action: "{action}" is illegal, "{item}" is the most relevant item in this room and "{raw_action}". Object: "{item}" is not currently navigable, you can try "navigate to <object>" to reach nearby, larger objects for closer observation.\n"""

                    else:
                        if item=="No Suitable Object":    
                            user_text = f"""<|feedback|>Action: "{action}" is illegal, the name of the object doesn't quite match the obejct in the image, Please try interacting with another object or navigating to another object.\n"""
                        else:                             
                            user_text = f"""<|feedback|>Action: {raw_action} is illegal, Object: {item} is currently unavailable for interaction. Possible situations include: {item} does not exist in your current view; you are too far away from {item}; the {item} cannot perform operation {action}.\nYou can try \"move forward\" to approach the target object or \"navigate to <object>\" to reach nearby, larger objects for closer inspection."""
                        
                    dic = {
                        "response": response,
                        "action": action,
                        "object": item,
                        "legal_locations": legal_locations,
                        "legal_objects": legal_objects,
                        "success": 0,
                        "errorInfo": user_text,
                        "images": image_fp
                    }
                    trajectory.append(dic)
                    
                    messages.append({
                        "role": "user",
                        "content": user_text+USER_IMAGE_PREFIX_ERROR
                    })
            
                
                else:
                    dic = {
                        "response": response,
                        "action": action,
                        "object": item,
                        "legal_locations": legal_locations,
                        "legal_objects": legal_objects,
                        "success": 1,
                        "errorInfo": "",
                        "images": image_fp
                    }
                    trajectory.append(dic)
                    if isinstance(image_fp, list):
                        for i in image_fp:
                            images.append(i)
                            user_text += "<image>"
                    else:
                        images.append(image_fp)
                        user_text += "<image>"
                
                    
                    if action == "init":
                        if action == "init":
                            if MODE=="LOCAL":
                                TASK_PREFIX=TASK_PREFIX_PUT
                            elif MODE=="API":
                                TASK_PREFIX=TASK_PREFIX_PUT_IN
                        messages.append({"role":"user",
                                        "content":user_text + TASK_PREFIX.format(
                                            task_name=task_name, )})
                                            
                    
                    elif "move forward" in action:
                        messages.append({
                            "role": "user",
                            "content": user_text+USER_IMAGE_PREFIX_MOVE_FORWARD.format(
                                action=action
                            )
                        })
                    else:
                        temp_action = action if item is None else action + " " + item
                        messages.append({"role":"user",
                                        "content":user_text+USER_IMAGE_PREFIX.format(
                                            action=temp_action,
                                            )})
                
            inputs = {"messages": messages, "images": images}
            
            if MODE=="API":
                api_messages = prepare_api_messages(inputs)
                response = call_llm(api_messages, model)
                call_model_count += 1
            elif MODE=="LOCAL":
                local_messages = prepare_deploy_messages(inputs)
                response = local_model(local_messages, port) #local model predict
                call_model_count += 1
            
            if response == "":
                print(f"--task{task['identity']}Trajectory acquisition failed -- request timed out, model is not output, end the current evaluation task!!!")
                return None, None, None

            if autogn.step_count!=last_step_count:
                call_model_count = 0
            else:
                print(f"******** Action_Execute_Count: {autogn.step_count} *** Call_VLM_Count: {call_model_count} ********")  
            raw_action, action, item = macth_action_item(response, autogn.action_space, objects,MODE)

            messages.append({"role":"assistant","content":response})
        
        dic = {
            "response": response,
            "action": "end",
            "object": None,
            "legal_locations": legal_locations,
            "legal_objects": legal_objects,
            "success": 1,
            "errorInfo": "",
            "images": []
        }
        trajectory.append(dic)
        autogn.controller.stop()
        del autogn
        return trajectory, messages, save_path
    except Exception as e:
        print(e)
        autogn.controller.stop()
        del autogn
        print(f"--task{task['identity']}Track acquisition failed -- emulator /api exception, end the current evaluation task!!!--")

def test(controller, test_data, model="Qwen2.5-VL-3B-Instruct", port=-1):
    save_path=f"./data/{model}/{test_data['identity']}_{test_data['tasktype']}_{test_data['scene']}_{test_data['instruction_idx']}"
    if os.path.exists(f"{save_path}/result.json"):
        print(f"""--task{test_data["identity"]}It has been evaluated successfully, skip it.---""")
        return
    
    test_start_time = time.time()
    id = test_data['instruction_idx']
    if 'task_metadata' in test_data:
        scene_metadata = test_data['task_metadata']
        key_actions = [(a['action']+" "+ a["objectType"]).strip() for a in scene_metadata['actions']]
        
    else:
        with open(f"./data/single_search_task_metadata/{test_data['scene']}.json") as f:
            scene_metadata = json.load(f)[0]
        key_actions = [(a['action']+" "+ a["objectType"]).strip() for a in scene_metadata[id]['actions']]
    
    
    trajectory, messages, result_dir = get_trajectory(controller, test_data, model, port=port)
    
    if trajectory is None:
        print(f"--task{test_data['identity']}failed--")
        return
    metric_dic = metric(test_data, trajectory, key_actions)
    test_end_time = time.time()
    elapsed_time = int(test_end_time - test_start_time)
    with open(f"{result_dir}/result.json","w") as f:
        f.write(json.dumps({
            "identity":test_data["identity"],
            "scene": test_data["scene"],
            "tasktype": test_data["tasktype"],
            "instruction_idx": test_data["instruction_idx"],
            "model": model,
            "taskname":test_data["taskname"],
            "trajectory": trajectory,
            "messages": messages,
            "key_actions": key_actions,
            "metrics": metric_dic,
            "time": elapsed_time,
            "maxstep": get_max_steps(test_data["tasktype"]),
        }, indent=4))
    print(f"""--task{test_data["identity"]}evaluate successed---""")

if __name__ == "__main__":
    
    if MODE=="LOCAL":
        parser = argparse.ArgumentParser()

        parser.add_argument("--input_path", type=str, default="./data/test_809.json", help="input file path")
        parser.add_argument("--model_name", type=str, default="Qwen2.5-VL-3B-Instruct", help="")
        parser.add_argument("--batch_size", type=int, default=200, help="")
        parser.add_argument("--port", type=int, default=10000, help="")
        parser.add_argument("--cur_count", type=int, default=1, help="")
        parser.add_argument("--total_count", type=int, default=4, help="")
        args = parser.parse_args()
        print(args)
        data = load_data(args)
        success_count = 0
        # controller = None
        controller = Controller(
            platform=CloudRendering,
            snapToGrid=False,
            quality='Medium',
            agentMode="default",
            massThreshold=None,
            scene='FloorPlan1',
            visibilityDistance=20,
            gridSize=0.1,
            renderDepthImage=False,
            renderInstanceSegmentation=False,
            width=800,
            height=450,
            fieldOfView=90,
        )
        for test_data in tqdm(data):
            try:
                test(controller, test_data, args.model_name, args.port)
                success_count += 1
            except Exception as e:
                print(e)
                print(f"--task{test_data['identity']}failed, End the current evaluation task!!!--")
                continue
        print(f"--The current process evaluation task end--total task count:{len(data)}successed task count:{success_count}")
    
    
    elif MODE=="API":
        match_item_model="Qwen/Qwen2.5-72B-Instruct"
    
    # from concurrent.futures import ThreadPoolExecutor
    # from tqdm import tqdm
    # with ThreadPoolExecutor(5) as executor:
    #     for match in tqdm(
    #         executor.map(test, data), total=len(data)
    #         ):
    #             pass
    # with ThreadPoolExecutor(2) as executor:
    #     futures = []
    #     for test_data, index in zip(data, [i for i in range(len(data))]):
    #         futures.append(executor.submit(test, test_data, index, args.model_name))
        
    #     for future in tqdm(futures, total=len(data)):
    #         future.result()