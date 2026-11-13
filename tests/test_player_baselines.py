import pandas as pd
import pytest

from src.player_baselines import calculate_player_baselines, _add_innings_phase


def sample_pressure_rows():
    rows = []
    names = {1: "Player A", 2: "Player B", 3: "Player C", 4: "Player D"}
    for player_id, name in names.items():
        for category, overid, pressure in [("ordinary", 7, False), ("death", 16, True)]:
            for ball in range(1, 6):
                runs = 2 if player_id == 1 and pressure else 1
                wicket = pressure and player_id == 1 and ball == 1
                rows.append({
                    "match_id": 100 + ball,
                    "innings": 1,
                    "comp_id": 10,
                    "comp_name": "Sample T20 Competition",
                    "match_format": "T20",
                    "season": "2025",
                    "overid": overid,
                    "innings_ball_num": ball + (0 if not pressure else 100),
                    "allocation_overs": 20.0,
                    "striker_id": player_id,
                    "striker_name": name,
                    "non_striker_id": 99,
                    "non_striker_name": "Other Player",
                    "bowler_id": player_id,
                    "bowler_name": name,
                    "runs": runs,
                    "is_four": False,
                    "is_six": False,
                    "is_wicket": wicket,
                    "dismissal_type": "Bowled" if wicket else None,
                    "dismissed_player_id": player_id if wicket else None,
                    "extras_type": None,
                    "is_regular_innings": True,
                    "is_additional_innings": False,
                    "is_early_collapse_pressure": False,
                    "is_death_over_pressure": pressure,
                    "is_pressure": pressure,
                })
    return pd.DataFrame(rows)


def test_standard_20_over_phase_boundaries():
    frame = pd.DataFrame({
        "overid": [1, 6, 7, 15, 16, 20],
        "allocation_overs": [20] * 6,
        "is_regular_innings": [True] * 6,
    })
    result = _add_innings_phase(frame)
    assert result.innings_phase.tolist() == [
        "powerplay", "powerplay", "middle", "middle", "death", "death"
    ]


def test_peer_baseline_is_leave_one_player_out_and_identifies_above_average():
    outputs = calculate_player_baselines(
        sample_pressure_rows(),
        min_peer_opportunities=1,
        min_peer_players=2,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )
    batting_context, batting_summary = outputs[0], outputs[1]
    row = batting_context.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]
    # Player A scores 200 per 100 balls; the other three average 100.
    assert row.player_rate == pytest.approx(200.0)
    assert row.peer_rate == pytest.approx(100.0)
    assert row.league_rate == pytest.approx(125.0)  # includes Player A in the full league mean
    assert row.relative_performance_vs_peer_pct == pytest.approx(100.0)

    summary = batting_summary.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]
    assert summary.relative_change_vs_ordinary_pct > 90


def test_peer_baseline_falls_back_to_format_season_when_competition_is_sparse():
    data = sample_pressure_rows()
    # Two players are split across two competition IDs; a competition-level
    # peer cohort has only one other player, while format-season has three.
    data.loc[data.striker_id.isin([3, 4]), "comp_id"] = 11
    data.loc[data.bowler_id.isin([3, 4]), "comp_id"] = 11
    data.loc[data.striker_id.isin([3, 4]), "comp_name"] = "Second T20 Competition"
    data.loc[data.bowler_id.isin([3, 4]), "comp_name"] = "Second T20 Competition"
    outputs = calculate_player_baselines(
        data,
        min_peer_opportunities=1000,
        min_peer_players=3,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )
    context = outputs[0]
    row = context.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]
    assert row.peer_baseline_scope in {
        "format_season_innings_phase", "format_innings_phase"
    }


def test_bowling_source_runs_metric_is_diagnostic_only():
    outputs = calculate_player_baselines(
        sample_pressure_rows(),
        min_peer_opportunities=1,
        min_peer_players=2,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )
    bowling_summary = outputs[3]
    row = bowling_summary.query(
        "metric == 'source_runs_field_per_100_candidate_legal_balls'"
    ).iloc[0]
    assert not bool(row.rating_eligible)


def test_no_supported_peer_group_is_retained_as_unmatched_not_guessed():
    data = sample_pressure_rows()
    outputs = calculate_player_baselines(
        data,
        min_peer_opportunities=10_000,
        min_peer_players=100,
        min_fallback_opportunities=10_000,
        min_fallback_players=100,
    )
    context = outputs[0]
    assert context.peer_rate.isna().all()
    assert context.peer_baseline_scope.isna().all()


def test_bowling_early_collapse_is_explicitly_a_batting_side_context():
    audit = calculate_player_baselines(
        sample_pressure_rows(),
        min_peer_opportunities=1,
        min_peer_players=2,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )[-1]
    assert "not automatically classified as pressure on the bowler" in audit["bowling_pressure_caveat"]
    assert audit["rankings_created"] is False


def test_peer_benchmark_table_contains_full_league_and_leave_one_out_rates():
    outputs = calculate_player_baselines(
        sample_pressure_rows(),
        min_peer_opportunities=1,
        min_peer_players=2,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )
    league = outputs[4]
    row = league.query(
        "role == 'batter' and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]
    assert "league_rate" in league.columns
    assert "peer_rate" not in league.columns
    assert row.league_rate == pytest.approx(125.0)
    assert row.league_opportunities > 0
    assert row.league_players == 4
