import pandas as pd
import pytest

from src.rr_ranked_player_fit import FIT, build_ranked_player_fit


def test_fit_review_covers_exactly_twenty_unique_players(tmp_path):
    names_bat = [
        "Najibullah Zadran", "Sikandar Raza", "Naman Dhir", "Rinku Singh",
        "Tristan Stubbs", "Nurul Hasan", "Rishabh Pant", "Ramandeep Singh",
        "Babar Azam", "Glenn Phillips",
    ]
    names_bowl = [
        "Sunil Narine", "Hasan Mahmud", "Rashid Khan", "Akeal Hosein",
        "Dasun Shanaka", "Riley Meredith", "Adam Zampa", "Nandre Burger",
        "Ben Dwarshuis", "Rahul Chahar",
    ]
    pd.DataFrame({"rank": range(1, 11), "player_name": names_bat, "reliability_score": [90-i for i in range(10)]}).to_csv(tmp_path / "batting_rankings_top10.csv", index=False)
    pd.DataFrame({"rank": range(1, 11), "player_name": names_bowl, "reliability_score": [90-i for i in range(10)]}).to_csv(tmp_path / "bowling_rankings_top10.csv", index=False)
    result, audit = build_ranked_player_fit(tmp_path)
    assert len(result) == 20
    assert result["player_name"].nunique() == 20
    assert len(FIT) == 20
    assert audit["players_reviewed"] == 20
    assert "not determined" in audit["availability_status"].lower()


def test_fit_review_fails_if_ranked_list_changes(tmp_path):
    pd.DataFrame({"rank": [1], "player_name": ["Unexpected Player"], "reliability_score": [100]}).to_csv(tmp_path / "batting_rankings_top10.csv", index=False)
    pd.DataFrame({"rank": [], "player_name": [], "reliability_score": []}).to_csv(tmp_path / "bowling_rankings_top10.csv", index=False)
    with pytest.raises(ValueError):
        build_ranked_player_fit(tmp_path)
