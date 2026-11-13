"""Preflight check: confirm the dashboard can read the existing project outputs."""
from __future__ import annotations

import sys
from pathlib import Path

from data_layer import DashboardDataError, load_dashboard_data, resolve_project_root


def main() -> int:
    root = resolve_project_root()
    if root is None:
        print("ERROR: project root not found. frontend/ must be beside outputs/.")
        print("Expected: project_root/frontend/ and project_root/outputs/")
        return 2
    try:
        d = load_dashboard_data(root)
    except DashboardDataError as exc:
        print(f"ERROR: {exc}")
        return 2

    batters = d["batting_rankings"].sort_values("rank")
    bowlers = d["bowling_rankings"].sort_values("rank")
    pressure = d["pressure_audit"]
    scope = d["scope_comparison"]
    print(f"Project root: {root}")
    print(f"Primary Top 10: {len(batters)} batters / {len(bowlers)} bowlers")
    print(f"Top batter: {batters.iloc[0]['player_name']} ({float(batters.iloc[0]['reliability_score']):.2f})")
    print(f"Top bowler: {bowlers.iloc[0]['player_name']} ({float(bowlers.iloc[0]['reliability_score']):.2f})")
    print(f"Unique combined-pressure records: {pressure.get('combined_pressure_records_without_double_counting', 'not reported')}")
    print(f"Scope overlaps: batters {scope.get('batters', {}).get('top10_overlap_out_of_10', 'not reported')}; bowlers {scope.get('bowlers', {}).get('top10_overlap_out_of_10', 'not reported')}")
    print("Dashboard data preflight: PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
