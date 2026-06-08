# Roadmap

techne is a curated skill library for practical AI-era craft: moves that improve
how an AI collaborator investigates, judges, writes, codes, and ships.

## Quality Bar

Every skill must be a forcing function for a move the model can make but often
skips. A skill earns its place by improving behavior under pressure, not by
reciting knowledge the model already has.

Prefer skills that:

- Install a concrete check, move, or stop condition.
- Address a repeated failure pattern.
- Have an empirical acceptance test.
- Fill a gap in the platform or do an existing move sharper than superpowers.

Avoid skills that:

- Repackage generic advice.
- Duplicate built-in Claude Code or superpowers behavior without a sharper bar.
- Depend on one private project unless that dependency is isolated as reference
  material.
- Need industry expertise the maintainer cannot judge.

## Audience x Jobs Map

`general`:

- interrogate
- research
- simplify
- explain
- decide

`coding`:

- debug
- trace
- review-diff

`writing`:

- structural-edit
- tighten
- voice-match
- fact-pass

`social`:

- hook
- repurpose
- angle

`finance`:

- global-alpha-style vertical analysis

## Seeding Principle

Seed only audiences where the maintainer can personally judge quality:
`coding`, `writing`, `social`, `finance`, and `general`.

Other industries stay as placeholders until they are judgeable by the maintainer
or contributed by someone who can own the quality bar.

## Profiles, Not Branches

Audiences are bundles and example sets over one flat skill library. They are not
filesystem branches. Keep `skills/<name>/SKILL.md` flat, and track audience,
sequence, and product packaging here.
