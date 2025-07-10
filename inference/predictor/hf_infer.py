from PIL import Image
from transformers import Qwen2_5_VLForConditionalGeneration, AutoTokenizer, AutoProcessor, Qwen2VLForConditionalGeneration
from qwen_vl_utils import process_vision_info
from .base_infer import BaseServer
from .utils import preprocess_image
import torch
import os
import math
MAX_PIXELS=os.getenv("MAX_PIXELS")
MIN_PIXELS=os.getenv("MIN_PIXELS")
if MAX_PIXELS is None:
    MAX_PIXELS = 180000
if MIN_PIXELS is None:
    MIN_PIXELS = 3136

class HfServer(BaseServer):
    
    def __init__(self, model_type="qwen2_5_vl", model_path="Qwen/Qwen2.5-VL-3B-Instruct"):
        self.model_path = model_path
        self.model_type = model_type
        self.model_example_map = {
            # "qwen_vl_chat": VllmServer.load_qwen_vl_chat,
            "qwen2_vl": HfServer.load_qwen2_vl,
            "qwen2_5_vl": HfServer.load_qwen2_5_vl
        }
        self.llm, self.processor = self.model_example_map[model_type](model_path)

    @staticmethod
    def load_qwen2_5_vl(model_path):
        model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
            model_path, 
            attn_implementation="flash_attention_2",
            torch_dtype=torch.bfloat16, # 'auto'
            device_map="auto"
        )# .eval()

        processor = AutoProcessor.from_pretrained(model_path)
        # The default range for the number of visual tokens per image in the model is 4-16384.
        # You can set min_pixels and max_pixels according to your needs, such as a token range of 256-1280, to balance performance and cost.
        # min_pixels = 256*28*28
        # max_pixels = 1280*28*28
        # processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct", min_pixels=min_pixels, max_pixels=max_pixels)
        return model, processor
    
    @staticmethod
    def load_qwen2_vl(model_path):
        # default: Load the model on the available device(s)
        model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_path, 
            torch_dtype=torch.bfloat16, # "auto", 
            device_map="auto",
            attn_implementation="flash_attention_2", # 节约内存
        ) #.eval()
        processor = AutoProcessor.from_pretrained(model_path)
        
        # The default range for the number of visual tokens per image in the model is 4-16384. You can set min_pixels and max_pixels according to your needs, such as a token count range of 256-1280, to balance speed and memory usage.
        # min_pixels = 256*28*28
        # max_pixels = 1280*28*28
        # processor = AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct", min_pixels=min_pixels, max_pixels=max_pixels)
        return model, processor
    
    def chat(self, inputs, generation_params=None):
        if isinstance(inputs, list):
            messages = inputs[0]["messages"]
        else:
            messages = inputs["messages"]
        if generation_params is None:
            generation_params={"do_sample":True,
                                # "max_length":32768, # defaults to model.config.max_length
                                "max_new_tokens":1024,
                                "temperature":0.6,
                                "top_k":10,
                                "top_p":None,
                                "repetition_penalty":1.1,
                                "length_penalty":1.1,
                                }
            # generation_params={"do_sample":False,
            #                     # "max_length":32768, # defaults to model.config.max_length
            #                     "max_new_tokens":1024,
            #                     "temperature":0.0,
            #                     "top_k":None,
            #                     "top_p":None,
            #                     # "repetition_penalty":1.01,
            #                     # "length_penalty":1.01,
            #                     }
        # messages = [
        #     {
        #         "role": "user",
        #         "content": [
        #             {"type": "image", "image": "data:image;base64,/9j/..."},
        #             {"type": "text", "text": "Describe this image."},
        #         ],
        #     }
        # ]
        text = self.processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        # print(text)
        image_inputs, video_inputs = process_vision_info(messages)
        # print(len(image_inputs),"image_inputs")
        # align training data
        image_inputs = [preprocess_image(img, MAX_PIXELS) for img in image_inputs]
        image_count = len(image_inputs)
        try_num = 0
        ratio = 0
        while True:
            if try_num > 2*image_count:
                return "", 0
            try:
                try_num += 1
                inputs = self.processor(
                    text=[text],
                    images=image_inputs,
                    videos=video_inputs,
                    padding=True,
                    return_tensors="pt",
                ).to(self.llm.device)
                print("input tokens shape:",inputs['input_ids'].shape)
                # Inference: Generation of the output
                with torch.no_grad():
                    generated_ids = self.llm.generate(**inputs, **generation_params)
                break
            except Exception as e:
                print(e)
                print(f"resize image resolution...{try_num}")
                print(f"total images:{len(image_inputs)}")
                # 如果所有的图像分辨率都降低一次了，则删掉前面的messages
                if len(messages) > 2*try_num+2 and ratio==1:
                    messages = messages[2:2*try_num:]
                    text = self.processor.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
                    image_inputs, video_inputs = process_vision_info(messages)
                # 降低第try_num张图片的分辨率,不会降低第1张的分辨率
                elif len(image_inputs) > try_num:
                    image_inputs[try_num] = preprocess_image(image_inputs[try_num], int(MAX_PIXELS)//2)
                    # image_inputs[try_num].resize((image_inputs[try_num].size[0]//2, image_inputs[try_num].size[1]//2),resample=Image.Resampling.NEAREST)                
                    print("image shape:",image_inputs[try_num].size[0],",",image_inputs[try_num].size[1])
                else:
                    ratio = 1
                

        generated_ids_trimmed = [
            out_ids[len(in_ids) :] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )
        print(len(generated_ids_trimmed[0]), output_text)
        return output_text, len(generated_ids_trimmed[0])

    def generate(self, prompt, generation_params):
        pass

# transformers 4.49.0.dev0