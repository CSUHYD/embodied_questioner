import ai2thor.server
from typing import List, Dict, Tuple
import re
# from .prompt import INSTRUCTION2ITEM_PROMPT
import openai
import cv2

class EventObject:
    @staticmethod
    def get_objects_type(event) -> List[str]:
        objects = event.metadata["objects"]
        return [obj["objectType"] for obj in objects]

    @staticmethod
    def get_objects(event) -> Tuple[List[dict], Dict[str, dict]]:
        item2object = {}
        objects = event.metadata["objects"]
        for item in objects:
            item2object[item["name"]] = item
        return objects, item2object
    
    @staticmethod
    def get_object_by_id(event, obj_id):
        objects = event.metadata["objects"]
        for obj in objects:
            if obj["objectId"] == obj_id:
                return obj
        return None
    
    @staticmethod
    def get_all_item_position(event) -> dict:
        item2position = {}
        objects = event.metadata["objects"]
        for item in objects:
            item2position[item["name"]] = item["position"]
        return item2position     

    @staticmethod
    def get_visible_objects(event) -> Tuple[List[dict],List[dict]]:
        objects = event.metadata["objects"]
        return [obj['name'] for obj in objects if obj["visible"]], [obj for obj in objects if obj["visible"]]

    @staticmethod
    def get_isInteractable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isInteractable"]]

    @staticmethod
    def get_receptacle_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["receptacle"]]

    @staticmethod
    def get_toggleable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["toggleable"]]

    @staticmethod
    def get_breakable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["breakable"]]

    @staticmethod
    def get_isToggled_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isToggled"]]

    @staticmethod
    def get_isBroken_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isBroken"]]

    @staticmethod
    def get_canFillWithLiquid_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["canFillWithLiquid"]]

    @staticmethod
    def get_isFilledWithLiquid_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isFilledWithLiquid"]]

    @staticmethod
    def get_fillLiquid_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["fillLiquid"]]

    @staticmethod
    def get_dirtyable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["dirtyable"]]

    @staticmethod
    def get_isDirty_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isDirty"]]

    @staticmethod
    def get_canBeUsedUp_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["canBeUsedUp"]]

    @staticmethod
    def get_isUsedUp_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isUsedUp"]]

    @staticmethod
    def get_cookable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["cookable"]]

    @staticmethod
    def get_isCooked_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isCooked"]]

    @staticmethod
    def get_isHeatSource_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isHeatSource"]]

    @staticmethod
    def get_isColdSource_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isColdSource"]]

    @staticmethod
    def get_sliceable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["sliceable"]]

    @staticmethod
    def get_openable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["openable"]]

    @staticmethod
    def get_isOpen_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isOpen"]]

    @staticmethod
    def get_pickupable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["pickupable"]]

    @staticmethod
    def get_isPickedUp_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isPickedUp"]]

    @staticmethod
    def get_moveable_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["moveable"]]
    
    @staticmethod
    def get_isMoving_objects(event, ) -> List[dict]:
        objects = event.metadata["objects"]
        return [obj for obj in objects if obj["isMoving"]]
    
    @staticmethod
    def get_object_color(event, object_id: str) -> str:
        object2color = event.object_id_to_color
        return object2color.get(object_id, "")
    
    @staticmethod
    def get_color_object(event, color: str):
        color2object = event.color_to_object_id
        return color2object.get(color, "")

    @staticmethod
    def get_item_mass(event, item_name: str) -> float:
        objects = event.metadata["objects"]
        for item in objects:
            if item["name"] == item_name:
                return item["mass"]
        return 0.0
    
    @staticmethod
    def get_item_volume(event, item_name: str) -> float:
        objects = event.metadata["objects"]
        for item in objects:
            if item["name"] == item_name:
                item_size = item["axisAlignedBoundingBox"]["size"]
                return round(item_size["x"] * item_size["y"] * item_size["z"], 4)
        return 0.0
    
    @staticmethod
    # 获取物品平面面积
    def get_item_surface_area(event, item_name: str) -> float:
        objects = event.metadata["objects"]
        for item in objects:
            if item["name"] == item_name:
                item_size = item["axisAlignedBoundingBox"]["size"]
                x = item_size["x"]
                y = item_size["y"]
                z = item_size["z"]
                max_surface= max(x*y, x*z, y*z)
                return round(max_surface, 4)
        return 0.0
    
    @staticmethod
    def get_item_position(event, item_name: str) -> dict:
        objects = event.metadata["objects"]
        for item in objects:
            if item["name"] == item_name:
                return item["position"]
        return {}
    
    @staticmethod
    def get_item_orientation(event, item_name: str) -> dict:
        objects = event.metadata["objects"]
        for item in objects:
            if item["name"] == item_name:
                return item["rotation"]
        return {}

def add_text_to_image(image, text, position):
    """
    在图像上添加指定的文字。
    
    :param image: 要添加文字的图像。
    :param text: 要添加的文字内容。
    :param position: 文字左下角在图像中的位置 (x, y)。
    :return: 添加了文字后的图像。
    """
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 3 # 字体大小
    font_color = (255, 0, 0)  # BGR颜色，这里设置为蓝色
    thickness = 3 # 字体粗细

    return cv2.putText(image, text, position, font, font_scale, font_color, thickness)

def add_border(image, border_size, border_color):
    """
    给图像添加边框。
    
    :param image: 输入图像。
    :param border_size: 边界大小（像素）。
    :param border_color: 边界的颜色 (B, G, R)。
    :return: 添加了边框的图像。
    """
    return cv2.copyMakeBorder(image, 0, 0, border_size, border_size, cv2.BORDER_CONSTANT, value=border_color)