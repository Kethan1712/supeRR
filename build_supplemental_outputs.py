"""Build evidence profiles, match spotlights, RR role depth and flag sensitivity."""
from pathlib import Path
import json
import pandas as pd
from src.data_loader import load_dataset
from src.player_evidence_profiles import build_player_evidence_profiles
from src.rr_role_depth import build_rr_role_depth_matrix
from src.boundary_flag_sensitivity import save_boundary_flag_sensitivity
from src.match_spotlights import build_match_spotlights

OUT=Path("outputs")

def main():
    tables=load_dataset("data")
    bat_profiles,bowl_profiles=build_player_evidence_profiles(OUT)
    role_depth=build_rr_role_depth_matrix(OUT)
    bat_spotlights,bowl_spotlights=build_match_spotlights(tables,OUT)
    bat=pd.read_csv(OUT/"batting_rankings_top10.csv")
    bowl=pd.read_csv(OUT/"bowling_rankings_top10.csv")
    boundary=save_boundary_flag_sensitivity(tables,bat,bowl,OUT/"boundary_flag_sensitivity.json")
    summary={
        "batter_profiles":len(bat_profiles),"bowler_profiles":len(bowl_profiles),
        "rr_role_depth_rows":len(role_depth),
        "batter_match_spotlights":len(bat_spotlights),"bowler_match_spotlights":len(bowl_spotlights),
        "boundary_flag_suspect_records":boundary["suspect_records"],
        "boundary_deletion_sensitivity":{
            "batters_top10_overlap":boundary["batters"]["top10_overlap"],
            "bowlers_top10_overlap":boundary["bowlers"]["top10_overlap"],
            "batters_rank_order_unchanged":boundary["batters"]["unchanged_rank_order"],
            "bowlers_rank_order_unchanged":boundary["bowlers"]["unchanged_rank_order"],
        },
    }
    (OUT/"supplemental_validation_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
