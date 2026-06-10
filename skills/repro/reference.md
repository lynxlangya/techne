# repro Reference

`repro` turns a debugging promise into a mechanical gate: fail first, fix, then
pass the same probe identity.

## Probe Identity

The ledger pairs runs by executed shape, not by display text.

Argv mode:

```json
{
  "mode": "argv",
  "argv": ["python3", "check.py", "a", "b c"],
  "cwd": ".",
  "timeoutSec": 600
}
```

Shell mode:

```json
{
  "mode": "shell",
  "shellCommand": "VAR=1 npm test",
  "cwd": ".",
  "timeoutSec": 600
}
```

All fields must match exactly for verification. `displayCommand` is only for
humans and is never used for pairing.

Inherited environment is excluded from v1 identity. If the probe depends on an
environment variable, encode it in shell form so it becomes part of
`shellCommand`. Pass the shell command as one quoted token after `--`; tokens
after `--` are joined with spaces before `sh -c`:

```bash
python3 skills/repro/scripts/repro_ledger.py run \
  --project /repo --bug locale-sort --shell --expect "wrong order" -- \
  'LC_ALL=C npm test'
```

## Probe Catalog

| Ecosystem | Canonical failing-probe forms |
| --- | --- |
| Python | Targeted `pytest` / `unittest` node; one-off `python -c` or script with `assert`. |
| JS/TS | Targeted `vitest`, `jest`, `node --test`; one-off Node script. |
| Frontend logic | Same unit runners as JS/TS. |
| Frontend visual/interaction | Scripted browser probe asserting DOM or behavior; purely visual cases use `--no-stable-expect` only when text cannot anchor the symptom. |
| Rust | Targeted `cargo test`; one-off binary or `#[test]`. |
| Go | `go test -run <Name>`. |
| Swift / iOS / macOS | `swift test`, `xcodebuild test -destination <simulator>`, or direct CLI binaries. |
| Shell / CLI tools | The command itself plus exit code; `bats` where present. |
| HTTP services | `curl` wrapped in a small assertion script checking status and body. |
| Data / DB bugs | Scripted query plus assertion. |

Package-local probes should use `--cwd <package-dir>`. Avoid hiding the working
directory inside `cd ... &&` because cwd is a first-class identity field.

## Strength Ladder

Name the rung in the final report. The ledger does not store this field because
it records executed facts, not self-assessed quality.

- **S1**: failing case added to the repo's committed test suite.
- **S2**: one-off scripted assertion, such as an uncommitted test file or script.
- **S3**: ad-hoc command whose exit code carries the assertion.
- **S4**: `mark-unreproduced` with recorded reason.

Any rung can pass the mechanical gate. Weak rungs must be visible, not hidden.

## Stable Expect Selection

Use the smallest stable text that proves the run reached the reported symptom.

Good anchors:

- Error class plus stable message.
- Assertion label.
- HTTP status plus stable response field.
- DOM text expected by a browser assertion.

Avoid:

- Heap addresses.
- PIDs.
- Timestamps.
- Temp directories.
- Wrapped line fragments.
- Locale- or terminal-width-dependent formatting.

The script strips ANSI CSI/OSC escape sequences and normalizes CRLF/lone CR to
LF before matching. Wider terminal cursor-control behavior is a v1 coverage gap.

## Hangs And Timeouts

A timeout counts as a failing observation. Verification requires the identical
identity completing with exit 0 inside the same timeout. The script runs probes
in a POSIX session/process group and kills the group on timeout so spawned
children do not outlive the probe.

If a probe is flaky, strengthen it before trusting it. v1 does not implement
N-run statistical handling.

## Unreproduced Path

Use `mark-unreproduced` only when honest reproduction cannot be obtained:

- Prior anchored attempt: at least one run with non-empty `--expect`.
- `--no-probe-possible`: nothing can be run at all.
- `--no-stable-expect`: runs are possible, but no stable symptom text exists.

Do not use `--no-stable-expect` when stable textual output exists. The final
report must say the fix is speculative.

## Scope

`repro_ledger.py` is Python 3 stdlib and POSIX-only for v1: macOS and Linux
developer environments. Windows support is a recorded gap because shell kind and
timeout-tree cleanup need separate semantics.
