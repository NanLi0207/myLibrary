# Contributing to myLibrary

Thank you for helping! Bug reports, ideas, fixes, new features, glossaries for new subjects and
better documentation are all welcome.

## How to contribute

1. **Open an issue** first for anything bigger than a small fix, so we can agree on the idea.
2. **Fork** the repository and create a branch for your change
   (`git switch -c fix-popup-position`).
3. Set up and check your work:

   ```powershell
   uv sync                      # Python + packages
   uv run pytest                # all tests must pass
   uv run ruff check .          # lint
   uv run ruff format .         # format
   ```

   For a change to the reading view or library page, also try it in the browser
   (`uv run scripts/library_server.py`) and say in the pull request what you tested.
4. **Open a pull request** against `main`, describing what changed and why. Small, focused pull
   requests are reviewed fastest.

## Project rules

- **Never commit books**, or text copied from them (they're copyrighted). Git ignores every
  PDF; notes must be written in your own words.
- **Leave `library/` alone.** It's the author's own library (notes, shelves, glossary), included
  as a live example. Contributions go to the tool (`scripts/`, `tests/`, docs). Use your own
  library for testing: it lives in its own folder (see the README's *Where things are stored*).
  A pull request that adds a new subject glossary can include it as an example under
  `examples/glossaries/`, which you're welcome to create.
- **Chinese always comes with English.** Any Chinese in the interface, messages or docs gets its
  English translation next to it: in the popup use `bi(zh, en)` / `biEl(...)` from
  `scripts/reader_static/lookup.js`; in text write e.g. "**加入生词本** (Save word)".
- **Keep the tool subject-neutral.** Nothing in `scripts/` should assume one subject; subject
  knowledge belongs in a library's `glossaries/<subject>.csv` (see the README's *Glossaries*
  section). New subject glossaries are very welcome. Scripts find the library through
  `scripts/paths.py` (`paths.LIBRARY`); never build data paths from a script's own location.
- **Add or update tests** for changes in behavior (`tests/`).
- Follow the existing style: plain, readable Python; comments that explain *why*.

## Contributor terms

By submitting a contribution (code, documentation, glossary entries or anything else) to this
repository, you agree that:

1. You wrote it yourself, or otherwise have the right to submit it under these terms.
2. Your contribution is licensed under the project's license, the
   [PolyForm Noncommercial License 1.0.0](LICENSE), like the rest of the project.
3. In addition, you grant Nan Li, the project's maintainer, a perpetual, worldwide,
   non-exclusive, royalty-free, irrevocable license to use, copy, modify, distribute and
   sublicense your contribution for any purpose, **including commercial purposes**, such as the
   paid ready-to-use package of myLibrary. This lets the project offer that package,
   which supports its development.

You keep the copyright in your contribution.

## Code of conduct

Be kind and patient, assume good intentions, and keep discussions about the work.
