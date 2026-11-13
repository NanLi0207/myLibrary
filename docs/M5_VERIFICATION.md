# M5d + M5e verification / 验证记录

Status (2026-11-13): **M5d image paste and M5e formula OCR committed (`4e4abcef348566c4a10c89c6f9ada2798a9b14a0`),
pushed and CI-verified** (https://github.com/NanLi0207/myLibrary/actions/runs/43403052717:
Python tests and Ruff, browser shard 1, browser shard 2 and notes-panel-closed browser tests
passed; success on the first attempt, no reruns). The Windows package passed 25 of 25 automated
acceptance checks (below); **not manually accepted, and no public Beta released**: the package
is not approved for public redistribution (ROADMAP section 2, L30). ☁ Automatic Git backup is
deferred (not fixed): ROADMAP L29. 已提交、推送并通过 CI；安装包通过自动化验收；尚未人工验收，公开测试版尚未发布。
The verification below was made on the working tree before the commit, on baseline
`69c684aac10dbeac283778ee256609de549595a1` (`main`, equal to `origin/main` then).

## History / 经过

1. 2026-11-12, morning: the inherited implementation was completed and tested (implementer:
   Codex). Its claim of complete Edge results "on the final implementation" was found
   unsupported by the first independent review (Claude Code): the browser suites had started
   before the last source and test changes. That evidence is superseded; its files remain in
   `.cache/m5-verification/`.
2. Round 1 (implementer: Claude Code), frozen-tree evidence
   `.cache/m5-verification-final-20261112T140737Z/` (accepted; superseded by later changes).
3. Round 2, after Codex's re-review, frozen-tree evidence
   `.cache/m5-verification-final-20261112T151434Z/` (superseded by later changes).
4. Codex's third review: M5d/M5e have credible passing evidence; automatic Git backup still had
   **five High-severity** publication, index and recovery issues, and the OCR install could lose
   a valid model if cut off between its two renames. The owner changed strategy: defer the
   automatic Git backup, fix the install recovery. Round 3 below.

All earlier evidence folders are kept unchanged (ignored, this computer only).

## Round 3 / 第三轮

**☁ Automatic Git backup deferred (not fixed).** `backup.DEFERRED = True`: `back_up()` returns
`{"ok": false, "deferred": true, "message": …}` and does nothing else in git (no commit, no push,
no index or ref change); a recovery record left by an earlier backup is only reported, never
replayed or deleted. The library page keeps the button visible as **☁ Back up (paused)** with
the reason, never shows "Backing up…" for it, and offers **💾 Back up** meanwhile even with no
backup folder chosen. The user's own git use is unaffected. The round-1/round-2 implementation
is kept, unused by the app, for the redesign: `tests/test_backup.py` runs it with DEFERRED off,
so its behaviour and the cases found unsafe stay documented. Passing there does not make it
safe: the third review's High findings stay open (L29). B2 (non-ASCII names) is handled in that
code but counts as open while the feature is paused.

**OCR model install recovery.** Under the install lock (an OS lock, released when the process
ends): the download is verified before the swap; the installed copy is moved aside and deleted
only once the verified new copy is in place; a failed swap whose rollback also fails keeps the
old copy whole in `.old-*`. `_recover` (run first by every install, and by `status()` and
recognition through `recover_interrupted()`) puts a whole copy (pinned SHA-256) back when the
installed model isn't whole, and deletes leftovers only when the model is whole or they aren't:
the last whole copy is never deleted; recovery needs no network.

Tests added in round 3:
- `tests/test_backup_deferred.py`: `test_deferred_backup_changes_nothing_in_git` (refs, HEAD,
  the index file's exact bytes, staged files, status, the remote's refs and the git folder's
  files all identical; an unpushed user commit, a staged file and a pasted image present),
  `test_a_leftover_recovery_record_is_reported_never_replayed_or_deleted`,
  `test_manual_git_work_goes_on_as_usual`, `test_the_folder_backup_still_holds_notes_and_images`,
  `test_the_page_says_the_git_backup_is_paused` (page flags and text, `/api/backup` answer).
- `tests/test_formula_ocr.py`: `test_a_crash_between_the_renames_is_recovered_without_a_download`
  (sockets blocked), `test_only_a_whole_copy_is_put_back`,
  `test_a_failed_install_after_a_crash_still_leaves_a_working_model`,
  `test_a_failed_swap_that_cant_be_undone_keeps_the_old_copy`.
- `tests/test_backup.py`: an autouse fixture runs the kept implementation with DEFERRED off.

Library page, checked by hand in Edge (temporary library in a repository with an upstream,
`MYLIBRARY_LIBRARY` pointed at a temporary folder): the button read "☁ Back up (paused)" with
its explanation as tooltip; 💾 Back up was visible without a backup folder; clicking ☁ showed
the "temporarily unavailable" message and no "Backing up…"; no page errors; HEAD unchanged.

Rounds 1–2 changes that stand (see ROADMAP section 11): merge image copies are idempotent and a
failed merge archives nothing; served images are validated in full with a digest ETag;
formulas are written with delimiters that read back whole; `\cfrac` is kept; Redo and IME
paste are tested; one model install at a time (OS lock).

## Frozen-tree verification, round 3 / 冻结工作区上的验证（第三轮，2026-11-12）

Evidence folder: `.cache/m5-verification-final-20261112T160840Z/` (ignored; logs, JUnit XML,
`manifest-start.json` SHA-256 `908ac208…cbcba135`, `manifest-run.json` `051a2646…26559b8`).
The start manifest holds the branch, HEAD, exact `git status`, an empty staging area and the
SHA-256 of all 512 non-ignored files (source, tests, configuration, documentation, `library/`,
`test_library/`). After **every** suite the tree was hashed again: identical each time, and at
the end. Suites ran one after another with the repository's `.venv` (no sync or install).
Environment: Windows 11, Python 3.14, Edge (msedge channel), Playwright 1.64.1.

| Suite | Start → end (+01:00) | Result |
|---|---|---|
| `ruff check .`, `ruff format --check .`, `git diff --check` | 17:08:40 | passed |
| `tests/browser/shards.py --check 2` (partition) | 17:08:40 → 17:08:45 | passed |
| Python, `pytest -q -rs` | 17:08:45 → 17:12:12 | 822 passed, 11 skipped, 0 failed (833) |
| Edge shard 1/2 | 17:12:12 → 17:20:52 | 106 passed, 105 deselected (in shard 2), 0 failed |
| Edge shard 2/2 | 17:20:53 → 17:30:05 | 105 passed, 106 deselected (in shard 1), 0 failed |
| Notes panel closed: CI's `test_reading`, `test_marks`, `test_saving` + `test_notes_assets_formula` | 17:30:05 → 17:34:33 | 46 passed, 0 failed |
| Real model, offline (sockets blocked): `test_formula_ocr.py -k real_model` | 17:34:33 → 17:34:45 | 8 passed, 38 deselected |
| Real model through HTTP and the Edge UI | 17:34:45 → 17:34:54 | 1 passed |

The 11 Python skips are symlink tests this Windows account may not run (privilege "not
held"); they are not passing checks. Junction, traversal, containment, long-path, concurrency
and atomic-write tests did run.

SHA-256 of the 28 M5d/M5e files as tested (start manifest; identical after every suite):

```
eb52ffbe112595858dfe969732166ba306719f7b58c49e25da7a086893e0fe06  .gitignore
05ab44604570a16716816c80d6ae51fc3a8c6908e3e6646c9a6245c8689d926e  DEVELOPMENT_SPEC.md
038e6a1bd98a740b12aff2b4e88d37624eac92b8d93ccf9f66870ee467cfa4f3  ROADMAP.md
07eb7edcd9b3e4791e00817894c7521a68b5f14fb9032baed286c34e73f409b7  docs/USER_GUIDE.md
64546c4b8e32d4d918423ec944f0be48de4963a9ad829ec1495f3d8d46d9d0ee  docs/FORMULA_OCR_LICENSES.md
8095c9fc0be9173eed976eaea9142da7ccbbbe726f9f29b931b48f3a992c8460  docs/M5_VERIFICATION.md (before this rewrite)
afe837f7166eeecb843600abdbbc74a472ce9ff9c30e0d3ca81bc05da933df5f  scripts/add_book.py
7f4c0bf2105c3e44d44d0f0fb77b1ebce48df5f9e3150aca2930eb23bb688a3d  scripts/backup.py
3e9a0e9328be5bf0c25635b5b8906af6672e053f0eeb86860bf1af0cf9fecfb7  scripts/formula_ocr.py
5cc23249571182261dd793be048c145c304f35653a05e95591048fcae625dd14  scripts/image_check.py
7756031aa1b4121235222f1fc922d32c7d180e95e46f5df80fea6946e916f673  scripts/library_jobs.py
cbcd705e3c53fb36b5943a2cfba48458774e8e84ab4322303bf1fe9b0702f633  scripts/library_page.py
7c7ccb5f4e3b2952022f207f8ce5506c2601db46508c0f21670e312431d9d386  scripts/library_server.py
1d17081120e1d7f050afd56999e798ce25b140edf2633318ac7c6469d5aef685  scripts/notes_store.py
cb6b9428734b5b486b9e88de01963eb2b07533e1e05eb12d4efd322d9407fb8e  scripts/reader.py
83943d4304a12111de63e91f28f1da95fa5b6eb1891ce9af0e886f282c5f009d  scripts/reader_static/formula.js
b1fd27714b837229e638b884ff97010202f56f7420163228787d30daf0d82c13  scripts/reader_static/notes.css
c83ffe7a12e334848993c140e03af93d72a2809e146961aa67696a8367e0500d  scripts/reader_static/notes.js
472f287d369a9d9f2760463ba438446abc5fa2ffae150469e88077a5475febf5  scripts/reader_static/preview.js
99066ed8c89778d3fc98c0533d4465288843dbfdc86bcbba38100f3a82a38a23  scripts/safe_io.py
9df37a04220602bd9e3cba244e5f18d2c4de52762e85748749ef01a720d61d8e  tests/browser/test_notes_assets_formula.py
d693aaefe145e380a37e1761ead9e3c22fe6d0a0e3dd99fcbe53638384304c5d  tests/browser/test_notes_format.py
a526834db123877025c5b0ade2187735e5ea66cbf1abefda5122906d586567e6  tests/conftest.py
5577f8f757df3a8d3eb251193ea6040170fa4faa36901f6e4a96ade4a8e42858  tests/test_backup.py
da3013d017bd04ca135162f250743541b412bd377be77b807854a11596733262  tests/test_backup_deferred.py
23fccf7706199e403aa32148a70e9b503a6efc67495ac59acd2822cec72f1766  tests/test_formula_ocr.py
9dc08233a90e866db0f221bf9a2c54a0301f59569b4bed514bf784e0205f52a9  tests/test_note_assets.py
fe37f5ea86d68d8bbeb3e21fa92ddc667963c577f362479e03abec5cc7cbbe52  tests/test_test_isolation.py
```

After the suites, only this file (`docs/M5_VERIFICATION.md`) was rewritten, to record them; no
source, test or configuration file changed. Real-model OCR used six synthetic formulas drawn
with matplotlib (plus dark-mode and transparent versions and one browser round trip): examples,
not an accuracy measure. Mocked recognition replies in the browser tests prove the UI plumbing
only.

## Package and licences / 安装包与许可（2026-11-13）

**Licence remediation (packaging only).** Changed: `package/licenses/` (new:
`FlatBuffers-LICENSE.txt`, verbatim from FlatBuffers v25.12.19; `markdown-it-bundled-LICENSES.txt`,
the licences of entities 8.1.0, linkify-it 6.1.0, mdurl 2.1.0, uc.micro 3.0.0 and punycode.js
2.3.1, which markdown-it 15.0.3's browser build inlines; `Python-incorporated-software.txt`,
CPython 3.14.10's notices for OpenSSL, expat, libffi, zlib, libmpdec, mimalloc and others,
missing from the runtime's own LICENSE.txt), `scripts/build_package.py` (copies them and ONNX
Runtime's licence and notices into `third_party_licenses/`; the build stops if a bundled Python
distribution ships no licence text), `THIRD_PARTY_NOTICES.md` (the full inventory of the built
package, the LGPL/GPL components and the open release questions), `docs/FORMULA_OCR_LICENSES.md`,
`tests/test_build_package.py`; documentation only in `scripts/backup.py` (its docstring now says
it is paused; code identical to round 3: same syntax tree once the module docstring is set
aside), `CLAUDE.md` and `ROADMAP.md` (L29's five findings one by one; L30). No application
behaviour changed, so the full suites weren't rerun (the reviewer to confirm).

**Build and package acceptance.** Evidence: `.cache/m5-package-licensing-20261113T084824Z/`.
Command `uv run scripts/build_package.py` (uv 0.13.7, Python 3.14.10, Windows 10.0.26300) on a
tree frozen first: the SHA-256 of all 516 non-ignored files (`sha256-1-frozen.json`, itself
`ae67461f…308aff8`) was identical after the build and after acceptance. Package:
`dist/myLibrary-0.2.5-win64.zip`, 177,234,531 bytes, SHA-256
`582969322bfc7e75ed3c65605a1b5cb66b6106a923cb2f74c5d9c09f27c6fd2e`, 3,466 files, longest path
125 characters; `third_party_licenses/` holds ECDICT, FlatBuffers, KaTeX, markdown-it and its
bundled libraries, ONNX Runtime (licence and notices), PDF.js, Python and the Python-incorporated
notices; the licence check finds no bundled distribution without a licence text.

Acceptance (`package_acceptance.py`, in the evidence folder): the zip unzipped outside the
repository, own USERPROFILE/APPDATA/LOCALAPPDATA/TEMP, PATH = Windows + git only (no uv or
Python), a temporary library and a synthetic PDF; Edge through Playwright as the client.
**21 of 21 passed:** package mode; PDF reading; a note edited, saved and typeset by KaTeX; image
paste, storage, display and display after reopening; ONNX Runtime 1.31.1 in the packaged Python;
the model not downloaded before consent and no account, key or payment asked for; the model
installed after consent (pinned, checked); an interrupted install recovered without a download;
real OCR through the packaged UI (three candidates, the right integral first, inserted and
saved); the ZIP backup holding notes and the image; "☁ Back up (paused)" with git's refs, HEAD,
log, index bytes and the remote unchanged; no page errors; clean quit; note, image and model
there after a restart; recognition in the packaged Python with all network connections blocked.

Disclosed along the way: a first attempt (`.cache/m5-package-licensing-20261113T084635Z/`,
marked INVALID) stopped at the new licence check, which matched file names only and missed
pypdfium2's licences in folders; its acceptance run had used the previous zip. The check was
fixed (by path) with a test. On the rebuilt zip a first run then failed 3 checks through two
faults of the acceptance script (typing before the note had loaded; comparing the whole git
status while the running server rewrites its own `.myLibrary/server.json`); with those fixed
(as the browser tests' `notes_settled`, and git state compared by refs, log, index bytes and
remote, `.myLibrary/` aside) the full run passed. Both runs' logs are kept (`run1-*`).

The licence audit's open questions are in THIRD_PARTY_NOTICES.md section 6 and ROADMAP L30:
LGPL-2.1 source access for FFmpeg 7.1 (OpenCV's plugin DLL, never loaded by myLibrary) and
GEOS 3.14.1 (Shapely, loaded when scan OCR runs), with legal review for a sold package;
ReportLab's Type 1 core fonts without licence text (unused); the formula model's unaudited
training data (its card declares MIT; the weights aren't bundled). Proposals, not done: leave
out FFmpeg's plugin DLL and `reportlab/fonts/` (each needs its own check and approval).

## Beta packaging corrections / 公开测试版的安装包修正（2026-11-13）

**Changes (packaging only; no application code):** `scripts/build_package.py` leaves out
exactly OpenCV's FFmpeg plugin `cv2/opencv_videoio_ffmpeg500_64.dll` (the only FFmpeg file in
the package), ReportLab's test font `reportlab/fonts/hb-test.ttf` and its unlicensed Type 1 core
fonts (17 families, `.afm` and `.pfb`), keeping OpenCV, the Vera fonts and DarkGarden with their
licences and source; the build stops if any FFmpeg file remains or a kept file is missing.
`package/licenses/GEOS-LGPL-NOTICE.txt` (new, shipped in `third_party_licenses/`): the GEOS
binaries and their hashes, the corresponding source and build materials with their evidence
and limits, and how to replace the DLLs. `THIRD_PARTY_NOTICES.md`, `docs/FORMULA_OCR_LICENSES.md`,
ROADMAP L30 and `tests/test_build_package.py` updated.

**GEOS corresponding source (prepared, not published).** The shipped
`geos-bf067cd6…ef08c9.dll` and `geos_c-6dd9fd91…e1e666.dll` are byte-identical to Shapely 2.2.0's
wheel `shapely-2.2.0-cp314-cp314-win_amd64.whl` (SHA-256 `48dd1d96…a18e`, as pinned in uv.lock;
RECORD hashes match). Shapely's tag 2.2.0 (commit `229c71f7…7454`): `release.yml` sets GEOS 3.14.1,
windows-2025, MSVC 14.44, cibuildwheel v4.2.1; `ci/install_geos.cmd` builds the official
`geos-3.14.1.tar.bz2` unmodified (Release, shared, no tests); the wheel's `DELVEWHEEL` record shows
delvewheel 1.13.1 repairing it from `D:\a\_temp\geos-3.14.1\bin`; the publishing run is
https://github.com/shapely/shapely/actions/runs/37597567800. The tarball (7,013,834 bytes,
SHA-256 `3c20919c…f7e716`) equals the digest published with GEOS's GitHub release 3.14.1 (tag
commit `c389f532…bdb`). Staged release assets (git-ignored, unpublished):
`dist/geos-source-materials/release-assets/` with `geos-3.14.1.tar.bz2`,
`shapely-2.2.0-geos-build-materials.zip` (SHA-256
`267d98b53e3a69f925ca1071a7793837e40e4a187dfb7b74aabb5580cfcc1904`: the build script, workflow,
pyproject, DELVEWHEEL, RECORD, LGPL text, notice, provenance, and Shapely's own BSD-3-Clause
`LICENSE.txt`, verbatim from tag 2.2.0, SHA-256 `4a207eac…f754`, the same text as the wheel's
copy apart from its CRLF line endings) and `SHA256SUMS.txt`. The zip was rebuilt on 2026-11-13
only to add that licence, owner-approved: its eight earlier entries are byte-identical to the
previous zip (`58bf02ee…5fff`, kept in `dist/geos-source-materials/superseded/`); the GEOS
tarball and the application package are unchanged.
**Evidence gap:** the build script downloads the tarball without checking it, the build may have
come from Shapely's CI cache, the run's logs weren't inspected and no bit-for-bit rebuild was
made; correspondence is documentary. Public distribution stays blocked (ROADMAP L30) until the
assets are published with the package and this evidence is accepted, with legal review of
LGPL-2.1 section 6.

**Build and acceptance.** Evidence: `.cache/m5-package-beta-20261113T090810Z/`. Tree frozen
first: SHA-256 of all 517 non-ignored files (`sha256-1-frozen.json`, itself `6997afab…7fb2a`)
identical after the build and after acceptance. Package `dist/myLibrary-0.2.5-win64.zip`,
163,090,459 bytes, SHA-256 `e617e00667e6a0b5b98d549cc2ee9316a37f3f8789c96dc313b46125e781bc76`,
3,431 files; the build left out 36 files; the zip's listing holds none of the excluded names;
no bundled distribution lacks a licence text. **25 of 25 checks passed** on a fresh extraction:
the 21 earlier checks, plus the package's contents (no FFmpeg file, no excluded font, every kept
font, all licence files, GEOS hashes as in the notice, `cv2.pyd` present), image decoding in the
packaged Python (OpenCV and Pillow, PNG and JPEG), and the scan-OCR text layer made by
`ocr_pdf.add_text_layer` on a synthetic scanned PDF twice: (A) with Windows Arial (font
`OCRText`, embedded `ArialMT`) and (B) with Arial made unavailable (font Helvetica, the standard
font, not embedded, so with no ReportLab font file). In both, "Searchable", "layer" and "Optics"
are found by text search, each word's box within 5 pt of where it was drawn (left and right
edges 2.8–5.0 pt), and GEOS 3.14.1 was loaded by the OCR. A first acceptance run on this zip
failed the paused-Git check through the check's own `git status`, which rewrote the index's
cached file times; with the index read first and `git status --no-optional-locks`, the full run
passed (both runs' logs kept, `run1-*`).

## Release acceptance gates still open / 发布前仍需验收

None of these is shown by the tests above:

1. Real-user manual acceptance of screenshot paste (Snipping Tool, browsers, PDF readers).
2. OCR quality on representative real formula images from the user's books.
3. A package install by hand on a clean Windows account: double-click start, Start-menu and
   desktop shortcuts (the automated run used a clean profile but skipped shortcuts and ran
   `python.exe launch.py`).
4. The whole machine offline while the packaged server runs (automated: the packaged Python
   with sockets blocked).
5. Licences (ROADMAP L30): publish the prepared GEOS source assets with the package and accept
   or close the correspondence evidence gap; legal review of LGPL-2.1 section 6; the model's
   training data. Until then the package must not be distributed publicly.
6. GitHub Actions CI for the committed M5d/M5e change (needs owner-approved commit and push).
7. ☁ Automatic Git backup: a separate security redesign (L29) before it may be switched on.

## Limits / 限制

As in ROADMAP L28 and L29: atomic image creation needs hard links (NTFS); no images in topic
notes; images are never garbage-collected; recognition can be wrong (three hypotheses at most,
no calibrated confidence); the 30 s deadline can't interrupt a native call or the model load,
and closing the dialog doesn't stop a running recognition; ☁ automatic Git backup is paused,
so the 💾 folder backup is the backup of notes and images, and a Git-only restore would lack
images. No production, personal or showcase library was used; tests write only into temporary
folders.
