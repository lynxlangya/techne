---
name: _template
description: Internal authoring template and manual canary. Copy this directory to start a new techne skill.
disable-model-invocation: true
---

# Skill Title

Use this file as the starting point for a new techne skill. Keep the skill body
tool-neutral: the guidance here should make sense outside any one host, with
tool-specific loading handled by plugin manifests.

## Quality Bar

A techne skill must force a move the model can make but often skips. It is not a
place to restate common knowledge, collect vague advice, or duplicate what the
platform or superpowers already handles well.

Before authoring, identify:

- The skipped move this skill forces.
- The failure pattern it prevents.
- The cases where the skill should not apply.
- The observable improvement expected when the skill is present.

## When To Use

State the triggering situation in concrete terms. Prefer user intents, task
conditions, and failure signals over broad domain labels.

## Instructions

Write the smallest set of instructions that reliably forces the move. Use direct
commands, checks, and stop conditions. Avoid product-specific paths, local tool
names, or host-only features unless they are documented as optional references.

## Validation

Each real skill should include an `eval.md` alongside `SKILL.md`. The eval file
records the empirical acceptance test from `WORKFLOW.md`: baseline behavior,
with-skill behavior, what counts as improvement, and the pass bar.

For scaffold-only or template changes, direct mechanical validation is enough.

## Supporting Files

Optional files live next to `SKILL.md` when they remove noise from the main
skill:

- `eval.md` for the empirical acceptance test.
- `scripts/` for executable helpers the model may run.
- `reference.md` for longer material loaded only when needed.

Do not add empty support folders. Add them only when the skill actually needs
them.
