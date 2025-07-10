"""
This example shows how to use vLLM for running offline inference with
multi-image input on vision language models for text generation,
using the chat template defined by the model.
"""
from argparse import Namespace
from typing import List, NamedTuple, Optional

from PIL.Image import Image
from transformers import AutoProcessor, AutoTokenizer
from .base_infer import BaseServer
from vllm import LLM, SamplingParams
from vllm.multimodal.utils import fetch_image
from qwen_vl_utils import process_vision_info
from .utils import preprocess_image
# from vllm.utils import FlexibleArgumentParser
import os, torch
TP = len(os.getenv("CUDA_VISIBLE_DEVICES").split(",")) if os.getenv("CUDA_VISIBLE_DEVICES") else 1
print("TP:",TP)
MAX_PIXELS=os.getenv("MAX_PIXELS")
MIN_PIXELS=os.getenv("MIN_PIXELS")
GMU=os.getenv("GMU")
print("gmu",GMU,type(GMU))
if MAX_PIXELS is None:
    MAX_PIXELS = 180000
if MIN_PIXELS is None:
    MIN_PIXELS = 3136
# export VLLM_WORKER_MULTIPROC_METHOD=spawn
# torch.multiprocessing.set_start_method('spawn')
# import multiprocessing as mp
# try:
#    mp.set_start_method('spawn', force=True)
#    print("spawned")
# except RuntimeError:
#    pass
# import multiprocessing
# multiprocessing.set_start_method('spawn')
# NOTE: The default `max_num_seqs` and `max_model_len` may result in OOM on
# lower-end GPUs.
# Unless specified, these settings have been tested to work on a single L4.

class VllmServer(BaseServer):
    
    def __init__(self, model_type="qwen2_vl", model_name=""):
        self.model_type = model_type
        self.model_name = model_name
        self.model_example_map = {
            "qwen_vl_chat": VllmServer.load_qwen_vl,
            "qwen2_vl": VllmServer.load_qwen2_vl,
            "qwen2_5_vl": VllmServer.load_qwen2_5_vl,
        }
        self.llm, self.processor = self.model_example_map[model_type](model_name)

    def chat_0(self, inputs, generation_params=None):
        if generation_params is None:
            sampling_params = SamplingParams(
                temperature=0.0, max_tokens=512, stop_token_ids=[])
        else:
            sampling_params = SamplingParams(**generation_params)
        if not isinstance(inputs, list):
            inputs = [inputs]
        '''inputs:
        [
            {
                "messages":[
                    {
                        "role": "system",
                        "content": "You are a robot decision-making assistant and you may need to observe, plan and think before making each decision."
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image": "image_url"},
                            {"type": "text", "text": user_text},
                        ]
                    },
                ]
            }
        ]
        '''
        outputs = self.llm.chat(inputs, sampling_params=sampling_params)
        results = []
        print(outputs[0])
        results = [o.outputs[0].text for o in outputs]
        return results

    def chat(self, inputs, generation_params=None):
        if generation_params is None:
            sampling_params = SamplingParams(
                temperature=0.6, max_tokens=1024, top_k=10, repetition_penalty=1.1, )#stop_token_ids=[]
            sampling_params = SamplingParams(
                temperature=0.0, max_tokens=1024,)#stop_token_ids=[]
            
        else:
            sampling_params = SamplingParams(**generation_params)
        
        if not isinstance(inputs, list):
            inputs = [inputs]
        '''inputs:
            [
                {
                    "messages":[
                        {
                            "role": "system",
                            "content": "You are a robot decision-making assistant and you may need to observe, plan and think before making each decision."
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "image": "encode"},
                                {"type": "text", "text": user_text},
                            ]
                        },
                    ]
                }
            ]
        '''
        prompts = []
        for line in inputs:
            messages = line["messages"]
            prompt = self.processor.apply_chat_template(
                                                messages,
                                                tokenize=False,
                                                add_generation_prompt=True)
        
            image_data, _ = process_vision_info(messages)
            image_data = [preprocess_image(img, MAX_PIXELS) for img in image_data]
            dic= {"prompt": prompt, "multi_modal_data": {"image": image_data}}
            prompts.append(dic)
            
        image_count = len(image_data)

        try_num = 0
        ratio=0
        while True:
            if try_num > 2*image_count:
                return "", 0
            try:
                try_num+=1
                outputs = self.llm.generate(prompts, sampling_params=sampling_params)
                break
            except Exception as e:
                print(e)
                print(f"resize image resolution...{try_num}")
                print(f"total images:{len(image_data)}")
                if ratio ==1:
                    prompts = []
                    for line in inputs:
                        messages = line["messages"]
                        if len(messages) > 2*try_num+2:
                            messages = messages[2:2*try_num:]
                        prompt = self.processor.apply_chat_template(
                                                            messages,
                                                            tokenize=False,
                                                            add_generation_prompt=True)
                    
                        image_data, _ = process_vision_info(messages)
                        image_data = [preprocess_image(img, int(MAX_PIXELS)//2) for img in image_data]
                        dic= {"prompt": prompt, "multi_modal_data": {"image": image_data}}
                        prompts.append(dic)
                else:
                    for prompt in prompts:
                        multi_modal_data = prompt["multi_modal_data"]
                        image_data = multi_modal_data["image"]
                        if len(image_data) > try_num:
                            image_data[try_num] = preprocess_image(image_data[try_num], int(MAX_PIXELS)//2)
                        else:
                            ratio = 1
                        prompt["multi_modal_data"]["image"] = image_data

        print(len(outputs[0].outputs[0].token_ids), outputs[0].outputs[0].text)
        results = [o.outputs[0].text for o in outputs]

        return results, len(outputs[0].outputs[0].token_ids)

    def generate(self, inputs, generation_params=None):
        if generation_params is None:
            sampling_params = SamplingParams(
                temperature=0.0, max_tokens=512, stop_token_ids=[])
        else:
            sampling_params = SamplingParams(**generation_params)
        
        try:
            from qwen_vl_utils import process_vision_info
        except ModuleNotFoundError:
            print('WARNING: `qwen-vl-utils` not installed, input images will not '
                'be automatically resized. You can enable this functionality by '
                '`pip install qwen-vl-utils`.')
            process_vision_info = None
        if not isinstance(inputs, list):
            inputs = [inputs]
        '''inputs:
            [
                {
                    "messages":[
                        {
                            "role": "system",
                            "content": "You are a robot decision-making assistant and you may need to observe, plan and think before making each decision."
                        },
                        {
                            "role": "user",
                            "content": [
                                {"type": "image", "image": "encode"},
                                {"type": "text", "text": user_text},
                            ]
                        },
                    ]
                }
            ]
        '''
        prompts = []
        for line in inputs:
            messages = line["messages"]
            prompt = self.processor.apply_chat_template(
                                                messages,
                                                tokenize=False,
                                                add_generation_prompt=True)
        
            if process_vision_info is None:
                image_data = [fetch_image(url) for url in line["images"]]
            else:
                image_data, _ = process_vision_info(messages)

            dic= {"prompt": prompt, "multi_modal_data": {"image": image_data}}
            
            prompts.append(dic)

        outputs = self.llm.generate(prompts, sampling_params=sampling_params)
        print(outputs[0])
        results = [o.outputs[0].text for o in outputs]

        return results

    @staticmethod
    def load_qwen_vl(question: str, image_urls: List[str]):
        model_name = "Qwen/Qwen-VL-Chat"
        llm = LLM(
            model=model_name,
            trust_remote_code=True,
            max_model_len=1024,
            max_num_seqs=2,
            limit_mm_per_prompt={"image": len(image_urls)},
        )
        placeholders = "".join(f"Picture {i}: <img></img>\n"
                            for i, _ in enumerate(image_urls, start=1))

        # This model does not have a chat_template attribute on its tokenizer,
        # so we need to explicitly pass it. We use ChatML since it's used in the
        # generation utils of the model:
        # https://huggingface.co/Qwen/Qwen-VL-Chat/blob/main/qwen_generation_utils.py#L265
        tokenizer = AutoTokenizer.from_pretrained(model_name,
                                                trust_remote_code=True)

        # Copied from: https://huggingface.co/docs/transformers/main/en/chat_templating
        chat_template = "{% if not add_generation_prompt is defined %}{% set add_generation_prompt = false %}{% endif %}{% for message in messages %}{{'<|im_start|>' + message['role'] + '\n' + message['content'] + '<|im_end|>' + '\n'}}{% endfor %}{% if add_generation_prompt %}{{ '<|im_start|>assistant\n' }}{% endif %}"  # noqa: E501

        messages = [{'role': 'user', 'content': f"{placeholders}\n{question}"}]
        prompt = tokenizer.apply_chat_template(messages,
                                            tokenize=False,
                                            add_generation_prompt=True,
                                            chat_template=chat_template)

        stop_tokens = ["<|endoftext|>", "<|im_start|>", "<|im_end|>"]
        stop_token_ids = [tokenizer.convert_tokens_to_ids(i) for i in stop_tokens]

        return None

    @staticmethod
    def load_qwen2_vl(model_name):
        llm = LLM(
            model=model_name,
            tokenizer=model_name,
            max_model_len=32768, # if process_vision_info is None else 10240,
            # max_num_seqs=5,
            # limit_mm_per_prompt={"image": len(image_urls)},
            tensor_parallel_size=1,
            gpu_memory_utilization=0.8,
            swap_space=8,
            cpu_offload_gb=8,
            trust_remote_code=True,
            limit_mm_per_prompt={"image": 32}
        )
        processor = AutoProcessor.from_pretrained(model_name)

        return llm, processor

    @staticmethod
    def load_qwen2_5_vl(model_name):
        llm = LLM(
            model=model_name,
            tokenizer=model_name,
            max_model_len=32768, # if process_vision_info is None else 10240,
            # max_num_seqs=5,
            # limit_mm_per_prompt={"image": len(image_urls)},
            tensor_parallel_size=TP,
            gpu_memory_utilization=0.8,
            trust_remote_code=True,
            limit_mm_per_prompt={"image": 32}
        )
        processor = AutoProcessor.from_pretrained(model_name)

        return llm, processor