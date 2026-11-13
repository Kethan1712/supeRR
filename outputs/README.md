# Generated analysis outputs

All primary outputs in this folder were generated from the supplied source CSVs using the default `ipl_t20i` scope (IPL 2022–2026 + T20I). The six original CSV inputs are included in the project-level `data/` folder; see `data/README_DATA_PROVENANCE.md` before redistributing them.

## Primary deliverables

- `batting_rankings_top10.csv` / `bowling_rankings_top10.csv`: final top-10 tables.
- `batting_candidate_scores.csv` / `bowling_candidate_scores.csv`: eligible candidate score breakdowns.
- `ranking_sensitivity.csv`: alternative prior/sample-size eligibility runs.
- `metric_weight_sensitivity.csv` and `.json`: alternative scoring weights and full top-10 details.
- `pressure_threshold_ranking_stability.csv`: 8-, 10- and 12-over early-collapse comparisons.

## Audit evidence

- `competition_scope_audit.json`: included/excluded competitions, matches and deliveries.
- `match_context_audit.json`: delivery ordering, innings and wicket-state checks.
- `pressure_detection_audit.json`: pressure coverage and overlap.
- `batting_metrics_audit.json`, `bowling_metrics_audit.json`: descriptive metric checks.
- `player_baseline_audit.json`, `player_reliability_audit.json`, `ranking_audit.json`: peer coverage, sample eligibility and score construction.

- `revised_allocation_inheritance_sensitivity.json`: full-pipeline check disabling inheritance of missing second-innings revised allocations; top-10 names and rank order remain unchanged.

## Rajasthan Royals appendix

- `rr_2026_squad_role_audit.csv`: retrospective RR 2026 player/phase usage.
- `rr_2027_ranked_player_fit.csv`: qualitative role-fit screen for the 20 ranked players. This is not evidence of 2027 availability, registration, fitness, release or price.

## Rebuild

From project root, run the full `python main.py ...` command in the root README. Do not hand-edit computed outputs; regenerate them from the input data and source code.

## Competition scope comparison

`scope_comparison/` contains a separate full ranking-pipeline rerun over all supplied T20-format competitions plus T20Is. The primary ranking CSVs remain IPL 2022 onward + T20I only. The expanded rankings are prefixed `expanded_` and must not be treated as the primary submission list. Run `python run_scope_comparison.py` to reproduce the independent runs and regenerate the comparison outputs.
