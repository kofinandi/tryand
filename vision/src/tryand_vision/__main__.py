import argparse

import cv2

from .detector import measure
from .serial_link import ArduinoLink


def main() -> None:
    parser = argparse.ArgumentParser(prog="tryand_vision")
    parser.add_argument("--port", help="serial port of the Arduino")
    parser.add_argument("--camera", type=int, default=0, help="camera index")
    parser.add_argument("--no-serial", action="store_true", help="run without an Arduino")
    args = parser.parse_args()

    if not args.no_serial and not args.port:
        parser.error("--port is required unless --no-serial is given")

    link = None if args.no_serial else ArduinoLink(args.port)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():
        raise SystemExit(f"cannot open camera {args.camera}")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            value = measure(frame)
            if link:
                link.set_value(value)
            cv2.putText(frame, str(value), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.imshow("tryand", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if link:
            link.close()


if __name__ == "__main__":
    main()
