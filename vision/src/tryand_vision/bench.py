"""Bench-test the servos from the keyboard, no camera needed.

    python -m tryand_vision.bench --port /dev/cu.usbmodemXXXX
"""

import argparse

from .serial_link import ArduinoLink

COMMANDS = {
    "o": ("open trapdoors", lambda link: link.open_trapdoors()),
    "c": ("close trapdoors", lambda link: link.close_trapdoors()),
    "l": ("chute left", lambda link: link.left()),
    "r": ("chute right", lambda link: link.right()),
}


def main() -> None:
    parser = argparse.ArgumentParser(prog="tryand_vision.bench")
    parser.add_argument("--port", required=True, help="serial port of the Arduino")
    args = parser.parse_args()

    with ArduinoLink(args.port) as link:
        print("connected:", "ok" if link.ping() else "no PONG")
        print("  ".join(f"{k} = {name}" for k, (name, _) in COMMANDS.items()), " q = quit")
        while True:
            key = input("> ").strip().lower()
            if key == "q":
                break
            if key in COMMANDS:
                COMMANDS[key][1](link)
            else:
                print("unknown key")


if __name__ == "__main__":
    main()
