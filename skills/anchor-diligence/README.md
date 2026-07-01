# anchor-diligence

`anchor-diligence` produces a cited public-company research dossier for one
listed equity. It is the finance shelf's vertical-analysis skill: a fixed
12-element rubric, dated evidence snapshots, and a gate that refuses reports
whose claims outrun their citations.

It does not produce buy/sell/hold calls, price targets, order drafts, or trade
signals.

## When To Use It

Use it for prompts like:

- "Deeply research Apple as a business."
- "Build a cited diligence dossier on 0700.HK."
- "Give me a comprehensive public-company deep dive on NVIDIA."

Do not use it for:

- quick quotes or price lookups;
- order placement or trading instructions;
- ETFs, bonds, crypto, macro-only topics, or private companies;
- multi-company comparison requests;
- investment verdicts.

## Workflow

1. Resolve identity with an E2 URL:

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py init \
  --project /tmp/company-research \
  --ticker AAPL \
  --exchange NASDAQ \
  --legal-name "Apple Inc." \
  --identifier 0000320193 \
  --issuer-host investor.apple.com \
  --identity-url "https://www.sec.gov/Archives/edgar/data/320193/..."
```

2. Save evidence snapshots:

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py snapshot \
  --project /tmp/company-research \
  --ticker AAPL \
  --source-id annual-report \
  --source-class regulatory-filing \
  --url "https://www.sec.gov/Archives/edgar/data/320193/..."
```

For host-relayed evidence with no fetchable URL:

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py snapshot \
  --project /tmp/company-research \
  --ticker AAPL \
  --source-id analyst-consensus \
  --source-class analyst-research \
  --content-file /tmp/analyst-consensus.txt \
  --source-locator "broker-mcp://consensus/AAPL" \
  --retrieval-method broker-mcp
```

3. Author `.techne/anchor-diligence/<TICKER>/research.json`.

4. Check:

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py check \
  --project /tmp/company-research \
  --ticker AAPL
```

5. Finalize:

```bash
python3 skills/anchor-diligence/scripts/diligence_gate.py finalize \
  --project /tmp/company-research \
  --ticker AAPL
```

## Evidence Strength

E2 is gate-fetched URL evidence and can support `present` when it passes URL,
source-class, reflection, date, and grounding checks.

E1 is host-relayed evidence. It is visible and useful, but always caps the
claim, subfacet, and element at `present-weak`.

## Output

The gate writes:

```text
.techne/anchor-diligence/<TICKER>/
  scope.json
  sources/
  research.json
  report.json
  reportMeta.json
  report.md
```

`report.md` contains Cover, Executive Summary, Deep Dive, and Appendix sections.
`reportMeta.json` carries warnings and sourcing-strength disclosure.

## Validation Status

Mechanical validation is handled by `eval.md` fixtures. Empirical acceptance is
a historical backtest and is owed after implementation, per `WORKFLOW.md`.
