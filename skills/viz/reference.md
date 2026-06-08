# viz Reference

Keep this file as the detailed catalog. Load it when root shape, non-code
classification, or Mermaid representation is not obvious.

## Root Catalog

High-confidence roots:

- JS/web: `package.json`, `pnpm-workspace.yaml`, `turbo.json`, `nx.json`,
  `lerna.json`
- Edge: `wrangler.toml`, `wrangler.json`, `wrangler.jsonc`
- Python: `pyproject.toml`, `requirements.txt`, `setup.py`
- Go: `go.mod`
- Rust: `Cargo.toml`
- Ruby: `Gemfile`
- PHP: `composer.json`
- Elixir: `mix.exs`
- Dart/Flutter: `pubspec.yaml`
- JVM: `pom.xml`, `build.gradle`, `build.gradle.kts`
- Gradle/Android: `settings.gradle`, `settings.gradle.kts`,
  `gradle.properties`, module `build.gradle`/`build.gradle.kts`,
  `AndroidManifest.xml`
- Swift/Apple: `Package.swift`, `*.xcodeproj/`, `*.xcworkspace/`, `Podfile`,
  `Cartfile`
- .NET: `*.sln`, `*.slnx`, `*.slnf`, `*.csproj`, `*.fsproj`, `*.vbproj`
- Native build: `CMakeLists.txt`, `Makefile`, `meson.build`, `configure.ac`,
  `configure`, `BUILD.bazel`, `MODULE.bazel`, `WORKSPACE`, `*.vcxproj`
- Containers: `Dockerfile`, `docker-compose.yml`, `docker-compose.yaml`,
  `compose.yml`, `compose.yaml`
- Infra/data notebooks: `*.tf`, `*.ipynb`

Lower-confidence roots:

- `xmake.lua`
- `premake5.lua`
- `Justfile`
- `Brewfile`
- `Procfile`
- `*.mk`
- `*.sql` folders with migration naming

## Bounded Source Signals

If root manifests are absent, scan only top levels first. Look for meaningful
source presence, not dependency/vendor dumps.

Code extensions:

- Web/source: `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`, `.html`, `.css`,
  `.scss`, `.vue`, `.svelte`
- Systems/native: `.c`, `.h`, `.cc`, `.cpp`, `.cxx`, `.hpp`, `.m`, `.mm`,
  `.rs`, `.go`, `.zig`
- Mobile/native: `.swift`, `.kt`, `.kts`, `.java`, `.dart`
- Backend/scripting: `.py`, `.rb`, `.php`, `.ex`, `.exs`, `.cs`, `.fs`, `.vb`,
  `.sh`, `.bash`, `.zsh`, `.ps1`, `.sql`
- Infra/notebook: `.tf`, `.hcl`, `.ipynb`

Ignore generated or vendored paths when deciding shape: `.git`, `node_modules`,
`vendor`, `Pods`, `.build`, `build`, `dist`, `target`, `.venv`, `venv`,
`DerivedData`, `.gradle`.

## Non-Code Decision

Use a two-tier rule:

1. Scan root catalog.
2. If no roots match, scan bounded source signals.

Declare `non-code` only when both tiers are absent, or when docs/vault signals
clearly dominate. Common docs/vault signals include `.obsidian/`, mostly
Markdown files, `attachments/`, `assets/`, `notes/`, and no source directories.

If Tier 2 finds source signals without manifests, classify as `source-only code`
and draw only what can be supported from those files.

## Shape Hints

- `single-frontend`: one app root with browser framework dependencies.
- `single-backend`: one server/library root with backend entrypoints or API
  framework dependencies.
- `coupled-fullstack`: frontend and backend in one app or adjacent roots.
- `monorepo`: workspace manifest or multiple packages/apps under shared root.
- `library`: package exposes reusable API and lacks deployed service entrypoint.
- `native`: Xcode, Android/Gradle, desktop/mobile native roots.
- `native+edge`: native app plus edge/server/backend roots or bindings.
- `source-only code`: source files exist but no recognized manifest/build root.
- `non-code`: no code roots/source signals, or docs/vault dominance.

## Mermaid Type Decision Table

| Need | MVP decision | Reason |
| --- | --- | --- |
| Codebase architecture / component map | Use `flowchart TD` | Fits packages, services, apps, infra, and provenance edges. |
| Drill-down of one grouped component | Use another `flowchart TD` | Keeps the same validation and altitude gate. |
| Call-level behavior | Defer | Call graph is out of scope for the MVP. |
| Database entities | Defer | ER diagrams are out of scope for the MVP. |
| Classes/types | Defer | Class diagrams are out of scope for the MVP. |
| Request lifecycle or temporal interaction | Defer | Sequence diagrams are out of scope for the MVP. |
| C4-style architecture | Defer | Mermaid C4 is not part of this MVP. |

## Flowchart Conventions

Represent provenance:

- Solid edge: `A --> B` for read-from-code facts.
- Dashed edge: `A -. infer .-> B` for inference.
- Edge labels: name protocol, import, binding, or source fact briefly.
- Comments: use `%% source: path/to/file` near relevant parts when helpful.
- Metadata: rely on `.index.json` for full source file lists and coverage.

Use `subgraph` for grouping when top-level nodes exceed the cap. If grouping
would hide important structure, split into a drill-down diagram and mark
metadata `split: true`.

Do not use call graph, ER, class, sequence, or C4 diagrams for this MVP.
