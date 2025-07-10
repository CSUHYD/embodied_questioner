import cv2
import time
import numpy as np
from ai2thor.controller import Controller
from data_engine.baseAgent import BaseAgent  # 或 from data_engine.RocAgent import RocAgent

# 初始化 AI2-THOR 控制器
controller = Controller(
    agentMode="default",
    visibilityDistance=1.5,
    scene="FloorPlan1",
    gridSize=0.05,
    snapToGrid=False,
    renderDepthImage=False,
    renderInstanceSegmentation=False,
    width=800,
    height=800,
    fieldOfView=90
)

is_third_person = False
last_mouse_pos = None
mouse_dragging = False
yaw = controller.last_event.metadata["agent"]["rotation"]["y"]
pitch = 0

# 初始化 agent
agent = BaseAgent(controller)  # 这里根据你的实际 agent 构造参数填写

# 键盘动作映射
key_action_map = {
    ord('w'): "forward",
    ord('s'): "backward",
    ord('a'): "left",
    ord('d'): "right",
    ord('t'): "third_person",
    ord('f'): "first_person",
    ord('e'): "pickup",
    ord('r'): {"action": "DropHeldObject"},
    ord('p'): "save_frame",
    ord('q'): "quit"
}

# ---------- 功能函数 ----------

def draw_object_bboxes(frame, event):
    for obj in event.metadata["objects"]:
        if obj["visible"] and obj.get("boundingBox"):
            bb = obj["boundingBox"]
            x1, y1 = int(bb["x1"]), int(bb["y1"])
            x2, y2 = int(bb["x2"]), int(bb["y2"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, obj["objectType"], (x1, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

def switch_to_third_person():
    global is_third_person
    is_third_person = True
    agent = controller.last_event.metadata["agent"]
    x, y, z = agent["position"].values()
    rotation_y = agent["rotation"]["y"]
    controller.step(
        action="TeleportFull",
        x=x - 1.0,
        y=y + 1.0,
        z=z,
        rotation={"x": 30, "y": rotation_y, "z": 0},
        horizon=30,
        standing=True,
        forceAction=True
    )

def switch_to_first_person():
    global is_third_person
    is_third_person = False
    agent = controller.last_event.metadata["agent"]
    controller.step(
        action="TeleportFull",
        **agent["position"],
        rotation=agent["rotation"],
        horizon=0,
        standing=True,
        forceAction=True
    )

def find_nearest_pickupable(event):
    min_dist = float('inf')
    nearest_obj = None
    agent_pos = event.metadata["agent"]["position"]
    for obj in event.metadata["objects"]:
        if obj.get("pickupable") and obj["visible"]:
            obj_pos = obj["position"]
            dist = ((obj_pos["x"] - agent_pos["x"])**2 + (obj_pos["z"] - agent_pos["z"])**2)**0.5
            if dist < min_dist:
                min_dist = dist
                nearest_obj = obj["objectId"]
    return nearest_obj

def move_agent(step_size, lateral=False):
    agent = controller.last_event.metadata["agent"]
    x, y, z = agent["position"].values()
    yaw = agent["rotation"]["y"]
    rad = yaw * np.pi / 180

    if lateral:
        dx = step_size * np.cos(rad)
        dz = -step_size * np.sin(rad)
    else:
        dx = step_size * np.sin(rad)
        dz = step_size * np.cos(rad)

    controller.step(
        action="TeleportFull",
        x=x + dx,
        y=y,
        z=z + dz,
        rotation=agent["rotation"],
        horizon=agent["cameraHorizon"],
        standing=True,
        forceAction=True
    )

def handle_action(key, frame_bgr):
    global yaw, pitch
    action = key_action_map.get(key)
    if action == "quit":
        return False
    elif action == "third_person":
        switch_to_third_person()
    elif action == "first_person":
        switch_to_first_person()
    elif action == "save_frame":
        filename = f"thor_view_{int(time.time())}.png"
        cv2.imwrite(filename, frame_bgr)
        print(f"保存帧至 {filename}")
    elif action == "forward":
        move_agent(0.05)
    elif action == "backward":
        move_agent(-0.05)
    elif action == "left":
        move_agent(-0.05, lateral=True)
    elif action == "right":
        move_agent(0.05, lateral=True)
    elif action == "pickup":
        obj_id = find_nearest_pickupable(controller.last_event)
        if obj_id:
            controller.step(action="PickupObject", objectId=obj_id)
            print(f"尝试抓取：{obj_id}")
        else:
            print("附近没有可抓取物体。")
    elif isinstance(action, dict):
        controller.step(**action)
    else:
        print(f"无绑定动作的按键: {chr(key)}")
    return True

def update_view_with_mouse():
    global yaw, pitch
    try:
        import pyautogui
        # 在macOS上，可能需要禁用pyautogui的failsafe
        pyautogui.FAILSAFE = False
    except ImportError:
        # 如果没有安装pyautogui，则跳过鼠标视角更新
        return

    # 获取窗口在屏幕上的位置
    rect = cv2.getWindowImageRect(WINDOW_NAME)
    if rect[2] < 0 or rect[3] < 0: # 窗口最小化时 rect 的 w,h 为 -1
        return
    x, y = rect[:2]
    
    # 获取鼠标在屏幕上的绝对位置
    mouse_screen_x, mouse_screen_y = pyautogui.position()

    # 计算鼠标相对于窗口中心的偏移量
    dx = mouse_screen_x - (x + CENTER_X)
    dy = mouse_screen_y - (y + CENTER_Y)

    # 若鼠标没有明显移动，跳过
    if abs(dx) < 1 and abs(dy) < 1:
        return

    # 更新 yaw 和 pitch
    yaw += dx * SENSITIVITY
    pitch = max(-60, min(60, pitch + dy * SENSITIVITY))

    # 获取当前位置，改变朝向
    agent = controller.last_event.metadata["agent"]
    controller.step(
        action="TeleportFull",
        **agent["position"],
        rotation={"x": 0, "y": yaw, "z": 0},
        horizon=pitch,
        standing=True,
        forceAction=True
    )

    # 将鼠标重置到窗口中心
    pyautogui.moveTo(x + CENTER_X, y + CENTER_Y)


# ---------- 主程序 ----------

# 设置窗口大小 & 中心位置
WINDOW_NAME = "AI2-THOR View"
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800
CENTER_X = WINDOW_WIDTH // 2
CENTER_Y = WINDOW_HEIGHT // 2

cv2.namedWindow(WINDOW_NAME)
cv2.moveWindow(WINDOW_NAME, 100, 100)  # 可选：设置窗口初始位置

# 初始化视角状态
yaw = controller.last_event.metadata["agent"]["rotation"]["y"]
pitch = controller.last_event.metadata["agent"]["cameraHorizon"]

# 设定灵敏度
SENSITIVITY = 0.15


while True:
    event = controller.last_event
    frame = event.frame.copy()
    draw_object_bboxes(frame, event)
    frame_bgr = frame[:, :, ::-1]
    cv2.imshow("AI2-THOR View", frame_bgr)
    update_view_with_mouse()

    key = cv2.waitKey(1) & 0xFF
    if key != 255:
        if not handle_action(key, frame_bgr):
            break

cv2.destroyAllWindows()
controller.stop()
print("仿真结束，资源已释放。")
