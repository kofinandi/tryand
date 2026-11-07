"""Integration: the REAL tryand_vision.Vision feeding the real loop.

Fake camera and fake YOLO (like vision/tests/test_vision.py), real threads and clock.
Skipped if tryand_vision / OpenCV are not installed.
"""

import threading
import time

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
vision_mod = pytest.importorskip("tryand_vision.vision")
detector = pytest.importorskip("tryand_vision.detector")

from tryand_logic.__main__ import run  # noqa: E402
from tryand_logic.control import ArduinoControl  # noqa: E402
from tryand_logic.sorting import SortingLogic, State  # noqa: E402


def empty():
    return np.zeros((100, 100, 3), dtype=np.uint8)


def with_object():
    f = empty()
    f[30:70, 30:70] = 255
    return f


class FakeCamera:
    def __init__(self):
        self.frame = empty()

    def isOpened(self):
        return True

    def read(self):
        time.sleep(0.005)
        return True, self.frame.copy()

    def release(self):
        pass


class FakeYolo:
    """'bottle' when the white square is there and `bottle` is True, else nothing."""

    def __init__(self):
        self.bottle = True

    def detect(self, frame):
        if frame.mean() > 0 and self.bottle:
            return [detector.Detection("bottle", 0.9, (30, 30, 70, 70))]
        return []


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, command):
        self.sent.append(command)
        return "OK"


@pytest.fixture
def machine():
    camera, yolo, link = FakeCamera(), FakeYolo(), FakeLink()
    classifier = detector.Classifier(detector.PresenceDetector(), yolo, history=3)
    vision = vision_mod.Vision(classifier=classifier, capture=camera, warmup_seconds=0.05)
    logic = SortingLogic(ArduinoControl(link), confirm_s=0.3, settle_s=0.05, open_s=0.1,
                         grace_s=0.05)
    stop = threading.Event()
    with vision:
        vision.wait_until_ready(timeout=2)
        t = threading.Thread(target=run, args=(vision, logic),
                             kwargs={"poll_s": 0.01, "should_stop": stop.is_set}, daemon=True)
        t.start()
        yield camera, yolo, link, logic
        stop.set()
        t.join(timeout=2)


def wait_for(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_bottle_goes_left_and_trash_goes_right(machine):
    camera, yolo, link, logic = machine
    time.sleep(0.2)
    assert link.sent == []                      # empty platform: nothing happens

    camera.frame = with_object()                # a bottle lands
    assert wait_for(lambda: link.sent[-1:] == ["CLOSE"])
    assert link.sent == ["LEFT", "OPEN", "CLOSE"]

    camera.frame = empty()                      # it fell into the bin
    assert wait_for(lambda: logic.state is State.WAITING)

    yolo.bottle = False                         # something that is not a bottle lands
    camera.frame = with_object()
    assert wait_for(lambda: len(link.sent) == 6)
    assert link.sent[3:] == ["RIGHT", "OPEN", "CLOSE"]


def test_camera_crash_closes_box(machine):
    camera, _, link, logic = machine

    def broken():
        return False, None

    camera.read = broken
    assert wait_for(lambda: logic.state is State.FAULT)
    assert link.sent == ["CLOSE"]
