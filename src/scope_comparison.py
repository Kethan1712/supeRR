"""Compare independently generated primary and expanded-scope top-10 rankings."""
from __future__ import annotations

from typing import Any
import pandas as pd

REQUIRED = {"rank", "player_id", "player_name", "reliability_score"}


def compare_top10(primary: pd.DataFrame, expanded: pd.DataFrame, role: str) -> tuple[dict[str, Any], pd.DataFrame]:
    """Compare top-10 lists by stable player ID, not display name."""
    if role not in {"batter", "bowler"}:
        raise ValueError("role must be 'batter' or 'bowler'")
    for label, frame in (("primary", primary), ("expanded", expanded)):
        missing = REQUIRED - set(frame.columns)
        if missing:
            raise ValueError(f"{label} {role} ranking is missing columns: {sorted(missing)}")
        if frame["player_id"].duplicated().any():
            raise ValueError(f"{label} {role} ranking has duplicate player IDs")
    p = primary.sort_values("rank").head(10).copy()
    e = expanded.sort_values("rank").head(10).copy()
    if len(p) != 10 or len(e) != 10:
        raise ValueError(f"Both {role} rankings must contain at least 10 rows")

    p_by_id = p.set_index("player_id", drop=False)
    e_by_id = e.set_index("player_id", drop=False)
    p_ids, e_ids = set(p_by_id.index), set(e_by_id.index)
    shared = p_ids & e_ids
    entered = e_ids - p_ids
    left = p_ids - e_ids

    rows: list[dict[str, Any]] = []
    for player_id in sorted(p_ids | e_ids, key=lambda pid: (
        int(e_by_id.loc[pid, "rank"]) if pid in e_ids else 99,
        int(p_by_id.loc[pid, "rank"]) if pid in p_ids else 99,
        str(e_by_id.loc[pid, "player_name"]) if pid in e_ids else str(p_by_id.loc[pid, "player_name"]),
    )):
        pr = p_by_id.loc[player_id] if player_id in p_ids else None
        er = e_by_id.loc[player_id] if player_id in e_ids else None
        rows.append({
            "role": role,
            "player_id": int(player_id),
            "player_name": str(er["player_name"] if er is not None else pr["player_name"]),
            "status": "retained" if player_id in shared else ("entered" if player_id in entered else "left"),
            "primary_rank": int(pr["rank"]) if pr is not None else None,
            "expanded_rank": int(er["rank"]) if er is not None else None,
            "primary_score": float(pr["reliability_score"]) if pr is not None else None,
            "expanded_score": float(er["reliability_score"]) if er is not None else None,
            "rank_change_expanded_minus_primary": int(er["rank"]) - int(pr["rank"]) if player_id in shared else None,
            "score_change_expanded_minus_primary": float(er["reliability_score"]) - float(pr["reliability_score"]) if player_id in shared else None,
        })

    def compact(frame: pd.DataFrame) -> list[dict[str, Any]]:
        return [{
            "rank": int(row.rank), "player_id": int(row.player_id),
            "player_name": str(row.player_name),
            "score": round(float(row.reliability_score), 6),
        } for row in frame.itertuples(index=False)]

    summary = {
        "role": role,
        "primary_top10": compact(p),
        "expanded_top10": compact(e),
        "top10_overlap_count": len(shared),
        "top10_overlap_out_of_10": f"{len(shared)}/10",
        "players_entering_expanded_top10": [str(e_by_id.loc[x, "player_name"]) for x in sorted(entered, key=lambda x: int(e_by_id.loc[x, "rank"]))],
        "players_leaving_primary_top10": [str(p_by_id.loc[x, "player_name"]) for x in sorted(left, key=lambda x: int(p_by_id.loc[x, "rank"]))],
        "shared_player_rank_changes": [r for r in rows if r["status"] == "retained" and r["primary_rank"] != r["expanded_rank"]],
    }
    return summary, pd.DataFrame(rows)
