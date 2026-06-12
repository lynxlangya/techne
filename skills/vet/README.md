# vet

`vet` is an evidence-gated diff review skill. It makes an AI reviewer anchor a
PR or branch to git, account the blast radius of changed symbols, verify claims
and citations, and render only admissible verdicts.

Use it for:

- PR review.
- Branch or commit-range review.
- Merge-readiness checks.
- "Is this safe to approve?" questions over a concrete git diff.

Do not use it for design-only review, whole-codebase audits, or bug fixing.

## Quick Start

Capture PR claims first:

```bash
gh pr view 123 --json title,body --jq '.title + "\n\n" + (.body // "")' > /tmp/pr-123-claims.txt
```

Anchor the review:

```bash
python3 skills/vet/scripts/vet_gate.py init \
  --project /path/to/project \
  --review pr-123 \
  --base origin/main \
  --head HEAD \
  --claims-file /tmp/pr-123-claims.txt
```

Write `.techne/review/pr-123/review.json`, then check and close:

```bash
python3 skills/vet/scripts/vet_gate.py check --project /path/to/project --review pr-123
python3 skills/vet/scripts/vet_gate.py close --project /path/to/project --review pr-123 --verdict request-changes
```

Generated `.techne/` output belongs to the target project and should not be
committed to this repository.

## Verdicts

- `approve`: all refs, hunks, claims, and test acknowledgments are accounted,
  with zero blocking findings.
- `request-changes`: at least one `blocking` or `concern` finding. Early stop is
  allowed only with a `blocking` R2/R3 finding; `verdict.json` records
  `blastRadiusComplete: false`.
- `blocked`: the review cannot honestly finish. Requires `--reason`.

See [reference.md](reference.md) for the JSON schema and [eval.md](eval.md) for
fixtures and empirical acceptance.
