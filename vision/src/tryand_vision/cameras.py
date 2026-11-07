"""Find which camera index is your iPhone.

On macOS an iPhone shows up as a normal webcam through Continuity Camera.
OpenCV numbers cameras 0, 1, 2, ... but the order is not guaranteed
(the MacBook's built-in camera is often 0, the iPhone often 1).
"""

import cv2


def list_cameras(max_index: int = 6) -> list[tuple[int, int, int]]:
    """Try camera indices 0..max_index-1 and return (index, width, height) for each that works."""
    found = []
    for index in range(max_index):
        cap = cv2.VideoCapture(index)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok:
                h, w = frame.shape[:2]
                found.append((index, w, h))
        cap.release()
    return found


def save_preview(index: int, path: str) -> bool:
    """Grab one frame from camera `index` and save it as an image, so you can see which camera it is."""
    cap = cv2.VideoCapture(index)
    for _ in range(10):  # first frames are often dark while the camera adjusts
        ok, frame = cap.read()
    cap.release()
    if ok:
        cv2.imwrite(path, frame)
    return ok
