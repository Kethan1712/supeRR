"""Role-usage audit for Rajasthan Royals' IPL 2026 squad.

This is a retrospective 2026 diagnostic using the supplied files. It does
not assert that any player will be retained, released, or available in 2027.
"""
from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd

from .match_context import build_match_context
from .pressure_detection import add_pressure_flags
from .bowling_metrics import BOWLER_CREDITED_DISMISSALS


def _as_bool(s: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(s):
        return s.fillna(False)
    return s.astype("string").str.strip().str.casefold().isin({"true", "1", "1.0", "yes", "y"})


def create_rr_2026_role_audit(tables: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, dict]:
    """Return 2026 RR player appearances, observed batting and bowling phase usage."""
    comps = tables["competitions"]
    matches = tables["matches"]
    teams = tables["teams"]
    mapping = tables["competition_team_player_mapping"]
    playing = tables["playing_eleven"]
    ball = tables["ball_by_ball"]

    rr_comp_rows = comps.loc[comps["comp_name"].eq("IPL 2026")]
    if len(rr_comp_rows) != 1:
        raise ValueError("Expected exactly one IPL 2026 competition record")
    comp_id = rr_comp_rows.iloc[0]["comp_id"]
    rr_team_rows = teams.loc[(teams["comp_id"].eq(comp_id)) & teams["team_name"].eq("Rajasthan Royals")]
    if len(rr_team_rows) != 1:
        raise ValueError("Could not uniquely identify Rajasthan Royals in IPL 2026 teams.csv")
    team_id = rr_team_rows.iloc[0]["team_id"]

    roster = mapping.loc[(mapping["comp_id"].eq(comp_id)) & (mapping["team_id"].eq(team_id)), ["player_id", "player_name"]].drop_duplicates()
    if roster["player_id"].duplicated().any():
        raise ValueError("RR 2026 competition mapping has duplicate player IDs")
    match_ids = set(matches.loc[matches["comp_id"].eq(comp_id), "match_id"])
    rr_playing = playing.loc[playing["match_id"].isin(match_ids) & playing["team_id"].eq(team_id)].copy()
    rr_playing["_played"] = _as_bool(rr_playing["is_played"])
    appearance = rr_playing.loc[rr_playing["_played"]].groupby("player_id")["match_id"].nunique()
    roster["matches_played"] = roster["player_id"].map(appearance).fillna(0).astype(int)

    team_match_ids = set(rr_playing.loc[rr_playing["_played"], "match_id"])
    season_ball = ball.loc[ball["match_id"].isin(team_match_ids)].copy()
    context = build_match_context(season_ball, matches.loc[matches["match_id"].isin(team_match_ids)], comps)
    context = add_pressure_flags(context)
    allocation = pd.to_numeric(context["allocation_overs"], errors="coerce")
    over = pd.to_numeric(context["overid"], errors="coerce")
    pp_end = np.ceil(allocation * 0.30)
    death_start = np.floor(allocation * 0.75) + 1
    context["phase"] = np.select(
        [over.le(pp_end), over.ge(death_start)],
        ["powerplay", "death"], default="middle"
    )
    context.loc[~context["is_regular_innings"], "phase"] = "additional_innings_unclassified"

    player_ids = set(roster["player_id"].astype(int))
    bat = context.loc[context["batting_team_id"].eq(team_id) & context["striker_id"].isin(player_ids)].copy()
    wide = bat["extras_type"].astype("string").str.strip().str.casefold().eq("wide").fillna(False)
    bat["balls_faced"] = (~wide).astype(int)
    bat["recorded_runs"] = pd.to_numeric(bat["runs"], errors="coerce").fillna(0)
    bat["is_four"] = _as_bool(bat["is_four"]).astype(int)
    bat["is_six"] = _as_bool(bat["is_six"]).astype(int)
    bat_sum = bat.groupby(["striker_id", "striker_name"]).agg(
        batting_matches=("match_id", "nunique"),
        balls_faced=("balls_faced", "sum"),
        recorded_runs=("recorded_runs", "sum"),
        flagged_fours=("is_four", "sum"),
        flagged_sixes=("is_six", "sum"),
    ).reset_index().rename(columns={"striker_id": "player_id", "striker_name": "source_player_name"})
    bat_phase = bat.groupby(["striker_id", "phase"])["balls_faced"].sum().unstack(fill_value=0)
    bat_phase = bat_phase.rename(columns={
        "powerplay": "batting_powerplay_balls", "middle": "batting_middle_balls", "death": "batting_death_balls"
    }).rename_axis("player_id").reset_index()

    bowl = context.loc[context["bowling_team_id"].eq(team_id) & context["bowler_id"].isin(player_ids)].copy()
    extras = bowl["extras_type"].astype("string").str.strip().str.casefold()
    bowl["candidate_legal_ball"] = (~extras.isin({"wide", "overstep"})).astype(int)
    dismissal = bowl["dismissal_type"].astype("string").str.strip().str.casefold()
    bowl["bowler_credited_wicket"] = (
        _as_bool(bowl["is_wicket"]) & dismissal.isin(BOWLER_CREDITED_DISMISSALS)
    ).astype(int)
    bowl_sum = bowl.groupby(["bowler_id", "bowler_name"]).agg(
        bowling_matches=("match_id", "nunique"),
        bowling_candidate_legal_balls=("candidate_legal_ball", "sum"),
        bowler_credited_wickets=("bowler_credited_wicket", "sum"),
    ).reset_index().rename(columns={"bowler_id": "player_id", "bowler_name": "source_bowler_name"})
    bowl_phase = bowl.groupby(["bowler_id", "phase"]).agg(
        candidate_legal_balls=("candidate_legal_ball", "sum"),
        bowler_credited_wickets=("bowler_credited_wicket", "sum"),
    ).reset_index()
    phase_balls = bowl_phase.pivot(index="bowler_id", columns="phase", values="candidate_legal_balls").fillna(0)
    phase_wkts = bowl_phase.pivot(index="bowler_id", columns="phase", values="bowler_credited_wickets").fillna(0)
    phase_balls = phase_balls.rename(columns={
        "powerplay": "bowling_powerplay_balls", "middle": "bowling_middle_balls", "death": "bowling_death_balls"
    }).rename_axis("player_id").reset_index()
    phase_wkts = phase_wkts.rename(columns={
        "powerplay": "bowling_powerplay_wickets", "middle": "bowling_middle_wickets", "death": "bowling_death_wickets"
    }).rename_axis("player_id").reset_index()

    result = roster.merge(bat_sum.drop(columns="source_player_name"), on="player_id", how="left")
    result = result.merge(bat_phase, on="player_id", how="left")
    result = result.merge(bowl_sum.drop(columns="source_bowler_name"), on="player_id", how="left")
    result = result.merge(phase_balls, on="player_id", how="left")
    result = result.merge(phase_wkts, on="player_id", how="left")
    for col in result.columns:
        if col not in {"player_name"}:
            result[col] = pd.to_numeric(result[col], errors="coerce").fillna(0)
    int_cols = [c for c in result.columns if c != "player_name"]
    result[int_cols] = result[int_cols].astype(int)
    result["batting_recorded_runs_per_100_balls"] = np.where(
        result["balls_faced"].gt(0), result["recorded_runs"] * 100 / result["balls_faced"], np.nan
    )
    audit = {
        "season": "IPL 2026",
        "team": "Rajasthan Royals",
        "competition_id": int(comp_id),
        "team_id": int(team_id),
        "mapped_squad_players": int(len(roster)),
        "team_matches_in_matches_csv": int(len(matches.loc[matches["comp_id"].eq(comp_id) & matches["match_id"].isin(team_match_ids)])),
        "matches_with_played_xi": int(len(team_match_ids)),
        "phase_definition": "Powerplay = first 30% of allocated overs; death = final 25%; middle = intervening overs, same proportional boundaries as the primary model.",
        "bowling_ball_definition": "Candidate legal balls exclude wide and Overstep rows; the count is not claimed to be scorecard-certified.",
        "bowling_wicket_definition": "Bowled, Caught, LBW, Stump and Hit Wicket only; run-outs and other non-bowler dismissals excluded.",
        "interpretation": "Retrospective 2026 role-use audit only. It does not predict 2027 retentions, releases, injury status, or auction availability.",
    }
    return result.sort_values(["matches_played", "recorded_runs", "bowler_credited_wickets"], ascending=[False, False, False]), audit


def save_rr_2026_role_audit(tables: dict[str, pd.DataFrame], output_dir: str | Path = "outputs") -> dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    frame, audit = create_rr_2026_role_audit(tables)
    csv_path = out / "rr_2026_squad_role_audit.csv"
    json_path = out / "rr_2026_squad_role_audit.json"
    frame.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return {"csv": str(csv_path), "audit": str(json_path), "summary": audit}
