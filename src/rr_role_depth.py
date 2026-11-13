"""Translate RR's observed IPL 2026 usage into a cautious role-depth matrix.

The labels are planning roles inferred from 2026 usage and squad membership,
not a forecast of the 2027 XI or injury status.
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path

ROLE_ROWS = [
    {"role":"Top-order / powerplay batting","first_choice_2026":"Vaibhav Sooryavanshi; Yashasvi Jaiswal","backup_2026":"Dhruv Jurel","injury_cover_2026":"Lhuan-dre Pretorius; Ravi Singh","successor_watch":"Aman Rao Perala","evidence":"Vaibhav 218 and Jaiswal 185 powerplay batting balls; both played 16 matches. Jurel played 16 matches but had more middle-order usage.","2027_action":"Reassess only after retentions; the 2026 data shows established opening volume, not a proven vacancy."},
    {"role":"Indian middle-order batting","first_choice_2026":"Dhruv Jurel; Riyan Parag","backup_2026":"Ravindra Jadeja","injury_cover_2026":"Shubham Dubey; Ravi Singh","successor_watch":"Aman Rao Perala","evidence":"Jurel 206 and Parag 144 middle-order batting balls; Jadeja 101. Dubey recorded 17 middle-order balls in 7 matches.","2027_action":"Naman Dhir is a conditional external fit if released; compare his role to retained Jurel/Parag/Jadeja before bidding."},
    {"role":"Finishing / lower-order batting","first_choice_2026":"Donovan Ferreira; Ravindra Jadeja","backup_2026":"Shubham Dubey; Shimron Hetmyer","injury_cover_2026":"Riyan Parag; Dasun Shanaka","successor_watch":"Shubham Dubey; Ravi Singh","evidence":"Ferreira had 83 and Jadeja 74 death-phase batting balls; Dubey 41, Hetmyer 26, Shanaka 17 and Parag 13. These are phase-use counts, not a formal batting-order classification.","2027_action":"Rinku Singh is an Indian finishing-profile fit if genuinely released; Ramandeep Singh offers lower-order all-round utility if released. Neither is assumed available."},
    {"role":"Wicketkeeper-batter","first_choice_2026":"Dhruv Jurel","backup_2026":"Donovan Ferreira","injury_cover_2026":"Lhuan-dre Pretorius; Ravi Singh","successor_watch":"Aman Rao Perala","evidence":"Jurel played 16 matches, Ferreira 15, Pretorius 2 and Ravi Singh 1 in the 2026 squad mapping. This is appearance evidence; actual keeper duties may vary by match.","2027_action":"Do not target another overseas keeper unless retentions create a clear vacancy."},
    {"role":"Death-overs pace","first_choice_2026":"Jofra Archer; Brijesh Sharma","backup_2026":"Sandeep Sharma; Nandre Burger; Tushar Deshpande","injury_cover_2026":"Adam Milne; Yudhvir Singh Charak","successor_watch":"Brijesh Sharma; Kuldeep Sen","evidence":"Death candidate-legal balls: Archer 108, Brijesh 96, Sandeep 52, Nandre 51, Tushar 48. Milne had 8; Yudhvir and Kuldeep Sen had no recorded 2026 appearances in the supplied audit.","2027_action":"The ranked bowling Top 10 contains no Indian specialist death pacer. Protect the 2026 domestic pace cover; add an Indian death specialist only if retentions/injury leave a verified gap."},
    {"role":"Powerplay pace","first_choice_2026":"Jofra Archer; Nandre Burger","backup_2026":"Brijesh Sharma; Sandeep Sharma; Tushar Deshpande","injury_cover_2026":"Adam Milne; Kwena Maphaka","successor_watch":"Kuldeep Sen; Yudhvir Singh Charak","evidence":"Powerplay candidate-legal balls: Archer 204, Nandre 156, Brijesh 73, Sandeep 48, Tushar 48. Milne 12; Maphaka, Kuldeep Sen and Yudhvir had no recorded appearances.","2027_action":"Assess pace balance after confirmed retentions and fitness checks; no external name is an auction target until registered."},
    {"role":"Middle-over spin","first_choice_2026":"Ravindra Jadeja; Yash Punja","backup_2026":"Ravi Bishnoi","injury_cover_2026":"Vignesh Puthur; Sushant Mishra","successor_watch":"Vignesh Puthur; Yash Punja","evidence":"Middle-over candidate-legal balls: Jadeja 198, Yash Punja 156, Bishnoi 120. Puthur had no recorded 2026 appearances; Sushant had 24.","2027_action":"Spin succession is a watch item, not an automatic acquisition gap; verify retention and development plans first."},
]


def build_rr_role_depth_matrix(output_dir="outputs") -> pd.DataFrame:
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    frame=pd.DataFrame(ROLE_ROWS)
    frame.to_csv(out/"rr_2027_role_depth_matrix.csv",index=False)
    return frame
