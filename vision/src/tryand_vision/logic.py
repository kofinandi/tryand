"""Sorting logic: sits between VISION and CONTROL.

    VISION  --(label: none / object1 / object2)-->  LOGIC  --(left/right, open/close)-->  CONTROL

A bottle lands in the box. VISION reports what it sees on every frame.
LOGIC accepts the bottle only once the same label has been seen continuously
for `confirm_s` seconds (default 1.2 s), picks a side, tells CONTROL to turn to
that side and open the box, closes it again after `open_s` seconds, then waits
until VISION reports the box empty before accepting the next bottle.

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
    WAITING = "waiting"        # box empty, nothing seen
    CONFIRMING = "confirming"  # a label is visible, timing it
    SORTING = "sorting"        # box open, bottle falling
    CLEARING = "clearing"      # box closed, waiting for VISION to see it empty


class Control(Protocol):
    """What LOGIC needs from the CONTROL part (the Arduino side)."""

    def move(self, side: Side) -> None: ...
    def open(self) -> None: ...
    def close(self) -> None: ...


DEFAULT_ROUTES: dict[Label, Side] = {
    Label.OBJECT1: Side.LEFT,
    Label.OBJECT2: Side.RIGHT,
}


@dataclass
class SortingLogic:
    control: Control
    confirm_s: float = 1.2
    open_s: float = 1.0
    routes: dict[Label, Side] = field(default_factory=lambda: dict(DEFAULT_ROUTES))
    on_sorted: Callable[[Label, Side], None] | None = None

    state: State = field(default=State.WAITING, init=False)
    _candidate: Label = field(default=Label.NONE, init=False)
    _since: float = field(default=0.0, init=False)
    _opened_at: float = field(default=0.0, init=False)

    def update(self, label: Label | str, now: float | None = None) -> State:
        """Feed one VISION result. Returns the state after handling it."""
        label = Label(label)
        now = time.monotonic() if now is None else now

        if self.state is State.WAITING:
            if label is not Label.NONE:
                self._start_confirming(label, now)

        elif self.state is State.CONFIRMING:
            if label is Label.NONE:
                self.state = State.WAITING
            elif label is not self._candidate:
                self._start_confirming(label, now)  # changed its mind: restart the timer
            elif now - self._since >= self.confirm_s:
                self._sort(label, now)

        elif self.state is State.SORTING:
            if now - self._opened_at >= self.open_s:
                self.control.close()
                self.state = State.CLEARING

        elif self.state is State.CLEARING:
            if label is Label.NONE:
                self.state = State.WAITING

        return self.state

    def _start_confirming(self, label: Label, now: float) -> None:
        self.state = State.CONFIRMING
        self._candidate = label
        self._since = now

    def _sort(self, label: Label, now: float) -> None:
        side = self.routes[label]
        self.control.move(side)
        self.control.open()
        self._opened_at = now
        self.state = State.SORTING
        if self.on_sorted:
            self.on_sorted(label, side)


class PrintControl:
    """Stand-in for CONTROL when no Arduino is attached (`--no-serial`)."""

    def move(self, side: Side) -> None:
        print(f"[control] move {side.value}")

    def open(self) -> None:
        print("[control] open")

    def close(self) -> None:
        print("[control] close")
