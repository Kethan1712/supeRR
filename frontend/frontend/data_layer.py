"""Read-only data access for the SupeRR Selector dashboard.

The dashboard deliberately reads the project's existing generated outputs. It does
not recompute rankings, infer unavailable statistics, or mutate source files.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd


class DashboardDataError(RuntimeError):
    """Raised when required project outputs are missing or malformed."""


def resolve_project_root() -> Path | None:
    """Find the project directory containing outputs/.

    Supports the normal layout:
        project_root/frontend/app.py
        project_root/outputs/...
    and an explicit SUPERR_PROJECT_ROOT environment variable.
    """
    env_root = os.getenv("SUPERR_PROJECT_ROOT")
    candidates: list[Path] = []
    if env_root:
        candidates.append(Path(env_root).expanduser().resolve())

    here = Path(__file__).resolve()
    candidates.extend([here.parent.parent, Path.cwd(), *Path.cwd().parents])

    visited: set[Path] = set()
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate in visited:
            continue
        visited.add(candidate)
        if (candidate / "outputs").is_dir():
            return candidate
    return None


def read_csv(root: Path, relative_path: str, required: bool = True) -> pd.DataFrame:
    path = root / relative_path
    if not path.is_file():
        if required:
            raise DashboardDataError(
                f"Required dashboard file is missing: {relative_path}. "
                "Copy the frontend folder into the SupeRR project root and check that outputs/ is present."
            )
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:  # pragma: no cover - defensive error message
        raise DashboardDataError(f"Could not read {relative_path}: {exc}") from exc


def read_json(root: Path, relative_path: str, required: bool = True) -> dict[str, Any]:
    path = root / relative_path
    if not path.is_file():
        if required:
            raise DashboardDataError(f"Required dashboard file is missing: {relative_path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise DashboardDataError(f"Expected a JSON object in {relative_path}")
        return value
    except DashboardDataError:
        raise
    except Exception as exc:  # pragma: no cover - defensive error message
        raise DashboardDataError(f"Could not read {relative_path}: {exc}") from exc


def require_columns(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [col for col in columns if col not in df.columns]
    if missing:
        raise DashboardDataError(
            f"{label} is missing expected columns: {', '.join(missing)}. "
            "The dashboard may be paired with a different project release."
        )


def load_dashboard_data(root: Path) -> dict[str, Any]:
    """Load and validate all dashboard inputs from the selected project root."""
    d: dict[str, Any] = {}
    d["batting_rankings"] = read_csv(root, "outputs/batting_rankings_top10.csv")
    d["bowling_rankings"] = read_csv(root, "outputs/bowling_rankings_top10.csv")
    d["batter_evidence"] = read_csv(root, "outputs/top10_batter_evidence.csv")
    d["bowler_evidence"] = read_csv(root, "outputs/top10_bowler_evidence.csv")
    d["batter_spotlights"] = read_csv(root, "outputs/top10_batter_match_spotlights.csv")
    d["bowler_spotlights"] = read_csv(root, "outputs/top10_bowler_match_spotlights.csv")
    d["role_depth"] = read_csv(root, "outputs/rr_2027_role_depth_matrix.csv")
    d["rr_player_fit"] = read_csv(root, "outputs/rr_2027_ranked_player_fit.csv")
    d["rr_squad_audit"] = read_csv(root, "outputs/rr_2026_squad_role_audit.csv", required=False)
    d["scope_players"] = read_csv(root, "outputs/scope_comparison/competition_scope_comparison_players.csv")
    d["expanded_batting_rankings"] = read_csv(root, "outputs/scope_comparison/expanded_batting_rankings_top10.csv")
    d["expanded_bowling_rankings"] = read_csv(root, "outputs/scope_comparison/expanded_bowling_rankings_top10.csv")
    d["metric_sensitivity"] = read_csv(root, "outputs/metric_weight_sensitivity.csv", required=False)
    d["pressure_stability"] = read_csv(root, "outputs/pressure_threshold_ranking_stability.csv", required=False)

    d["pressure_audit"] = read_json(root, "outputs/pressure_detection_audit.json")
    d["competition_audit"] = read_json(root, "outputs/competition_scope_audit.json")
    d["scope_comparison"] = read_json(root, "outputs/scope_comparison/competition_scope_comparison.json")
    d["validation"] = read_json(root, "outputs/final_validation_summary.json")
    d["release_checks"] = read_json(root, "outputs/final_release_checks.json")
    d["batting_audit"] = read_json(root, "outputs/batting_metrics_audit.json")
    d["bowling_audit"] = read_json(root, "outputs/bowling_metrics_audit.json")
    d["boundary_sensitivity"] = read_json(root, "outputs/boundary_flag_sensitivity.json")
    d["match_context_audit"] = read_json(root, "outputs/match_context_audit.json")
    d["test_results"] = (root / "outputs/test_results.txt").read_text(encoding="utf-8", errors="replace") if (root / "outputs/test_results.txt").is_file() else "Test-results text file not found."
    d["readme"] = (root / "README.md").read_text(encoding="utf-8", errors="replace") if (root / "README.md").is_file() else ""
    d["root"] = root

    require_columns(d["batting_rankings"], ["rank", "player_id", "player_name", "reliability_score"], "Primary batting rankings")
    require_columns(d["bowling_rankings"], ["rank", "player_id", "player_name", "reliability_score"], "Primary bowling rankings")
    require_columns(d["batter_evidence"], ["player_id", "player_name", "final_index", "pressure_opportunities", "pressure_matches"], "Batter evidence")
    require_columns(d["bowler_evidence"], ["player_id", "player_name", "final_index", "pressure_opportunities", "pressure_matches"], "Bowler evidence")
    require_columns(d["batter_spotlights"], ["player_id", "player_name", "match_date", "competition", "opponent"], "Batter match spotlights")
    require_columns(d["bowler_spotlights"], ["player_id", "player_name", "match_date", "competition", "opponent"], "Bowler match spotlights")
    require_columns(d["role_depth"], ["role", "first_choice_2026", "backup_2026", "injury_cover_2026", "successor_watch", "evidence", "2027_action"], "RR role-depth matrix")
    require_columns(d["rr_player_fit"], ["player_id", "player_name", "role", "nationality_group", "role_profile", "2026_team_status", "rr_role_fit", "fit_rationale", "status_note"], "RR player fit")
    require_columns(d["scope_players"], ["role", "player_name", "status", "primary_rank", "expanded_rank", "primary_score", "expanded_score"], "Scope comparison")
    require_columns(d["expanded_batting_rankings"], ["rank", "player_name", "reliability_score"], "Expanded batting rankings")
    require_columns(d["expanded_bowling_rankings"], ["rank", "player_name", "reliability_score"], "Expanded bowling rankings")

    # Make numeric fields numeric even if a CSV editor stored them as text.
    numeric_map = {
        "batting_rankings": ["rank", "reliability_score"],
        "bowling_rankings": ["rank", "reliability_score"],
        "batter_evidence": ["final_index", "pressure_opportunities", "pressure_matches", "ordinary_opportunities", "ordinary_matches"],
        "bowler_evidence": ["final_index", "pressure_opportunities", "pressure_matches", "ordinary_opportunities", "ordinary_matches"],
        "scope_players": ["primary_rank", "expanded_rank", "primary_score", "expanded_score", "rank_change_expanded_minus_primary", "score_change_expanded_minus_primary"],
    }
    for key, cols in numeric_map.items():
        for col in cols:
            if col in d[key].columns:
                d[key][col] = pd.to_numeric(d[key][col], errors="coerce")

    for key in ["batter_spotlights", "bowler_spotlights"]:
        d[key]["match_date"] = pd.to_datetime(d[key]["match_date"], errors="coerce")

    return d


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
