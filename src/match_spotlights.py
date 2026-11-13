"""Extract illustrative match-level pressure segments for selected players.

These spotlights are examples, not the inputs used to rank players. The final
index is calculated from the full eligible sample across all pressure matches.
"""
from __future__ import annotations
import pandas as pd
from pathlib import Path
from .dataset_scope import apply_competition_scope
from .match_context import build_match_context
from .pressure_detection import add_pressure_flags
from .bowling_metrics import BOWLER_CREDITED_DISMISSALS


def _bool(s): return s.astype('boolean').fillna(False).astype(bool)


def build_match_spotlights(source_tables, output_dir='outputs'):
    tables,_=apply_competition_scope(source_tables,'ipl_t20i')
    p=add_pressure_flags(build_match_context(tables['ball_by_ball'],tables['matches'],tables['competitions']))
    matches=tables['matches'][['match_id','match_date','home_team_id','away_team_id','home_team','away_team']]
    bat_top=pd.read_csv(Path(output_dir)/'batting_rankings_top10.csv')
    bowl_top=pd.read_csv(Path(output_dir)/'bowling_rankings_top10.csv')

    b=p.loc[_bool(p['is_pressure']) & p['striker_id'].isin(bat_top.player_id)].copy()
    b['wide']=b['extras_type'].astype('string').str.strip().str.casefold().eq('wide').fillna(False)
    b['balls_faced']=(~b['wide']).astype(int)
    b['recorded_runs']=pd.to_numeric(b['runs'],errors='coerce').fillna(0)
    b['fours']=_bool(b['is_four']).astype(int); b['sixes']=_bool(b['is_six']).astype(int)
    bg=b.groupby(['striker_id','striker_name','match_id','innings','batting_team_id','bowling_team_id','comp_name','season'],dropna=False).agg(
        pressure_balls=('balls_faced','sum'),pressure_recorded_runs=('recorded_runs','sum'),flagged_fours=('fours','sum'),flagged_sixes=('sixes','sum')
    ).reset_index()
    bg=bg.merge(matches,on='match_id',how='left',validate='many_to_one')
    bg['opponent']=bg.apply(lambda r:r['away_team'] if r['batting_team_id']==r['home_team_id'] else r['home_team'],axis=1)
    bg['pressure_segment_recorded_sr']=bg['pressure_recorded_runs'].div(bg['pressure_balls'].replace(0,pd.NA))*100
    bat_rows=[]
    for _,r in bat_top.iterrows():
        choices=bg.loc[bg.striker_id.eq(r.player_id)].sort_values(['pressure_recorded_runs','pressure_balls','match_date'],ascending=[False,False,True])
        if choices.empty: continue
        x=choices.iloc[0]
        bat_rows.append({'rank':int(r['rank']),'player_id':int(r.player_id),'player_name':r.player_name,'match_id':int(x.match_id),'match_date':x.match_date,'competition':x.comp_name,'season':x.season,'innings':int(x.innings),'opponent':x.opponent,'pressure_balls':int(x.pressure_balls),'pressure_recorded_runs':int(x.pressure_recorded_runs),'flagged_fours':int(x.flagged_fours),'flagged_sixes':int(x.flagged_sixes),'pressure_segment_recorded_sr':float(x.pressure_segment_recorded_sr) if pd.notna(x.pressure_segment_recorded_sr) else None,'interpretation':'Illustrative pressure-labelled segment; not the sole basis of the ranking.'})

    q=p.loc[_bool(p['is_death_over_pressure']) & p['bowler_id'].isin(bowl_top.player_id)].copy()
    extras=q['extras_type'].astype('string').str.strip().str.casefold()
    q['candidate_legal_balls']=(~extras.isin(['wide','overstep'])).astype(int)
    q['bowler_credited_wickets']=(_bool(q['is_wicket']) & q['dismissal_type'].astype('string').str.strip().str.casefold().isin(BOWLER_CREDITED_DISMISSALS)).astype(int)
    q['fours']=_bool(q['is_four']).astype(int);q['sixes']=_bool(q['is_six']).astype(int)
    qg=q.groupby(['bowler_id','bowler_name','match_id','innings','bowling_team_id','batting_team_id','comp_name','season'],dropna=False).agg(
        death_candidate_legal_balls=('candidate_legal_balls','sum'),bowler_credited_wickets=('bowler_credited_wickets','sum'),flagged_fours_conceded=('fours','sum'),flagged_sixes_conceded=('sixes','sum')
    ).reset_index()
    qg=qg.merge(matches,on='match_id',how='left',validate='many_to_one')
    qg['opponent']=qg.apply(lambda r:r['away_team'] if r['bowling_team_id']==r['home_team_id'] else r['home_team'],axis=1)
    qg['flagged_boundaries_conceded']=qg['flagged_fours_conceded']+qg['flagged_sixes_conceded']
    bowl_rows=[]
    for _,r in bowl_top.iterrows():
        choices=qg.loc[qg.bowler_id.eq(r.player_id)].sort_values(['bowler_credited_wickets','death_candidate_legal_balls','flagged_boundaries_conceded','match_date'],ascending=[False,False,True,True])
        if choices.empty: continue
        x=choices.iloc[0]
        bowl_rows.append({'rank':int(r['rank']),'player_id':int(r.player_id),'player_name':r.player_name,'match_id':int(x.match_id),'match_date':x.match_date,'competition':x.comp_name,'season':x.season,'innings':int(x.innings),'opponent':x.opponent,'death_candidate_legal_balls':int(x.death_candidate_legal_balls),'bowler_credited_wickets':int(x.bowler_credited_wickets),'flagged_fours_conceded':int(x.flagged_fours_conceded),'flagged_sixes_conceded':int(x.flagged_sixes_conceded),'interpretation':'Illustrative death-over spell segment; not the sole basis of the ranking.'})
    bat_df=pd.DataFrame(bat_rows); bowl_df=pd.DataFrame(bowl_rows)
    out=Path(output_dir); bat_df.to_csv(out/'top10_batter_match_spotlights.csv',index=False); bowl_df.to_csv(out/'top10_bowler_match_spotlights.csv',index=False)
    return bat_df,bowl_df
