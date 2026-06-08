# Install techne

techne keeps one source of truth in `skills/`. Each target below either loads
that directory through a thin native skin or installs the same skills through
the Agent Skills CLI.

## Claude Code

Native plugin install:

```text
/plugin marketplace add lynxlangya/techne
/plugin install techne@techne
/reload-plugins
```

Use the skill as `/techne:viz`.

Local development from a clone:

```text
/plugin marketplace add ./
/plugin install techne@techne
/reload-plugins
```

## Codex

Codex uses Agent Skills for techne. This installs `viz` globally through the
Skills CLI and makes it available to Codex.

```bash
npx skills add lynxlangya/techne --skill viz -a codex -g -y
```

## Cursor

techne includes `.cursor-plugin/plugin.json` with `skills: "./skills/"` for
Cursor's plugin manifest shape. Real Cursor native install is not verified in
this repository yet.

Agent Skills fallback:

```bash
npx skills add lynxlangya/techne --skill viz -a cursor -g -y
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
npx skills add lynxlangya/techne --skill viz -a gemini-cli -g -y
```

## Kimi Code

Kimi Code uses Agent Skills:

```bash
npx skills add lynxlangya/techne --skill viz -a kimi-code-cli -g -y
```

## Universal Agent Skills Fallback

The npm package is `skills` from Vercel Labs. Install one techne skill into a
supported agent:

```bash
npx skills add lynxlangya/techne --skill <name> -a <agent> -y
```

Useful agent ids include `claude-code`, `codex`, `cursor`, `gemini-cli`, and
`kimi-code-cli`.

Use `-g` for a global install, or omit it to install into the current project.

## Version Touchpoints

Keep these version fields in sync when releasing techne:

- `.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `.cursor-plugin/plugin.json`
- `gemini-extension.json`

Current version: `0.1.0`.
