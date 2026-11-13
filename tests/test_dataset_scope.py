import pandas as pd
from src.dataset_scope import apply_competition_scope


def _tables():
    return {
        "competitions": pd.DataFrame([
            {"comp_id": 1, "comp_name": "IPL 2022", "match_format": "T20", "season": "2022"},
            {"comp_id": 4, "comp_name": "IPL 2021", "match_format": "T20", "season": "2021"},
            {"comp_id": 2, "comp_name": "Asia Cup Rising Stars 2025", "match_format": "T20", "season": "2025"},
            {"comp_id": 3, "comp_name": "Men's T20I", "match_format": "T20I", "season": "2025"},
        ]),
        "matches": pd.DataFrame([
            {"match_id": 11, "comp_id": 1}, {"match_id": 12, "comp_id": 2}, {"match_id": 13, "comp_id": 3}, {"match_id": 14, "comp_id": 4}
        ]),
        "ball_by_ball": pd.DataFrame([{"match_id": 11}, {"match_id": 12}, {"match_id": 13}, {"match_id": 14}]),
        "playing_eleven": pd.DataFrame([{"match_id": 11, "team_id": 1}, {"match_id": 12, "team_id": 2}, {"match_id": 13, "team_id": 3}, {"match_id": 14, "team_id": 4}]),
        "teams": pd.DataFrame([{"comp_id": 1}, {"comp_id": 2}, {"comp_id": 3}, {"comp_id": 4}]),
        "competition_team_player_mapping": pd.DataFrame([{"comp_id": 1}, {"comp_id": 2}, {"comp_id": 3}, {"comp_id": 4}]),
    }


def test_primary_scope_keeps_ipl_and_t20i_only():
    scoped, audit = apply_competition_scope(_tables())
    assert set(scoped["matches"].match_id) == {11, 13}
    assert set(scoped["competitions"].comp_id) == {1, 3}
    assert audit["selected_counts"]["matches"] == 2
    assert audit["excluded_match_rows"] == 2
    assert 14 not in set(scoped["matches"].match_id)


def test_expanded_scope_keeps_all_t20_and_t20i():
    scoped, audit = apply_competition_scope(_tables(), "all_supplied_t20_t20i")
    assert set(scoped["matches"].match_id) == {11, 12, 13, 14}
    assert audit["excluded_match_rows"] == 0


def test_excluded_competition_audit_includes_ball_by_ball_coverage():
    scoped, audit = apply_competition_scope(_tables())
    excluded = audit["excluded_competitions"]
    rising = next(row for row in excluded if row["comp_name"] == "Asia Cup Rising Stars 2025")
    assert rising["match_rows"] == 1
    assert rising["matches_with_ball_by_ball"] == 1
    assert rising["matches_without_ball_by_ball"] == 0
