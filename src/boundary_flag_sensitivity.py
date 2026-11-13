"""Worst-case deletion sensitivity for deliveries with missing boundary flags.

The source contains records with recorded runs of 4 or 6 but neither is_four nor
is_six set. This audit removes those rows from the complete analytical frame,
then recomputes peer baselines, reliability and rankings. It is deliberately a
conservative deletion test (not a boundary-only denominator correction): the
removed deliveries no longer contribute to any metric. The primary ranking is
never overwritten.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

from .dataset_scope import apply_competition_scope
from .match_context import build_match_context
from .pressure_detection import add_pressure_flags
from .player_baselines import calculate_player_baselines
from .player_reliability import calculate_player_reliability
from .player_ratings import calculate_rankings


def _bool(s: pd.Series) -> pd.Series:
    return s.astype("boolean").fillna(False).astype(bool)


def run_boundary_flag_sensitivity(source_tables: dict[str, pd.DataFrame],
                                  primary_bat: pd.DataFrame,
                                  primary_bowl: pd.DataFrame) -> dict:
    tables, scope_audit = apply_competition_scope(source_tables, "ipl_t20i")
    context = build_match_context(tables["ball_by_ball"], tables["matches"], tables["competitions"])
    pressured = add_pressure_flags(context)
    runs = pd.to_numeric(pressured["runs"], errors="coerce")
    flags = _bool(pressured["is_four"]) | _bool(pressured["is_six"])
    suspect = runs.isin([4, 6]) & ~flags
    suspect_count = int(suspect.sum())
    suspect_runs = runs.loc[suspect].value_counts().to_dict()
    filtered = pressured.loc[~suspect].copy()

    bat_ctx, _, bowl_ctx, _, _, baseline_audit = calculate_player_baselines(filtered)
    bat_rel, _, bowl_rel, _, rel_audit = calculate_player_reliability(filtered, bat_ctx, bowl_ctx)
    bat, bowl, _, _, rank_audit = calculate_rankings(bat_rel, bowl_rel)

    def compare(primary: pd.DataFrame, alternative: pd.DataFrame) -> dict:
        p = primary.sort_values("rank").head(10)["player_name"].astype(str).tolist()
        a = alternative.sort_values("rank").head(10)["player_name"].astype(str).tolist()
        ps, ass = set(p), set(a)
        return {
            "primary_names": p,
            "alternative_names": a,
            "top10_overlap": len(ps & ass),
            "unchanged_rank_order": p == a,
            "entered": [x for x in a if x not in ps],
            "left": [x for x in p if x not in ass],
        }

    return {
        "method": "Drop all records with recorded runs equal to 4 or 6 but neither boundary flag set, then fully recompute context-matched peer baselines, reliability and rankings. This is a conservative whole-record deletion stress test; it is not a correction of missing flags.",
        "suspect_records": suspect_count,
        "suspect_recorded_runs_breakdown": {str(k): int(v) for k, v in suspect_runs.items()},
        "primary_scope_matches": int(scope_audit.get("selected_counts", {}).get("matches", 0)),
        "remaining_delivery_records": int(len(filtered)),
        "removed_delivery_records": suspect_count,
        "baseline_coverage_after_deletion": {
            "batting_pct": baseline_audit["batting_context_coverage"]["peer_coverage_pct"],
            "bowling_pct": baseline_audit["bowling_context_coverage"]["peer_coverage_pct"],
        },
        "batters": compare(primary_bat, bat),
        "bowlers": compare(primary_bowl, bowl),
        "ranking_recomputed": True,
        "primary_rankings_overwritten": False,
    }


def save_boundary_flag_sensitivity(source_tables, primary_bat, primary_bowl,
                                   output_path="outputs/boundary_flag_sensitivity.json") -> dict:
    result = run_boundary_flag_sensitivity(source_tables, primary_bat, primary_bowl)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
