"""Pretend to be the control logic, while watching the live video.

Run:  python examples/try_pull.py --camera 0

In the video window (click it first so it gets your key presses):
    SPACE  ask vision "what is on the platform?" (like the control logic would)
    b      take a new background picture (empty the platform first!)
    q      quit

The top bar shows what vision sees *right now* (changes all the time).
The bottom bar shows the answer the "control logic" got when it asked.

Why a helper thread for asking?
    `wait_for_stable()` can wait up to 3 seconds. If we called it here
    directly, the video would freeze while waiting. So the question is asked
    in a separate thread, and the main thread keeps drawing the video.

Good place for a breakpoint: the `answer = ...` line in `ask()`.
"""

import argparse
import threading

import cv2

from tryand_vision.display import draw
from tryand_vision.vision import Vision


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()

    print("Loading camera and YOLO... keep the platform EMPTY.")
    vision = Vision(camera=args.camera).start()

    # What the bottom bar says. A list so the helper thread can change it.
    footer = ["warming up... keep the platform empty"]
    asking = threading.Event()  # set while a question is in progress

    def ask():
        footer[0] = "asking... (waiting until the picture is steady)"
        answer = vision.wait_for_stable(frames=8, timeout=3)
        if answer is None:
            footer[0] = "answer: None (kept changing, e.g. hand in view)"
        else:
            footer[0] = f"answer: {answer.name}"
        print(footer[0])
        asking.clear()

    try:
        ready_announced = False
        while True:
            vision.classify()  # raises if the vision thread crashed
            if not ready_announced and vision.is_ready:
                footer[0] = "ready - put something down, press SPACE"
                print("Ready. Click the video window, press SPACE to ask, q to quit.")
                ready_announced = True

            frame, result, detections = vision.latest_frame()
            if frame is not None:
                cv2.imshow("try pull", draw(frame, result, detections, footer[0]))

            key = cv2.waitKey(10) & 0xFF
            if key == ord("q"):
                break
            if key == ord(" ") and ready_announced and not asking.is_set():
                asking.set()
                threading.Thread(target=ask, daemon=True).start()
            if key == ord("b"):
                vision.recapture_background()
                footer[0] = "background re-captured"
    finally:
        vision.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
