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
