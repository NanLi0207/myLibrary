"""Paraxial (first-order) optics with ray-transfer (ABCD) matrices.

Convention: a ray is the column vector [y, n*u] (height, reduced angle),
so every matrix has determinant 1 and works across media of different index.
Lengths are in whatever unit you choose (mm is typical); be consistent.
"""

from functools import reduce

import numpy as np


def free_space(t: float, n: float = 1.0) -> np.ndarray:
    """Transfer over thickness t in a medium of index n."""
    return np.array([[1.0, t / n], [0.0, 1.0]])


def refraction(c: float, n1: float, n2: float) -> np.ndarray:
    """Refraction at a spherical surface of curvature c = 1/R from index n1 to n2."""
    power = (n2 - n1) * c
    return np.array([[1.0, 0.0], [-power, 1.0]])


def thin_lens(f: float) -> np.ndarray:
    """Thin lens of focal length f in air."""
    return np.array([[1.0, 0.0], [-1.0 / f, 1.0]])


def system_matrix(*elements: np.ndarray) -> np.ndarray:
    """Combine elements listed in the order light meets them."""
    return reduce(lambda acc, m: m @ acc, elements, np.eye(2))


def efl(m: np.ndarray) -> float:
    """Effective focal length of a system matrix (in air on both sides)."""
    return -1.0 / m[1, 0]
