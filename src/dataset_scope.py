"""Competition-scope controls for the SupeRR Selector dataset.

The primary scope follows the Round 1 brief: IPL seasons from 2022 onward and
T20 Internationals. Other T20-format domestic/representative competitions are
excluded from the primary ranking, but can be retained in an explicitly
labelled expanded-scope sensitivity run.
"""
from __future__ import annotations

import re
from typing import Mapping
import pandas as pd

IPL_PATTERN = re.compile(r"^IPL 20(?:2[2-9]|[3-9]\d)$")


def apply_competition_scope(
    tables: Mapping[str, pd.DataFrame], scope: str = "ipl_t20i"
) -> tuple[dict[str, pd.DataFrame], dict]:
    required = {"ball_by_ball", "matches", "competitions", "playing_eleven", "teams", "competition_team_player_mapping"}
    missing = sorted(required - set(tables))
    if missing:
        raise ValueError(f"Dataset tables missing for scope filtering: {missing}")

    comp = tables["competitions"].copy()
    matches = tables["matches"].copy()
    if comp["comp_id"].duplicated().any():
        raise ValueError("competitions.comp_id must be unique")
    if matches["match_id"].duplicated().any():
        raise ValueError("matches.match_id must be unique")
    meta = matches.merge(
        comp[["comp_id", "comp_name", "match_format", "season"]],
        on="comp_id", how="left", validate="many_to_one", indicator=True
    )
    if meta["_merge"].ne("both").any():
        raise ValueError("Some matches have no competition metadata")
    if scope == "ipl_t20i":
        include = meta["match_format"].eq("T20I") | meta["comp_name"].astype(str).str.fullmatch(IPL_PATTERN)
        scope_description = "IPL seasons 2022 onward plus T20 Internationals"
    elif scope == "all_supplied_t20_t20i":
        include = meta["match_format"].isin(["T20", "T20I"])
        scope_description = "All supplied T20-format competitions plus T20 Internationals (expanded-scope sensitivity only)"
    else:
        raise ValueError(f"Unsupported scope {scope!r}; choose 'ipl_t20i' or 'all_supplied_t20_t20i'")

    selected_match_meta = meta.loc[include].copy()
    selected_match_ids = set(selected_match_meta["match_id"])
    selected_comp_ids = set(selected_match_meta["comp_id"])
    result = {key: value.copy() for key, value in tables.items()}
    result["matches"] = matches.loc[matches["match_id"].isin(selected_match_ids)].copy()
    result["competitions"] = comp.loc[comp["comp_id"].isin(selected_comp_ids)].copy()
    result["ball_by_ball"] = tables["ball_by_ball"].loc[tables["ball_by_ball"]["match_id"].isin(selected_match_ids)].copy()
    result["playing_eleven"] = tables["playing_eleven"].loc[tables["playing_eleven"]["match_id"].isin(selected_match_ids)].copy()
    result["teams"] = tables["teams"].loc[tables["teams"]["comp_id"].isin(selected_comp_ids)].copy()
    result["competition_team_player_mapping"] = tables["competition_team_player_mapping"].loc[
        tables["competition_team_player_mapping"]["comp_id"].isin(selected_comp_ids)
    ].copy()

    ball_match_ids = set(result["ball_by_ball"]["match_id"].dropna().unique())
    comp_counts = (
        selected_match_meta.groupby(["comp_id", "comp_name", "match_format", "season"], dropna=False)
        .agg(match_rows=("match_id", "nunique"))
        .reset_index()
    )
    comp_counts["matches_with_ball_by_ball"] = comp_counts["comp_id"].map(
        selected_match_meta.loc[selected_match_meta["match_id"].isin(ball_match_ids)]
        .groupby("comp_id")["match_id"].nunique()
    ).fillna(0).astype(int)
    comp_counts["matches_without_ball_by_ball"] = comp_counts["match_rows"] - comp_counts["matches_with_ball_by_ball"]

    excluded_matches = meta.loc[~include].copy()
    source_ball_match_ids = set(tables["ball_by_ball"]["match_id"].dropna().unique())
    excluded_matches["has_ball_by_ball"] = excluded_matches["match_id"].isin(source_ball_match_ids)
    excluded = excluded_matches.groupby(
        ["comp_id", "comp_name", "match_format", "season"], dropna=False
    ).agg(
        match_rows=("match_id", "nunique"),
        matches_with_ball_by_ball=("has_ball_by_ball", "sum"),
    ).reset_index()
    excluded["matches_with_ball_by_ball"] = excluded["matches_with_ball_by_ball"].astype(int)
    excluded["matches_without_ball_by_ball"] = (
        excluded["match_rows"] - excluded["matches_with_ball_by_ball"]
    ).astype(int)
    audit = {
        "scope": scope,
        "description": scope_description,
        "selection_rule": "T20I match_format OR exact IPL season 2022 onward competition name" if scope == "ipl_t20i" else "match_format in {T20,T20I}",
        "source_counts": {
            "competitions_rows": int(len(comp)),
            "matches_rows": int(len(matches)),
            "ball_by_ball_rows": int(len(tables["ball_by_ball"])),
            "matches_with_ball_by_ball": int(tables["ball_by_ball"]["match_id"].nunique()),
        },
        "selected_counts": {
            "competition_ids": int(len(selected_comp_ids)),
            "matches": int(len(result["matches"])),
            "matches_with_ball_by_ball": int(result["ball_by_ball"]["match_id"].nunique()),
            "matches_without_ball_by_ball": int(len(result["matches"]) - result["ball_by_ball"]["match_id"].nunique()),
            "ball_by_ball_rows": int(len(result["ball_by_ball"])),
            "playing_eleven_rows": int(len(result["playing_eleven"])),
            "team_rows": int(len(result["teams"])),
            "competition_team_player_mapping_rows": int(len(result["competition_team_player_mapping"])),
        },
        "selected_competitions": comp_counts.to_dict(orient="records"),
        "excluded_competitions": excluded.to_dict(orient="records"),
        "excluded_match_rows": int((~include).sum()),
    }
    return result, audit
