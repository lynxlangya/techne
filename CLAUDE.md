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
  structures.

There is still **no root app, no root package manager, no CI, and no repo-wide
test runner**. `skills/viz/scripts/package.json` only pins helper dependencies
for that skill's Mermaid validator. Do not infer commands, dependencies, or
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

`skills/viz` is the active seeded skill.

- `SKILL.md` forces the cognitive procedure: route the diagram kind, read real
  evidence, draw only evidenced relationships, enforce complexity gates, mark
  provenance, then validate/store/build the viewer.
- Supported `diagramKind` values are `architecture`, `interaction`,
  `data-model`, `state-model`, and `type-structure`.
- Supported Mermaid types are `flowchart` / `graph`, `sequenceDiagram`,
  `erDiagram`, `stateDiagram-v2` / `stateDiagram`, and `classDiagram`.
- `scripts/validate-mermaid.mjs` is parse-only plus counters. It intentionally
  does **not** call `mermaid.render()` under Node/jsdom; browser rendering is
  checked through the self-contained file viewer.
- `scripts/store_viz.py` writes diagrams to a target project's
  `.techne/viz/*.md` and `.index.json`, and idempotently adds `.techne/` to that
  target project's `.gitignore`.
- `scripts/build_viewer.py` builds a self-contained `.techne/viz/index.html`.
  It does not start a server.
- Generated `.techne/` output belongs in target projects and must not be
  committed to this repository.

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
node skills/viz/scripts/validate-mermaid.mjs diagram.md --max-nodes 15
python3 skills/viz/scripts/store_viz.py --project /tmp/project --name diagram --title "Diagram" --diagram diagram.md --shape monorepo --diagram-kind architecture --type flowchart
python3 skills/viz/scripts/build_viewer.py --project /tmp/project
git diff --check
```

For viewer work, also open the generated `file://.../.techne/viz/index.html`
and verify the relevant diagrams render without console errors or external
network loads.

## Legacy code

The old `atools-js` codebase is preserved on the **`legacy`** branch (`origin/legacy`): a browser/Node TS utility library (clipboard, cookie, regex validator, calc/time helpers) built with Rollup, tested with Jest, published to npm. Reach for it only if the user explicitly wants to reference or restore prior work — it is not the current direction.

## Conventions

- **Bilingual docs** — public-facing docs are English-first with a Chinese companion section for the same user-facing content. Keep English as the default execution/reference language, then add Chinese so the maintainer and Chinese users can read the same intent.
- **Skill docs split** — `SKILL.md` is the executable skill body; a real skill's human-facing usage guide should live in a nearby `README.md`.
- **`main` is the working branch**; `legacy` exists solely to archive the pre-reset code. Keep it untouched.
- **Minimal, content-first changes** — avoid adding root scaffolding, package managers, CI, or new host skins unless the issue explicitly requires them.
- **Review handoff** — Codex-authored PRs normally stop at Claude/maintainer review unless the user explicitly asks to merge.
