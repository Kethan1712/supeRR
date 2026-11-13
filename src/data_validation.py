"""Schema and coverage checks for the supplied SupeRR Selector data."""

REQUIRED_COLUMNS = {
    "ball_by_ball": {
        "match_id", "innings", "overid", "over_ball_num", "innings_ball_num",
        "striker_id", "striker_name", "bowler_id", "bowler_name", "runs",
        "is_wicket", "dismissal_type", "dismissed_player_id", "extras_type",
        "is_four", "is_six",
    },
    "matches": {"match_id", "comp_id", "match_date", "stage", "win_team_id", "result"},
    "competitions": {"comp_id", "comp_name", "match_format", "season"},
    "playing_eleven": {"match_id", "team_id", "player_id", "is_played"},
    "teams": {"comp_id", "team_id", "team_name"},
    "competition_team_player_mapping": {
        "comp_id", "team_id", "player_id", "player_name"
    },
}

def validate_schemas(tables):
    """Return a list of schema problems; does not mutate input tables."""
    problems = []
    for table_name, required in REQUIRED_COLUMNS.items():
        if table_name not in tables:
            problems.append("Missing loaded table: {}".format(table_name))
            continue
        missing = sorted(required - set(tables[table_name].columns))
        if missing:
            problems.append(
                "{} is missing columns: {}".format(table_name, ", ".join(missing))
            )
    return problems

def coverage_summary(tables):
    """Return basic row counts and match-to-delivery coverage."""
    summary = {
        name: {"rows": int(len(df)), "columns": int(len(df.columns))}
        for name, df in tables.items()
    }
    if "matches" in tables and "ball_by_ball" in tables:
        match_ids = set(tables["matches"]["match_id"].dropna().unique())
        delivery_ids = set(tables["ball_by_ball"]["match_id"].dropna().unique())
        summary["match_coverage"] = {
            "matches_in_matches_file": len(match_ids),
            "matches_with_ball_by_ball": len(match_ids & delivery_ids),
            "matches_without_ball_by_ball": len(match_ids - delivery_ids),
            "delivery_match_ids_not_in_matches_file": len(delivery_ids - match_ids),
        }
    return summary
