from tryand_logic.sorting import Label, Side, SortingLogic, State


class FakeControl:
    def __init__(self):
        self.calls = []

    def move(self, side):
        self.calls.append(("move", side))

    def open(self):
        self.calls.append(("open",))

    def close(self):
        self.calls.append(("close",))


def make():
    control = FakeControl()
    return SortingLogic(control, confirm_s=1.2, open_s=1.0), control


def feed(logic, label, start, end, step=0.1):
    """Feed the same label every `step` seconds from start to end (inclusive)."""
    t = start
    while t <= end + 1e-9:
        logic.update(label, t)
        t = round(t + step, 6)


def test_empty_box_does_nothing():
    logic, control = make()
    feed(logic, Label.NONE, 0.0, 5.0)
    assert logic.state is State.WAITING
    assert control.calls == []


def test_object_shorter_than_confirm_time_is_ignored():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 1.1)
    logic.update(Label.NONE, 1.15)
    assert logic.state is State.WAITING
    assert control.calls == []


def test_object1_goes_left_after_1_2_seconds():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 1.1)
    assert control.calls == []
    logic.update(Label.OBJECT1, 1.2)
    assert logic.state is State.SORTING
    assert control.calls == [("move", Side.LEFT), ("open",)]


def test_object2_goes_right():
    logic, control = make()
    feed(logic, Label.OBJECT2, 0.0, 1.2)
    assert control.calls == [("move", Side.RIGHT), ("open",)]


def test_label_change_restarts_timer():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 1.0)
    feed(logic, Label.OBJECT2, 1.1, 2.2)  # only 1.1 s of object2 so far
    assert control.calls == []
    logic.update(Label.OBJECT2, 2.35)  # 1.25 s of object2
    assert control.calls == [("move", Side.RIGHT), ("open",)]


def test_box_closes_then_waits_until_empty():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 1.2)       # sorted at t=1.2
    feed(logic, Label.OBJECT1, 1.3, 2.1)
    assert ("close",) not in control.calls
    logic.update(Label.OBJECT1, 2.2)           # 1.0 s after opening
    assert control.calls[-1] == ("close",)
    assert logic.state is State.CLEARING

    # Bottle still visible: must not be sorted a second time.
    feed(logic, Label.OBJECT1, 2.3, 6.0)
    assert control.calls.count(("open",)) == 1

    logic.update(Label.NONE, 6.1)
    assert logic.state is State.WAITING


def test_two_bottles_in_a_row():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 2.2)
    logic.update(Label.NONE, 2.3)
    feed(logic, Label.OBJECT2, 2.4, 3.6)
    assert control.calls == [
        ("move", Side.LEFT), ("open",), ("close",),
        ("move", Side.RIGHT), ("open",),
    ]


def test_accepts_plain_strings_from_vision():
    logic, control = make()
    feed(logic, "object2", 0.0, 1.2)
    assert control.calls[0] == ("move", Side.RIGHT)
