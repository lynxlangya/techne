# techne

> **τέχνη** · /ˈtɛk.niː/ · "TEK-nee"

Ancient Greek for **craft · skill · art**: the practical know-how of *making*
and *doing*, and the shared root of both **technique** and **technology**.
Aristotle placed *technē* (knowing **how**) beside *epistēmē* (knowing
**that**).

Skills and agents for the AI era.

Website: [techne.wangyun.fan](https://techne.wangyun.fan).

Chinese version: [README-CN.md](README-CN.md).

## What This Is

techne is a curated library of skills and agent assets for practical AI-era
work. A techne skill is not a prompt snippet. It is a forced cognitive move: a
small procedure that makes an AI collaborator investigate, judge, write, code,
or ship in a way it often skips under pressure.

The project keeps one shared source of truth in `skills/`. Host-specific files
stay thin: Claude Code plugin metadata, Cursor and Gemini manifests, and install
instructions for Codex, Kimi, and other Agent Skills hosts all point back to the
same skill bodies.

## Skills

The current seeded skills use the `anchor-*` prefix because each one anchors AI
work to evidence it cannot self-report or fake: a source tree, run ledger, git
diff, or written brief.

- `anchor-viz` — investigate a real codebase by diagramming it. It routes one user
  request across architecture, interaction, data-model, state-model, and
  type-structure diagrams, then validates and builds a local viewer. See
  [skills/anchor-viz/README.md](skills/anchor-viz/README.md) for detailed usage.
- `anchor-repro` — force bug fixes through a failing reproduction first, then verify
  with the same probe after the fix. See
  [skills/anchor-repro/README.md](skills/anchor-repro/README.md) for detailed usage.
- `anchor-vet` — force code review through computed scope, accounted blast radius,
  verified claims/findings, and admissible verdicts before approving or
  requesting changes. See [skills/anchor-vet/README.md](skills/anchor-vet/README.md) for
  detailed usage.
- `anchor-intake` — interrogate a written engineering implementation brief before work
  starts, accounting the fixed rubric, surfacing gaps/traps/questions, and
  emitting an intent-level plan. See
  [skills/anchor-intake/README.md](skills/anchor-intake/README.md) for detailed usage.

## Install

**Recommended: ask your AI agent.** Paste this into Claude Code or Codex:

```text
Install techne for my current agent by following https://github.com/lynxlangya/techne/blob/main/INSTALL.md, then verify the techne skills are available.
```

The agent reads [INSTALL.md](INSTALL.md), detects your harness (Claude / Codex /
Cursor / Gemini / Kimi), runs the right install path, and confirms the skill
works.

**Manual:** per-harness commands and the universal `npx skills` fallback are in
[INSTALL.md](INSTALL.md).

For Claude Code:

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

For Codex:

```bash
npx skills add lynxlangya/techne -a codex -g -y
```

See [WORKFLOW.md](WORKFLOW.md) for the delivery process and
[ROADMAP.md](ROADMAP.md) for the product map.

## Documentation

Public-facing documentation is split by language:

- `README.md` is the default English document.
- `README-CN.md` is the Chinese companion document.

The same convention applies to skill usage guides when a Chinese version is
needed, for example `skills/anchor-viz/README.md` and `skills/anchor-viz/README-CN.md`.
