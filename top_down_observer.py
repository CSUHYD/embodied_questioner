import cv2
import numpy as np
from ai2thor.controller import Controller

def set_top_down_view(controller):
    """
    设置摄像头在房间上方俯瞰视角
    """
    bounds = controller.last_event.metadata["sceneBounds"]["cornerPoints"]
    center_x = sum(p[0] for p in bounds) / 8
    center_z = sum(p[2] for p in bounds) / 8
    max_y = max(p[1] for p in bounds)

    controller.step(
        action="TeleportFull",
        x=center_x,
        y=max_y + 1.5,  # 高于房间上方
        z=center_z,
        rotation={"x": 90, "y": 0, "z": 0},  # 向下看
        horizon=0,
        standing=True,
        forceAction=True
    )
    print(f"设置鸟瞰视角于位置：({center_x:.2f}, {max_y + 1.5:.2f}, {center_z:.2f})")

def main():
    controller = Controller(
        agentMode="default",
        visibilityDistance=3.0,
        scene="FloorPlan1",
        gridSize=0.25,
        snapToGrid=True,
        renderDepthImage=False,
        renderInstanceSegmentation=False,
        width=800,
        height=800,
        fieldOfView=90
    )

    # 等待初始化完成
    controller.step(action="Pass")

    # 设置鸟瞰视角
    set_top_down_view(controller)

    # 显示图像窗口
    cv2.namedWindow("Top Down View")

    while True:
        frame = controller.last_event.frame
        frame_bgr = frame[:, :, ::-1]  # RGB to BGR
        cv2.imshow("Top Down View", frame_bgr)

        key = cv2.waitKey(1)
        if key == ord('q'):
            break

    cv2.destroyAllWindows()
    controller.stop()
    print("仿真结束。")

if __name__ == "__main__":
    main()