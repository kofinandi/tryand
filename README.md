# tryand

A Python computer-vision component that controls an Arduino board over serial.

```
.
├── vision/     Python package: camera capture, detection, serial link
├── logic/      Python package: sorting decisions + left/right/open/close control API
└── firmware/   Arduino sketch that drives the trapdoor and chute servos
```

## Serial protocol

Newline-terminated ASCII lines at 115200 baud.

| Direction        | Line           | Meaning                                                  |
|------------------|----------------|----------------------------------------------------------|
| Python → Arduino | `PING`         | Connectivity check                                       |
| Python → Arduino | `LEFT`         | Point the chute to the left bin (servo 0°)               |
| Python → Arduino | `RIGHT`        | Point the chute to the right bin (servo 90°)             |
| Python → Arduino | `OPEN`         | Open the box: both upper trapdoors open (bottle drops)   |
| Python → Arduino | `CLOSE`        | Close the box: both upper trapdoors close                |
| Arduino → Python | `PONG`         | Reply to `PING`                                          |
| Arduino → Python | `OK`           | Command accepted, servos are moving                      |
| Arduino → Python | `DONE <cmd>`   | Movement for `LEFT`/`RIGHT`/`OPEN`/`CLOSE` finished      |
| Arduino → Python | `ERR <reason>` | Command rejected                                         |

Moves are non-blocking: the Arduino answers `OK` straight away and sends
`DONE <cmd>` once the servos arrive (about 0.3 s). `ArduinoLink` skips `DONE`
lines when it waits for a reply, so callers that ignore them (such as
`ArduinoControl`) are unaffected. On power-up the box is closed and the chute is
centred (servo 45°).

Keep this table in sync with `firmware/tryand_firmware/tryand_firmware.ino`
and `vision/src/tryand_vision/serial_link.py`.

`LEFT`/`RIGHT`/`OPEN`/`CLOSE` are sent by `ArduinoControl`
(`logic/src/tryand_logic/control.py`); the firmware replies `OK` to each.

## Wiring

Servo power comes from an external 5 V supply, **not** from the Arduino.
The supply ground must be shared with an Arduino GND pin.

| Servo           | Signal pin | Power (red)       | Ground (brown)        |
|-----------------|------------|-------------------|-----------------------|
| Trapdoor A      | D9         | external 5 V +    | external 5 V − / GND  |
| Trapdoor B      | D10        | external 5 V +    | external 5 V − / GND  |
| Chute           | D11        | external 5 V +    | external 5 V − / GND  |

The two trapdoor servos are mounted mirrored: A travels 0→90° to open, B travels
90→0°. Angles are calibrated with the constants at the top of the sketch.

## Firmware

Target board: **Arduino UNO R4 WiFi**. Requires
[arduino-cli](https://arduino.github.io/arduino-cli/) and the `arduino:renesas_uno`
core (`arduino-cli core install arduino:renesas_uno`). On Apple Silicon the core's
x86 compiler needs Rosetta 2.

```sh
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware/tryand_firmware
arduino-cli upload  --fqbn arduino:renesas_uno:unor4wifi -p /dev/cu.usbmodemXXXX firmware/tryand_firmware
```

Close anything that has the serial port open (bench tool, vision, logic) before
uploading. If an upload fails with "No device found", unplug and replug USB and
retry.

## Vision

The vision part answers "NO_OBJECT / BOTTLE / NO_BOTTLE". The control logic on the Mac
pulls answers from it via `tryand_vision.vision.Vision` (see [vision/GUIDE.md](vision/GUIDE.md)).

```sh
cd vision
python3.12 -m venv ~/.venvs/tryand-vision && source ~/.venvs/tryand-vision/bin/activate
pip install -e ".[dev]"
python -m tryand_vision --camera 1 --show-mask   # debug viewer
```

Test the mechanism without a camera (`o` open, `c` close, `l` left, `r` right, `q` quit):

```sh
python -m tryand_vision.bench --port /dev/cu.usbmodemXXXX
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
