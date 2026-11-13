"""Entry point for the SupeRR Selector validation pipeline."""

import argparse
import json
from pathlib import Path

from src.data_loader import load_dataset
from src.dataset_scope import apply_competition_scope
from src.data_validation import coverage_summary, validate_schemas
from src.match_context import build_match_context, context_audit
from src.pressure_detection import (
    add_pressure_flags,
    pressure_audit,
    pressure_threshold_sensitivity,
)
from src.batting_metrics import calculate_batting_metrics, save_batting_metrics
from src.bowling_metrics import calculate_bowling_metrics, save_bowling_metrics
from src.player_baselines import calculate_player_baselines, save_player_baselines
from src.baseline_charts import create_baseline_charts
from src.player_reliability import calculate_player_reliability, save_player_reliability
from src.player_ratings import (
    calculate_rankings, calculate_stability, calculate_pressure_cutoff_stability,
    calculate_metric_weight_sensitivity, save_rankings
)
from src.visualizations import create_ranking_visuals
from src.rr_squad_audit import save_rr_2026_role_audit
from src.rr_ranked_player_fit import build_ranked_player_fit


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--audit-context",
        action="store_true",
        help="Build delivery context and report sequence/wicket-state checks.",
    )
    parser.add_argument(
        "--audit-pressure",
        action="store_true",
        help="Build pressure labels and report early-collapse/death-phase coverage.",
    )
    parser.add_argument(
        "--audit-batting",
        action="store_true",
        help="Calculate descriptive batter metrics by pressure category and baseline.",
    )
    parser.add_argument(
        "--audit-bowling",
        action="store_true",
        help="Calculate descriptive bowler metrics by pressure context and baseline.",
    )
    parser.add_argument(
        "--audit-baselines",
        action="store_true",
        help="Calculate context-matched peer (league) and individual player baseline comparisons.",
    )
    parser.add_argument(
        "--audit-reliability",
        action="store_true",
        help="Calculate sample-size-adjusted performance and match-to-match consistency evidence.",
    )
    parser.add_argument(
        "--audit-rankings",
        action="store_true",
        help="Run baselines, reliability and the primary top-10 rankings.",
    )
    parser.add_argument(
        "--audit-pressure-ranking-stability",
        action="store_true",
        help="Rebuild baselines and rankings under alternate 8/12-over collapse thresholds (slower).",
    )
    parser.add_argument(
        "--scope", choices=["ipl_t20i", "all_supplied_t20_t20i"], default="ipl_t20i",
        help="Primary scope is IPL 2022+ and T20I; expanded scope is for sensitivity only.",
    )
    parser.add_argument(
        "--audit-rr-squad", action="store_true",
        help="Create a retrospective Rajasthan Royals 2026 role/phase-usage audit.",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing the six supplied CSV files (default: data).",
    )
    args = parser.parse_args()

    source_tables = load_dataset(args.data_dir)
    tables, scope_audit = apply_competition_scope(source_tables, args.scope)
    problems = validate_schemas(tables)
    if problems:
        raise SystemExit("Data validation failed:\n- " + "\n- ".join(problems))

    print("Schema validation: PASS")
    print("Competition scope audit:")
    print(json.dumps(scope_audit, indent=2, default=str))
    Path("outputs").mkdir(exist_ok=True)
    (Path("outputs") / "competition_scope_audit.json").write_text(
        json.dumps(scope_audit, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(coverage_summary(tables), indent=2, default=str))

    if (args.audit_context or args.audit_pressure or args.audit_batting
            or args.audit_bowling or args.audit_baselines or args.audit_reliability
            or args.audit_rankings or args.audit_pressure_ranking_stability or args.audit_rr_squad):
        context = build_match_context(
            tables["ball_by_ball"], tables["matches"], tables["competitions"]
        )
        Path("outputs").mkdir(exist_ok=True)

        if args.audit_context:
            audit = context_audit(context)
            audit_path = Path("outputs") / "match_context_audit.json"
            audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
            print("\nDelivery context audit:")
            print(json.dumps(audit, indent=2))
            print(f"\nAudit saved to: {audit_path}")

        if (args.audit_pressure or args.audit_batting or args.audit_bowling
                or args.audit_baselines or args.audit_reliability or args.audit_rankings
                or args.audit_pressure_ranking_stability):
            pressured = add_pressure_flags(context)

        if args.audit_pressure:
            audit = pressure_audit(pressured)
            audit_path = Path("outputs") / "pressure_detection_audit.json"
            audit_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
            print("\nPressure detection audit:")
            print(json.dumps(audit, indent=2))
            print(f"\nAudit saved to: {audit_path}")

            sensitivity = pressure_threshold_sensitivity(context)
            sensitivity_path = Path("outputs") / "pressure_threshold_sensitivity.json"
            sensitivity_path.write_text(
                json.dumps(sensitivity, indent=2), encoding="utf-8"
            )
            print("\nEarly-collapse threshold sensitivity (8/10/12 overs on a 20-over allocation):")
            print(json.dumps(sensitivity, indent=2))
            print(f"\nSensitivity audit saved to: {sensitivity_path}")

        if args.audit_batting:
            player_metrics, match_metrics, audit = calculate_batting_metrics(pressured)
            paths = save_batting_metrics(player_metrics, match_metrics, audit)
            print("\nBatting metrics audit:")
            print(json.dumps(audit, indent=2))
            print("\nSaved batting metric files:")
            print(json.dumps(paths, indent=2))

        if args.audit_bowling:
            player_metrics, match_metrics, audit = calculate_bowling_metrics(pressured)
            paths = save_bowling_metrics(player_metrics, match_metrics, audit)
            print("\nBowling metrics audit:")
            print(json.dumps(audit, indent=2))
            print("\nSaved bowling metric files:")
            print(json.dumps(paths, indent=2))

        if (args.audit_baselines or args.audit_reliability or args.audit_rankings
                or args.audit_pressure_ranking_stability):
            (
                batting_context,
                batting_summary,
                bowling_context,
                bowling_summary,
                peer_benchmarks,
                baseline_audit,
            ) = calculate_player_baselines(pressured)

            if args.audit_baselines:
                charts = create_baseline_charts(batting_summary, bowling_summary)
                baseline_audit["baseline_charts"] = charts
                paths = save_player_baselines(
                    batting_context,
                    batting_summary,
                    bowling_context,
                    bowling_summary,
                    peer_benchmarks,
                    baseline_audit,
                )
                print("\nPlayer baseline audit:")
                print(json.dumps(baseline_audit, indent=2))
                print("\nSaved baseline comparison files:")
                print(json.dumps(paths, indent=2))

            if args.audit_reliability or args.audit_rankings or args.audit_pressure_ranking_stability:
                (
                    batting_reliability,
                    batting_match_consistency,
                    bowling_reliability,
                    bowling_match_consistency,
                    reliability_audit,
                ) = calculate_player_reliability(
                    pressured, batting_context, bowling_context
                )
                reliability_paths = save_player_reliability(
                    batting_reliability,
                    batting_match_consistency,
                    bowling_reliability,
                    bowling_match_consistency,
                    reliability_audit,
                )
                print("\nPlayer reliability audit:")
                print(json.dumps(reliability_audit, indent=2))
                print("\nSaved reliability evidence files:")
                print(json.dumps(reliability_paths, indent=2))

                if args.audit_rankings or args.audit_pressure_ranking_stability:
                    bat_rank, bowl_rank, bat_features, bowl_features, rank_audit = calculate_rankings(
                        batting_reliability, bowling_reliability
                    )
                    sensitivity, sensitivity_audit = calculate_stability(
                        batting_reliability, bowling_reliability
                    )
                    rank_paths = save_rankings(
                        bat_rank, bowl_rank, bat_features, bowl_features,
                        sensitivity, rank_audit, sensitivity_audit
                    )
                    print("\nTOP 10 BATTERS:")
                    print(bat_rank.head(10).to_string(index=False))
                    print("\nTOP 10 BOWLERS:")
                    print(bowl_rank.head(10).to_string(index=False))
                    print("\nRanking files:")
                    print(json.dumps(rank_paths, indent=2))

                    metric_sensitivity, metric_sensitivity_audit = calculate_metric_weight_sensitivity(
                        batting_reliability, bowling_reliability
                    )
                    metric_sensitivity.to_csv(
                        Path("outputs") / "metric_weight_sensitivity.csv", index=False
                    )
                    (Path("outputs") / "metric_weight_sensitivity.json").write_text(
                        json.dumps(metric_sensitivity_audit, indent=2, default=str), encoding="utf-8"
                    )
                    print("\nMetric-weight sensitivity:")
                    print(metric_sensitivity.to_string(index=False))

                    if args.audit_pressure_ranking_stability:
                        pressure_stability, pressure_stability_audit = calculate_pressure_cutoff_stability(
                            context, bat_rank, bowl_rank
                        )
                        pressure_stability.to_csv(
                            Path("outputs") / "pressure_threshold_ranking_stability.csv", index=False
                        )
                        (Path("outputs") / "pressure_threshold_ranking_stability.json").write_text(
                            json.dumps(pressure_stability_audit, indent=2), encoding="utf-8"
                        )
                        print("\nPressure cutoff ranking stability:")
                        print(pressure_stability.to_string(index=False))

                    chart_paths = create_ranking_visuals("outputs")
                    print("\nRanking charts:")
                    print(json.dumps(chart_paths, indent=2))

        if args.audit_rr_squad:
            rr_paths = save_rr_2026_role_audit(tables, "outputs")
            print("\nRajasthan Royals 2026 squad role audit:")
            print(json.dumps(rr_paths, indent=2))
            fit_table, fit_audit = build_ranked_player_fit("outputs")
            print("\nRR role-fit review for all 20 ranked players:")
            print(json.dumps(fit_audit, indent=2))
            print(fit_table[["role", "rank", "player_name", "rr_role_fit"]].to_string(index=False))


if __name__ == "__main__":
    main()
