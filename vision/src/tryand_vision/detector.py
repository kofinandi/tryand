"""Vision logic. Replace `measure` with the real detection."""

import cv2
import numpy as np


def measure(frame: np.ndarray) -> int:
    """Map a frame to a 0-255 value. Placeholder: mean brightness."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return int(gray.mean())
