import numpy as np
import pytest

from mylibrary import efl, free_space, refraction, system_matrix, thin_lens


def test_two_thin_lenses_match_gullstrand():
    f1, f2, d = 100.0, 50.0, 20.0
    m = system_matrix(thin_lens(f1), free_space(d), thin_lens(f2))
    expected = 1.0 / (1 / f1 + 1 / f2 - d / (f1 * f2))
    assert efl(m) == pytest.approx(expected)


def test_thick_lens_matrix_is_unimodular():
    n = 1.5168  # N-BK7 at d-line
    m = system_matrix(refraction(1 / 50, 1.0, n), free_space(5.0, n), refraction(-1 / 50, n, 1.0))
    assert np.linalg.det(m) == pytest.approx(1.0)
