# 测试/示例书库 (Test & Demo library)

This folder is the **canonical** Test & Demo library: a complete myLibrary library (catalog,
PDFs, notes, glossary, reading log, review progress, a topic note) that anyone can clone and
share. It is kept in git, PDFs included, and is never opened or changed directly:

- **Test & Demo mode** (📚 on the library page, or `Start myLibrary Dev.cmd` → 2) opens a
  **working copy** of it in this computer's `.myLibrary-local/test-library-working/`, made on
  first use. Your changes there are kept across restarts until you choose
  **重置 (Reset)** in the launcher's Test & Demo menu (the replaced copy is kept once, in
  `.myLibrary-local/test-library-previous/`).
- **Automated tests** copy it into their own temporary folders (`tests/test_test_library.py`);
  they never write here.
- The server refuses to open `test_library/` itself.

`library.toml` marks it (`test_library = true`): it is never backed up, never offered as a
personal library, and its id (`6f1c2a9e-…`) is the same in every clone.

## What's in it (18 documents, 4 negative fixtures, about 3.5 MB)

Two documents are **real** (see *Real documents* below); all others are **synthetic**: made
for this project by `tests/make_test_library.py` from
the project's own dependencies, with invented titles, authors, DOIs (the reserved test prefix
`10.5555`) and text. They contain no text from any real publication. Fonts: only PDF standard
fonts (Helvetica, Times, Courier, Symbol, not embedded) and the Adobe CID font name
`STSong-Light` for Chinese (not embedded; the viewer substitutes a system font). No
third-party font or image is embedded anywhere.

| Type | File | Subject | Covers |
|---|---|---|---|
| book | `books/lumen-2024-primer-geometrical-optics.pdf` | physics/optics | native text, bookmarks, 3 chapters, equations, table, figure, PDF marks (highlight + sticky note with `/NM`) |
| book | `books/vector-2023-notes-linear-algebra.pdf` | mathematics | printed Contents page only (no bookmarks), 4 chapters |
| book | `books/graph-2022-algorithms-example.pdf` | computer science | code listing, a landscape page, a page rotated 90° |
| book | `books/li-2021-short-history-writing.pdf` | humanities | Chinese text, Unicode accents and symbols |
| book | `books/cell-2020-cell-biology-field-guide.pdf` | biology | image-only scan, slightly skewed, no text layer |
| book | `books/bone-2019-human-anatomy-review-sheets.pdf` | medicine | scan with a **genuine OCR layer** (rapidocr, via `scripts/ocr_pdf.py`) |
| book | `books/mean-2018-statistics-mixed-pages.pdf` | mathematics | mixed: pages 1–2 searchable, 3–4 image-only |
| book | `books/unknown--field-notes-without-metadata.pdf` | social sciences | incomplete metadata (no author, year or PDF Info) |
| book | `books/format-1999-legacy-document-structure.pdf` | computer science | hand-written PDF 1.3, classic xref table |
| paper | `papers/node-2024-sparse-graphs-fast-search.pdf` | computer science | two columns, figure, DOI |
| paper | `papers/photon-2023-thermal-lensing-synthetic-laser-rod.pdf` | physics/optics | two columns, equations, table |
| paper | `papers/pulse-2022-synthetic-cohort-study-sleep-memory.pdf` | biology/medicine | AES-256 encrypted, empty user password (as publisher PDFs) |
| paper | `papers/node-2023-sparse-graphs-fast-search.pdf` | computer science | near-duplicate (preprint of the 2024 paper, no DOI): kept as its own item |
| paper | `papers/survey-2021-reading-habits-students.pdf` | social sciences | one column, table |
| thesis | `theses/proof-2020-learning-shortest-paths-synthetic-graphs.pdf` | computer science/mathematics | PhD title page, contents, references, appendix |
| thesis | `theses/zhang-2021-urban-memory-oral-history.pdf` | humanities | Chinese title page (硕士学位论文, Master's thesis) |
| paper (real) | `papers/collard-2023-optimizing-internal-phase-reference-shape.pdf` | physics/optics | a real publisher PDF (PDF 1.6, embedded fonts, figures, equations, references), 12 pages |
| paper (real) | `papers/dashnow-2014-ten-simple-rules-writing-plos.pdf` | computational biology / scientific writing | a real short article, 5 pages |

**Negative fixtures** (`fixtures/`, not in the catalog, so the library itself never shows
them): `encrypted-with-password.pdf` (user password `test`), `truncated.pdf` (cut off at 60 %),
`not-a-pdf.pdf` (a web page with a .pdf name), `Downloaded copy (1).pdf` (byte-identical to the
optics book: ＋ Add must file it as a repeat into `archive/`).

**Synthetic study data**: chapter 1 of the optics book and the PhD thesis ticked; "Last read"
lines; notes in the student's own (invented) words in the optics book's chapter 1 and the 2024
paper; two saved words (`vocabulary.md`) and one review answer; a topic note
(`notes/topics/aperture.md`); two days of reading log; a `physics` glossary (物理 Physics).

`MANIFEST.json` lists every PDF with its id, SHA-256, size, pages, the features above and what
the tests expect (`expect`); `tests/test_test_library.py` checks the files against it.

Expected app behaviour, recorded from the generator's run (ROADMAP, Limitations, L-T1–L-T3):
- the image-only scan and the legacy PDF get no chapter notes ("no table of contents found");
- the OCR'd book and the mixed book get chapter titles with the first section's heading run
  into them (e.g. "Means and Medians 1.1 The sample mean");
- the item without author or year is named `unknown--…` (two hyphens).

## Licence and provenance

**Synthetic documents** were created for myLibrary and are distributed with it under the
repository's licence (`LICENSE`).

**Real documents** are included unchanged (byte for byte), each under its own licence, checked
at the source on 2026-11-09. `MANIFEST.json` holds the same details for each (`source`:
`real`), and `tests/make_test_library.py` (`REAL`) refuses to build with any other file.

1. **Optimizing the internal phase reference to shape the output of a multimode optical fiber**
   — Liam Collard, Linda Piscopo, Filippo Pisano, Di Zheng, Massimo De Vittorio, Ferruccio
   Pisanello. *PLOS ONE* 18(9): e0290300 (2023), Public Library of Science.
   - Source: <https://doi.org/10.1371/journal.pone.0290300>; PDF:
     `https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0290300&type=printable`
   - Category / subject: research paper / physics, optics.
   - **Licence: CC BY 4.0** (<https://creativecommons.org/licenses/by/4.0/>).
   - **Attribution (required):** Collard L, Piscopo L, Pisano F, Zheng D, De Vittorio M,
     Pisanello F (2023) Optimizing the internal phase reference to shape the output of a
     multimode optical fiber. PLoS ONE 18(9): e0290300.
     https://doi.org/10.1371/journal.pone.0290300. Licensed under CC BY 4.0; not modified.
   - Evidence: the article page states "This is an open access article distributed under the
     terms of the Creative Commons Attribution License", linked to CC BY 4.0; page 1 of the
     PDF prints the same. No figure is marked as reproduced from elsewhere.
   - SHA-256 `bb943236476a97bae2ce84f0455c35f9cf535bd55a8977da727372e65b5a32e1` (2,602,652
     bytes). Covers: a real publisher's PDF (fonts, figures, equations, references, DOI).
2. **Ten Simple Rules for Writing a PLOS Ten Simple Rules Article** — Harriet Dashnow, Andrew
   Lonsdale, Philip E. Bourne. *PLOS Computational Biology* 10(10): e1003858 (2014), Public
   Library of Science.
   - Source: <https://doi.org/10.1371/journal.pcbi.1003858>; PDF:
     `https://journals.plos.org/ploscompbiol/article/file?id=10.1371/journal.pcbi.1003858&type=printable`
   - Category / subject: article (editorial format) / computational biology, scientific
     writing.
   - **Licence: CC0 1.0** public domain dedication
     (<https://creativecommons.org/publicdomain/zero/1.0/>). No attribution required; the
     citation is given as a courtesy.
   - Evidence: the article page states "... may be freely reproduced, distributed,
     transmitted, modified, built upon, or otherwise used by anyone for any lawful purpose.
     The work is made available under the Creative Commons CC0 public domain dedication.";
     page 1 of the PDF prints the same.
   - SHA-256 `93b6752052ef18f987fee5be87009e5027be03bf78624ea160c9229bb20db5e9` (451,576
     bytes). Covers: a short real article in another subject and an older PDF producer.

Not included (2026-11-09): an open **textbook** (the clearly CC BY ones found, e.g. OpenStax,
are tens of MB) and a **thesis** (the CC BY candidate found was a self-deposited record whose
uploader couldn't be verified as the rights holder, with interview data and a student number
in its file name). Any document added must get all of the details above; open access alone is
not enough.

## Adding a fixture

1. Add it to `tests/make_test_library.py` (`build()` for a library document, `doc(...)` with
   its features and `expect`; `negative_fixtures()` for a file that must not open). A new
   library document also gets a line in `FIXED_IDS` (a fresh UUID4); never change or reuse
   an existing id.
2. Download the real documents (their `pdf_url` above, into an empty folder), move this
   folder away, rebuild with
   `uv run tests/make_test_library.py --out test_library --real-from <that folder>`, and put
   this README.md back (the generator doesn't write it).
3. A rebuild is reproducible: the same ids (`FIXED_IDS`), the same date (`CORPUS_DATE`),
   seeded encryption, so an unchanged corpus rebuilds byte for byte (checked 2026-11-09: two
   rebuilds, 64 files identical) and `git status test_library` shows only what you changed.
4. Run `uv run pytest tests/test_test_library.py` and keep the whole library under 50 MB.

Never put a private book, note or real person's data here: the folder is public.
