import pandas as pd

from src.batting_metrics import calculate_batting_metrics


def _pressure_frame(rows):
    frame = pd.DataFrame(rows)
    defaults = {
        "innings": 1,
        "comp_id": 1,
        "comp_name": "Test Competition",
        "match_format": "T20",
        "season": "Test Season",
        "is_regular_innings": True,
        "is_additional_innings": False,
        "is_early_collapse_pressure": False,
        "is_death_over_pressure": False,
        "is_pressure": False,
        "is_wicket": False,
        "runs": 0,
        "dismissed_player_id": None,
        "extras_type": None,
        "is_four": False,
        "is_six": False,
        "runs": 0,
        "non_striker_id": 2,
        "non_striker_name": "Player B",
    }
    for column, value in defaults.items():
        if column not in frame:
            frame[column] = value
    return frame


def test_wides_excluded_from_balls_faced_but_no_balls_count():
    frame = _pressure_frame([
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 1, "extras_type": None},
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 0, "extras_type": "wide"},
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 4, "extras_type": "Overstep", "is_four": True},
    ])
    player, _, audit = calculate_batting_metrics(frame)
    row = player.query("player_id == 1 and metric_category == 'ordinary_baseline'").iloc[0]
    assert row.balls_faced == 2
    assert row.recorded_runs == 5
    assert row.flagged_fours == 1
    assert audit["source_coverage"]["wide_records"] == 1
    assert audit["source_coverage"]["overstep_records_counted_as_faced"] == 1


def test_dismissal_is_attributed_to_dismissed_player_not_automatically_striker():
    frame = _pressure_frame([
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "non_striker_id": 2, "non_striker_name": "Player B", "runs": 1},
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "non_striker_id": 2, "non_striker_name": "Player B", "is_wicket": True, "runs": 0, "dismissed_player_id": 2, "dismissal_type": "RunOut"},
        {"match_id": 1, "striker_id": 2, "striker_name": "Player B", "non_striker_id": 1, "non_striker_name": "Player A", "runs": 2},
    ])
    player, _, audit = calculate_batting_metrics(frame)
    a = player.query("player_id == 1 and metric_category == 'ordinary_baseline'").iloc[0]
    b = player.query("player_id == 2 and metric_category == 'ordinary_baseline'").iloc[0]
    assert a.attributed_dismissals == 0
    assert b.attributed_dismissals == 1
    assert audit["dismissal_attribution_checks"]["dismissals_attributed_to_non_striker"] == 1


def test_pressure_categories_and_union_do_not_duplicate_combined_pressure():
    frame = _pressure_frame([
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 4, "is_four": True, "is_death_over_pressure": True, "is_pressure": True},
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 6, "is_six": True, "is_early_collapse_pressure": True, "is_death_over_pressure": True, "is_pressure": True},
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 1},
    ])
    player, _, _ = calculate_batting_metrics(frame)
    lookup = player.set_index("metric_category")
    assert lookup.loc["early_collapse_pressure", "balls_faced"] == 1
    assert lookup.loc["death_over_pressure", "balls_faced"] == 2
    assert lookup.loc["combined_pressure", "balls_faced"] == 2
    assert lookup.loc["ordinary_baseline", "balls_faced"] == 1


def test_additional_innings_retained_in_separate_category():
    frame = _pressure_frame([
        {"match_id": 1, "innings": 3, "is_regular_innings": False, "is_additional_innings": True,
         "striker_id": 1, "striker_name": "Player A", "runs": 3},
    ])
    player, _, audit = calculate_batting_metrics(frame)
    assert len(player) == 1
    assert player.iloc[0].metric_category == "additional_innings_unclassified"
    assert audit["source_coverage"]["additional_innings_records"] == 1


def test_missing_dismissed_player_id_is_reported_not_guessed():
    frame = _pressure_frame([
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "is_wicket": True,
         "dismissed_player_id": None, "dismissal_type": "Retire Out"},
    ])
    player, _, audit = calculate_batting_metrics(frame)
    assert player.iloc[0].attributed_dismissals == 0
    assert audit["dismissal_attribution_checks"]["dismissed_player_id_missing"] == 1


def test_innings_batted_counts_match_innings_pairs_not_only_innings_numbers():
    frame = _pressure_frame([
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 1},
        {"match_id": 2, "striker_id": 1, "striker_name": "Player A", "runs": 2},
    ])
    player, _, _ = calculate_batting_metrics(frame)
    row = player.query("player_id == 1 and metric_category == 'ordinary_baseline'").iloc[0]
    assert row.innings_batted == 2
    assert row.matches_represented == 2


def test_match_level_additive_totals_reconcile_to_player_level():
    frame = _pressure_frame([
        {"match_id": 1, "striker_id": 1, "striker_name": "Player A", "runs": 1},
        {"match_id": 2, "striker_id": 1, "striker_name": "Player A", "runs": 4, "is_four": True, "is_death_over_pressure": True, "is_pressure": True},
    ])
    player, matches, _ = calculate_batting_metrics(frame)
    keys = ["player_id", "player_name", "metric_category"]
    additive = ["balls_faced", "balls_faced_excluding_penalty", "recorded_runs", "flagged_fours", "flagged_sixes", "attributed_dismissals"]
    summed = matches.groupby(keys, dropna=False)[additive].sum().reset_index()
    merged = player.merge(summed, on=keys, suffixes=("_player", "_matches"), validate="one_to_one")
    for column in additive:
        assert (merged[f"{column}_player"] == merged[f"{column}_matches"]).all()
