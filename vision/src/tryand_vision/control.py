"""CONTROL API: the four buttons of the sorting machine.

    left()   -> chute points to the left bin      sends "LEFT"
    right()  -> chute points to the right bin     sends "RIGHT"
    open()   -> box opens, bottle drops           sends "OPEN"
    close()  -> box closes                        sends "CLOSE"

Each call sends one line over serial and waits for the Arduino's `OK`
(see the protocol table in the top-level README). `ArduinoControl` also has
`move(side)`, so it can be passed straight to `SortingLogic`:

    with ArduinoLink("COM3") as link:
        logic = SortingLogic(ArduinoControl(link))
"""

from __future__ import annotations

from typing import Protocol

from .logic import Side


class _Link(Protocol):
    def send(self, command: str) -> str: ...


class ArduinoControl:
    def __init__(self, link: _Link):
        self._link = link

    def left(self) -> None:
        self._link.send("LEFT")

    def right(self) -> None:
        self._link.send("RIGHT")

    def open(self) -> None:
        self._link.send("OPEN")

    def close(self) -> None:
        """Close the box (not the serial port — that is `ArduinoLink.close()`)."""
        self._link.send("CLOSE")

    def move(self, side: Side | str) -> None:
        if Side(side) is Side.LEFT:
            self.left()
        else:
            self.right()
