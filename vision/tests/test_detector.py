import numpy as np

from tryand_vision.detector import measure


def test_measure_black_and_white():
    black = np.zeros((10, 10, 3), dtype=np.uint8)
    white = np.full((10, 10, 3), 255, dtype=np.uint8)
    assert measure(black) == 0
    assert measure(white) == 255
