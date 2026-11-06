# Third-party software

myLibrary uses the following software. Their licenses allow both free and commercial
distribution. Whoever distributes myLibrary together with them, as in the ready-to-use package,
must include their license texts and copyright notices.

## Downloaded by myLibrary on first start (not in this repository)

| Component | Used for | License |
|---|---|---|
| [PDF.js](https://github.com/mozilla/pdf.js) 4.10.38, Mozilla Foundation | The PDF viewer in the reading view | Apache-2.0 (the `LICENSE` file inside `.cache/reader/pdfjs/`) |
| [ECDICT](https://github.com/skywind3000/ECDICT), Copyright (c) Linwei | The offline English–Chinese dictionary | MIT |

## Python packages (installed by `uv sync`)

| Package | License |
|---|---|
| numpy | BSD-3-Clause (and bundled components under 0BSD, MIT, Zlib, CC0-1.0) |
| scipy (`science` group) | BSD-3-Clause |
| sympy (`science` group) | BSD-3-Clause |
| matplotlib (`science` group) | Matplotlib License (PSF-based) |
| pypdf | BSD-3-Clause |
| pypdfium2 (with PDFium) | BSD-3-Clause / Apache-2.0, plus PDFium's dependency licenses |
| rapidocr | Apache-2.0 |
| onnxruntime | MIT |
| reportlab | BSD |
| cryptography (opens copy-protected PDFs; its Windows build includes OpenSSL) | Apache-2.0 OR BSD-3-Clause; OpenSSL: Apache-2.0 |
| cffi (used by cryptography) | MIT-0 |
| pycparser (used by cffi) | BSD-3-Clause |
| optiland (optional `optics` group) | MIT |
| rayoptics (optional `optics` group) | BSD-3-Clause |

These packages also install their own dependencies, each under its own license; `uv tree`
lists them all. The license text of each installed package is in its folder under
`.venv/Lib/site-packages/` (`*.dist-info/`); in the ready-to-use package, under
`runtime/site-packages/`.
