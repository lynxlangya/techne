# anchor-intake

`anchor-intake` is a techne skill for interrogating a written engineering
implementation brief before work starts. It forces the AI collaborator to walk a
fixed ten-element rubric, cite present/weak claims against the brief, surface
gaps and traps, and emit an intent-level plan only after the intake checks pass.

Use it when a task starts from a ticket, PRD, design note, or substantive
engineering brief. Do not use it for bare one-line requests, non-engineering
documents, code review, bug fixing, or execution itself.

Chinese version: [README-CN.md](README-CN.md).

## Install or Update

Claude Code native plugin:

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

If techne is already installed in Claude Code:

```bash
claude plugin update techne
```

For normal Codex installs, use the root [INSTALL.md](../../INSTALL.md) command
to install the whole techne skill set:

```bash
npx skills add lynxlangya/techne -a codex -g -y
```

If you intentionally want only `anchor-intake`, install the single skill:

```bash
npx skills add lynxlangya/techne --skill anchor-intake -a codex -g -y
npx skills update anchor-intake -g -y
```

Other hosts and fallback commands are documented in the root
[INSTALL.md](../../INSTALL.md).

## Quick Start

Open the target project in your agent and provide the written brief.

Claude Code:

```text
/techne:anchor-intake
Interrogate this implementation brief before planning:
<paste ticket / PRD / design note>
```

Codex or another Agent Skills host:

```text
Use the anchor-intake skill. Interrogate this engineering implementation brief before
planning:
<paste ticket / PRD / design note>
```

A good run should show:

- A captured brief under `.techne/plan/<slug>/brief.txt`.
- Every fixed rubric element accounted as `present`, `present-weak`, or `gap`.
- Verified citations for present and weak elements.
- Grounded `valueItems` for present elements.
- Questions for every weak element or gap.
- Span-anchored solution-as-goal or contradiction findings when present.
- A finalized `intakeReport.json` and `plan.json`.

Do not commit `.techne/` output. The script adds `.techne/` to the target
project's `.gitignore` when needed.

## Script Usage

Initialize a plan from a brief file:

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py init \
  --project /path/to/project \
  --plan login-brief \
  --brief-file /tmp/login-brief.txt
```

Write `.techne/plan/login-brief/intake.json`, then check:

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py check \
  --project /path/to/project \
  --plan login-brief
```

Finalize after the check passes:

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py finalize \
  --project /path/to/project \
  --plan login-brief
```

If the captured artifact is not an engineering implementation brief:

```bash
python3 /path/to/techne/skills/anchor-intake/scripts/intake_gate.py finalize \
  --project /path/to/project \
  --plan login-brief \
  --unscopable \
  --reason "This is a marketing brief, not an engineering implementation brief."
```

## What Gets Written

`anchor-intake` writes generated artifacts in the target project:

```text
.techne/
  plan/
    <slug>/
      brief.txt
      context.json
      intake.json
      report.json
      plan.json
      intakeReport.json
```

## Boundaries

- v1 is POSIX-only: macOS and Linux developer environments.
- v1 supports one rubric: engineering implementation briefs.
- The gate verifies spans and grounding; it does not mechanically judge whether
  a grounded value semantically answers the right rubric element.
- False gaps and question substance are empirical surfaces, not hard gates.
- The output is a surfaced report and intent-level plan, not implementation.
