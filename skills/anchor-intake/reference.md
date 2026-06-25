# anchor-intake Reference

Load this file when writing `intake.json`, interpreting `report.json`, or
deciding whether an intake disposition, finding, question, or finalized
`plan.json` is honest.

## JSON Contract

`intake_gate.py` writes target-project artifacts under `.techne/plan/<slug>/`.

`context.json` is computed by `init` and contains:

- `briefSha256`, `briefBytes`, and `briefSource`.
- `rubricId: engineering-implementation-brief-v1`.
- the skill-fixed ten-element rubric manifest.

`intake.json` is authored by the reviewer/planner:

- `elements`: dispositions for every fixed rubric element.
- `findings`: span-anchored `solution-as-goal` and `contradiction` findings.
- `questions`: dependent questions with `resolves` and `planDelta`.
- `steps`: intent-level plan steps with dependencies and terminal outcome.

`report.json` is computed by `check`:

- offset + quote citation verification against `brief.txt`.
- value grounding checks for `present` elements.
- shape-status warnings for status-gated present values.
- weak/gap question checks, question resolution checks, and step DAG checks.
- blocking `failures` and non-blocking `warnings`.

`plan.json` and `intakeReport.json` are computed by `finalize`:

- `plan.json` has `schema: techne.intake.plan/1` and carries the intent-level
  steps plus questions.
- `intakeReport.json` surfaces every gap, weak element, solution-as-goal
  finding, contradiction, question, and warning.
- `--unscopable --reason` emits loud unfinished artifacts for unsupported or
  non-engineering briefs.

## Fixed Rubric

Rubric id: `engineering-implementation-brief-v1`.

| Element | Meaning |
| --- | --- |
| `goal-and-why` | The intended end state and the reason it matters. |
| `users-stakeholders` | The people, teams, systems, or roles affected by the work. |
| `measurable-success-threshold` | A measurable condition that says when the work succeeds. |
| `scope-in` | The concrete behavior or deliverable included in this work. |
| `non-goals` | Explicitly excluded behavior, audiences, platforms, or deliverables. |
| `inputs` | Inputs the implementation consumes, such as user fields, files, events, or parameters. |
| `data-sources` | Authoritative sources of data the implementation reads or writes. |
| `external-dependencies` | External systems, APIs, services, approvals, credentials, or teams the work depends on. |
| `constraints` | Limits on implementation such as compatibility, security, privacy, platform, time, or style. |
| `acceptance-method` | How the result will be verified, checked, reviewed, tested, or signed off. |

Every element must be independently accounted. A span that answers `inputs` does
not also satisfy `data-sources`; a phrase that names scope does not also satisfy
non-goals.

## Element Dispositions

`present`:

```json
{
  "disposition": "present",
  "citation": {"offset": 145, "quote": "billing warehouse invoices table"},
  "valueItems": [
    {
      "text": "billing warehouse invoices table",
      "valueSpans": [
        {"offset": 145, "quote": "billing warehouse invoices table"}
      ]
    }
  ]
}
```

`present` requires a verifying citation and non-empty `valueItems`. The gate
does not accept legacy `extractedValue`; v1 uses structured `valueItems`
because each item must be grounded independently.

`present-weak`:

```json
{
  "disposition": "present-weak",
  "citation": {"offset": 78, "quote": "load fast"},
  "valueItems": [{"text": "load fast", "valueSpans": [{"offset": 78, "quote": "load fast"}]}],
  "questionIds": ["Q1"]
}
```

`present-weak` requires a verifying citation and a dependent question that
references the cited span or weak value.

`gap`:

```json
{
  "disposition": "gap",
  "questionIds": ["Q2"]
}
```

`gap` requires a dependent question that names the missing element, or a visible
`modelDefault` / `flaggedDefault`. A default is allowed only as a surfaced
assumption, never as a silent replacement for user evidence.

## Citations

All citations use offset + quote verification against `brief.txt`:

```json
{"offset": 36, "quote": "ops team"}
```

The offset is zero-based character offset into the UTF-8 decoded brief text. The
gate verifies that `brief[offset:offset + len(quote)] == quote`.

The same object shape is used for element citations, finding citations, and
`valueSpans`. A `valueSpan` may also be a bare string; it must still appear as a
contiguous substring in the brief.

## Value Grounding

Checks: `value_item_not_contiguously_grounded` and
`value_not_grounded_in_spans`.

Algorithm for each value item:

1. Normalize the item `text` and each of its own `valueSpans` with Unicode NFKC
   and `casefold()`.
2. Map punctuation and symbols to spaces.
3. Tokenize on whitespace.
4. Drop tokens in the STOPLIST and the RUBRIC-LABEL set below.
5. The remaining content tokens from the item text must be non-empty.
6. Every remaining content token must appear in one of that same item's
   verified contiguous `valueSpans`.

No cross-item or cross-span union is allowed. A value item with text
`API source metrics` and spans `API review`, `source code`, and `metrics naming`
fails because no one contiguous span grounds all content tokens for that item.

## STOPLIST

The skill-fixed STOPLIST is:

`a`, `an`, `and`, `are`, `as`, `at`, `be`, `been`, `being`, `by`, `can`,
`could`, `did`, `do`, `does`, `done`, `for`, `from`, `had`, `has`, `have`,
`having`, `if`, `in`, `into`, `is`, `it`, `its`, `may`, `might`, `must`, `of`,
`on`, `or`, `our`, `shall`, `should`, `so`, `than`, `that`, `the`, `their`,
`them`, `then`, `there`, `these`, `this`, `those`, `through`, `to`, `use`,
`used`, `using`, `via`, `was`, `we`, `were`, `will`, `with`, `would`.

## RUBRIC-LABEL Set

The skill-fixed RUBRIC-LABEL set is:

`acceptance`, `constraint`, `constraints`, `data`, `deadline`, `deliverable`,
`dependency`, `dependencies`, `external`, `goal`, `goals`, `input`, `inputs`,
`measurable`, `method`, `non`, `outcome`, `scope`, `source`, `sources`,
`stakeholder`, `stakeholders`, `success`, `threshold`, `user`, `users`,
`verification`, `why`.

Stopword-only and rubric-label-only values fail because no content tokens remain.
`metric` and `metrics` are intentionally not dropped; they can be content in
briefs and are needed to catch word-salad grounding.

## Shape Rules

Shape failures are status gates, not finalize gates. A `present` element that
fails a shape rule is treated as effective `present-weak`; it must have a
dependent question, and `report.json` records `present_value_fails_shape` as a
warning.

`measurable-success-threshold`:

- requires a metric or condition, and
- requires a threshold, comparator, or deadline.

Examples that pass: `p95 latency < 200ms`, `export by 6am UTC`, `identify risk
within two minutes`.

Examples that fail: `P0`, `load fast`, a bare priority label.

`acceptance-method`:

- requires a verification-action token such as `test`, `check`, `review`,
  `sign-off`, `verify`, `validate`, or `QA`.

Elements without a shape rule remain value-grounded only. This is intentional;
semantic adequacy is empirical and author-visible, not mechanically decided.

## Findings

`solution-as-goal`:

```json
{
  "id": "S1",
  "kind": "solution-as-goal",
  "citation": {"offset": 12, "quote": "Build a Slack bot"},
  "claim": "The brief names Slack bot as the solution before stating the underlying goal."
}
```

Requires one verifying brief citation.

`contradiction`:

```json
{
  "id": "C1",
  "kind": "contradiction",
  "citations": [
    {"offset": 20, "quote": "ship mobile"},
    {"offset": 140, "quote": "mobile is out of scope"}
  ]
}
```

Requires two verifying brief citations.

## Questions

Questions must resolve at least one known element or finding and carry a
`planDelta`.

```json
{
  "id": "Q1",
  "text": "Which data sources should this implementation read?",
  "resolves": ["data-sources"],
  "planDelta": {"adds": ["Bind implementation to the named source"]}
}
```

Option-shaped questions are also valid when every option has its own
`planDelta`:

```json
{
  "id": "Q2",
  "text": "Which acceptance method should gate completion?",
  "resolves": ["acceptance-method"],
  "options": [
    {"label": "Automated test", "planDelta": {"adds": ["Add automated regression test"]}},
    {"label": "Human review", "planDelta": {"adds": ["Route to named reviewer sign-off"]}}
  ]
}
```

`question_not_bound_to_element` is structural but narrow: for a `gap`, the
question must name the missing element label; for `present-weak`, it must refer
to the weak cited span or value. Whether it asks the best substantive question
is empirical and author-visible.

## Steps

Steps are intent-level, not execution-level. Each step needs:

- `id`
- `dependsOnAssumptions` referencing rubric element ids, finding ids, or question ids
- `dependsOnSteps`
- `verifiableOutcome`
- `terminal: true` on at least one reachable terminal step

At least one root step must have no `dependsOnSteps`. Every step must be
reachable from a root and lie on a path to a terminal step.

## Failure And Warning Kinds

Blocking failures:

- `rubric_element_unaccounted`
- `citation_unverified`
- `value_not_grounded_in_spans`
- `value_item_not_contiguously_grounded`
- `present_without_value`
- `weak_or_gap_without_question`
- `question_not_bound_to_element`
- `question_without_resolution`
- `orphan_step`
- `step_dangling_ref`

Non-blocking warnings:

- `present_value_fails_shape`
- `gap_with_indicator_terms_present`

`present_value_fails_shape` changes the effective disposition to `present-weak`
and therefore still requires a dependent question. `gap_with_indicator_terms_present`
is a smoke alarm for the author and the empirical judge.

## Known Weak Spots

`anchor-intake` makes no claim to mechanically decide these residues:

- A grounded value can still be semantically mislabeled against the wrong rubric
  element. A9/A10 bound this to a visible, falsifiable claim against the brief;
  the empirical RUBRIC-GRADE value-diff and the author catch it.
- A false `gap` is an absence claim and cannot be hard-verified. The smoke alarm
  only surfaces suspicious indicator terms; C2/A7 catch false gaps empirically.
- A question can be token-bound to the right span or element while still asking
  the wrong substantive question. This remains an empirical surface.
- Load-bearing elements outside the fixed v1 engineering rubric are not
  mechanically forced.
- v1 is only for engineering implementation briefs. Non-engineering artifacts
  should self-eject or finalize as `--unscopable`.
