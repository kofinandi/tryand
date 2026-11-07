"""Tests for the decision logic. They use fake images and a fake YOLO, so they run fast."""

import numpy as np

from tryand_vision.detector import Classifier, Detection, PresenceDetector, Result, decide

BOTTLE = Detection("bottle", 0.9, (0, 0, 10, 10))
KNIFE = Detection("knife", 0.9, (0, 0, 10, 10))


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
    assert decide(False, [KNIFE]) == Result.NO_BOTTLE


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


def test_big_bottle_found_on_zoomed_out_retry():
    """A bottle filling the frame is only recognised once the frame is padded."""
    from types import SimpleNamespace

    import numpy as np
    from tryand_vision.detector import BottleDetector

    def box(cls, conf, xyxy):
        return SimpleNamespace(cls=[cls], conf=[conf], xyxy=[xyxy])

    class FakeYolo:
        def __init__(self):
            self.shapes = []

        def __call__(self, frame, conf, verbose):
            self.shapes.append(frame.shape[:2])
            boxes = [] if len(self.shapes) == 1 else [box(0, 0.6, (100, 50, 300, 250))]
            return [SimpleNamespace(boxes=boxes, names={0: "bottle"})]

    det = BottleDetector.__new__(BottleDetector)
    det.model, det.min_confidence, det.bottle_confidence, det.zoom_out_pad = FakeYolo(), 0.4, 0.15, 0.5
    det.label_map = {}
    found = det.detect(np.zeros((200, 400, 3), np.uint8))
    assert det.model.shapes == [(200, 400), (400, 800)]
    assert [(d.label, d.box) for d in found] == [("bottle", (0, 0, 100, 150))]


def test_cup_counts_as_bottle():
    assert decide(True, [Detection("cup", 0.9, (0, 0, 10, 10))]) is Result.BOTTLE


def test_world_prompts_map_to_cup_and_bottle():
    """YOLO-World reports the prompt text ("paper cup"); it must become "cup"."""
    from types import SimpleNamespace

    import numpy as np
    from tryand_vision.detector import WORLD_PROMPTS, BottleDetector

    class FakeWorld:
        def __call__(self, frame, conf, verbose):
            b = SimpleNamespace(cls=[0], conf=[0.6], xyxy=[(10, 10, 50, 50)])
            return [SimpleNamespace(boxes=[b], names={0: "paper cup"})]

    det = BottleDetector.__new__(BottleDetector)
    det.model, det.min_confidence, det.bottle_confidence, det.zoom_out_pad = FakeWorld(), 0.4, 0.15, 0.5
    det.label_map = WORLD_PROMPTS
    found = det.detect(np.zeros((100, 100, 3), np.uint8))
    assert [d.label for d in found] == ["cup"]
    assert decide(True, found) is Result.BOTTLE
