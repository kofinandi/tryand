"""Sorting logic: sits between VISION and CONTROL.

    VISION  --(label: none / object1 / object2)-->  LOGIC  --(left/right, open/close)-->  CONTROL

One bottle, step by step (default timings):

    WAITING     box empty
    CONFIRMING  a bottle is seen; it must stay the same label for `confirm_s` (1.2 s)
    MOVING      chute turned left/right; wait `settle_s` (0.4 s) so the servo arrives
    SORTING     box open; close it after `open_s` (1.0 s)
    CLEARING    box closed; wait until VISION sees it empty, then back to WAITING
    FAULT       CONTROL failed (ERR / no reply): box closed if possible, nothing
                else is sent until `reset()` is called

Camera glitches: a different label (including `none`) is only believed once it
has lasted `grace_s` (0.3 s). Shorter blips are ignored, so one bad frame does
not restart the 1.2 s timer or re-arm the box.

The class never sleeps: call `update(label, now)` once per frame with the
current time. That keeps it compatible with the camera loop and easy to test.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Protocol


class Label(str, Enum):
    """What VISION reports for one frame."""

    NONE = "none"
    OBJECT1 = "object1"
    OBJECT2 = "object2"


class Side(str, Enum):
    LEFT = "left"
    RIGHT = "right"


class State(str, Enum):
    WAITING = "waiting"
    CONFIRMING = "confirming"
    MOVING = "moving"
    SORTING = "sorting"
    CLEARING = "clearing"
    FAULT = "fault"


class Control(Protocol):
    """What LOGIC needs from the CONTROL part (the Arduino side)."""

    def move(self, side: Side) -> None: ...
    def open(self) -> None: ...
    def close(self) -> None: ...


def _elapsed(start: float, now: float, duration: float) -> bool:
    """True once `duration` seconds have passed (tolerant to float rounding)."""
    return now - start >= duration - 1e-9


DEFAULT_ROUTES: dict[Label, Side] = {
    Label.OBJECT1: Side.LEFT,
    Label.OBJECT2: Side.RIGHT,
}


@dataclass
class SortingLogic:
    control: Control
    confirm_s: float = 1.2
    settle_s: float = 0.4
    open_s: float = 1.0
    grace_s: float = 0.3
    routes: dict[Label, Side] = field(default_factory=lambda: dict(DEFAULT_ROUTES))
    on_sorted: Callable[[Label, Side], None] | None = None
    on_error: Callable[[Exception], None] | None = None

    state: State = field(default=State.WAITING, init=False)
    last_error: Exception | None = field(default=None, init=False)
    _candidate: Label = field(default=Label.NONE, init=False)
    _since: float = field(default=0.0, init=False)
    _other: Label | None = field(default=None, init=False)
    _other_since: float = field(default=0.0, init=False)
    _side: Side = field(default=Side.LEFT, init=False)
    _t: float = field(default=0.0, init=False)

    def update(self, label: Label | str, now: float | None = None) -> State:
        """Feed one VISION result. Returns the state after handling it."""
        label = Label(label)
        now = time.monotonic() if now is None else now

        if self.state is State.FAULT:
            return self.state

        try:
            self._step(label, now)
        except Exception as exc:  # ArduinoError, serial errors, ...
            self._fault(exc)
        return self.state

    def reset(self) -> None:
        """Leave FAULT (after fixing the problem) and start again from WAITING."""
        self.last_error = None
        self._go(State.WAITING)

    # --- internals ---------------------------------------------------------

    def _step(self, label: Label, now: float) -> None:
        if self.state is State.WAITING:
            if label is not Label.NONE:
                self._confirm(label, now)

        elif self.state is State.CONFIRMING:
            changed = self._stable_change(label, now)
            if changed is Label.NONE:
                self._go(State.WAITING)
            elif changed is not None:
                self._confirm(changed, self._other_since)
            # Don't sort while an unconfirmed change (maybe the bottle left) is pending.
            if (
                self.state is State.CONFIRMING
                and self._other is None
                and _elapsed(self._since, now, self.confirm_s)
            ):
                self._start_move(now)

        elif self.state is State.MOVING:
            if _elapsed(self._t, now, self.settle_s):
                self.control.open()
                self._t = now
                self._go(State.SORTING)

        elif self.state is State.SORTING:
            if _elapsed(self._t, now, self.open_s):
                self.control.close()
                self._go(State.CLEARING)

        elif self.state is State.CLEARING:
            if self._stable_change(label, now) is Label.NONE:
                self._go(State.WAITING)

    def _stable_change(self, label: Label, now: float) -> Label | None:
        """Return `label` once it has differed from the candidate for `grace_s`."""
        if label is self._candidate:
            self._other = None
            return None
        if label is not self._other:
            self._other, self._other_since = label, now
        if _elapsed(self._other_since, now, self.grace_s):
            return label
        return None

    def _confirm(self, label: Label, since: float) -> None:
        self._candidate, self._since = label, since
        self._other = None
        self._go(State.CONFIRMING)

    def _start_move(self, now: float) -> None:
        self._side = self.routes[self._candidate]
        self.control.move(self._side)
        self._t = now
        self._go(State.MOVING)
        if self.on_sorted:
            self.on_sorted(self._candidate, self._side)

    def _go(self, state: State) -> None:
        self.state = state
        self._other = None

    def _fault(self, exc: Exception) -> None:
        self.last_error = exc
        self.state = State.FAULT
        try:
            self.control.close()  # safest position: box shut
        except Exception:
            pass
        if self.on_error:
            self.on_error(exc)


class PrintControl:
    """Stand-in for CONTROL when no Arduino is attached (`--no-serial`)."""

    def move(self, side: Side) -> None:
        print(f"[control] move {side.value}")

    def open(self) -> None:
        print("[control] open")

    def close(self) -> None:
        print("[control] close")
