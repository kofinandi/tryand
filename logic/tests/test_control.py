import pytest

from tryand_logic.control import ArduinoControl
from tryand_logic.sorting import Label, Side, SortingLogic


class FakeLink:
    def __init__(self):
        self.sent = []

    def send(self, command):
        self.sent.append(command)
        return "OK"


@pytest.mark.parametrize(
    "button, command",
    [("left", "LEFT"), ("right", "RIGHT"), ("open", "OPEN"), ("close", "CLOSE")],
)
def test_each_button_sends_its_command(button, command):
    link = FakeLink()
    getattr(ArduinoControl(link), button)()
    assert link.sent == [command]


def test_move_maps_side_to_command():
    link = FakeLink()
    control = ArduinoControl(link)
    control.move(Side.LEFT)
    control.move("right")
    assert link.sent == ["LEFT", "RIGHT"]


def test_logic_drives_arduino_commands():
    link = FakeLink()
    logic = SortingLogic(ArduinoControl(link), confirm_s=1.2, settle_s=0.4, open_s=1.0)
    for t in (0.0, 0.6, 1.2, 1.6, 2.6):
        logic.update(Label.NO_BOTTLE, t)
    assert link.sent == ["RIGHT", "OPEN", "CLOSE"]
