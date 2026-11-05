"""Reusable optics code, built up while working through the optics books.

Chapter scripts in examples/ can import it (`from optics.paraxial import thin_lens`); the
script template puts this code/ folder on the import path.
"""

from optics.paraxial import efl, free_space, refraction, system_matrix, thin_lens

__all__ = ["free_space", "thin_lens", "refraction", "system_matrix", "efl"]
