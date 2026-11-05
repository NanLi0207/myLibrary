"""Your own reusable code, built up while working through your books.

Notebooks import from here so that code written for one chapter can be reused (and tested)
in later chapters. Replace or extend the example module with code for your own subject:
mylibrary.paraxial (first-order optics) came out of reading optical design books.
"""

from mylibrary.paraxial import efl, free_space, refraction, system_matrix, thin_lens

__all__ = ["free_space", "thin_lens", "refraction", "system_matrix", "efl"]
