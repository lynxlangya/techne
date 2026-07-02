# Roadmap

techne is a curated skill library for practical AI-era craft: moves that improve
how an AI collaborator investigates, judges, writes, codes, and ships.

## Quality Bar

Every skill must be a forcing function for a move the model can make but often
skips. A skill earns its place by improving behavior under pressure, not by
reciting knowledge the model already has.

Prefer skills that:

- Install a concrete check, move, or stop condition.
- Address a repeated failure pattern.
- Have an empirical acceptance test.
- Fill a gap in the platform or do an existing move sharper than superpowers.

Avoid skills that:

- Repackage generic advice.
- Duplicate built-in Claude Code or superpowers behavior without a sharper bar.
- Depend on one private project unless that dependency is isolated as reference
  material.
- Need industry expertise the maintainer cannot judge.

## Audience x Jobs Map

`general`:

- interrogate
- research
- simplify
- explain
- decide

`coding`:

- debug
- trace
- review-diff

`writing`:

- structural-edit
- tighten
- voice-match
- fact-pass

`social`:

- hook
- repurpose
- angle

`finance`:

- global-alpha-style vertical analysis

## Seeding Principle

Seed only audiences where the maintainer can personally judge quality:
`coding`, `writing`, `social`, `finance`, and `general`.

Other industries stay as placeholders until they are judgeable by the maintainer
or contributed by someone who can own the quality bar.

## Current Seed

The current seeded line is the Anchor set: skills whose shared move is anchoring
model work to external evidence that is mechanically checked.

`anchor-viz` is the first real seeded skill. It lives under `skills/anchor-viz/` and forces
codebase investigation through diagramming.

Current `anchor-viz` diagram kinds:

- `architecture`: project/module/service topology via Mermaid `flowchart` /
  `graph`.
- `interaction`: request, command, job, or actor flow via `sequenceDiagram`.
- `data-model`: tables/entities and schema relationships via `erDiagram`.
- `state-model`: status and workflow transitions via `stateDiagram-v2` /
  `stateDiagram`.
- `type-structure`: bounded class/interface/protocol structure via
  `classDiagram`.

The next `anchor-viz` work should improve faithfulness and evaluator coverage before
adding more Mermaid types. Unsupported diagram families stay out until they have
their own evidence contract and mechanical gate.

`anchor-repro` is the second real seeded skill and the first `coding/debug` skill. It
lives under `skills/anchor-repro/` and forces behavioral bug fixes through a mechanical
fail -> fix -> same-probe verification ledger.

`anchor-vet` is the third real seeded skill and the `coding/review-diff` seed. It
lives under `skills/anchor-vet/` and forces diff review through computed scope,
accounted blast radius, verified claims/findings, and admissible verdicts.

`anchor-intake` is the fourth real seeded skill and the `general/interrogate` seed. It
lives under `skills/anchor-intake/` and forces written engineering implementation
briefs through a fixed rubric before work starts, surfacing gaps,
solution-as-goal traps, contradictions, and dependent questions before emitting
an intent-level plan.

`anchor-diligence` is the fifth real seeded skill and the `finance/global-alpha-style
vertical analysis` seed. It lives under `skills/anchor-diligence/` and forces deep
single-company public-equity research through exact identity resolution, dated evidence
snapshots, a fixed finance rubric, citation verification, and a no-verdict report.

## Validation Status

Per [`WORKFLOW.md`](WORKFLOW.md), a skill clears two gates: **step 4** mechanical
review and **step 5** empirical acceptance — baseline vs. with-skill, judged
jointly, on the principle `changing ≠ improving`. All four seeded skills merged
**ahead of step 5**; the empirical proof is **owed** and is run **manually by the
maintainer in real projects**. This table is the durable tracker: issue-based
tracking has eroded — two tracking issues were closed with the debt still
carried — so trust this ledger, not issue state.

| Skill | Step 4 — mechanical | Step 5 — empirical | Tracking issue | Methodology |
| --- | --- | --- | --- | --- |
| `anchor-viz` | passed (merged) | **not recorded — owed** | #11 closed (build PR; no dedicated empirical issue) | [`skills/anchor-viz/eval.md`](skills/anchor-viz/eval.md) |
| `anchor-repro` | passed (24/24 + review probes) | **not run — owed** | #22 closed 2026-06-10 (debt carried) | [`skills/anchor-repro/eval.md`](skills/anchor-repro/eval.md) |
| `anchor-vet` | passed (56/56) | **not run — owed** | #25 closed 2026-06-13 (debt carried) | [`skills/anchor-vet/eval.md`](skills/anchor-vet/eval.md) |
| `anchor-intake` | passed (21/21 + review probes) | **not run — owed** | #28 open | [`skills/anchor-intake/eval.md`](skills/anchor-intake/eval.md) |
| `anchor-diligence` | passed (34 fixtures + PR review + fix-up pass, merged 2026-07-02) | **not run — owed** | #31 open | [`skills/anchor-diligence/eval.md`](skills/anchor-diligence/eval.md) |

Discharging a skill's step-5 debt: run its `eval.md` empirical protocol (baseline
vs. with-skill over seeded real-project material against a maintainer answer key),
record the result in that `eval.md` Acceptance Status, and update the row above.
Closing a tracking issue does **not** discharge the debt; only a recorded result
does.

## Packaging Status

techne now ships one shared `skills/` body through multiple thin paths:

- Claude Code native plugin: `.claude-plugin/`.
- Cursor manifest: `.cursor-plugin/plugin.json`.
- Gemini extension manifest: `gemini-extension.json`.
- Codex, Kimi, and fallback installs: `INSTALL.md` via Agent Skills CLI where
  applicable.

Keep version touchpoints synchronized through `INSTALL.md`. Do not add new
agent skins unless they can point at the same `skills/` body without copying
skill text.

## Profiles, Not Branches

Audiences are bundles and example sets over one flat skill library. They are not
filesystem branches. Keep `skills/<name>/SKILL.md` flat, and track audience,
sequence, and product packaging here.
