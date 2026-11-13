"""Generate final evidence charts from audited ranking outputs."""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt


def _bar_chart(frame: pd.DataFrame, title: str, path: Path) -> None:
    if frame.empty:
        return
    chart = frame.sort_values("rank", ascending=True).copy()
    chart = chart.sort_values("reliability_score", ascending=True)
    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.barh(chart["player_name"], chart["reliability_score"])
    ax.set_xlabel("Pressure Reliability Index (0-100)")
    ax.set_title(title)
    ax.set_xlim(0, 100)
    ax.grid(axis="x", alpha=0.25)
    for y, value in enumerate(chart["reliability_score"]):
        ax.text(value + 0.8, y, f"{value:.1f}", va="center", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)


def create_ranking_visuals(output_dir: str | Path = "outputs") -> dict:
    out = Path(output_dir)
    charts = out / "charts"
    batting = pd.read_csv(out / "batting_rankings_top10.csv")
    bowling = pd.read_csv(out / "bowling_rankings_top10.csv")
    stability_path = out / "pressure_threshold_ranking_stability.csv"
    stability = pd.read_csv(stability_path) if stability_path.exists() else pd.DataFrame()

    bat_path = charts / "batting_top10_reliability.png"
    bowl_path = charts / "bowling_top10_reliability.png"
    _bar_chart(batting, "Top 10 Batters Under Pressure", bat_path)
    _bar_chart(bowling, "Top 10 Bowlers Under Pressure", bowl_path)

    overlap_path = charts / "pressure_cutoff_top10_overlap.png"
    if not stability.empty:
        plot = stability.set_index("collapse_cutoff_over_standard_20")[[
            "batting_top10_overlap_primary", "bowling_top10_overlap_primary"
        ]]
        fig, ax = plt.subplots(figsize=(7.5, 4.6))
        plot.plot(kind="bar", ax=ax)
        ax.set_xlabel("Early-collapse cutoff (standard 20-over innings)")
        ax.set_ylabel("Shared players with the primary top 10")
        ax.set_title("Top-10 Membership Stability Under Alternative Collapse Cutoffs")
        ax.set_ylim(0, 10.5)
        ax.set_yticks(range(0, 11, 1))
        ax.grid(axis="y", alpha=0.25)
        ax.legend(["Batters", "Bowlers"], frameon=False)
        fig.tight_layout()
        fig.savefig(overlap_path, dpi=180, bbox_inches="tight")
        plt.close(fig)

    return {
        "batting_top10_chart": str(bat_path),
        "bowling_top10_chart": str(bowl_path),
        "pressure_cutoff_stability_chart": str(overlap_path) if not stability.empty else None,
    }
