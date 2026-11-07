"""The VISION -> LOGIC -> CONTROL loop, with a fake vision and a fake clock."""

from enum import Enum

from tryand_logic.__main__ import run
from tryand_logic.control import ArduinoControl
from tryand_logic.sorting import Label, SortingLogic, State, label_from_vision


class Result(Enum):  # same names as tryand_vision.vision.Result
    NO_OBJECT = 0
    BOTTLE = 1
    NO_BOTTLE = 2


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, command):
        self.sent.append(command)
        return "OK"


class FakeVision:
    """Plays a script of (until_time, Result); raises `crash_at` time if set."""

    def __init__(self, clock, script, crash_at=None):
        self.clock, self.script, self.crash_at = clock, script, crash_at

    def classify(self):
        now = self.clock()
        if self.crash_at is not None and now >= self.crash_at:
            raise RuntimeError("vision thread crashed")
        for until, result in self.script:
            if now < until:
                return result
        return Result.NO_OBJECT


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t = round(self.t + s, 6)


def test_label_from_vision():
    assert label_from_vision(Result.NO_OBJECT) is Label.NONE
    assert label_from_vision(Result.BOTTLE) is Label.BOTTLE
    assert label_from_vision(Result.NO_BOTTLE) is Label.NO_BOTTLE


def make(script, crash_at=None, end=6.0):
    clock, link = FakeClock(), FakeLink()
    vision = FakeVision(clock, script, crash_at)
    logic = SortingLogic(ArduinoControl(link))
    state = run(vision, logic, poll_s=0.05, clock=clock, sleep=clock.sleep,
                should_stop=lambda: clock.t >= end)
    return state, link


def test_bottle_then_trash_are_sorted_left_then_right():
    script = [
        (0.5, Result.NO_OBJECT),
        (3.5, Result.BOTTLE),       # bottle lands at 0.5, falls after the box opens
        (4.0, Result.NO_OBJECT),
        (7.0, Result.NO_BOTTLE),    # trash lands at 4.0
    ]
    state, link = make(script, end=8.0)
    assert link.sent == ["LEFT", "OPEN", "CLOSE", "RIGHT", "OPEN", "CLOSE"]
    assert state is State.WAITING  # platform empty again at the end


def test_vision_crash_closes_box_and_stops():
    script = [(0.5, Result.NO_OBJECT), (9.0, Result.BOTTLE)]
    state, link = make(script, crash_at=1.0)
    assert state is State.FAULT
    assert link.sent == ["CLOSE"]
