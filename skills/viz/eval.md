# viz Eval

This is the empirical acceptance methodology. Codex only runs mechanical checks;
Claude and the maintainer run the skill-level evaluation in an authenticated
Claude context.

## Test Set

Use four maintainer-private local repos:

- A web+edge workspace.
- A JS workspace app.
- A non-code notes vault.
- A native+edge hybrid, especially Swift/Xcode.

Do not commit private paths, generated diagrams, or `.techne/` output.

## Baseline

Ask the model to draw the architecture without `viz`.

Record:

- Fabricated nodes.
- Fabricated edges.
- Incorrect project shape.
- Diagram readability.
- Render/validation failures.

## With Skill

Invoke `viz` on the same repos. The skill must:

- Classify shape with evidence.
- Avoid fabricating nodes or edges.
- Use the non-code branch for the notes vault.
- Avoid false-refusing manifest-less code.
- Keep top-level altitude readable.
- Validate and store the diagram.

## Metrics

- Fabrication rate: target approximately zero fabricated nodes/edges.
- Shape correctness: project classification matches evidence.
- Altitude: top-level nodes stay within cap or are grouped/split.
- Renderability: Mermaid validates and viewer renders.
- Improvement: with-`viz` beats baseline on at least one metric.

## Pass Bar

Pass only if with-`viz` has approximately zero fabrications, correct shape,
readable altitude, successful validation/rendering, visible improvement over
baseline on at least one metric, and passes the non-code refuse-to-fabricate
case without false-refusing source-only code.
