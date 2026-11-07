"""The interface the control logic uses: ask the camera "what is on the platform?".

The control logic is the boss. It *pulls* an answer when it is ready:

    from tryand_vision.vision import Vision, Result

    with Vision(camera=1) as vision:        # starts the camera in the background
        vision.wait_until_ready()            # camera warmed up, background captured
        ...
        result = vision.wait_for_stable()    # waits until the answer is steady
        if result == Result.BOTTLE:
            ...

Why a background thread?
    Opening a camera and loading YOLO takes seconds, and the majority vote
    needs several recent frames. So the camera runs all the time in a
    *thread* (a second line of execution inside the same program) and keeps
    the newest answer ready. Asking for it is then instant.

Thread safety:
    Two threads touching the same data at the same time can corrupt it.
    `self._lock` makes sure only one thread at a time reads or writes the
    shared answer and frame.
"""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np

from .detector import DEFAULT_MODEL, BottleDetector, Classifier, Detection, PresenceDetector, Result

__all__ = ["Result", "Vision"]


class Vision:
    def __init__(
        self,
        camera: int = 0,
        model: str = DEFAULT_MODEL,
        confidence: float = 0.4,
        bottle_confidence: float = 0.15,
        zoom_out_pad: float = 0.5,
        min_area: float = 0.01,
        warmup_seconds: float = 2.0,
        classifier: Classifier | None = None,
        capture=None,
    ):
        # `classifier` and `capture` let tests pass in fakes instead of a real
        # YOLO model and camera. Normal code leaves them as None.
        self.warmup_seconds = warmup_seconds
        self.classifier = classifier or Classifier(
            PresenceDetector(min_area_fraction=min_area),
            BottleDetector(model, min_confidence=confidence, bottle_confidence=bottle_confidence,
                           zoom_out_pad=zoom_out_pad),
        )
        # macOS only allows opening the camera from the main thread, so we
        # open it here, and only *read* from it in the background thread.
        self._cap = capture if capture is not None else cv2.VideoCapture(camera)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open camera {camera} (try --list-cameras)")

        self._lock = threading.Lock()
        self._result = Result.NO_OBJECT
        self._frame: np.ndarray | None = None
        self._detections: list[Detection] = []
        self._stable_frames = 0
        self._frame_count = 0
        self._recapture_background = False
        self._ready = threading.Event()  # set once the background is captured
        self._running = False
        self._thread: threading.Thread | None = None
        self.error: Exception | None = None

    # ------------------------------------------------------------------ #
    # Starting and stopping
    # ------------------------------------------------------------------ #

    def start(self) -> Vision:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        self._cap.release()

    def __enter__(self) -> Vision:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # ------------------------------------------------------------------ #
    # What the control logic calls
    # ------------------------------------------------------------------ #

    def wait_until_ready(self, timeout: float = 30.0) -> None:
        """Block until the camera is warm and the empty background is captured."""
        if not self._ready.wait(timeout):
            self._check_alive()
            raise TimeoutError("vision did not become ready")

    def classify(self) -> Result:
        """Return the latest (smoothed) answer immediately."""
        self._check_alive()
        with self._lock:
            return self._result

    def wait_for_stable(self, frames: int = 8, timeout: float = 3.0) -> Result | None:
        """Wait until the last `frames` frames all agree, then return that answer.

        Use this when deciding where an object goes: it avoids deciding while
        the object is still sliding in or a hand is in the picture.
        Returns None if the scene did not calm down within `timeout` seconds.

        Only frames captured *after* this call count, so you never get an old
        "stable" answer from before the object arrived.
        """
        deadline = time.monotonic() + timeout
        with self._lock:
            first_frame = self._frame_count
        while time.monotonic() < deadline:
            self._check_alive()
            with self._lock:
                new_frames = self._frame_count - first_frame
                if new_frames >= frames and self._stable_frames >= frames:
                    return self._result
            time.sleep(0.01)
        return None

    def recapture_background(self) -> None:
        """Take a new picture of the empty platform. Only call it when the platform IS empty."""
        with self._lock:
            self._recapture_background = True

    # For the debug viewer
    def latest_frame(self) -> tuple[np.ndarray | None, Result, list[Detection]]:
        with self._lock:
            frame = None if self._frame is None else self._frame.copy()
            return frame, self._result, list(self._detections)

    @property
    def is_ready(self) -> bool:
        """True once the camera is warm and the background is captured (doesn't wait)."""
        return self._ready.is_set()

    @property
    def frame_count(self) -> int:
        with self._lock:
            return self._frame_count

    # ------------------------------------------------------------------ #
    # The background thread
    # ------------------------------------------------------------------ #

    def _check_alive(self) -> None:
        if self.error is not None:
            raise RuntimeError("vision thread crashed") from self.error

    def _loop(self) -> None:
        started = time.monotonic()
        try:
            while self._running:
                ok, frame = self._cap.read()
                if not ok:
                    raise RuntimeError("camera stopped delivering frames")

                presence = self.classifier.presence
                with self._lock:
                    recapture = self._recapture_background
                    self._recapture_background = False
                if recapture or (
                    not self._ready.is_set() and time.monotonic() - started >= self.warmup_seconds
                ):
                    presence.set_background(frame)
                    self.classifier.reset()
                    self._ready.set()

                result = self.classifier.classify(frame)  # slow part, done outside the lock

                with self._lock:
                    self._result = result
                    self._frame = frame
                    self._detections = self.classifier.last_detections
                    # Before the background exists the answers mean nothing.
                    self._stable_frames = self.classifier.stable_frames if self._ready.is_set() else 0
                    self._frame_count += 1
        except Exception as exc:  # noqa: BLE001 - hand any crash to the control logic
            self.error = exc
