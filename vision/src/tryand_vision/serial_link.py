"""Serial link to the Arduino. Protocol is documented in the top-level README."""

import time

import serial

BAUD_RATE = 115200
MOVE_TIMEOUT = 3.0  # seconds to wait for a servo move to finish


class ArduinoError(RuntimeError):
    pass


class ArduinoLink:
    """Controls the upper trapdoors (open/close) and the lower chute (left/right)."""

    def __init__(self, port: str, baud: int = BAUD_RATE, timeout: float = 1.0):
        self._ser = serial.Serial(port, baud, timeout=timeout)
        self._done: set[str] = set()  # DONE lines seen but not yet consumed
        time.sleep(2.0)  # the board may reset when the port opens
        self._ser.reset_input_buffer()

    def _read_line(self, timeout: float) -> str:
        """Read one line, or return '' if nothing arrives within `timeout`."""
        old = self._ser.timeout
        self._ser.timeout = timeout
        try:
            return self._ser.readline().decode("ascii", errors="replace").strip()
        finally:
            self._ser.timeout = old

    def _request(self, line: str) -> str:
        """Send a command and return the immediate reply (PONG / OK)."""
        self._ser.write((line + "\n").encode("ascii"))
        while True:
            reply = self._read_line(1.0)
            if not reply:
                raise ArduinoError(f"no reply to {line!r}")
            if reply.startswith("DONE "):  # completion of an earlier command
                self._done.add(reply[5:])
                continue
            if reply.startswith("ERR"):
                raise ArduinoError(f"{line!r} -> {reply}")
            return reply

    def _wait_done(self, name: str, timeout: float = MOVE_TIMEOUT) -> None:
        deadline = time.monotonic() + timeout
        while name not in self._done:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ArduinoError(f"timed out waiting for {name} to finish")
            reply = self._read_line(remaining)
            if reply.startswith("DONE "):
                self._done.add(reply[5:])
        self._done.discard(name)

    def _move(self, name: str, wait: bool) -> None:
        self._done.discard(name)  # forget any stale completion
        self._request(name)
        if wait:
            self._wait_done(name)

    def send(self, command: str) -> str:
        """Send one protocol line and return the reply (raises ArduinoError on ERR)."""
        return self._request(command)

    def ping(self) -> bool:
        return self._request("PING") == "PONG"

    def open_trapdoors(self, wait: bool = True) -> None:
        self._move("OPEN", wait)

    def close_trapdoors(self, wait: bool = True) -> None:
        self._move("CLOSE", wait)

    def left(self, wait: bool = True) -> None:
        self._move("LEFT", wait)

    def right(self, wait: bool = True) -> None:
        self._move("RIGHT", wait)

    def close(self) -> None:
        """Close the serial port (not the trapdoors: that is `close_trapdoors()`)."""
        self._ser.close()

    def __enter__(self) -> "ArduinoLink":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
