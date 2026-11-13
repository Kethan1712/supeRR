# SupeRR Selector Season 2 — Round 1

**Most Reliable Batters and Bowlers Under Pressure**  
Audit + evidence edition · Analysis cut-off: 13 November 2026

This project contains the reproducible Python analysis, original competition-supplied CSV inputs, the methodology report (DOCX and PDF), player-level evidence profiles for all 20 selected players, sensitivity audits, and an additional Rajasthan Royals (RR) 2026 role-depth / IPL 2027 planning appendix.

## Dual-scope analysis and submission decision

This project maintains two independently calculated ranking populations. The **official Round 1 submission scope** follows the problem statement's IPL and T20I population. The **expanded research scope** is the broader primary research analysis for this project and adds the two supplied T20 competitions. Do not mix scores across scopes because peer baselines and candidate pools are recalculated separately.

### Official Round 1 submission scope

The Round 1 problem statement specifies IPL and T20I. The official submission analysis includes:
- IPL seasons 2022–2026
- T20 Internationals from 2022 onward
- 853 selected matches, 837 with ball-by-ball records, and 194,014 selected delivery rows

The supplied pack also contains two additional T20 competitions: Men's T20 Emerging Teams Asia Cup 2024 (15 matches) and Asia Cup Rising Stars 2025 (15 matches). All 30 have ball-by-ball records and contribute 6,985 delivery rows. They are included in the **expanded research scope**: a second, independently rerun analysis includes all supplied T20-format competitions plus T20Is. Its results are kept separately under `outputs/scope_comparison/` and do not overwrite the official IPL + T20I ranking CSVs.

### Competition-scope sensitivity result

| Measure | Official: IPL + T20I | Expanded research: all supplied T20 + T20I |
|---|---:|---:|
| Competition IDs represented | 136 | 138 |
| Match rows | 853 | 883 |
| Matches with ball-by-ball data | 837 | 867 |
| Ball-by-ball delivery rows | 194,014 | 200,999 |
| Batter Top 10 overlap | Primary reference | 9/10 |
| Bowler Top 10 overlap | Primary reference | 8/10 |

The expanded batter list adds Liam Livingstone and removes Ramandeep Singh. The expanded bowler list adds Ehsan Khan and Rasikh Salam and removes Ben Dwarshuis and Rahul Chahar. Shared players can also change position and score because the candidate pool and context-matched peer comparisons are recalculated over the expanded population. These expanded rankings are the project's broader research result. The IPL + T20I rankings remain the official Unstop submission lists because they match the Round 1 population specified in the brief.

## Official Round 1 submission rankings (IPL + T20I)

The 0–100 index is a relative composite percentile, **not a probability or guarantee**. The official ranking CSVs are authoritative for Unstop; the report and evidence tables are generated from them. Expanded research rankings are stored separately under `outputs/scope_comparison/`.

### Batters

| Rank | Player | Index |
|---:|---|---:|
| 1 | Najibullah Zadran | 87.62 |
| 2 | Sikandar Raza | 85.09 |
| 3 | Naman Dhir | 82.69 |
| 4 | Rinku Singh | 81.71 |
| 5 | Tristan Stubbs | 80.79 |
| 6 | Nurul Hasan | 78.35 |
| 7 | Rishabh Pant | 76.31 |
| 8 | Ramandeep Singh | 75.19 |
| 9 | Babar Azam | 74.93 |
| 10 | Glenn Phillips | 74.67 |

### Bowlers

| Rank | Player | Index |
|---:|---|---:|
| 1 | Sunil Narine | 85.97 |
| 2 | Hasan Mahmud | 83.82 |
| 3 | Rashid Khan | 82.54 |
| 4 | Akeal Hosein | 80.98 |
| 5 | Dasun Shanaka | 80.29 |
| 6 | Riley Meredith | 79.43 |
| 7 | Adam Zampa | 79.16 |
| 8 | Nandre Burger | 78.76 |
| 9 | Ben Dwarshuis | 77.60 |
| 10 | Rahul Chahar | 76.67 |

## Method summary

- **Batters:** combined early-collapse OR death-phase pressure, de-duplicated.
- **Bowlers:** death-phase pressure only; a batting-side collapse is not automatically pressure on the bowler.
- **Pressure:** five wickets lost by the end of the first 50% of allocated innings; pressure begins on the next delivery. Death phase is the final 25% of allocated innings.
- **Batting metrics:** recorded runs per 100 balls (50%), dismissal rate (30%, lower better), boundary flags per 100 balls (20%).
- **Bowling metrics:** bowler-creditable wickets per 100 candidate legal balls (60%), flagged boundaries conceded per 100 candidate legal balls (40%, lower better).
- **Peer baselines:** leave-one-player-out, opportunity-weighted and context-matched by competition/innings/phase, with format-season and format fallbacks.
- **Shrinkage:** player-level prior of 60 opportunities; match-level prior of 12 opportunities.
- **Final index:** 70% pressure-performance component + 30% match-consistency component.
- **Eligibility:** batter minimum 100 combined-pressure balls and 10 matches; bowler minimum 60 death candidate legal balls and 10 matches; ordinary comparison and peer coverage requirements also apply.

The selected weights and thresholds are declared modelling choices. Sensitivity outputs disclose the effect of alternatives. Under equal metric weights, batter Top 10 overlap is 10/10 and bowler overlap is 7/10. A deletion stress test that removes all 23 deliveries with a recorded 4/6 but missing boundary flags leaves both Top 10 lists and their rank order unchanged.

## Player-level evidence

- `outputs/top10_batter_evidence.csv`
- `outputs/top10_bowler_evidence.csv`
- `outputs/top10_batter_match_spotlights.csv`
- `outputs/top10_bowler_match_spotlights.csv`

These files provide pressure opportunities, match counts, positive match share, peer-relative pressure performance, uplift versus ordinary performance, score components, and metric-level inputs for every selected player. Evidence-volume labels are sample-volume descriptions, not probabilities or confidence intervals.

## RR 2027 planning

- `outputs/rr_2026_squad_role_audit.csv`: observed 2026 phase usage.
- `outputs/rr_2027_role_depth_matrix.csv`: first-choice / backup / injury-cover / successor planning labels based on 2026 usage.
- `outputs/rr_2027_ranked_player_fit.csv`: role-fit screen for all 20 ranked players.

The 2027 plan is conditional. No player is described as available to RR until official retention/release and final auction-registration information confirms eligibility. The role-depth matrix is not an official 2027 depth chart.

## Reproducibility

The six original CSV inputs are included in `data/` for reviewer reproducibility. See `data/README_DATA_PROVENANCE.md`; do not publish the raw files publicly unless the competition organiser's terms permit redistribution.

From the project root:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python main.py --audit-context --audit-pressure --audit-batting --audit-bowling --audit-baselines --audit-reliability --audit-rankings --audit-pressure-ranking-stability --audit-rr-squad
python build_supplemental_outputs.py
python run_scope_comparison.py
python generate_report.py
```

Tested environment is recorded in `environment.txt` (Python 3.13.5, pandas 2.2.3, NumPy 2.3.5, Matplotlib 3.10.8, pytest 9.0.2, python-docx 1.2.0). The latest full test run: **57 passed** (52 previous tests + 5 competition-scope comparison/audit regression tests).

## Important output files

- `methodology_report.pdf` and `methodology_report.docx`
- `outputs/batting_rankings_top10.csv`
- `outputs/bowling_rankings_top10.csv`
- `outputs/top10_batter_evidence.csv`
- `outputs/top10_bowler_evidence.csv`
- `outputs/top10_batter_match_spotlights.csv`
- `outputs/top10_bowler_match_spotlights.csv`
- `outputs/metric_weight_sensitivity.json`
- `outputs/pressure_threshold_ranking_stability.csv`
- `outputs/boundary_flag_sensitivity.json`
- `outputs/rr_2027_role_depth_matrix.csv`
- `outputs/rr_2027_ranked_player_fit.csv`
- `outputs/final_validation_summary.json`
- `outputs/supplemental_validation_summary.json`
- `outputs/scope_comparison/competition_scope_comparison.json`
- `outputs/scope_comparison/competition_scope_comparison.md`
- `outputs/scope_comparison/competition_scope_comparison_players.csv`
- `outputs/scope_comparison/expanded_batting_rankings_top10.csv`
- `outputs/scope_comparison/expanded_bowling_rankings_top10.csv`
- `outputs/scope_comparison/expanded_batting_candidate_scores.csv`
- `outputs/scope_comparison/expanded_bowling_candidate_scores.csv`

## Limitations

Recorded runs are not asserted to be fully scorecard-reconciled batter runs. Bowling economy and true dot-ball rates are omitted because extras are incomplete. Boundary flags contain 23 missing flags on 4/6-run deliveries. The pressure proxy does not reconstruct required run rate, target, wickets in hand or match closeness. The 0–100 score is not a calibrated probability of future success.
