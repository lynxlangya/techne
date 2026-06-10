# repro

`repro` is a techne skill for bug fixes. It forces the AI collaborator to record
a failing reproduction before editing code, then verify the fix by rerunning the
same probe identity.

Use it when a task has observable wrong behavior: failing tests, stack traces,
crashes, hangs, regressions, wrong output, wrong rendering, or "X currently does
Y; it should do Z."

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

Codex via Agent Skills:

```bash
npx skills add lynxlangya/techne --skill repro -a codex -g -y
npx skills update repro -g -y
```

Other hosts and fallback commands are documented in the root
[INSTALL.md](../../INSTALL.md).

## Quick Start

Open the target project in your agent, then ask for a bug fix with `repro`.

Claude Code:

```text
/techne:repro
Fix this bug: running npm test in packages/app fails with "TypeError: cannot
read properties of undefined". Reproduce it first, then verify with the same
probe after the fix.
```

Codex or another Agent Skills host:

```text
Use the repro skill. Fix this bug: the login test fails with "TypeError:
cannot read properties of undefined". Reproduce it first, then verify with the
same probe after the fix.
```

A good run should show:

- The chosen probe and stable `--expect` anchor.
- A failing ledger entry before production-code edits.
- Diagnosis tied to the failing probe.
- A post-fix passing run with the same identity.
- `close` JSON proving either verified or visibly speculative.
- The strength rung: S1, S2, S3, or S4.

Do not commit `.techne/` output. The ledger adds `.techne/` to the target
project's `.gitignore` when needed.

## Script Usage

Run a package-local failing probe:

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug login-crash \
  --cwd packages/app \
  --expect "TypeError: cannot read" \
  --timeout 60 \
  -- npm test -- login.test.ts
```

After fixing, rerun the identical probe and close:

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug login-crash \
  --cwd packages/app \
  --expect "TypeError: cannot read" \
  --timeout 60 \
  -- npm test -- login.test.ts

python3 /path/to/techne/skills/repro/scripts/repro_ledger.py close \
  --project /path/to/project \
  --bug login-crash
```

If an environment variable is part of the probe, encode it in shell mode:

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py run \
  --project /path/to/project \
  --bug locale-sort \
  --shell \
  --expect "sort order is wrong" \
  -- LC_ALL=C npm test
```

If reproduction is genuinely impossible:

```bash
python3 /path/to/techne/skills/repro/scripts/repro_ledger.py mark-unreproduced \
  --project /path/to/project \
  --bug customer-only-crash \
  --no-probe-possible \
  --reason "Requires customer-only credentials and data unavailable locally"
```

## What Gets Written

`repro` writes generated ledgers in the target project:

```text
.techne/
  repro/
    <bug-slug>.jsonl
```

Each run records:

- Probe identity: mode, argv or shell string, cwd, timeout.
- Exit code, timeout status, duration, output tail.
- Optional `--expect` match and context.
- Git evidence when the project is inside a git worktree.

## Boundaries

- v1 is POSIX-only: macOS and Linux developer environments.
- Windows support is a recorded future target.
- The gate defeats negligent skipping, not deliberate falsification.
- `--no-stable-expect` is only for symptoms with no stable textual output.
- A changed probe is a new fail -> pass cycle, not a verification of the old
  one.
