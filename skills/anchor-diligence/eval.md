# anchor-diligence Eval

`anchor-diligence` is accepted only if it improves deep single-company public
equity research under pressure. Mechanical fixtures test `diligence_gate.py`;
empirical validation is a historical backtest run after implementation.

## Acceptance Status

- 2026-07-01 — Mechanical implementation PR self-check: **passed** for
  `diligence_gate.py` py-compile, clean finalize, attack-shaped `/tmp`
  fixtures from rounds 2-5, URL/IP admissibility probes, `git diff --check`,
  and `claude plugin validate . --strict`.
- 2026-07-01 — Empirical acceptance: **not yet run**, owed. The implementation
  PR must not close issue #31. Historical backtest results should be recorded
  here and in `ROADMAP.md` before the skill is considered accepted.

## Mechanical Fixtures

All fixtures run against throwaway `/tmp` projects. Generated `.techne/` output
must not be committed.

| Fixture | Expected |
| --- | --- |
| `rubric_element_unaccounted` | missing one of the 12 elements fails with `rubric_element_unaccounted` |
| `citation_quote_mismatch` | wrong offset or quote fails with `citation_unverified` |
| `citation_unsaved_source` | citation to a file not in `sources/` fails with `citation_targets_unsaved_source` |
| `source_hash_or_event_tamper` | cited source whose bytes or metadata no longer match the gate event fails with `source_hash_mismatch` or `source_provenance_unverified` |
| `plain_summary_not_grounded` | summary introduces an ungrounded product/name/number/date and fails with `plain_summary_introduces_ungrounded_content` |
| `present_missing_summary` | `present`, `present-weak`, or `no-material-link` without a short `plainSummary` fails with `present_without_summary` |
| `fabricated_e1_cannot_present` | one or more E1 claim items under declared `present` fails with `present_disposition_contains_e1_claimitem` |
| `two_e1_corrob_still_weak` | two E1 snippets with matching content remain `present-weak`; disclosure count is display-only |
| `e1_count_canonicalized` | two relayed snippets with same normalized `sourceLocator` and content hash disclose `1 independent E1 source (2 relayed snippets)` |
| `gap_without_ledger` | `gap` without `searchLedger` fails with `gap_without_search_ledger` |
| `gap_below_source_class_floor` | gap ledger missing fixed source classes fails with `gap_below_source_class_floor` and may warn on indicator terms |
| `false_no_material_link_indicator` | `ai-relevance no-material-link` over saved AI+revenue/product evidence warns `no_material_link_indicator_conflict` |
| `no_material_link_without_surfaces` | `no-material-link` without cited checked surfaces fails with `no_material_link_without_checked_surfaces` |
| `identity_requires_e2` | identity fields without E2 citations fail with `identity_uncited` |
| `identity_exact_listing_match` | requested ticker/exchange mismatch fails with `identity_requested_mismatch` |
| `subfacet_incomplete_parent_present` | compound parent declared `present` with missing/weak subfacet fails with `subfacet_unaccounted` or `parent_present_with_weak_subfacet` |
| `business_model_5th_subfacet_launder` | extra unlisted subfacet cannot replace the required A12 subfacets |
| `comparison_snapshot_uncited` | `competitive-landscape present` without cited comparison cells fails with `comparison_snapshot_uncited` |
| `risk_item_uncategorized` | `risk-factors` item without fixed category tag fails with `risk_item_missing_category` |
| `snapshot_non_overwrite` | repeated `snapshot --source-id` creates versioned files and manifest entries, never overwrites |
| `post_analysis_asof_citation` | backtest citation dated after `analysisAsOf` fails with `citation_after_analysis_asof` |
| `padded_query_reflector` | quote tokens covered by URL query cause `e2_reflection_downgrade` even when URL has many decoys |
| `generic_reflector_named_class` | `postman-echo`, `httpbin`, webhook/debug endpoints are rejected for E2 |
| `source_class_self_report_rejected` | URL whose verified source class is not allowlisted cannot support E2 |
| `a14_6to4_teredo_cgnat_docs_multicast_nat64` | non-global or non-unicast transition/special ranges fail URL/IP admissibility |
| `a17_trivial_e2_material_e1_same_element` | trivial E2 claim plus material E1 claim under same declared `present` fails with `present_disposition_contains_e1_claimitem` |
| `a17_subfacet_parent_chain` | parent `present` with one weak subfacet fails with `parent_present_with_weak_subfacet` |
| `clean_finalize` | all 12 elements accounted, identity E2-cited, citations verified, subfacets complete; `finalize` writes `report.md`, `report.json`, and `reportMeta.json` |
| `status_surfaces_artifacts` | `status` reports scope, research, report, final report, and source list |
| `argparse_unknown` | unknown subcommand or unknown flag exits through argparse with code 2 |
| `gitignore_idempotent` | `.techne/` is appended to target `.gitignore` once |

## Attack-Shaped Fixture Notes

Round 2 probes:

- E1 corroboration is not external provenance. Matching E1 citations must never
  promote a disposition to `present`.
- `data:` and other non-network URL schemes must be rejected before fetch.
- identity cannot be cleared by E1-only evidence.

Round 3 probes:

- HTTPS reflectors are self-authored-content paths and must be caught by
  source-class plus reflection checks.
- decimal/octal/hex/private/loopback/mapped-address SSRF variants must fail
  closed after final resolution.
- E1 corroboration disclosure must dedupe by normalized source identity and
  content hash.

Round 4 probes:

- padded reflector URLs are defeated only when the denominator is cited quote
  tokens covered by URL tokens.
- `is_global` alone is not enough; multicast and NAT64 well-known-prefix
  samples report global in Python but must still be rejected.

Round 5 probes:

- A17 requires weakest-link aggregation across every claim item.
- A17 must compose through the subfacet layer: parent `present` requires every
  required subfacet `present`.

## Empirical Acceptance

Validation runs after the implementation exists, per `WORKFLOW.md` step 5.

Test set:

- Three companies across at least two supported markets.
- Each company has a maintainer-authored answer key frozen before any leg.
- Each answer key is dated to a historical as-of point, ideally 18-24 months in
  the past.
- At least one identity trap.
- At least one company with no material AI exposure.
- At least one company with real material AI exposure.
- At least one seeded false-gap positive.

Protocol:

- Baseline leg: plain deep company research with no skill.
- Skill leg: identical prompt with `anchor-diligence`.
- Backtest mode constrains citations to material datable at or before
  `analysisAsOf`.

Metrics per leg:

- identity resolution correctness;
- rubric disposition vs. answer key;
- citation verification rate;
- fabrication rate;
- no-material-link vs. AI relevance accuracy;
- report layer completeness;
- engagement with expected source classes and known contradictory evidence.

Controls:

- C1 negative trigger: quick quote should self-eject and create no
  `.techne/anchor-diligence/*`.
- C2 anti-forced-relevance: no-AI company lands on evidenced
  `no-material-link`.
- C3 identity resolution: trap resolves correctly or refuses.
- C4 positive-AI control: material AI company must not land on
  `no-material-link`.

Pass bar:

- Skill legs achieve full rubric accounting and citation verification in 3/3.
- Fabrication rate is approximately zero.
- C1-C4 all pass.
- No leg where the gate forces a dishonest frame or blocks an honest dossier.
- If baseline already clears this, the skill has no marginal value and is not
  accepted.

## Goodhart Watch

Record these in the empirical write-up:

- cosmetic citations that quote real but irrelevant prose;
- source selection that is genuine but cherry-picked or stale;
- no-material-link used to dodge real AI exposure;
- comparison snapshot cells picked to imply a verdict;
- excessive E1 reliance hidden behind smooth prose;
- false gaps that offload extraction work to the user;
- glossary/plain-summary theater that restates jargon rather than explaining it.

## Coverage Gaps

- semantic relevance of a verified citation;
- source accuracy;
- representative source selection;
- gate-executed financial-data connectors;
- Windows support;
- richer report viewer or charts.
