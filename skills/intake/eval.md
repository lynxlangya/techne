# intake Eval

`intake` is accepted only if it improves pre-work brief interrogation under
pressure. The mechanical fixtures test `intake_gate.py`; empirical validation
tests the skill in a real Claude context before issue #28 is closed.

## Acceptance Status

- 2026-06-13 — Mechanical fixtures A-L, floor fixtures, and house fixtures:
  **passed in the implementation PR self-check** against throwaway `/tmp`
  projects (`21/21 passed`).
- 2026-06-13 — Empirical acceptance: **not yet run**. This issue must remain
  open until results are recorded here and in an issue comment for #28.

## Mechanical Fixtures

All fixtures run against throwaway `/tmp` projects. Generated `.techne/` output
must not be committed.

| # | Fixture | Expected |
| --- | --- | --- |
| A | rubric element omitted from `intake.json` | `check` fails with `rubric_element_unaccounted` |
| B | `present` citation has wrong offset or non-matching quote | `check` fails with `citation_unverified` |
| C | `present` has no `valueItems` | `check` fails with `present_without_value` |
| D | `present-weak` has no dependent question | `check` fails with `weak_or_gap_without_question` |
| E | `gap` has no question and no visible `modelDefault` | `check` fails with `weak_or_gap_without_question` |
| F | `solution-as-goal` lacks a verifying brief citation | `check` fails with `citation_unverified` |
| G | `contradiction` has fewer than two verifying spans or one bad span | `check` fails with `citation_unverified` |
| H | question lacks `resolves` or `planDelta` | `check` fails with `question_without_resolution` |
| I | step references an unknown step or assumption | `check` fails with `step_dangling_ref` |
| J | `finalize` before all rubric elements account and citations verify | refused with the underlying check failures |
| K | `finalize --unscopable` without/with `--reason` | without reason refused; with reason emits loud unfinished `plan.json` and `intakeReport.json` |
| L | self-eject/idempotence surfaces | no `.techne/plan/<slug>` for self-eject; re-`check` is idempotent; two slugs are independent; re-`init` with same brief hash is idempotent and different hash is refused |

Floor fixtures from the amendments:

| Fixture | Expected |
| --- | --- |
| `value_not_in_spans` | invented `Jira sprint API` grounded only in `billing warehouse invoices table` fails with `value_not_grounded_in_spans` |
| `rubric-label-only value` | value text such as `data source` has no content tokens after STOPLIST/RUBRIC-LABEL removal and fails |
| `atomic partial-present` | a value item whose span omits a content token fails with `value_not_grounded_in_spans` |
| `present_value_fails_shape` | `P0 load fast` as `measurable-success-threshold` produces `present_value_fails_shape`, effective `present-weak`, and still finalizes only when a dependent question exists |
| `question_not_bound_to_element` | weak/gap question that does not reference the weak span/value or missing element label fails |
| `value_item word-salad` | `API source metrics` stitched from `API review`, `source code`, and `Metrics naming` fails because no single item span grounds all content tokens |

House fixtures:

- false-`gap` with indicator terms in the brief emits non-blocking
  `gap_with_indicator_terms_present`.
- at least one reachable terminal step is required.
- a verified `solution-as-goal` finding with a dependent question checks cleanly.

## Empirical Acceptance

Validation runs in a Claude context per `WORKFLOW.md`.

Test set:

- Seeded substantial engineering implementation briefs, each with a maintainer
  answer key authored before any leg.
- At least one ticket-like brief.
- At least one PRD/design-note-like brief.
- At least one solution-as-goal trap.
- At least one planted contradiction.
- At least one seeded missing load-bearing element such as data source or
  external dependency.
- At least one brief with cosmetic adjacent terms that should not satisfy an
  atomic element.

Each answer key is RUBRIC-GRADE:

- every atomic element is tagged `present | present-weak | gap`;
- `present` carries acceptable normalized value(s), not just prose notes;
- `present-weak` states why the value is weak and the required question;
- `gap` states why adjacent brief terms do not satisfy the element;
- solution-as-goal and contradiction traps identify the required source spans.

Protocol:

- Fresh-session baseline legs use plain plan mode over the same brief.
- Fresh-session skill legs use `intake` and the same brief.
- Judges compare baseline vs. skill blind to condition where feasible.

Metrics per leg:

- whether seeded load-bearing gaps are surfaced;
- whether solution-as-goal and contradiction traps are surfaced with verified
  spans;
- per-element disposition vs. answer key;
- normalized extracted values vs. acceptable values;
- false-`gap` on present elements;
- cosmetic-`present` on seeded gaps;
- cosmetic questions not needed by the answer key;
- citation verification and friction.

Controls:

- **C0 positive engagement:** seeded substantial brief must create
  `.techne/plan/<slug>/context.json` and account the full fixed rubric.
- **C1 negative self-eject:** trivial one-liner must eject, write no
  `.techne/plan/<slug>`, and give a one-sentence reason.
- **C2 anti-over-ask:** no false-`gap` on answer-key-present elements and no
  cosmetic questions baseline did not also ask.
- **C3 span-anchored trap:** at least one leg reaches a verified contradiction
  or solution-as-goal finding.

Pass bar:

- Skill legs surface seeded load-bearing gaps and solution-as-goal traps at a
  clear margin over baseline.
- Zero cosmetic questions beyond baseline.
- All skill-leg citations verify mechanically.
- No false-`gap` on an answer-key-present element.
- No cosmetic-`present` on an answer-key-gap element.
- C0-C3 all pass.
- No leg where the gate forces a dishonest frame or blocks an honest intake
  outright.

If baseline already does all of this, the skill has no marginal value and is not
accepted.

## Goodhart Watch

Record these in the empirical write-up:

- cosmetic citations that quote real but irrelevant prose;
- invented values blocked by A9/A10;
- grounded-but-mislabeled values caught by RUBRIC-GRADE value diff;
- false gaps that offload extraction work to the user;
- rubric rubber-stamping where every element is marked `present`;
- questions that are token-bound but substance-wrong;
- overuse of `--unscopable` on substantial engineering briefs;
- attempts to use the engineering rubric on non-engineering artifacts.

## Coverage Gaps

- semantic adequacy of a grounded citation;
- load-bearing requirements outside the v1 engineering rubric;
- non-engineering rubrics for writing, research, operations, or product strategy;
- Windows support;
- generated report viewer.
