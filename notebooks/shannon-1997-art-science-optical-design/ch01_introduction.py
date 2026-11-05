import marimo

__generated_with = "0.25.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import matplotlib.pyplot as plt
    import numpy as np

    import mylibrary

    return mo, np, mylibrary, plt


@app.cell
def _(mo):
    mo.md(r"""
    # The art and science of optical design
    ## Ch 1: Introduction: the Art and Science of Design

    Notes: `notes/shannon-1997-art-science-optical-design/ch01-introduction.md`. Use this notebook to try the chapter's ideas:
    re-derive equations, check worked examples, add sliders and plots.
    """)
    return


if __name__ == "__main__":
    app.run()
