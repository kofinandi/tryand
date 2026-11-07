"""Integration: real SortingLogic -> ArduinoControl -> ArduinoLink -> fake firmware.

The fake serial port answers like firmware/tryand_firmware: `OK` straight away and
`DONE <cmd>` once the (simulated) servos have arrived. Skipped without pyserial.
"""

import pytest

pytest.importorskip("serial")

from tryand_vision import serial_link

from tryand_logic.control import ArduinoControl
from tryand_logic.sorting import Label, SortingLogic, State


class FakeFirmware:
    """Stands in for serial.Serial, speaking the protocol in the top-level README."""

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout", 1.0)
        self.replies: list[str] = []
        self.received: list[str] = []
        self.reject: set[str] = set()

    def reset_input_buffer(self):
        self.replies.clear()

    def write(self, data: bytes):
        cmd = data.decode().strip()
        self.received.append(cmd)
        if cmd == "PING":
            self.replies.append("PONG")
        elif cmd in self.reject:
            self.replies.append("ERR rejected")
        elif cmd in ("LEFT", "RIGHT", "OPEN", "CLOSE"):
            self.replies += ["OK", f"DONE {cmd}"]
        else:
            self.replies.append("ERR unknown_command")

    def readline(self) -> bytes:
        return (self.replies.pop(0) + "\n").encode() if self.replies else b""

    def close(self):
        pass


@pytest.fixture
def machine(monkeypatch):
    monkeypatch.setattr(serial_link.serial, "Serial", FakeFirmware)
    monkeypatch.setattr(serial_link.time, "sleep", lambda s: None)
    link = serial_link.ArduinoLink("fake")
    logic = SortingLogic(ArduinoControl(link))
    return link, logic


def sort_one(logic: SortingLogic, label: Label, t0: float = 0.0) -> float:
    """Present `label` until the logic has finished with it; return the end time."""
    t = t0
    while logic.state is not State.CLEARING and logic.state is not State.FAULT:
        logic.update(label, t)
        t += 0.05
        assert t - t0 < 10, "logic never finished"
    return t


def test_bottle_goes_left_then_box_opens_and_closes(machine):
    link, logic = machine
    assert link.ping()
    sort_one(logic, Label.BOTTLE)
    assert link._ser.received == ["PING", "LEFT", "OPEN", "CLOSE"]


def test_non_bottle_goes_right(machine):
    link, logic = machine
    sort_one(logic, Label.NO_BOTTLE)
    assert link._ser.received == ["RIGHT", "OPEN", "CLOSE"]


def test_two_objects_in_a_row(machine):
    link, logic = machine
    t = sort_one(logic, Label.BOTTLE)
    for i in range(10):  # platform empties: back to WAITING
        logic.update(Label.NONE, t + i * 0.05)
    assert logic.state is State.WAITING
    sort_one(logic, Label.NO_BOTTLE, t + 1.0)
    assert link._ser.received == ["LEFT", "OPEN", "CLOSE", "RIGHT", "OPEN", "CLOSE"]


def test_arduino_error_faults_and_tries_to_close_the_box(machine):
    link, logic = machine
    link._ser.reject = {"OPEN"}
    sort_one(logic, Label.BOTTLE)
    assert logic.state is State.FAULT
    assert link._ser.received[-1] == "CLOSE"  # safest position
