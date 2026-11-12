# myLibrary — Shared AI Instructions (Codex / Claude Code)

This file is a **tool-compatible entry point**, not a separate source of rules.
The same rules apply to both Claude Code and Codex.

**Before implementing or reviewing, read:**

1. `docs/AI_DEVELOPMENT.md` — canonical shared roles, approval gates, code style, testing, handoff and safety.
2. `CLAUDE.md` — existing myLibrary architecture, document identity, data and packaging constraints. **It applies to Codex too.**
3. `ROADMAP.md` — owner-approved milestone, scope, acceptance and unresolved issues.
4. Relevant `DEVELOPMENT_SPEC.md` sections and touched source/tests.

**Default role: read-only / no changes until assigned.** The owner's explicit task names the Implementer or Independent Reviewer. Only one agent may modify a shared checkout. The Reviewer does not edit tracked files or change tool/model installations. Never commit, push, force-push, reset, clean, migrate, or touch personal/frozen showcase data without the exact required owner approval.

Preserve all pre-existing uncommitted and untracked work, regardless of milestone, session, or agent; inspect it before making changes. Do not use broad staging (`git add .` / `git add -A`). Follow the network and cost policy in `docs/AI_DEVELOPMENT.md` §5 and each milestone's own limits in `ROADMAP.md` (for example, OCR that must stay free and local). Follow existing Python Ruff configuration and module-local JS style; never reformat the whole repository.

If instructions conflict, preserve the stricter data safety rule and tell the owner before taking a risky action.
