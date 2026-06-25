---
name: anchor-vet
description: Evidence-gated diff review for PRs, branches, commit ranges, staged code changes, and merge readiness checks. Use when an AI reviewer must review a concrete git-anchored diff, judge whether code is safe to merge, inspect a PR URL or branch, cross-examine PR or commit claims, account blast radius, or render approve/request-changes/blocked verdicts. Do not use for design-only review, whole-codebase audits, bug fixing, or code authoring without a git diff under judgment.
---

# anchor-vet

Force the skipped move in code review: prove the reviewed diff's scope, blast
radius, claims, findings, and verdict are anchored to git evidence.

## Trigger Check

Use this skill only when there is a concrete code change to judge: a PR, branch,
commit range, or staged review target.

Boundary test: can you name a `base...head` pair of git states whose difference
is the artifact under judgment? If yes, use `anchor-vet`. If no, get the branch or ref
first; do not review pasted diffs or prose descriptions.

Do not use `anchor-vet` for design feedback without a diff, whole-codebase audits,
feature implementation, bug fixing, formatting-only tasks, or document review.
If the user asks you to fix findings too, render the review verdict first; fixes
are a separate task, and behavioral fixes route to `anchor-repro`.

## Forced Procedure

1. **Anchor the scope.** Check out the reviewed head locally. Capture external
   claims before `init`: for PRs, save the title/body from `gh pr view
   --json title,body --jq '.title + "\n\n" + (.body // "")'` to a claims file.
   Run:
   `python3 skills/anchor-vet/scripts/vet_gate.py init --project <root> --review <slug> --base <ref> --head <ref> --claims-file <path>`
   or, only when there are genuinely no external claims, `--no-claims`.
2. **Read every hunk.** Inspect the full diff and every hunk in `scope.json`.
   If the diff is too large to read honestly, stop and propose a split.
3. **Walk the blast radius.** For each candidate symbol, read the references
   found by the gate. Record examined refs with `effect` and a one-line `note`.
   Examined means you opened/read the reference and judged how the change
   affects it.
4. **Account weak or symbolless hunks.** For weak/symbolless hunks, use a
   verified `enclosingUnit` when a named unit exists, or `file-level` with a
   reason only for genuinely unit-less code/config/prose.
5. **Cross-examine claims.** Disposition every anchored claim id from
   `scope.json`: `verified`, `contradicted`, `not-verifiable-from-diff`, or
   `non-claim`. Verified/contradicted claims need citations.
6. **Hunt findings with severity honesty.** Use only `blocking`, `concern`, and
   `nit`. Cite findings. A `blocking` finding needs R2 cited evidence or an R3
   repro probe. When a behavioral assertion is cheap to demonstrate, record a
   failing `anchor-repro` ledger entry against the reviewed head and cite it with
   `entrySha256`.
7. **Write and check `review.json`.** Run:
   `python3 skills/anchor-vet/scripts/vet_gate.py check --project <root> --review <slug>`.
   Fix check failures by doing the missing review work, not by padding JSON.
8. **Render the verdict through the gate.** Run:
   `python3 skills/anchor-vet/scripts/vet_gate.py close --project <root> --review <slug> --verdict approve|request-changes|blocked`.
   Report the verdict, cite `verdict.json`, and name each finding's evidence
   rung.

## Script Contract

Artifacts are written under the target project:

```text
.techne/review/<slug>/
  scope.json    # computed by init
  review.json   # authored by the reviewer
  report.json   # computed by check
  verdict.json  # computed by close
```

Generated `.techne/` output belongs to target projects. Do not commit it to this
repository.

Review skeleton:

```json
{
  "schema": "techne.vet/1",
  "symbols": [
    {
      "id": "s-...",
      "symbol": "changedName",
      "disposition": "reviewed",
      "refs": [
        {
          "file": "src/caller.py",
          "line": 42,
          "effect": "unaffected",
          "note": "caller passes the same contract"
        }
      ]
    }
  ],
  "hunks": [],
  "claims": [
    {
      "ids": ["c-..."],
      "disposition": "verified",
      "citations": [{"file": "src/change.py", "line": 10}]
    }
  ],
  "findings": [],
  "testsAcknowledgment": "No tests changed; the diff is docs-only or existing coverage is enough because ..."
}
```

Use `reference.md` for the full JSON schema, rubrics, exclusions, weak spots,
and probe guidance.

## Stop Conditions

- Stop if no git-anchored `base...head` diff is available.
- Stop if `init` refuses because of dirty worktree, missing merge base, or head
  mismatch; fix the setup or record `blocked`.
- Stop if the review is too large to read in full; propose a split instead of
  sampling silently.
- Stop before `approve` if refs, hunks, claims, or test acknowledgment remain
  unaccounted.
- If head moves mid-review, do not fight the tool. Close the old slug as
  `blocked --reason ...` or leave it, then start a new slug for the new head.
