---
name: viz
description: Draw a faithful architecture or structure diagram of a real codebase or project by scanning the actual repo, never guessing. Use for system architecture, request lifecycle, data model, state transitions, type structure, draw the architecture, map this project, 画架构图.
---

# viz

Investigate by diagramming. The diagram is the byproduct; the value is forcing
real investigation before drawing.

## Forced Procedure

1. **Route the request.** Choose one `diagramKind` from the table below. If the
   user's intent fits multiple kinds, ask one short clarification instead of
   guessing.
2. **Find evidence for that kind.** For `architecture`, enumerate roots,
   manifests, workspace/build/native/container/edge/infra/source-only signals.
   For other kinds, find the bounded entrypoint, schema, state enum, workflow,
   or module/type namespace before drawing.
3. **Classify shape or scope.** For `architecture`, state one project shape and
   cite evidence: `single-frontend`, `single-backend`, `coupled-fullstack`,
   `monorepo`, `library`, `native`, `native+edge`, `source-only code`, or
   `non-code`. For other kinds, state the bounded scope and the files that prove
   it.
4. **Apply the non-code decision.** Never declare non-code only because manifests
   are absent. First scan roots; then run a bounded source-extension/code-signal
   scan. If both are absent, or docs/vault signals clearly dominate, do not
   fabricate a code diagram. Draw the real top-level structure or ask what the
   user wants.
5. **Draw only evidenced relationships.** Use the evidence contract for the
   selected kind. Every node, participant, entity, state, type, and edge/message
   must come from a file read.
6. **Enforce complexity gates.** Keep `architecture` at 12-15 top-level nodes by
   default. For other kinds, use the validator's participant/message,
   entity/relationship, state/transition, or type/member limits. Split into
   drill-down diagrams when needed.
7. **Mark provenance.** Add render-neutral comments for every element before
   storing:
   `%% techne:source <elementRef> <path>[#<symbol>]` or, for relationship-like
   elements only, `%% techne:inferred <relationshipRef> <reason>`. Entity-like
   elements always need verified `techne:source`; relationship-like elements
   need file+symbol proof unless explicitly inferred with sourced endpoints.
   Use `actor` for human sequence participants so the actor path-only allowance
   is mechanically scoped. Solid relationships mean read-from-code. Dashed or
   labeled relationships mean inference only where the selected Mermaid type
   supports it.
8. **Emit, validate, store, build viewer, open when interactive.** Write Mermaid
   source first, validate it, store it with `scripts/store_viz.py`, always build
   the self-contained viewer, and only open it when the session is interactive.

## Diagram Routing

| User intent | `diagramKind` | Mermaid `type` | Evidence focus |
| --- | --- | --- | --- |
| Project architecture, module/service/package topology | `architecture` | `flowchart` / `graph` | Manifests, workspaces, imports, services, bindings, infra edges. |
| Request lifecycle, command/job flow, actor conversation | `interaction` | `sequenceDiagram` | Entrypoint, ordered calls/messages, handlers, clients, queues. |
| Tables, entities, persistence relationships | `data-model` | `erDiagram` | Schema, migrations, ORM/entity declarations, foreign keys, associations. |
| Status/order/task/review lifecycle | `state-model` | `stateDiagram-v2` / `stateDiagram` | Status constants, state machines, reducers, guards, transition handlers. |
| Classes, interfaces, structs, protocols, bounded type structure | `type-structure` | `classDiagram` | Type declarations, inheritance, implementation, composition, public method groups. |

Examples:

- "map this project" -> `architecture`.
- "show how login request flows" -> `interaction`.
- "draw the database relationships" -> `data-model`.
- "how does order status change" -> `state-model`.
- "show the public types in this module" -> `type-structure`.

## Script Usage

- Validate Mermaid and altitude:
  `node skills/viz/scripts/validate-mermaid.mjs diagram.md --project /path/to/project --max-nodes 15`
- Store a diagram in a target project:
  `python3 skills/viz/scripts/store_viz.py --project /path/to/project --name login-flow --title "Login flow" --diagram diagram.md --shape monorepo`
- Build the self-contained viewer, opening it only when interactive:
  `python3 skills/viz/scripts/build_viewer.py --project /path/to/project --open`

The validator expects `mermaid@11.15.0` and `jsdom` to be installed in one of
these places: `TECHNE_VIZ_NODE_MODULES`, `skills/viz/scripts/node_modules`, the
current working directory, or an ancestor directory.

## Stop Conditions

- Stop and ask if you cannot inspect the project files.
- Stop and ask if the requested diagram kind is ambiguous.
- Stop before drawing unsupported architecture for a non-code project.
- Stop before drawing a non-architecture diagram without a bounded entrypoint,
  schema, status lifecycle, or module/type scope.
- Stop before storing a diagram that fails syntax validation, provenance
  validation, or a complexity gate.
- Do not create `.techne/` content inside this repository while authoring the
  skill itself.
