import os
from pathlib import Path

import numpy as np

from src import matplotlib_style  # noqa: F401

IN_CI = bool(os.environ.get("GITHUB_ACTIONS"))

# test artifacts
OUTPUT_DIR = Path("tests/output")
OUTPUT_DIR.mkdir(exist_ok=True)

# Tolerances for floating point comparisons
ABSOLUTE_TOLERANCE = 1e-3
RELATIVE_TOLERANCE = 1e-3


def check(test: float, expected: float) -> None:
    assert np.isclose(test, expected, rtol=RELATIVE_TOLERANCE, atol=ABSOLUTE_TOLERANCE), f"Expected {expected:,}, got {test:,}"
