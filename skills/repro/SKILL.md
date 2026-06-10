---
name: repro
description: Reproduce a behavioral bug before fixing it, record the failing probe, and verify the fix with the same probe. Use for bug reports, failing tests, crashes, hangs, regressions, wrong output, and observable behavior that should change.
---

# repro

Force the skipped move in debugging: observe the bug before editing, then prove
the fix with the same observation.

## Trigger Check

Use this skill when the task is to correct observable behavior that is currently
wrong: a failing test, error message, stack trace, regression, crash, hang, wrong
return value, wrong render, or "X does Y; it should do Z."

Do not use it for new features, refactors, renames, formatting, docs/copy
changes, dependency bumps without a behavioral symptom, or performance work
without a measurable probe.

Boundary test: can the wrongness be written as "running X currently produces Y;
it should produce Z"? If yes, use this skill and make X the probe seed. If the
statement cannot be formed from current information, ask for or find the missing
observation before editing.

## Forced Procedure

1. **Capture the symptom and stable anchor.** Choose the most stable literal
   substring of the observable symptom for `--expect`. Omit heap addresses,
   PIDs, timestamps, temp paths, and wrapped fragments. Use `--expect` whenever
   the symptom has stable text. If no stable text exists, `--no-stable-expect`
   is the honest fallback, not an unanchored run; do not use it when stable
   textual output exists.
2. **Locate, then probe.** Read enough code to place the behavior. Pick the
   smallest CLI probe that exercises the reported symptom. In workspaces or
   monorepos, run from the package with `--cwd <package-dir>`, not with a
   `cd ... &&` convention. If required environment changes matter, encode them
   inside `--shell` as one quoted command string such as
   `'VAR=... command'`; inherited environment changes are not part of probe
   identity in v1.
3. **Demonstrate.** Run the probe through
   `scripts/repro_ledger.py run --project <root> --bug <slug> ... -- <command>`.
   Read the failing output and confirm it fails for the reported reason:
   mechanically, `expectMatched` should be true when `--expect` was supplied;
   procedurally, inspect the tail/context instead of trusting an exit code.
4. **Diagnose against the probe.** Test hypotheses with discriminating runs
   before stacking edits. If a better probe is needed, the new probe starts a
   new fail -> pass cycle and must be observed failing too.
5. **Fix.**
6. **Verify with the identical probe identity.** Re-run the same execution mode,
   argv vector or shell string, `--cwd`, and `--timeout`. Then run
   `scripts/repro_ledger.py close --project <root> --bug <slug>`.
7. **Promote when possible.** If the target repo has a test suite, promote the
   probe into a committed regression test. This is encouraged, not a gate.
8. **Report.** Cite the `close` JSON, cite the first repro entry's git evidence,
   name the strength rung from `reference.md`, and carry `speculative` when the
   ledger took an unreproduced path.

## Ledger Usage

Run and record a probe:

```bash
python3 skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug login-crash \
  --cwd packages/app \
  --expect "TypeError: cannot read" \
  --timeout 60 \
  -- npm test -- login.test.ts
```

Verify after the fix:

```bash
python3 skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug login-crash \
  --cwd packages/app \
  --expect "TypeError: cannot read" \
  --timeout 60 \
  -- npm test -- login.test.ts

python3 skills/repro/scripts/repro_ledger.py close \
  --project /path/to/project \
  --bug login-crash
```

Mark an honestly speculative fix only when reproduction is impossible:

```bash
python3 skills/repro/scripts/repro_ledger.py mark-unreproduced \
  --project /path/to/project \
  --bug customer-only-crash \
  --no-probe-possible \
  --reason "Requires customer-only data and credentials unavailable in this environment"
```

The ledger writes target-project artifacts under `.techne/repro/` and
idempotently adds `.techne/` to the target project's `.gitignore`. Do not commit
`.techne/` output.

## Stop Conditions

- Stop before editing if you have not run a failing probe or recorded an
  explicit `mark-unreproduced` path.
- Stop if a failing run does not match the reported symptom; a hollow failure is
  not a reproduction.
- Stop if a passing post-fix run uses a different identity; changed probes need
  their own fail -> pass cycle.
- Stop before claiming a non-speculative fix if `close` does not exit 0 with a
  verified same-probe summary.
