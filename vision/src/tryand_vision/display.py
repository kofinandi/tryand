"""Drawing helpers shared by the debug viewer and the examples."""

import cv2

from .detector import TARGET_LABELS, Detection, Result

# BGR colours (OpenCV uses Blue-Green-Red order, not RGB)
COLOURS = {
    Result.NO_OBJECT: (200, 200, 200),  # grey
    Result.BOTTLE: (0, 200, 0),  # green
    Result.NO_BOTTLE: (0, 0, 230),  # red
}
OTHER_OBJECT = (255, 150, 0)  # blue: something YOLO knows that is not a bottle or cup
WHITE = (255, 255, 255)


def _title(result: Result, detections: list[Detection]) -> str:
    """Top-bar text: say which target was seen (CUP or BOTTLE) instead of the enum name."""
    if result is Result.BOTTLE:
        targets = [d for d in detections if d.label in TARGET_LABELS]
        return max(targets, key=lambda d: d.confidence).label.upper() if targets else "BOTTLE / CUP"
    if result is Result.NO_BOTTLE:
        return "NOT A CUP OR BOTTLE"
    return "NO OBJECT"


def draw(frame, result: Result, detections: list[Detection], footer: str = ""):
    """Draw YOLO boxes, the current answer (top bar) and an optional footer text."""
    for d in detections:
        x1, y1, x2, y2 = d.box
        colour = COLOURS[Result.BOTTLE] if d.label in TARGET_LABELS else OTHER_OBJECT
        cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)
        cv2.putText(frame, f"{d.label} {d.confidence:.2f}", (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, colour, 2)
    cv2.rectangle(frame, (0, 0), (frame.shape[1], 50), (0, 0, 0), -1)
    cv2.putText(frame, _title(result, detections), (10, 37), cv2.FONT_HERSHEY_SIMPLEX, 1.2, COLOURS[result], 3)
    if footer:
        h = frame.shape[0]
        cv2.rectangle(frame, (0, h - 50), (frame.shape[1], h), (0, 0, 0), -1)
        cv2.putText(frame, footer, (10, h - 17), cv2.FONT_HERSHEY_SIMPLEX, 0.9, WHITE, 2)
    return frame
