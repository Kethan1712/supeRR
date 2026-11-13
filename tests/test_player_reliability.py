import pandas as pd
import pytest

from src.player_baselines import calculate_player_baselines
from src.player_reliability import calculate_player_reliability
from tests.test_player_baselines import sample_pressure_rows


def _run_sample(prior_strengths=(30, 60, 100), match_prior=12):
    pressured = sample_pressure_rows()
    baselines = calculate_player_baselines(
        pressured,
        min_peer_opportunities=1,
        min_peer_players=2,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )
    return calculate_player_reliability(
        pressured,
        baselines[0],
        baselines[2],
        prior_strengths=prior_strengths,
        match_prior_opportunities=match_prior,
    )


def test_reliability_outputs_include_sample_adjusted_metrics_and_consistency():
    batting, batting_matches, bowling, bowling_matches, audit = _run_sample()

    assert not batting.empty
    assert not batting_matches.empty
    assert not bowling.empty
    assert not bowling_matches.empty
    assert "sample_adjusted_vs_peer_pct_prior_60" in batting.columns
    assert "positive_match_share_pct" in batting.columns
    assert "matches_with_baseline" in batting.columns
    assert audit["rankings_created"] is False


def test_stronger_prior_shrinks_extreme_small_sample_performance_toward_zero():
    batting, _, _, _, _ = _run_sample(prior_strengths=(0, 30, 60, 100))
    row = batting.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]

    assert abs(row.sample_adjusted_vs_peer_pct_prior_0) > abs(
        row.sample_adjusted_vs_peer_pct_prior_30
    )
    assert abs(row.sample_adjusted_vs_peer_pct_prior_30) > abs(
        row.sample_adjusted_vs_peer_pct_prior_60
    )
    assert abs(row.sample_adjusted_vs_peer_pct_prior_60) > abs(
        row.sample_adjusted_vs_peer_pct_prior_100
    )


def test_match_consistency_uses_distinct_matches_not_delivery_rows():
    batting, batting_matches, _, _, _ = _run_sample()
    summary = batting.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]
    rows = batting_matches.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    )
    assert summary.matches_with_baseline == 5
    assert rows.match_id.nunique() == 5
    assert summary.positive_match_share_pct == pytest.approx(
        rows.match_adjusted_vs_peer_pct.gt(0).mean() * 100
    )


def test_more_match_prior_shrinks_one_match_extreme_toward_peer():
    pressured = sample_pressure_rows()
    baselines = calculate_player_baselines(
        pressured,
        min_peer_opportunities=1,
        min_peer_players=2,
        min_fallback_opportunities=1,
        min_fallback_players=2,
    )
    small_prior = calculate_player_reliability(
        pressured, baselines[0], baselines[2], match_prior_opportunities=0
    )[1]
    large_prior = calculate_player_reliability(
        pressured, baselines[0], baselines[2], match_prior_opportunities=30
    )[1]
    keys = ["player_id", "metric_category", "metric", "match_id"]
    a = small_prior.merge(large_prior, on=keys, suffixes=("_small", "_large"))
    row = a.query(
        "player_id == 1 and metric_category == 'death_over_pressure' "
        "and metric == 'recorded_runs_per_100_balls'"
    ).iloc[0]
    assert abs(row.match_adjusted_vs_peer_pct_small) > abs(
        row.match_adjusted_vs_peer_pct_large
    )


def test_diagnostic_bowling_source_runs_are_not_in_reliability_metrics():
    _, _, bowling, _, _ = _run_sample()
    assert not bowling.metric.str.contains("source_runs_field").any()


def test_no_supported_peer_baselines_produce_no_fabricated_adjusted_score():
    pressured = sample_pressure_rows()
    baselines = calculate_player_baselines(
        pressured,
        min_peer_opportunities=10_000,
        min_peer_players=100,
        min_fallback_opportunities=10_000,
        min_fallback_players=100,
    )
    batting, _, bowling, _, audit = calculate_player_reliability(
        pressured, baselines[0], baselines[2]
    )
    assert batting.empty
    assert bowling.empty
    assert audit["batting"]["matched_rows"] == 0
    assert audit["bowling"]["matched_rows"] == 0


def test_player_reliability_does_not_create_rankings():
    *_, audit = _run_sample()
    assert audit["rankings_created"] is False
    assert "top_10" not in audit
