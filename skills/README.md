# Skills

`skills/` is the source of truth for techne skill bodies. Each skill is a
tool-neutral asset packaged by thin host-specific skins.

## Layout

Use a flat directory per skill:

```text
skills/
  <name>/
    SKILL.md
    eval.md        # optional
    scripts/       # optional
    reference.md   # optional
```

Do not create category folders such as `skills/coding/` or `skills/writing/`.
Audience, category, and product sequencing belong in `ROADMAP.md`, not in the
filesystem.

## Skill Body

`SKILL.md` is the asset. Keep it independent of Claude Code, Codex, or any other
host unless a section is explicitly marked as host-specific reference material.
The same body should be usable through one Claude skin, one Codex skin, or future
skins without becoming separate products.

Every real techne skill should force a move the model would otherwise skip. Do
not add skills that only recite general knowledge or clone a built-in platform
capability without a sharper acceptance test.

## Eval Convention

Add `eval.md` for real skills. It should state:

- The baseline prompt or pressure case.
- The failure pattern observed without the skill.
- The with-skill behavior expected.
- The pass bar and how it will be judged.
- Any cases where the skill should not fire.

This follows `WORKFLOW.md`: empirical validation starts with the first real
skill, not with this scaffold.

## Optional Support Files

Use support files only when needed:

- `scripts/` for helpers the model can execute.
- `reference.md` for longer background that should not live in the always-loaded
  top of `SKILL.md`.
- Examples or templates when they materially improve compliance.

Do not commit empty support folders.

## One Body, Two Skins

The Claude plugin skin lives in `.claude-plugin/`. A Codex skin is intentionally
deferred until the Codex skill format is verified. Both should point at this
single `skills/` library rather than forking skill bodies.
