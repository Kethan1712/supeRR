"""Descriptive batting metrics from the supplied ball-by-ball records.

This module intentionally uses conservative field names because the source pack
has no data dictionary and its extras columns are incomplete. ``runs`` is
aggregated as ``recorded_runs`` (not claimed to be a fully validated official
batter-run total). Wides are not counted as balls faced. All non-wide records,
including the single Penalty-coded record, are counted as a faced-ball event in
the primary calculation and separately disclosed in the audit.

Pressure groups are reported separately:
- early_collapse_pressure
- death_over_pressure
- combined_pressure (union; no double counting)
- ordinary_baseline (regular-innings records in neither pressure group)
- additional_innings_unclassified (retained separately)

The module does not assign a final player rating or ranking.
"""

from __future__ import annotations

import pandas as pd

PRESSURE_GROUPS = {
    "early_collapse_pressure": "is_early_collapse_pressure",
    "death_over_pressure": "is_death_over_pressure",
    "combined_pressure": "is_pressure",
}
ORDINARY_GROUP = "ordinary_baseline"
ADDITIONAL_GROUP = "additional_innings_unclassified"

REQUIRED_COLUMNS = {
    "match_id", "innings", "comp_id", "striker_id", "striker_name",
    "runs", "is_four", "is_six", "is_wicket", "dismissed_player_id",
    "extras_type", "is_regular_innings", "is_additional_innings",
    "is_early_collapse_pressure", "is_death_over_pressure", "is_pressure",
}


def _category_frames(pressured: pd.DataFrame) -> list[pd.DataFrame]:
    """Create explicitly labelled analysis groups without dropping source rows."""
    frames: list[pd.DataFrame] = []
    regular = _bool_series(pressured["is_regular_innings"])
    additional = _bool_series(pressured["is_additional_innings"])

    masks = [
        (name, regular & _bool_series(pressured[column]))
        for name, column in PRESSURE_GROUPS.items()
    ]
    masks.append((ORDINARY_GROUP, regular & ~_bool_series(pressured["is_pressure"])))
    masks.append((ADDITIONAL_GROUP, additional))

    for category, mask in masks:
        subset = pressured.loc[mask].copy()
        if not subset.empty:
            subset["metric_category"] = category
            frames.append(subset)

    if not frames:
        return [pressured.iloc[0:0].assign(metric_category=pd.Series(dtype="object"))]
    return frames


def _bool_series(values: pd.Series) -> pd.Series:
    """Convert nullable/object boolean columns without pandas downcast warnings."""
    return values.astype("boolean").fillna(False).astype(bool)


def _safe_rate(numerator: pd.Series, denominator: pd.Series, scale: float = 1.0) -> pd.Series:
    result = numerator.astype(float).div(denominator.where(denominator.ne(0))) * scale
    return result


def _aggregate_grouped(
    tagged: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    """Aggregate batter delivery events and player-attributed dismissals."""
    if tagged.empty:
        return pd.DataFrame(columns=group_columns)

    # A recorded delivery faced by a striker. Only wide records are excluded.
    striker_events = tagged.copy()
    striker_events["is_batter_ball_faced"] = ~striker_events["extras_type"].eq("wide")
    striker_events["is_batter_ball_faced_excluding_penalty"] = (
        ~striker_events["extras_type"].isin(["wide", "Penalty"])
    )
    striker_events["recorded_runs"] = pd.to_numeric(
        striker_events["runs"], errors="coerce"
    ).fillna(0)
    striker_events["four_flag"] = _bool_series(striker_events["is_four"])
    striker_events["six_flag"] = _bool_series(striker_events["is_six"])

    striker_events["innings_key"] = (
        striker_events["match_id"].astype("string")
        + ":" + striker_events["innings"].astype("string")
    )
    batting = striker_events.groupby(group_columns, dropna=False, sort=False).agg(
        balls_faced=("is_batter_ball_faced", "sum"),
        balls_faced_excluding_penalty=("is_batter_ball_faced_excluding_penalty", "sum"),
        recorded_runs=("recorded_runs", "sum"),
        flagged_fours=("four_flag", "sum"),
        flagged_sixes=("six_flag", "sum"),
        innings_batted=("innings_key", "nunique"),
    ).reset_index()

    # Build a stable player-name lookup from both batting positions. This is
    # needed because a run-out can dismiss the non-striker.
    name_pairs = pd.concat(
        [
            tagged[["player_id", "player_name"]].rename(
                columns={"player_id": "lookup_player_id"}
            ),
            tagged[["non_striker_id", "non_striker_name"]].rename(
                columns={
                    "non_striker_id": "lookup_player_id",
                    "non_striker_name": "player_name",
                }
            ) if "non_striker_id" in tagged and "non_striker_name" in tagged
            else pd.DataFrame(columns=["lookup_player_id", "player_name"]),
        ],
        ignore_index=True,
    ).dropna(subset=["lookup_player_id", "player_name"])
    name_lookup = (
        name_pairs.drop_duplicates("lookup_player_id", keep="first")
        .set_index("lookup_player_id")["player_name"]
    )

    # Attribute each dismissal to dismissed_player_id, not automatically to the
    # striker. A missing ID is reported in the audit and is not guessed.
    wickets = tagged.loc[
        _bool_series(tagged["is_wicket"])
        & tagged["dismissed_player_id"].notna()
    ].copy()
    if wickets.empty:
        dismissals = pd.DataFrame(columns=group_columns + ["attributed_dismissals"])
    else:
        wickets["player_id"] = wickets["dismissed_player_id"].astype("int64")
        wickets["player_name"] = wickets["player_id"].map(name_lookup)
        dismissals = (
            wickets.groupby(group_columns, dropna=False, sort=False)
            .size().rename("attributed_dismissals").reset_index()
        )

    result = batting.merge(dismissals, on=group_columns, how="outer")
    for column in [
        "balls_faced", "balls_faced_excluding_penalty", "recorded_runs",
        "flagged_fours", "flagged_sixes", "innings_batted",
        "attributed_dismissals",
    ]:
        if column not in result:
            result[column] = 0
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype("int64")

    result["strike_rate_recorded"] = _safe_rate(
        result["recorded_runs"], result["balls_faced"], 100.0
    )
    result["strike_rate_excluding_penalty"] = _safe_rate(
        result["recorded_runs"], result["balls_faced_excluding_penalty"], 100.0
    )
    result["fours_per_100_balls"] = _safe_rate(
        result["flagged_fours"], result["balls_faced"], 100.0
    )
    result["sixes_per_100_balls"] = _safe_rate(
        result["flagged_sixes"], result["balls_faced"], 100.0
    )
    result["boundaries_per_100_balls"] = _safe_rate(
        result["flagged_fours"] + result["flagged_sixes"],
        result["balls_faced"], 100.0,
    )
    result["dismissals_per_100_balls"] = _safe_rate(
        result["attributed_dismissals"], result["balls_faced"], 100.0
    )
    result["balls_per_dismissal"] = _safe_rate(
        result["balls_faced"], result["attributed_dismissals"]
    )
    result["recorded_runs_per_dismissal"] = _safe_rate(
        result["recorded_runs"], result["attributed_dismissals"]
    )
    return result


def _tag_analysis_groups(pressured: pd.DataFrame) -> pd.DataFrame:
    frames = _category_frames(pressured)
    tagged = pd.concat(frames, ignore_index=True, sort=False)
    if tagged.empty:
        return tagged
    tagged["player_id"] = tagged["striker_id"].astype("int64")
    return tagged


def calculate_batting_metrics(
    pressured: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return player metrics, player-match metrics and a data-quality audit.

    The function makes descriptive summaries only. It does not calculate a
    pressure rating, choose eligibility thresholds, or rank players.
    """
    missing = sorted(REQUIRED_COLUMNS - set(pressured.columns))
    if missing:
        raise ValueError(f"pressured dataframe is missing columns: {missing}")

    if pressured["striker_id"].isna().any():
        raise ValueError("striker_id contains missing values; cannot attribute batting events")
    runs = pd.to_numeric(pressured["runs"], errors="coerce")
    if runs.isna().any() or runs.lt(0).any():
        raise ValueError("runs contains missing or negative values")

    tagged = _tag_analysis_groups(pressured)
    # Use a common player-name field for both batting and dismissal aggregation.
    tagged = tagged.rename(columns={"striker_name": "player_name"})
    player_keys = [
        "player_id", "player_name", "metric_category"
    ]
    match_keys = player_keys + [
        "match_id", "comp_id"
    ]
    for optional in ["comp_name", "match_format", "season"]:
        if optional in tagged.columns:
            match_keys.append(optional)

    player_metrics = _aggregate_grouped(tagged, player_keys)
    match_metrics = _aggregate_grouped(tagged, match_keys)

    # Distinct-match and competition support counts are important reliability
    # inputs later; they are descriptive here and do not impose eligibility.
    support_columns = ["player_id", "player_name", "metric_category"]
    support_agg = {"matches_represented": ("match_id", "nunique")}
    if "comp_id" in tagged.columns:
        support_agg["competitions_represented"] = ("comp_id", "nunique")
    if "season" in tagged.columns:
        support_agg["seasons_represented"] = ("season", "nunique")
    support = tagged.groupby(support_columns, dropna=False, sort=False).agg(**support_agg).reset_index()
    player_metrics = player_metrics.merge(support, on=support_columns, how="left", validate="one_to_one")
    for count_column in ["matches_represented", "competitions_represented", "seasons_represented"]:
        if count_column in player_metrics.columns:
            player_metrics[count_column] = (
                pd.to_numeric(player_metrics[count_column], errors="coerce")
                .fillna(0).astype("int64")
            )

    # Ensure consistent output order and include a plain player_name column.
    front = [c for c in ["player_id", "player_name", "metric_category"] if c in player_metrics]
    metric_cols = [c for c in player_metrics.columns if c not in front]
    player_metrics = player_metrics[front + metric_cols].sort_values(
        ["metric_category", "player_id"], kind="mergesort"
    ).reset_index(drop=True)
    match_front = [c for c in match_keys if c in match_metrics]
    match_metrics = match_metrics[match_front + [
        c for c in match_metrics.columns if c not in match_front
    ]].sort_values(["metric_category", "player_id", "match_id"], kind="mergesort").reset_index(drop=True)

    # Audits preserve uncertain source semantics instead of hiding them.
    wickets = pressured[_bool_series(pressured["is_wicket"])]
    extras_nonzero = pressured[
        pressured["extras_type"].notna()
        & pd.to_numeric(pressured["runs"], errors="coerce").fillna(0).ne(0)
    ]
    four_flag_mismatch = pressured[
        _bool_series(pressured["is_four"])
        & pd.to_numeric(pressured["runs"], errors="coerce").ne(4)
    ]
    six_flag_mismatch = pressured[
        _bool_series(pressured["is_six"])
        & pd.to_numeric(pressured["runs"], errors="coerce").ne(6)
    ]
    missing_dismissed_id = wickets["dismissed_player_id"].isna()
    non_striker_dismissals = wickets[
        wickets["dismissed_player_id"].eq(wickets["non_striker_id"])
    ]
    missing_id_by_category = (
        tagged.loc[
            _bool_series(tagged["is_wicket"]) & tagged["dismissed_player_id"].isna()
        ]
        .groupby("metric_category", dropna=False)
        .size()
        .to_dict()
    )

    audit = {
        "metric_scope": {
            "regular_innings": "innings 1 and 2; these receive pressure labels",
            "additional_innings": (
                "retained in a separate unclassified metric group; not mixed into pressure or ordinary baselines"
            ),
            "all_competitions": "all competition records supplied to the pressure-enriched dataframe",
        },
        "batting_measurement_definitions": {
            "balls_faced": "striker delivery records excluding extras_type='wide'; Overstep/no-ball records count; the single Penalty-coded record is retained in the primary count and a second balls-faced/strike-rate variant excludes it",
            "recorded_runs": "sum of the source runs column; labelled recorded_runs because the pack has no complete data dictionary and extras coding contains anomalies",
            "fours_and_sixes": "count of is_four and is_six flags; not inferred from runs==4/6, because some 4/6 run values have no boundary flag",
            "dismissals": "is_wicket events attributed using dismissed_player_id; run-outs and non-striker dismissals are attributed to the dismissed batter, not automatically to striker",
            "missing_dismissal_id": "not assigned to any player; explicitly counted in this audit",
        },
        "source_coverage": {
            "delivery_records_input": int(len(pressured)),
            "regular_innings_records": int(pressured["is_regular_innings"].fillna(False).sum()),
            "additional_innings_records": int(pressured["is_additional_innings"].fillna(False).sum()),
            "unique_strikers": int(pressured["striker_id"].nunique()),
            "wide_records": int(pressured["extras_type"].eq("wide").sum()),
            "overstep_records_counted_as_faced": int(pressured["extras_type"].eq("Overstep").sum()),
            "penalty_records_counted_as_faced": int(pressured["extras_type"].eq("Penalty").sum()),
            "balls_faced_records_primary_rule": int((~pressured["extras_type"].eq("wide")).sum()),
            "balls_faced_records_excluding_penalty": int((~pressured["extras_type"].isin(["wide", "Penalty"])).sum()),
            "recorded_runs_sum": int(pd.to_numeric(pressured["runs"]).sum()),
        },
        "run_and_boundary_checks": {
            "non_null_extras_records_with_nonzero_runs": int(len(extras_nonzero)),
            "nonzero_runs_by_extras_type": {
                str(k): int(v)
                for k, v in extras_nonzero.groupby("extras_type").size().items()
            },
            "four_flags_with_runs_not_equal_to_4": int(len(four_flag_mismatch)),
            "six_flags_with_runs_not_equal_to_6": int(len(six_flag_mismatch)),
            "runs_equal_4_without_four_flag": int(
                (pd.to_numeric(pressured["runs"]).eq(4) & ~_bool_series(pressured["is_four"])).sum()
            ),
            "runs_equal_6_without_six_flag": int(
                (pd.to_numeric(pressured["runs"]).eq(6) & ~_bool_series(pressured["is_six"])).sum()
            ),
        },
        "dismissal_attribution_checks": {
            "is_wicket_records": int(len(wickets)),
            "dismissed_player_id_missing": int(missing_dismissed_id.sum()),
            "dismissals_attributed_to_non_striker": int(len(non_striker_dismissals)),
            "dismissals_attributed_to_striker": int(
                wickets["dismissed_player_id"].eq(wickets["striker_id"]).sum()
            ),
            "missing_dismissal_id_by_metric_category": {
                str(k): int(v) for k, v in missing_id_by_category.items()
            },
        },
        "player_metric_rows": int(len(player_metrics)),
        "player_match_metric_rows": int(len(match_metrics)),
        "metric_categories": sorted(player_metrics["metric_category"].unique().tolist()) if not player_metrics.empty else [],
    }

    return player_metrics, match_metrics, audit


def save_batting_metrics(
    player_metrics: pd.DataFrame,
    match_metrics: pd.DataFrame,
    audit: dict,
    output_dir: str = "outputs",
) -> dict[str, str]:
    """Save batting metric outputs as CSV and JSON, returning their paths."""
    from pathlib import Path
    import json

    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    player_path = path / "batting_player_metrics.csv"
    match_path = path / "batting_match_metrics.csv"
    audit_path = path / "batting_metrics_audit.json"
    player_metrics.to_csv(player_path, index=False)
    match_metrics.to_csv(match_path, index=False)
    audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return {
        "player_metrics": str(player_path),
        "match_metrics": str(match_path),
        "audit": str(audit_path),
    }
