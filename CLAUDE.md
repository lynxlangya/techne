# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status: greenfield

`techne` (τέχνη — Greek for *craft · skill · art*) is a **fresh start**. The repo currently holds only documentation — `README.md` plus the `AGENTS.md` / `CLAUDE.md` / `WORKFLOW.md` governance files; no source code yet. The previous `atools-js` TypeScript utility library was intentionally removed in `5fbb02a` (`chore(main)!: clear legacy atools-js codebase`).

There is currently **no build system, no test runner, no linter, and no source code**. Do not infer commands, dependencies, or architecture from the legacy library — that direction was abandoned. As real tooling lands, fill in the Commands and Architecture sections below; until then there is nothing to build or test.

## Project intent

Per the README, techne is a home for **"Skills and agents for the AI era."** Absent other direction from the user, treat new work as building toward that goal — expect skill/agent definitions rather than a published utility package.

## Development workflow

All non-trivial work follows [`WORKFLOW.md`](WORKFLOW.md) — read it before starting any skill/agent task. In short: design and pressure-test the skill here in Claude Code → write it up as a GitHub issue (spec + rejected alternatives + an empirical accept test) → codex red-teams the spec, then executes it in a PR → Claude reviews the PR and runs the validation → the user merges. Spine: **every output faces a non-author adversary** (Claude designs / codex red-teams; codex executes / Claude reviews). Two hard gates — a spec that fails red-team isn't executed; a skill that fails empirical acceptance isn't merged (validation = *improve*, not merely *change*). Trivial, reversible changes take the light path: direct change, one cross-check, no issue.

## Legacy code

The old `atools-js` codebase is preserved on the **`legacy`** branch (`origin/legacy`): a browser/Node TS utility library (clipboard, cookie, regex validator, calc/time helpers) built with Rollup, tested with Jest, published to npm. Reach for it only if the user explicitly wants to reference or restore prior work — it is not the current direction.

## Conventions

- **Bilingual docs** — the README leads in English with a Chinese (中文) `<sub>` gloss. Preserve this dual-language framing for user-facing documentation.
- **`main` is the working branch**; `legacy` exists solely to archive the pre-reset code. Keep it untouched.
