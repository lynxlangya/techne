# vet Eval

`vet` is accepted only if it improves code review behavior under pressure. The
mechanical fixtures test `vet_gate.py`; empirical validation tests the skill in a
real Claude review context before the issue is closed.

## Acceptance Status

- 2026-06-12 — Mechanical fixtures A-X, L1/L2, Y, Z, AA-AH, and house fixtures:
  **passed in the implementation PR self-check** against throwaway `/tmp`
  projects (`49/49 passed`).
- 2026-06-12 — Empirical acceptance: **not yet run**. This issue must remain
  open until results are recorded here and in an issue comment for #25.

## Mechanical Fixtures

All fixtures run against throwaway `/tmp` projects. Generated `.techne/` output
must not be committed.

| # | Fixture | Expected |
| --- | --- | --- |
| A | `init` on a repo with `base...head`, including a body-only hunk | `scope.json` written with resolved SHAs, files, hunks, candidates, testsDelta, and body-only unit binding |
| B | `init` outside a git repository | refused loudly, exit nonzero |
| C | `init` with worktree HEAD != resolved `--head`; dirty worktree without `--allow-dirty` | both refused; `--allow-dirty` records `allowDirty: true` |
| D | binary + lockfile changes in the diff | excluded from symbol candidates; classification recorded in `scope.json` |
| E | finding cites a nonexistent file | `check` fails naming the finding id |
| F | finding cites a valid file with out-of-range lines | `check` fails |
| G | citations inside vs outside changed hunks | tags computed `inDiff` / `context` |
| H | `declaredExtra` symbol absent from changed lines/context | `check` fails |
| I | scope candidate with no disposition in `review.json` | `check` fails |
| J | examined ref whose file:line lacks the token | `check` fails |
| K | all found refs examined or excluded with reasons | coverage computed; `approve` admissible |
| L1 | unaccounted refs + >=1 `blocking` finding at R2/R3 | `request-changes` admissible; `blastRadiusComplete: false` |
| L2 | unaccounted refs + `concern`-only findings | `request-changes` refused with `refs_unaccounted` |
| M | exclusion without a reason | `check` fails |
| N | `blocking` finding with zero verified citations | `check` fails |
| O | `blocking` finding with verified citations | R2 computed; `request-changes` admissible |
| P | finding with probe -> existing repro entry, failing, expect-matched, same head | R3 computed |
| Q | probe reference to a missing entry or passing entry | `check` fails |
| R | prod changed, tests unchanged, no `testsAcknowledgment` | `approve` inadmissible with `tests_unacknowledged` |
| S | claim without disposition; `verified` claim without citation | `check` fails |
| T | `close --verdict approve` with open `blocking` finding | refused with `blocking_open` |
| U | `close --verdict request-changes` with zero findings >= `concern` | refused with `no_findings_for_request_changes` |
| V | `close --verdict blocked` without/with `--reason` | without reason refused; with reason exits 0 and marks unfinished |
| W | changed symbol with zero refs outside the diff | trivially accounted; `refsFound: 0` recorded |
| X | symbol with >200 refs | bare exclusion refused; bounded/path-excluded accounting required; cap recorded |
| Y | helper/target mis-header body edit; code hunk `file-level` dodge | `target` binds; `enclosingUnit: helper` fails; code `file-level` refused |
| Z | `run` with >200 raw refs; bounded plan omits live path | omitted raw path refuses approval; full path coverage or reasoned exclusion admits |
| AA | claims choice/id stability | missing claims choice refused; claim ids content-derived; unknown/undispositioned claims fail; changed claims digest on same slug refused |
| AB | stale or tampered repro probe | stale head and edited JSONL line fail check |
| AC | head moves after init | `check` and approve/request-changes close refuse; `status` reports mismatch; blocked close records both SHAs |
| AD | shallow/no local merge base | `init` refuses with `no_merge_base` guidance |
| AE | Python triple string and JS block comment contain fake definitions | fake definitions neither bind nor refuse honest unit |
| AF | nested function body edit | inner and outer units enter floor; accounting inner alone cannot approve |
| AG | commit body/trailer claims | body paragraph and non-allowlisted trailers anchor as claims; identity trailers exempt |
| AH | brace stack same-indent and Allman wrappers | outer and inner enter floor; accounting inner alone cannot approve |

House fixtures:

- unknown subcommand/flag -> argparse exit 2.
- `.techne/` appended to `.gitignore` once, idempotently.
- two review slugs in one project are independent.
- `check` is idempotent and re-runnable after `review.json` edits.
- re-`init` with same SHAs is idempotent; different SHAs are refused.

## Empirical Acceptance

Validation runs in a Claude context per `WORKFLOW.md`.

Test set:

- Three seeded PRs across three ecosystems: one Python, one JS/TS, one Rust or
  Swift; at least one in a workspace/monorepo package.
- Each seeded PR reverts a real historical bugfix commit and bundles 2-4 benign
  changes, with a plausible PR description that claims the benign improvements
  and is silent about the defect.
- One clean PR as a signal-to-noise control.
- The same seeded repositories may serve the outstanding `repro` empirical gate.

Protocol:

- Six fresh-session legs: baseline review vs. with-`vet` review for each seeded
  PR.

Metrics per leg:

- seeded defect found and severity.
- false positives on benign changes.
- refs outside the diff actually opened vs. claimed in `review.json`.
- claim dispositions vs. ground truth.
- verdict correctness.
- friction: turns, wall time, and any admissibility friction.

Controls:

- C1 negative trigger: one non-review coding task with `vet` installed. Fails
  iff `vet_gate.py` runs or `.techne/review/*` is created.
- C2 clean PR: reaches `approve` with zero `blocking` and at most one
  `concern`/`nit`.
- C3 probe composition: at least one `vet` leg reaches R3 through a real
  `repro` ledger probe.

Pass bar:

- 0/3 `approve` on seeded-defect PRs.
- Seeded defect found with `request-changes` in >=2/3, with 3/3 as target.
- Severity is never softer than baseline.
- Vet detects defects at least as often as baseline overall and better in at
  least one leg.
- False positives are not worse than baseline.
- C1-C3 all pass.
- No leg where admissibility rules force a dishonest verdict.

A missed leg is recorded as a failed leg and root-caused. It is excusable only
when the seed was not surfaceable by construction; then the seed is fixed and
rerun.

## Goodhart Watch

Record these in the empirical write-up:

- examined-ref padding.
- live code excluded as generated/vendor/too common.
- bounded-plan patterns crafted to miss live call sites.
- severity deflation.
- claim dodging or false `--no-claims` on PR reviews.
- early-stop and `blocked` overuse.

## Coverage Gaps

- semantic xref through AST/LSP.
- dynamic dispatch, reflection, macro expansion, and string-built names.
- Windows support.
- generated report viewer.
