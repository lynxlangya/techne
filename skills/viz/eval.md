# viz Eval

This is the empirical acceptance methodology. Codex only runs mechanical checks;
Claude and the maintainer run the skill-level evaluation in an authenticated
Claude context.

## Test Set

Use maintainer-private local repos or bounded areas that cover the supported
diagram kinds where feasible:

- Architecture: a web+edge workspace, JS workspace app, or native+edge hybrid.
- Interaction: one request, command, job, login, sync, or async flow.
- Data model: one schema, migration set, or ORM/entity area.
- State model: one status lifecycle, reducer, workflow, or state machine.
- Type structure: one bounded module/package with public types.
- Non-code guard: a notes/docs vault.

Do not commit private paths, generated diagrams, or `.techne/` output.

## Baseline

Ask the model to draw the requested diagram without `viz`.

Record:

- Wrong diagram-kind choice.
- Fabricated nodes.
- Fabricated edges, messages, relationships, transitions, or type links.
- Incorrect project shape.
- Incorrect temporal order, schema relationship, lifecycle transition, or type
  relationship.
- Diagram readability.
- Render/validation failures.

## With Skill

Invoke `viz` on the same repos. The skill must:

- Route to the correct `diagramKind`, or ask one clarification when ambiguous.
- Classify shape with evidence.
- State bounded scope for non-architecture diagrams.
- Avoid fabricating nodes, participants, entities, states, types, edges,
  messages, relationships, or transitions.
- Use the non-code branch for the notes vault.
- Avoid false-refusing manifest-less code.
- Keep complexity within the relevant gate or split the diagram.
- Validate and store the diagram.

## Metrics

- Routing correctness: selected `diagramKind` matches user intent and evidence.
- Fabrication rate: target approximately zero fabricated diagram elements.
- Shape correctness: project classification matches evidence.
- Architecture: modules/services/boundaries match source evidence.
- Interaction: message order matches the code path.
- Data model: entities and relationships match schema evidence.
- State model: states, transitions, and triggers match code evidence.
- Type structure: inheritance, implementation, composition, and public method
  groups match declarations.
- Complexity: diagrams stay within cap or split/narrow scope.
- Renderability: Mermaid validates and viewer renders.
- Improvement: with-`viz` beats baseline on at least one metric.

## Pass Bar

Pass only if with-`viz` has approximately zero fabrications, correct shape,
correct diagram-kind routing, readable complexity, successful
validation/rendering, visible improvement over baseline on at least one metric,
and passes the non-code refuse-to-fabricate case without false-refusing
source-only code.

Codex can run only the mechanical checks. Claude and the maintainer must judge
whether the diagrams are faithful to private/local source evidence.

## Mechanical Provenance Fixtures

Run these with temporary fixture projects only. Do not commit generated
`.techne/` output.

| # | Fixture | Expected |
| --- | --- | --- |
| A | Fabricated diagram with `techne:source` paths that do not exist | Validator exit 1 with missing paths; store refuses. |
| B | Real paths but fabricated symbols | Validator exit 1 with `symbol_not_found`. |
| C | Valid diagram with zero annotations | Validator exit 1 with uncovered elements. |
| D | Small real fixture project, every element annotated with real path+symbol | Validator exit 0; store succeeds; index has computed coverage and derived `sourceFiles`. |
| E | Fixture D plus one `techne:inferred` edge whose endpoints are sourced | Passes with `inferred: 1` in coverage. |
| F | Annotation references an element ID not present in the diagram | Validator exit 1. |
| G | Path escapes project root | Validator exit 1. |
| H | Valid five-kind fixtures without `--project` | Still validate with `provenance.verified: false`. |
| I | All elements marked only as `techne:inferred` | Validator exit 1 because entity-like elements require source. |
| J | Inferred edge whose endpoint lacks a verified source | Validator exit 1. |
| K | Architecture node cites an existing directory | Passes as `pathVerified`. |
| L | Architecture edge cites a directory | Validator exit 1. |
| M | Non-architecture element cites a directory | Validator exit 1. |
| N | Store called with stale `--node-count` | Rejected as an unknown argument. |
| O | `node` or validator dependencies missing | Store exits non-zero with an actionable message. |
| P | Unknown `%% techne:*` directive | Validator exit 1. |
| Q | Every element cites existing `README.md` path-only | Validator exit 1 because relationship-like elements require `#symbol`. |
| R | Relationship-like `techne:source` without `#symbol` | Validator exit 1. |
| S | `actor User` cites a real route/handler file path-only | Passes as `pathVerified`. |
| T | `participant BillingService` cites a broad real file without symbol | Validator exit 1. |
| U | Store called with stale `--diagram-kind` or `--type` | Rejected as unknown arguments. |
| V | `sequenceDiagram` stored successfully | Index records `diagramKind: interaction` and `type: sequenceDiagram` from validator output. |
