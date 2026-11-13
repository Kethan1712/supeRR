import json
import pandas as pd

from src.player_evidence_profiles import build_player_evidence_profiles
from src.rr_role_depth import build_rr_role_depth_matrix
from src.boundary_flag_sensitivity import run_boundary_flag_sensitivity


def test_player_evidence_profiles_cover_all_ranked_players(tmp_path):
    # Use real project outputs; this verifies one evidence row per submitted rank.
    import shutil
    from pathlib import Path
    source = Path('outputs')
    for name in ['batting_rankings_top10.csv','bowling_rankings_top10.csv',
                 'batting_candidate_scores.csv','bowling_candidate_scores.csv']:
        shutil.copy(source/name, tmp_path/name)
    bat, bowl = build_player_evidence_profiles(tmp_path)
    assert len(bat) == 10 and len(bowl) == 10
    assert bat['player_id'].is_unique and bowl['player_id'].is_unique
    assert bat['final_index'].is_monotonic_decreasing
    assert bowl['final_index'].is_monotonic_decreasing
    assert bat['recorded_runs_raw_numerator'].notna().all()
    assert bowl['bowler_credited_wickets_raw_numerator'].notna().all()


def test_rr_role_depth_matrix_has_required_depth_columns(tmp_path):
    matrix = build_rr_role_depth_matrix(tmp_path)
    required = {'role','first_choice_2026','backup_2026','injury_cover_2026',
                'successor_watch','evidence','2027_action'}
    assert required.issubset(matrix.columns)
    assert len(matrix) == 7
    death = matrix.loc[matrix['role'].eq('Death-overs pace')].iloc[0]
    assert 'Jofra Archer' in death['first_choice_2026']
    assert 'Brijesh Sharma' in death['first_choice_2026']


def test_boundary_flag_deletion_sensitivity_does_not_change_top10_membership_or_order():
    from src.data_loader import load_dataset
    from pathlib import Path
    tables = load_dataset('data')
    bat = pd.read_csv('outputs/batting_rankings_top10.csv')
    bowl = pd.read_csv('outputs/bowling_rankings_top10.csv')
    result = run_boundary_flag_sensitivity(tables, bat, bowl)
    assert result['suspect_records'] == 23
    assert result['batters']['top10_overlap'] == 10
    assert result['bowlers']['top10_overlap'] == 10
    assert result['batters']['unchanged_rank_order'] is True
    assert result['bowlers']['unchanged_rank_order'] is True
    assert result['primary_rankings_overwritten'] is False


def test_match_spotlights_include_top_ranked_players():
    from src.data_loader import load_dataset
    from src.match_spotlights import build_match_spotlights
    bat, bowl = build_match_spotlights(load_dataset('data'), 'outputs')
    assert len(bat) == 10 and len(bowl) == 10
    assert 'Najibullah Zadran' in set(bat.player_name)
    assert 'Rinku Singh' in set(bat.player_name)
    assert 'Hasan Mahmud' in set(bowl.player_name)
    assert 'Rashid Khan' in set(bowl.player_name)
    assert bat['pressure_balls'].gt(0).all()
    assert bowl['death_candidate_legal_balls'].gt(0).all()
