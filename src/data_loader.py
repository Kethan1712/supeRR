"""Load the supplied SupeRR Selector CSV files."""

from pathlib import Path
import pandas as pd

REQUIRED_FILES = {
    "ball_by_ball": "ball_by_ball.csv",
    "matches": "matches.csv",
    "competitions": "competitions.csv",
    "playing_eleven": "playing_eleven.csv",
    "teams": "teams.csv",
    "competition_team_player_mapping": "competition_team_player_mapping.csv",
}

def load_dataset(data_dir="data"):
    """Load required CSVs from data_dir and return a dictionary of DataFrames.

    The source CSVs are expected directly inside data_dir. No rows are
    silently dropped or modified by this function.
    """
    data_path = Path(data_dir)
    missing = [filename for filename in REQUIRED_FILES.values()
               if not (data_path / filename).is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing required CSV file(s) in '{}': {}. "
            "Extract the supplied data pack into the data/ folder.".format(
                data_path, ", ".join(missing)
            )
        )

    return {
        key: pd.read_csv(data_path / filename, low_memory=False)
        for key, filename in REQUIRED_FILES.items()
    }
