1. We provide `template.yaml` for conveniently setting different training parameters.
2. In our Iterative Training Pipeline stage 3, we will only train the tokens of the reflective trajectory. `git clone -b embodied-reasoner https://github.com/iGangao/LLaMA-Factory.git` is necessary.

> **Note**: In our Iterative Training Pipeline stage 3, we will only train the tokens of the reflective trajectory. For this purpose, we add a special token `<|feedback|>`. You need to modify the `tokenizer_config.json` file under the model path and add `<|feedback|>` token. We provide examples below.
    
```json
{
    "add_prefix_space": false,
    "added_tokens_decoder": {
        "151643": {
        "content": "<|endoftext|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151644": {
        "content": "<|im_start|>",
        "lstrip": false
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151645": {
        "content": "<|im_end|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151646": {
        "content": "<|object_ref_start|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151647": {
        "content": "<|object_ref_end|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151648": {
        "content": "<|box_start|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151649": {
        "content": "<|box_end|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151650": {
        "content": "<|quad_start|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151651": {
        "content": "<|quad_end|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151652": {
        "content": "<|vision_start|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151653": {
        "content": "<|vision_end|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151654": {
        "content": "<|vision_pad|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151655": {
        "content": "<|image_pad|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151656": {
        "content": "<|video_pad|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        },
        "151657": {
        "content": "<|feedback|>",
        "lstrip": false,
        "normalized": false,
        "rstrip": false,
        "single_word": false,
        "special": true
        }
    },
    "additional_special_tokens": ["<|im_start|>", "<|im_end|>", "<|object_ref_start|>","<|object_ref_end|>","<|box_start|>","<|box_end|>","<|quad_start|>","<|quad_end|>","<|vision_start|>","<|vision_end|>","<|vision_pad|>","<|image_pad|>","<|video_pad|>","<|feedback|>"],
    "bos_token": null,
    "chat_template": "{% set image_count = namespace(value=0) %}{% set video_count = namespace(value=0) %}{% for message in messages %}{% if loop.first and message['role'] != 'system' %}<|im_start|>system\nYou are a helpful assistant.<|im_end|>\n{% endif %}<|im_start|>{{ message['role'] }}\n{% if message['content'] is string %}{{ message['content'] }}<|im_end|>\n{% else %}{% for content in message['content'] %}{% if content['type'] == 'image' or 'image' in content or 'image_url' in content %}{% set image_count.value = image_count.value + 1 %}{% if add_vision_id %}Picture {{ image_count.value }}: {% endif %}<|vision_start|><|image_pad|><|vision_end|>{% elif content['type'] == 'video' or 'video' in content %}{% set video_count.value = video_count.value + 1 %}{% if add_vision_id %}Video {{ video_count.value }}: {% endif %}<|vision_start|><|video_pad|><|vision_end|>{% elif 'text' in content %}{{ content['text'] }}{% endif %}{% endfor %}<|im_end|>\n{% endif %}{% endfor %}{% if add_generation_prompt %}<|im_start|>assistant\n{% endif %}",
    "clean_up_tokenization_spaces": false,
    "eos_token": "<|im_end|>",
    "padding_side": "left",
    "errors": "replace",
    "model_max_length": 32768,
    "pad_token": "<|endoftext|>",
    "split_special_tokens": false,
    "tokenizer_class": "Qwen2Tokenizer",
    "unk_token": null
}
```
  
