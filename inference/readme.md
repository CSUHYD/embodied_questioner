# 本地部署vlm
    ``` shell
        python ./local_deploy.py --frame "hf" --model_type "qwen2_5_vl" --model_name ""
    ```
# 通过请求调用vlm
    ``` python
        import copy, base64
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

        def prepare_local_messages(data):
            for d in data:
                index = -1
                messages = []
                for line in d["messages"]:
                    if "<image>" in line["content"]:
                        index += 1
                        count = line["content"].count('<image>')
                        user_text = line["content"].replace("<image>","")
                        content = []
                        for i in range(count):
                            content.append({"type": "image","image": d["images"][index]})
                            index += 1
                        content.append({"type": "text", "text": user_text})
                        line["content"] = content
            return data

        import requests
        import json
        test_demo=[{
            "messages":[
                {"role":"user", "content": "<image>What is the content of each image?"}
            ],
            "images":[
                "xxx",
            ]
        }]
        messages = prepare_deploy_messages(test_demo[0])
        data = {
            "messages": messages,
        }

        url = "http://127.0.0.1:10000/chat"
        response = requests.post(url, json=data)
        print(response.json())
    ```