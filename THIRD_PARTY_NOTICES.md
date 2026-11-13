# Third-party software

myLibrary uses the following software. Whoever distributes myLibrary together with it, as in
the ready-to-use package, must include the licence texts and copyright notices named here, and
meet the further conditions listed for some components (section 5). This file lists what the
package actually contains (checked in the built package, 2026-11-13); open release questions are
in section 6.

Where the texts are, in the ready-to-use package:
- `third_party_licenses/`: the reading view's components, the Python runtime's licence and the
  notices for software incorporated in Python, FlatBuffers (its wheel ships none), the
  libraries inlined in markdown-it's browser build, ONNX Runtime's licence and notices, ECDICT,
  and `GEOS-LGPL-NOTICE.txt` (GEOS's binaries, corresponding source and how to replace them).
- `runtime/site-packages/<package>.dist-info/` (and the `LICENSE-3RD-PARTY.txt`,
  `licenses/` and font licence files each package ships): every other Python package's own
  licence texts, as the package's authors provide them.
- In a source checkout the same Python packages' texts are under `.venv/Lib/site-packages/`.

## 1. The reading view (bundled; downloaded by myLibrary on first start in a source checkout)

| Component | Used for | License |
|---|---|---|
| [PDF.js](https://github.com/mozilla/pdf.js) 4.10.38, Mozilla Foundation | The PDF viewer in the reading view | Apache-2.0 (`third_party_licenses/PDF.js-LICENSE.txt`). It includes Adobe's CMaps (BSD-3-Clause, `.cache/reader/pdfjs/web/cmaps/LICENSE`) and the standard fonts from Foxit (BSD-style, `web/standard_fonts/LICENSE_FOXIT`) and Liberation (SIL OFL 1.1, `web/standard_fonts/LICENSE_LIBERATION`). |
| [ECDICT](https://github.com/skywind3000/ECDICT), Copyright (c) Linwei | The offline English–Chinese dictionary | MIT (`third_party_licenses/ECDICT-LICENSE.txt`) |
| [markdown-it](https://github.com/markdown-it/markdown-it) 15.0.3, Copyright (c) 2014 Vitaly Puzrin, Alex Kocharin | The notes' preview (its browser build) | MIT (`third_party_licenses/markdown-it-LICENSE.txt`) |
| Inlined in markdown-it's browser build: [entities](https://github.com/fb55/entities) (Felix Böhm), [linkify-it](https://github.com/markdown-it/linkify-it), [mdurl](https://github.com/markdown-it/mdurl), [uc.micro](https://github.com/markdown-it/uc.micro), [punycode.js](https://github.com/mathiasbynens/punycode.js) | URL, entity and Unicode handling in the preview | entities: BSD-2-Clause; the others: MIT (texts and versions: `third_party_licenses/markdown-it-bundled-LICENSES.txt`; argparse, markdown-it's command-line dependency, isn't in the build) |
| [KaTeX](https://github.com/KaTeX/KaTeX) 0.19.1, Copyright (c) 2013-2020 Khan Academy and other contributors | Maths in the notes' preview: `katex.min.js`, `katex.min.css` and its WOFF2 fonts (built from [KaTeX/katex-fonts](https://github.com/KaTeX/katex-fonts), Copyright (c) 2018 Khan Academy, also MIT) | MIT (`third_party_licenses/KaTeX-LICENSE.txt`) |

## 2. The Python runtime (bundled)

| Component | License |
|---|---|
| Python 3.14.10 (python-build-standalone build, from uv) | PSF License (`third_party_licenses/Python-LICENSE.txt`, which also holds the Windows build's conditions for Microsoft's distributable code, and the bzip2, Zstandard and Tcl/Tk notices) |
| Software incorporated in Python: OpenSSL 3.5.9 (`libssl`/`libcrypto` DLLs), expat, libffi (`libffi-8.dll`), zlib (zlib-ng), libmpdec, mimalloc, SipHash, Mersenne Twister and the other parts Python's own documentation lists | Their notices, verbatim from CPython 3.14.10's "Licenses and Acknowledgements for Incorporated Software": `third_party_licenses/Python-incorporated-software.txt` (OpenSSL: Apache-2.0) |
| SQLite 3.53.1 (`sqlite3.dll`) | Public domain |
| Tcl/Tk 9.0.4 (`tcl90.dll`, `tcl9tk90.dll`) and libtommath (`libtommath.dll`) | Tcl/Tk licence (BSD-style, in `Python-LICENSE.txt`); libtommath: public domain (Unlicense). (The package leaves out `tkinter`; these DLLs come with the runtime.) |
| Microsoft Visual C++ runtime (`vcruntime140.dll`, `vcruntime140_1.dll`; `msvcp140*.dll` in `numpy.libs/` and `shapely.libs/`) | Microsoft's distributable-code terms (see `Python-LICENSE.txt` and `shapely-*.dist-info/licenses/LICENSE_win32`) |

## 3. Python packages (bundled: the core dependencies in uv.lock)

| Package (version in the package) | License | Bundled native parts and their notices |
|---|---|---|
| numpy 2.5.4 | BSD-3-Clause (and bundled components under 0BSD, MIT, Zlib, CC0-1.0) | OpenBLAS 0.3.34 (BSD-3-Clause), LAPACK (BSD-3-Clause-Open-MPI) and the GCC runtime (GPL-3.0-or-later WITH GCC-exception-3.1) in `numpy.libs/libscipy_openblas64_*.dll`: all in `numpy-*.dist-info/licenses/LICENSE.txt` |
| pypdf 6.21.4 | BSD-3-Clause | — |
| pypdfium2 5.14.0 (with PDFium 156.0.8076) | BSD-3-Clause / Apache-2.0, plus PDFium's dependency licenses | `pdfium.dll`: PDFium (BSD-3-Clause) with abseil, AGG, fast_float, FreeType, ICU, Little CMS, libjpeg-turbo, OpenJPEG, libpng, LLVM libc, simdutf, zlib: texts in `pypdfium2-*.dist-info/licenses/` |
| rapidocr 3.10.0 | Apache-2.0 | Its PP-OCR models (`rapidocr/models/*.onnx`, from Baidu's PaddleOCR, Apache-2.0): `rapidocr-*.dist-info/licenses/MODEL_LICENSES.md` |
| onnxruntime 1.31.1 | MIT | `onnxruntime.dll`: `third_party_licenses/onnxruntime-LICENSE`, `third_party_licenses/onnxruntime-ThirdPartyNotices.txt` (myLibrary runs it with the CPU provider only) |
| flatbuffers 25.12.19 (used by onnxruntime) | Apache-2.0 | Its wheel has no licence file: `third_party_licenses/FlatBuffers-LICENSE.txt` (Apache-2.0, from the project's v25.12.19 release) |
| protobuf 7.36.2 (used by onnxruntime) | BSD-3-Clause | `protobuf-*.dist-info/LICENSE` |
| opencv-python-headless 5.0.0.93 (OpenCV 5.0.0, used by rapidocr) | Apache-2.0 | OpenCV with libjpeg-turbo, libpng, zlib, libtiff, libwebp, OpenJPEG and CLAPACK built in: `cv2/LICENSE.txt`, `cv2/LICENSE-3RD-PARTY.txt`. **Not in the package:** the wheel's FFmpeg plugin `cv2/opencv_videoio_ffmpeg500_64.dll` (FFmpeg 7.1, LGPL-2.1), left out by `build_package.py` because OpenCV loads it only to open video, which myLibrary doesn't do; `cv2/LICENSE-3RD-PARTY.txt` still describes it, as the wheel ships that file |
| shapely 2.2.0 (used by rapidocr) | BSD-3-Clause | **GEOS 3.14.1 (LGPL-2.1)** as `shapely.libs/geos-*.dll`, `geos_c-*.dll`: `shapely-*.dist-info/licenses/LICENSE_GEOS` (see section 5) |
| pyclipper 1.4.0 (used by rapidocr) | MIT | The Clipper library (Boost Software License 1.0; its text is required only with source copies) |
| pillow 13.0.0 | MIT-CMU | FreeType 2.14.3 (FreeType License), Little CMS 2.19, libwebp 1.6.0, libavif 1.4.2, libjpeg-turbo, OpenJPEG 2.5.4, zlib-ng, libtiff 4.7.2: all in `pillow-*.dist-info/licenses/LICENSE` (no raqm, FriBiDi, HarfBuzz or libimagequant in this build) |
| reportlab 5.1.0 | BSD | Fonts kept in `reportlab/fonts/`: Bitstream Vera (`Vera*.ttf`, `bitstream-vera-license.txt`) and DarkGarden (GPL-2.0-or-later with a font exception; its source `DarkGarden.sfd`, readme and both licence files are there; see section 5). **Not in the package:** the wheel's Type 1 core fonts (`_a______`, `_ab_____`, `_abi____`, `_ai_____`, `_eb_____`, `_ebi____`, `_ei_____`, `_er_____`, `callig15`, `cob_____`, `cobo____`, `com_____`, `coo_____`, `sy______`, `zd______`, `zx______`, `zy______`, each `.afm` and `.pfb`), which come with no licence text, and its test font `hb-test.ttf`: left out by `build_package.py`; ReportLab's PDF text output uses its built-in metrics (`reportlab/pdfbase/_fontdata*.py`) or a system TrueType font, not these files |
| cryptography 50.0.2 (opens copy-protected PDFs) | Apache-2.0 OR BSD-3-Clause | OpenSSL 4.0.3 built in (Apache-2.0): `cryptography-*.dist-info/licenses/` |
| cffi 2.1.1 (used by cryptography) | MIT-0 | — |
| pycparser 3.12 (used by cffi) | BSD-3-Clause | — |
| requests 2.34.2 | Apache-2.0 | Its NOTICE: `requests-*.dist-info/licenses/NOTICE` |
| urllib3 2.8.0, idna 3.20, charset-normalizer 3.5.2 (used by requests) | MIT, BSD-3-Clause, MIT | — |
| certifi 2026.10.23 (used by requests) | MPL-2.0 (unmodified; its source is the package itself) | — |
| tqdm 4.70.1, colorlog 6.12.0, colorama 0.4.6 (used by rapidocr) | MPL-2.0 AND MIT, MIT, BSD-3-Clause | — |
| omegaconf 2.4.0 (used by rapidocr) | BSD-3-Clause | The ANTLR 4 runtime (BSD-3-Clause): `omegaconf-*.dist-info/licenses/ATTRIBUTION/LICENSE-antlr4` |
| pyyaml 6.0.3, six 1.17.0, packaging 26.3 | MIT, MIT, Apache-2.0 OR BSD-2-Clause | — |

The development and optional groups are not in the package: scipy, sympy (`science`,
BSD-3-Clause), matplotlib (`science`, Matplotlib License, PSF-based), optiland (`optics`, MIT),
rayoptics (`optics`, BSD-3-Clause), and the test tools.

## 4. Downloaded separately, only at the user's request (not in the package)

| Component | How | License, as declared by its publisher |
|---|---|---|
| Pix2Text MFR 1.5 formula model by breezedeus (`encoder_model.onnx`, `decoder_model.onnx`, `tokenizer.json`, its model card) | Downloaded by the user, after an explicit choice in the ∑ dialog (or `formula_ocr.py --setup`), from https://huggingface.co/breezedeus/pix2text-mfr-1.5 at the pinned revision `1cef9f0bdcd6a4c63df7de1311fb0894593340cc`, each file checked against its SHA-256; stored in `%APPDATA%\myLibrary\formula-ocr\` (package) or `.cache/formula-ocr/` (source checkout), with its model card | The model card declares `license: mit`. It states the model uses Microsoft's TrOCR architecture, "starting with its initial values and retrained using a dataset of mathematical formula images"; the training data isn't otherwise described, and the test data comes from images users uploaded to the Pix2Text online service. That declaration is the publisher's: it doesn't by itself establish rights in the training data, which haven't been audited (docs/FORMULA_OCR_LICENSES.md). myLibrary doesn't redistribute the weights. |
| [Pix2Text](https://github.com/breezedeus/Pix2Text) (code) | Not used: myLibrary's own adapter runs the model with ONNX Runtime | MIT |

## 5. LGPL and GPL components in the package

| Component | Where | Linking | Replaceable by the user | Corresponding source |
|---|---|---|---|---|
| GEOS 3.14.1, LGPL-2.1 | `runtime/site-packages/shapely.libs/geos-bf067cd6ff74ee0ad5f3ff52c7ef08c9.dll`, `geos_c-6dd9fd915eef8a7928285416bef1e666.dll`, byte-identical to Shapely 2.2.0's wheel | Dynamically linked: Shapely's `lib` and `_geometry_helpers` modules import `geos_c`, which imports `geos` (loaded at run time when RapidOCR runs) | Yes: separate DLLs; how, in `third_party_licenses/GEOS-LGPL-NOTICE.txt` section 4 | GEOS 3.14.1's official tarball (SHA-256 `3c20919c…f7e716`, equal to GEOS's GitHub release digest) and Shapely's build scripts at tag 2.2.0, as prepared release assets (`geos-3.14.1.tar.bz2`, `shapely-2.2.0-geos-build-materials.zip`; **not yet published**); provenance and evidence limits in `GEOS-LGPL-NOTICE.txt` |
| GCC runtime, GPL-3.0-or-later WITH GCC-exception-3.1 | inside `numpy.libs/libscipy_openblas64_*.dll` | — | — | The GCC Runtime Library Exception permits this distribution without GPL terms for the program |
| DarkGarden font, GPL-2.0-or-later with a font exception | `runtime/site-packages/reportlab/fonts/DarkGarden*` | A data file, unused by myLibrary | — | Its source (`DarkGarden.sfd`) is included |

FFmpeg (LGPL-2.1, OpenCV's video plugin) is **not** in the package (section 3). The LGPL-2.1 text
for GEOS is in `shapely-*.dist-info/licenses/LICENSE_GEOS`. **Not yet resolved for
distribution (section 6):** LGPL-2.1 section 4 asks a distributor of the library's object code to
accompany it with the corresponding source, or to offer equivalent access to it from the same
place; that the upstream projects publish it doesn't by itself discharge the obligation for
myLibrary's own distribution. The source materials are prepared but not published, and their
correspondence to the binaries rests on documents, not a rebuild (`GEOS-LGPL-NOTICE.txt`).
Section 6 of the LGPL also asks that the terms of the combined work permit modification for the
user's own use and reverse engineering for debugging such modifications.

## 6. Open release questions (to be settled before a package is distributed)

1. **GEOS source access** (section 5): publish the prepared source assets with the release
   that distributes the package, and accept or close the evidence limits (the build's logs, a
   checksum-less download, a possible CI cache, no bit-for-bit rebuild). Until then, public
   distribution of the package stays blocked. Whether myLibrary's own licence terms meet
   LGPL-2.1 section 6 needs **legal review** (for any distribution, free or sold).
2. FFmpeg and ReportLab's unlicensed Type 1 fonts: **resolved by leaving them out** of the package
   (2026-11-13); nothing in myLibrary used them.
3. **The formula model's training data**: rights not audited (section 4).
