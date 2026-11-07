from tryand_logic.sorting import Label, Side, SortingLogic, State

# Default timings: confirm 1.2 s, servo settle 0.4 s, box open 1.0 s, glitch grace 0.3 s.
# A bottle seen from t=0 is: moved at 1.2, opened at 1.6, closed at 2.6.

L, R = ("move", Side.LEFT), ("move", Side.RIGHT)
OPEN, CLOSE = ("open",), ("close",)


class FakeControl:
    def __init__(self, fail_on=None):
        self.calls = []
        self.fail_on = fail_on  # name of the call that raises

    def _do(self, call):
        self.calls.append(call)
        if self.fail_on == call[0]:
            raise RuntimeError(f"ERR {call[0]}")

    def move(self, side):
        self._do(("move", side))

    def open(self):
        self._do(("open",))

    def close(self):
        self._do(("close",))


def make(**kw):
    control = kw.pop("control", None) or FakeControl()
    return SortingLogic(control, **kw), control


def feed(logic, label, start, end, step=0.1):
    """Feed the same label every `step` seconds from start to end (inclusive)."""
    t = start
    while t <= end + 1e-9:
        logic.update(label, t)
        t = round(t + step, 6)


# --- basic flow ---------------------------------------------------------------

def test_empty_box_does_nothing():
    logic, control = make()
    feed(logic, Label.NONE, 0.0, 5.0)
    assert logic.state is State.WAITING
    assert control.calls == []


def test_object_shorter_than_confirm_time_is_ignored():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 1.0)
    feed(logic, Label.NONE, 1.1, 1.5)
    assert logic.state is State.WAITING
    assert control.calls == []


def test_object1_left_full_sequence():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 1.1)
    assert control.calls == []
    logic.update(Label.OBJECT1, 1.2)
    assert logic.state is State.MOVING and control.calls == [L]
    feed(logic, Label.OBJECT1, 1.3, 1.6)
    assert logic.state is State.SORTING and control.calls == [L, OPEN]
    feed(logic, Label.OBJECT1, 1.7, 2.6)
    assert logic.state is State.CLEARING and control.calls == [L, OPEN, CLOSE]


def test_object2_goes_right():
    logic, control = make()
    feed(logic, Label.OBJECT2, 0.0, 2.6)
    assert control.calls == [R, OPEN, CLOSE]


def test_routes_can_be_swapped():
    logic, control = make(routes={Label.OBJECT1: Side.RIGHT, Label.OBJECT2: Side.LEFT})
    feed(logic, Label.OBJECT1, 0.0, 1.2)
    assert control.calls == [R]


def test_accepts_plain_strings_from_vision():
    logic, control = make()
    feed(logic, "object2", 0.0, 1.2)
    assert control.calls == [R]


# --- 1. servo settle time -----------------------------------------------------

def test_box_does_not_open_before_servo_has_turned():
    logic, control = make(settle_s=0.4)
    feed(logic, Label.OBJECT1, 0.0, 1.5)  # moved at 1.2, only 0.3 s ago
    assert control.calls == [L]
    logic.update(Label.OBJECT1, 1.6)
    assert control.calls == [L, OPEN]


# --- 2. camera glitches ---------------------------------------------------------

def test_single_none_frame_does_not_restart_timer():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 0.6)
    logic.update(Label.NONE, 0.7)            # one bad frame
    feed(logic, Label.OBJECT1, 0.8, 1.2)
    assert control.calls == [L]               # still sorted at 1.2


def test_single_wrong_label_frame_does_not_restart_timer():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 0.6)
    logic.update(Label.OBJECT2, 0.7)
    feed(logic, Label.OBJECT1, 0.8, 1.2)
    assert control.calls == [L]


def test_real_label_change_restarts_timer_from_when_it_changed():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 0.5)
    feed(logic, Label.OBJECT2, 0.6, 1.7)      # object2 since 0.6 -> confirmed at 1.8
    assert control.calls == []
    logic.update(Label.OBJECT2, 1.8)
    assert control.calls == [R]


def test_bottle_removed_goes_back_to_waiting_after_grace():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 0.5)
    feed(logic, Label.NONE, 0.6, 0.8)
    assert logic.state is State.CONFIRMING   # only 0.2 s of none
    logic.update(Label.NONE, 0.9)
    assert logic.state is State.WAITING
    assert control.calls == []


def test_clearing_needs_stable_empty_box():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 2.6)      # closed at 2.6
    logic.update(Label.NONE, 2.7)             # glitch: box looks empty for one frame
    feed(logic, Label.OBJECT1, 2.8, 5.0)
    assert logic.state is State.CLEARING
    assert control.calls.count(OPEN) == 1     # not sorted twice
    feed(logic, Label.NONE, 5.1, 5.4)
    assert logic.state is State.WAITING


def test_two_bottles_in_a_row():
    logic, control = make()
    feed(logic, Label.OBJECT1, 0.0, 2.6)
    feed(logic, Label.NONE, 2.7, 3.0)
    feed(logic, Label.OBJECT2, 3.1, 5.7)
    assert control.calls == [L, OPEN, CLOSE, R, OPEN, CLOSE]


# --- 3. Arduino errors ----------------------------------------------------------

def test_error_on_move_closes_box_and_stops():
    errors = []
    logic, control = make(control=FakeControl(fail_on="move"), on_error=errors.append)
    feed(logic, Label.OBJECT1, 0.0, 1.2)
    assert logic.state is State.FAULT
    assert control.calls == [L, CLOSE]        # tried to move, then closed for safety
    assert str(logic.last_error) == "ERR move" and len(errors) == 1

    feed(logic, Label.OBJECT1, 1.3, 5.0)      # nothing more is sent while in FAULT
    assert control.calls == [L, CLOSE]


def test_error_on_open_closes_box():
    logic, control = make(control=FakeControl(fail_on="open"))
    feed(logic, Label.OBJECT2, 0.0, 1.6)
    assert logic.state is State.FAULT
    assert control.calls == [R, OPEN, CLOSE]


def test_error_on_close_does_not_crash():
    logic, control = make(control=FakeControl(fail_on="close"))
    feed(logic, Label.OBJECT1, 0.0, 2.6)      # close fails, safety close fails too
    assert logic.state is State.FAULT


def test_reset_after_fault():
    control = FakeControl(fail_on="move")
    logic, _ = make(control=control)
    feed(logic, Label.OBJECT1, 0.0, 1.2)
    assert logic.state is State.FAULT
    control.fail_on = None                    # problem fixed (cable plugged back)
    logic.reset()
    assert logic.state is State.WAITING and logic.last_error is None
    feed(logic, Label.OBJECT2, 2.0, 3.2)
    assert control.calls[-1] == R
