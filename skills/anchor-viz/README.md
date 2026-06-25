# anchor-viz

`anchor-viz` is a techne skill for investigating a real codebase by diagramming it. It
does not draw from intuition alone. It scans the repository, chooses the right
diagram kind, cites the evidence it read, validates the Mermaid source, stores
the diagram in the target project, and builds a local file-based viewer.

Use it when a visual map will make a codebase easier to understand, review, or
debug.

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

If you intentionally want only `anchor-viz`, install the single skill:

```bash
npx skills add lynxlangya/techne --skill anchor-viz -a codex -g -y
npx skills update anchor-viz -g -y
```

Other hosts and fallback commands are documented in the root
[INSTALL.md](../../INSTALL.md).

## Quick Start

Open your target project in the agent, then invoke `anchor-viz` with a bounded request.

Claude Code:

```text
/techne:anchor-viz
Scan this repository and draw an architecture diagram. Identify the project
shape, cite the files you read, keep the diagram within 12-15 top-level nodes,
validate it, store it, build the local viewer, and open it when ready.
```

Codex or another Agent Skills host:

```text
Use the anchor-viz skill. Scan this repository and draw an architecture diagram.
Identify the project shape, cite the files you read, keep the diagram within
12-15 top-level nodes, validate it, store it, and build the local viewer.
```

A good run should show:

- The selected `diagramKind`.
- The repository shape or bounded scope.
- The evidence files read before drawing.
- Diagram titles and labels in the user's language, while code identifiers,
  paths, symbols, package names, and established technical terms stay
  source-native.
- Mermaid source with `%% techne:source` / `%% techne:inferred`
  provenance comments that passes validation.
- Stored output under `.techne/viz/` in the target project.
- A self-contained `.techne/viz/index.html` viewer.

Do not commit `.techne/` output. `store_viz.py` adds `.techne/` to the target
project's `.gitignore` when needed.

## Diagram Kinds

| Ask for | `diagramKind` | Mermaid type | Best for |
| --- | --- | --- | --- |
| Project/module/service topology | `architecture` | `flowchart` / `graph` | Repos, apps, packages, services, infra edges. |
| Request, command, job, or actor flow | `interaction` | `sequenceDiagram` | Login, sync, queue processing, CLI commands. |
| Tables, entities, and persistence relationships | `data-model` | `erDiagram` | SQL migrations, ORM models, schemas. |
| Status or workflow lifecycle | `state-model` | `stateDiagram-v2` / `stateDiagram` | Order states, review flows, reducers, state machines. |
| Classes, interfaces, protocols, structs, or public types | `type-structure` | `classDiagram` | Bounded module/type structure. |

If your request fits multiple kinds, `anchor-viz` should ask one clarification instead
of guessing.

## Language Behavior

`anchor-viz` follows the user's language for human-facing text. Ask in English and the
diagram title, display labels, and short explanations should be English. Ask in
Chinese and those user-facing labels should be Chinese. Code-facing evidence
stays as written in the repository: paths, Mermaid IDs, symbols, class/function
names, package names, and terms such as API, SDK, CLI, HTTP, SwiftUI, AppKit,
and React are not forced through translation.

## Prompt Recipes

### macOS or Native App Architecture

```text
/techne:anchor-viz
Scan this macOS project and draw an architecture diagram. Focus on the Xcode or
SwiftPM roots, app entrypoint, targets, SwiftUI/AppKit boundary, persistence,
network layer, extensions, background work, and any edge/backend integration.
Only draw relationships backed by files you read.
```

### Frontend Architecture

```text
/techne:anchor-viz
Scan this frontend repository and draw an architecture diagram. Identify the
package manager, workspace shape, app entry, routes, state management, API
client, build/deploy config, and major feature modules. Keep it within 12-15
top-level nodes or split the diagram.
```

### Interaction Flow

```text
/techne:anchor-viz
Draw the login flow as an interaction diagram. Start from the route or page
entrypoint, then follow form submission, validation, state updates, API calls,
error handling, and navigation. Every participant and message must come from
files you read.
```

### Data Model

```text
/techne:anchor-viz
Draw the database relationships as a data-model diagram. Use migrations, schema
files, or ORM/entity declarations. Exclude relationships that are only guessed
from names.
```

### State Model

```text
/techne:anchor-viz
Draw the order status lifecycle as a state-model diagram. First find the status
enum, reducer, transition map, guard, workflow, or handler that proves each
transition.
```

### Type Structure

```text
/techne:anchor-viz
Draw the type structure for the Settings module as a classDiagram. Bound the
scope to public types, protocols/interfaces, view models, services, and direct
composition or inheritance relationships.
```

## Output

`anchor-viz` stores generated diagrams in the target project, not in techne itself:

```text
.techne/
  viz/
    <diagram>.md
    .index.json
    index.html
```

The viewer is a self-contained static HTML file. It should open from `file://`
without a local server or network request:

```bash
open .techne/viz/index.html
```

## Script Usage

Validate against a target project so provenance is enforced:

```bash
node skills/anchor-viz/scripts/validate-mermaid.mjs diagram.md --project /path/to/project --max-nodes 15
```

Store a diagram. `store_viz.py` runs the validator itself and derives
`diagramKind`, `type`, `sourceFiles`, `coverage`, and `nodeCount`; do not pass
self-reported source or coverage metadata:

```bash
python3 skills/anchor-viz/scripts/store_viz.py \
  --project /path/to/project \
  --name login-flow \
  --title "Login flow" \
  --diagram diagram.md \
  --shape monorepo
```

## What to Check

When testing `anchor-viz`, judge the run by evidence, not by visual polish alone:

- Did it pick the correct `diagramKind`?
- Did every node, participant, entity, state, type, edge, message, relationship,
  or transition have valid provenance?
- Did it avoid invented modules, messages, states, entities, or type links?
- Did it keep the diagram readable or split the scope?
- Did Mermaid validation pass?
- Did the viewer build and render?
- Did it avoid committing `.techne/` artifacts?

## Boundaries

`anchor-viz` intentionally does not support arbitrary Mermaid diagrams. Unsupported
families include Gantt, pie, journey, timeline, mindmap, Git graph, C4,
quadrant, requirement, packet, and Sankey diagrams.

It should stop or ask when:

- It cannot inspect the target project.
- The requested diagram kind is ambiguous.
- A non-architecture diagram has no bounded entrypoint, schema, lifecycle, or
  module/type scope.
- The repository is non-code and a code architecture diagram would be
  fabricated.
- The Mermaid source fails validation or exceeds the complexity gate.
