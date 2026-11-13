import pandas as pd

from src.baseline_charts import create_baseline_charts


def test_baseline_charts_are_created(tmp_path):
    batting = pd.DataFrame([
        {"player_id": 1, "player_name": "A", "metric": "recorded_runs_per_100_balls",
         "metric_category": "ordinary_baseline", "relative_performance_vs_peer_pct": 10.0,
         "opportunities": 50},
        {"player_id": 1, "player_name": "A", "metric": "recorded_runs_per_100_balls",
         "metric_category": "combined_pressure", "relative_performance_vs_peer_pct": 15.0,
         "opportunities": 20},
    ])
    bowling = pd.DataFrame([
        {"player_id": 1, "player_name": "A", "metric": "bowler_wickets_per_100_candidate_legal_balls",
         "metric_category": "ordinary_baseline", "relative_performance_vs_peer_pct": -5.0,
         "opportunities": 50},
        {"player_id": 1, "player_name": "A", "metric": "bowler_wickets_per_100_candidate_legal_balls",
         "metric_category": "death_over_context", "relative_performance_vs_peer_pct": 5.0,
         "opportunities": 20},
    ])
    result = create_baseline_charts(
        batting, bowling, tmp_path, min_plot_opportunities=1
    )
    assert result["batting"]["players_plotted"] == 1
    assert result["bowling"]["players_plotted"] == 1
    assert (tmp_path / "batting_peer_baseline_scatter.png").is_file()
    assert (tmp_path / "bowling_peer_baseline_scatter.png").is_file()
