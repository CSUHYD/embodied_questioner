


import os
import json
from tqdm import tqdm
import copy
import json
import random
import re
import copy
import base64
import tiktoken
import argparse


model = "gpt-4o"
step2count={}

def num_tokens_from_string(string: str, model: str) -> int:
    """Returns the number of tokens in a text string."""
    encoding = tiktoken.encoding_for_model(model)
    num_tokens = len(encoding.encode(string))
    return num_tokens

def lcs_length(seq1, seq2):
    m = len(seq1)
    n = len(seq2)
    
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
                
    return dp[m][n]

def metric(tasktype, taskname, trajectory, key_actions):
    shortest_actions = copy.deepcopy(key_actions)
    # tasktype = task["tasktype"]
    # taskname = task["taskname"]
    flag=0
    total_reward = 0
    reward = 0
    pre_action=""
    object_list=[]
    
    ordered_actions = []
    model_actions = []
    
    total_token_length = []
    
    for t in trajectory:
        total_token_length.append(num_tokens_from_string(t["response"], "gpt-4o"))
        action, item, legal_interactions, success = t["action"], t["object"], t["legal_objects"], t["success"]
        # if action == 'navigate to' and success == 1:
        #     object_list.append(item)
        if action == 'navigate to':
            object_list.append(item)
        if action in ["init", "observe", "move forward", "navigate to", "error", ] or success==0:#"close"
            if success:
                if item is not None:
                    pre_action = action+" "+item
                else:
                    pre_action = action
            continue
        # 
        elif "end" in action:
            
            if tasktype=="single_search":
                temp_flag = 0
                for obj in legal_interactions:
                    if obj.lower() in taskname.lower():
                        reward += 1
                        temp_flag = 1
                        # print("single_search reward1",reward)
                        break
                if temp_flag == 0:
                    # 
                    # print(key_actions)
                    # print(pre_action, item)
                    if pre_action in key_actions:
                        reward += 1
                        flag=1
                        # print("single_search reward2",reward)
                        break
            
            else:
                reward += 1
                model_actions.append(action)
        
        elif item is not None:
            if action.startswith("put"):
                action = "put"
            if action+" "+item in shortest_actions:
                shortest_actions.remove(action+" "+item) 
                model_actions.append(action+" "+item)
                reward += 1
        
        if item is not None:
            pre_action = action+" "+item
        else:
            pre_action = action
    
    
    for ka in key_actions:
        if "observe" in ka or "move forward" in ka or "navigate to" in ka: # or "close" in ka
            continue
        else:
            ordered_actions.append(ka)
            total_reward += 1
    
    
    object_list_new = list(set(object_list))
    re_num=len(object_list)-len(object_list_new)
    if len(object_list) != 0:
        re_rate = re_num / len(object_list)
    else:
        re_rate = 0
    
    metric_dic = {
        "success": int(reward/total_reward),
        "efficiency": (len(key_actions)+1)/len(trajectory) if int(reward/total_reward) else 0.0,
        "completeness": reward/total_reward,
        "completeness_ordered": lcs_length(model_actions, ordered_actions)/len(ordered_actions) if tasktype!="single_search" else reward/total_reward,
        "key_actions_success": flag,
        "repeat_rate":re_rate,
        "step":len(key_actions)-1 if tasktype!="single_search_from_closerep" else 2,
        "length":sum(total_token_length) # //len(total_token_length)
    }
    if len(key_actions)-1 ==3:
        print(len(key_actions)-1, tasktype)
    if str(len(key_actions)-1) not in step2count:
        step2count[str(len(key_actions)-1)] = 0
    step2count[str(len(key_actions)-1)] += 1
    return metric_dic

def load_data(prefix_path):
    data_temp = []
    exsit_task = 0
    try:
        for pre in os.listdir(prefix_path):
            mid_path = os.path.join(prefix_path, pre)
            exsit_task+=1
            for path in os.listdir(mid_path):
                file_path = os.path.join(mid_path, path)
                if file_path.endswith(".json"):
                    with open(file_path, 'r') as f:
                        data_temp.append(json.load(f))
    except Exception as e:
        print(e)
    print(f"--evaluate success count:{len(data_temp)}, evaluating count:{exsit_task-len(data_temp)},last count:{784-exsit_task}--")
    
    dic = {}

    for line in data_temp:
        tasktype = line["tasktype"]
        taskname = line["taskname"]
        trajectory = line["trajectory"]
        key_actions = line["key_actions"]
        metric_ = metric(tasktype, taskname, trajectory, key_actions)
        step = str(metric_["step"]) if metric_["step"] < 9 else "9+"
        if step not in dic:
            dic[step] = {}
            dic[step]["avg_length"] = [metric_["length"]]
            dic[step]["success_rate"] = [metric_["success"]]
        else:
            dic[step]["avg_length"].append(metric_["length"])
            dic[step]["success_rate"].append(metric_["success"])

        line["metric_f"] = metric_
    for step in dic:
        dic[step]["avg_length"] = round(sum(dic[step]["avg_length"])/len(dic[step]["avg_length"]),4) #  max(dic[step]["avg_length"]) 
        dic[step]["success_rate"] = round(sum(dic[step]["success_rate"])/len(dic[step]["success_rate"]),4)

    with open(prefix_path+"_length_step_sr_.json","w") as f:
        f.write(json.dumps(dic, ensure_ascii=False, indent=4))


    with open(prefix_path+".jsonl","w") as f:
        for line in data_temp:
            f.write(json.dumps(line, ensure_ascii=False)+"\n")
        
    return data_temp

def main(model_list):
    data = []
    for model in model_list:
        prefix_path = f"data/{model}"
        if os.path.exists(prefix_path):
            print(f"--model:{model}--evaluate--")
            data.extend(load_data(prefix_path))

    model2data = {}
    model2result = {}
    for line in data:
        model = line["model"]
        if model in model2data:
            model2data[model].append(line)
        else:
            model2data[model] = [line]

    for model in model2data:
        success_count = 0
        efficiency = 0.0
        completeness = 0.0
        completeness_ordered = 0.0
        repeat_rate = 0.0
        task_type2success_count = {}
        task_type2efficiency = {}
        task_type2completeness_ordered = {}
        task_type2completeness = {}
        task_type2repeat_rate = {}
        tasktype2count={}

        result = {
            "success_rate": {},
            "success_count": {},
            "efficiency": {},
            "completeness": {},
            "completeness_ordered": {},
            "repeat_rate": {},
        }
        for line in model2data[model]:
            line["tasktype"]= line["tasktype"]
            success_count += line['metric_f']['success']
            efficiency += line['metric_f']['efficiency']
            completeness += line['metric_f']['completeness'] if "completeness" in line['metric_f'] else line['metric_f']['extend']
            completeness_ordered += line['metric_f']['completeness_ordered']
            repeat_rate += line['metric_f']['repeat_rate']

            if line["tasktype"] in tasktype2count:
                tasktype2count[line["tasktype"]] += 1
            else:
                tasktype2count[line["tasktype"]] = 1
            
            if line["tasktype"] in task_type2success_count:
                task_type2success_count[line["tasktype"]] += line['metric_f']['success']
            else:
                task_type2success_count[line["tasktype"]] = line['metric_f']['success']
            
            if line["tasktype"] in task_type2efficiency:
                task_type2efficiency[line["tasktype"]] += line['metric_f']['efficiency']
            else:
                task_type2efficiency[line["tasktype"]] = line['metric_f']['efficiency']

            if line["tasktype"] in task_type2completeness:
                task_type2completeness[line["tasktype"]] += line['metric_f']['completeness'] if "completeness" in line['metric_f'] else line['metric_f']['extend']
            else:
                task_type2completeness[line["tasktype"]] = line['metric_f']['completeness'] if "completeness" in line['metric_f'] else line['metric_f']['extend']

            if line["tasktype"] in task_type2completeness_ordered:
                task_type2completeness_ordered[line["tasktype"]] += line['metric_f']['completeness_ordered'] 
            else:
                task_type2completeness_ordered[line["tasktype"]] = line['metric_f']['completeness_ordered']

            if line["tasktype"] in task_type2repeat_rate:
                task_type2repeat_rate[line["tasktype"]] += line['metric_f']['repeat_rate']
            else:
                task_type2repeat_rate[line["tasktype"]] = line['metric_f']['repeat_rate']

        dic = {
            "S":["single_search","single_search_from_closerep"],
            "M":["single_pickup","single_pickup_from_closerep","single_toggle"],
            "T":["pickup_and_put","pickup_and_put_in_closerep","pickup_from_closerep_and_put","pickup_from_closerep_and_put_in_closerep"],
            "C":["ordered_pickup_two_object_and_put", "long-range tasks with dependency relationships"
            ]
        }
        for key, val in dic.items():
            result["success_rate"][key] = (round(sum([task_type2success_count[tasktype] for tasktype in val])/sum([tasktype2count[tasktype] for tasktype in val]), 4), sum([tasktype2count[tasktype] for tasktype in val]))
            result["efficiency"][key] = (round(sum([task_type2efficiency[tasktype] for tasktype in val])/sum([tasktype2count[tasktype] for tasktype in val]), 4), sum([task_type2success_count[tasktype] for tasktype in val]))
            result["completeness"][key] = (round(sum([task_type2completeness[tasktype] for tasktype in val])/sum([tasktype2count[tasktype] for tasktype in val]), 4), sum([tasktype2count[tasktype] for tasktype in val]))
            result["completeness_ordered"][key] = (round(sum([task_type2completeness_ordered[tasktype] for tasktype in val])/sum([tasktype2count[tasktype] for tasktype in val]), 4), sum([tasktype2count[tasktype] for tasktype in val]))
            result["repeat_rate"][key] = (round(sum([task_type2repeat_rate[tasktype] for tasktype in val])/sum([tasktype2count[tasktype] for tasktype in val]), 4), sum([tasktype2count[tasktype] for tasktype in val]))

        result["success_rate"]["all"] = (round(success_count / len(model2data[model]), 4), len(model2data[model]))
        
        result["efficiency"]["all"] = (round(efficiency / len(model2data[model]), 4), len(model2data[model]))
        
        result["completeness"]["all"] = (round(completeness / len(model2data[model]), 4), len(model2data[model]))
        
        result["completeness_ordered"]["all"] = (round(completeness_ordered / len(model2data[model]), 4), len(model2data[model]))

        result["repeat_rate"]["all"] = (round(repeat_rate / len(model2data[model]), 4), len(model2data[model]))

        # result["success_count"]["all"] = success_count
        for key in task_type2success_count:
            result["success_rate"][key] = (round(task_type2success_count[key] / tasktype2count[key], 4), tasktype2count[key])
            # result["success_count"][key] = task_type2success_count[key]
        
        for key in task_type2efficiency:
            if task_type2success_count[key]:
                result["efficiency"][key] = (round(task_type2efficiency[key] / tasktype2count[key], 4), tasktype2count[key])
            else:
                result["efficiency"][key] = (0,tasktype2count[key])
        
        for key in task_type2completeness:
            result["completeness"][key] = (round(task_type2completeness[key] / tasktype2count[key], 4), tasktype2count[key])   
        
        for key in task_type2completeness_ordered:
            result["completeness_ordered"][key] = (round(task_type2completeness_ordered[key] / tasktype2count[key], 4), tasktype2count[key])   
                
        for key in task_type2repeat_rate:
            result["repeat_rate"][key] = (round(task_type2repeat_rate[key] / tasktype2count[key], 4), tasktype2count[key])   
        

        model2result[model] = result

    show_result(model2result)
    for s, count in step2count.items():
        print(s, count)
    # print(model2result)

def show_result(model2result):
    print("="*150)
    print(f"{'model':<120}{'success_rate':<15}{'all_count':<15}")
    print("="*150)
    for model in model2result:
        print(f"{model:<120}{model2result[model]['success_rate']['all'][0]:<15}{model2result[model]['success_rate']['all'][1]:<15}")
        print("-"*150)
    
    with open("data/result/result.csv", 'w') as f:
        f.write("model,tasktype,success_rate,efficiency,completeness,completeness_ordered,repeat_rate,tasktype_count,all_count\n")
        for model in model2result:
            for tasktype in model2result[model]["success_rate"]:
                f.write(f"{model},{tasktype},{model2result[model]['success_rate'][tasktype][0]},{model2result[model]['efficiency'][tasktype][0]},{model2result[model]['completeness'][tasktype][0]},{model2result[model]['completeness_ordered'][tasktype][0]}, {model2result[model]['repeat_rate'][tasktype][0]},{model2result[model]['success_rate'][tasktype][1]},{model2result[model]['success_rate']['all'][1]}\n")
            f.write("\n")

if __name__=="__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--model_name", type=str, default=None, help="")
    
    args = parser.parse_args()
    if args.model_name is None:
        print("please input model_name")
        exit()
    model_list = args.model_name.split(",")
    # model_list = ["Qwen/Qwen2.5-VL-3B-Instruct"]
    main(model_list)