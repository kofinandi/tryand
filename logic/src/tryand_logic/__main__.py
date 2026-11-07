"""Run the whole sorting machine:  VISION -> LOGIC -> CONTROL.

    python -m tryand_logic --camera 1 --port COM3          # real Arduino
    python -m tryand_logic --camera 1 --no-serial          # print the commands instead
    python -m tryand_logic --camera 1 --no-serial --show   # ...and watch the video

Keep the platform EMPTY for the first seconds: vision takes its background picture then.
Stop with Ctrl+C (or `q` in the video window with --show).
With --show, `b` re-takes the background picture (platform must be empty); use it when
the machine is stuck in "clearing" because vision keeps seeing something.

Vision answers NO_OBJECT / BOTTLE / NO_BOTTLE. By default a BOTTLE goes LEFT and
anything else (NO_BOTTLE) goes RIGHT; use --swap-sides to invert that.
"""

from __future__ import annotations

import argparse
import time
from typing import Callable

from .control import ArduinoControl
from .sorting import Label, PrintControl, Side, SortingLogic, State, label_from_vision


def run(
    vision,
    logic: SortingLogic,
    *,
    poll_s: float = 0.02,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    should_stop: Callable[[], bool] = lambda: False,
    on_tick: Callable[[State], None] | None = None,
) -> State:
    """Ask vision for its latest answer every `poll_s` seconds and feed it to the logic.

    Returns the final state. Stops on `should_stop()`, or in FAULT (Arduino error,
    or the camera crashed: then the box is closed first).
    """
    while not should_stop():
        try:
            label = label_from_vision(vision.classify())
        except Exception as exc:  # vision thread crashed / camera unplugged
            logic.fail(exc)
            break
        state = logic.update(label, clock())
        if on_tick:
            on_tick(state)
        if state is State.FAULT:
            break
        sleep(poll_s)
    return logic.state


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="tryand_logic", description=__doc__.split("\n")[0])
    p.add_argument("--camera", type=int, default=0, help="camera index (vision --list-cameras)")
    p.add_argument("--port", help="Arduino serial port, e.g. COM3 or /dev/cu.usbmodem1101")
    p.add_argument("--no-serial", action="store_true", help="print commands, no Arduino")
    p.add_argument("--show", action="store_true", help="show the video with the current state")
    p.add_argument("--swap-sides", action="store_true", help="BOTTLE right, NO_BOTTLE left")
    p.add_argument("--confirm", type=float, default=1.2, help="seconds a bottle must be seen")
    p.add_argument("--settle", type=float, default=1.0, help="seconds for the chute servo")
    p.add_argument("--open", type=float, default=2.0, help="seconds the box stays open")
    p.add_argument("--grace", type=float, default=0.3, help="ignore camera blips shorter than this")
    p.add_argument("--clear-timeout", type=float, default=5.0,
                   help="give up waiting for an empty box after this many seconds (0 = never)")
    p.add_argument("--confidence", type=float, default=0.4, help="vision: YOLO confidence")
    p.add_argument("--bottle-confidence", type=float, default=0.15,
                   help="vision: min confidence for bottles only (lower if close-up bottles are missed)")
    p.add_argument("--zoom-out", type=float, default=0.5,
                   help="retry on a zoomed-out frame when no bottle is found: border added per side as a fraction of the frame (0 = off, 1 = very close bottles)")
    p.add_argument("--min-area", type=float, default=0.01, help="vision: min changed area")
    args = p.parse_args(argv)
    if not args.no_serial and not args.port:
        p.error("--port is required unless --no-serial is given")

    # Imported here so the logic package (and its tests) don't need YOLO/OpenCV.
    from tryand_vision.vision import Vision

    link = None
    if args.no_serial:
        control = PrintControl()
    else:
        from tryand_vision.serial_link import ArduinoLink

        link = ArduinoLink(args.port)
        if not link.ping():
            raise SystemExit(f"Arduino on {args.port} did not answer PING")
        control = ArduinoControl(link)

    left, right = (Side.RIGHT, Side.LEFT) if args.swap_sides else (Side.LEFT, Side.RIGHT)
    logic = SortingLogic(
        control,
        confirm_s=args.confirm,
        settle_s=args.settle,
        open_s=args.open,
        grace_s=args.grace,
        clear_timeout_s=args.clear_timeout or None,
        routes={Label.BOTTLE: left, Label.NO_BOTTLE: right},
        on_sorted=lambda label, side: print(f"sorted {label.value} -> {side.value}"),
        on_error=lambda exc: print(f"FAULT: {exc!r} (box closed, machine stopped)"),
    )

    stop = [False]
    last = [None]

    def on_tick(state: State) -> None:
        if state is not last[0]:
            print(f"[logic] {state.value}")
            last[0] = state
        if args.show:
            _show(vision, state, stop)

    def on_clear_timeout() -> None:
        print("[logic] box never looked empty: re-taking the background picture")
        vision.recapture_background()

    logic.on_clear_timeout = on_clear_timeout

    print("Loading camera and YOLO... keep the platform EMPTY.")
    vision = Vision(
        camera=args.camera,
        confidence=args.confidence,
        bottle_confidence=args.bottle_confidence,
        zoom_out_pad=args.zoom_out,
        min_area=args.min_area,
    )
    try:
        with vision:
            vision.wait_until_ready()
            control.close()  # start from a known position
            print("Ready. Put a bottle on the platform. Ctrl+C to stop.")
            run(vision, logic, should_stop=lambda: stop[0], on_tick=on_tick)
    except KeyboardInterrupt:
        print("stopped")
    finally:
        if logic.state is not State.FAULT:
            try:
                control.close()  # leave the box shut
            except Exception:
                pass
        if link:
            link.close()
        if args.show:
            import cv2

            cv2.destroyAllWindows()


def _show(vision, state: State, stop: list[bool]) -> None:
    import cv2
    from tryand_vision.display import draw

    frame, result, detections = vision.latest_frame()
    if frame is not None:
        cv2.imshow("tryand", draw(frame, result, detections, f"logic: {state.value}"))
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        stop[0] = True
    elif key == ord("b") and state in (State.WAITING, State.CLEARING):
        vision.recapture_background()


if __name__ == "__main__":
    main()
