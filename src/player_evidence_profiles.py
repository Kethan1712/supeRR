"""Create compact, traceable performance evidence for every selected player."""
from __future__ import annotations
import pandas as pd
from pathlib import Path

BAT_METRIC_LABELS = {
    "recorded_runs_per_100_balls": "recorded_runs",
    "dismissals_per_100_balls": "dismissals",
    "boundaries_per_100_balls": "flagged_boundaries",
}
BOWL_METRIC_LABELS = {
    "bowler_wickets_per_100_candidate_legal_balls": "bowler_credited_wickets",
    "flagged_boundaries_per_100_candidate_legal_balls": "flagged_boundaries_conceded",
}


def _evidence_band(opps: float, matches: int, role: str) -> str:
    if role == "Batter":
        if opps >= 250 and matches >= 20: return "Higher volume"
        if opps >= 150 and matches >= 15: return "Moderate volume"
        return "Qualified; smaller sample"
    if opps >= 200 and matches >= 20: return "Higher volume"
    if opps >= 100 and matches >= 12: return "Moderate volume"
    return "Qualified; smaller sample"


def build_player_evidence_profiles(output_dir="outputs") -> tuple[pd.DataFrame, pd.DataFrame]:
    out = Path(output_dir)
    bat_rank = pd.read_csv(out / "batting_rankings_top10.csv")
    bowl_rank = pd.read_csv(out / "bowling_rankings_top10.csv")
    bat_detail = pd.read_csv(out / "batting_candidate_scores.csv")
    bowl_detail = pd.read_csv(out / "bowling_candidate_scores.csv")

    def role_profiles(rankings, detail, category, metric_labels, role):
        rows=[]
        for _, p in rankings.iterrows():
            d=detail[(detail.player_id==p.player_id)&(detail.metric_category==category)].copy()
            metrics={}
            for _, m in d.iterrows():
                label=metric_labels[m.metric]
                n=float(m.matched_opportunities)
                raw=float(m.observed_numerator_matched)/n*100 if n else float("nan")
                metrics[f"{label}_raw_numerator"] = float(m.observed_numerator_matched)
                metrics[f"{label}_opportunities"] = n
                metrics[f"{label}_raw_rate_per_100"] = raw
                metrics[f"{label}_peer_rate_per_100"] = float(m.peer_rate_opportunity_weighted)
                metrics[f"{label}_adjusted_relative_vs_peer_pct"] = float(m.sample_adjusted_vs_peer_pct_prior_60)
                metrics[f"{label}_pressure_uplift_pct_points"] = float(m.pressure_uplift_vs_ordinary_pct_points)
                metrics[f"{label}_performance_percentile"] = float(m.performance_percentile)
                metrics[f"{label}_consistency_percentile"] = float(m.consistency_percentile)
                metrics[f"{label}_metric_weight"] = float(m.metric_weight)
            opps=float(p.pressure_opportunities); matches=int(p.pressure_matches)
            row={
                "rank":int(p["rank"]),"player_id":int(p.player_id),"player_name":p.player_name,
                "role":role,"final_index":float(p.reliability_score),
                "performance_component":float(p.performance_component),
                "consistency_component":float(p.consistency_component),
                "pressure_opportunities":opps,"pressure_matches":matches,
                "ordinary_opportunities":float(p.ordinary_opportunities),"ordinary_matches":int(p.ordinary_matches),
                "positive_match_share_pct":float(p.positive_match_share_pct),
                "mean_pressure_adjusted_vs_peer_pct":float(p.mean_pressure_adjusted_vs_peer_pct),
                "mean_uplift_vs_ordinary_pct_points":float(p.mean_uplift_vs_ordinary_pct_points),
                "evidence_volume_label":_evidence_band(opps,matches,role),
            }
            row.update(metrics)
            rows.append(row)
        return pd.DataFrame(rows)

    bat=role_profiles(bat_rank,bat_detail,"combined_pressure",BAT_METRIC_LABELS,"Batter")
    bowl=role_profiles(bowl_rank,bowl_detail,"death_over_context",BOWL_METRIC_LABELS,"Bowler")
    bat.to_csv(out/"top10_batter_evidence.csv",index=False)
    bowl.to_csv(out/"top10_bowler_evidence.csv",index=False)
    return bat,bowl
