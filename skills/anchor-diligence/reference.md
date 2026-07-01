# anchor-diligence Reference

Load this file when writing `research.json`, interpreting `report.json`, or
deciding whether a diligence disposition is honest.

## Contents

- JSON contract
- Fixed rubric
- Evidence rungs and URL admissibility
- Claim grounding and summaries
- Dispositions, gaps, and no-material-link
- Subfacets and aggregation
- Date admissibility and warnings
- Source classes
- Failure codes
- Known weak spots

## JSON Contract

`diligence_gate.py` writes artifacts under
`.techne/anchor-diligence/<TICKER>/`.

`scope.json` is computed by `init` and contains:

- `rubricId: public-company-deep-dive-v1`.
- the resolved identity sub-schema with E2 citations.
- optional E2-cited issuer hosts, used to admit company IR and product
  disclosure URLs for this run.
- optional `analysisAsOf` for backtest mode.
- the fixed rubric, source-class allowlists, gap floors, and subfacet manifest.

`sources/` is computed by `snapshot` and `init`:

- `*.txt` is the saved evidence text.
- `*.txt.meta.json` stores gate-recorded provenance: rung, `capturedAt`,
  `sourceLocator`, retrieval method, content hash, source class, and source
  dates when supplied.
- `events.jsonl` records the gate operation that created each cited source;
  `check` requires a matching event and content hash.
- `manifest.json` lists all snapshots. Re-using a source id creates a versioned
  file and never overwrites the existing snapshot.

`research.json` is authored by the researcher:

- `elements`: every fixed rubric element, each with a disposition.
- `claimItems`: atomic grounded claims for evidence-bearing dispositions.
- `searchLedger`: required for gaps.
- `checkedSurfaces`: required for `ai-relevance` `no-material-link`.
- subfacet objects under compound elements.

`report.json` and `reportMeta.json` are computed by `check`:

- offset + quote citation verification against saved snapshots.
- evidence-rung computation per citation and claim item.
- claim-item grounding, summary grounding, source-class, date, and aggregation
  checks.
- blocking `failures` and non-blocking `warnings`.
- Appendix disclosure for E1 corroboration counts, canonicalized by normalized
  `sourceLocator` plus content hash.

`report.md` is computed by `finalize` after a clean check.

## Fixed Rubric

Rubric id: `public-company-deep-dive-v1`.

| Element | Meaning |
| --- | --- |
| `history-origin` | founding story, milestones, and abandoned strategies/business lines |
| `business-model` | revenue streams, unit economics, moat, and switching costs |
| `financial-analysis-3yr` | three-year revenue, margin, cash-flow, and balance-sheet trend |
| `competitive-landscape` | competitors, positioning basis, and comparison snapshot |
| `management` | executives, background, tenure, and notable changes |
| `culture` | stated values, founder communications, and credible third-party accounts |
| `major-events` | M&A, leadership changes, restructuring, crises, IPO/spin-offs |
| `ownership-structure` | major shareholders and institutional holders |
| `institutional-sentiment` | analyst ratings, price targets, consensus, and institutional framing |
| `risk-factors` | regulatory, competitive, operational, financial, and macro risks |
| `ai-relevance` | material AI exposure or evidenced absence of a material link |
| `price-trend` | qualitative price and volatility description |

Every element must be accounted independently. A citation that helps
`business-model` does not automatically satisfy `financial-analysis-3yr`.

## Evidence Rungs And URL Admissibility

`E2` is gate-fetched URL evidence. The gate receives only a URL, performs the
fetch, writes the bytes, and records provenance. `present` requires E2.

`E1` is host-relayed evidence pasted from a tool or MCP source into
`snapshot --content-file`. It may be useful, but the gate cannot prove the bytes
are external. E1 permanently caps a claim item, subfacet, and element at
`present-weak`, regardless of corroboration count.

The deferred v2 source class is a gate-executed connector/API call. v1 has no
connector path.

E2 URL admissibility:

- Scheme: `https` is required for warning-free E2. `http` is accepted only with
  a sourcing warning. Non-network schemes such as `data`, `file`, `blob`,
  `javascript`, and `about` are rejected.
- Host: every resolved address must be public global unicast. The predicate is
  `is_global` and not `is_multicast`, `is_reserved`, `is_loopback`,
  `is_link_local`, `is_private`, or `is_unspecified`, including IPv4-mapped IPv6.
- Redirects: every redirect target is re-validated, and the final host is
  re-resolved at fetch time.
- Named reflector/debug/webhook classes are rejected outright.
- Source class: the URL must verify into a source class allowlisted for the
  cited element. The model's `--source-class` label is not enough by itself.
  Issuer-owned IR/product URLs count only when the issuer host was itself cited
  from E2 identity evidence during `init`.
- Reflection: the gate compares cited quote tokens to URL path/query/fragment
  tokens. If too much of the cited quote is covered by the model-supplied URL,
  the citation is downgraded out of E2. The denominator is quote tokens, not URL
  tokens, so padding the URL with decoys does not help.

## Claim Grounding And Summaries

Evidence-bearing dispositions use `claimItems`:

```json
{
  "id": "fin1",
  "text": "Revenue increased from 10.0 billion in 2022 to 12.5 billion in 2024.",
  "citations": [
    {"file": "annual-report.txt", "offset": 42, "quote": "Revenue was 10.0 billion in 2022 and 12.5 billion in 2024"}
  ]
}
```

Grounding algorithm:

1. Normalize NFKC, casefold, and punctuation to spaces.
2. Tokenize on whitespace.
3. Drop the skill STOPLIST and RUBRIC-LABEL tokens.
4. Every remaining content token in a `claimItem.text` must appear in one of
   that item's own verified citation spans.
5. A single contiguous citation span must ground the item. No cross-citation
   token union is accepted.
6. Trend or derived language needs `derivedFrom` or at least two dated grounding
   citations.

`plainSummary` is not the cited unit. It may summarize only grounded claim items
and may not introduce new names, numbers, products, percentages, dates, or
causal links absent from those claim items.

## Dispositions, Gaps, And No-Material-Link

Allowed dispositions:

- `present`: every claim item is independently E2-grounded.
- `present-weak`: cited evidence exists, but at least one claim item is E1 or
  otherwise weak.
- `gap`: no admissible evidence was found after the source-class floor was
  searched.
- `no-material-link`: only for `ai-relevance`; an evidenced finding that checked
  surfaces show no material AI exposure.

`gap` requires:

```json
{
  "disposition": "gap",
  "reason": "No admissible culture evidence found beyond generic career-page copy.",
  "searchLedger": {
    "sourceClassesChecked": ["company-ir", "financial-news"],
    "queries": [
      {"sourceClass": "company-ir", "query": "company values culture", "searchedAt": "2026-07-01T00:00:00Z"}
    ]
  }
}
```

The gate checks the fixed source-class floor per element. It also warns if saved
snapshots contain indicator terms for an element declared `gap`.

`no-material-link` requires `checkedSurfaces`, each with citations, and warns
when AI terms co-occur with revenue/product/segment terms in saved snapshots.

## Subfacets And Aggregation

Compound elements carry required subfacets:

- `financial-analysis-3yr`: `revenue-trend`,
  `margin-profitability-trend`, `cash-flow-trend`, `balance-sheet-health`.
- `competitive-landscape`: `peer-identification`, `positioning-basis`,
  `comparison-snapshot`.
- `business-model`: `revenue-streams`, `unit-economics`,
  `moat-or-switching-costs`.
- `history-origin` and `major-events`: `abandonedStrategiesChecked`.
- `risk-factors`: each risk item has a category tag:
  `regulatory`, `competitive`, `operational`, `financial`, or `macro`.

Aggregation is weakest-link:

- A claim item is `present` only if its citations are E2 after source-class and
  reflection checks.
- A subfacet is `present` only if every claim item under it is E2-grounded.
- A parent element with required subfacets is `present` only if every required
  subfacet is `present`.
- A single E1 claim item under a declared `present` element or subfacet triggers
  `present_disposition_contains_e1_claimitem` and caps the computed result at
  `present-weak`.

`competitive-landscape present` also requires a cited `comparisonSnapshot`
containing neutral peer metrics. The gate verifies cell citations but does not
rank or score peers.

## Date Admissibility And Warnings

Snapshots may carry `sourcePublishedAt`, `filingDate`, `periodEnd`, or
`observedMarketDate`. The first available admissible date is used for date
checks, falling back to `capturedAt`.

In backtest mode, `scope.json.analysisAsOf` makes post-as-of citations blocking
failures: `citation_after_analysis_asof`.

In normal mode:

- `price-trend` and `institutional-sentiment` warn if citation fetch times are
  too far apart from the rest of the report.
- elements based on a single source identity warn as `single_source_element`.
- stale dated sources warn as `stale_source`.
- differing grounded values across saved snapshots warn as
  `newer_contradictory_source_alarm`.

These warnings are structural smoke alarms. Source-selection honesty and
representativeness are judged in empirical step 5, not mechanically proven.

## Source Classes

Common E2 classes:

- `identity-registry`
- `regulatory-filing`
- `exchange-filing`
- `exchange-listing`
- `company-ir`
- `market-data`
- `data-provider`
- `financial-news`
- `analyst-research`
- `proxy-filing`
- `shareholder-disclosure`
- `product-disclosure`
- `third-party-research`
- `employee-review`

The script ships a bounded domain/path classifier for recognized filing,
exchange, market-data, and news domains. If a URL cannot be verified into a
class allowlisted for the cited element, an E2 citation cannot support
`present`.

## Failure Codes

Common blocking failures:

- `identity_unresolved`
- `identity_uncited`
- `identity_requested_mismatch`
- `rubric_element_unaccounted`
- `citation_targets_unsaved_source`
- `citation_unverified`
- `source_hash_mismatch`
- `source_provenance_unverified`
- `e2_source_class_not_allowlisted`
- `claim_item_not_grounded_in_citation`
- `plain_summary_introduces_ungrounded_content`
- `present_without_summary`
- `present_disposition_contains_e1_claimitem`
- `gap_without_reasoning`
- `gap_without_search_ledger`
- `gap_below_source_class_floor`
- `no_material_link_without_checked_surfaces`
- `subfacet_unaccounted`
- `parent_present_with_weak_subfacet`
- `comparison_snapshot_uncited`
- `risk_item_missing_category`
- `citation_after_analysis_asof`

Common warnings:

- `e2_reflection_downgrade`
- `gap_with_indicator_terms_present`
- `no_material_link_indicator_conflict`
- `fetch_time_spread_exceeds_threshold`
- `single_source_element`
- `stale_source`
- `newer_contradictory_source_alarm`

## Known Weak Spots

- The gate verifies citation bytes and grounding, not semantic relevance.
- It cannot prove that a genuine external source was representative rather than
  cherry-picked; this is step-5 empirical residue.
- E1 evidence is useful for disclosure but cannot reach `present` in v1.
- URL source-class inference is intentionally conservative and may reject real
  sources until the allowlist grows.
- Windows is out of v1 scope.
