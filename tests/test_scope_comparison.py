import pandas as pd
import pytest

from src.scope_comparison import compare_top10


def _ranking(names, scores):
    return pd.DataFrame({
        "rank": list(range(1, len(names) + 1)),
        "player_id": list(range(100, 100 + len(names))),
        "player_name": names,
        "reliability_score": scores,
    })


def test_compare_top10_reports_overlap_entries_exits_and_rank_changes():
    primary_names = [f"P{i}" for i in range(1, 11)]
    expanded_names = ["P1", "P2", "P3", "P5", "P4", "P6", "P7", "P8", "P9", "New"]
    primary = _ranking(primary_names, [90 - i for i in range(10)])
    expanded_ids = [100, 101, 102, 104, 103, 105, 106, 107, 108, 200]
    expanded = pd.DataFrame({
        "rank": list(range(1, 11)),
        "player_id": expanded_ids,
        "player_name": expanded_names,
        "reliability_score": [91, 89, 88, 86, 87, 85, 84, 83, 82, 75],
    })
    summary, rows = compare_top10(primary, expanded, "batter")
    assert summary["top10_overlap_out_of_10"] == "9/10"
    assert summary["players_entering_expanded_top10"] == ["New"]
    assert summary["players_leaving_primary_top10"] == ["P10"]
    p4 = rows.loc[rows.player_name.eq("P4")].iloc[0]
    assert p4["primary_rank"] == 4
    assert p4["expanded_rank"] == 5


def test_compare_top10_rejects_duplicate_player_ids():
    frame = _ranking([f"P{i}" for i in range(1, 11)], [90 - i for i in range(10)])
    frame.loc[1, "player_id"] = frame.loc[0, "player_id"]
    with pytest.raises(ValueError, match="duplicate player IDs"):
        compare_top10(frame, _ranking([f"Q{i}" for i in range(1, 11)], [90 - i for i in range(10)]), "bowler")


def test_compare_top10_requires_ten_rows():
    short = _ranking([f"P{i}" for i in range(1, 10)], [90 - i for i in range(9)])
    full = _ranking([f"Q{i}" for i in range(1, 11)], [90 - i for i in range(10)])
    with pytest.raises(ValueError, match="at least 10 rows"):
        compare_top10(short, full, "batter")


def test_compare_top10_validates_role_name():
    full = _ranking([f"P{i}" for i in range(1, 11)], [90 - i for i in range(10)])
    with pytest.raises(ValueError, match="role must"):
        compare_top10(full, full, "allrounder")
