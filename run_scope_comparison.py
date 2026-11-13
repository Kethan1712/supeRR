"""Re-run the complete ranking pipeline under both documented competition scopes.

Primary scope: IPL 2022 onward + T20 Internationals.
Expanded sensitivity scope: every supplied T20-format competition + T20Is.

The runs execute the full ranking dependency pipeline in isolated temporary
working directories. Optional report-only audits are not repeated here because
they do not affect the ranking outputs being compared.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from src.scope_comparison import compare_top10

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "scope_comparison"
PIPELINE_FLAGS = ["--audit-rankings"]


def _run_scope(scope: str, data_dir: Path, run_root: Path) -> tuple[Path, list[str]]:
    run_root.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable, str(PROJECT_ROOT / "main.py"), *PIPELINE_FLAGS,
        "--scope", scope, "--data-dir", str(data_dir),
    ]
    env = os.environ.copy()
    env.setdefault("PYTHONHASHSEED", "0")
    log_path = run_root / "pipeline.log"
    with log_path.open("w", encoding="utf-8") as log:
        completed = subprocess.run(
            command, cwd=run_root, env=env, stdout=log,
            stderr=subprocess.STDOUT, text=True, check=False,
        )
    if completed.returncode != 0:
        tail = log_path.read_text(encoding="utf-8", errors="replace")[-6000:]
        raise RuntimeError(
            f"Scope run {scope!r} failed with exit code {completed.returncode}.\n{tail}"
        )
    output = run_root / "outputs"
    required = [
        "competition_scope_audit.json", "batting_rankings_top10.csv",
        "bowling_rankings_top10.csv", "batting_candidate_scores.csv",
        "bowling_candidate_scores.csv", "metric_weight_sensitivity.csv",
    ]
    missing = [name for name in required if not (output / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Scope run {scope!r} did not create required outputs: {missing}")
    audit = json.loads((output / "competition_scope_audit.json").read_text(encoding="utf-8"))
    if audit.get("scope") != scope:
        raise AssertionError(f"Scope audit mismatch: requested {scope}, got {audit.get('scope')}")
    return output, command


def _copy_expanded_evidence(expanded_output: Path) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    copies = {
        "batting_rankings_top10.csv": "expanded_batting_rankings_top10.csv",
        "bowling_rankings_top10.csv": "expanded_bowling_rankings_top10.csv",
        "batting_candidate_scores.csv": "expanded_batting_candidate_scores.csv",
        "bowling_candidate_scores.csv": "expanded_bowling_candidate_scores.csv",
        "competition_scope_audit.json": "expanded_competition_scope_audit.json",
        "metric_weight_sensitivity.csv": "expanded_metric_weight_sensitivity.csv",
    }
    for source, target in copies.items():
        shutil.copy2(expanded_output / source, OUTPUT_DIR / target)


def _write_markdown(summary: dict[str, Any]) -> None:
    p = summary["primary_scope"]
    e = summary["expanded_scope"]
    b = summary["batters"]
    w = summary["bowlers"]
    lines = [
        "# Competition-scope sensitivity analysis", "",
        "The primary ranking uses IPL 2022 onward and T20 Internationals. The expanded run includes all supplied T20-format competitions plus T20Is. Both runs were independently recalculated from the six source CSVs using the same pipeline and scoring settings.", "",
        "| Measure | Primary: IPL + T20I | Expanded: all supplied T20 + T20I |",
        "|---|---:|---:|",
        f"| Competition IDs represented | {p['competition_ids']} | {e['competition_ids']} |",
        f"| Match rows | {p['matches']} | {e['matches']} |",
        f"| Matches with ball-by-ball data | {p['matches_with_ball_by_ball']} | {e['matches_with_ball_by_ball']} |",
        f"| Delivery rows | {p['ball_by_ball_rows']:,} | {e['ball_by_ball_rows']:,} |",
        "",
        "## Additional competitions in the expanded scope", "",
    ]
    for comp in summary["additional_competitions"]:
        lines.append(f"- {comp['comp_name']}: {comp['match_rows']} matches; {comp['matches_with_ball_by_ball']} with ball-by-ball data.")
    lines += [
        "", "## Top-10 comparison", "",
        f"- Batters: {b['top10_overlap_out_of_10']} overlap. Entering: {', '.join(b['players_entering_expanded_top10']) or 'None'}. Leaving: {', '.join(b['players_leaving_primary_top10']) or 'None'}.",
        f"- Bowlers: {w['top10_overlap_out_of_10']} overlap. Entering: {', '.join(w['players_entering_expanded_top10']) or 'None'}. Leaving: {', '.join(w['players_leaving_primary_top10']) or 'None'}.",
        "",
        "## Interpretation", "",
        "This is a population-definition sensitivity test, not a claim that either competition pool is universally correct. Adding competitions can add eligible players and opportunities, and can also change context-matched peer cohorts and relative scores. The primary ranking remains the IPL 2022 onward + T20I list because that is the population named in the Round 1 brief. The expanded rankings are retained as a transparent supplementary result; they do not overwrite the primary ranking CSVs.",
        "",
        "## Reproduction", "",
        "Run `python run_scope_comparison.py` from the project root. The script executes both full pipelines in isolated temporary working directories and writes the summary, player-level changes, expanded top-10 CSVs, full candidate score CSVs, scope audit, and run logs under `outputs/scope_comparison/`.",
        "",
    ]
    (OUTPUT_DIR / "competition_scope_comparison.md").write_text("\n".join(lines), encoding="utf-8")


def run(data_dir: Path) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {data_dir}")
    required_data = [
        "ball_by_ball.csv", "matches.csv", "competitions.csv", "playing_eleven.csv",
        "teams.csv", "competition_team_player_mapping.csv",
    ]
    missing = [name for name in required_data if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Data directory is missing required CSV files: {missing}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log_dir = OUTPUT_DIR / "run_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="suprr_scope_runs_") as temp:
        temp_root = Path(temp)
        primary_output, primary_command = _run_scope("ipl_t20i", data_dir, temp_root / "primary")
        expanded_output, expanded_command = _run_scope(
            "all_supplied_t20_t20i", data_dir, temp_root / "expanded"
        )

        primary_audit = json.loads((primary_output / "competition_scope_audit.json").read_text(encoding="utf-8"))
        expanded_audit = json.loads((expanded_output / "competition_scope_audit.json").read_text(encoding="utf-8"))
        bat_summary, bat_players = compare_top10(
            pd.read_csv(primary_output / "batting_rankings_top10.csv"),
            pd.read_csv(expanded_output / "batting_rankings_top10.csv"), "batter"
        )
        bowl_summary, bowl_players = compare_top10(
            pd.read_csv(primary_output / "bowling_rankings_top10.csv"),
            pd.read_csv(expanded_output / "bowling_rankings_top10.csv"), "bowler"
        )

        additional = primary_audit.get("excluded_competitions", [])
        additional_competitions = []
        for item in additional:
            matches = int(item.get("match_rows", 0))
            with_balls = int(item.get("matches_with_ball_by_ball", 0))
            additional_competitions.append({
                "comp_id": int(item["comp_id"]),
                "comp_name": str(item["comp_name"]),
                "match_format": str(item["match_format"]),
                "season": str(item.get("season", "")),
                "match_rows": matches,
                "matches_with_ball_by_ball": with_balls,
                "matches_without_ball_by_ball": matches - with_balls,
            })

        p_count = primary_audit["selected_counts"]
        e_count = expanded_audit["selected_counts"]
        summary: dict[str, Any] = {
            "analysis": "independent full-pipeline comparison of competition population definitions",
            "primary_scope_name": "IPL 2022 onward + T20 Internationals",
            "expanded_scope_name": "All supplied T20-format competitions + T20 Internationals",
            "source_counts": primary_audit["source_counts"],
            "primary_scope": {
                "competition_ids": int(p_count["competition_ids"]),
                "matches": int(p_count["matches"]),
                "matches_with_ball_by_ball": int(p_count["matches_with_ball_by_ball"]),
                "matches_without_ball_by_ball": int(p_count["matches_without_ball_by_ball"]),
                "ball_by_ball_rows": int(p_count["ball_by_ball_rows"]),
            },
            "expanded_scope": {
                "competition_ids": int(e_count["competition_ids"]),
                "matches": int(e_count["matches"]),
                "matches_with_ball_by_ball": int(e_count["matches_with_ball_by_ball"]),
                "matches_without_ball_by_ball": int(e_count["matches_without_ball_by_ball"]),
                "ball_by_ball_rows": int(e_count["ball_by_ball_rows"]),
            },
            "additional_competitions": additional_competitions,
            "additional_match_rows": int(e_count["matches"] - p_count["matches"]),
            "additional_delivery_rows": int(e_count["ball_by_ball_rows"] - p_count["ball_by_ball_rows"]),
            "batters": bat_summary,
            "bowlers": bowl_summary,
            "commands": {
                "primary": primary_command,
                "expanded": expanded_command,
                "invocation": "python run_scope_comparison.py",
            },
        }
        (OUTPUT_DIR / "competition_scope_comparison.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        pd.concat([bat_players, bowl_players], ignore_index=True).to_csv(
            OUTPUT_DIR / "competition_scope_comparison_players.csv", index=False
        )
        _copy_expanded_evidence(expanded_output)

        # Keep concise execution logs for auditability without retaining temporary trees.
        shutil.copy2(temp_root / "primary" / "pipeline.log", log_dir / "primary_pipeline.log")
        shutil.copy2(temp_root / "expanded" / "pipeline.log", log_dir / "expanded_pipeline.log")

    _write_markdown(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory containing the six supplied CSV inputs.")
    args = parser.parse_args()
    summary = run(Path(args.data_dir))
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
