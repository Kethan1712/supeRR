from pathlib import Path

import pytest

from data_layer import DashboardDataError, load_dashboard_data, resolve_project_root


@pytest.fixture(scope="module")
def dashboard_data():
    root = resolve_project_root()
    if root is None:
        pytest.skip("Project root with outputs/ was not found; copy frontend/ beside outputs/ first.")
    try:
        return load_dashboard_data(root)
    except DashboardDataError as exc:
        pytest.fail(str(exc))


def test_primary_leaderboards_have_ten_ranked_players(dashboard_data):
    assert len(dashboard_data["batting_rankings"]) == 10
    assert len(dashboard_data["bowling_rankings"]) == 10
    assert dashboard_data["batting_rankings"]["rank"].tolist() == list(range(1, 11))
    assert dashboard_data["bowling_rankings"]["rank"].tolist() == list(range(1, 11))


def test_player_evidence_and_spotlights_are_loaded(dashboard_data):
    assert len(dashboard_data["batter_evidence"]) == 10
    assert len(dashboard_data["bowler_evidence"]) == 10
    assert len(dashboard_data["batter_spotlights"]) == 10
    assert len(dashboard_data["bowler_spotlights"]) == 10


def test_pressure_totals_and_overlap_are_consistent(dashboard_data):
    audit = dashboard_data["pressure_audit"]
    early = audit["early_collapse_pressure_records"]
    death = audit["death_phase_pressure_records"]
    overlap = audit["overlapping_pressure_records"]
    unique = audit["combined_pressure_records_without_double_counting"]
    assert unique == early + death - overlap


def test_scope_comparison_is_kept_separate(dashboard_data):
    comparison = dashboard_data["scope_comparison"]
    assert comparison["primary_scope"]["matches"] == 853
    assert comparison["expanded_scope"]["matches"] == 883
    assert comparison["batters"]["top10_overlap_out_of_10"] == "9/10"
    assert comparison["bowlers"]["top10_overlap_out_of_10"] == "8/10"
    assert len(dashboard_data["expanded_batting_rankings"]) == 10
    assert len(dashboard_data["expanded_bowling_rankings"]) == 10


def test_rr_strategy_outputs_are_present(dashboard_data):
    assert len(dashboard_data["role_depth"]) == 7
    assert len(dashboard_data["rr_player_fit"]) == 20


def test_pressure_categories_reconcile_to_regular_innings(dashboard_data):
    audit = dashboard_data["pressure_audit"]
    categories = audit["pressure_category_record_counts"]
    classified = sum(int(value) for value in categories.values())
    assert classified == audit["regular_innings_delivery_records"]
    assert audit["additional_innings_delivery_records"] == 26


def test_original_primary_ranking_lock_is_preserved(dashboard_data):
    lock = dashboard_data["release_checks"]["original_ranking_lock"]
    actual_batters = dashboard_data["batting_rankings"].sort_values("rank")["player_name"].tolist()
    actual_bowlers = dashboard_data["bowling_rankings"].sort_values("rank")["player_name"].tolist()
    assert actual_batters == lock["batters"]["players"]
    assert actual_bowlers == lock["bowlers"]["players"]


def test_additional_competitions_are_present_and_separate(dashboard_data):
    comps = dashboard_data["scope_comparison"]["additional_competitions"]
    assert len(comps) == 2
    assert sum(int(item["match_rows"]) for item in comps) == 30
    assert sum(int(item["matches_with_ball_by_ball"]) for item in comps) == 30
    assert dashboard_data["scope_comparison"]["additional_delivery_rows"] == 6985
