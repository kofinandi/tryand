"""Tests for the pull interface (Vision), using a fake camera and a fake YOLO."""

import time

import numpy as np
import pytest

from tryand_vision.detector import Classifier, Detection, PresenceDetector, Result
from tryand_vision.vision import Vision

BOTTLE = Detection("bottle", 0.9, (30, 30, 70, 70))


def empty_frame():
    return np.zeros((100, 100, 3), dtype=np.uint8)


def frame_with_object():
    frame = empty_frame()
    frame[30:70, 30:70] = 255
    return frame


class FakeCamera:
    """Pretends to be cv2.VideoCapture. Change `.frame` to change what it 'sees'."""

    def __init__(self):
        self.frame = empty_frame()
        self.broken = False

    def isOpened(self):
        return True

    def read(self):
        time.sleep(0.002)  # a real camera delivers ~30 frames per second
        if self.broken:
            return False, None
        return True, self.frame.copy()

    def release(self):
        pass


class FakeBottleDetector:
    """Says 'bottle' whenever the white square is in the frame."""

    def detect(self, frame):
        return [BOTTLE] if frame.mean() > 0 else []


@pytest.fixture
def setup():
    camera = FakeCamera()
    classifier = Classifier(PresenceDetector(), FakeBottleDetector(), history=3)
    vision = Vision(classifier=classifier, capture=camera, warmup_seconds=0.05)
    with vision:
        vision.wait_until_ready(timeout=2)
        yield vision, camera


def test_empty_platform(setup):
    vision, _ = setup
    assert vision.wait_for_stable(frames=5, timeout=2) == Result.NO_OBJECT


def test_bottle_arrives(setup):
    vision, camera = setup
    camera.frame = frame_with_object()
    # Called right as the object lands: must NOT return the old "empty" answer.
    assert vision.wait_for_stable(frames=5, timeout=2) == Result.BOTTLE
    assert vision.classify() == Result.BOTTLE


def test_flickering_scene_times_out(setup):
    vision, camera = setup
    flicker = [empty_frame(), frame_with_object()]

    original_read = camera.read
    count = {"n": 0}

    def flickering_read():
        count["n"] += 1
        camera.frame = flicker[count["n"] % 2]
        return original_read()

    camera.read = flickering_read
    assert vision.wait_for_stable(frames=5, timeout=0.3) is None


def test_camera_failure_is_reported(setup):
    vision, camera = setup
    camera.broken = True
    time.sleep(0.05)
    with pytest.raises(RuntimeError, match="crashed"):
        vision.classify()
