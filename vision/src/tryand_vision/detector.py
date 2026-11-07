"""Vision logic: decide whether the camera sees NO OBJECT, a BOTTLE, or NO BOTTLE.

The decision is made from two independent questions:

1. "Is there *anything* on the platform?"
   -> answered by `PresenceDetector` (background subtraction: compare the current
      frame to a picture of the empty platform).

2. "Is that thing a bottle?"
   -> answered by `BottleDetector` (a pre-trained neural network, YOLO, that
      knows the class "bottle" out of the box).

`Classifier` combines both answers and smooths them over a few frames so the
result does not flicker.

Why two steps? A pre-trained YOLO model only knows 80 everyday object classes.
A crumpled napkin or a candy wrapper is not one of them, so YOLO alone would say
"nothing here" for most trash. Background subtraction catches *any* object,
YOLO only has to answer the narrower bottle question.
"""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from enum import Enum

import cv2
import numpy as np


class Result(Enum):
    """The three possible answers. The int value is what we send over serial."""

    NO_OBJECT = 0
    BOTTLE = 1
    NO_BOTTLE = 2  # there is an object, but it is not a bottle


# --------------------------------------------------------------------------- #
# Step 1: is there anything on the platform?
# --------------------------------------------------------------------------- #


class PresenceDetector:
    """Detects *any* object by comparing each frame to a reference "empty" frame.

    Assumes the camera does not move and the platform is empty when you call
    `set_background` (press `b` in the live view to do that).
    """

    def __init__(self, min_area_fraction: float = 0.01, diff_threshold: int = 30):
        # min_area_fraction: how big (as a fraction of the image) the changed
        #   region must be to count as an object. 0.01 = 1 % of the picture.
        #   Raise it if dust/shadows trigger false objects.
        # diff_threshold: how different (0-255) a pixel must be from the
        #   background to count as "changed". Raise it if lighting flicker
        #   triggers false objects.
        self.min_area_fraction = min_area_fraction
        self.diff_threshold = diff_threshold
        self._background: np.ndarray | None = None

    @staticmethod
    def _prepare(frame: np.ndarray) -> np.ndarray:
        # Grayscale: we only care about brightness changes, not colour.
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # Blur: removes camera noise so single noisy pixels do not count.
        return cv2.GaussianBlur(gray, (21, 21), 0)

    @property
    def has_background(self) -> bool:
        return self._background is not None

    def set_background(self, frame: np.ndarray) -> None:
        self._background = self._prepare(frame)

    def object_mask(self, frame: np.ndarray) -> np.ndarray:
        """Black/white image: white where the frame differs from the background."""
        if self._background is None:
            raise RuntimeError("call set_background() first")
        diff = cv2.absdiff(self._background, self._prepare(frame))
        _, mask = cv2.threshold(diff, self.diff_threshold, 255, cv2.THRESH_BINARY)
        # "Dilate" grows the white areas so a split-up object becomes one blob.
        return cv2.dilate(mask, None, iterations=2)

    def is_present(self, frame: np.ndarray) -> bool:
        mask = self.object_mask(frame)
        changed_fraction = cv2.countNonZero(mask) / mask.size
        return changed_fraction >= self.min_area_fraction


# --------------------------------------------------------------------------- #
# Step 2: is it a bottle?
# --------------------------------------------------------------------------- #


@dataclass
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in pixels


# The labels that count as the sorted item (Result.BOTTLE): a bottle or a cup.
TARGET_LABELS = frozenset({"bottle", "cup"})

# Default model: YOLO-World, an "open vocabulary" YOLO that finds whatever the text
# prompts describe. The plain COCO model (yolo11n.pt) never recognised a paper cup
# lying on its side on the platform; YOLO-World with these prompts does.
# Each prompt is mapped to the label the rest of the code uses.
DEFAULT_MODEL = "yolov8s-worldv2.pt"
WORLD_PROMPTS = {
    "bottle": "bottle",
    "plastic bottle": "bottle",
    "cup": "cup",
    "paper cup": "cup",
}

# Classes YOLO may report but that must never count as an object on the platform.
IGNORED_LABELS = frozenset({"person"})


class BottleDetector:
    """Wraps a YOLO model that finds bottles and cups.

    By default a YOLO-World model prompted with WORLD_PROMPTS (only bottles and cups
    are reported; any *other* object is caught by PresenceDetector instead). A plain
    COCO model such as yolo11n.pt can still be passed with `model_name`.
    The model file is downloaded automatically the first time.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        min_confidence: float = 0.4,
        bottle_confidence: float = 0.15,
        zoom_out_pad: float = 0.5,
    ):
        # Imported here (not at the top) so the rest of the module, and the
        # tests, work without loading the heavy deep-learning libraries.
        from ultralytics import YOLO

        self.model = YOLO(model_name)
        self.label_map: dict[str, str] = {}
        if "world" in model_name.lower():
            self.model.set_classes(list(WORLD_PROMPTS))
            self.label_map = WORLD_PROMPTS
        self.min_confidence = min_confidence
        # A bottle held close is cropped by the frame edge or fills it, and YOLO's
        # confidence drops. Accept bottles and cups at a lower confidence than other objects.
        self.bottle_confidence = min(bottle_confidence, min_confidence)
        # Fraction of the frame size added on each side for the zoom-out retry
        # (0.5 -> objects appear half as big). 0 turns the retry off.
        self.zoom_out_pad = zoom_out_pad

    def detect(self, frame: np.ndarray) -> list[Detection]:
        """Return every object YOLO recognises (bottles and others), except IGNORED_LABELS.

        A bottle held very close fills the frame, which YOLO handles badly. If the
        normal pass finds no bottle, look again at a zoomed-out copy (the frame
        padded with grey borders) so a big bottle appears at a normal size.
        """
        detections = self._run(frame)
        if not any(d.label in TARGET_LABELS for d in detections):
            zoomed_out = self._run(frame, pad_fraction=self.zoom_out_pad)
            detections += [d for d in zoomed_out if d.label in TARGET_LABELS]
        return detections

    def _run(self, frame: np.ndarray, pad_fraction: float = 0.0) -> list[Detection]:
        h, w = frame.shape[:2]
        pad_y, pad_x = int(h * pad_fraction), int(w * pad_fraction)
        if pad_y or pad_x:
            frame = cv2.copyMakeBorder(
                frame, pad_y, pad_y, pad_x, pad_x, cv2.BORDER_CONSTANT, value=(114, 114, 114)
            )
        result = self.model(frame, conf=self.bottle_confidence, verbose=False)[0]
        detections = []
        for box in result.boxes:
            class_id = int(box.cls[0])
            label, confidence = result.names[class_id], float(box.conf[0])
            label = self.label_map.get(label, label)  # "paper cup" -> "cup"
            if label in IGNORED_LABELS:
                continue
            if label not in TARGET_LABELS and confidence < self.min_confidence:
                continue
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
            # Map back to the original frame (undo the padding, stay inside the image).
            x1, x2 = max(0, x1 - pad_x), min(w - 1, x2 - pad_x)
            y1, y2 = max(0, y1 - pad_y), min(h - 1, y2 - pad_y)
            detections.append(Detection(label=label, confidence=confidence, box=(x1, y1, x2, y2)))
        return detections


# --------------------------------------------------------------------------- #
# Combine both steps
# --------------------------------------------------------------------------- #


def decide(object_present: bool, detections: list[Detection]) -> Result:
    """Pure decision rule for a single frame. Easy to read and to test."""
    if any(d.label in TARGET_LABELS for d in detections):
        return Result.BOTTLE
    if object_present or detections:
        # Something is there (background changed, or YOLO saw e.g. a "knife").
        return Result.NO_BOTTLE
    return Result.NO_OBJECT


class Classifier:
    """Runs both detectors on each frame and smooths the answer over time."""

    def __init__(self, presence: PresenceDetector, bottles, history: int = 5):
        # bottles: anything with a .detect(frame) -> list[Detection] method.
        # history: number of recent frames to vote over. Higher = steadier but
        #   slower to react.
        self.presence = presence
        self.bottles = bottles
        self._recent: deque[Result] = deque(maxlen=history)
        self.last_detections: list[Detection] = []
        # How many frames in a row gave exactly the same single-frame answer.
        # High number = the scene is calm (object lying still, nobody's hand in view).
        self.stable_frames = 0

    def classify(self, frame: np.ndarray) -> Result:
        present = self.presence.is_present(frame) if self.presence.has_background else False
        self.last_detections = self.bottles.detect(frame)
        raw = decide(present, self.last_detections)
        self.stable_frames = self.stable_frames + 1 if self._recent and raw == self._recent[-1] else 1
        self._recent.append(raw)
        # Majority vote: the most common answer among the last few frames.
        return Counter(self._recent).most_common(1)[0][0]

    def reset(self) -> None:
        self._recent.clear()
        self.stable_frames = 0
