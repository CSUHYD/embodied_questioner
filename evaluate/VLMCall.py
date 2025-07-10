import http.client
import json
from mimetypes import guess_type
import random

import base64
from datetime import datetime
from PIL import Image
import io
import matplotlib.pyplot as plt
from openai import OpenAI, AzureOpenAI, APIError
import time


from VLMCallapi_keys import moda_keys,api_keys
    
class VLMRequestError(Exception):
    pass  


moda_models=[
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-VL-7B-Instruct",
    "Qwen/Qwen2-VL-7B-Instruct"
]

class VLMAPI:
    def __init__(self,model):#gpt-4o-2024-11-20,gpt-4o-mini
        self.model=model
        

    def vlm_request(self,
                    messages,
                    max_tokens=4096,
                    retry_limit=3
                    ):
        
        
        if self.model in moda_models:
            
            retry_count = 0
            while retry_count < retry_limit: 
                try:
                    t1=time.time()
                    # import pdb;pdb.set_trace()
                    print(f"********* start call {self.model} *********")
                    
                    api_key=random.choice(moda_keys)
                    client = OpenAI(
                        api_key=api_key, # 请替换成您的ModelScope SDK Token
                        base_url="https://api-inference.modelscope.cn/v1"
                    )
                    if self.model=="Qwen/Qwen2-VL-7B-Instruct":
                        max_tokens=2000
                    outputs = client.chat.completions.create(
                        model=self.model, 
                        stream=False,
                        messages = messages,
                        temperature=0.9,
                        max_tokens=max_tokens
                        )
                    
                    
                    content = outputs.choices[0].message.content
                    
                    # record 
                    current_time = int(datetime.now().timestamp())  
                    formatted_time = datetime.utcfromtimestamp(current_time).strftime("%Y/%m/%d/%H:%M:%S")
                    data_dict = {
                        "model":self.model,
                        "messages":messages,
                        "response": {
                            "model":outputs.model,
                            "content":content,
                            "usage":str(outputs.usage),
                            "choices":str(outputs.choices[0]),
                            "created":outputs.created,
                            },
                        "current_time": formatted_time
                    }
                    save_path=f"./data/{self.model}/apiRecord.json"
                    save_data_to_json(data_dict, save_path)
                    
                    
                    
                    t2=time.time()-t1
                    print("****** content: \n",content)
                    print(f"********* end call {self.model}: {t2:.2f}*********")
                    
                    return content
                
                except Exception as ex:
                    print(f"Attempt call {self.model} {retry_count + 1} failed: {ex}")
                    time.sleep(300)
                    retry_count += 1
            
            
        else:
            payload = json.dumps(
                {
                    "model": self.model,
                    "stream": False,
                    "messages": messages,
                    "temperature": 0.9,
                    "max_tokens": max_tokens
                }
            )
            
            conn = http.client.HTTPSConnection("api2.aigcbest.top")
            
            retry_count = 0
            while retry_count < retry_limit: 
                try:
                    api_key=random.choice(api_keys)
                    headers = {
                    'Accept': 'application/json',
                    'Authorization': 'Bearer '+api_key,
                    'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
                    'Content-Type': 'application/json'
                    }
                    t1=time.time()
                    # import pdb;pdb.set_trace()
                    print(f"********* start call {self.model} *********")
                    
                    test=conn.request("POST", "/v1/chat/completions", payload, headers)

                    res = conn.getresponse()
                    
                    
                    data = res.read()
                    data=data.decode("utf-8")
                    data_dict = json.loads(data)
                    # print(data)
                    content = data_dict["choices"][0]["message"]["content"]


                    # record 
                    current_time = int(datetime.now().timestamp())  
                    formatted_time = datetime.utcfromtimestamp(current_time).strftime("%Y/%m/%d/%H:%M:%S")
                    record = {
                        "model":self.model,
                        "messages":messages,
                        "response": data_dict,
                        "current_time": formatted_time
                    }
                    save_path=f"./data/{self.model}/apiRecord.json"
                    save_data_to_json(record, save_path)

                    t2=time.time()-t1
                    print("****** content: \n",content)
                    print(f"********* end call {self.model}: {t2:.2f} *********")
                    
                    return content
                except Exception as ex:
                    print(f"Attempt call {self.model} {retry_count + 1} failed: {ex}")
                    time.sleep(300)
                    retry_count += 1
        
        return None



    def encode_image_2(self, image_path):
        # 获取图像的 MIME 类型，默认为 'image/jpeg'，如果无法识别则使用默认
        mime_type, _ = guess_type(image_path)
        if mime_type is None:
            mime_type = 'image/jpeg'  # 默认 MIME 类型

        # 打开图像并调整大小
        with Image.open(image_path) as img:
            original_width, original_height = img.size
            new_width = original_width // 2
            new_height = original_height // 2
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            print("new_width:",new_width,"new_height:",new_height)
            
            # 使用 BytesIO 缓存图像数据
            buffered = io.BytesIO()
            resized_img.save(buffered, format="JPEG")
            
            # 将图像数据编码为 Base64
            base64_encoded_data = base64.b64encode(buffered.getvalue()).decode('utf-8')

        # 构造 data URL
        return f"data:{mime_type};base64,{base64_encoded_data}"


    # def vlm_request_2(self,
    #                 systext,
    #                 usertext,
    #                 image_path1=None,
    #                 image_path2=None,
    #                 image_path3=None,
    #                 max_tokens=1500,
    #                 api_key=GPT4V_KEY,
    #                 azure_endpoint=GPT4V_ENDPOINT,
    #                 retry_limit=3):
        
    #     # 构建系统提示
    #     sys_prompt = systext

    #     # 构建用户输入提示
    #     user_prompt = usertext

    #     # 准备消息列表
    #     messages = [
    #         {"role": "system", "content": sys_prompt},
    #         {"role": "user", "content": user_prompt},
    #     ]
        
    #     # 将图像信息加入消息中，按需添加
    #     image_paths = [image_path1, image_path2, image_path3]
    #     for image_path in image_paths:
    #         if image_path:
    #             img_url = self.encode_image_2(image_path) 
    #             messages.append(
    #                 {
    #                     "role": "user",
    #                     "content": [
    #                         {
    #                             "type": "image_url",
    #                             "image_url": {"url": img_url},
    #                         }
    #                     ]
    #                 }
    #             )
        
    #     # 初始化 AzureOpenAI 客户端
    #     client = AzureOpenAI(
    #         azure_endpoint=azure_endpoint,
    #         api_key=api_key,
    #         api_version="2024-02-15-preview"
    #     )
    #     retry_count = 0
    #     while retry_count < retry_limit:
    #         try:
    #             time.sleep(61)  # 暂停 45 秒
    #             # 调用 API
    #             outputs = client.chat.completions.create(
    #                 model=self.model,
    #                 messages=messages,
    #                 max_tokens=max_tokens,
    #                 temperature=0.8,
    #             )
                
    #             # 提取响应
    #             response = outputs.choices[0].message.content

    #             # 获取当前时间戳并格式化
    #             current_time = int(datetime.now().timestamp())  
    #             formatted_time = datetime.utcfromtimestamp(current_time).strftime("%Y/%m/%d/%H:%M:%S")
                
    #             # 添加时间戳到响应数据
    #             data_dict = {
    #                 "response": response,
    #                 "current_time": formatted_time
    #             }
                
    #             # 保存响应数据到 JSON 文件
    #             save_data_to_json(data_dict, "./vlmRecord.json")
    #             # 返回响应内容
    #             return response
                
    #         except Exception as ex:
    #             print(f"Attempt {retry_count + 1} failed: {ex}")
    #             retry_count += 1
            
    #         return "Failed to generate completion after multiple attempts."

import os
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


if __name__=="__main__":
    
    model="Qwen/Qwen2-VL-7B-Instruct"
    llmapi=VLMAPI(model)
    # /Users/meng/mllm-embody/ipynb/Third_Person_Frame_1.png
    # categories=['Bowl', 'Knife', 'CoffeeMachine', 'ButterKnife', 'Vase', 'Apple', 'Microwave', 'Shelf', 'SaltShaker', 'Spoon', 'Mug', 'StoveBurner', 'StoveKnob', 'Plate', 'Cup', 'Lettuce', 'Pan', 'SoapBottle', 'HousePlant', 'PepperShaker', 'WineBottle', 'Statue', 'Spatula', 'Cabinet', 'Faucet', 'CounterTop', 'Window', 'SinkBasin', 'DishSponge', 'GarbageCan', 'LightSwitch', 'Kettle', 'Pot', 'Book', 'Drawer', 'Floor', 'Fork', 'Egg', 'Stool', 'CreditCard', 'Tomato', 'ShelvingUnit', 'PaperTowelRoll', 'Sink', 'Potato', 'Bread', 'Bottle', 'Fridge', 'Toaster']
    
    # systext=f"""
    # You are a mobile robot located in a room. Your task is to analyze and describe the objects in the room based on a third-person overhead view.
    # """
    # usertext=f""""Please describe the objects visible in the overhead view of the room, focusing on the spatial relationships between them.
    # The categories of objects in the room are: {categories}.
    # Note: Do not describe object categories that are not present in the room. Do not describe uncertain or unclear relative positions in the image.
    # Make sure to describe the scene from your first-person perspective, starting with "From a third-person perspective, the room I am in ..."
    # The description should be clear and concise, limited to 150 words, and focus solely on the room description.
    # """
    
    # image_path1="/Users/meng/mllm-embody/ipynb/Third_Person_Frame_1.png"
    # llmapi.vlm_request(systext,usertext,image_path1)
    systext="hi"
    usertext="hi"
    messages = [
        {"role": "system", "content": systext},
        {"role": "user", "content": systext},
    ]
    content=llmapi.vlm_request(messages)
    print(content)
    
    
    
    
    
    
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
   
    #############最初始的思考计划
   
    # image_path1="ipynb/Third_Person_Frame_1.png"
    # image_path2="ipynb/Third_Person_Frame_1.png"
    
    # # 识别+搜索【分开？】agent：寻找较大件的物体时
    # # 给的自由度过高？
    # sysprompt1="""
    # 你的任务是寻找参考图像中的目标：robot agent。在参考图像中已经圈画出，它是一个移动的机器人。
    # """
    # # memory的存储和分析组件：物体周围哪些地方已经被搜索过，现在在物体的哪一侧，下一步可选择的转向
    # # hisrotate="""
    # # 正面向桌子区域已被搜索过，未发现robot agent，当前转向桌子左侧90度区域进行搜索，下一步可选择转向为右侧。
    # # """
    # # hisrotate="""
    # # 正面向桌子和左侧90度区域附近已被搜索过，未发现robot agent。当前正面向桌子进行搜索，下一步可选择转动方向为左侧和右侧。
    # # """
    # # hisrotate="""
    # # 正面向桌子和桌子左侧90度区域附近已被搜索过，未发现robot agent。当前转向桌子右侧90度区域进行搜索，下一步可选择转动方向为左侧。
    # # """
    # hisrotate="""
    # 正面向桌子,桌子左侧90度区域附近和右侧90度区域附近3个区域已被搜索过，未发现robot agent。当前正面向桌子进行搜索，下一步可选择转动方向为左侧和右侧。
    # """
    # object="桌子"
    # reference=f"请根据实时场景图，历史搜索信息，当前相对{object}的角度和位置"
    # userprompt1=f"""
    # 请根据参考图像以及实时场景图，判断所寻找的目标是否存在。请先仔细的观察场景，一步步推理，最后给出你的答案。
    # 实时场景图中标注了当前可转动的方向，{hisrotate}
    # 请回答：A.存在, B.物体周围需要进一步查找, C.不存在，当前物体周围已完全探索。
    # 如果决定需要进一步查找即选择B，{reference}，思考下一步动作。以物体为中心，若左右两侧90度区域之内都已搜索，且未发现目标，则认为该物体周围已经完全探索。注意思考左右转动的角度是否足够覆盖搜索范围，避免遗漏。注意已经搜索过的转动区域需要跳过，避免重复搜索。
    # 输出你的动作：向前，向后或者旋转，并给出选择理由。注意，其中旋转需要给出方向和角度可从45，90，135，180，225，270，315和360之间选择。
    # 如果决定当前物体周围已经搜索完全即选择C，{reference}，转身寻找其他区域。
    # 输出你的动作：左转或者右转，角度在从0到360度之间，开始在其他区域寻找目标。
    # """
    
    # # 有：接近
    
    
    # # 指路agent：
    # # 结合上一步给出-刚刚离开的物体
    # sysprompt2="""
    # 你的任务是在房间中搜索出参考图像中的目标物体：robot agent。你需要搜索的目标物体在参考图像中已经圈画出，它是一个移动的机器人。
    # """
    
    # lastdecide="身后桌子附近"
    # userprompt2=f"""
    # 上一步你判断{lastdecide}不存在要寻找的目标物体，请根据实时场景图和参考图像，判断寻找目标是否存在，思考选择下一个搜索区域。
    # 请回答：A.存在,B.移动到下一个搜索区域
    # 若选择移动到下一个搜索区域即B选项，为了探索更广的新区域，请根据实时场景图给出1个下一步最想接近的物体名称和行进方向。    
    # """
    
    # # memory判断
    # area="桌子"
    # sysprompt3="""
    # 你的任务是在房间中搜索出目标物体：robot agent。
    # """
    # userprompt3=f"""
    # 现在你需要移动到下一个搜索区域：{area}附近。为避免重复搜索，请你根据实时场景图和曾经搜索过的{area}附近历史场景图判断，下一个搜索区域是否重复搜索。仔细对比图片，给出你的选择和原因。
    # 请回答：A.下一个区域未被搜索过,B.下一个区域此前已经被搜索过   
    # """
    
    
    
    # content=vlm_request_1(sysprompt3,userprompt3,image_path1,image_path2)
    
    
    # record={
    #     "image_path":image_path2,
    #     "output":content
    # }
    # filepath="/Users/meng/project/mllm-embody/testimage/testjson.json"
    # with open(filepath,'r') as file:
    #     current_record=json.load(file)
    # current_record.append(record)
    # with open(filepath,'w',encoding="utf-8") as file:
    #     json.dump(current_record,file,ensure_ascii=False,indent=4)
    # # print(content)
    
    # # 引导agent：
    # sysprompt2="""
    # 你的任务是在房间中搜索出参考图像中的物体：robot agent。你需要搜索的物体在参考图像中已经圈画出，它是一个移动的机器人。
    # """
    # userprompt2="""
    # 上一步你判断当前场景中不存在需要寻找的物体，你需要进一步搜索。请告诉我你为了下一步搜索，最想接近的方向或物体。
    
    # """
    
    
