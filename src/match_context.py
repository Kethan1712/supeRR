"""Build delivery-level match context without inventing score information.

This module adds competition metadata and the number of wickets lost BEFORE
 each recorded delivery. It deliberately does not reconstruct team totals,
required run rates, legal balls, or pressure labels.
"""

from __future__ import annotations

import pandas as pd

DELIVERY_KEYS = ["match_id", "innings"]


def build_match_context(
    ball_by_ball: pd.DataFrame,
    matches: pd.DataFrame,
    competitions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return a sorted copy of ball-by-ball data enriched with match context.

    ``innings_ball_num`` is used to order deliveries within an innings. The
    source data is not modified. ``wickets_before`` is shifted so a wicket on
    the current delivery is not counted as already lost before that delivery.

    Innings 1 and 2 are marked as regular innings. Innings 3+ are retained and
    marked separately; they are not silently discarded or labelled as Super
    Overs because that interpretation must be independently confirmed.
    """
    required_ball = {
        "match_id", "innings", "innings_ball_num", "overid", "is_wicket"
    }
    required_matches = {"match_id", "comp_id"}
    missing_ball = sorted(required_ball - set(ball_by_ball.columns))
    missing_matches = sorted(required_matches - set(matches.columns))
    if missing_ball:
        raise ValueError(f"ball_by_ball is missing columns: {missing_ball}")
    if missing_matches:
        raise ValueError(f"matches is missing columns: {missing_matches}")

    if matches["match_id"].duplicated().any():
        raise ValueError("matches.match_id must be unique for a many-to-one join")
    if ball_by_ball["match_id"].isna().any():
        raise ValueError("ball_by_ball contains null match_id values")
    if ball_by_ball["innings_ball_num"].isna().any():
        raise ValueError("ball_by_ball contains null innings_ball_num values")

    context = ball_by_ball.copy()
    context = context.merge(
        matches,
        on="match_id",
        how="left",
        validate="many_to_one",
        suffixes=("", "_match"),
        indicator="_match_join",
    )
    unmatched = int(context["_match_join"].ne("both").sum())
    context = context.drop(columns="_match_join")
    if unmatched:
        raise ValueError(
            f"{unmatched} delivery records have no matching row in matches.csv"
        )

    if competitions is not None:
        if "comp_id" not in competitions.columns:
            raise ValueError("competitions is missing comp_id")
        if competitions["comp_id"].duplicated().any():
            raise ValueError("competitions.comp_id must be unique")
        competition_columns = [
            column for column in
            ["comp_id", "comp_name", "match_format", "season"]
            if column in competitions.columns
        ]
        context = context.merge(
            competitions[competition_columns],
            on="comp_id",
            how="left",
            validate="many_to_one",
            indicator="_competition_join",
        )
        missing_competition = int(
            context["_competition_join"].ne("both").sum()
        )
        context = context.drop(columns="_competition_join")
        if missing_competition:
            raise ValueError(
                f"{missing_competition} delivery records have no competition metadata"
            )

    context = context.sort_values(
        ["match_id", "innings", "innings_ball_num"], kind="mergesort"
    ).reset_index(drop=True)

    if context.duplicated(DELIVERY_KEYS + ["innings_ball_num"]).any():
        raise ValueError(
            "Duplicate innings_ball_num values found within a match innings"
        )

    context["is_wicket"] = context["is_wicket"].fillna(False).astype(bool)
    group = context.groupby(DELIVERY_KEYS, sort=False)
    context["wickets_before"] = group["is_wicket"].transform(
        lambda values: values.astype("int8").cumsum().shift(1, fill_value=0)
    ).astype("int8")
    context["wickets_after"] = (
        context["wickets_before"] + context["is_wicket"].astype("int8")
    ).astype("int8")
    context["is_regular_innings"] = context["innings"].isin([1, 2])
    context["is_additional_innings"] = ~context["is_regular_innings"]

    return context


def context_audit(context: pd.DataFrame) -> dict:
    """Summarise sequence and wicket-state checks for a context dataframe."""
    required = {
        "match_id", "innings", "innings_ball_num", "overid",
        "wickets_before", "wickets_after", "is_regular_innings",
    }
    missing = sorted(required - set(context.columns))
    if missing:
        raise ValueError(f"context is missing audit columns: {missing}")

    ordered = context.sort_values(
        ["match_id", "innings", "innings_ball_num"], kind="mergesort"
    )
    grouped = ordered.groupby(DELIVERY_KEYS, sort=False)
    sequence_delta = grouped["innings_ball_num"].diff()
    # A group whose first recorded delivery is not numbered 1 is counted once.
    group_first = grouped["innings_ball_num"].first()
    groups_not_starting_at_one = int(group_first.ne(1).sum())
    groups_with_gaps = int(
        (sequence_delta.notna() & sequence_delta.ne(1))
        .groupby([ordered["match_id"], ordered["innings"]])
        .any()
        .sum()
    )

    return {
        "delivery_records": int(len(context)),
        "matches_represented": int(context["match_id"].nunique()),
        "innings_groups": int(context.groupby(DELIVERY_KEYS).ngroups),
        "regular_innings_records": int(context["is_regular_innings"].sum()),
        "additional_innings_records": int(context["is_additional_innings"].sum()),
        "duplicate_delivery_numbers": int(
            context.duplicated(DELIVERY_KEYS + ["innings_ball_num"]).sum()
        ),
        "innings_groups_not_starting_at_ball_1": groups_not_starting_at_one,
        "innings_groups_with_sequence_gaps": groups_with_gaps,
        "max_wickets_before_delivery": int(context["wickets_before"].max()),
        "wicket_state_monotonic": bool(
            (context["wickets_after"] >= context["wickets_before"]).all()
        ),
    }
