# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status: early skill library

`techne` (τέχνη — Greek for *craft · skill · art*) is a fresh start from the
old `atools-js` utility library, but it is no longer docs-only. Current `main`
contains:

- `skills/` as the source of truth for tool-neutral skill bodies.
- `.claude-plugin/` as the Claude Code plugin skin and development marketplace.
- `.cursor-plugin/plugin.json` and `gemini-extension.json` as thin host skins.
- `INSTALL.md` as the install matrix for Claude, Codex, Cursor, Gemini, Kimi,
  and the universal Agent Skills fallback.
- `skills/viz/`, the first real skill: a typed diagram router for codebase
  architecture, request interactions, data models, state models, and type
  structures, with a mechanical provenance gate.
- `skills/repro/`, the second real skill: a repro-first bugfix gate that forces
  fail → fix → same-probe verification through a run ledger.

There is still **no root app, no root package manager, no CI, and no repo-wide
test runner**. `skills/viz/scripts/package.json` only pins helper dependencies
for that skill's Mermaid validator; `skills/repro/scripts/repro_ledger.py` is
dependency-free Python 3 stdlib (POSIX-only). Do not infer commands, dependencies, or
architecture from the legacy library; that direction was abandoned.

## Project intent

Per the README, techne is a home for **"Skills and agents for the AI era."**
Absent other direction from the user, treat new work as improving shared
skill/agent bodies and their thin distribution skins, not as rebuilding a
published utility package.

The current product rule is **one body, multiple skins**: keep the real skill
content in `skills/`; host-specific files should be manifests, marketplaces, or
install instructions that point back to that shared body.

## Current skill surface

Two skills are seeded: `skills/viz` and `skills/repro`.

`skills/viz` (coding/investigate):

- `SKILL.md` forces the cognitive procedure: route the diagram kind, read real
  evidence, draw only evidenced relationships, enforce complexity gates, mark
  provenance, then validate/store/build the viewer.
- Supported `diagramKind` values are `architecture`, `interaction`,
  `data-model`, `state-model`, and `type-structure`.
- Supported Mermaid types are `flowchart` / `graph`, `sequenceDiagram`,
  `erDiagram`, `stateDiagram-v2` / `stateDiagram`, and `classDiagram`.
- `scripts/validate-mermaid.mjs` parses and counts, and — with
  `--project <root>` — mechanically verifies `%% techne:source` /
  `%% techne:inferred` provenance annotations against the target project
  (paths, symbols, citation strength) and computes coverage; without
  `--project` it syntax-checks annotations only. It intentionally does **not**
  call `mermaid.render()` under Node/jsdom; browser rendering is checked
  through the self-contained file viewer.
- `scripts/store_viz.py` runs the validator itself (provenance enforced, no
  bypass flags) and derives `diagramKind`, `type`, `sourceFiles`, `coverage`,
  and `nodeCount` from validator output — there are no self-reported metadata
  flags. It writes diagrams to a target project's `.techne/viz/*.md` and
  `.index.json`, and idempotently adds `.techne/` to that target project's
  `.gitignore`.
- `scripts/build_viewer.py` builds a self-contained `.techne/viz/index.html`.
  It does not start a server.

`skills/repro` (coding/debug):

- `SKILL.md` forces the cognitive procedure: trigger-check the task as a
  behavioral bug, capture a stable `--expect` anchor, demonstrate the failure
  through the ledger before editing, fix, verify with the byte-identical probe
  identity, then report citing the `close` JSON and strength rung.
- `scripts/repro_ledger.py` (Python 3 stdlib, POSIX/macOS/Linux only) executes
  and records probes in a target project's `.techne/repro/<bug>.jsonl`.
  Classification is computed, never declared: probe identity is
  `{mode, argv | shellCommand, cwd, timeoutSec}`, and `close` exits 0 only on a
  fail → later same-identity pass, or on a loud `mark-unreproduced`
  speculative path.

Generated `.techne/` output (viz and repro alike) belongs in target projects
and must not be committed to this repository.

## Development workflow

All non-trivial work follows [`WORKFLOW.md`](WORKFLOW.md) — read it before starting any skill/agent task. In short: design and pressure-test the skill here in Claude Code → write it up as a GitHub issue (spec + rejected alternatives + an empirical accept test) → codex red-teams the spec, then executes it in a PR → Claude reviews the PR and runs the validation → the user merges. Spine: **every output faces a non-author adversary** (Claude designs / codex red-teams; codex executes / Claude reviews). Two hard gates — a spec that fails red-team isn't executed; a skill that fails empirical acceptance isn't merged (validation = *improve*, not merely *change*). Trivial, reversible changes take the light path: direct change, one cross-check, no issue.

## Commands

Use these commands as the current mechanical baseline:

```bash
claude plugin validate . --strict
claude --bare --plugin-dir . plugin details techne
```

For `viz` script changes, create temp fixtures and temp target projects. The
validator needs `mermaid@11.15.0` and `jsdom` in `TECHNE_VIZ_NODE_MODULES`,
`skills/viz/scripts/node_modules`, the current directory, or an ancestor:

```bash
node skills/viz/scripts/validate-mermaid.mjs diagram.md --project /tmp/project --max-nodes 15
python3 skills/viz/scripts/store_viz.py --project /tmp/project --name diagram --title "Diagram" --diagram diagram.md --shape monorepo
python3 skills/viz/scripts/build_viewer.py --project /tmp/project
git diff --check
```

For viewer work, also open the generated `file://.../.techne/viz/index.html`
and verify the relevant diagrams render without console errors or external
network loads.

For `repro` script changes, exercise the ledger against throwaway `/tmp`
projects — `skills/repro/eval.md` fixtures A–X are the reference suite:

```bash
python3 -m py_compile skills/repro/scripts/repro_ledger.py
python3 skills/repro/scripts/repro_ledger.py run --project /tmp/project --bug demo --expect "boom" -- python3 -c 'print("boom"); raise SystemExit(1)'
python3 skills/repro/scripts/repro_ledger.py status --project /tmp/project --bug demo
```

## Legacy code

The old `atools-js` codebase is preserved on the **`legacy`** branch (`origin/legacy`): a browser/Node TS utility library (clipboard, cookie, regex validator, calc/time helpers) built with Rollup, tested with Jest, published to npm. Reach for it only if the user explicitly wants to reference or restore prior work — it is not the current direction.

## Conventions

- **Bilingual docs** — public-facing docs are split by language: `README.md` is the default English document, and `README-CN.md` is the Chinese companion. Use the same pattern for skill usage guides when Chinese docs are needed.
- **Skill docs split** — `SKILL.md` is the executable skill body; a real skill's human-facing usage guides should live in nearby `README.md` / `README-CN.md` files.
- **`main` is the working branch**; `legacy` exists solely to archive the pre-reset code. Keep it untouched.
- **Minimal, content-first changes** — avoid adding root scaffolding, package managers, CI, or new host skins unless the issue explicitly requires them.
- **Review handoff** — Codex-authored PRs normally stop at Claude/maintainer review unless the user explicitly asks to merge.
