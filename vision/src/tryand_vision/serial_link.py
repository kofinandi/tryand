"""Serial link to the Arduino. Protocol is documented in the top-level README."""

import time

import serial

BAUD_RATE = 115200


class ArduinoError(RuntimeError):
    pass


class ArduinoLink:
    def __init__(self, port: str, baud: int = BAUD_RATE, timeout: float = 1.0):
        self._ser = serial.Serial(port, baud, timeout=timeout)
        time.sleep(2.0)  # most boards reset when the port opens
        self._ser.reset_input_buffer()

    def _request(self, line: str) -> str:
        self._ser.write((line + "\n").encode("ascii"))
        reply = self._ser.readline().decode("ascii", errors="replace").strip()
        if not reply:
            raise ArduinoError(f"no reply to {line!r}")
        if reply.startswith("ERR"):
            raise ArduinoError(f"{line!r} -> {reply}")
        return reply

    def send(self, command: str) -> str:
        """Send one protocol line and return the reply (raises ArduinoError on ERR)."""
        return self._request(command)

    def ping(self) -> bool:
        return self._request("PING") == "PONG"

    def set_value(self, value: int) -> None:
        self._request(f"SET {max(0, min(255, int(value)))}")

    def close(self) -> None:
        self._ser.close()

    def __enter__(self) -> "ArduinoLink":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
