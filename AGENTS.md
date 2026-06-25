# AGENTS.md

```yaml
version: v0.1
project: techne
updated: 2026-06-13
```

## Project Facts

- `techne` is an early-stage skills/plugin repository for "Skills and agents for the AI era."
- The current `main` branch contains the Claude plugin skin, install matrix docs, Cursor/Gemini thin skins, and four real skills: `skills/anchor-viz` (typed diagram router with a mechanical provenance gate), `skills/anchor-repro` (repro-first bugfix ledger), `skills/anchor-vet` (evidence-gated diff review), and `skills/anchor-intake` (written-brief interrogation gate).
- There is still no root app, root package manager, CI, or general test runner. `skills/anchor-viz/scripts/package.json` is a local helper manifest for the Mermaid validator, not a repo-wide build system; `skills/anchor-repro/scripts/repro_ledger.py`, `skills/anchor-vet/scripts/vet_gate.py`, and `skills/anchor-intake/scripts/intake_gate.py` are dependency-free Python 3 stdlib (POSIX-only).
- The git history contains a legacy `atools-js` codebase, but new work in this repo should not infer current architecture, tooling, or business rules from that legacy history unless the user explicitly asks for migration or reference work.

## Working Rules

- Start with current files, not assumptions: inspect the present tree before choosing a structure, dependency, or framework.
- Keep early changes content-first and minimal. Do not add scaffolding, package managers, CI, telemetry, network services, or generated boilerplate unless the task requires them.
- When adding skills, agents, docs, or examples, include the intended usage, constraints, and a direct validation path.
- Prefer small, reviewable directory structures over broad future-facing abstractions until the repo has repeated patterns.
- Keep one tool-neutral skill body in `skills/`; host-specific files should stay as thin skins or install instructions that point back to that body.
- Keep public-facing documentation split by language: `README.md` is the default English document, and `README-CN.md` is the Chinese companion. For real skills, keep executable instructions in `SKILL.md` and human usage guidance in nearby `README.md` / `README-CN.md` files.
- Do not commit generated `.techne/` viewer output. `skills/anchor-viz/scripts/build_viewer.py` writes `.techne/viz/index.html` inside target projects only.
- Do not commit secrets, tokens, private config, `.env` contents, or logs that may contain credentials.

## Development workflow

Non-trivial work follows [`WORKFLOW.md`](WORKFLOW.md) — read it before acting on any skill/agent task. For this (codex) side specifically:

- Work arrives as a GitHub issue holding a spec: goal, design + rejected alternatives, implementation detail, an empirical accept test, and scope/deploy target.
- **Red-team the spec first; do not rubber-stamp it.** Your opening move on an issue is to try to prove the design wrong or find a better one — not to confirm it is feasible. Execute only once it survives (two rounds without convergence → escalate to the user).
- Execute in a PR; your self-check is mechanical only (builds, lints, format). Quality judgement and validation are Claude's side — a Claude skill only runs inside Claude, so you can author one but cannot exercise it.
- Keep a skill's body tool-neutral; it deploys through one shared body and multiple thin host paths.
- Every output faces a non-author adversary: Claude designs / you red-team; you execute / Claude reviews. The user holds the merge gate.

## Verification

- For documentation-only changes, run `git diff --check`.
- For plugin packaging changes, run `claude plugin validate . --strict`; use `claude --bare --plugin-dir . plugin details techne` when you need to confirm skill discovery without opening an interactive Claude session.
- For `skills/anchor-viz` script changes, run focused checks for the touched surface: `node skills/anchor-viz/scripts/validate-mermaid.mjs ...`, `python3 skills/anchor-viz/scripts/store_viz.py ...`, and `python3 skills/anchor-viz/scripts/build_viewer.py --project ...`; install or point `TECHNE_VIZ_NODE_MODULES` at `mermaid@11.15.0` + `jsdom` for validator checks.
- For `skills/anchor-repro` script changes, run `python3 -m py_compile skills/anchor-repro/scripts/repro_ledger.py` and exercise the touched behavior against throwaway `/tmp` projects; the fixture table A–X in `skills/anchor-repro/eval.md` is the reference suite. The ledger must stay Python 3 stdlib and POSIX-only (macOS/Linux).
- For `skills/anchor-vet` script changes, run `python3 -m py_compile skills/anchor-vet/scripts/vet_gate.py` and exercise the touched behavior against throwaway `/tmp` projects; the fixture table in `skills/anchor-vet/eval.md` is the reference suite. The gate must stay Python 3 stdlib and POSIX-only (macOS/Linux).
- For `skills/anchor-intake` script changes, run `python3 -m py_compile skills/anchor-intake/scripts/intake_gate.py` and exercise the touched behavior against throwaway `/tmp` briefs; the fixture table in `skills/anchor-intake/eval.md` is the reference suite. The gate must stay Python 3 stdlib and POSIX-only (macOS/Linux).
- For code or executable assets, use the closest direct validation and state any empirical gap. Codex can mechanically validate scripts and packaging, but Claude/maintainer review judges skill faithfulness on real projects.
