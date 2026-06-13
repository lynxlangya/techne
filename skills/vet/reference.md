# vet Reference

Load this file when writing `review.json`, interpreting `report.json`, or
deciding whether a finding, exclusion, claim disposition, or verdict is honest.

## JSON Contract

`vet_gate.py` writes target-project artifacts under `.techne/review/<slug>/`.

`scope.json` is computed by `init` and contains:

- `baseSha`, `headSha`, and `mergeBaseSha`.
- `changedFiles`, `hunks`, `candidateSymbols`, `testsDelta`.
- `claims`, including external claims and computed commit-message claims.
- `heuristics`, including path/test/definition/masking/trailer allowlists.

`review.json` is authored by the reviewer:

- `symbols`: dispositions for every `candidateSymbols[].id`.
- `hunks`: dispositions for weak or symbolless hunks.
- `pathExclusions`: generated/vendor/out-of-scope prefixes with reasons.
- `claims`: dispositions referencing claim ids from `scope.json`.
- `findings`: cited findings with `blocking`, `concern`, or `nit` severity.
- `testsAcknowledgment`: required when production changed and tests did not.

`report.json` is computed by `check`:

- citation verification and `inDiff` / `context` tags.
- raw and bounded xref counts.
- unaccounted refs and hunks.
- evidence rungs and admissible verdicts.

`verdict.json` is computed by `close`:

- final verdict and finish state.
- `blastRadiusComplete`.
- finding/rung summary.
- artifact hashes and probe ledger hashes.

## Review JSON Fields

Symbol dispositions:

```json
{
  "id": "s-...",
  "symbol": "run",
  "disposition": "reviewed",
  "refs": [
    {"file": "src/api.py", "line": 8, "effect": "affected", "note": "route calls run()"}
  ],
  "boundedPlan": [
    {"pattern": ".run(", "paths": ["src"], "rationale": "call-shape search for method refs"}
  ],
  "pathExclusions": [
    {"prefix": "generated", "reason": "generated fixture corpus"}
  ]
}
```

Allowed `effect` values are `unaffected`, `affected`, and `unknown`.

Weak or symbolless hunk dispositions:

```json
{"hunkId": "h1", "unit": "enclosingUnit", "symbol": "target", "definingFile": "app.py", "definingLine": 4}
{"hunkId": "h2", "unit": "file-level", "reason": "top-level config file has no named code unit"}
```

Claim dispositions:

```json
{"ids": ["c-..."], "disposition": "verified", "citations": [{"file": "app.py", "line": 10}]}
{"ids": ["c-...", "c-..."], "disposition": "non-claim"}
{"ids": ["c-..."], "disposition": "not-verifiable-from-diff"}
```

Finding with a repro probe:

```json
{
  "id": "F1",
  "severity": "blocking",
  "title": "Cache writes race with reads",
  "claim": "The new cache path can return stale values.",
  "citations": [{"file": "cache.py", "line": 44}],
  "probe": {
    "ledger": ".techne/repro/cache-race.jsonl",
    "entryIndex": 0,
    "entrySha256": "<sha256 of exact JSONL line>",
    "note": "Probe fails on the reviewed head."
  }
}
```

## Severity Rubric

`blocking`: should not merge as-is. Use for functional regressions, data loss,
security/privacy issues, broken builds/tests, contract breaks, migration
hazards, or missing safety checks.

`concern`: real risk or defect worth a decision, but not clearly merge-blocking
alone. Use for ambiguous compatibility risk, missing edge-case coverage, or
maintainability debt tied to the diff.

`nit`: polish. Use only for small clarity, naming, or formatting notes that do
not affect merge safety.

Severity honesty matters. Do not soften a real defect to `concern` just because
you are unsure how to phrase it politely.

## Evidence Rungs

The script computes finding rungs:

- `R3 probe-demonstrated`: a valid failing `repro` JSONL entry at
  `scope.headSha`, with matching `entrySha256`.
- `R2 cited-verified`: at least one citation verifies against the reviewed tree.
- `R1 unanchored`: no verified citation or valid probe.

`blocking` findings must reach R2 or R3. R1 `concern` / `nit` findings are
allowed but visible.

`vet` reads only these `techne.repro/1` fields from a ledger entry:
`type`, `exit`, `timedOut`, `expectMatched`, and `git.head`. It never imports or
executes `repro_ledger.py`.

## Definition And Unit Binding

Definition matching runs on lexically masked source. Masked comments and string
literals cannot create a unit or refuse an `enclosingUnit`.

Masking support in v1:

- Python `.py`: stdlib `tokenize`, including f-string and t-string token
  families when the host Python exposes them.
- JS/TS `.js`, `.jsx`, `.ts`, `.tsx`, `.mjs`, `.cjs`: `//`, `/* */`,
  single/double strings, and template literals. Template interpolation marks the
  affected lines weak.
- C-like `.c`, `.h`, `.cc`, `.cpp`, `.cxx`, `.hpp`, `.hh`, `.java`, `.kt`,
  `.kts`, `.go`, `.rs`, `.swift`, `.m`, `.mm`, `.cs`, `.fs`, `.vb`, `.php`:
  normal line comments, block comments, and single/double strings only.
- Raw strings, text blocks, nested block comments, regex-literal ambiguity,
  unterminated constructs, and unknown extensions mark affected hunks weak.

Python uses an indentation stack. For brace syntaxes, the implementation uses a
single top-to-changed-line brace-depth scan:

- Same-line definitions push when `{` appears before any `;`.
- Allman definitions are held pending and pushed by the next line whose first
  non-space token is `{`.
- Prototypes and forward declarations ending in `;` before any `{` are ignored.
- One-line `definition { body }` forms are active for a change on that line, and
  then pop when the closing brace is passed.
- Removed-side definitions from deleted lines enter `candidateSymbols` with
  source `removed-definition`; their refs are searched in the reviewed head so
  stale callers/imports remain accountable after deletions or renames.

This resolves the round-5 brace association question for v1. If the scanner is
not confident, the hunk is `unitBinding: weak` and approval needs an explicit
verified hunk disposition.

## Claim Normalization

Claim ids are `c-<sha256(source + NUL + normalized text)[:12]>`.

Normalization runs in this exact order:

1. CRLF -> LF.
2. Strip trailing whitespace per line.
3. Trim leading/trailing blank lines.
4. No internal whitespace collapsing.

Duplicate `source + normalized text` pairs dedupe to one id.

## Trailer Allowlist

Git trailer syntax is used only to locate trailer-shaped lines. Auto-exemption
uses this exact identity/attribution allowlist, case-insensitive:

- `Signed-off-by`
- `Co-authored-by`
- `Reviewed-by`
- `Acked-by`
- `Tested-by`
- `Reported-by`
- `Suggested-by`
- `Helped-by`
- `Cc`

No patterns are allowed. `Caused-by` does not ride a `*-by` rule. `Fixes`,
`Security`, `Regression`, `Performance`, `Tests`, `Deploy-note`, and project
custom trailers are anchored as claims.

All nine keys remain in v1 because each is identity/attribution metadata rather
than a behavior claim. No extra key is added because project-custom trailers are
the dangerous self-selection surface this gate is closing.

## Exclusions

Legitimate path exclusions:

- vendored dependency trees.
- generated bundles or codegen output.
- lockfiles/binaries where semantic review is not possible.
- fixtures or snapshots unrelated to live behavior.

Not legitimate:

- live code that is tedious to inspect.
- tests merely because they are noisy.
- source subtrees omitted by a bounded plan without reason.

For common tokens (`run`, `get`, `set`), use `boundedPlan` rather than a bare
`too-common-token` exclusion. The script executes bounded searches itself and
keeps raw-vs-bounded visibility.

## Known Weak Spots

- Textual xref misses dynamic dispatch, reflection, string-built names, macro
  expansion, and semantic aliases.
- A bounded plan can still miss call sites inside a scanned file if the pattern
  is badly chosen; this is a Goodhart-watch item.
- Unit detection is heuristic and textual, not AST/LSP-backed.
- Rust lifetime syntax can still make the light scanner fail closed to weak on
  ordinary code; v1 accepts the friction rather than risking false bindings.
- Windows is out of v1 scope; the script is POSIX-only.
