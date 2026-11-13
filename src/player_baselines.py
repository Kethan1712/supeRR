"""Context-aware peer (league) and individual player baseline comparisons.

This module does NOT rank players or create a composite score. It builds
context-matched peer benchmarks and compares each player's ordinary and
pressure performance relative to those peers.

A key design choice is to compare *relative standing* rather than subtract raw
rates across different innings phases. For example, death-over strike rates
are naturally higher than middle-over strike rates. Each player's observed
rate is therefore compared with a peer rate from the same competition/format,
innings, phase, and metric category. The player's ordinary relative standing
can then be compared with their pressure relative standing.

Peer rates are opportunity-weighted pooled rates calculated leave-one-player-
out. Competition-specific benchmarks are preferred; sparse groups fall back
to format-season and then format-wide cohorts. All fallback choices are
recorded in the outputs.

Source-data limitations remain explicit:
- Batting uses the source `runs` field, labelled recorded runs.
- Bowling uses candidate legal balls (excluding wide and Overstep rows).
- Bowling source-runs rate is diagnostic only, not official runs conceded or
  economy rate; complete bowler-charged extras are unavailable.
- Early-collapse rows in bowling outputs describe bowling *against a batting
  side that has collapsed*, not necessarily pressure on the bowler.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

BOWLER_CREDITED_DISMISSALS = {
    "bowled", "caught", "lbw", "stump", "hit wicket"
}
KNOWN_ILLEGAL_DELIVERY_TYPES = {"wide", "overstep"}

# A comparison cohort must contain other players, not the player being scored.
DEFAULT_MIN_PEER_OPPORTUNITIES = 300
DEFAULT_MIN_PEER_PLAYERS = 8
DEFAULT_MIN_FALLBACK_OPPORTUNITIES = 50
DEFAULT_MIN_FALLBACK_PLAYERS = 3

CONTEXT_KEYS = [
    "player_id", "player_name", "comp_id", "comp_name", "match_format",
    "season", "innings", "innings_phase", "metric_category",
]
PEER_SCOPE_LEVELS = [
    ("competition_innings_phase", ["comp_id", "innings", "innings_phase", "metric_category"]),
    ("format_season_innings_phase", ["match_format", "season", "innings", "innings_phase", "metric_category"]),
    ("format_innings_phase", ["match_format", "innings", "innings_phase", "metric_category"]),
]

BATTER_METRICS = [
    {
        "metric": "recorded_runs_per_100_balls",
        "numerator": "recorded_runs",
        "denominator": "balls_faced",
        "scale": 100.0,
        "direction": "higher_is_better",
        "rating_eligible": True,
        "interpretation": "Recorded source runs per 100 balls faced; not asserted as fully scorecard-verified batter runs.",
    },
    {
        "metric": "boundaries_per_100_balls",
        "numerator": "flagged_boundaries",
        "denominator": "balls_faced",
        "scale": 100.0,
        "direction": "higher_is_better",
        "rating_eligible": True,
        "interpretation": "Source is_four plus is_six flags per 100 balls faced.",
    },
    {
        "metric": "dismissals_per_100_balls",
        "numerator": "attributed_dismissals",
        "denominator": "balls_faced",
        "scale": 100.0,
        "direction": "lower_is_better",
        "rating_eligible": True,
        "interpretation": "Dismissals attributed through dismissed_player_id per 100 balls faced; missing IDs are not guessed.",
    },
]

BOWLER_METRICS = [
    {
        "metric": "bowler_wickets_per_100_candidate_legal_balls",
        "numerator": "bowler_credited_wickets",
        "denominator": "candidate_legal_balls",
        "scale": 100.0,
        "direction": "higher_is_better",
        "rating_eligible": True,
        "interpretation": "Bowler-creditable wickets per 100 candidate legal deliveries.",
    },
    {
        "metric": "flagged_boundaries_per_100_candidate_legal_balls",
        "numerator": "flagged_boundaries_conceded",
        "denominator": "candidate_legal_balls",
        "scale": 100.0,
        "direction": "lower_is_better",
        "rating_eligible": True,
        "interpretation": "Boundary flags conceded per 100 candidate legal deliveries.",
    },
    {
        "metric": "source_runs_field_per_100_candidate_legal_balls",
        "numerator": "source_runs_field_sum",
        "denominator": "candidate_legal_balls",
        "scale": 100.0,
        "direction": "lower_is_better",
        "rating_eligible": False,
        "interpretation": "Diagnostic only: source runs field per 100 candidate legal deliveries; not total bowler runs conceded.",
    },
]


def _bool_series(values: pd.Series) -> pd.Series:
    return values.astype("boolean").fillna(False).astype(bool)


def _normalise_text(values: pd.Series) -> pd.Series:
    return values.astype("string").str.strip().str.casefold()


def _add_innings_phase(data: pd.DataFrame) -> pd.DataFrame:
    """Add powerplay/middle/death phase using each innings allocation.

    For a 20-over innings this produces overs 1-6, 7-15, and 16-20. Shortened
    innings use the same 30%/75% proportional boundaries as the pressure logic.
    """
    required = {"overid", "allocation_overs", "is_regular_innings"}
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"pressure dataframe is missing phase columns: {missing}")

    result = data.copy()
    allocation = pd.to_numeric(result["allocation_overs"], errors="coerce")
    over = pd.to_numeric(result["overid"], errors="coerce")
    regular = _bool_series(result["is_regular_innings"])
    if allocation.loc[regular].isna().any() or allocation.loc[regular].le(0).any():
        raise ValueError("Regular innings contain missing or invalid allocated overs")
    if over.loc[regular].isna().any():
        raise ValueError("Regular innings contain missing overid values")

    powerplay_end = np.ceil(allocation * 0.30)
    death_start = np.floor(allocation * 0.75) + 1
    phase = pd.Series("additional_innings_unclassified", index=result.index, dtype="object")
    phase.loc[regular & over.le(powerplay_end)] = "powerplay"
    phase.loc[regular & over.gt(powerplay_end) & over.lt(death_start)] = "middle"
    phase.loc[regular & over.ge(death_start)] = "death"
    result["innings_phase"] = phase
    return result


def _category_frames(data: pd.DataFrame, role: str) -> list[tuple[str, pd.DataFrame]]:
    regular = _bool_series(data["is_regular_innings"])
    if role == "batter":
        pressure_groups = [
            ("early_collapse_pressure", "is_early_collapse_pressure"),
            ("death_over_pressure", "is_death_over_pressure"),
            ("combined_pressure", "is_pressure"),
        ]
    elif role == "bowler":
        pressure_groups = [
            ("early_collapse_context", "is_early_collapse_pressure"),
            ("death_over_context", "is_death_over_pressure"),
            ("combined_pressure_context", "is_pressure"),
        ]
    else:
        raise ValueError("role must be 'batter' or 'bowler'")

    frames: list[tuple[str, pd.DataFrame]] = []
    for category, flag in pressure_groups:
        subset = data.loc[regular & _bool_series(data[flag])].copy()
        if not subset.empty:
            subset["metric_category"] = category
            frames.append((category, subset))

    ordinary = data.loc[regular & ~_bool_series(data["is_pressure"])].copy()
    if not ordinary.empty:
        ordinary["metric_category"] = "ordinary_baseline"
        frames.append(("ordinary_baseline", ordinary))
    return frames


def _player_names(data: pd.DataFrame) -> pd.Series:
    pairs = [
        data[["striker_id", "striker_name"]].rename(
            columns={"striker_id": "player_id", "striker_name": "player_name"}
        ),
        data[["non_striker_id", "non_striker_name"]].rename(
            columns={"non_striker_id": "player_id", "non_striker_name": "player_name"}
        ),
    ]
    names = pd.concat(pairs, ignore_index=True).dropna(subset=["player_id", "player_name"])
    names["player_id"] = pd.to_numeric(names["player_id"], errors="coerce")
    names = names.dropna(subset=["player_id"]).drop_duplicates("player_id", keep="first")
    return names.set_index("player_id")["player_name"]


def _build_batting_context(data: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {
        "match_id", "innings", "comp_id", "comp_name", "match_format", "season",
        "striker_id", "striker_name", "non_striker_id", "non_striker_name",
        "runs", "is_four", "is_six", "is_wicket", "dismissed_player_id",
        "extras_type", "is_regular_innings", "is_early_collapse_pressure",
        "is_death_over_pressure", "is_pressure", "allocation_overs", "overid",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"pressure dataframe is missing batting baseline fields: {missing}")
    if data["striker_id"].isna().any():
        raise ValueError("striker_id contains missing values")

    source = _add_innings_phase(data)
    names = _player_names(source)
    groups: list[pd.DataFrame] = []
    missing_dismissal_ids = 0

    for category, frame in _category_frames(source, "batter"):
        frame = frame.copy()
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
        context_keys = [
            "player_id", "player_name", "comp_id", "comp_name", "match_format",
            "season", "innings", "innings_phase", "metric_category",
        ]
        batter = frame.groupby(context_keys, dropna=False, sort=False).agg(
            balls_faced=("balls_faced", "sum"),
            recorded_runs=("recorded_runs", "sum"),
            flagged_boundaries=("flagged_boundaries", "sum"),
            matches_represented=("match_id", "nunique"),
        ).reset_index()

        wickets = frame.loc[
            _bool_series(frame["is_wicket"])
        ].copy()
        missing_dismissal_ids += int(wickets["dismissed_player_id"].isna().sum())
        wickets = wickets.dropna(subset=["dismissed_player_id"])
        if not wickets.empty:
            wickets["player_id"] = pd.to_numeric(
                wickets["dismissed_player_id"], errors="coerce"
            )
            wickets = wickets.dropna(subset=["player_id"])
            wickets["player_id"] = wickets["player_id"].astype("int64")
            wickets["player_name"] = wickets["player_id"].map(names).astype("string")
            dismissals = wickets.groupby(context_keys, dropna=False, sort=False).agg(
                attributed_dismissals=("is_wicket", "size"),
                dismissal_matches=("match_id", "nunique"),
            ).reset_index()
            batter = batter.merge(
                dismissals, on=context_keys, how="outer", validate="one_to_one"
            )
        else:
            batter["attributed_dismissals"] = 0
            batter["dismissal_matches"] = 0

        for col in ["balls_faced", "recorded_runs", "flagged_boundaries", "matches_represented",
                    "attributed_dismissals", "dismissal_matches"]:
            if col not in batter:
                batter[col] = 0
            batter[col] = pd.to_numeric(batter[col], errors="coerce").fillna(0)
        batter["matches_represented"] = batter[["matches_represented", "dismissal_matches"]].max(axis=1)
        batter = batter.drop(columns=["dismissal_matches"])
        groups.append(batter)

    if not groups:
        return pd.DataFrame(columns=CONTEXT_KEYS + ["balls_faced", "recorded_runs", "flagged_boundaries", "attributed_dismissals", "matches_represented"]), {
            "missing_dismissal_ids": missing_dismissal_ids
        }
    context = pd.concat(groups, ignore_index=True, sort=False)
    return context, {"missing_dismissal_ids": missing_dismissal_ids}


def _build_bowling_context(data: pd.DataFrame) -> pd.DataFrame:
    required = {
        "match_id", "innings", "comp_id", "comp_name", "match_format", "season",
        "bowler_id", "bowler_name", "runs", "is_four", "is_six", "is_wicket",
        "dismissal_type", "extras_type", "is_regular_innings",
        "is_early_collapse_pressure", "is_death_over_pressure", "is_pressure",
        "allocation_overs", "overid",
    }
    missing = sorted(required - set(data.columns))
    if missing:
        raise ValueError(f"pressure dataframe is missing bowling baseline fields: {missing}")
    if data["bowler_id"].isna().any():
        raise ValueError("bowler_id contains missing values")

    source = _add_innings_phase(data)
    groups: list[pd.DataFrame] = []
    context_keys = [
        "player_id", "player_name", "comp_id", "comp_name", "match_format",
        "season", "innings", "innings_phase", "metric_category",
    ]
    for category, frame in _category_frames(source, "bowler"):
        frame = frame.copy()
        frame["player_id"] = pd.to_numeric(frame["bowler_id"], errors="raise").astype("int64")
        frame["player_name"] = frame["bowler_name"].astype("string")
        extras = _normalise_text(frame["extras_type"])
        frame["candidate_legal_ball"] = ~extras.isin(KNOWN_ILLEGAL_DELIVERY_TYPES)
        frame["source_runs_field"] = pd.to_numeric(frame["runs"], errors="coerce")
        if frame["source_runs_field"].isna().any() or frame["source_runs_field"].lt(0).any():
            raise ValueError("runs contains missing or negative values")
        dismissal = _normalise_text(frame["dismissal_type"])
        frame["bowler_credited_wicket"] = (
            _bool_series(frame["is_wicket"])
            & dismissal.isin(BOWLER_CREDITED_DISMISSALS)
        )
        frame["flagged_boundaries_conceded"] = (
            _bool_series(frame["is_four"]).astype("int8")
            + _bool_series(frame["is_six"]).astype("int8")
        )
        aggregate = frame.groupby(context_keys, dropna=False, sort=False).agg(
            candidate_legal_balls=("candidate_legal_ball", "sum"),
            source_runs_field_sum=("source_runs_field", "sum"),
            bowler_credited_wickets=("bowler_credited_wicket", "sum"),
            flagged_boundaries_conceded=("flagged_boundaries_conceded", "sum"),
            matches_represented=("match_id", "nunique"),
        ).reset_index()
        groups.append(aggregate)

    if not groups:
        return pd.DataFrame(columns=CONTEXT_KEYS + [
            "candidate_legal_balls", "source_runs_field_sum",
            "bowler_credited_wickets", "flagged_boundaries_conceded",
            "matches_represented",
        ])
    return pd.concat(groups, ignore_index=True, sort=False)


def _peer_baselines_for_metric(
    context: pd.DataFrame,
    metric_definition: dict,
    *,
    min_peer_opportunities: int,
    min_peer_players: int,
    min_fallback_opportunities: int,
    min_fallback_players: int,
) -> pd.DataFrame:
    """Attach a leave-one-player-out peer rate to every player-context row."""
    numerator = metric_definition["numerator"]
    denominator = metric_definition["denominator"]
    scale = float(metric_definition["scale"])
    metric_rows = context[CONTEXT_KEYS + ["matches_represented", numerator, denominator]].copy()
    metric_rows = metric_rows.loc[pd.to_numeric(metric_rows[denominator], errors="coerce").gt(0)].copy().reset_index(drop=True)
    metric_rows["metric"] = metric_definition["metric"]
    metric_rows["metric_direction"] = metric_definition["direction"]
    metric_rows["rating_eligible"] = bool(metric_definition["rating_eligible"])
    metric_rows["player_numerator"] = pd.to_numeric(metric_rows[numerator], errors="coerce").fillna(0.0)
    metric_rows["player_opportunities"] = pd.to_numeric(metric_rows[denominator], errors="coerce").fillna(0.0)
    metric_rows["player_rate"] = (
        metric_rows["player_numerator"] / metric_rows["player_opportunities"] * scale
    )

    metric_rows["league_rate"] = np.nan
    metric_rows["league_opportunities"] = np.nan
    metric_rows["league_players"] = np.nan
    metric_rows["peer_rate"] = np.nan
    metric_rows["peer_opportunities"] = np.nan
    metric_rows["peer_players"] = np.nan
    metric_rows["peer_baseline_scope"] = pd.NA
    metric_rows["peer_rate_direction"] = metric_definition["direction"]

    for scope_name, scope_keys in PEER_SCOPE_LEVELS:
        total = metric_rows.groupby(
            scope_keys, dropna=False, sort=False
        ).agg(
            cohort_numerator=("player_numerator", "sum"),
            cohort_opportunities=("player_opportunities", "sum"),
            cohort_players=("player_id", "nunique"),
        ).reset_index()
        own = metric_rows.groupby(
            scope_keys + ["player_id"], dropna=False, sort=False
        ).agg(
            own_numerator=("player_numerator", "sum"),
            own_opportunities=("player_opportunities", "sum"),
        ).reset_index()
        candidate = metric_rows[scope_keys + ["player_id"]].merge(
            total, on=scope_keys, how="left", validate="many_to_one"
        ).merge(
            own, on=scope_keys + ["player_id"], how="left", validate="many_to_one"
        )
        peer_num = candidate["cohort_numerator"] - candidate["own_numerator"]
        peer_den = candidate["cohort_opportunities"] - candidate["own_opportunities"]
        peer_players = candidate["cohort_players"] - 1
        if scope_name == "format_innings_phase":
            enough = (
                peer_den.ge(min_fallback_opportunities)
                & peer_players.ge(min_fallback_players)
            )
        else:
            enough = (
                peer_den.ge(min_peer_opportunities)
                & peer_players.ge(min_peer_players)
            )
        unassigned = metric_rows["peer_rate"].isna()
        use = unassigned & enough & peer_den.gt(0)
        if use.any():
            metric_rows.loc[use, "league_rate"] = (
                candidate.loc[use, "cohort_numerator"]
                / candidate.loc[use, "cohort_opportunities"] * scale
            ).to_numpy()
            metric_rows.loc[use, "league_opportunities"] = candidate.loc[use, "cohort_opportunities"].to_numpy()
            metric_rows.loc[use, "league_players"] = candidate.loc[use, "cohort_players"].to_numpy()
            metric_rows.loc[use, "peer_rate"] = (peer_num.loc[use] / peer_den.loc[use] * scale).to_numpy()
            metric_rows.loc[use, "peer_opportunities"] = peer_den.loc[use].to_numpy()
            metric_rows.loc[use, "peer_players"] = peer_players.loc[use].to_numpy()
            metric_rows.loc[use, "peer_baseline_scope"] = scope_name

    direction = metric_definition["direction"]
    if direction == "higher_is_better":
        metric_rows["relative_performance_vs_peer_pct"] = (
            (metric_rows["player_rate"] / metric_rows["peer_rate"] - 1.0) * 100.0
        )
    else:
        metric_rows["relative_performance_vs_peer_pct"] = (
            (1.0 - metric_rows["player_rate"] / metric_rows["peer_rate"]) * 100.0
        )
    metric_rows.loc[metric_rows["peer_rate"].le(0), "relative_performance_vs_peer_pct"] = np.nan

    metric_rows["peer_baseline_cohort"] = ""
    scope = metric_rows["peer_baseline_scope"]
    competition_mask = scope.eq("competition_innings_phase")
    season_mask = scope.eq("format_season_innings_phase")
    format_mask = scope.eq("format_innings_phase")
    metric_rows.loc[competition_mask, "peer_baseline_cohort"] = (
        "competition=" + metric_rows.loc[competition_mask, "comp_id"].astype(str)
        + " | innings=" + metric_rows.loc[competition_mask, "innings"].astype(str)
        + " | phase=" + metric_rows.loc[competition_mask, "innings_phase"].astype(str)
    )
    metric_rows.loc[season_mask, "peer_baseline_cohort"] = (
        "format=" + metric_rows.loc[season_mask, "match_format"].astype(str)
        + " | season=" + metric_rows.loc[season_mask, "season"].astype(str)
        + " | innings=" + metric_rows.loc[season_mask, "innings"].astype(str)
        + " | phase=" + metric_rows.loc[season_mask, "innings_phase"].astype(str)
    )
    metric_rows.loc[format_mask, "peer_baseline_cohort"] = (
        "format=" + metric_rows.loc[format_mask, "match_format"].astype(str)
        + " | innings=" + metric_rows.loc[format_mask, "innings"].astype(str)
        + " | phase=" + metric_rows.loc[format_mask, "innings_phase"].astype(str)
    )

    return metric_rows


def _summarise_player_metrics(context_metrics: pd.DataFrame) -> pd.DataFrame:
    """Vectorised player-level roll-up of context-matched peer performance."""
    if context_metrics.empty:
        return pd.DataFrame()
    keys = ["player_id", "player_name", "metric_category", "metric", "metric_direction", "rating_eligible"]
    frame = context_metrics.copy()
    frame["_opportunities"] = pd.to_numeric(frame["player_opportunities"], errors="coerce").fillna(0.0)
    frame["_matched_opportunities"] = frame["_opportunities"].where(frame["peer_rate"].notna(), 0.0)
    frame["_peer_weighted"] = (pd.to_numeric(frame["peer_rate"], errors="coerce") * frame["_opportunities"]).fillna(0.0)
    frame["_league_weighted"] = (pd.to_numeric(frame["league_rate"], errors="coerce") * frame["_opportunities"]).fillna(0.0)
    frame["_relative_weighted"] = (pd.to_numeric(frame["relative_performance_vs_peer_pct"], errors="coerce") * frame["_opportunities"]).fillna(0.0)
    frame["_peer_opportunities_min"] = pd.to_numeric(frame["peer_opportunities"], errors="coerce")
    frame["_peer_players_min"] = pd.to_numeric(frame["peer_players"], errors="coerce")
    summary = frame.groupby(keys, dropna=False, sort=False).agg(
        opportunities=("_opportunities", "sum"),
        matched_peer_opportunities=("_matched_opportunities", "sum"),
        total_numerator=("player_numerator", "sum"),
        peer_weighted_numerator=("_peer_weighted", "sum"),
        league_weighted_numerator=("_league_weighted", "sum"),
        relative_weighted_sum=("_relative_weighted", "sum"),
        context_groups=("player_id", "size"),
        context_groups_with_peer=("peer_rate", lambda values: int(values.notna().sum())),
        minimum_peer_opportunities_in_matched_context=("_peer_opportunities_min", "min"),
        minimum_peer_players_in_matched_context=("_peer_players_min", "min"),
    ).reset_index()
    matched = summary["matched_peer_opportunities"].gt(0)
    summary["player_rate_pooled"] = np.where(
        summary["opportunities"].gt(0),
        summary["total_numerator"] / summary["opportunities"] * 100.0, np.nan
    )
    summary["peer_rate_weighted"] = np.where(
        matched, summary["peer_weighted_numerator"] / summary["matched_peer_opportunities"], np.nan
    )
    summary["league_rate_weighted"] = np.where(
        matched, summary["league_weighted_numerator"] / summary["matched_peer_opportunities"], np.nan
    )
    summary["relative_performance_vs_peer_pct"] = np.where(
        matched, summary["relative_weighted_sum"] / summary["matched_peer_opportunities"], np.nan
    )
    summary["peer_coverage_pct"] = np.where(
        summary["opportunities"].gt(0),
        summary["matched_peer_opportunities"] / summary["opportunities"] * 100.0, np.nan
    )
    summary["minimum_peer_players_in_matched_context"] = summary["minimum_peer_players_in_matched_context"].fillna(0).astype(int)

    ordinary = summary.loc[summary["metric_category"].eq("ordinary_baseline"), [
        "player_id", "metric", "relative_performance_vs_peer_pct"
    ]].rename(columns={
        "relative_performance_vs_peer_pct": "ordinary_relative_performance_vs_peer_pct"
    })
    summary = summary.merge(ordinary, on=["player_id", "metric"], how="left", validate="many_to_one")
    is_pressure = ~summary["metric_category"].eq("ordinary_baseline")
    summary["relative_change_vs_ordinary_pct"] = np.nan
    summary.loc[is_pressure, "relative_change_vs_ordinary_pct"] = (
        summary.loc[is_pressure, "relative_performance_vs_peer_pct"]
        - summary.loc[is_pressure, "ordinary_relative_performance_vs_peer_pct"]
    )
    summary["interpretation"] = np.where(
        summary["rating_eligible"],
        "Positive relative performance means above peer benchmark; positive relative change means improved peer standing under this context.",
        "Diagnostic only; not eligible for a final rating because source runs are incomplete as bowler-conceded runs.",
    )
    return summary.sort_values(
        ["metric_category", "metric", "relative_performance_vs_peer_pct"],
        ascending=[True, True, False], na_position="last", kind="mergesort"
    ).reset_index(drop=True)

def _extract_peer_benchmarks(role_context: pd.DataFrame) -> pd.DataFrame:
    # This file is the actual full-cohort league average (including all players).
    # Leave-one-player-out peer comparators remain in the detailed context file.
    cols = [
        "metric", "metric_category", "peer_baseline_scope", "peer_baseline_cohort",
        "league_rate", "league_opportunities", "league_players", "peer_rate_direction",
    ]
    if role_context.empty:
        return pd.DataFrame(columns=cols)
    return (
        role_context.loc[role_context["league_rate"].notna(), cols]
        .drop_duplicates()
        .sort_values(["metric_category", "metric", "peer_baseline_scope", "peer_baseline_cohort"], kind="mergesort")
        .reset_index(drop=True)
    )


def calculate_player_baselines(
    pressured: pd.DataFrame,
    *,
    min_peer_opportunities: int = DEFAULT_MIN_PEER_OPPORTUNITIES,
    min_peer_players: int = DEFAULT_MIN_PEER_PLAYERS,
    min_fallback_opportunities: int = DEFAULT_MIN_FALLBACK_OPPORTUNITIES,
    min_fallback_players: int = DEFAULT_MIN_FALLBACK_PLAYERS,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Calculate batting and bowling peer/individual baseline comparisons.

    Returns, in order: batting context, batting player summary, bowling
    context, bowling player summary, peer benchmark table, and audit.
    """
    if min_peer_opportunities < 1 or min_peer_players < 2:
        raise ValueError("Peer thresholds must require positive opportunities and at least two players")
    if min_fallback_opportunities < 1 or min_fallback_players < 2:
        raise ValueError("Fallback thresholds must require positive opportunities and at least two players")

    batting_base, batting_aux_audit = _build_batting_context(pressured)
    bowling_base = _build_bowling_context(pressured)

    def process_role(base: pd.DataFrame, definitions: list[dict]):
        pieces = [
            _peer_baselines_for_metric(
                base,
                definition,
                min_peer_opportunities=min_peer_opportunities,
                min_peer_players=min_peer_players,
                min_fallback_opportunities=min_fallback_opportunities,
                min_fallback_players=min_fallback_players,
            )
            for definition in definitions
        ]
        context_metrics = pd.concat(pieces, ignore_index=True, sort=False) if pieces else pd.DataFrame()
        summary = _summarise_player_metrics(context_metrics)
        return context_metrics, summary

    batting_context, batting_summary = process_role(batting_base, BATTER_METRICS)
    bowling_context, bowling_summary = process_role(bowling_base, BOWLER_METRICS)
    league_benchmarks = pd.concat(
        [
            _extract_peer_benchmarks(batting_context).assign(role="batter"),
            _extract_peer_benchmarks(bowling_context).assign(role="bowler"),
        ],
        ignore_index=True,
        sort=False,
    )

    def coverage(frame: pd.DataFrame) -> dict:
        if frame.empty:
            return {"context_metric_rows": 0, "rows_with_peer_baseline": 0, "peer_coverage_pct": None}
        n = int(frame["peer_rate"].notna().sum())
        return {
            "context_metric_rows": int(len(frame)),
            "rows_with_peer_baseline": n,
            "peer_coverage_pct": round(n / len(frame) * 100, 2),
            "unmatched_context_rows": int(len(frame) - n),
            "scope_counts": {
                str(k): int(v)
                for k, v in frame["peer_baseline_scope"].fillna("no_supported_peer_group").value_counts().items()
            },
        }

    audit = {
        "module": "player_baselines",
        "purpose": (
            "Compare pressure and ordinary performance with context-matched peer averages, "
            "then compare the player's relative standing in pressure contexts with their own ordinary standing."
        ),
        "method": {
            "league_average": "Opportunity-weighted pooled rate across all players in the selected peer cohort, including the subject player.",
            "peer_comparator": "Opportunity-weighted pooled rate among other players (leave-one-player-out); this is used for relative-performance calculations to avoid self-benchmarking.",
            "peer_scope_priority": [name for name, _ in PEER_SCOPE_LEVELS],
            "primary_peer_support_requirement": {
                "other_player_opportunities": min_peer_opportunities,
                "other_players": min_peer_players,
            },
            "format_wide_fallback_support_requirement": {
                "other_player_opportunities": min_fallback_opportunities,
                "other_players": min_fallback_players,
            },
            "innings_phase": "Powerplay is first 30% of allocated overs; death is final 25%; remaining overs are middle. Standard 20-over phases are 1-6, 7-15, 16-20.",
            "relative_performance": "For higher-is-better metrics, (player rate / peer rate - 1) * 100. For lower-is-better metrics, (1 - player rate / peer rate) * 100. Positive means better than peer average.",
            "relative_change_vs_ordinary": "Pressure relative-performance percentage minus the same player's ordinary relative-performance percentage. This compares league-relative standing, not raw rates across different phases.",
            "raw_player_rate_caveat": "Player pooled rate and peer weighted rate are descriptive; context-adjusted relative-performance fields should be used for cross-phase interpretation.",
        },
        "metric_definitions": {
            "batting": BATTER_METRICS,
            "bowling": BOWLER_METRICS,
        },
        "bowling_pressure_caveat": (
            "Early-collapse bowling rows describe bowling against a batting side under collapse pressure; "
            "they are not automatically classified as pressure on the bowler. Death-over performance is "
            "the primary available bowling pressure context."
        ),
        "source_limitations": {
            "runs": "The source runs field is used as recorded and is not assumed to be a complete official batting/scorecard total.",
            "bowling_runs": "Source runs field is incomplete as bowler-charged runs because extras are missing; its baseline metric is diagnostic-only.",
            "economy_and_dot_balls": "No conventional bowling economy rate or true dot-ball rate is created.",
            "candidate_legal_balls": "Excludes wide and Overstep rows; retains the single Penalty-coded record in the primary denominator, matching the existing descriptive bowling module.",
        },
        "batting_context_coverage": coverage(batting_context),
        "bowling_context_coverage": coverage(bowling_context),
        "batting_players_in_summary": int(batting_summary["player_id"].nunique()) if not batting_summary.empty else 0,
        "bowling_players_in_summary": int(bowling_summary["player_id"].nunique()) if not bowling_summary.empty else 0,
        "batting_missing_dismissal_ids": int(batting_aux_audit["missing_dismissal_ids"]),
        "rankings_created": False,
        "composite_score_created": False,
    }
    return batting_context, batting_summary, bowling_context, bowling_summary, league_benchmarks, audit


def save_player_baselines(
    batting_context: pd.DataFrame,
    batting_summary: pd.DataFrame,
    bowling_context: pd.DataFrame,
    bowling_summary: pd.DataFrame,
    league_benchmarks: pd.DataFrame,
    audit: dict,
    output_dir: str | Path = "outputs",
) -> dict[str, str]:
    """Save context comparisons, player summaries, peer benchmarks and audit."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tables = {
        "batting_context": (batting_context, "batting_baseline_context.csv"),
        "batting_summary": (batting_summary, "batting_baseline_summary.csv"),
        "bowling_context": (bowling_context, "bowling_baseline_context.csv"),
        "bowling_summary": (bowling_summary, "bowling_baseline_summary.csv"),
        "peer_benchmarks": (league_benchmarks, "peer_league_benchmarks.csv"),
    }
    saved = {}
    for key, (frame, filename) in tables.items():
        destination = out / filename
        frame.to_csv(destination, index=False)
        saved[key] = str(destination)
    audit_path = out / "player_baseline_audit.json"
    audit_path.write_text(json.dumps(audit, indent=2, default=str), encoding="utf-8")
    saved["audit"] = str(audit_path)
    return saved
