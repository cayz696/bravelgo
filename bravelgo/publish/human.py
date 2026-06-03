"""Human-like delays for publish automation."""
from __future__ import annotations

import random
import time


def pause(a: float = 0.5, b: float = 2.0) -> None:
    time.sleep(random.uniform(a, b))


def pause_long() -> None:
    pause(2.0, 4.5)
