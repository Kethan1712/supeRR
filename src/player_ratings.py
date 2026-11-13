"""Build transparent pressure-reliability scores and ranking sensitivity checks.

Primary ranking choices:
- Batters: combined pressure (early collapse OR death overs, de-duplicated).
- Bowlers: death-over context only. An early batting collapse is pressure on
  batters, not automatically pressure on the bowling side.
- Player comparison: sample-adjusted pressure-vs-peer performance AND the
  change in peer-relative standing from the player's ordinary baseline.
- Reliability: match-to-match positive share, median adjusted match effect,
  and dispersion across matches.

The resulting 0-100 score is a relative composite, not a probability.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BATTER_CATEGORY = "combined_pressure"
BOWLER_CATEGORY = "death_over_context"
ORDINARY_CATEGORY = "ordinary_baseline"
DEFAULT_PRIOR = 60
DEFAULT_MIN_BATTER_OPPORTUNITIES = 100
DEFAULT_MIN_BOWLER_OPPORTUNITIES = 60
DEFAULT_MIN_MATCHES = 10
DEFAULT_MIN_BASELINE_COVERAGE = 80.0

BATTER_WEIGHTS = {
    "recorded_runs_per_100_balls": 0.50,
    "dismissals_per_100_balls": 0.30,
    "boundaries_per_100_balls": 0.20,
}
BOWLER_WEIGHTS = {
    "bowler_wickets_per_100_candidate_legal_balls": 0.60,
    "flagged_boundaries_per_100_candidate_legal_balls": 0.40,
}


def _percentile(values: pd.Series, *, higher_better: bool = True) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    if not higher_better:
        numeric = -numeric
    return numeric.rank(pct=True, method="average") * 100.0


def _role_features(
    reliability: pd.DataFrame,
    *,
    pressure_category: str,
    metric_weights: dict[str, float],
    min_opportunities: int,
    min_matches: int,
    min_baseline_coverage: float,
    prior_strength: int,
    role: str,
    performance_weight: float,
    consistency_weight: float,
) -> tuple[pd.DataFrame, dict]:
    required = {
        "player_id", "player_name", "metric_category", "metric", "metric_direction",
        "all_opportunities", "matches_in_category", "baseline_coverage_pct",
        "matches_with_peer_baseline", f"sample_adjusted_vs_peer_pct_prior_{prior_strength}",
        "positive_match_share_pct", "median_match_adjusted_vs_peer_pct",
        "std_match_adjusted_vs_peer_pct",
    }
    missing = sorted(required - set(reliability.columns))
    if missing:
        raise ValueError(f"{role} reliability input missing columns: {missing}")

    pressure = reliability.loc[
        reliability["metric_category"].eq(pressure_category)
        & reliability["metric"].isin(metric_weights)
    ].copy()
    ordinary = reliability.loc[
        reliability["metric_category"].eq(ORDINARY_CATEGORY)
        & reliability["metric"].isin(metric_weights),
        ["player_id", "metric", f"sample_adjusted_vs_peer_pct_prior_{prior_strength}",
         "all_opportunities", "matches_in_category", "baseline_coverage_pct", "matches_with_peer_baseline"],
    ].copy()
    ordinary = ordinary.rename(columns={
        f"sample_adjusted_vs_peer_pct_prior_{prior_strength}": "ordinary_adjusted_vs_peer_pct",
        "all_opportunities": "ordinary_opportunities",
        "matches_in_category": "ordinary_matches",
        "baseline_coverage_pct": "ordinary_baseline_coverage_pct",
        "matches_with_peer_baseline": "ordinary_matches_with_peer_baseline",
    })
    merged = pressure.merge(ordinary, on=["player_id", "metric"], how="left", validate="one_to_one")
    pressure_col = f"sample_adjusted_vs_peer_pct_prior_{prior_strength}"
    merged["pressure_adjusted_vs_peer_pct"] = pd.to_numeric(merged[pressure_col], errors="coerce")
    merged["pressure_uplift_vs_ordinary_pct_points"] = (
        merged["pressure_adjusted_vs_peer_pct"] - merged["ordinary_adjusted_vs_peer_pct"]
    )

    # Baseline support and participation thresholds are evaluated per metric.
    eligible_row = (
        merged["all_opportunities"].ge(min_opportunities)
        & merged["matches_in_category"].ge(min_matches)
        & merged["baseline_coverage_pct"].ge(min_baseline_coverage)
        & merged["matches_with_peer_baseline"].ge(min_matches)
        & merged["ordinary_opportunities"].ge(min_opportunities)
        & merged["ordinary_matches"].ge(min_matches)
        & merged["ordinary_baseline_coverage_pct"].ge(min_baseline_coverage)
        & merged["ordinary_matches_with_peer_baseline"].ge(min_matches)
        & merged["pressure_adjusted_vs_peer_pct"].notna()
        & merged["ordinary_adjusted_vs_peer_pct"].notna()
        & merged["pressure_uplift_vs_ordinary_pct_points"].notna()
    )
    merged["eligible_metric"] = eligible_row
    eligible_player_counts = merged.loc[eligible_row].groupby("player_id")["metric"].nunique()
    required_metric_count = len(metric_weights)
    eligible_players = set(eligible_player_counts[eligible_player_counts.eq(required_metric_count)].index)
    merged["eligible_player"] = merged["player_id"].isin(eligible_players)
    scoring = merged.loc[merged["eligible_player"]].copy()

    if scoring.empty:
        audit = {
            "role": role, "pressure_category": pressure_category,
            "players_with_all_metrics": 0, "metric_weights": metric_weights,
            "min_opportunities": min_opportunities, "min_matches": min_matches,
            "min_baseline_coverage_pct": min_baseline_coverage,
            "prior_strength": prior_strength,
        }
        return pd.DataFrame(), audit

    scoring["pressure_level_percentile"] = scoring.groupby("metric", sort=False)[
        "pressure_adjusted_vs_peer_pct"
    ].transform(_percentile)
    scoring["pressure_uplift_percentile"] = scoring.groupby("metric", sort=False)[
        "pressure_uplift_vs_ordinary_pct_points"
    ].transform(_percentile)
    scoring["performance_percentile"] = (
        0.50 * scoring["pressure_level_percentile"]
        + 0.50 * scoring["pressure_uplift_percentile"]
    )
    scoring["positive_match_percentile"] = scoring.groupby("metric", sort=False)[
        "positive_match_share_pct"
    ].transform(_percentile)
    scoring["median_match_percentile"] = scoring.groupby("metric", sort=False)[
        "median_match_adjusted_vs_peer_pct"
    ].transform(_percentile)
    scoring["match_stability_percentile"] = scoring.groupby("metric", sort=False)[
        "std_match_adjusted_vs_peer_pct"
    ].transform(lambda s: _percentile(s, higher_better=False))
    scoring["consistency_percentile"] = (
        0.50 * scoring["positive_match_percentile"]
        + 0.30 * scoring["median_match_percentile"]
        + 0.20 * scoring["match_stability_percentile"]
    )
    scoring["metric_weight"] = scoring["metric"].map(metric_weights)
    scoring["weighted_performance"] = scoring["performance_percentile"] * scoring["metric_weight"]
    scoring["weighted_consistency"] = scoring["consistency_percentile"] * scoring["metric_weight"]

    player_scores = scoring.groupby(["player_id", "player_name"], sort=False).agg(
        performance_component=("weighted_performance", "sum"),
        consistency_component=("weighted_consistency", "sum"),
        pressure_opportunities=("all_opportunities", "min"),
        pressure_matches=("matches_in_category", "min"),
        ordinary_opportunities=("ordinary_opportunities", "min"),
        ordinary_matches=("ordinary_matches", "min"),
        pressure_baseline_coverage_pct=("baseline_coverage_pct", "min"),
        ordinary_baseline_coverage_pct=("ordinary_baseline_coverage_pct", "min"),
        positive_match_share_pct=("positive_match_share_pct", "mean"),
        mean_pressure_adjusted_vs_peer_pct=("pressure_adjusted_vs_peer_pct", "mean"),
        mean_uplift_vs_ordinary_pct_points=("pressure_uplift_vs_ordinary_pct_points", "mean"),
    ).reset_index()
    player_scores["reliability_score"] = (
        performance_weight * player_scores["performance_component"]
        + consistency_weight * player_scores["consistency_component"]
    )
    player_scores = player_scores.sort_values(
        ["reliability_score", "pressure_opportunities", "pressure_matches", "player_name"],
        ascending=[False, False, False, True], kind="mergesort"
    ).reset_index(drop=True)
    player_scores.insert(0, "rank", np.arange(1, len(player_scores) + 1))
    audit = {
        "role": role,
        "pressure_category": pressure_category,
        "metric_weights": metric_weights,
        "prior_strength": prior_strength,
        "min_opportunities": min_opportunities,
        "min_matches": min_matches,
        "min_baseline_coverage_pct": min_baseline_coverage,
        "players_with_all_metrics": int(len(player_scores)),
        "pressure_rows_examined": int(len(pressure)),
        "eligible_metric_rows": int(eligible_row.sum()),
        "ranking_score": f"{performance_weight:.0%} performance composite + {consistency_weight:.0%} match-consistency composite",
        "performance_composite": "For each metric, 50% percentile of pressure performance vs peers + 50% percentile of pressure uplift vs the same player's ordinary peer-relative performance; then metric-weighted.",
        "consistency_composite": "For each metric, 50% positive adjusted match share + 30% median adjusted match peer-relative performance + 20% inverse dispersion percentile; then metric-weighted.",
        "score_interpretation": "Relative percentile composite from 0 to 100; not a probability or percentage chance of success.",
    }
    return scoring, {**audit, "player_scores": player_scores}


def calculate_rankings(
    batting_reliability: pd.DataFrame,
    bowling_reliability: pd.DataFrame,
    *,
    prior_strength: int = DEFAULT_PRIOR,
    min_batter_opportunities: int = DEFAULT_MIN_BATTER_OPPORTUNITIES,
    min_bowler_opportunities: int = DEFAULT_MIN_BOWLER_OPPORTUNITIES,
    min_matches: int = DEFAULT_MIN_MATCHES,
    min_baseline_coverage: float = DEFAULT_MIN_BASELINE_COVERAGE,
    batter_metric_weights: dict[str, float] | None = None,
    bowler_metric_weights: dict[str, float] | None = None,
    performance_weight: float = 0.70,
    consistency_weight: float = 0.30,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    if not np.isclose(performance_weight + consistency_weight, 1.0) or min(performance_weight, consistency_weight) < 0:
        raise ValueError("performance_weight and consistency_weight must be non-negative and sum to 1")
    bat_weights = dict(batter_metric_weights or BATTER_WEIGHTS)
    bowl_weights = dict(bowler_metric_weights or BOWLER_WEIGHTS)
    if not np.isclose(sum(bat_weights.values()), 1.0) or any(v < 0 for v in bat_weights.values()):
        raise ValueError("Batter metric weights must be non-negative and sum to 1")
    if not np.isclose(sum(bowl_weights.values()), 1.0) or any(v < 0 for v in bowl_weights.values()):
        raise ValueError("Bowler metric weights must be non-negative and sum to 1")
    bat_features, bat_info = _role_features(
        batting_reliability,
        pressure_category=BATTER_CATEGORY,
        metric_weights=bat_weights,
        min_opportunities=min_batter_opportunities,
        min_matches=min_matches,
        min_baseline_coverage=min_baseline_coverage,
        prior_strength=prior_strength,
        role="batters",
        performance_weight=performance_weight,
        consistency_weight=consistency_weight,
    )
    bowl_features, bowl_info = _role_features(
        bowling_reliability,
        pressure_category=BOWLER_CATEGORY,
        metric_weights=bowl_weights,
        min_opportunities=min_bowler_opportunities,
        min_matches=min_matches,
        min_baseline_coverage=min_baseline_coverage,
        prior_strength=prior_strength,
        role="bowlers",
        performance_weight=performance_weight,
        consistency_weight=consistency_weight,
    )
    bat_scores = bat_info.pop("player_scores", pd.DataFrame())
    bowl_scores = bowl_info.pop("player_scores", pd.DataFrame())
    audit = {
        "module": "player_ratings",
        "primary_prior_strength": prior_strength,
        "performance_weight": performance_weight,
        "consistency_weight": consistency_weight,
        "batter_metric_weights": bat_weights,
        "bowler_metric_weights": bowl_weights,
        "eligibility": {
            "batters_min_pressure_balls": min_batter_opportunities,
            "bowlers_min_death_over_candidate_legal_balls": min_bowler_opportunities,
            "min_pressure_matches": min_matches,
            "min_baseline_coverage_pct": min_baseline_coverage,
            "ordinary_baseline_must_also_meet_opportunity_and_match_thresholds": True,
            "all_role_metrics_must_have_supported_baselines": True,
        },
        "batting": bat_info,
        "bowling": bowl_info,
        "bowling_pressure_scope_note": "Main bowler ranking uses death-over context. Early-collapse bowling context is retained as supporting analysis, not treated as pressure on the bowler.",
        "limitations": [
            "Recorded batting runs are not a completely scorecard-reconciled official batter-runs field.",
            "Bowling uses candidate legal balls excluding wides and Overstep; the candidate count is not independently scorecard-certified.",
            "Bowling uses bowler-creditable wickets and boundary flags; economy rate and true dot-ball rate are not used because bowler extras are incomplete.",
            "The composite score is a transparent relative ranking index, not a calibrated probability.",
            "The 60-opportunity shrinkage prior and eligibility thresholds are modelling choices; stability checks are required.",
        ],
        "rankings_created": True,
    }
    return bat_scores, bowl_scores, bat_features, bowl_features, audit


def _top10_overlap(a: pd.DataFrame, b: pd.DataFrame) -> float:
    if a.empty or b.empty:
        return float("nan")
    return len(set(a.head(10).player_id) & set(b.head(10).player_id))


def calculate_stability(
    batting_reliability: pd.DataFrame,
    bowling_reliability: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """Compare top-10 membership for prior and eligibility alternatives."""
    rows = []
    baseline = None
    scenario_results = {}
    scenarios = [
        (60, 100, 60, 10),
        (30, 100, 60, 10),
        (100, 100, 60, 10),
        (60, 80, 40, 10),
        (60, 120, 80, 10),
        (60, 100, 60, 8),
    ]
    for prior, bat_opp, bowl_opp, matches in scenarios:
        bat, bowl, _, _, audit = calculate_rankings(
            batting_reliability,
            bowling_reliability,
            prior_strength=prior,
            min_batter_opportunities=bat_opp,
            min_bowler_opportunities=bowl_opp,
            min_matches=matches,
            min_baseline_coverage=80.0,
        )
        label = f"prior{prior}_bat{bat_opp}_bowl{bowl_opp}_matches{matches}"
        scenario_results[label] = {"batters": bat, "bowlers": bowl}
        for role, frame in (("batters", bat), ("bowlers", bowl)):
            rows.append({
                "scenario": label,
                "role": role,
                "candidate_count": int(len(frame)),
                "top10_player_names": " | ".join(frame.head(10).player_name.astype(str)),
                "top10_player_ids": " | ".join(frame.head(10).player_id.astype(str)),
            })
    base_label = "prior60_bat100_bowl60_matches10"
    base = scenario_results[base_label]
    stability = []
    for label, results in scenario_results.items():
        if label == base_label:
            continue
        for role in ("batters", "bowlers"):
            stability.append({
                "scenario": label,
                "role": role,
                "top10_overlap_with_primary": int(_top10_overlap(base[role], results[role])),
            })
    return pd.DataFrame(rows), {
        "primary_scenario": base_label,
        "scenarios": rows,
        "top10_membership_overlap": stability,
        "interpretation": "Top-10 overlap counts shared players versus the primary score. Rankings should be described as more stable when overlap remains high across prior and eligibility alternatives.",
    }


def save_rankings(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    batting_features: pd.DataFrame,
    bowling_features: pd.DataFrame,
    stability: pd.DataFrame,
    audit: dict,
    stability_audit: dict,
    output_dir: str = "outputs",
) -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "batting_top10": "batting_rankings_top10.csv",
        "bowling_top10": "bowling_rankings_top10.csv",
        "batting_all_candidates": "batting_candidate_scores.csv",
        "bowling_all_candidates": "bowling_candidate_scores.csv",
        "ranking_sensitivity": "ranking_sensitivity.csv",
        "ranking_audit": "ranking_audit.json",
        "ranking_stability_audit": "ranking_stability_audit.json",
    }
    batting.head(10).to_csv(out / files["batting_top10"], index=False)
    bowling.head(10).to_csv(out / files["bowling_top10"], index=False)
    batting_features.to_csv(out / files["batting_all_candidates"], index=False)
    bowling_features.to_csv(out / files["bowling_all_candidates"], index=False)
    stability.to_csv(out / files["ranking_sensitivity"], index=False)
    (out / files["ranking_audit"]).write_text(json.dumps(audit, indent=2), encoding="utf-8")
    (out / files["ranking_stability_audit"]).write_text(json.dumps(stability_audit, indent=2), encoding="utf-8")
    return {key: str(out / value) for key, value in files.items()}


def calculate_pressure_cutoff_stability(
    context: pd.DataFrame,
    primary_batters: pd.DataFrame,
    primary_bowlers: pd.DataFrame,
    *,
    fractions: tuple[float, ...] = (0.40, 0.60),
) -> tuple[pd.DataFrame, dict]:
    """Rebuild baselines/rankings under alternate 8- and 12-over collapse cutoffs."""
    from src.pressure_detection import add_pressure_flags
    from src.player_baselines import calculate_player_baselines
    from src.player_reliability import calculate_player_reliability

    rows = []
    details = []
    for fraction in fractions:
        pressured = add_pressure_flags(context, early_collapse_fraction=fraction)
        batting_base, _, bowling_base, _, _, baseline_audit = calculate_player_baselines(pressured)
        batting_rel, _, bowling_rel, _, reliability_audit = calculate_player_reliability(
            pressured, batting_base, bowling_base
        )
        bat, bowl, _, _, _ = calculate_rankings(batting_rel, bowling_rel)
        cutoff = int(np.ceil(20 * fraction))
        row = {
            "collapse_cutoff_over_standard_20": cutoff,
            "batting_candidate_count": int(len(bat)),
            "bowling_candidate_count": int(len(bowl)),
            "batting_top10": " | ".join(bat.head(10).player_name.astype(str)),
            "bowling_top10": " | ".join(bowl.head(10).player_name.astype(str)),
            "batting_top10_overlap_primary": int(_top10_overlap(primary_batters, bat)),
            "bowling_top10_overlap_primary": int(_top10_overlap(primary_bowlers, bowl)),
        }
        rows.append(row)
        details.append({
            "cutoff_over": cutoff,
            "batting_ids": bat.head(10).player_id.astype(int).tolist(),
            "bowling_ids": bowl.head(10).player_id.astype(int).tolist(),
            "baseline_batting_rows": int(len(batting_base)),
            "baseline_bowling_rows": int(len(bowling_base)),
            "reliability_batting_players": reliability_audit["batting"]["players_in_reliability_output"],
            "reliability_bowling_players": reliability_audit["bowling"]["players_in_reliability_output"],
            "baseline_batting_coverage_pct": baseline_audit["batting_context_coverage"]["peer_coverage_pct"],
            "baseline_bowling_coverage_pct": baseline_audit["bowling_context_coverage"]["peer_coverage_pct"],
        })
    result = pd.DataFrame(rows)
    audit = {
        "method": "Recalculate the entire context-matched peer baseline, player reliability evidence and rankings after changing only the early-collapse cutoff. Death-over cutoff and primary eligibility/prior settings remain fixed.",
        "primary_collapse_cutoff_over_standard_20": 10,
        "alternatives": details,
        "interpretation": "Top-10 overlap counts shared player IDs compared with the primary 10-over definition.",
    }
    return result, audit


def calculate_metric_weight_sensitivity(
    batting_reliability: pd.DataFrame, bowling_reliability: pd.DataFrame
) -> tuple[pd.DataFrame, dict]:
    """Re-rank candidates under reasonable alternative metric/score weights."""
    scenarios = {
        "primary": {"bat": BATTER_WEIGHTS, "bowl": BOWLER_WEIGHTS, "performance": 0.70},
        "equal_metrics": {
            "bat": {k: 1 / 3 for k in BATTER_WEIGHTS},
            "bowl": {k: 0.50 for k in BOWLER_WEIGHTS}, "performance": 0.70,
        },
        "runs_and_wickets_emphasis": {
            "bat": dict(zip(BATTER_WEIGHTS, [0.60, 0.25, 0.15])),
            "bowl": dict(zip(BOWLER_WEIGHTS, [0.75, 0.25])), "performance": 0.70,
        },
        "survival_and_boundary_control": {
            "bat": dict(zip(BATTER_WEIGHTS, [0.45, 0.40, 0.15])),
            "bowl": dict(zip(BOWLER_WEIGHTS, [0.50, 0.50])), "performance": 0.70,
        },
        "boundary_emphasis": {
            "bat": dict(zip(BATTER_WEIGHTS, [0.45, 0.25, 0.30])),
            "bowl": dict(zip(BOWLER_WEIGHTS, [0.70, 0.30])), "performance": 0.70,
        },
        "consistency_heavier": {
            "bat": BATTER_WEIGHTS, "bowl": BOWLER_WEIGHTS, "performance": 0.60,
        },
        "performance_heavier": {
            "bat": BATTER_WEIGHTS, "bowl": BOWLER_WEIGHTS, "performance": 0.80,
        },
    }
    base_bat = base_bowl = None
    rows: list[dict] = []
    details: dict = {}
    for name, spec in scenarios.items():
        bat, bowl, _, _, _ = calculate_rankings(
            batting_reliability, bowling_reliability,
            batter_metric_weights=spec["bat"], bowler_metric_weights=spec["bowl"],
            performance_weight=spec["performance"],
            consistency_weight=1.0 - spec["performance"],
        )
        if name == "primary":
            base_bat, base_bowl = bat, bowl
        b_overlap = len(set(base_bat.head(10).player_id) & set(bat.head(10).player_id)) if base_bat is not None else 0
        w_overlap = len(set(base_bowl.head(10).player_id) & set(bowl.head(10).player_id)) if base_bowl is not None else 0
        rows.append({
            "scenario": name,
            "batter_top10_overlap_with_primary": b_overlap,
            "bowler_top10_overlap_with_primary": w_overlap,
            "batter_candidates": int(len(bat)),
            "bowler_candidates": int(len(bowl)),
            "performance_weight": spec["performance"],
            "consistency_weight": 1.0 - spec["performance"],
        })
        details[name] = {
            "batter_weights": spec["bat"], "bowler_weights": spec["bowl"],
            "performance_weight": spec["performance"],
            "batter_top10": bat.head(10)[["rank", "player_id", "player_name", "reliability_score"]].to_dict("records"),
            "bowler_top10": bowl.head(10)[["rank", "player_id", "player_name", "reliability_score"]].to_dict("records"),
        }
    summary = pd.DataFrame(rows)
    return summary, {"scenario_definitions": details, "interpretation": "Overlap is a stability diagnostic, not proof that any weight set is correct. Primary weights are modelling choices; rank lists should be read with this sensitivity in mind."}
