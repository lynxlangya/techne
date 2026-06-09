---
name: viz
description: Draw a faithful architecture or structure diagram of a real codebase or project by scanning the actual repo, never guessing. Use for system architecture, draw the architecture, map this project, 画架构图.
---

# viz

Investigate by diagramming. The diagram is the byproduct; the value is forcing
real investigation before drawing.

## Forced Procedure

1. **Find roots.** Enumerate top-level manifest, workspace, build, native,
   container, edge, infra, and source-only signals before deciding shape. Use the
   catalog in [reference.md](reference.md) when the project is not obvious.
2. **Classify shape.** State one classification and cite evidence:
   `single-frontend`, `single-backend`, `coupled-fullstack`, `monorepo`,
   `library`, `native`, `native+edge`, `source-only code`, or `non-code`.
3. **Apply the non-code decision.** Never declare non-code only because manifests
   are absent. First scan roots; then run a bounded source-extension/code-signal
   scan. If both are absent, or docs/vault signals clearly dominate, do not
   fabricate an architecture. Draw the real top-level structure or ask what the
   user wants. If source signals exist without manifests, classify as
   `source-only code` and draw cautiously from real files.
4. **Choose top-level components.** Use real packages, modules, apps, services,
   and infrastructure units. Do not turn individual files into architecture
   nodes unless the project is genuinely source-only and tiny.
5. **Draw real edges.** Every edge must come from a file read: imports between
   packages, build/workspace dependencies, HTTP/RPC clients, compose networks,
   queues, database access, or edge bindings. No unsupported edges.
6. **Enforce altitude.** Target 12-15 top-level nodes. If there are more, group
   them in Mermaid `subgraph` blocks or create a drill-down diagram. The
   validator/store helper has a node-count gate; do not route around it.
7. **Mark provenance.** Solid Mermaid edges mean read-from-code. Dashed edges
   (`-. infer .->`) mean inference. Record sources in stored metadata and, when
   useful, in comments near the diagram.
8. **Emit, validate, store, build viewer, open when interactive.** Write Mermaid
   source first, validate it, store it with `scripts/store_viz.py`, always build
   the self-contained viewer, and only open it when the session is interactive.

## Script Usage

- Validate Mermaid and altitude:
  `node skills/viz/scripts/validate-mermaid.mjs diagram.md --max-nodes 15`
- Store a diagram in a target project:
  `python3 skills/viz/scripts/store_viz.py --project /path/to/project --name architecture --title "Architecture" --diagram diagram.md --shape monorepo --type flowchart --source src/app.ts --coverage grounded --node-count 8`
- Build the self-contained viewer, opening it only when interactive:
  `python3 skills/viz/scripts/build_viewer.py --project /path/to/project --open`

The validator expects `mermaid@11.15.0` and `jsdom` to be installed in one of
these places: `TECHNE_VIZ_NODE_MODULES`, `skills/viz/scripts/node_modules`, the
current working directory, or an ancestor directory.

## Stop Conditions

- Stop and ask if you cannot inspect the project files.
- Stop before drawing unsupported architecture for a non-code project.
- Stop before storing a diagram that fails syntax validation or the altitude
  gate.
- Do not create `.techne/` content inside this repository while authoring the
  skill itself.
