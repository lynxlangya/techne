# AGENTS.md

```yaml
version: v0.1
project: techne
updated: 2026-06-08
```

## Project Facts

- `techne` is an early-stage repository for "Skills and agents for the AI era."
- The current working tree only establishes the product direction in `README.md`; there is no committed app, package manager, build system, or test runner yet.
- The git history contains a legacy `atools-js` codebase, but new work in this repo should not infer current architecture, tooling, or business rules from that legacy history unless the user explicitly asks for migration or reference work.

## Working Rules

- Start with current files, not assumptions: inspect the present tree before choosing a structure, dependency, or framework.
- Keep early changes content-first and minimal. Do not add scaffolding, package managers, CI, telemetry, network services, or generated boilerplate unless the task requires them.
- When adding skills, agents, docs, or examples, include the intended usage, constraints, and a direct validation path.
- Prefer small, reviewable directory structures over broad future-facing abstractions until the repo has repeated patterns.
- Do not commit secrets, tokens, private config, `.env` contents, or logs that may contain credentials.

## Verification

- For documentation-only changes, run `git diff --check`.
- For code or executable assets added later, use the project-local scripts once they exist; if no test/build entry exists, perform the closest direct validation and state the gap.
