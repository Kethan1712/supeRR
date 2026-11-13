# Competition-scope sensitivity analysis

The primary ranking uses IPL 2022 onward and T20 Internationals. The expanded run includes all supplied T20-format competitions plus T20Is. Both runs were independently recalculated from the six source CSVs using the same pipeline and scoring settings.

| Measure | Primary: IPL + T20I | Expanded: all supplied T20 + T20I |
|---|---:|---:|
| Competition IDs represented | 136 | 138 |
| Match rows | 853 | 883 |
| Matches with ball-by-ball data | 837 | 867 |
| Delivery rows | 194,014 | 200,999 |

## Additional competitions in the expanded scope

- Mens T20 Emerging Teams Asia Cup 2024: 15 matches; 15 with ball-by-ball data.
- Asia Cup Rising Stars 2025: 15 matches; 15 with ball-by-ball data.

## Top-10 comparison

- Batters: 9/10 overlap. Entering: Liam Livingstone. Leaving: Ramandeep Singh.
- Bowlers: 8/10 overlap. Entering: Ehsan Khan, Rasikh Salam. Leaving: Ben Dwarshuis, Rahul Chahar.

## Interpretation

This is a population-definition sensitivity test, not a claim that either competition pool is universally correct. Adding competitions can add eligible players and opportunities, and can also change context-matched peer cohorts and relative scores. The primary ranking remains the IPL 2022 onward + T20I list because that is the population named in the Round 1 brief. The expanded rankings are retained as a transparent supplementary result; they do not overwrite the primary ranking CSVs.

## Reproduction

Run `python run_scope_comparison.py` from the project root. The script executes both full pipelines in isolated temporary working directories and writes the summary, player-level changes, expanded top-10 CSVs, full candidate score CSVs, scope audit, and run logs under `outputs/scope_comparison/`.
