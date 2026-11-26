# code to determine which resolutions are supported by the camera

import cv2


COMMON_RESOLUTIONS = [
    (320, 240),
    (640, 480),
    (800, 600),
    (1024, 768),
    (1280, 720),
    (1920, 1080),
    (2560, 1440),
    (3840, 2160),
]


cap = cv2.VideoCapture(0)

if not cap.isOpened():
    raise RuntimeError("Could not open camera.")


for width, height in COMMON_RESOLUTIONS:

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    actual_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

    print(
        f"Requested: {width}x{height}"
        f" | Actual: {int(actual_width)}x{int(actual_height)}"
    )

cap.release()