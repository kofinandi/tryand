"""Debug viewer: watch what the vision part sees and answers.

This does NOT control the machine. The control logic (separate code on the Mac)
uses `tryand_vision.vision.Vision` directly. Use this viewer to set up the
camera and tune the settings.

Keys in the video window:
    q  quit
    b  re-capture the background (take everything off the platform first!)
    s  save the current frame to vision/data/ (useful to collect test images)
"""

import argparse
import time
from pathlib import Path

import cv2

from .cameras import list_cameras, save_preview
from .display import draw

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def main() -> None:
    parser = argparse.ArgumentParser(prog="tryand_vision")
    parser.add_argument("--camera", type=int, default=0, help="camera index (see --list-cameras)")
    parser.add_argument("--list-cameras", action="store_true",
                        help="list available cameras, save a preview image of each, and exit")
    parser.add_argument("--model", default="yolo11n.pt", help="YOLO model file")
    parser.add_argument("--confidence", type=float, default=0.4,
                        help="minimum YOLO confidence (0-1) to accept a detection")
    parser.add_argument("--min-area", type=float, default=0.01,
                        help="fraction of the image that must change to count as an object")
    parser.add_argument("--show-mask", action="store_true",
                        help="also show the black/white background-difference image")
    args = parser.parse_args()

    if args.list_cameras:
        DATA_DIR.mkdir(exist_ok=True)
        cams = list_cameras()
        if not cams:
            print("No cameras found. Check System Settings > Privacy & Security > Camera.")
        for index, w, h in cams:
            path = DATA_DIR / f"camera_{index}.jpg"
            save_preview(index, str(path))
            print(f"camera {index}: {w}x{h}  preview saved to {path}")
        return

    from .vision import Vision  # imported here so --list-cameras doesn't load YOLO

    print("Loading YOLO model (downloads on first run)...")
    vision = Vision(args.camera, args.model, args.confidence, args.min_area)
    vision.start()
    print("Keep the platform empty for 2 seconds...")

    last_printed = None
    last_count = -1
    try:
        while True:
            # Windows must be drawn from the main thread on macOS, so the
            # viewer runs here and just *reads* what the vision thread produced.
            vision.classify()  # raises if the vision thread crashed
            frame, result, detections = vision.latest_frame()
            if frame is not None and vision.frame_count != last_count:
                last_count = vision.frame_count
                if result != last_printed:
                    print(f"-> {result.name}")
                    last_printed = result
                if args.show_mask and vision.classifier.presence.has_background:
                    cv2.imshow("presence mask", vision.classifier.presence.object_mask(frame))
                cv2.imshow("tryand", draw(frame, result, detections))

            key = cv2.waitKey(10) & 0xFF
            if key == ord("q"):
                break
            if key == ord("b"):
                vision.recapture_background()
                print("Background re-captured.")
            if key == ord("s") and frame is not None:
                DATA_DIR.mkdir(exist_ok=True)
                path = DATA_DIR / f"frame_{int(time.time() * 1000)}.jpg"
                cv2.imwrite(str(path), frame)
                print(f"saved {path}")
    finally:
        vision.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
