# tryand

A Python computer-vision component that controls an Arduino board over serial.

```
.
├── vision/     Python package: camera capture, detection, serial link
└── firmware/   Arduino sketch that receives commands from the vision side
```

## Serial protocol

Newline-terminated ASCII lines at 115200 baud.

| Direction        | Line           | Meaning                          |
|------------------|----------------|----------------------------------|
| Python → Arduino | `PING`         | Connectivity check               |
| Python → Arduino | `SET <value>`  | Set output value (0–255)         |
| Arduino → Python | `PONG`         | Reply to `PING`                  |
| Arduino → Python | `OK`           | Command accepted                 |
| Arduino → Python | `ERR <reason>` | Command rejected                 |

Keep this table in sync with `firmware/tryand_firmware/tryand_firmware.ino`
and `vision/src/tryand_vision/serial_link.py`.

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
