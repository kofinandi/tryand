"""Tests ArduinoLink against a fake serial port that mimics the firmware."""

import pytest

from tryand_vision import serial_link
from tryand_vision.serial_link import ArduinoError, ArduinoLink


class FakeSerial:
    """Replies like the firmware: OK immediately, DONE <cmd> right after."""

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout", 1.0)
        self.out = []  # lines waiting to be read
        self.sent = []
        self.silent_done = False

    def reset_input_buffer(self):
        self.out.clear()

    def write(self, data: bytes):
        cmd = data.decode().strip()
        self.sent.append(cmd)
        if cmd == "PING":
            self.out.append("PONG")
        elif cmd in ("OPEN", "CLOSE", "LEFT", "RIGHT"):
            self.out.append("OK")
            if not self.silent_done:
                self.out.append(f"DONE {cmd}")
        else:
            self.out.append("ERR unknown_command")

    def readline(self) -> bytes:
        return (self.out.pop(0) + "\n").encode() if self.out else b""

    def close(self):
        pass


@pytest.fixture
def link(monkeypatch):
    monkeypatch.setattr(serial_link.serial, "Serial", FakeSerial)
    monkeypatch.setattr(serial_link.time, "sleep", lambda s: None)
    return ArduinoLink("fake")


def test_ping(link):
    assert link.ping()


def test_commands_are_sent_and_awaited(link):
    link.open_trapdoors()
    link.left()
    link.close_trapdoors()
    link.right()
    assert link._ser.sent == ["OPEN", "LEFT", "CLOSE", "RIGHT"]


def test_no_wait_leaves_done_for_later(link):
    link.open_trapdoors(wait=False)
    link.left(wait=False)  # the DONE OPEN line arrives while reading this reply
    link._wait_done("OPEN")
    link._wait_done("LEFT")


def test_timeout_when_done_never_arrives(link):
    link._ser.silent_done = True
    with pytest.raises(ArduinoError):
        link._move("OPEN", wait=False) or link._wait_done("OPEN", timeout=0.05)


def test_error_reply_raises(link):
    with pytest.raises(ArduinoError):
        link._request("BOGUS")
