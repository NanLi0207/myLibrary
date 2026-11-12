# myLibrary — Shared AI Development & Review Standard

**Status:** Proposed standard. Adopt only after the owner approves adding the files to the repository.
**Scope:** All AI-assisted work on this repository, regardless of which agent is active.
**Purpose:** One implementation owner, independent review, consistent code, verifiable quality, and no surprises to user data.

## 1. Sources of truth and precedence

Before work, read only the material relevant to the assigned task, starting with:

1. This `docs/AI_DEVELOPMENT.md` — **canonical shared** workflow, quality gates, and code conventions.
2. `CLAUDE.md` — existing myLibrary-specific architecture and safety rules. **Both agents must read it, regardless of the filename.**
3. `ROADMAP.md` — currently approved milestone, acceptance criteria, open issues, and historical IDs.
4. `DEVELOPMENT_SPEC.md` — product constraints and applicable requirements.
5. Relevant code, tests, and user-guide sections; history files only when needed.

The owner's latest explicit instruction controls the task scope and approvals. Preserve all safety constraints from these files; if instructions disagree, follow the stricter non-destructive rule and report the conflict rather than guessing. Do not silently broaden scope. Never treat a proposed roadmap item as authorization to implement it.

`CLAUDE.md` remains the repository's detailed architecture reference for now: do **not** replace, truncate or duplicate it wholesale. `AGENTS.md` and `CLAUDE.md` are tool-compatible entry points; this `docs/AI_DEVELOPMENT.md` is the **single authoritative reference** for cross-agent process and coding conventions. Keep project-specific architecture in `CLAUDE.md`, and current milestone facts in `ROADMAP.md`. If two files disagree on data protection, preserve the stricter safety constraint and report the conflict. Do not silently remove an existing rule.

## 2. Roles and the single-writer rule

Exactly one agent is the **Implementer** for an active milestone. The other is the **Independent Reviewer**. Roles can switch between milestones or after an explicit handoff; they are not permanently assigned to a product.

| Role | Allowed | Not allowed without owner permission |
| --- | --- | --- |
| Implementer | Inspect, design within scope, edit approved files, add tests, run tests, update milestone docs | Commit, push, rebase, force-push, alter real/showcase data, start another milestone |
| Reviewer | Inspect diff and call paths, inspect test evidence, run narrowly justified verification in temporary locations, report findings | Edit source/docs, reformat, install dependencies, commit, push, reset/clean, act as a second implementer |
| Owner | Approves scope, role changes, significant architecture decisions, commits, pushes, and acceptance | — |

**One writer per working tree.** Do not let Claude Code and Codex edit the same checkout simultaneously. The reviewer is read-only with respect to tracked source and the working tree. Prefer a read-only checkout, separate worktree, or a review of a stable diff for strict isolation. If a review command necessarily creates test output, keep it in the existing ignored test-output area or a temporary directory, and disclose it.

Parallel implementation in isolated Git worktrees is **not** enabled by default. It requires the owner's specific approval, separate branches, non-overlapping responsibilities, an integration owner, and explicit integration testing. Never perform automatic merges.

## 3. Session start: mandatory baseline

Before changing files, the Implementer records:

- Assigned role and exact authorized milestone/issue IDs.
- `git status --short`, `git branch --show-current`, `git rev-parse HEAD`, and available remote base.
- Tracked modifications and untracked files already present, including work another agent left behind.
- Relevant instructions, architecture, tests, open limitations and acceptance requirements.
- The smallest reasonable file and API surface to touch.
- Any risky or irreversible operations that require a separate approval.

Existing changes are **not disposable**. The tree may hold uncommitted or untracked work from an earlier session or another agent, such as an unfinished milestone. Inspect it before continuing. Never overwrite another agent's in-progress changes simply to get a clean tree.

An Implementer may send a short plan and then work within the approved scope. A Reviewer should first identify the baseline and changed files, then review without implementing.

## 4. Scope and approval gates

Use these independent gates:

1. **Plan approved:** The owner authorizes the specified milestone/bug work; not a Git commit.
2. **Implementation and local verification:** The Implementer edits and tests locally; no commit or push.
3. **Independent review:** The Reviewer examines correctness, security, data integrity, compatibility, and evidence.
4. **Fix/re-review:** The Implementer fixes accepted findings; the Reviewer rechecks affected areas.
5. **Local commit approved:** Only after the owner explicitly authorizes this commit. Stage **named files only**.
6. **Push approved:** Only after the owner separately authorizes pushing the identified commit SHA.
7. **Exact-commit CI:** Verify the pushed SHA and all required GitHub Actions jobs before claiming CI-verified.

Approval for one gate is **not** approval for a later gate. Never commit or push because tests passed, because the user is absent, or because an agent ran out of usage.

Do not start a future milestone, upgrade dependencies, add broad architecture, bump a release version, change license terms, or redesign the UI merely because it is convenient. Explain and seek approval for material deviations.

## 5. Data safety — higher priority than convenience

- The user's real library is outside the repository and must not be modified in development or tests.
- Repository `library/` is intentionally tracked **frozen showcase content**, including curated non-PDF data. Preserve its tracking. **Never blanket-ignore, untrack, delete, reset, or normalize `library/`.**
- The frozen `test_library/` is protected too. Test writes only in isolated temporary libraries populated with synthetic data.
- Never commit or upload private PDFs, copyrighted screenshots, real notes, credentials, API keys, personal images, OCR weights, caches, generated test assets, or other private data.
- PDFs must stay excluded from the public repository, except any explicitly approved synthetic test fixtures already tracked.
- Do not mutate notes, catalog entries, document UUIDs, paths, marks, reading logs, or user settings without the exact approved behavior.
- User work is archived rather than silently deleted where the existing architecture requires it. No destructive migrations without explicit approval, tested backups, and rollback.
- Preserve README and notes content, BOM, LF/CRLF, final newline, and unknown metadata. Avoid whole-file rewriting and unrelated normalization. Existing bug B33 is **not** permission to normalize files.
- Follow `safe_io.py` for atomic writing, lock-protected read/change/write, Windows long paths, and critical sections; use `catalog` helpers for catalog updates.
- Use the document UUID as identity, not slug, filename, ISBN or DOI. Derive document paths through the catalog row and established safe path helpers.
- Treat all external paths, clipboard data, OCR output, Markdown, PDF contents, and HTTP parameters as untrusted. Keep path containment, symlink/junction checks, MIME/content validation, size limits, safe rendering, and localhost security intact.
- **Network and cost policy.** myLibrary is local-first and offline-first:
  - Core reading, note-taking and library management must not depend on cloud services.
  - Never transmit user notes, PDF contents, screenshots, images or other personal data to an external service without the user's explicit, informed approval.
  - Never introduce a mandatory paid API, subscription or recurring service cost without separate owner approval.
  - Optional provider-based features (for example AI or translation) are possible only when the owner explicitly approves them. They must be opt-in, disclose what will be transmitted, and explain any potential costs; users must be able to keep using all core functionality without enabling any provider.
  - Optional local models must be free to use and license-reviewed; permission is required before large downloads.
  - A milestone's own restrictions in `ROADMAP.md` / `DEVELOPMENT_SPEC.md` take precedence for that milestone (for example, a feature required to be free, local and offline).

**Forbidden cleanup without explicit, scoped approval:** `git reset --hard`, `git clean`, broad `git checkout --`, blanket staging, destructive migrations, rewriting user files, and uninstalling/reinstalling validated model assets merely to start fresh.

## 6. Shared code style: general principles

Both agents follow **the style already established in each module**. Avoid gratuitous refactoring and global reformatting. A touched function should become clearer, not merely different. The project's actual linters/formatters and tests are authoritative over stylistic preference.

- Prefer the smallest cohesive change that solves the user-visible problem.
- Separate concerns: filesystem/data layer, server/API layer, UI/editor logic, OCR adapter, and tests.
- Keep interfaces explicit; avoid hidden global state, magic side effects, unnecessary abstraction, and speculative plugin frameworks.
- Reuse existing helpers and patterns before introducing new helpers.
- Use descriptive names; don't abbreviate core domain concepts without a reason.
- Prefer early validation and precise errors. Never silently swallow a failure that could lose user work.
- Write comments explaining **why** a constraint exists, especially security and concurrency, rather than narrating obvious lines.
- Do not add a dependency, framework, or runtime network access without a documented need and approval.
- Do not make a repository-wide formatting or whitespace change as part of a feature.
- Keep code and tests subject-neutral: do not hard-code optics-domain assumptions into general library application code.

### 6.1 Python

- Python version and dependency policy: follow `pyproject.toml` and `uv.lock` (currently Python >=3.14).
- **Ruff is the single source of truth** for formatting/linting. Current settings: `line-length = 100`, rules `E`, `F`, `I`, `UP`, `B`, and explicit per-file exceptions.
- Use `uv run ruff check .` and `uv run ruff format --check .`. When formatting, apply it only to relevant files unless a separately approved cleanup requires more.
- Let Ruff manage import order and formatting. Do not fight its string quoting, wrapping, or trailing-comma choices.
- Modules/functions/variables: `snake_case`; classes and exception types: `PascalCase`; constants: `UPPER_SNAKE_CASE`.
- Add useful type annotations to new public interfaces and complex data flows; don't retrofit the entire repository just for typing.
- Keep functions focused; pass dependencies and paths explicitly where that improves testing. Avoid generic `except Exception` that hides important errors; distinguish validation, IO, conflict, and dependency failures.
- Use `pathlib.Path` at module boundaries, but honor existing `safe_io` wrappers for guarded filesystem operations. Never introduce unsafe direct writes.
- Use docstrings on non-obvious public APIs, invariants, and security-sensitive helpers. Avoid redundant docstrings on trivial local functions.
- Tests should describe observable behavior rather than internal implementation, and prefer pytest fixtures and temporary directories.

### 6.2 JavaScript, HTML and CSS

- Stay with the existing **vanilla JavaScript / HTML / CSS** architecture; no new frontend framework or build pipeline without approval.
- Match the file's established indentation and syntax. In existing `reader_static/*.js`, use **2-space indentation**, `const` by default, `let` only for reassignment, semicolons, and the surrounding quote convention (commonly double quotes).
- Functions/variables: `camelCase`; constants: `UPPER_SNAKE_CASE` for true cross-module constants, preserving established local conventions; DOM/CSS identifiers: `ml-` prefix where applicable. Do not rename existing public identifiers for style alone.
- Avoid implicit globals, deep nested callbacks, and duplicate event handlers. Guard event callbacks by the current document/note/session state.
- Preserve the existing note-editing pipeline, undo behavior, conflict handling, and IME composition logic. Asynchronous results must never apply to a different active note.
- Treat any dynamically generated HTML as security-sensitive. Prefer `textContent`, `replaceChildren`, and explicit DOM creation for untrusted strings. Do not add unsafe `innerHTML` paths or HTML execution; preserve the existing vetted Markdown renderer boundary.
- No external image/network requests, CDN runtime assets, executable SVG, or user-supplied URL loading unless explicitly within the approved and secured feature.
- Use existing bilingual UI helpers and patterns. **Where Chinese appears in UI/docs/messages, include nearby English**, as required by `CLAUDE.md`.
- Preserve accessibility and keyboard use (focus, shortcuts, error feedback), and ensure errors and pending states are visible.
- There is currently no repository-wide JS formatter/linter equivalent to Ruff; do not introduce or run broad Prettier/ESLint auto-fixes without separate approval. Validate with applicable browser tests and focused review.

### 6.3 Markdown, configuration, and tests

- Docs: concise bilingual Chinese/English wherever the project requires it. Do not silently change old roadmap IDs or statuses. Record observed behavior, not assumed success.
- Configuration/lockfiles: change only when dependencies or behavior genuinely require it; keep versions pinned/checksummed where existing policy requires.
- Source files: preserve established line endings and formatting; do not normalize notes or fixtures with meaningful bytes. `.gitattributes` explicitly requires CRLF for `*.cmd` and treats PDFs as binary.
- Prefer small, narrowly scoped fixtures. Tests must not need a real personal library or network when testing an offline feature.
- If you introduce a new coding convention, explain the need; do not silently force it on unaffected code.

## 7. Definition of done: tests and evidence

### 7.1 During implementation

- Add/update tests for each behavioral change and for every plausible data-loss/security failure mode.
- Run targeted tests while developing. Do not repeatedly run the full suite without a reason.
- Favor deterministic concurrency tests (barriers/held responses/controlled ordering) over arbitrary sleeps.
- Re-run impacted tests after fixes; before calling the milestone locally verified, run the required full suites on the **final tested code**.
- Record actual commands, pass/skip/fail counts, environment, and output evidence. A remembered result or empty JUnit report is not proof.
- Tests that are skipped or not run must be clearly reported; a mock does not prove a real OCR engine works.

### 7.2 Standard checks

For relevant code changes:

```powershell
uv run pytest -q -rs
uv run ruff check .
uv run ruff format --check .
git diff --check
```

For browser-related features, also verify both Edge shards and the notes-closed set using the actual commands/partition configuration in `.github/workflows/tests.yml` and `tests/browser/shards.py`. Do not assume plain `pytest` includes browser tests. Preserve logs and failure traces in ignored `test-results/` or temporary locations.

For OCR: require a **real local offline inference smoke test**, separate from mocked integration tests, with named inputs, observed outputs, and disclosed limitations. For optional packages, test the unavailable-dependency path. For packaged builds, distinguish ordinary Python tests from independent, clean-package/manual acceptance.

For a job described as complete, separate these statuses:

- **Implemented:** code present, not necessarily verified.
- **Locally verified:** required local tests passed on the reported worktree state.
- **Committed:** owner-approved local commit exists.
- **Pushed:** specified commit is on remote.
- **CI-verified:** all required jobs passed for that exact SHA.
- **Manually accepted:** owner confirms required hands-on behavior; CI alone is not manual acceptance.

Never claim one status based only on another.

### 7.3 Reviewer evidence policy

The Reviewer ordinarily reads the base-to-HEAD diff (plus uncommitted diff), touched code, call paths, targeted tests, and test summaries first. Inspect broader modules only where a concrete risk calls for it. A small targeted verification is appropriate when evidence is missing; a complete duplicate full-suite run is **not** the default.

Review by risk: data loss/corruption, security, race conditions, backward compatibility, broken UI workflow, missing tests, then maintainability. Do not invent findings; cite exact file and function/line area, reproduction condition, impact, and practical fix.

Reviewer verdict must be one of:

1. **Ready for owner commit decision** — no known blocking defect; evidence adequate.
2. **Fix required** — list blocking findings and minimum reproductions.
3. **Verification incomplete** — specify exact missing proof, not a broad vague request.

Severity: `Critical` (security/data loss), `High` (core correctness/race), `Medium` (important reliability/test gap), `Low` (non-blocking polish). Style preferences alone do not block a safe, consistent implementation.

## 8. Developer → reviewer → developer handoff

A handoff is a **report, not permission to change code**. Include:

1. Milestone ID, exact scope, owner approval, and current role.
2. Baseline commit SHA, current HEAD, branch, remote state, and `git status --short`.
3. Exact modified/untracked paths and whether any pre-existing work was present.
4. Architecture/API/storage decisions and invariants that must remain true.
5. Implemented items vs. incomplete items, mapped to acceptance requirements.
6. Test commands and actual results; CI run links only if a push was authorized and occurred.
7. Real-world/manual checks (e.g., actual OCR) distinguished from mocked tests.
8. Security/data-integrity risks, open issues, and any uncertain claims.
9. Next safe action and explicit forbidden actions (usually no commit/push).

For usage exhaustion or switching tools, leave a compact `SESSION_HANDOFF.md` **only if explicitly requested or already approved**; otherwise deliver the structured report in the conversation. Never persist private notes, tokens, machine paths, or user data in repository documentation. Do not create an unapproved docs-only commit.

At handoff, the current writer must stop modifying files before a second writer takes over. The second agent first checks that the tree matches the handoff; if it differs, stop and reconcile, not overwrite.

## 9. Git, review and CI discipline

- Never use `git add .` or `git add -A`. Stage precisely named, reviewed paths after commit authorization.
- Inspect staged diff, `git diff --check`, and data/privacy-sensitive files before committing.
- Prefer one logical commit per approved milestone/fix, unless the owner authorizes a split. Do not amend/rebase an existing approved commit without explicit permission.
- Use a concise English imperative commit subject that describes the change; do not invent a SHA or claim a push occurred.
- Verify the remote SHA immediately before an approved push; require a normal fast-forward. Never force-push unless the owner gives a separate explicit instruction after reviewing the risks.
- After push, check the **exact commit SHA**, GitHub Actions run ID, overall conclusion, Python job, both browser shards, and notes-closed job. Check partition coverage when applicable.
- A failing job means **not CI-verified**. Collect failure evidence and stop; no automatic rerun, fixes, or extra commits without approval.
- Do not mix unrelated issue fixes, roadmap renumbering, formatting sweeps, personal data, dependency upgrades, or release packaging into a feature commit.
- When CI changes documentation status after the code commit, avoid an extra docs-only commit unless approved; record the verified run in the next authorized code/doc change.

## 10. Stop-and-escalate conditions

Stop implementation and ask the owner for direction **before proceeding** if:

- A change would touch the real library or frozen showcase/test library.
- A destructive operation, migration, public exposure of private content, or license incompatibility is possible.
- A required fix demands a framework swap, major API redesign, new recurring cost, substantial package redesign, or unexpected external service.
- The active tree/branch differs from the handoff in an unexplained way, or another agent is still writing.
- Core acceptance cannot be tested, significant data-integrity risks remain, or the selected OCR solution cannot legally/technically run as required.
- A planned action would exceed the owner's explicit authorization.

When blocked, leave existing changes intact and report evidence, options, and a minimally disruptive next step. Never replace uncertainty with a success claim.

## 11. Task response templates

### Implementer completion report

```text
Role: Implementer | Milestone: <ID> | Git: <branch, base SHA, HEAD, clean/dirty>
Implemented: <user-observable behavior and touched files>
Not implemented / deferred: <explicit list>
Safety and compatibility: <data, paths, conflicts, backup, offline>
Tests: <exact commands + counts + supporting logs/artifacts>
Manual / real-engine verification: <done / not done, evidence>
Known issues: <IDs, severity, constraints>
Request: <review only / permission for local commit only>
Actions not taken: no commit, no push, no new milestone
```

### Reviewer report

```text
Role: Independent Reviewer | Baseline: <SHA> | Tree inspected: <state>
Findings:
- [Critical/High/Medium/Low] <file/function> — <repro, impact, suggested fix>
Verification gaps: <specific missing evidence>
Existing tests reviewed/run: <commands and actual results>
Verdict: Ready for owner commit decision / Fix required / Verification incomplete
Working tree changes made by reviewer: none
```

### Usage-limit / agent-switch checkpoint

```text
Role handing off: <agent>
Owner-approved milestone: <ID>
Base and HEAD SHA: <...>
Dirty/untracked files: <exact paths>
Completed: <...>
Unfinished: <...>
Verified vs. claimed tests: <...>
Running background processes: <...>
Known risks and next safe command: <...>
No commit/push unless already expressly authorized
```

## 12. Adoption and maintenance

- Add this standard and its two entry points as a **separate, owner-approved documentation change** at a safe checkpoint; never weave it into an unfinished milestone's implementation or use adoption to tidy unrelated files.
- Keep a short repository-root `AGENTS.md` for Codex to find this document, and add a short introduction to the existing `CLAUDE.md` for Claude Code. Both agents must read both the shared standard and existing myLibrary architecture. Preserve all original `CLAUDE.md` content.
- Keep this document focused on stable cross-agent rules; do **not** insert live usage balances, active dirty-file counts, temporary model test results, or milestones' changing CI statuses here. Those belong in handoff reports and `ROADMAP.md`.
- Amend this document only for a genuinely reusable workflow/style rule, not an exception found in a single bug. All rule changes require owner review and are subject to the same commit/push gates.
- The optional `.editorconfig` is for editor consistency only. An EditorConfig-aware editor applies it to **any file it saves, existing files included**, so it sets no charset and no line endings (except CRLF for `.cmd`), sets nothing for Markdown, CSV, JSON or text, and unsets everything under `library/` and `test_library/`. Do not add rules that would normalize existing files. Ruff and the existing test suite remain the executable checks.

**Core rule: one writer, one independent reviewer, owner-controlled Git, preserved data, reproducible tests, and one coherent code style.**
