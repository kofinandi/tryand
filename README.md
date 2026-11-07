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

The vision part answers "NO_OBJECT / BOTTLE / NO_BOTTLE". The control logic on the Mac
pulls answers from it via `tryand_vision.vision.Vision` (see [vision/GUIDE.md](vision/GUIDE.md)).

```sh
cd vision
python3.12 -m venv ~/.venvs/tryand-vision && source ~/.venvs/tryand-vision/bin/activate
pip install -e ".[dev]"
python -m tryand_vision --camera 1 --show-mask   # debug viewer
```

Keep the virtualenv outside the repo: the repo may live in iCloud Drive, which hides files
and breaks Python's editable installs. Run tests with `pytest`.

## Logic

```
VISION --(NO_OBJECT / BOTTLE / NO_BOTTLE)--> LOGIC --(left/right, open/close)--> CONTROL
```

- `sorting.py`: `SortingLogic` accepts an object once vision gives the same answer
  for 1.2 s, turns the chute (`BOTTLE` left, `NO_BOTTLE` right), waits 0.4 s for
  the servo, opens the box, closes it after 1.0 s, and waits for an empty platform
  before the next object. Vision blips shorter than 0.3 s are ignored. If the
  Arduino or the camera fails it closes the box and stops in `State.FAULT` until
  `reset()`. Call `update(label)` regularly; it never blocks.
- `control.py`: `ArduinoControl(link)` with `left()`, `right()`, `open()`,
  `close()`; `link` is a `tryand_vision.serial_link.ArduinoLink`.
- `__main__.py`: runs the whole machine. It polls `Vision.classify()` every 20 ms
  and feeds the answer to `SortingLogic`.

Install in the same virtualenv as vision (it uses `tryand_vision`):

```sh
cd logic
pip install -e ".[dev]"
python -m tryand_logic --camera 1 --no-serial --show   # print commands, no Arduino
python -m tryand_logic --camera 1 --port /dev/cu.usbmodemXXXX
pytest
```

Keep the platform empty for the first seconds (vision captures its background).
Timings and sides are options: `--confirm`, `--settle`, `--open`, `--grace`, `--swap-sides`.
