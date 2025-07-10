import cv2
import numpy as np

print("Press keys (ESC to exit):")

while True:
    img = 255 * np.ones((100, 400, 3), dtype=np.uint8)
    cv2.imshow("Key Test", img)
    k = cv2.waitKey(0)
    print(f"Key pressed: {k}")
    if k == 27:  # ESC
        break