import copy, base64
import math
from PIL import Image

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def preprocess_image(image: Image, image_resolution=180000) -> Image:
    r"""
    Pre-processes a single image. for qwen2-vl
    """
    image_resolution: int = int(image_resolution)
    # print("predictor:utils:preprocess_image:MAX_PIXELS:",image_resolution)
    print("predictor:utils:preprocess_image:image.width:",image.width)
    print("predictor:utils:preprocess_image:image.height:",image.height)
    # print("predictor:utils:preprocess_image:image.mode:",image.mode)
    if (image.width * image.height) > image_resolution:
        resize_factor = math.sqrt(image_resolution / (image.width * image.height))
        width, height = int(image.width * resize_factor), int(image.height * resize_factor)
        image = image.resize((width, height), resample=Image.Resampling.NEAREST)

    if image.mode != "RGB":
        image = image.convert("RGB")

    if min(image.width, image.height) < 28:
        width, height = max(image.width, 28), max(image.height, 28)
        image = image.resize((width, height), resample=Image.Resampling.NEAREST)

    if image.width / image.height > 200:
        width, height = image.height * 180, image.height
        image = image.resize((width, height), resample=Image.Resampling.NEAREST)

    if image.height / image.width > 200:
        width, height = image.width, image.width * 180
        image = image.resize((width, height), resample=Image.Resampling.NEAREST)
    print("predictor:utils:preprocess_image:image.width:",image.width)
    print("predictor:utils:preprocess_image:image.height:",image.height)
    return image


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
