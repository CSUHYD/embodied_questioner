import http.client
import json
import random

import base64
from datetime import datetime
from PIL import Image
import io
import time


from VLMCallapi_keys import api_keys
# you can add your api_key in VLMCallapi_keys.py
    
class VLMRequestError(Exception):
    pass  

class VLMAPI:
    def __init__(self,model):#gpt-4o-2024-11-20,gpt-4o-mini
        self.model=model
        

    def encode_image(self, image_path):
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
        payload_data = [
            {
                "type": "text",
                "text": usertext
            },
        ]

        if image_path1:
            base64_image1 = self.encode_image(image_path1)
            payload_data.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image1}",
                        "detail": "low"
                    }
                }
            )
        if image_path2:
            base64_image2 = self.encode_image(image_path2)
            payload_data.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image2}",
                        "detail": "low"
                    }
                }
            )
        if image_path3:
            base64_image3 = self.encode_image(image_path3)
            payload_data.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_image3}",
                        "detail": "low"
                    }
                }
            )
        
        messages=[
                    {
                        "role": "system",
                        "content": systext
                    },
                    {
                        "role": "user",
                        "content": payload_data
                    }
                ]
        
         
        payload = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "messages": messages,
                "temperature": 0.9,
                "max_tokens": max_tokens
            }
        )
        
        conn = http.client.HTTPSConnection("us.ifopen.ai")
        
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
                print(f"********* start call {self.model} *********")
                
                test=conn.request("POST", "/v1/chat/completions", payload, headers)

                res = conn.getresponse()

                data = res.read()
                data=data.decode("utf-8")
                data_dict = json.loads(data)
                content = data_dict["choices"][0]["message"]["content"]

                current_time = int(datetime.now().timestamp())  
                formatted_time = datetime.utcfromtimestamp(current_time).strftime("%Y/%m/%d/%H:%M:%S")
                # record = {
                #     "model":self.model,
                #     "messages":messages,
                #     "response": data_dict,
                #     "current_time": formatted_time
                # }
                # save_path=f"./data/{self.model}/apiRecord.json"
                # save_data_to_json(record, save_path)

                t2=time.time()-t1
                print("****** content: \n",content)
                print(f"********* end call {self.model}: {t2:.2f} *********")
                
                return content
            except Exception as ex:
                print(f"Attempt call {self.model} {retry_count + 1} failed: {ex}")
                time.sleep(300)
                retry_count += 1
        
        return "Failed to generate completion after multiple attempts."




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
    model="gpt-4o-2024-11-20"
    llmapi=VLMAPI(model)
