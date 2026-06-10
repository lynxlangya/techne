# repro Eval

`repro` is accepted only if it improves debugging behavior under pressure. The
mechanical fixtures test the ledger. The empirical gate tests the skill inside a
real Claude context before merge.

## Acceptance Status

- 2026-06-10 — Mechanical fixtures A–X: **passed**, twice independently — in PR
  #23's self-check and re-verified in the Claude review (24/24, plus fresh-eyes
  probes and a realistic end-to-end fail → fix → verify cycle).
- 2026-06-10 — Empirical acceptance (3 seeded historical bugs, baseline vs
  skill, controls C1–C3): **not yet run**. PR #23 merged ahead of this gate;
  the results are owed and will be recorded here and on issue #22 when the
  protocol runs. Until then, `repro` has not cleared its own empirical bar.

## Mechanical Fixtures

All fixtures must pass in the PR with throwaway projects under `/tmp`.

| # | Fixture | Expected |
| --- | --- | --- |
| A | `run` failing probe | entry recorded, `exit != 0` |
| B | `close` with empty ledger | exit 1, `no_repro` |
| C | `close` with failing entry only | exit 1, `no_verify` |
| D | fail then pass, same identity | `close` exit 0 |
| E | fail `cmd1`, pass `cmd2` | exit 1, `identity_mismatch` |
| F | `--expect` not found in failing output | `expectMatched: false`; `close` exit 1, `expect_not_matched` |
| G | `--expect` matched fail -> same-identity pass | `close` exit 0 |
| H | passing runs only | exit 1, `no_repro` |
| I | `mark-unreproduced`, no attempts, no impossibility flag | refused, exit nonzero |
| J | `mark-unreproduced` after an anchored attempt | `close` exit 0, `speculative: true` |
| K | probe hits `--timeout` | `timedOut: true`; later in-time exit-0 same identity -> `close` exit 0 |
| L | `.gitignore` handling | `.techne/` appended once, idempotent on rerun |
| M | two bug slugs in one project | independent ledgers; reruns append, never overwrite |
| N | unknown subcommand / unknown flag | argparse error, exit 2 |
| O | `--shell` run vs argv run with identical visible text | different identities; pass of one does not verify the other |
| P | `--cwd packages/app` probe | cwd recorded; different cwd -> `identity_mismatch`; same cwd -> close exit 0 |
| Q | `--cwd ../outside`, absolute cwd, or symlink escape | refused |
| R | colorized ANSI output, plain `--expect` | `expectMatched: true` after normalization |
| S | expect match earlier than final tail | `expectMatched: true`; `expectContext` carries the snippet |
| T | timed-out probe that spawned a grandchild | process group killed; grandchild does not outlive the run |
| U | unanchored attempt then `mark-unreproduced` with no flag | refused; with `--no-stable-expect --reason` allowed |
| V | hang repro at timeout T1, pass at timeout T2 | no verify; `identity_mismatch` |
| W | run inside git repo vs non-git directory | git evidence block vs `git: null`; run never blocked |
| X | fail with argv `['a b','c']`, pass with argv `['a','b c']` | distinct identities; `identity_mismatch` |

## Empirical Acceptance

The merge gate is not closed by mechanical fixtures alone. Validation runs in a
Claude context per `WORKFLOW.md`.

Test set:

- Three seeded bugs across three ecosystems.
- One Python.
- One JS/TS.
- One Rust or Swift.
- Each seeded bug is created by reverting a real historical bug-fix commit on a
  real repository.
- At least one bug lives below the repo root in a workspace or monorepo package
  so `--cwd` is exercised on real ground.

Protocol:

- Six fresh-session legs.
- Baseline leg: plain "fix this bug: <symptom>" with no skill.
- Skill leg: identical prompt with `repro` installed.

Metrics per leg:

- Failing probe created and executed before the first production-code edit.
- Fix addresses the historical root cause rather than only patching the symptom.
- Post-fix verification reruns the same probe identity and passes.
- Unrelated-edit count.
- Friction: turns, wall time, and cases where the ledger fought a correct fix.

Controls:

- **C1 negative trigger**: one non-bug task with the skill installed. The control
  fails iff `repro_ledger.py` is executed or `.techne/repro/*` is created;
  merely mentioning that `repro` is out of scope passes.
- **C2 escape hatch**: one genuinely unreproducible case must take
  `mark-unreproduced` with a meaningful reason and final speculative label.
- **C3 package-local**: the monorepo seeded bug must fail with the real symptom
  from its package `--cwd`, not with a root-cwd setup error.

Pass bar:

- Skill legs achieve fail-before-fix and same-probe verification in 3/3.
- Root-cause quality is never worse than baseline and better in at least one leg.
- Unrelated edits are not worse.
- C1-C3 all pass.
- No leg where the gate blocks a correct fix outright.

If baseline already does all of this, the skill has no marginal value and is not
merged.

## Coverage Gaps

Record these as v1 gaps, not as proven surfaces:

- Windows ledger support.
- TTY cursor-control sequences beyond CSI/OSC + CR normalization.
- Frontend visual/browser probes if no acceptance repo exercises them.
- HTTP service probes if no acceptance repo exercises them.
- iOS simulator/signing probes if no acceptance repo exercises them.

## Goodhart Watch

The eval write-up should note:

- Hollow probes that fail for unrelated reasons despite `--expect`.
- `mark-unreproduced` rate and reason quality.
- Probes that appear only after fix attempts, visible through git evidence.
- Degenerate `exit 1`-shaped no-op probes.
- Inherited environment manipulation around a fixed identity.
