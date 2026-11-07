"""Tests for the decision logic. They use fake images and a fake YOLO, so they run fast."""

import numpy as np

from tryand_vision.detector import Classifier, Detection, PresenceDetector, Result, decide

BOTTLE = Detection("bottle", 0.9, (0, 0, 10, 10))
CUP = Detection("cup", 0.9, (0, 0, 10, 10))


def empty_frame():
    return np.zeros((100, 100, 3), dtype=np.uint8)


def frame_with_object():
    frame = empty_frame()
    frame[30:70, 30:70] = 255  # a white square = "an object"
    return frame


class FakeBottleDetector:
    """Stands in for YOLO: returns whatever we tell it to."""

    def __init__(self, detections):
        self.detections = detections

    def detect(self, frame):
        return self.detections


def test_decide_rules():
    assert decide(False, []) == Result.NO_OBJECT
    assert decide(True, []) == Result.NO_BOTTLE
    assert decide(True, [BOTTLE]) == Result.BOTTLE
    assert decide(False, [BOTTLE]) == Result.BOTTLE
    assert decide(False, [CUP]) == Result.NO_BOTTLE


def test_presence_detector():
    presence = PresenceDetector()
    presence.set_background(empty_frame())
    assert not presence.is_present(empty_frame())
    assert presence.is_present(frame_with_object())


def test_classifier_smooths_over_frames():
    presence = PresenceDetector()
    presence.set_background(empty_frame())
    fake = FakeBottleDetector([])
    clf = Classifier(presence, fake, history=3)

    assert clf.classify(empty_frame()) == Result.NO_OBJECT
    assert clf.classify(empty_frame()) == Result.NO_OBJECT

    fake.detections = [BOTTLE]
    # One bottle frame is outvoted by two empty ones...
    assert clf.classify(frame_with_object()) == Result.NO_OBJECT
    # ...but after two bottle frames the majority flips.
    assert clf.classify(frame_with_object()) == Result.BOTTLE
