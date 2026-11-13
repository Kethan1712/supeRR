import pandas as pd
from src.player_ratings import calculate_rankings


def _make_role_rows(players, metrics, categories, role, prior=60):
    rows = []
    for pid, name, pressure_opp, pressure_matches, ordinary_opp, ordinary_matches, strength in players:
        for metric in metrics:
            for category in categories:
                pressure = category != "ordinary_baseline"
                base = {
                    "player_id": pid, "player_name": name, "metric_category": category,
                    "metric": metric, "metric_direction": "higher_is_better",
                    "all_opportunities": pressure_opp if pressure else ordinary_opp,
                    "matches_in_category": pressure_matches if pressure else ordinary_matches,
                    "baseline_coverage_pct": 100.0,
                    "matches_with_peer_baseline": pressure_matches if pressure else ordinary_matches,
                    f"sample_adjusted_vs_peer_pct_prior_{prior}": strength if pressure else 0.0,
                    "positive_match_share_pct": 60.0 + (pid % 30),
                    "median_match_adjusted_vs_peer_pct": strength / 2 if pressure else 1.0,
                    "std_match_adjusted_vs_peer_pct": 8.0,
                }
                rows.append(base)
    return pd.DataFrame(rows)


def test_rankings_require_pressure_and_ordinary_samples():
    bat = _make_role_rows(
        [(1, "A", 120, 10, 150, 10, 20), (2, "B", 120, 10, 150, 10, 10), (3, "C", 50, 4, 150, 10, 50)],
        ["recorded_runs_per_100_balls", "boundaries_per_100_balls", "dismissals_per_100_balls"],
        ["combined_pressure", "ordinary_baseline"], "batter")
    bowl = _make_role_rows(
        [(11, "X", 80, 10, 90, 10, 20), (12, "Y", 80, 10, 90, 10, 10), (13, "Z", 10, 2, 90, 10, 60)],
        ["bowler_wickets_per_100_candidate_legal_balls", "flagged_boundaries_per_100_candidate_legal_balls"],
        ["death_over_context", "ordinary_baseline"], "bowler")
    b, w, _, _, audit = calculate_rankings(bat, bowl, min_batter_opportunities=100,
        min_bowler_opportunities=60, min_matches=8)
    assert b.player_name.tolist() == ["A", "B"]
    assert w.player_name.tolist() == ["X", "Y"]
    assert audit["rankings_created"] is True


def test_ratings_are_bounded_0_100():
    # Use the same small controlled fixture, then verify percentile composite range.
    bat = _make_role_rows(
        [(i, f"B{i}", 120, 10, 150, 10, i * 3) for i in range(1, 5)],
        ["recorded_runs_per_100_balls", "boundaries_per_100_balls", "dismissals_per_100_balls"],
        ["combined_pressure", "ordinary_baseline"], "batter")
    bowl = _make_role_rows(
        [(i+10, f"W{i}", 80, 10, 90, 10, i * 3) for i in range(1, 5)],
        ["bowler_wickets_per_100_candidate_legal_balls", "flagged_boundaries_per_100_candidate_legal_balls"],
        ["death_over_context", "ordinary_baseline"], "bowler")
    b, w, _, _, _ = calculate_rankings(bat, bowl)
    assert b.reliability_score.between(0, 100).all()
    assert w.reliability_score.between(0, 100).all()
