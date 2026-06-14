---
name: intake
description: Interrogate a written engineering implementation brief before work starts. Use when a user brings a ticket, PRD, design note, or substantive engineering task brief and wants to begin implementation planning; force every fixed rubric element to be accounted, cite present/weak claims against the brief, surface gaps, solution-as-goal traps, contradictions, and questions, then emit an intent-level plan. Do not use for bare one-line requests, non-engineering artifacts, code diff review, bug fixing, or execution itself.
---

# intake

Force the skipped move before execution: interrogate the written brief against a
fixed engineering implementation rubric, then plan only after gaps and weak
assumptions are visible.

## Trigger Check

Use this skill when the user provides a substantial written engineering
implementation brief: a ticket, PRD, design note, or task brief with enough text
to interrogate before work starts.

Do not use it for a bare one-line request, an already precise command, a
marketing brief, research proposal, prose draft, code diff review, bug fix, or
implementation execution. For unsupported or too-thin artifacts, self-eject in
one sentence and write no `.techne/plan/<slug>` output. If a captured artifact
later proves unsupported, use `finalize --unscopable --reason ...`.

Boundary test: can you point to a user-authored written artifact and ask whether
it names the engineering goal, users, measurable success threshold, scope,
non-goals, inputs, data sources, dependencies, constraints, and acceptance
method? If yes, use `intake`. If no, eject or ask for the brief first.

## Forced Procedure

1. **Capture the brief.** Save the user-authored artifact verbatim. Run:
   `python3 skills/intake/scripts/intake_gate.py init --project <root> --plan <slug> --brief-file <path>`.
2. **Read the brief in full.** Do not fill the rubric from memory or from the
   user's surrounding chat if the value is not in the captured brief.
3. **Account every fixed rubric element.** For each of the ten elements, write
   one disposition in `.techne/plan/<slug>/intake.json`:
   `present` with citation and `valueItems`, `present-weak` with citation and a
   dependent question, or `gap` with a question or visible `modelDefault`.
4. **Surface traps and conflicts.** Add span-anchored `solution-as-goal` and
   `contradiction` findings whenever the brief implies them. Contradictions need
   two verified spans.
5. **Ask only dependent questions.** Every question must resolve an element or
   finding and carry a `planDelta`. Weak/gap questions must reference the weak
   span/value or the missing element label.
6. **Author intent-level steps.** Steps are not execution yet. Each step needs an
   `id`, `dependsOnAssumptions`, `dependsOnSteps`, `verifiableOutcome`, and at
   least one terminal step reachable from a root step.
7. **Check and repair.** Run:
   `python3 skills/intake/scripts/intake_gate.py check --project <root> --plan <slug>`.
   Fix structural failures by doing the missing intake work, not by padding JSON.
8. **Finalize.** Run:
   `python3 skills/intake/scripts/intake_gate.py finalize --project <root> --plan <slug>`.
   Relay the generated `intakeReport.json` to the user, especially gaps, weak
   elements, questions, solution-as-goal findings, contradictions, and warnings.

## Script Contract

Artifacts are written under the target project:

```text
.techne/plan/<slug>/
  brief.txt          # captured external artifact
  context.json       # computed by init
  intake.json        # authored by the reviewer/planner
  report.json        # computed by check
  plan.json          # computed by finalize
  intakeReport.json  # computed by finalize
```

Generated `.techne/` output belongs to target projects. Do not commit it to this
repository.

Minimal `intake.json` shape:

```json
{
  "schema": "techne.intake/1",
  "elements": {
    "data-sources": {
      "disposition": "gap",
      "questionIds": ["Q1"]
    }
  },
  "findings": [
    {
      "id": "S1",
      "kind": "solution-as-goal",
      "citation": {"offset": 16, "quote": "Build a Slack bot"}
    }
  ],
  "questions": [
    {
      "id": "Q1",
      "text": "Which data sources should the implementation read?",
      "resolves": ["data-sources"],
      "planDelta": {"adds": ["Bind implementation to the named source"]}
    }
  ],
  "steps": [
    {
      "id": "s1",
      "title": "Implement only the scoped behavior",
      "dependsOnAssumptions": ["goal-and-why"],
      "dependsOnSteps": [],
      "verifiableOutcome": "The scoped behavior can be verified by the acceptance method",
      "terminal": true
    }
  ]
}
```

Use [reference.md](reference.md) for the full JSON contract, fixed rubric,
STOPLIST/RUBRIC-LABEL set, shape rules, warning semantics, and known weak spots.

## Stop Conditions

- Stop before planning if there is no substantial written engineering brief.
- Stop before `finalize` if `check` reports blocking failures.
- Stop and use `--unscopable --reason` if the artifact is not an engineering
  implementation brief or is too garbled/thin to interrogate honestly.
- Stop before executing the work. `intake` ends at a surfaced report and
  intent-level plan; implementation belongs to the next workflow step.
