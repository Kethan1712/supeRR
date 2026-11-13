"""Create exploratory graphs comparing ordinary and pressure peer standing."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _scatter_baseline(
    summary: pd.DataFrame,
    *,
    role: str,
    ordinary_category: str,
    pressure_category: str,
    metric: str,
    title: str,
    output_path: Path,
    min_plot_opportunities: int,
) -> dict:
    selected = summary.loc[
        summary["metric"].eq(metric)
        & summary["metric_category"].isin([ordinary_category, pressure_category])
    ].copy()
    if selected.empty:
        return {"path": str(output_path), "players_plotted": 0, "status": "no_data"}

    ordinary = selected.loc[
        selected["metric_category"].eq(ordinary_category),
        ["player_id", "relative_performance_vs_peer_pct", "opportunities"],
    ].rename(columns={
        "relative_performance_vs_peer_pct": "ordinary_vs_peer_pct",
        "opportunities": "opportunities_ordinary",
    })
    pressure = selected.loc[
        selected["metric_category"].eq(pressure_category),
        ["player_id", "player_name", "relative_performance_vs_peer_pct", "opportunities"],
    ].rename(columns={
        "relative_performance_vs_peer_pct": "pressure_vs_peer_pct",
        "opportunities": "opportunities_pressure",
    })
    plotted = pressure.merge(ordinary, on="player_id", how="inner", validate="one_to_one")
    plotted = plotted.dropna(subset=["ordinary_vs_peer_pct", "pressure_vs_peer_pct"])
    plotted = plotted.loc[
        plotted["opportunities_pressure"].ge(min_plot_opportunities)
        & plotted["opportunities_ordinary"].ge(min_plot_opportunities)
    ]
    if plotted.empty:
        return {"path": str(output_path), "players_plotted": 0, "status": "no_matched_players"}

    fig, ax = plt.subplots(figsize=(9, 7))
    ax.scatter(
        plotted["ordinary_vs_peer_pct"],
        plotted["pressure_vs_peer_pct"],
        s=18,
        alpha=0.65,
    )
    ax.axhline(0, linewidth=1, linestyle="--")
    ax.axvline(0, linewidth=1, linestyle="--")
    ax.set_xlabel("Ordinary performance vs context-matched peer average (%)")
    ax.set_ylabel("Pressure performance vs context-matched peer average (%)")
    ax.set_title(f"{title}\nExploratory view: at least {min_plot_opportunities} opportunities in each context")
    ax.grid(True, alpha=0.2)
    ax.text(
        0.02, 0.98,
        "Above 0 = better than peer average\nUpper-right = above peers in both contexts",
        transform=ax.transAxes,
        va="top",
        ha="left",
    )
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return {
        "path": str(output_path),
        "players_plotted": int(len(plotted)),
        "status": "created",
        "role": role,
        "pressure_category": pressure_category,
        "metric": metric,
    }


def create_baseline_charts(
    batting_summary: pd.DataFrame,
    bowling_summary: pd.DataFrame,
    output_dir: str | Path = "outputs/charts",
    *,
    min_plot_opportunities: int = 60,
) -> dict:
    """Create one primary batting and bowling baseline comparison scatter plot."""
    output = Path(output_dir)
    batting_result = _scatter_baseline(
        batting_summary,
        role="batter",
        ordinary_category="ordinary_baseline",
        pressure_category="combined_pressure",
        metric="recorded_runs_per_100_balls",
        title="Batters: ordinary vs combined-pressure standing against peers",
        output_path=output / "batting_peer_baseline_scatter.png",
        min_plot_opportunities=min_plot_opportunities,
    )
    bowling_result = _scatter_baseline(
        bowling_summary,
        role="bowler",
        ordinary_category="ordinary_baseline",
        pressure_category="death_over_context",
        metric="bowler_wickets_per_100_candidate_legal_balls",
        title="Bowlers: ordinary vs death-over wicket-taking standing against peers",
        output_path=output / "bowling_peer_baseline_scatter.png",
        min_plot_opportunities=min_plot_opportunities,
    )
    return {"batting": batting_result, "bowling": bowling_result}
