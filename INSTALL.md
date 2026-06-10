# Install techne

techne keeps one source of truth in `skills/`. Each target below either loads
that directory through a thin native skin or installs the same skills through
the Agent Skills CLI.

## For an AI agent

If you were asked to install techne: clone the repo to a stable local path (don't
run from a throwaway temp dir), detect which harness you're running in, follow the
matching section below, then verify the skill is available (e.g. `/techne:viz` in
Claude Code, or techne skills listed by your agent). If you can't tell which
harness you're in, use the universal `npx skills` fallback. The default install
path installs the techne skill set as a package; do not pass `--skill <name>`
unless you intentionally want only one skill.

## Claude Code

Native plugin install:

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne-dev
/reload-plugins
```

Use skills as `/techne:<skill>`, for example `/techne:viz` or
`/techne:repro`.

Local development from a clone:

```text
/plugin marketplace add ./
/plugin install techne@techne-dev
/reload-plugins
```

## Codex

Codex uses Agent Skills for techne. Install the techne skill set globally
through the Skills CLI and make the current repository skills available to
Codex. Re-run this `add` command after techne gains new skills; `skills update`
only refreshes skills that are already installed.

```bash
npx skills add lynxlangya/techne -a codex -g -y
npx skills list -g -a codex
```

## Cursor

techne includes `.cursor-plugin/plugin.json` with `skills: "./skills/"` for
Cursor's plugin manifest shape. Real Cursor native install is not verified in
this repository yet.

Agent Skills fallback:

```bash
npx skills add lynxlangya/techne -a cursor -g -y
```

## Gemini CLI

techne includes `gemini-extension.json`. Gemini CLI extensions auto-discover
bundled `skills/`; this skin intentionally does not add always-on `GEMINI.md`
context.

```bash
gemini extensions install https://github.com/lynxlangya/techne
```

Real Gemini install is deferred to an environment with Gemini CLI active.

Agent Skills fallback:

```bash
npx skills add lynxlangya/techne -a gemini-cli -g -y
```

## Kimi Code

Kimi Code uses Agent Skills:

```bash
npx skills add lynxlangya/techne -a kimi-code-cli -g -y
```

## Universal Agent Skills Fallback

The npm package is `skills` from Vercel Labs. Install the techne skill set into
a supported agent:

```bash
npx skills add lynxlangya/techne -a <agent> -y
```

Useful agent ids include `claude-code`, `codex`, `cursor`, `gemini-cli`, and
`kimi-code-cli`.

Use `-g` for a global install, or omit it to install into the current project.

To inspect the package before installing:

```bash
npx skills add lynxlangya/techne --list
```

To install exactly one skill instead of the whole techne set:

```bash
npx skills add lynxlangya/techne --skill <name> -a <agent> -y
```

The `_template` directory is an internal authoring template with
`disable-model-invocation: true`. Some Agent Skills CLI versions may still copy
it during whole-package installs; it is not a user-facing techne skill.

## Version Touchpoints

Keep these version fields in sync when releasing techne:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`
- `gemini-extension.json`

Current version: `0.1.0`.
