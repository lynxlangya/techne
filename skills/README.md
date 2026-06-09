# Skills

`skills/` is the source of truth for techne skill bodies. Each skill is a
tool-neutral asset packaged by thin host-specific skins.

## Layout

Use a flat directory per skill:

```text
skills/
  <name>/
    SKILL.md
    README.md      # recommended English usage guide for real skills
    README-CN.md   # optional Chinese companion usage guide
    eval.md        # optional
    scripts/       # optional
    reference.md   # optional
```

Do not create category folders such as `skills/coding/` or `skills/writing/`.
Audience, category, and product sequencing belong in `ROADMAP.md`, not in the
filesystem.

Current real skills:

- `viz`: investigate a real codebase by diagramming it. It is a typed diagram
  router over architecture, interaction, data-model, state-model, and
  type-structure diagrams. See [viz/README.md](viz/README.md) for human-facing
  usage and [viz/README-CN.md](viz/README-CN.md) for Chinese usage.

## Skill Body

`SKILL.md` is the asset. Keep it independent of Claude Code, Codex, or any other
host unless a section is explicitly marked as host-specific reference material.
The same body should be usable through Claude Code, Codex, Cursor, Gemini, Kimi,
or future host paths without becoming separate products.

Every real techne skill should force a move the model would otherwise skip. Do
not add skills that only recite general knowledge or clone a built-in platform
capability without a sharper acceptance test.

For real skills, keep human-facing usage guidance beside the skill. `README.md`
is the default English guide; `README-CN.md` is the Chinese companion when
needed. Keep `SKILL.md` focused on the procedure the model must execute.

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

For executable helpers, keep generated output out of this repo. For example,
`viz` writes target-project output under `.techne/viz/`; those files are
artifacts, not source.

## One Body, Multiple Thin Skins

The Claude plugin skin lives in `.claude-plugin/`. Cursor and Gemini have thin
manifests at `.cursor-plugin/plugin.json` and `gemini-extension.json`. Codex,
Kimi, and other hosts use the install matrix in `INSTALL.md`, including the
Agent Skills CLI fallback.

All skins and installers should point at this single `skills/` library rather
than forking skill bodies.
