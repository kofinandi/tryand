# tryand

A Python computer-vision component that controls an Arduino board over serial.

```
.
├── vision/     Python package: camera capture, detection, serial link
├── logic/      Python package: sorting decisions + left/right/open/close control API
└── firmware/   Arduino sketch that receives commands from the vision side
```

## Serial protocol

Newline-terminated ASCII lines at 115200 baud.

| Direction        | Line           | Meaning                          |
|------------------|----------------|----------------------------------|
| Python → Arduino | `PING`         | Connectivity check               |
| Python → Arduino | `SET <value>`  | Set output value (0–255)         |
| Python → Arduino | `LEFT`         | Point the chute to the left bin  |
| Python → Arduino | `RIGHT`        | Point the chute to the right bin |
| Python → Arduino | `OPEN`         | Open the box (bottle drops)      |
| Python → Arduino | `CLOSE`        | Close the box                    |
| Arduino → Python | `PONG`         | Reply to `PING`                  |
| Arduino → Python | `OK`           | Command accepted                 |
| Arduino → Python | `ERR <reason>` | Command rejected                 |

Keep this table in sync with `firmware/tryand_firmware/tryand_firmware.ino`
and `vision/src/tryand_vision/serial_link.py`.

`LEFT`/`RIGHT`/`OPEN`/`CLOSE` are sent by `ArduinoControl`
(`logic/src/tryand_logic/control.py`); the firmware must reply `OK` to each.

## Firmware

Requires [arduino-cli](https://arduino.github.io/arduino-cli/).

```sh
arduino-cli compile --fqbn arduino:avr:uno firmware/tryand_firmware
arduino-cli upload  --fqbn arduino:avr:uno -p /dev/cu.usbmodemXXXX firmware/tryand_firmware
```

## Vision

```sh
cd vision
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m tryand_vision --port /dev/cu.usbmodemXXXX
```

Use `--no-serial` to run the vision loop without a board attached.
Run tests with `pytest`.

## Logic

```
VISION --(none / object1 / object2)--> LOGIC --(left/right, open/close)--> CONTROL
```

- `sorting.py`: `SortingLogic` accepts a bottle once the same label is seen for
  1.2 s, turns the chute (`object1` left, `object2` right — placeholders), waits
  0.4 s for the servo, opens the box, closes it after 1.0 s, and waits for an
  empty box before the next bottle. Camera blips shorter than 0.3 s are ignored.
  If the Arduino fails (`ERR` / no reply) it closes the box and stops in
  `State.FAULT` until `reset()`. Call `update(label)` once per camera frame; it
  never blocks.
- `control.py`: `ArduinoControl(link)` with `left()`, `right()`, `open()`,
  `close()`; `link` is a `tryand_vision.serial_link.ArduinoLink`.

```sh
cd logic
pip install -e ".[dev]"
pytest
```
