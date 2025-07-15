import requests
import json
import random
import base64
from datetime import datetime
from PIL import Image
import io
import time
import os
import json
import requests
import logging

def load_prompt_config(config_path="config/prompt_config.json"):
    """加载 prompt 配置文件"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Config file {config_path} not found, using default config")
        return {}

# 默认配置
PROMPT_CONFIG = load_prompt_config()

    
class VLMRequestError(Exception):
    pass  

class VLMAPI:
    def __init__(self, model):  # qwen2.5vl:32b, llava:7b, etc.
        self.model = model
        self.api_url = "http://110.42.252.68:8080/api/generate"
        

    def encode_image(self, image_path):
        """编码图像为base64格式"""
        with Image.open(image_path) as img:
            original_width, original_height = img.size

            if original_width == 1600 and original_height == 800:
                new_width = original_width // 2
                new_height = original_height // 2
                resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                buffered = io.BytesIO()
                resized_img.save(buffered, format="JPEG")
                base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            else:
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')

        return base64_image
    

    def vlm_request(self,
                    systext,
                    usertext,
                    image_path1=None,
                    image_path2=None,
                    image_path3=None,
                    max_tokens=1500,
                    retry_limit=3):
        """
        发送VLM请求到Ollama API
        
        Args:
            systext: 系统提示文本
            usertext: 用户提示文本
            image_path1/2/3: 图像路径（可选）
            max_tokens: 最大token数
            retry_limit: 重试次数
        """
        print("===== VLM SYSTEXT =====\n%s", systext)
        print("===== VLM USERTEXT =====\n%s", usertext)
        
        # 构建完整的提示文本
        full_prompt = f"{systext}\n\n{usertext}"
        
        # 准备图像数据
        images = []
        if image_path1:
            base64_image1 = self.encode_image(image_path1)
            images.append(base64_image1)
        if image_path2:
            base64_image2 = self.encode_image(image_path2)
            images.append(base64_image2)
        if image_path3:
            base64_image3 = self.encode_image(image_path3)
            images.append(base64_image3)
        
        # 构建Ollama API请求payload
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.9
            }
        }
        
        # 如果有图像，添加到payload中
        if images:
            payload["images"] = images
        
        retry_count = 0
        while retry_count < retry_limit: 
            try:
                t1 = time.time()
                print(f"********* start call {self.model} *********")
                
                # 发送请求到Ollama API
                response = requests.post(self.api_url, json=payload, timeout=60)
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("response", "")
                    
                    current_time = int(datetime.now().timestamp())  
                    formatted_time = datetime.utcfromtimestamp(current_time).strftime("%Y/%m/%d/%H:%M:%S")
                    
                    # 记录API调用（可选）
                    # record = {
                    #     "model": self.model,
                    #     "prompt": full_prompt,
                    #     "response": data,
                    #     "current_time": formatted_time
                    # }
                    # save_path = f"./data/{self.model}/apiRecord.json"
                    # save_data_to_json(record, save_path)

                    t2 = time.time() - t1
                    print(f"********* end call {self.model}: {t2:.2f} *********")
                    
                    return content
                else:
                    print(f"API request failed with status code: {response.status_code}")
                    print(f"Response: {response.text}")
                    
            except Exception as ex:
                print(f"Attempt call {self.model} {retry_count + 1} failed: {ex}")
                time.sleep(300)
                retry_count += 1
        
        return "Failed to generate completion after multiple attempts."


def save_data_to_json(json_data, base_path):
    """保存JSON数据到文件"""
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
    
    print("save json data to path:", base_path)


if __name__ == "__main__":
    # 测试代码
    model = "qwen2.5vl:32b"
    llmapi = VLMAPI(model)
    
    # 测试1: 纯文本请求
    print("=" * 50)
    print("测试1: 纯文本请求")
    print("=" * 50)
    prompt_config = PROMPT_CONFIG.get("vlm_call", {}).get("general", {})
    systext = prompt_config.get("systext", "You are a helpful assistant.")
    usertext = "Hello, can you introduce yourself?"
    
    response = llmapi.vlm_request(systext, usertext)
    print("Response:", response)
    
    # 测试2: 单张图片请求
    print("\n" + "=" * 50)
    print("测试2: 单张图片请求")
    print("=" * 50)
    prompt_config = PROMPT_CONFIG.get("vlm_call", {}).get("image_analysis", {})
    systext = prompt_config.get("systext", "You are a helpful assistant that can analyze images.")
    usertext = prompt_config.get("usertext", "请描述这张图片中你看到了什么？")
    image_path1 = "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Apple_37512a22.png"
    
    response = llmapi.vlm_request(systext, usertext, image_path1=image_path1)
    print("Response:", response)
    
    # 测试3: 两张图片请求
    print("\n" + "=" * 50)
    print("测试3: 两张图片请求")
    print("=" * 50)
    prompt_config = PROMPT_CONFIG.get("vlm_call", {}).get("multi_image_analysis", {})
    systext = prompt_config.get("systext", "You are a helpful assistant that can analyze multiple images.")
    usertext = prompt_config.get("usertext", "请比较这两张图片中的物体，它们有什么相同和不同之处？")
    image_path1 = "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Apple_37512a22.png"
    image_path2 = "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Bread_dca87251.png"
    
    response = llmapi.vlm_request(systext, usertext, image_path1=image_path1, image_path2=image_path2)
    print("Response:", response)
    
    # 测试4: 三张图片请求
    print("\n" + "=" * 50)
    print("测试4: 三张图片请求")
    print("=" * 50)
    prompt_config = PROMPT_CONFIG.get("vlm_call", {}).get("three_image_analysis", {})
    systext = prompt_config.get("systext", "You are a helpful assistant that can analyze multiple images.")
    usertext = prompt_config.get("usertext", "请分析这三张图片中的厨房用品，它们分别是什么？")
    image_path1 = "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Apple_37512a22.png"
    image_path2 = "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Bread_dca87251.png"
    image_path3 = "data/item_image/FloorPlan3_physics/FloorPlan3_physics_Bowl_2813285c.png"
    
    response = llmapi.vlm_request(systext, usertext, image_path1=image_path1, image_path2=image_path2, image_path3=image_path3)
    print("Response:", response) 