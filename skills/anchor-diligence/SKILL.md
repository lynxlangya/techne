---
name: anchor-diligence
description: Deep single-company public-equity research anchored to dated evidence snapshots and a fixed finance rubric. Use when a user asks for comprehensive research, a company deep dive, business/financial diligence, or global-alpha-style vertical analysis on one publicly listed equity identified by ticker or company name. Do not use for quick price quotes, order/trade drafting, investment verdicts, ETFs, bonds, crypto, macro-only topics, private companies, or multi-company comparison requests.
---

# anchor-diligence

Force the skipped move in company research: resolve the exact public equity,
fetch dated evidence before citing it, account every fixed diligence dimension,
and render a no-verdict dossier through a mechanical gate.

## Trigger Check

Use this skill for deep research on exactly one publicly listed equity, including
US, HK, A-share, and ADR subjects. The request should seek understanding rather
than a quick quote or trading action.

Self-eject for quick price lookups, order drafting or execution, buy/sell/hold
verdict requests, non-equity subjects, private companies, macro-only research,
ETFs, bonds, crypto, or multi-company comparison tasks. If identity is
ambiguous, refuse rather than guessing.

## Forced Procedure

1. **Resolve identity first.** Find an E2-admissible identity URL for the exact
   listing. Run:
   `python3 skills/anchor-diligence/scripts/diligence_gate.py init --project <dir> --ticker <ticker> --exchange <exchange> --legal-name <name> --identity-url <url>`.
   Add `--identifier <CIK|ISIN|LEI>` when available, `--issuer-host <host>`
   when the E2 identity source names the issuer's IR host, and
   `--analysis-as-of <YYYY-MM-DD>` for backtest mode.
2. **Fetch and save evidence.** For each relevant source, prefer a direct URL:
   `snapshot --url <url> --source-class <class>`. Use `snapshot --content-file
   <path> --source-locator <tool/query> --retrieval-method <method>` only for
   host-relayed evidence that has no fetchable URL. URL evidence can reach E2;
   host-relayed evidence is capped at `present-weak`.
3. **Author `research.json`.** Account all 12 rubric elements with `present`,
   `present-weak`, `gap`, or `no-material-link` for `ai-relevance` only. Use
   `claimItems` with citations into saved snapshots. Keep `plainSummary` to a
   one-line explanation of those grounded claims only.
4. **Check and repair.** Run:
   `python3 skills/anchor-diligence/scripts/diligence_gate.py check --project <dir> --ticker <ticker>`.
   Fix failures by fetching better evidence, narrowing claims, or downgrading
   the disposition. Do not pad JSON to appease the gate.
5. **Finalize.** Run:
   `python3 skills/anchor-diligence/scripts/diligence_gate.py finalize --project <dir> --ticker <ticker>`.
   Relay `report.md`, and surface warnings from `reportMeta.json`.

## Script Contract

Artifacts are written under the invocation directory:

```text
.techne/anchor-diligence/<TICKER>/
  scope.json
  events.jsonl
  sources/
    *.txt
    *.txt.meta.json
    manifest.json
  research.json
  report.json
  reportMeta.json
  report.md
```

Generated `.techne/` output belongs to the target project or working directory.
Do not commit it to this repository.

Minimal `research.json` shape:

```json
{
  "schema": "techne.diligence.research/1",
  "elements": {
    "ai-relevance": {
      "disposition": "no-material-link",
      "plainSummary": "The company disclosures checked do not show material AI revenue or products.",
      "claimItems": [
        {
          "id": "ai1",
          "text": "The segment disclosure names cloud services and hardware, not AI revenue.",
          "citations": [{"file": "annual-report.txt", "offset": 120, "quote": "cloud services and hardware"}]
        }
      ],
      "checkedSurfaces": [
        {
          "surface": "annual report segment disclosure",
          "citations": [{"file": "annual-report.txt", "offset": 120, "quote": "cloud services and hardware"}]
        }
      ]
    }
  }
}
```

Use [reference.md](reference.md) for the full JSON contract, rubric, source
classes, E1/E2 rules, grounding, subfacets, date admissibility, and warnings.

## Stop Conditions

- Stop before evidence gathering if identity cannot be resolved to one exact
  public listing with E2 identity evidence.
- Stop before `finalize` if `check` reports blocking failures.
- Stop rather than rendering a buy/sell/hold verdict. This skill produces a
  citation-verified dossier, not investment advice or a trade signal.
