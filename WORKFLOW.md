```yaml
version: v0.1
project: techne
updated: 2026-06-09
```

# Workflow

How a skill goes from idea to deployed-and-tuned. The unit of work is one skill
(or agent); this is the process that produces it.

> <sub>一个 skill 从想法到上岗、再到调优的流程。Claude Code 探讨设计,codex 执行,你做终判;
> 每个产出环节都有一个「非作者」的对手把关。本文档以英文为正文(便于两个模型精确执行 + 公开分发),
> 关键术语附中文。要中文为主随时说。</sub>

## Principle — every output faces a non-author adversary

No one signs off on their own work. (没有谁能给自己的产出盖章。) This is the
backbone; the two gates below exist to enforce it.

## Roles

| Role | Owns | Its adversary |
|---|---|---|
| **Claude** | design · validation (skills only run inside Claude) · PR review | codex red-teams the spec |
| **codex** | spec red-team · execution (PR) · mechanical self-check | Claude reviews the PR |
| **You** | joint validation · the merge gate | the human over everything |

## Default pipeline

For any new skill/agent, or a change with design content.

0. **Discuss** (Claude Code) — until the consensus is concrete enough to write as a spec.
1. **Issue** — Claude writes it: spec + rejected alternatives + empirical acceptance (template below).
2. **GATE · spec red-team** — codex's job is to *prove the design wrong or find a better one*, **not** to confirm it's feasible. Not converged in two rounds → escalate to you.
3. **Execute** — codex implements, opens a PR, runs a mechanical self-check (builds, lints, format).
4. **Review** — Claude reviews in two hats: *did it faithfully execute the spec*, and *fresh-eyes: is the result actually good*. Claude runs the empirical validation inside a Claude context.
5. **GATE · empirical acceptance** — baseline vs. with-skill, meeting the bar fixed in the issue. Judged jointly by you and me. Finance: historical ground-truth backtest. Else: blind baseline-vs-skill.
6. **Merge** — your call.
7. **Deploy to hosts** — Claude plugin + install matrix skins (one body,
   multiple thin host paths).
8. **Tune** — use surfaces problems; fixes ride the light path.

Two hard gates: a spec that fails red-team is not executed (2); a skill that fails
empirical acceptance is not merged (5). Everything else is just flow.

## Light path

Trivial, reversible changes — a typo, wording, a small tweak to an existing skill.
Change it on a branch → the other agent does one cross-check pass → you merge.
No issue, no red-team. Trigger test: *does this need a spec?* Yes → default
pipeline; pure patching → light. Tuning loops usually ride here.

## The spec (what the issue holds)

- **Goal** — which "move the model has but skips" this installs.
- **Design & rejected alternatives** — ADR-style: what was considered and cut, and why. Stops codex re-litigating settled questions or "fixing" a deliberate choice.
- **Implementation detail.**
- **Empirical acceptance** — baseline, test set, what counts as *improvement*, the pass bar. If you can't write this, it isn't ready for an issue.
- **Scope & deploy target.**

## Authoring — one body, multiple thin host paths

The skill **body** (the forced cognitive move) is the asset, and it stays
tool-neutral. Claude, Codex, Cursor, Gemini, Kimi, or any future host should load
or install that same body through thin manifests, marketplaces, or install
instructions. Keep tool-specific things — trigger mechanism, plugin metadata,
tool names — *out* of the body. One shared body prevents the hosts from drifting
into separate products.

Structural constraint: a Claude skill only runs inside Claude. codex can author
one but can't exercise it — so validation (steps 4–5) always lives on the Claude /
your side, and never closes end-to-end on codex.

## What counts as validation

"Changes the answer" is necessary but not sufficient — **changing ≠ improving**
(改变 ≠ 改善). A skill earns its place only if, on the cases where the model would
otherwise skip the move, forcing it *improves* the outcome. Judge jointly. Finance
has delayed ground truth, so backtest against history; elsewhere, blind
baseline-vs-skill.

## How this doc earns its place

It proves out on the first real skill that clears the empirical gate. If a stage
adds ceremony without catching anything across the first few skills, cut that
stage — the process answers to the same proportionality bar as the skills do.
