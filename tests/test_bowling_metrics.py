import pandas as pd
import pytest

from src.bowling_metrics import calculate_bowling_metrics


def sample_pressure_data():
    return pd.DataFrame(
        [
            # Ordinary: legal ball, bowler-creditable caught wicket.
            {
                "match_id": 1, "innings": 1, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 1,
                "is_four": False, "is_six": False, "is_wicket": True,
                "dismissal_type": "Caught", "extras_type": None,
                "is_regular_innings": True, "is_additional_innings": False,
                "is_early_collapse_pressure": False,
                "is_death_over_pressure": False, "is_pressure": False,
                "innings_ball_num": 1,
            },
            # Ordinary: wide stumping is credited to the bowler; not a legal ball.
            {
                "match_id": 1, "innings": 1, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 0,
                "is_four": False, "is_six": False, "is_wicket": True,
                "dismissal_type": "Stump", "extras_type": "wide",
                "is_regular_innings": True, "is_additional_innings": False,
                "is_early_collapse_pressure": False,
                "is_death_over_pressure": False, "is_pressure": False,
                "innings_ball_num": 2,
            },
            # Death context: no-ball with run-out; not credited to bowler.
            {
                "match_id": 1, "innings": 1, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 0,
                "is_four": False, "is_six": False, "is_wicket": True,
                "dismissal_type": "RunOut", "extras_type": "Overstep",
                "is_regular_innings": True, "is_additional_innings": False,
                "is_early_collapse_pressure": False,
                "is_death_over_pressure": True, "is_pressure": True,
                "innings_ball_num": 3,
            },
            # Death context: legal ball, boundary conceded.
            {
                "match_id": 1, "innings": 1, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 4,
                "is_four": True, "is_six": False, "is_wicket": False,
                "dismissal_type": None, "extras_type": None,
                "is_regular_innings": True, "is_additional_innings": False,
                "is_early_collapse_pressure": False,
                "is_death_over_pressure": True, "is_pressure": True,
                "innings_ball_num": 4,
            },
            # Ambiguous 'other' extra category is retained, not assumed illegal.
            {
                "match_id": 1, "innings": 1, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 4,
                "is_four": True, "is_six": False, "is_wicket": False,
                "dismissal_type": None, "extras_type": "other",
                "is_regular_innings": True, "is_additional_innings": False,
                "is_early_collapse_pressure": False,
                "is_death_over_pressure": False, "is_pressure": False,
                "innings_ball_num": 5,
            },
            # Early-collapse context: byes, legal delivery, zero batter runs.
            {
                "match_id": 2, "innings": 1, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 0,
                "is_four": False, "is_six": False, "is_wicket": False,
                "dismissal_type": None, "extras_type": "byes",
                "is_regular_innings": True, "is_additional_innings": False,
                "is_early_collapse_pressure": True,
                "is_death_over_pressure": False, "is_pressure": True,
                "innings_ball_num": 5,
            },
            # Penalty is in additional innings and is kept as an alternate case.
            {
                "match_id": 3, "innings": 3, "comp_id": 10,
                "bowler_id": 100, "bowler_name": "Bowler A", "runs": 0,
                "is_four": False, "is_six": False, "is_wicket": False,
                "dismissal_type": None, "extras_type": "Penalty",
                "is_regular_innings": False, "is_additional_innings": True,
                "is_early_collapse_pressure": False,
                "is_death_over_pressure": False, "is_pressure": False,
                "innings_ball_num": 1,
            },
        ]
    )


def test_candidate_legal_balls_exclude_wide_and_overstep_but_flag_penalty_variant():
    player, _, _ = calculate_bowling_metrics(sample_pressure_data())
    ordinary = player[player.metric_category == "ordinary_baseline"].iloc[0]
    assert ordinary.bowling_delivery_records == 3
    assert ordinary.candidate_legal_balls == 2
    assert ordinary.candidate_legal_balls_excluding_penalty == 2
    assert ordinary.bowler_credited_wickets == 2  # includes stumping on wide

    additional = player[player.metric_category == "additional_innings_unclassified"].iloc[0]
    assert additional.candidate_legal_balls == 1
    assert additional.candidate_legal_balls_excluding_penalty == 0


def test_runout_is_not_credited_and_boundary_flag_is_counted():
    player, _, _ = calculate_bowling_metrics(sample_pressure_data())
    death = player[player.metric_category == "death_over_context"].iloc[0]
    assert death.bowling_delivery_records == 2
    assert death.candidate_legal_balls == 1
    assert death.bowler_credited_wickets == 0
    assert death.non_bowler_wickets_in_bowling_spell == 1
    assert death.flagged_fours_conceded == 1


def test_early_collapse_is_separately_labelled_as_batting_side_context():
    player, _, audit = calculate_bowling_metrics(sample_pressure_data())
    early = player[player.metric_category == "early_collapse_context"].iloc[0]
    assert early.candidate_legal_balls == 1
    assert "pressure on the batting side" in audit["scope"]["bowling_interpretation"]


def test_audit_does_not_claim_official_economy_or_dot_ball_rate():
    _, _, audit = calculate_bowling_metrics(sample_pressure_data())
    assert "not calculated" in audit["metric_definitions"]["economy_rate"]
    assert "not calculated" in audit["metric_definitions"]["dot_ball_rate"]


def test_missing_bowler_id_is_rejected():
    frame = sample_pressure_data()
    frame.loc[0, "bowler_id"] = None
    with pytest.raises(ValueError, match="bowler_id contains missing values"):
        calculate_bowling_metrics(frame)


def test_missing_extras_type_is_treated_as_candidate_legal_ball():
    player, _, _ = calculate_bowling_metrics(sample_pressure_data())
    ordinary = player[player.metric_category == "ordinary_baseline"].iloc[0]
    assert ordinary.candidate_legal_balls == 2
    assert ordinary.candidate_legal_balls_with_zero_source_runs_field == 0
