"""Role-fit review for the 20 model-ranked players against RR's 2026 squad profile.

This is an editorial scouting aid, not a prediction of player release, auction
registration, asking price, fitness or availability. Franchise labels describe
published 2026 squads, updated for confirmed 2027 trades known by 2026-11-12.
"""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd

AS_OF = "2026-11-12"
SQUAD_SOURCE = "https://www.bbc.co.uk/sport/cricket/articles/cp891x46p65o"
PANT_TRADE_SOURCE = "https://www.iplt20.com/news/article/rishabh-pant-and-kuldeep-yadav-complete-high-profile-trade-between-dc-and-lsg"

# Roles are broad cricketing profiles, not claims about a fixed batting position.
FIT = {
    "Najibullah Zadran": ("Overseas", "Middle-order batter / finisher", "Not listed in reviewed 2026 IPL squad list", "Conditional", "A left-handed finishing option only if RR lose an established finisher; overseas-slot cost and existing Hetmyer/Ferreira/Shanaka cover make this a watchlist name, not a current need."),
    "Sikandar Raza": ("Overseas", "Batting all-rounder", "Not listed in reviewed 2026 IPL squad list", "Conditional", "Offers batting plus spin flexibility, but RR already used Parag, Jadeja and Shanaka as all-round options; consider only if that balance changes."),
    "Naman Dhir": ("Indian", "Middle-order batter / utility option", "Mumbai Indians (2026)", "Good role fit if released", "Could add Indian middle-order depth and reduce overseas-slot pressure; only pursue after checking MI's final release list and RR's retained batting group."),
    "Rinku Singh": ("Indian", "Finisher", "Kolkata Knight Riders (2026)", "Strong role fit if released", "A high-value Indian finishing profile, but the 2026 squad listing places him at KKR; no assumption of availability or affordable release is justified."),
    "Tristan Stubbs": ("Overseas", "Middle-order batter / wicketkeeper", "Delhi Capitals (2026)", "Conditional / role overlap", "High-quality power option, but overlaps RR's overseas middle-order and wicketkeeping cover; pursue only if multiple current options depart."),
    "Nurul Hasan": ("Overseas", "Wicketkeeper-batter", "Not listed in reviewed 2026 IPL squad list", "Low priority", "RR already has Jurel and other wicketkeeping cover in the 2026 group; another overseas keeper is not a first-order gap."),
    "Rishabh Pant": ("Indian", "Wicketkeeper-batter / top-middle order", "Delhi Capitals (2027 trade confirmed)", "Not a practical target", "A confirmed 2027 trade returned him to DC; RR also has Dhruv Jurel as a major wicketkeeping option. Do not treat him as an auction target."),
    "Ramandeep Singh": ("Indian", "Batting all-rounder / lower-order option", "Kolkata Knight Riders (2026)", "Good role fit if released", "Could add Indian lower-order flexibility; the need depends on RR's retained all-rounders and actual release status."),
    "Babar Azam": ("Overseas", "Top-order batter", "Not listed in reviewed 2026 IPL squad list", "Do not shortlist as an auction target", "The model ranks T20I pressure evidence; it does not establish IPL registration or auction eligibility. RR's 2026 top order is already well supplied."),
    "Glenn Phillips": ("Overseas", "Batting all-rounder / wicketkeeper option", "Gujarat Titans (2026)", "Conditional / role overlap", "Versatility is attractive, but RR's overseas batting and wicketkeeping roles were already covered in 2026; no availability is established."),
    "Sunil Narine": ("Overseas", "Spin all-rounder", "Kolkata Knight Riders (2026)", "Low practical fit", "Elite model result, but RR already had Jadeja and Bishnoi for spin plus several all-rounders; his 2026 franchise status is KKR."),
    "Hasan Mahmud": ("Overseas", "Fast bowler", "Not listed in reviewed 2026 IPL squad list", "Conditional pace option", "Could be assessed if RR lose overseas pace depth; require proof of 2027 registration, availability, role suitability and medical status before bidding."),
    "Rashid Khan": ("Overseas", "Leg-spin all-rounder", "Gujarat Titans (2026)", "Low practical fit", "A strong statistical performer, but RR used Bishnoi and Jadeja in spin roles; overseas-slot and release/price uncertainty are substantial."),
    "Akeal Hosein": ("Overseas", "Left-arm orthodox spinner", "Chennai Super Kings (2026)", "Low / role overlap", "Adds spin variety, but RR's 2026 middle-over plan already included Jadeja and Bishnoi; only relevant if that combination changes."),
    "Dasun Shanaka": ("Overseas", "Batting all-rounder / seam option", "Rajasthan Royals (2026)", "Retention / role-use decision", "Already part of RR's 2026 group and appears in the model's bowler top 10; assess retention, workload and role definition rather than treating him as an external buy."),
    "Riley Meredith": ("Overseas", "Fast bowler", "Not listed in reviewed 2026 IPL squad list", "Conditional pace option", "Could be examined for pace depth if an actual vacancy emerges; verify current fitness, 2027 registration and death-phase role before considering."),
    "Adam Zampa": ("Overseas", "Leg-spinner", "Not listed in reviewed 2026 IPL squad list", "Low / conditional", "A wicket-taking spin option, but the 2026 RR deployment already used Bishnoi and Jadeja; only consider if spin depth changes materially."),
    "Nandre Burger": ("Overseas", "Left-arm fast bowler", "Rajasthan Royals (2026)", "Retention / fitness decision", "Already in the 2026 RR squad and provides left-arm pace; evaluate availability, fitness and workload before considering a replacement."),
    "Ben Dwarshuis": ("Overseas", "Left-arm fast bowler / lower-order batting", "Punjab Kings (2026)", "Conditional pace depth", "Could add a left-arm pace variation if RR lose an overseas seamer; only pursue if released and an overseas slot remains."),
    "Rahul Chahar": ("Indian", "Leg-spinner", "Chennai Super Kings (2026)", "Conditional / role overlap", "An Indian spin option, but Bishnoi and Jadeja were already established in RR's 2026 middle-over deployment; assess only if there is a genuine vacancy."),
}


def build_ranked_player_fit(output_dir: str | Path = "outputs") -> tuple[pd.DataFrame, dict]:
    out = Path(output_dir)
    batting = pd.read_csv(out / "batting_rankings_top10.csv")
    bowling = pd.read_csv(out / "bowling_rankings_top10.csv")
    batting["role"] = "Batter"
    bowling["role"] = "Bowler"
    ranked = pd.concat([batting, bowling], ignore_index=True)
    missing = sorted(set(ranked["player_name"]) - set(FIT))
    extra = sorted(set(FIT) - set(ranked["player_name"]))
    if missing or extra or len(ranked) != 20 or ranked["player_name"].duplicated().any():
        raise ValueError(f"Ranked-player fit map mismatch; missing={missing}; extra={extra}; rows={len(ranked)}")
    fields = ["nationality_group", "role_profile", "2026_team_status", "rr_role_fit", "fit_rationale"]
    for field, index in zip(fields, range(5)):
        ranked[field] = ranked["player_name"].map(lambda name: FIT[name][index])
    ranked["status_note"] = "2026 squad status is not 2027 retention or auction availability."
    ranked = ranked.sort_values(["role", "rank"], key=lambda s: s.map({"Batter": 0, "Bowler": 1}) if s.name == "role" else s)
    ranked.to_csv(out / "rr_2027_ranked_player_fit.csv", index=False)
    audit = {
        "as_of": AS_OF,
        "players_reviewed": int(len(ranked)),
        "batters_reviewed": int((ranked["role"] == "Batter").sum()),
        "bowlers_reviewed": int((ranked["role"] == "Bowler").sum()),
        "availability_status": "Not determined; final retention/release and auction register were not yet available as of the report cut-off.",
        "2026_squad_source": SQUAD_SOURCE,
        "confirmed_pant_trade_source": PANT_TRADE_SOURCE,
        "important_limit": "Fit categories are qualitative role assessments, not model scores, probabilities, release predictions or bid recommendations.",
    }
    (out / "rr_2027_ranked_player_fit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    return ranked, audit
