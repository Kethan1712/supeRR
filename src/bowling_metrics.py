"""Descriptive bowling metrics from supplied ball-by-ball records.

The source pack does not contain a complete extras-run amount. Accordingly,
this module does NOT calculate official runs conceded, economy rate, or true dot
balls. It reports observable fields with deliberately explicit names:

* candidate_legal_balls: excludes known wide and Overstep (no-ball) records;
* source_runs_field_sum: sum of the source `runs` field, not total runs
  charged to the bowler;
* zero_source_runs_field_per_100_candidate_legal_balls: not called a dot-ball rate because byes and
  leg-byes have zero in `runs` while their actual extras are missing.

Bowler-creditable dismissals are Bowled, Caught, LBW, Stump, and Hit Wicket.
Run-outs and other non-bowler dismissals are reported separately. Stumpings on
wides remain credited to the bowler, while run-outs on wides/no-balls do not.

Pressure categories are reported as match-context groups. In particular,
early-collapse context is pressure on the batting side and is NOT assumed to
mean the bowling side itself was under pressure. Final bowling-rating logic
must make that distinction explicit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

PRESSURE_GROUPS = {
    "early_collapse_context": "is_early_collapse_pressure",
    "death_over_context": "is_death_over_pressure",
    "combined_pressure_context": "is_pressure",
}
ORDINARY_GROUP = "ordinary_baseline"
ADDITIONAL_GROUP = "additional_innings_unclassified"

BOWLER_CREDITED_DISMISSALS = {
    "bowled",
    "caught",
    "lbw",
    "stump",
    "hit wicket",
}
KNOWN_ILLEGAL_DELIVERY_TYPES = {"wide", "overstep"}

REQUIRED_COLUMNS = {
    "match_id",
    "innings",
    "comp_id",
    "bowler_id",
    "bowler_name",
    "runs",
    "is_four",
    "is_six",
    "is_wicket",
    "dismissal_type",
    "extras_type",
    "is_regular_innings",
    "is_additional_innings",
    "is_early_collapse_pressure",
    "is_death_over_pressure",
    "is_pressure",
}


def _bool_series(values: pd.Series) -> pd.Series:
    """Convert nullable/object boolean columns safely."""
    return values.astype("boolean").fillna(False).astype(bool)


def _normalise_text(values: pd.Series) -> pd.Series:
    return values.astype("string").str.strip().str.casefold()


def _safe_rate(numerator: pd.Series, denominator: pd.Series, scale: float = 1.0) -> pd.Series:
    return numerator.astype(float).div(denominator.where(denominator.ne(0))) * scale


def _category_frames(data: pd.DataFrame) -> list[pd.DataFrame]:
    regular = _bool_series(data["is_regular_innings"])
    additional = _bool_series(data["is_additional_innings"])
    masks = [
        (name, regular & _bool_series(data[column]))
        for name, column in PRESSURE_GROUPS.items()
    ]
    masks.extend([
        (ORDINARY_GROUP, regular & ~_bool_series(data["is_pressure"])),
        (ADDITIONAL_GROUP, additional),
    ])

    frames = []
    for category, mask in masks:
        subset = data.loc[mask].copy()
        if not subset.empty:
            subset["metric_category"] = category
            frames.append(subset)
    if not frames:
        return [data.iloc[0:0].assign(metric_category=pd.Series(dtype="object"))]
    return frames


def _prepare_tagged(data: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(data.columns))
    if missing:
        raise ValueError(f"pressure-enriched dataframe is missing columns: {missing}")
    if data["bowler_id"].isna().any():
        raise ValueError("bowler_id contains missing values; cannot attribute bowling events")

    runs = pd.to_numeric(data["runs"], errors="coerce")
    if runs.isna().any() or runs.lt(0).any():
        raise ValueError("runs contains missing or negative values")

    tagged = pd.concat(_category_frames(data), ignore_index=True, sort=False)
    if tagged.empty:
        return tagged

    tagged["player_id"] = tagged["bowler_id"].astype("int64")
    tagged["player_name"] = tagged["bowler_name"].astype("string")
    tagged["source_runs_field"] = pd.to_numeric(
        tagged["runs"], errors="coerce"
    ).fillna(0)
    tagged["extras_type_normalised"] = _normalise_text(tagged["extras_type"])
    tagged["dismissal_type_normalised"] = _normalise_text(tagged["dismissal_type"])

    tagged["is_candidate_legal_ball"] = ~tagged[
        "extras_type_normalised"
    ].isin(KNOWN_ILLEGAL_DELIVERY_TYPES)
    # Penalty is kept in the primary variant because the single source record's
    # event semantics are not documented. An alternate denominator excludes it.
    tagged["is_candidate_legal_ball_excluding_penalty"] = (
        tagged["is_candidate_legal_ball"]
        & tagged["extras_type_normalised"].ne("penalty").fillna(True)
    )
    tagged["is_known_illegal_delivery"] = tagged[
        "extras_type_normalised"
    ].isin(KNOWN_ILLEGAL_DELIVERY_TYPES)

    tagged["is_bowler_credited_wicket"] = (
        _bool_series(tagged["is_wicket"])
        & tagged["dismissal_type_normalised"].isin(BOWLER_CREDITED_DISMISSALS)
    )
    tagged["is_non_bowler_wicket"] = (
        _bool_series(tagged["is_wicket"])
        & ~tagged["is_bowler_credited_wicket"]
    )
    tagged["is_four_flag"] = _bool_series(tagged["is_four"])
    tagged["is_six_flag"] = _bool_series(tagged["is_six"])
    tagged["is_zero_source_runs_field"] = (
        tagged["is_candidate_legal_ball"]
        & tagged["source_runs_field"].eq(0)
    )
    return tagged


def _aggregate(tagged: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if tagged.empty:
        return pd.DataFrame(columns=group_columns)

    tagged = tagged.copy()
    tagged["innings_key"] = (
        tagged["match_id"].astype("string")
        + ":" + tagged["innings"].astype("string")
    )

    grouped = tagged.groupby(group_columns, dropna=False, sort=False)
    result = grouped.agg(
        bowling_delivery_records=("bowler_id", "size"),
        candidate_legal_balls=("is_candidate_legal_ball", "sum"),
        candidate_legal_balls_excluding_penalty=(
            "is_candidate_legal_ball_excluding_penalty", "sum"
        ),
        source_runs_field_sum=("source_runs_field", "sum"),
        bowler_credited_wickets=("is_bowler_credited_wicket", "sum"),
        non_bowler_wickets_in_bowling_spell=("is_non_bowler_wicket", "sum"),
        flagged_fours_conceded=("is_four_flag", "sum"),
        flagged_sixes_conceded=("is_six_flag", "sum"),
        candidate_legal_balls_with_zero_source_runs_field=(
            "is_zero_source_runs_field", "sum"
        ),
        wide_records=("extras_type_normalised", lambda s: s.eq("wide").sum()),
        overstep_records=("extras_type_normalised", lambda s: s.eq("overstep").sum()),
        other_extras_records=("extras_type_normalised", lambda s: s.eq("other").sum()),
        penalty_records=("extras_type_normalised", lambda s: s.eq("penalty").sum()),
        innings_bowled_in=("innings_key", "nunique"),
    ).reset_index()

    if "match_id" in tagged.columns:
        support = tagged.groupby(group_columns, dropna=False, sort=False).agg(
            matches_represented=("match_id", "nunique")
        ).reset_index()
        result = result.merge(support, on=group_columns, how="left", validate="one_to_one")
    if "comp_id" in tagged.columns:
        support = tagged.groupby(group_columns, dropna=False, sort=False).agg(
            competitions_represented=("comp_id", "nunique")
        ).reset_index()
        result = result.merge(support, on=group_columns, how="left", validate="one_to_one")
    if "season" in tagged.columns:
        support = tagged.groupby(group_columns, dropna=False, sort=False).agg(
            seasons_represented=("season", "nunique")
        ).reset_index()
        result = result.merge(support, on=group_columns, how="left", validate="one_to_one")

    count_columns = [
        column for column in result.columns
        if column.endswith("records") or column.endswith("balls")
        or column.endswith("wickets") or column.endswith("conceded")
        or column in {"bowler_credited_wickets", "innings_bowled_in", "matches_represented",
                      "competitions_represented", "seasons_represented",
                      "flagged_fours_conceded", "flagged_sixes_conceded"}
    ]
    for column in count_columns:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype("int64")

    result["bowler_wickets_per_100_candidate_legal_balls"] = _safe_rate(
        result["bowler_credited_wickets"], result["candidate_legal_balls"], 100.0
    )
    result["source_runs_field_per_6_candidate_legal_balls"] = _safe_rate(
        result["source_runs_field_sum"], result["candidate_legal_balls"], 6.0
    )
    result["flagged_fours_per_100_candidate_legal_balls"] = _safe_rate(
        result["flagged_fours_conceded"], result["candidate_legal_balls"], 100.0
    )
    result["flagged_sixes_per_100_candidate_legal_balls"] = _safe_rate(
        result["flagged_sixes_conceded"], result["candidate_legal_balls"], 100.0
    )
    result["flagged_boundaries_per_100_candidate_legal_balls"] = _safe_rate(
        result["flagged_fours_conceded"] + result["flagged_sixes_conceded"],
        result["candidate_legal_balls"],
        100.0,
    )
    result["zero_source_runs_field_per_100_candidate_legal_balls"] = _safe_rate(
        result["candidate_legal_balls_with_zero_source_runs_field"],
        result["candidate_legal_balls"],
        100.0,
    )
    return result


def calculate_bowling_metrics(
    pressured: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Calculate descriptive bowler and bowler-match metrics plus a quality audit.

    Output rates are explicitly based on candidate legal balls, not asserted
    scorecard-verified legal balls. The function does not create ratings or ranks.
    """
    tagged = _prepare_tagged(pressured)
    player_keys = ["player_id", "player_name", "metric_category"]
    match_keys = player_keys + ["match_id", "comp_id"]
    for optional in ["comp_name", "match_format", "season"]:
        if optional in tagged.columns:
            match_keys.append(optional)

    player_metrics = _aggregate(tagged, player_keys)
    match_metrics = _aggregate(tagged, match_keys)

    front = [c for c in player_keys if c in player_metrics]
    player_metrics = player_metrics[front + [
        c for c in player_metrics.columns if c not in front
    ]].sort_values(["metric_category", "player_id"], kind="mergesort").reset_index(drop=True)
    match_front = [c for c in match_keys if c in match_metrics]
    match_metrics = match_metrics[match_front + [
        c for c in match_metrics.columns if c not in match_front
    ]].sort_values(["metric_category", "player_id", "match_id"], kind="mergesort").reset_index(drop=True)

    wickets = pressured.loc[_bool_series(pressured["is_wicket"])].copy()
    dismissal_type = _normalise_text(wickets["dismissal_type"])
    bowler_credit = dismissal_type.isin(BOWLER_CREDITED_DISMISSALS)
    extras_type = _normalise_text(pressured["extras_type"])
    runs = pd.to_numeric(pressured["runs"], errors="coerce").fillna(0)
    if "extras_2_runs" in pressured.columns:
        extras2 = pd.to_numeric(pressured["extras_2_runs"], errors="coerce").fillna(0)
    else:
        extras2 = pd.Series(0, index=pressured.index, dtype="int64")
    four_flags = _bool_series(pressured["is_four"])
    six_flags = _bool_series(pressured["is_six"])

    by_extras = {}
    for category, subset in pressured.assign(_runs=runs, _extras2=extras2).groupby(
        extras_type.fillna("<null>"), dropna=False
    ):
        by_extras[str(category)] = {
            "records": int(len(subset)),
            "sum_source_runs_field": int(subset["_runs"].sum()),
            "records_with_nonzero_source_runs": int(subset["_runs"].ne(0).sum()),
            "records_with_nonzero_extras_2_runs": int(subset["_extras2"].ne(0).sum()),
            "sum_extras_2_runs": int(subset["_extras2"].sum()),
        }

    legal_mask = extras_type.isna() | ~extras_type.isin(KNOWN_ILLEGAL_DELIVERY_TYPES)
    penalty_mask = extras_type.eq("penalty").fillna(False)
    wide_wickets = wickets.loc[_normalise_text(wickets["extras_type"]).eq("wide")]
    no_ball_wickets = wickets.loc[_normalise_text(wickets["extras_type"]).eq("overstep")]

    audit = {
        "scope": {
            "regular_innings": "innings 1 and 2; pressure categories applied as match context",
            "additional_innings": "retained separately and not mixed into regular pressure/ordinary groups",
            "competitions": "all competition records in the supplied dataset are retained",
            "bowling_interpretation": (
                "early-collapse context describes pressure on the batting side; it is not automatically treated as pressure on the bowler"
            ),
        },
        "metric_definitions": {
            "bowling_delivery_records": "all recorded delivery rows assigned to the bowler",
            "candidate_legal_balls": "bowling delivery rows excluding extras_type wide and Overstep; Penalty retained in primary count due uncertain event semantics",
            "candidate_legal_balls_excluding_penalty": "same as primary candidate legal balls but also excludes the single Penalty-coded record",
            "bowler_credited_wickets": "is_wicket records with dismissal_type Bowled, Caught, LBW, Stump or Hit Wicket; stumping on wide remains credited; RunOut is not credited",
            "source_runs_field_sum": "sum of runs field only; not complete bowler runs conceded because actual wide/byes/leg-byes are not fully present",
            "economy_rate": "not calculated: total bowler-charged runs cannot be reconstructed reliably from supplied extras fields",
            "dot_ball_rate": "not calculated: byes/leg-byes have missing run values, so zero runs field cannot identify a true dot ball",
            "boundary_rates": "counts supplied is_four/is_six flags; source audit discloses flag mismatches",
        },
        "source_checks": {
            "delivery_records": int(len(pressured)),
            "unique_bowlers": int(pressured["bowler_id"].nunique()),
            "missing_bowler_ids": int(pressured["bowler_id"].isna().sum()),
            "wide_records": int(extras_type.eq("wide").sum()),
            "overstep_records": int(extras_type.eq("overstep").sum()),
            "other_extras_records": int(extras_type.eq("other").sum()),
            "penalty_records": int(penalty_mask.sum()),
            "primary_candidate_legal_ball_records": int(legal_mask.sum()),
            "candidate_legal_balls_if_penalty_excluded": int((legal_mask & ~penalty_mask).sum()),
            "all_wicket_records": int(len(wickets)),
            "bowler_credited_wicket_records": int(bowler_credit.sum()),
            "non_bowler_wicket_records": int((~bowler_credit).sum()),
            "bowler_credited_wickets_on_wides": int(
                dismissal_type.loc[wide_wickets.index].isin(BOWLER_CREDITED_DISMISSALS).sum()
            ),
            "bowler_credited_wickets_on_overstep": int(
                dismissal_type.loc[no_ball_wickets.index].isin(BOWLER_CREDITED_DISMISSALS).sum()
            ),
            "missing_bowler_id_on_wicket_records": int(wickets["bowler_id"].isna().sum()),
            "source_runs_field_sum": int(runs.sum()),
            "four_flag_records_with_runs_not_equal_to_4": int((four_flags & runs.ne(4)).sum()),
            "six_flag_records_with_runs_not_equal_to_6": int((six_flags & runs.ne(6)).sum()),
            "runs_equal_4_without_four_flag": int((runs.eq(4) & ~four_flags).sum()),
            "runs_equal_6_without_six_flag": int((runs.eq(6) & ~six_flags).sum()),
            "extras2_nonzero_records": int(extras2.ne(0).sum()),
            "extras2_sum": int(extras2.sum()),
            "extras_breakdown": by_extras,
            "wicket_type_counts": {
                str(k): int(v) for k, v in wickets["dismissal_type"].fillna("<null>").value_counts().items()
            },
        },
        "metric_output": {
            "player_metric_rows": int(len(player_metrics)),
            "player_match_metric_rows": int(len(match_metrics)),
            "metric_categories": sorted(player_metrics["metric_category"].unique().tolist()) if not player_metrics.empty else [],
        },
    }
    return player_metrics, match_metrics, audit


def save_bowling_metrics(
    player_metrics: pd.DataFrame,
    match_metrics: pd.DataFrame,
    audit: dict,
    output_dir: str = "outputs",
) -> dict[str, str]:
    """Save bowler metrics and source audit to CSV/JSON."""
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    player_path = path / "bowling_player_metrics.csv"
    match_path = path / "bowling_match_metrics.csv"
    audit_path = path / "bowling_metrics_audit.json"
    player_metrics.to_csv(player_path, index=False)
    match_metrics.to_csv(match_path, index=False)
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return {
        "player_metrics": str(player_path),
        "match_metrics": str(match_path),
        "audit": str(audit_path),
    }
