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

## Typed Mermaid Decision Table

| Diagram kind | User phrasing | Evidence to read | Mermaid type | Complexity gate | Stop or ask when |
| --- | --- | --- | --- | --- | --- |
| `architecture` | "map this project", "draw architecture", "what are the modules/services" | Root catalog, workspace manifests, imports, service clients, infra/container/edge bindings | `flowchart` / `graph` | 12-15 top-level nodes by default unless grouped/split | Project is non-code, evidence is missing, or broad scope needs splitting |
| `interaction` | "how does this request/job/command flow", "login lifecycle" | Router/controller/handler entrypoints, service calls, clients, jobs, queues, callbacks | `sequenceDiagram` | 8 participants and 20 messages by default | No bounded entrypoint, temporal order cannot be read, or static dependencies are being mistaken for messages |
| `data-model` | "database relationships", "entities", "schema" | Migrations, DDL, ORM models, Prisma/Drizzle/ActiveRecord/Ecto/entity definitions, foreign keys, associations | `erDiagram` | 12 entities and 20 relationships by default | Relationships come only from naming guesses or schema scope is too broad |
| `state-model` | "status lifecycle", "state transitions", "workflow states" | Enums/status constants, reducers, state machines, transition handlers, guards, workflow definitions | `stateDiagram-v2` / `stateDiagram` | 12 states and 20 transitions by default | Transitions or triggers cannot be tied to code evidence |
| `type-structure` | "class/type/interface structure", "protocol hierarchy" | Class/interface/protocol/struct/type declarations, inheritance, implementation, composition, public method groups | `classDiagram` | 12 types and 30 relationship/member lines by default | Module/package scope is unbounded or relationships are inferred from names only |

Unsupported in this version: Gantt, pie, journey, timeline, mindmap, Git graph,
C4, quadrant, requirement, packet, sankey, and arbitrary Mermaid diagrams.

## Evidence Catalogs

### Architecture

Use packages, modules, apps, services, infra, containers, build/workspace
dependencies, imports between packages, HTTP/RPC clients, queues, database
access, and edge bindings. Do not turn individual files into architecture nodes
unless the project is genuinely source-only and tiny.

### Interaction

Look for the bounded entrypoint first:

- Web/API: routes, controllers, middleware, handlers, RPC procedure files.
- Jobs/commands: CLI entrypoints, scheduled handlers, queue consumers, workers.
- Clients/messages: service clients, fetch/RPC calls, event emitters, queue
  producers, callbacks.

Sequence messages must be ordered from code reads. Participants are real
actors, services, modules, or external systems found in code.

### Data Model

Look for schema evidence:

- SQL migrations, DDL files, `schema.sql`.
- ORM/entity files such as Prisma, Drizzle, ActiveRecord, Ecto, SQLAlchemy,
  Django models, TypeORM, Entity Framework, Rails models.
- Foreign keys, explicit references, join tables, association declarations.

Exclude inferred relationships by default. If the user asks for likely edges,
label them visibly and record why they are inferred.

### State Model

Look for explicit lifecycle evidence:

- Enum/status constants and allowed values.
- Reducers, transition maps, workflow definitions, state machines.
- Guard functions, command handlers, transition side effects.

Transitions need source and trigger evidence. If Mermaid cannot distinguish an
inferred transition visually, label it with `inferred:`.

### Type Structure

Keep scope bounded to one module/package unless the user asks otherwise. Read:

- Classes, interfaces, protocols, structs, traits, type aliases.
- Inheritance and implementation declarations.
- Composition fields and public method groups.

Exclude inferred type relationships by default. If likely/inferred edges are
requested, label them visibly.

## Provenance Conventions

Represent provenance:

- Solid relationship/message: read-from-code fact.
- Dashed relationship/message: inference only where the Mermaid type supports a
  clean weak/dashed form.
- Annotated inference: use labels such as `inferred:` when Mermaid has no clean
  dashed/weak relationship syntax.
- Edge/message labels: name protocol, import, binding, trigger, method, or
  source fact briefly.
- Comments: use `%% source: path/to/file` near relevant parts when helpful.
- Metadata: rely on `.index.json` for full source file lists and coverage.

Use `subgraph` for grouping when top-level nodes exceed the cap. If grouping
would hide important structure, split into a drill-down diagram and mark
metadata `split: true`.
