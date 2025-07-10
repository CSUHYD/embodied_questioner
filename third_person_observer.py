import cv2
import time
import math
from ai2thor.controller import Controller
from data_engine.RocAgent import RocAgent
import threading

def setup_third_person_camera(controller):
    """
    自动选择四个角点中距离最近的可达点，设置摄像头在该点正上方（y+1.5），
    rotation为x=45，y指向房间中心。
    """
    scene_bounds = controller.last_event.metadata['sceneBounds']
    corner_points = [scene_bounds['cornerPoints'][2], scene_bounds['cornerPoints'][3], scene_bounds['cornerPoints'][6], scene_bounds['cornerPoints'][7]]
    reachable_positions = controller.step(dict(action='GetReachablePositions')).metadata['actionReturn']
    min_distance = float('inf')
    target_position = None
    corner_index = 0
    for i, scene_bounds_corner in enumerate(corner_points):
        for position in reachable_positions:
            distance = ((position['x'] - scene_bounds_corner[0]) ** 2 + (position['z'] - scene_bounds_corner[2]) ** 2) ** 0.5
            if distance < min_distance:
                min_distance = distance
                target_position = position
                corner_index = i
    center = scene_bounds['center']
    dx = center['x'] - target_position['x']
    dz = center['z'] - target_position['z']
    yaw = (math.degrees(math.atan2(dx, dz))) % 360
    third_person_camera_position = {
        'x': target_position['x'],
        'y': target_position['y'] + 1.5,
        'z': target_position['z']
    }
    third_person_camera_rotation = {'x': 45, 'y': yaw, 'z': 0}
    third_person_camera_fov = 90
    controller.step(dict(
        action='AddThirdPartyCamera',
        position=third_person_camera_position,
        rotation=third_person_camera_rotation,
        fieldOfView=third_person_camera_fov
    )) 


# 初始化 AI2-THOR 控制器
controller = Controller(
    agentMode="default",
    visibilityDistance=1.5,
    scene="FloorPlan3",
    gridSize=0.05,
    snapToGrid=False,
    renderDepthImage=False,
    renderInstanceSegmentation=False,
    width=800,
    height=800,
    fieldOfView=90
)

# 初始化 RocAgent
agent = RocAgent(controller)

# 设置第三人称初始视角（可选 edge/corner）
agent.get_corner_init_view()  # 或 agent.get_edge_init_view()

# 设置第三人称摄像头
setup_third_person_camera(controller)

WINDOW_NAME_FP = "AI2-THOR First Person View"
WINDOW_NAME_TP = "AI2-THOR Top-down Camera"
cv2.namedWindow(WINDOW_NAME_FP)
cv2.moveWindow(WINDOW_NAME_FP, 100, 100)
cv2.namedWindow(WINDOW_NAME_TP)
cv2.moveWindow(WINDOW_NAME_TP, 950, 100)

# 键盘控制映射
key_action_map = {
    ord('w'): lambda: agent.action.action_mapping["move_ahead"](controller, 0.25),
    ord('a'): lambda: agent.action.action_mapping["rotate_left"](controller, 30),
    ord('d'): lambda: agent.action.action_mapping["rotate_right"](controller, 30),
    ord('s'): lambda: agent.action.action_mapping["move_back"](controller, 0.25),
    ord('q'): "quit",
    ord('i'): "get_all_item_image"
}

# 标记采集状态
gathering_images = False

def gather_images_thread(agent):
    global gathering_images
    gathering_images = True
    print("正在采集所有物品图片，请稍候……")
    agent.get_all_item_image()
    print("采集完成！")
    gathering_images = False

def exec_example(agent):
    agent.put_tomato_on_plate()

while True:
    # 获取当前第三人称视角画面
    frame = controller.last_event.frame.copy()
    frame_bgr = frame[:, :, ::-1]
    cv2.imshow(WINDOW_NAME_FP, frame_bgr)

    # 获取第三人称摄像头画面（俯视）
    if hasattr(controller.last_event, 'third_party_camera_frames') and len(controller.last_event.third_party_camera_frames) > 0:
        tp_frame = controller.last_event.third_party_camera_frames[0]
        tp_frame_bgr = tp_frame[:, :, ::-1]
        cv2.imshow(WINDOW_NAME_TP, tp_frame_bgr)

    key = cv2.waitKey(1) & 0xFF
    if key in key_action_map:
        action = key_action_map[key]
        if action == "quit":
            break
        elif action == "get_all_item_image":
            if not gathering_images:
                # t = threading.Thread(target=gather_images_thread, args=(agent,))
                t = threading.Thread(target=exec_example, args=(agent,))
                t.start()
            else:
                print("采集正在进行中，请稍候……")
        else:
            action()

cv2.destroyAllWindows()
controller.stop()
print("仿真结束，资源已释放。")