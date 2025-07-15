
import json
import os   
from PIL import Image 
import numpy as np
from ai2thor.controller import Controller
import math
import shutil


def get_volume_distance_rate(metadata):
    volumes = []
    objectid2object={}
    for obj in metadata["objects"]:
        objectid2object[obj["objectId"]]=obj
        if obj["objectType"]!="Floor":
            size=obj["axisAlignedBoundingBox"]["size"]
            v=size["x"]*size["y"]*size["z"]
            dx=obj["axisAlignedBoundingBox"]["center"]["x"]
            dz=obj["axisAlignedBoundingBox"]["center"]["z"]
            agentx=metadata["agent"]["position"]["x"]
            agentz=metadata["agent"]["position"]["z"]
            d=math.sqrt((dx-agentx)**2+(dz-agentz)**2)

            sxz = size["x"] * size["z"]
            sxy = size["x"] * size["y"]
            szy = size["y"] * size["z"]
            s = max(sxz, sxy, szy)
            if d != 0: 
                rate = v / d
            else:
                rate = 0 
            rate=v/d
            isnavigable=False
            # if obj["visible"]==True:
            if True:
                if v<0.01:
                    isnavigable=False
                    if s>0.5 and d<10:
                        isnavigable=True
                    elif s>0.15 and d<4:
                        isnavigable=True
                    elif s>0.08 and d<2.5:
                        isnavigable=True 
                    elif v>0.005 and d<2:
                        isnavigable=True 
                    elif v>0.001 and d<1.5:
                        isnavigable=True
                    elif d<1:
                        isnavigable=True
                else:
                    isnavigable=True
                    if rate<=0.02:
                        isnavigable=False
                        if s>0.5 and d<10:
                            isnavigable=True
                        elif s>0.15 and d<4:
                            isnavigable=True
                        elif s>0.08 and d<2.5:
                            isnavigable=True 
                        elif v>0.005 and d<2:
                            isnavigable=True 
                        elif v>0.001 and d<1.5:
                            isnavigable=True
                        elif d<1:
                            isnavigable=True                        
            volumes.append({
                "objectId":obj["objectId"],
                "objectType":obj["objectType"],
                "visible":obj["visible"],
                "volume":v,
                "s":s,
                "distance":d,
                "rate":rate,
                "isnavigable":isnavigable
            })
            sorted_volumes = sorted(volumes, key=lambda v: v["rate"])

    # save_data_to_json(sorted_volumes,"./test/navigable_list.json")
    return sorted_volumes


def get_scene_metadata(scene,base_path):
    controller = Controller(
        agentMode="default", 
        visibilityDistance=1.5,  
        scene=scene,
        gridSize=0.25,  
        snapToGrid=True, 
        rotateStepDegrees=90, 
        renderDepthImage=False,  
        renderInstanceSegmentation=False, 
        width=1024,
        height=1024,
        fieldOfView=145,
    )
    metadata=controller.last_event.metadata
    save_data_to_json(metadata,base_path)
    controller.stop()
    return

def load_json(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: {file_path} not found.")
        return None
    except json.JSONDecodeError:
        print(f"Error: {file_path} is not a valid JSON file.")
        return None

def save_data_to_json(json_data, base_path):
    os.makedirs(os.path.dirname(base_path), exist_ok=True)
    try:
        with open(base_path, "r") as f:
            existing_data = json.load(f)
            if not isinstance(existing_data, list):
                existing_data = []
    except (FileNotFoundError, json.JSONDecodeError):
        existing_data = []

    existing_data.append(json_data)
    with open(base_path, "w") as f:
        json.dump(existing_data, f, indent=4)
    
    print("save json data to path:",base_path)
    return
   
        
def save_image(event, file_path):
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory: {directory}")
        
    frame = event.frame
    if frame.dtype != np.uint8:
        frame = (frame - np.min(frame)) / (np.max(frame) - np.min(frame)) * 255
        frame = frame.astype(np.uint8)
    Image.fromarray(frame).save(file_path)
    print(f"Saved frame as {file_path}.")
    return file_path

def clear_folder(origin_path):
    if os.path.exists(origin_path):
        shutil.rmtree(origin_path)
    os.makedirs(origin_path)