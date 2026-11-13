"""Sample-size adjustment and match-to-match consistency evidence.

This module deliberately stops short of producing a final composite player
rating or top-10 list. It produces auditable, metric-level evidence for later
rating design:

* raw pressure performance relative to the matched leave-one-player-out peer;
* empirical-prior shrinkage at several opportunity strengths;
* match-level peer-adjusted performance with a small match prior; and
* consistency summaries across distinct matches.

Only metrics marked rating_eligible in player_baselines are included. Bowling
source-runs-field rate is excluded because the dataset does not contain a
complete record of bowler-charged extras.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from src.player_baselines import _add_innings_phase

DEFAULT_PRIOR_STRENGTHS = (30, 60, 100)
DEFAULT_MATCH_PRIOR_OPPORTUNITIES = 12

BATTER_CATEGORIES = (
    ("early_collapse_pressure", "is_early_collapse_pressure"),
    ("death_over_pressure", "is_death_over_pressure"),
    ("combined_pressure", "is_pressure"),
)
BOWLER_CATEGORIES = (
    ("early_collapse_context", "is_early_collapse_pressure"),
    ("death_over_context", "is_death_over_pressure"),
    ("combined_pressure_context", "is_pressure"),
)

MATCH_CONTEXT_KEYS = [
    "player_id", "player_name", "match_id", "comp_id", "comp_name",
    "match_format", "season", "innings", "innings_phase", "metric_category",
]
BASELINE_JOIN_KEYS = [
    "player_id", "comp_id", "season", "innings", "innings_phase",
    "metric_category", "metric",
]

BATTER_METRICS = (
    ("recorded_runs_per_100_balls", "recorded_runs", "balls_faced", "higher_is_better"),
    ("boundaries_per_100_balls", "flagged_boundaries", "balls_faced", "higher_is_better"),
    ("dismissals_per_100_balls", "attributed_dismissals", "balls_faced", "lower_is_better"),
)
BOWLER_METRICS = (
    (
        "bowler_wickets_per_100_candidate_legal_balls",
        "bowler_credited_wickets",
        "candidate_legal_balls",
        "higher_is_better",
    ),
    (
        "flagged_boundaries_per_100_candidate_legal_balls",
        "flagged_boundaries_conceded",
        "candidate_legal_balls",
        "lower_is_better",
    ),
)


def _bool_series(values: pd.Series) -> pd.Series:
    return values.astype("boolean").fillna(False).astype(bool)


def _normalise_text(values: pd.Series) -> pd.Series:
    return values.astype("string").str.strip().str.casefold()


def _build_category_frames(data: pd.DataFrame, role: str) -> list[tuple[str, pd.DataFrame]]:
    regular = _bool_series(data["is_regular_innings"])
    categories = BATTER_CATEGORIES if role == "batter" else BOWLER_CATEGORIES
    frames: list[tuple[str, pd.DataFrame]] = []
    for category, flag in categories:
        selected = data.loc[regular & _bool_series(data[flag])].copy()
        if not selected.empty:
            selected["metric_category"] = category
            frames.append((category, selected))

    ordinary = data.loc[regular & ~_bool_series(data["is_pressure"])].copy()
    if not ordinary.empty:
        ordinary["metric_category"] = "ordinary_baseline"
        frames.append(("ordinary_baseline", ordinary))
    return frames


def _batting_match_context(data: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    frames: list[pd.DataFrame] = []
    missing_dismissed_player_ids = 0
    non_striker_dismissals = 0
    event_only_dismissals = 0

    for _, raw in _build_category_frames(data, "batter"):
        frame = _add_innings_phase(raw)
        frame["player_id"] = pd.to_numeric(frame["striker_id"], errors="raise").astype("int64")
        frame["player_name"] = frame["striker_name"].astype("string")
        extras = _normalise_text(frame["extras_type"])
        frame["balls_faced"] = (~extras.eq("wide").fillna(False)).astype("int8")
        frame["recorded_runs"] = pd.to_numeric(frame["runs"], errors="coerce")
        if frame["recorded_runs"].isna().any() or frame["recorded_runs"].lt(0).any():
            raise ValueError("runs contains missing or negative values")
        frame["flagged_boundaries"] = (
            _bool_series(frame["is_four"]).astype("int8")
            + _bool_series(frame["is_six"]).astype("int8")
        )
        aggregate = frame.groupby(MATCH_CONTEXT_KEYS, dropna=False, sort=False).agg(
            balls_faced=("balls_faced", "sum"),
            recorded_runs=("recorded_runs", "sum"),
            flagged_boundaries=("flagged_boundaries", "sum"),
        ).reset_index()

        wickets = frame.loc[_bool_series(frame["is_wicket"])].copy()
        missing_dismissed_player_ids += int(wickets["dismissed_player_id"].isna().sum())
        non_striker_dismissals += int(
            (pd.to_numeric(wickets["dismissed_player_id"], errors="coerce")
             != pd.to_numeric(wickets["striker_id"], errors="coerce")).fillna(False).sum()
        )
        wickets = wickets.dropna(subset=["dismissed_player_id"]).copy()
        if not wickets.empty:
            wickets["player_id"] = pd.to_numeric(
                wickets["dismissed_player_id"], errors="coerce"
            )
            wickets = wickets.dropna(subset=["player_id"])
            wickets["player_id"] = wickets["player_id"].astype("int64")
            name_map = {}
            for id_col, name_col in (("striker_id", "striker_name"), ("non_striker_id", "non_striker_name")):
                pairs = frame[[id_col, name_col]].dropna().drop_duplicates(id_col)
                name_map.update(dict(zip(pairs[id_col].astype("int64"), pairs[name_col].astype(str))))
            wickets["player_name"] = wickets["player_id"].map(name_map).astype("string")
            wicket_agg = wickets.groupby(MATCH_CONTEXT_KEYS, dropna=False, sort=False).agg(
                attributed_dismissals=("is_wicket", "size")
            ).reset_index()
            aggregate = aggregate.merge(
                wicket_agg, on=MATCH_CONTEXT_KEYS, how="outer", validate="one_to_one"
            )
        else:
            aggregate["attributed_dismissals"] = 0

        for column in ("balls_faced", "recorded_runs", "flagged_boundaries", "attributed_dismissals"):
            if column not in aggregate:
                aggregate[column] = 0
            aggregate[column] = pd.to_numeric(aggregate[column], errors="coerce").fillna(0)

        event_only_dismissals += int(
            aggregate["attributed_dismissals"].gt(0).mul(aggregate["balls_faced"].eq(0)).sum()
        )
        frames.append(aggregate)

    if not frames:
        return pd.DataFrame(columns=MATCH_CONTEXT_KEYS + [
            "balls_faced", "recorded_runs", "flagged_boundaries", "attributed_dismissals"
        ]), {
            "missing_dismissed_player_ids": missing_dismissed_player_ids,
            "non_striker_dismissals": non_striker_dismissals,
            "dismissal_only_context_rows": event_only_dismissals,
        }

    result = pd.concat(frames, ignore_index=True, sort=False)
    # A player can have a batting and dismissal contribution in the same context;
    # the outer merge above keeps both. Distinct category frames never overlap
    # within a category, but separate categories are intentionally retained.
    return result, {
        "missing_dismissed_player_ids": missing_dismissed_player_ids,
        "non_striker_dismissals": non_striker_dismissals,
        "dismissal_only_context_rows": event_only_dismissals,
    }


def _bowling_match_context(data: pd.DataFrame) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    bowler_credit = {"bowled", "caught", "lbw", "stump", "hit wicket"}
    illegal_types = {"wide", "overstep"}

    for _, raw in _build_category_frames(data, "bowler"):
        frame = _add_innings_phase(raw)
        frame["player_id"] = pd.to_numeric(frame["bowler_id"], errors="raise").astype("int64")
        frame["player_name"] = frame["bowler_name"].astype("string")
        extras = _normalise_text(frame["extras_type"])
        frame["candidate_legal_balls"] = (~extras.isin(illegal_types)).astype("int8")
        frame["bowler_credited_wickets"] = (
            _bool_series(frame["is_wicket"])
            & _normalise_text(frame["dismissal_type"]).isin(bowler_credit)
        ).astype("int8")
        frame["flagged_boundaries_conceded"] = (
            _bool_series(frame["is_four"]).astype("int8")
            + _bool_series(frame["is_six"]).astype("int8")
        )
        aggregate = frame.groupby(MATCH_CONTEXT_KEYS, dropna=False, sort=False).agg(
            candidate_legal_balls=("candidate_legal_balls", "sum"),
            bowler_credited_wickets=("bowler_credited_wickets", "sum"),
            flagged_boundaries_conceded=("flagged_boundaries_conceded", "sum"),
        ).reset_index()
        frames.append(aggregate)

    if not frames:
        return pd.DataFrame(columns=MATCH_CONTEXT_KEYS + [
            "candidate_legal_balls", "bowler_credited_wickets", "flagged_boundaries_conceded"
        ])
    return pd.concat(frames, ignore_index=True, sort=False)


def _to_metric_long(
    context: pd.DataFrame,
    role: str,
) -> pd.DataFrame:
    definitions = BATTER_METRICS if role == "batter" else BOWLER_METRICS
    rows: list[pd.DataFrame] = []
    denominator_col = "balls_faced" if role == "batter" else "candidate_legal_balls"
    for metric, numerator, denominator, direction in definitions:
        selected = context.loc[pd.to_numeric(context[denominator], errors="coerce").gt(0)].copy()
        if selected.empty:
            continue
        selected["metric"] = metric
        selected["metric_numerator"] = pd.to_numeric(selected[numerator], errors="coerce").fillna(0.0)
        selected["metric_opportunities"] = pd.to_numeric(selected[denominator], errors="coerce").fillna(0.0)
        selected["metric_direction"] = direction
        rows.append(selected[MATCH_CONTEXT_KEYS + [
            "metric", "metric_numerator", "metric_opportunities", "metric_direction"
        ]])
    if not rows:
        return pd.DataFrame(columns=MATCH_CONTEXT_KEYS + [
            "metric", "metric_numerator", "metric_opportunities", "metric_direction"
        ])
    return pd.concat(rows, ignore_index=True, sort=False)


def _attach_peer_rates(
    match_metrics: pd.DataFrame,
    baseline_context: pd.DataFrame,
    role: str,
) -> tuple[pd.DataFrame, dict]:
    required = set(BASELINE_JOIN_KEYS + ["peer_rate", "rating_eligible"])
    missing = sorted(required - set(baseline_context.columns))
    if missing:
        raise ValueError(f"{role} baseline context missing columns: {missing}")

    peer = baseline_context.loc[
        baseline_context["rating_eligible"].astype(bool),
        BASELINE_JOIN_KEYS + ["peer_rate", "peer_baseline_scope"]
    ].copy()
    if peer.duplicated(BASELINE_JOIN_KEYS).any():
        raise ValueError(f"{role} baseline context is not unique on peer-join keys")

    merged = match_metrics.merge(
        peer,
        on=BASELINE_JOIN_KEYS,
        how="left",
        validate="many_to_one",
    )
    merged["baseline_matched"] = pd.to_numeric(merged["peer_rate"], errors="coerce").notna()
    merged["expected_numerator"] = (
        pd.to_numeric(merged["peer_rate"], errors="coerce")
        * merged["metric_opportunities"] / 100.0
    )
    coverage = {
        "match_metric_rows": int(len(merged)),
        "matched_rows": int(merged["baseline_matched"].sum()),
        "unmatched_rows": int((~merged["baseline_matched"]).sum()),
        "matched_row_pct": round(float(merged["baseline_matched"].mean() * 100), 2) if len(merged) else None,
        "all_opportunities": int(merged["metric_opportunities"].sum()),
        "matched_opportunities": int(merged.loc[merged["baseline_matched"], "metric_opportunities"].sum()),
    }
    return merged, coverage


def _signed_relative_performance(
    observed_rate: pd.Series,
    expected_rate: pd.Series,
    direction: pd.Series,
) -> pd.Series:
    raw = (observed_rate / expected_rate - 1.0) * 100.0
    lower_better = direction.eq("lower_is_better")
    raw.loc[lower_better] = -raw.loc[lower_better]
    raw.loc[expected_rate.le(0) | expected_rate.isna()] = np.nan
    return raw


def _summarise_player_reliability(
    attached: pd.DataFrame,
    *,
    prior_strengths: Iterable[int],
) -> pd.DataFrame:
    """Vectorised player-level shrinkage summaries by metric/category."""
    keys = ["player_id", "player_name", "metric_category", "metric", "metric_direction"]
    if attached.empty or not attached["baseline_matched"].astype(bool).any():
        return pd.DataFrame()

    work = attached.copy()
    work["_all_opportunities"] = pd.to_numeric(
        work["metric_opportunities"], errors="coerce"
    ).fillna(0.0)
    work["_matched_opportunities"] = work["_all_opportunities"].where(
        work["baseline_matched"], 0.0
    )
    work["_matched_numerator"] = pd.to_numeric(
        work["metric_numerator"], errors="coerce"
    ).where(work["baseline_matched"], 0.0).fillna(0.0)
    work["_expected_numerator"] = pd.to_numeric(
        work["expected_numerator"], errors="coerce"
    ).fillna(0.0)
    work["_all_match_id"] = work["match_id"].where(work["_all_opportunities"].gt(0))
    work["_matched_match_id"] = work["match_id"].where(
        work["baseline_matched"] & work["_all_opportunities"].gt(0)
    )

    summary = work.groupby(keys, dropna=False, sort=False).agg(
        all_opportunities=("_all_opportunities", "sum"),
        matched_opportunities=("_matched_opportunities", "sum"),
        matches_in_category=("_all_match_id", "nunique"),
        matches_with_peer_baseline=("_matched_match_id", "nunique"),
        observed_numerator_matched=("_matched_numerator", "sum"),
        expected_numerator_from_peer=("_expected_numerator", "sum"),
    ).reset_index()

    summary["baseline_coverage_pct"] = np.where(
        summary["all_opportunities"].gt(0),
        summary["matched_opportunities"] / summary["all_opportunities"] * 100.0,
        np.nan,
    )
    summary["peer_rate_opportunity_weighted"] = np.where(
        summary["matched_opportunities"].gt(0),
        summary["expected_numerator_from_peer"] / summary["matched_opportunities"] * 100.0,
        np.nan,
    )
    summary["raw_rate_matched"] = np.where(
        summary["matched_opportunities"].gt(0),
        summary["observed_numerator_matched"] / summary["matched_opportunities"] * 100.0,
        np.nan,
    )
    expected = summary["peer_rate_opportunity_weighted"]
    direction = summary["metric_direction"]

    def relative(rate: pd.Series) -> pd.Series:
        values = (rate / expected - 1.0) * 100.0
        values = values.where(direction.ne("lower_is_better"), -values)
        return values.where(expected.gt(0) & expected.notna())

    summary["raw_relative_vs_peer_pct"] = relative(summary["raw_rate_matched"])
    for prior in prior_strengths:
        if prior < 0:
            raise ValueError("prior strengths cannot be negative")
        posterior = (
            summary["observed_numerator_matched"] + prior * expected / 100.0
        ) / (summary["matched_opportunities"] + prior).replace(0, np.nan) * 100.0
        summary[f"sample_adjusted_vs_peer_pct_prior_{prior}"] = relative(posterior)

    sort_prior = 60 if 60 in prior_strengths else tuple(prior_strengths)[0]
    return summary.sort_values(
        ["metric_category", "metric", f"sample_adjusted_vs_peer_pct_prior_{sort_prior}"],
        ascending=[True, True, False], na_position="last", kind="mergesort"
    ).reset_index(drop=True)

def _build_match_consistency(
    attached: pd.DataFrame,
    *,
    match_prior_opportunities: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    matched = attached.loc[attached["baseline_matched"]].copy()
    if matched.empty:
        return pd.DataFrame(), pd.DataFrame()

    match_keys = [
        "player_id", "player_name", "metric_category", "metric", "metric_direction", "match_id"
    ]
    match_rows = matched.groupby(match_keys, dropna=False, sort=False).agg(
        observed_numerator=("metric_numerator", "sum"),
        opportunities=("metric_opportunities", "sum"),
        expected_numerator=("expected_numerator", "sum"),
        contexts_represented=("innings_phase", "nunique"),
    ).reset_index()
    match_rows["peer_expected_rate"] = (
        match_rows["expected_numerator"] / match_rows["opportunities"] * 100.0
    )
    match_rows["observed_rate"] = (
        match_rows["observed_numerator"] / match_rows["opportunities"] * 100.0
    )
    # Shrink each match toward its matched peer rate to limit one-appearance extremes.
    k = int(match_prior_opportunities)
    match_rows["match_adjusted_rate"] = (
        match_rows["observed_numerator"]
        + k * match_rows["peer_expected_rate"] / 100.0
    ) / (match_rows["opportunities"] + k) * 100.0
    match_rows["match_adjusted_vs_peer_pct"] = _signed_relative_performance(
        match_rows["match_adjusted_rate"],
        match_rows["peer_expected_rate"],
        match_rows["metric_direction"],
    )

    match_rows["_positive"] = match_rows["match_adjusted_vs_peer_pct"].gt(0).astype("int8")
    match_rows["_negative"] = match_rows["match_adjusted_vs_peer_pct"].lt(0).astype("int8")
    match_rows["_neutral"] = match_rows["match_adjusted_vs_peer_pct"].eq(0).astype("int8")
    summary_keys = ["player_id", "player_name", "metric_category", "metric", "metric_direction"]
    summary = match_rows.groupby(summary_keys, dropna=False, sort=False).agg(
        matches_with_baseline=("match_id", "nunique"),
        mean_match_adjusted_vs_peer_pct=("match_adjusted_vs_peer_pct", "mean"),
        median_match_adjusted_vs_peer_pct=("match_adjusted_vs_peer_pct", "median"),
        std_match_adjusted_vs_peer_pct=("match_adjusted_vs_peer_pct", "std"),
        positive_match_count=("_positive", "sum"),
        negative_match_count=("_negative", "sum"),
        neutral_match_count=("_neutral", "sum"),
        median_match_opportunities=("opportunities", "median"),
        total_matched_opportunities=("opportunities", "sum"),
        maximum_single_match_opportunities=("opportunities", "max"),
    ).reset_index()
    summary["positive_match_share_pct"] = (
        summary["positive_match_count"] / summary["matches_with_baseline"] * 100.0
    )
    summary["negative_match_share_pct"] = (
        summary["negative_match_count"] / summary["matches_with_baseline"] * 100.0
    )
    summary["largest_match_opportunity_share_pct"] = (
        summary["maximum_single_match_opportunities"]
        / summary["total_matched_opportunities"] * 100.0
    )
    return match_rows.sort_values(match_keys, kind="mergesort"), summary


def calculate_player_reliability(
    pressured: pd.DataFrame,
    batting_baseline_context: pd.DataFrame,
    bowling_baseline_context: pd.DataFrame,
    *,
    prior_strengths: Iterable[int] = DEFAULT_PRIOR_STRENGTHS,
    match_prior_opportunities: int = DEFAULT_MATCH_PRIOR_OPPORTUNITIES,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Create sample-adjusted player metrics and match-consistency evidence.

    Returns:
        batting reliability summary, batting match consistency rows,
        bowling reliability summary, bowling match consistency rows, audit.

    The outputs are metric-level components, not a composite player rating.
    """
    prior_strengths = tuple(sorted({int(x) for x in prior_strengths}))
    if not prior_strengths or any(x < 0 for x in prior_strengths):
        raise ValueError("prior_strengths must contain non-negative integers")
    if match_prior_opportunities < 0:
        raise ValueError("match_prior_opportunities cannot be negative")

    batting_context, batting_audit = _batting_match_context(pressured)
    bowling_context = _bowling_match_context(pressured)
    batting_long = _to_metric_long(batting_context, "batter")
    bowling_long = _to_metric_long(bowling_context, "bowler")

    batting_attached, batting_coverage = _attach_peer_rates(
        batting_long, batting_baseline_context, "batting"
    )
    bowling_attached, bowling_coverage = _attach_peer_rates(
        bowling_long, bowling_baseline_context, "bowling"
    )

    batting_summary = _summarise_player_reliability(
        batting_attached, prior_strengths=prior_strengths
    )
    bowling_summary = _summarise_player_reliability(
        bowling_attached, prior_strengths=prior_strengths
    )
    batting_match_rows, batting_consistency = _build_match_consistency(
        batting_attached, match_prior_opportunities=match_prior_opportunities
    )
    bowling_match_rows, bowling_consistency = _build_match_consistency(
        bowling_attached, match_prior_opportunities=match_prior_opportunities
    )

    def merge_consistency(summary: pd.DataFrame, consistency: pd.DataFrame) -> pd.DataFrame:
        if summary.empty or consistency.empty:
            return summary
        keys = ["player_id", "player_name", "metric_category", "metric", "metric_direction"]
        return summary.merge(consistency, on=keys, how="left", validate="one_to_one")

    batting_summary = merge_consistency(batting_summary, batting_consistency)
    bowling_summary = merge_consistency(bowling_summary, bowling_consistency)

    audit = {
        "module": "player_reliability",
        "purpose": "Produce sample-size-adjusted peer-relative performance and match-to-match consistency evidence; no composite ranking is created.",
        "prior_strengths_opportunities": list(prior_strengths),
        "primary_comparison_prior_for_sorting_only": 60 if 60 in prior_strengths else prior_strengths[0],
        "match_prior_opportunities": int(match_prior_opportunities),
        "shrinkage_method": "Posterior-style rate = (observed numerator + prior opportunities * matched peer rate) / (matched opportunities + prior opportunities). Reported relative difference is direction-adjusted versus the same peer rate.",
        "match_consistency_method": "Each player-match metric is shrunk toward its context-matched peer rate using the configured match prior. Consistency is described by mean/median adjusted match performance, dispersion, and positive/negative match shares.",
        "batting": {
            **batting_coverage,
            **batting_audit,
            "players_in_reliability_output": int(batting_summary["player_id"].nunique()) if not batting_summary.empty else 0,
            "match_rows_with_baseline": int(len(batting_match_rows)),
            "metrics": [x[0] for x in BATTER_METRICS],
        },
        "bowling": {
            **bowling_coverage,
            "players_in_reliability_output": int(bowling_summary["player_id"].nunique()) if not bowling_summary.empty else 0,
            "match_rows_with_baseline": int(len(bowling_match_rows)),
            "metrics": [x[0] for x in BOWLER_METRICS],
            "excluded_metric": "source_runs_field_per_100_candidate_legal_balls (incomplete bowler extras)",
        },
        "limitations": [
            "A fixed prior-opportunity grid is a transparent shrinkage sensitivity analysis, not a fitted empirical-Bayes prior.",
            "Match consistency is computed only for match-context rows with a supported peer baseline.",
            "A positive match share does not by itself establish reliability; match counts and opportunity coverage must also be considered.",
            "Bowling early-collapse context describes bowling against a batting side that has lost five wickets early; it is not automatically pressure on the bowler.",
            "No combined composite rating, eligibility threshold, or top-10 ranking is produced by this module.",
        ],
        "rankings_created": False,
    }
    return batting_summary, batting_match_rows, bowling_summary, bowling_match_rows, audit


def save_player_reliability(
    batting_summary: pd.DataFrame,
    batting_match_rows: pd.DataFrame,
    bowling_summary: pd.DataFrame,
    bowling_match_rows: pd.DataFrame,
    audit: dict,
    output_dir: str = "outputs",
) -> dict:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "batting_reliability": "batting_reliability.csv",
        "batting_match_consistency": "batting_match_consistency.csv",
        "bowling_reliability": "bowling_reliability.csv",
        "bowling_match_consistency": "bowling_match_consistency.csv",
        "reliability_audit": "player_reliability_audit.json",
    }
    batting_summary.to_csv(output / files["batting_reliability"], index=False)
    batting_match_rows.to_csv(output / files["batting_match_consistency"], index=False)
    bowling_summary.to_csv(output / files["bowling_reliability"], index=False)
    bowling_match_rows.to_csv(output / files["bowling_match_consistency"], index=False)
    (output / files["reliability_audit"]).write_text(
        json.dumps(audit, indent=2), encoding="utf-8"
    )
    return {key: str(output / filename) for key, filename in files.items()}
