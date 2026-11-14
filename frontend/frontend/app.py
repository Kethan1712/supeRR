from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))

from data_layer import DashboardDataError, load_dashboard_data, resolve_project_root  # noqa: E402
from ui_helpers import format_number, metric_card, searchable_table, section_header, status_pill  # noqa: E402


st.set_page_config(
    page_title="SupeRR Selector | Season 2",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

NAV_ITEMS = [
    "01 · Overview",
    "02 · Top 10 Batters",
    "03 · Top 10 Bowlers",
    "04 · Player Intelligence",
    "05 · Pressure Analysis",
    "06 · Scope Comparison",
    "07 · RR Auction Strategy",
    "08 · Methodology & Validation",
]


@st.cache_data(show_spinner=False)
def cached_load(root_string: str):
    return load_dashboard_data(Path(root_string))


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1500px;}
        [data-testid="stSidebar"] {border-right: 1px solid rgba(216,177,90,.18);}
        .brand-kicker {color:#D8B15A; font-size:.74rem; letter-spacing:.18em; text-transform:uppercase; font-weight:700;}
        .hero-title {font-size:2.25rem; line-height:1.08; font-weight:800; letter-spacing:-.04em; margin:.25rem 0 .4rem 0;}
        .hero-subtitle {color:#AAB3C2; font-size:1rem; margin-bottom:1.1rem;}
        .section-title {font-size:1.25rem; font-weight:750; letter-spacing:-.02em; margin:.6rem 0 .25rem 0;}
        .metric-card {background:linear-gradient(145deg,#141C2A,#0E1520); border:1px solid rgba(216,177,90,.24); border-radius:14px; padding:1rem 1.1rem; min-height:105px; box-shadow:0 7px 22px rgba(0,0,0,.14);}
        .metric-label {color:#AAB3C2; font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; font-weight:650;}
        .metric-value {font-size:1.9rem; font-weight:800; color:#F4F5F7; margin-top:.28rem; line-height:1.1;}
        .pill {display:inline-block; border-radius:100px; padding:.22rem .62rem; font-size:.75rem; font-weight:700; border:1px solid #3B4658;}
        .pill-good {color:#8ED6B2; background:rgba(40,130,90,.13); border-color:rgba(88,190,140,.35);}
        .pill-warning {color:#E9C777; background:rgba(190,140,40,.12); border-color:rgba(216,177,90,.38);}
        .pill-danger {color:#F09A9A; background:rgba(170,60,60,.12); border-color:rgba(220,100,100,.32);}
        .pill-neutral {color:#BDC6D5; background:rgba(150,165,185,.08);}
        .small-note {font-size:.82rem; color:#9AA6B8;}
        .gold-rule {height:2px; background:linear-gradient(90deg,#D8B15A,rgba(216,177,90,0)); margin:.4rem 0 1.1rem 0;}
        /* Metric card */
        div[data-testid="stMetric"] {
            background: linear-gradient(145deg, #182335, #101827) !important;
            border: 1px solid rgba(216,177,90,.30);
            padding: 16px 18px;
            border-radius: 14px;
            box-shadow: 0 6px 18px rgba(0,0,0,.15);
        }

       /* Force readable labels on all native Streamlit metric cards */
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] *,
div[data-testid="stMetric"] label,
div[data-testid="stMetric"] label *,
div[data-testid="stMetric"] p,
div[data-testid="stMetric"] span {
    color: #D1D5DB !important;
    opacity: 1 !important;
    -webkit-text-fill-color: #D1D5DB !important;
}

/* Keep metric values bright white */
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricValue"] *,
div[data-testid="stMetric"] [data-testid="stMetricValue"] span {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    font-weight: 750 !important;
}

        /* Metric value */
        div[data-testid="stMetricValue"],
        div[data-testid="stMetricValue"] * {
            color: #FFFFFF !important;
            font-weight: 750 !important;
        }

        /* Metric help and delta */
        div[data-testid="stMetricDelta"],
        div[data-testid="stMetricDelta"] * {
            color: #D8B15A !important;
        }

        /* Cleaner dataframe appearance */
        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(216,177,90,.20);
            border-radius: 12px;
            overflow: hidden;
        }

        /* Consistent section spacing */
        div[data-testid="stVerticalBlock"] > div {
            scroll-margin-top: 20px;
        }

        /* Improve buttons */
        .stButton > button {
            border-radius: 9px;
            font-weight: 600;
            transition: all .2s ease;
        }

        /* Improve input fields */
        .stTextInput input {
            border-radius: 9px;
        }

        /* Improve select boxes */
        .stSelectbox div[data-baseweb="select"] {
            border-radius: 9px;
        }
        a {color:#E4C477 !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero() -> None:
    st.markdown('<div class="brand-kicker">Season 2 · IPL 2027 Auction Intelligence</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-title">SUPERR SELECTOR</div>', unsafe_allow_html=True)
    st.markdown('<div class="hero-subtitle">Most Reliable Batters and Bowlers Under Pressure · Analytics Platform</div>', unsafe_allow_html=True)
    st.markdown('<div class="gold-rule"></div>', unsafe_allow_html=True)


def fmt_index(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "reliability_score" in out.columns:
        out["reliability_score"] = pd.to_numeric(out["reliability_score"], errors="coerce").round(2)
    return out


def go_to(page: str, player_id=None) -> None:
    st.session_state["nav_target"] = page
    if player_id is not None:
        st.session_state["selected_player_id"] = int(player_id)
    st.rerun()


def page_overview(d: dict) -> None:
    hero()
    st.markdown("### Executive overview")
    st.write(
        "A reproducible, ball-by-ball analysis of player performance in defined pressure situations. "
        "The primary rankings use IPL 2022–2026 and senior T20 Internationals from 2022 onward."
    )

    validation = d["validation"]
    pressure = d["pressure_audit"]
    scope = d["competition_audit"].get("selected_counts", {})
    batting_n = len(d["batting_rankings"])
    bowling_n = len(d["bowling_rankings"])
    eligible_batters = validation.get("eligible_candidates", {}).get("batting", "—")
    eligible_bowlers = validation.get("eligible_candidates", {}).get("bowling", "—")
    matches = scope.get("matches", "—")
    matches_with_data = scope.get("matches_with_ball_by_ball", "—")
    deliveries = scope.get("ball_by_ball_rows", pressure.get("delivery_records_total", "—"))
    unique_pressure = pressure.get("combined_pressure_records_without_double_counting", "—")

    cards = [
        ("Eligible batters", format_number(eligible_batters)),
        ("Eligible bowlers", format_number(eligible_bowlers)),
        ("Matches", format_number(matches)),
        ("Deliveries analysed", format_number(deliveries)),
        ("Matches with ball data", format_number(matches_with_data)),
        ("Unique pressure deliveries", format_number(unique_pressure)),
    ]
    for row_start in (0, 3):
        cols = st.columns(3)
        for col, (label, value) in zip(cols, cards[row_start : row_start + 3]):
            with col:
                metric_card(label, value)

    st.caption("Primary scope · IPL + T20I · All figures are loaded from this project's audit and ranking outputs.")
    st.markdown("### Explore the leaderboards")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🏏  Explore Batters", use_container_width=True, type="primary"):
            go_to("02 · Top 10 Batters")
    with b2:
        if st.button("🎯  Explore Bowlers", use_container_width=True):
            go_to("03 · Top 10 Bowlers")

    st.markdown("### Official primary-scope leaders")
    left, right = st.columns(2)
    with left:
        st.markdown("**Top batter**")
        leader = d["batting_rankings"].sort_values("rank").iloc[0]
        st.metric(str(leader["player_name"]), f'{float(leader["reliability_score"]):.2f}', "Batting index")
    with right:
        st.markdown("**Top bowler**")
        leader = d["bowling_rankings"].sort_values("rank").iloc[0]
        st.metric(str(leader["player_name"]), f'{float(leader["reliability_score"]):.2f}', "Bowling index")
    st.info(
        "The 0–100 index is a relative composite score under the stated model. "
        "It is not a probability of future success, a career ranking, or a guarantee of auction performance."
    )


def leaderboard_page(d: dict, role: str) -> None:
    is_batter = role == "batter"
    title = "Top 10 Batters" if is_batter else "Top 10 Bowlers"
    key = "batting_rankings" if is_batter else "bowling_rankings"
    df = fmt_index(d[key].sort_values("rank"))
    section_header(title, "Official primary-scope leaderboard · IPL + senior T20I")
    st.caption("Click column headers to sort. Use the search field to filter names. Select a player below to open their evidence profile.")
    filtered, clicked_row = searchable_table(df, height=430, key_prefix=role)
    if clicked_row is not None:
        st.success(f"Selected: {clicked_row['player_name']} · #{int(clicked_row['rank'])}")
        if st.button("Open selected player profile", key=f"open_selected_{role}", type="primary"):
            go_to("04 · Player Intelligence", int(clicked_row["player_id"]))

    chart = px.bar(
        df.sort_values("reliability_score", ascending=True),
        x="reliability_score",
        y="player_name",
        orientation="h",
        text=df.sort_values("reliability_score", ascending=True)["reliability_score"].map(lambda x: f"{x:.2f}"),
        labels={"reliability_score": "Reliability index (0–100)", "player_name": "Player"},
        title=f"{title} · index comparison",
    )
    chart.update_traces(marker_color="#D8B15A", textposition="outside", cliponaxis=False)
    chart.update_layout(height=420, margin=dict(l=15, r=55, t=55, b=35), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(chart, use_container_width=True)

    options = df[["player_id", "player_name", "rank"]].copy()
    options["label"] = options.apply(lambda x: f"#{int(x['rank'])} · {x['player_name']}", axis=1)
    selected_label = st.selectbox("Open player intelligence", options["label"].tolist(), key=f"profile_select_{role}")
    selected_id = int(options.loc[options["label"] == selected_label, "player_id"].iloc[0])
    if st.button("Open detailed player profile", key=f"open_profile_{role}", type="primary"):
        go_to("04 · Player Intelligence", selected_id)
    if len(filtered) == 0:
        st.warning("No players match that search.")


def metric_component_table(row: pd.Series, role: str) -> pd.DataFrame:
    if role == "Batter":
        components = [
            ("Recorded runs", "recorded_runs", "Higher is favourable"),
            ("Dismissals", "dismissals", "Lower is favourable"),
            ("Flagged boundaries", "flagged_boundaries", "Higher is favourable"),
        ]
    else:
        components = [
            ("Bowler-credited wickets", "bowler_credited_wickets", "Higher is favourable"),
            ("Flagged boundaries conceded", "flagged_boundaries_conceded", "Lower is favourable"),
        ]
    records = []
    for label, prefix, direction in components:
        records.append(
            {
                "Metric": label,
                "Raw pressure rate / 100": row.get(f"{prefix}_raw_rate_per_100"),
                "Peer rate / 100": row.get(f"{prefix}_peer_rate_per_100"),
                "Adjusted vs peer (%)": row.get(f"{prefix}_adjusted_relative_vs_peer_pct"),
                "Pressure uplift (pp)": row.get(f"{prefix}_pressure_uplift_pct_points"),
                "Model weight": row.get(f"{prefix}_metric_weight"),
                "Direction": direction,
            }
        )
    out = pd.DataFrame(records)
    for c in ["Raw pressure rate / 100", "Peer rate / 100", "Adjusted vs peer (%)", "Pressure uplift (pp)"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").round(2)
    out["Model weight"] = pd.to_numeric(out["Model weight"], errors="coerce").map(lambda x: f"{x:.0%}" if pd.notna(x) else "—")
    return out


def player_profile_page(d: dict) -> None:
    section_header("Player Intelligence", "Player-level evidence from the official primary-scope ranking outputs")
    role_choice = st.radio("Player category", ["Batter", "Bowler"], horizontal=True)
    evidence_key = "batter_evidence" if role_choice == "Batter" else "bowler_evidence"
    spot_key = "batter_spotlights" if role_choice == "Batter" else "bowler_spotlights"
    evidence = d[evidence_key].sort_values("rank").copy()
    labels = evidence.apply(lambda r: f"#{int(r['rank'])} · {r['player_name']}", axis=1)
    stored_id = st.session_state.get("selected_player_id")
    default_index = 0
    if stored_id is not None:
        matches = evidence.index[evidence["player_id"].astype(int) == int(stored_id)].tolist()
        if matches:
            default_index = evidence.index.get_loc(matches[0])
    choice = st.selectbox("Select player", labels.tolist(), index=min(default_index, len(labels) - 1), key=f"profile_choice_{role_choice}")
    row = evidence.loc[labels == choice].iloc[0]
    st.session_state["selected_player_id"] = int(row["player_id"])

    st.markdown(f"## {row['player_name']}")
    score_col, rank_col, volume_col = st.columns(3)
    score_col.metric("Official primary index", f"{float(row['final_index']):.2f}")
    rank_col.metric("Primary rank", f"#{int(row['rank'])}")
   volume_label = str(row.get("evidence_volume_label", "Not labelled"))

volume_col.caption("EVIDENCE VOLUME")
volume_col.write(volume_label)

    kpis = st.columns(4)
    kpis[0].metric("Pressure opportunities", format_number(row.get("pressure_opportunities")))
    kpis[1].metric("Pressure matches", format_number(row.get("pressure_matches")))
    kpis[2].metric("Positive match share", f"{float(row.get('positive_match_share_pct', 0)):.1f}%")
    kpis[3].metric("Ordinary matches", format_number(row.get("ordinary_matches")))

    a, b, c = st.columns(3)
    a.metric("Performance component", f"{float(row.get('performance_component', 0)):.2f}")
    b.metric("Consistency component", f"{float(row.get('consistency_component', 0)):.2f}")
    c.metric("Mean pressure vs peers", f"{float(row.get('mean_pressure_adjusted_vs_peer_pct', 0)):.2f}%")
    st.metric("Mean uplift vs ordinary performance", f"{float(row.get('mean_uplift_vs_ordinary_pct_points', 0)):.2f} percentage points")

    st.markdown("### Metric-level evidence")
    st.dataframe(metric_component_table(row, role_choice), use_container_width=True, hide_index=True)
    st.caption(
        "Rates are calculated from the source's recorded fields and supplied flags. "
        "They are not reconstructed official scorecard strike rates or economy rates."
    )

    spot = d[spot_key]
    spot = spot[spot["player_id"].astype(int) == int(row["player_id"])].copy()
    st.markdown("### Match spotlight")
    if spot.empty:
        st.info("No spotlight row is available for this player in the supplied output file.")
    else:
        if role_choice == "Batter":
            display_cols = ["match_date", "competition", "innings", "opponent", "pressure_balls", "pressure_recorded_runs", "flagged_fours", "flagged_sixes", "pressure_segment_recorded_sr", "interpretation"]
            rename = {"pressure_segment_recorded_sr": "Segment recorded runs / 100 balls"}
        else:
            display_cols = ["match_date", "competition", "innings", "opponent", "death_candidate_legal_balls", "bowler_credited_wickets", "flagged_fours_conceded", "flagged_sixes_conceded", "interpretation"]
            rename = {}
        st.dataframe(spot[display_cols].rename(columns=rename), use_container_width=True, hide_index=True)
        if role_choice == "Batter":
            st.caption("The spotlight is one illustrative pressure-labelled innings segment, not the full basis of the ranking.")
        else:
            st.caption("The spotlight is one illustrative death-over spell segment, not the full basis of the ranking.")

    with st.expander("View complete evidence row"):
        st.json({k: (None if pd.isna(v) else v.item() if hasattr(v, "item") else v) for k, v in row.to_dict().items()})


def pressure_page(d: dict) -> None:
    section_header("Pressure Analysis", "Pressure is operationalised using innings context, not inferred psychological state")
    audit = d["pressure_audit"]
    counts = audit.get("pressure_category_record_counts", {})
    early = int(audit.get("early_collapse_pressure_records", 0))
    death = int(audit.get("death_phase_pressure_records", 0))
    overlap = int(audit.get("overlapping_pressure_records", 0))
    unique = int(audit.get("combined_pressure_records_without_double_counting", 0))
    ordinary = int(counts.get("ordinary", 0))
    death_only = int(counts.get("death_over", 0))
    collapse_only = int(counts.get("early_collapse", 0))
    both = int(counts.get("early_collapse_and_death_over", overlap))

    cols = st.columns(4)
    cols[0].metric("Early-collapse records", format_number(early))
    cols[1].metric("Death-phase records", format_number(death))
    cols[2].metric("Overlap", format_number(overlap))
    cols[3].metric("Unique combined pressure", format_number(unique))

    st.markdown("### De-duplicated delivery distribution")
    dist = pd.DataFrame(
        {
            "Pressure category": ["Ordinary", "Death only", "Early collapse only", "Both pressure categories"],
            "Delivery records": [ordinary, death_only, collapse_only, both],
        }
    )
    fig = px.bar(dist, x="Pressure category", y="Delivery records", text="Delivery records", labels={"Delivery records": "Delivery records", "Pressure category": "Category"})
    fig.update_traces(marker_color=["#526174", "#D8B15A", "#9C7B3E", "#E6D4A3"], texttemplate="%{text:,}", textposition="outside", cliponaxis=False)
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=25, b=15), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    regular_records = int(audit.get("regular_innings_delivery_records", 0))
    additional_records = int(audit.get("additional_innings_delivery_records", 0))
    st.caption(
        "The 'both' category is counted once in the de-duplicated distribution. "
        "Early-collapse and death headline totals overlap and must not be added together. "
        f"The distribution covers {regular_records:,} regular-innings records; "
        f"{additional_records:,} additional-innings records are retained separately and are not pressure-classified."
    )

    st.markdown("### Pressure definitions")
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("**Early-collapse pressure**")
        st.write("Five or more wickets lost by the end of the first 50% of the allocated innings. The pressure flag starts on the next delivery after the fifth wicket.")
    with p2:
        st.markdown("**Death-phase pressure**")
        st.write("The final 25% of allocated innings, rounded to full overs. In a standard 20-over innings, this corresponds to overs 16–20.")
    st.info("Batters are evaluated on the de-duplicated union of early-collapse OR death-phase deliveries. Bowlers are evaluated on death-phase pressure only; batting-side collapse is not automatically treated as pressure on the bowler.")

    st.markdown("### Metric weights used by the scoring model")
    weight_rows = []
    for role_name, evidence_key, metrics in [
        ("Batting", "batter_evidence", [("Recorded runs per 100 balls", "recorded_runs"), ("Dismissals per 100 balls", "dismissals"), ("Flagged boundaries per 100 balls", "flagged_boundaries")]),
        ("Bowling", "bowler_evidence", [("Bowler-credited wickets per 100 candidate legal balls", "bowler_credited_wickets"), ("Flagged boundaries conceded per 100 candidate legal balls", "flagged_boundaries_conceded")]),
    ]:
        evidence_row = d[evidence_key].iloc[0]
        for metric_label, prefix in metrics:
            weight_rows.append({"Role": role_name, "Metric": metric_label, "Weight": float(evidence_row.get(f"{prefix}_metric_weight", 0))})
    weight_df = pd.DataFrame(weight_rows)
    weight_df["Weight"] = weight_df["Weight"].map(lambda x: f"{x:.0%}")
    st.dataframe(weight_df, use_container_width=True, hide_index=True)

    st.markdown("### Measurement notes")
    st.write("The source records are described as delivery records. Wide and Overstep records are excluded from candidate legal-ball counts; a single Penalty-coded record is retained under the primary rule because its semantics are uncertain.")
    st.write("Bowling economy and true dot-ball rates are not shown because the supplied extras fields do not support a reliable reconstruction of total bowler-charged runs or true dot balls.")
    allocation = audit.get("allocation_source_record_counts", {})
    with st.expander("Allocated-innings handling and audit detail"):
        st.json({
            "allocation_source_record_counts": allocation,
            "revised_allocation_encoding_check": audit.get("revised_allocation_encoding_check", {}),
            "early_collapse_innings": audit.get("early_collapse_innings"),
            "matches_with_early_collapse": audit.get("matches_with_early_collapse"),
            "matches_with_death_phase_pressure": audit.get("matches_with_death_phase_pressure"),
        })


def scope_page(d: dict) -> None:
    section_header("Competition Scope Comparison", "Two separately recalculated scopes · scores are not directly comparable across scopes")
    scope = d["scope_comparison"]
    primary = scope.get("primary_scope", {})
    expanded = scope.get("expanded_scope", {})
    selection = st.radio("Ranking population", ["Official · IPL + T20I", "Expanded · all supplied T20 + T20I"], horizontal=True)
    is_expanded = selection.startswith("Expanded")
    selected = expanded if is_expanded else primary

    cols = st.columns(4)
    cols[0].metric("Match rows", format_number(selected.get("matches")))
    cols[1].metric("Matches with ball data", format_number(selected.get("matches_with_ball_by_ball")))
    cols[2].metric("Delivery records", format_number(selected.get("ball_by_ball_rows")))
    cols[3].metric("Competition IDs", format_number(selected.get("competition_ids")))

    ranking_tabs = st.tabs(["Batting Top 10", "Bowling Top 10"])
    for tab, key, label in [(ranking_tabs[0], "expanded_batting_rankings" if is_expanded else "batting_rankings", "Batter"), (ranking_tabs[1], "expanded_bowling_rankings" if is_expanded else "bowling_rankings", "Bowler")]:
        with tab:
            table = fmt_index(d[key].sort_values("rank"))
            st.dataframe(table, use_container_width=True, hide_index=True, column_config={"reliability_score": st.column_config.NumberColumn("Index", format="%.2f")})

    batter_overlap = scope.get("batters", {}).get("top10_overlap_out_of_10", "—")
    bowler_overlap = scope.get("bowlers", {}).get("top10_overlap_out_of_10", "—")
    st.markdown("### Effect of adding Emerging Teams and Rising Stars")
    a, b = st.columns(2)
    a.metric("Batter Top 10 overlap", batter_overlap)
    b.metric("Bowler Top 10 overlap", bowler_overlap)
    added = scope.get("additional_competitions", [])
    if added:
        st.dataframe(pd.DataFrame(added), use_container_width=True, hide_index=True)

    st.markdown("### Players entering, leaving and retained")
    compare = d["scope_players"].copy()
    compare["role"] = compare["role"].str.title()
    st.dataframe(
        compare,
        use_container_width=True,
        hide_index=True,
        column_config={
            "primary_score": st.column_config.NumberColumn("Primary index", format="%.2f"),
            "expanded_score": st.column_config.NumberColumn("Expanded index", format="%.2f"),
            "rank_change_expanded_minus_primary": st.column_config.NumberColumn("Rank change", format="%+.0f"),
            "score_change_expanded_minus_primary": st.column_config.NumberColumn("Score change", format="%+.2f"),
        },
    )
    st.warning(
        "The candidate pool and peer baselines are recalculated in each scope. "
        "Do not interpret a primary index and an expanded index as values on one unchanged scale. "
        "The primary ranking files remain the official submission reference."
    )


def rr_strategy_page(d: dict) -> None:
    section_header("Rajasthan Royals · IPL 2027 Auction Strategy", "Role-depth view based on the supplied 2026 usage audit and conditional player-fit screen")
    st.info("This is a planning aid, not an official 2027 squad list. A 2026 squad listing does not prove 2027 retention, release or auction availability.")
    st.markdown("### RR role-depth matrix")
    st.dataframe(d["role_depth"], use_container_width=True, hide_index=True, height=420)

    st.markdown("### Ranked-player fit screen")
    fit = d["rr_player_fit"].copy()
    filter_role = st.selectbox("Filter player category", ["All", "Batter", "Bowler"])
    if filter_role != "All":
        fit = fit[fit["role"].str.lower() == filter_role.lower()]
    fit = fit.sort_values(["role", "rank"])
    fit_columns = [
        "rank", "player_name", "role", "reliability_score", "pressure_opportunities",
        "pressure_matches", "mean_pressure_adjusted_vs_peer_pct",
        "mean_uplift_vs_ordinary_pct_points", "nationality_group",
        "role_profile", "2026_team_status", "rr_role_fit",
    ]
    st.dataframe(
        fit[fit_columns],
        use_container_width=True,
        hide_index=True,
        column_config={"reliability_score": st.column_config.NumberColumn("Index", format="%.2f")},
    )
    labels = fit.apply(lambda r: f"{r['player_name']} · {r['role']} · {r['rr_role_fit']}", axis=1).tolist()
    if labels:
        selected = st.selectbox("Inspect RR fit rationale", labels, key="rr_fit_select")
        selected_row = fit.iloc[labels.index(selected)]
        st.markdown(f"#### {selected_row['player_name']}")
        st.write(f"**Role profile:** {selected_row['role_profile']}")
        st.write(f"**2026 team status in reviewed data:** {selected_row['2026_team_status']}")
        st.write(f"**RR fit assessment:** {selected_row['rr_role_fit']}")
        k1, k2, k3 = st.columns(3)
        k1.metric("Primary index", f"{float(selected_row['reliability_score']):.2f}")
        k2.metric("Pressure opportunities", format_number(selected_row["pressure_opportunities"]))
        k3.metric("Pressure matches", format_number(selected_row["pressure_matches"]))
        st.write(str(selected_row["fit_rationale"]))
        st.caption(str(selected_row["status_note"]))

    if not d["rr_squad_audit"].empty:
        with st.expander("2026 RR squad usage data"):
            squad = d["rr_squad_audit"].copy()
            st.dataframe(squad, use_container_width=True, hide_index=True, height=400)
    st.markdown("### Auction decision guardrails")
    st.write("1. Confirm official retention and release decisions before treating a player as purchasable.")
    st.write("2. Confirm the final auction registration list before naming a player as an available target.")
    st.write("3. Reassess role vacancies after retentions, overseas-slot limits, injury cover and current squad depth are known.")
    st.write("4. Treat statistical ranking and squad fit as separate decisions: a high-ranked player is not automatically the best auction purchase.")


def methodology_page(d: dict) -> None:
    section_header("Methodology & Validation", "What the system measures, how it scores, and what the source data cannot support")
    b_audit = d["batting_audit"]
    w_audit = d["bowling_audit"]
    v = d["validation"]
    checks = d["release_checks"]

    st.markdown("### Eligibility and reproducibility")
    cols = st.columns(4)
    cols[0].metric("Eligible batter candidates", format_number(v.get("eligible_candidates", {}).get("batting", 0)))
    cols[1].metric("Eligible bowler candidates", format_number(v.get("eligible_candidates", {}).get("bowling", 0)))
    tests = checks.get("automated_tests", {})
    cols[2].metric("Automated tests passed", format_number(tests.get("passed", 0)))
    cols[3].metric("Automated test failures", format_number(tests.get("failed", 0)))
    st.code(tests.get("command", "python -m pytest -q"), language="bash")
    st.caption(str(tests.get("final_run", d["test_results"].strip().splitlines()[-1] if d["test_results"].strip() else "Test record unavailable")))

    st.markdown("### Dataset source and analysis period")
    st.write("The project uses the six supplied CSV inputs in the parent project's data/ folder: ball-by-ball records, matches, playing elevens, competition/team/player mapping, teams and competitions. The dashboard reads generated outputs; it does not need to reload raw deliveries for display.")
    st.write("Primary analysis period: IPL seasons 2022–2026 and senior T20 Internationals from 2022 onward, as represented in the supplied data pack.")

    st.markdown("### Scoring construction")
    st.write("The final index combines a pressure-performance component (70%) and a match-consistency component (30%). The index is a model-based relative score, not a probability of future success.")
    metric_rows = []
    batter_row = d["batter_evidence"].iloc[0]
    bowler_row = d["bowler_evidence"].iloc[0]
    for label, row, prefixes in [
        ("Batting", batter_row, [("Recorded runs / 100 balls", "recorded_runs"), ("Dismissals / 100 balls", "dismissals"), ("Flagged boundaries / 100 balls", "flagged_boundaries")]),
        ("Bowling", bowler_row, [("Bowler-credited wickets / 100 candidate legal balls", "bowler_credited_wickets"), ("Flagged boundaries conceded / 100 candidate legal balls", "flagged_boundaries_conceded")]),
    ]:
        for metric, prefix in prefixes:
            metric_rows.append({"Role": label, "Metric": metric, "Weight": float(row.get(f"{prefix}_metric_weight", 0))})
    mdf = pd.DataFrame(metric_rows)
    mdf["Weight"] = mdf["Weight"].map(lambda x: f"{x:.0%}")
    st.dataframe(mdf, use_container_width=True, hide_index=True)

    st.markdown("### How the composite is constructed")
    st.write("For each metric, the pressure-performance percentile is the average of (a) pressure performance relative to peers and (b) that player's pressure uplift relative to their ordinary peer-adjusted performance. The metric-level performance percentiles are then combined using the role-specific metric weights.")
    st.write("For each metric, the consistency percentile is composed of 50% positive adjusted match share, 30% median adjusted match peer-relative performance and 20% inverse dispersion (lower match-to-match variability scores better). These metric-level consistency percentiles are then combined using the same role-specific metric weights.")

    st.markdown("### Peer baselines and shrinkage")
    st.write("Peer baselines use a leave-one-player-out, context-matched hierarchy: competition + innings + phase; then format + season + innings + phase; then format + innings + phase. The player-level shrinkage prior is 60 opportunities; the match-level prior is 12 opportunities.")
    st.latex(r"\text{Shrunk rate} = \frac{\text{Observed numerator} + k \times (\text{Peer rate}/100)}{\text{Matched opportunities} + k} \times 100")
    st.write("Here, k is the prior opportunity strength (60 for player-level pressure/ordinary rates and 12 for player-match estimates). Small samples are pulled more strongly toward their context-matched peer rate; larger samples are influenced more by the player's observed data. Shrinkage reduces volatility but does not eliminate uncertainty.")

    st.markdown("### Eligibility thresholds")
    st.write("Batters need at least 100 combined-pressure opportunities and 10 pressure matches. Bowlers need at least 60 death-phase candidate legal balls and 10 pressure matches. The ordinary comparison must also meet its opportunity and match thresholds, every rated metric must have supported pressure and ordinary peer baselines, and baseline coverage must be at least 80%.")
    st.write("Final index = 70% pressure-performance component + 30% match-consistency component. It is a relative composite percentile, not a probability or forecast of future success.")

    st.markdown("### Data limitations surfaced by the audit")
    left, right = st.columns(2)
    with left:
        st.markdown("**Batting data**")
        runchecks = b_audit.get("run_and_boundary_checks", {})
        dchecks = b_audit.get("dismissal_attribution_checks", {})
        st.write(f"Recorded runs total: {format_number(b_audit.get('source_coverage', {}).get('recorded_runs_sum', 0))}")
        st.write(f"Four-run rows without a four flag: {format_number(runchecks.get('runs_equal_4_without_four_flag', 0))}")
        st.write(f"Six-run rows without a six flag: {format_number(runchecks.get('runs_equal_6_without_six_flag', 0))}")
        st.write(f"Dismissal records with missing dismissed-player ID: {format_number(dchecks.get('dismissed_player_id_missing', 0))}")
    with right:
        st.markdown("**Bowling data**")
        metric_defs = w_audit.get("metric_definitions", {})
        source_checks = w_audit.get("source_checks", {})
        st.write(f"Candidate legal-ball records: {format_number(source_checks.get('primary_candidate_legal_ball_records', 0))}")
        st.write(f"Bowler-credited wickets: {format_number(source_checks.get('bowler_credited_wicket_records', 0))}")
        st.write("Economy rate: not calculated (total bowler-charged runs cannot be reconstructed reliably).")
        st.write("True dot-ball rate: not calculated (extras data cannot reliably identify all dot balls).")
    st.markdown("### Scope and ranking checks")
    st.json({
        "primary_scope": v.get("scope", {}),
        "batters": {k: v.get("batters", {}).get(k) for k in ["rows", "unique_players", "ranks_1_to_10", "scores_descending", "minimum_pressure_metric_baseline_coverage_pct"]},
        "bowlers": {k: v.get("bowlers", {}).get(k) for k in ["rows", "unique_players", "ranks_1_to_10", "scores_descending", "minimum_pressure_metric_baseline_coverage_pct"]},
        "ranking_lock": checks.get("original_ranking_lock", {}),
        "scope_comparison": checks.get("competition_scope_comparison", {}),
    })
    st.markdown("### Full test output")
    st.code(d["test_results"], language="text")


def render_sidebar(d: dict) -> str:
    st.sidebar.markdown('<div class="brand-kicker">SUPERR SELECTOR</div>', unsafe_allow_html=True)
    st.sidebar.markdown("## Season 2")
    st.sidebar.caption("IPL 2027 Auction Intelligence")
    default_page = st.session_state.get("nav_target", NAV_ITEMS[0])
    if default_page not in NAV_ITEMS:
        default_page = NAV_ITEMS[0]
    choice = st.sidebar.radio("NAVIGATION", NAV_ITEMS, index=NAV_ITEMS.index(default_page), label_visibility="visible")
    st.session_state["nav_target"] = choice
    st.sidebar.markdown("---")
    st.sidebar.caption("Primary rankings: IPL + senior T20I")
    st.sidebar.caption("Expanded scope: supplementary sensitivity analysis")
    st.sidebar.caption("Read-only presentation layer · CSV-backed")
    return choice


def main() -> None:
    apply_styles()
    root = resolve_project_root()
    manual_root = st.session_state.get("manual_project_root")
    if manual_root and (Path(manual_root) / "outputs").is_dir():
        root = Path(manual_root).resolve()
    if root is None:
        st.title("SUPERR SELECTOR")
        st.error("Could not find the project outputs/ folder.")
        st.write("Copy this `frontend/` folder directly into the SupeRR project root, beside `outputs/`, then run the dashboard again.")
        st.code("project_root/\n├── frontend/\n├── outputs/\n├── src/\n└── data/", language="text")
        manual = st.text_input("Or enter the full path to your SupeRR project root")
        if manual and (Path(manual).expanduser() / "outputs").is_dir():
            st.session_state["manual_project_root"] = str(Path(manual).expanduser().resolve())
            st.rerun()
        return

    try:
        d = cached_load(str(root))
    except DashboardDataError as exc:
        st.error(str(exc))
        st.info("The frontend was built for the SupeRR Selector Season 2 Complete project outputs. Make sure you copied it into that project release.")
        return

    page = render_sidebar(d)
    if page == NAV_ITEMS[0]:
        page_overview(d)
    elif page == NAV_ITEMS[1]:
        leaderboard_page(d, "batter")
    elif page == NAV_ITEMS[2]:
        leaderboard_page(d, "bowler")
    elif page == NAV_ITEMS[3]:
        player_profile_page(d)
    elif page == NAV_ITEMS[4]:
        pressure_page(d)
    elif page == NAV_ITEMS[5]:
        scope_page(d)
    elif page == NAV_ITEMS[6]:
        rr_strategy_page(d)
    elif page == NAV_ITEMS[7]:
        methodology_page(d)

    st.markdown("---")
    st.caption(f"Data source: {root / 'outputs'} · Dashboard reads existing CSV/JSON outputs and does not recalculate rankings.")


if __name__ == "__main__":
    main()
