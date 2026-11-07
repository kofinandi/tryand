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
(`vision/src/tryand_vision/control.py`); the firmware must reply `OK` to each.

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
