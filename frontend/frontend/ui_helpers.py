"""Reusable display helpers for the SupeRR Selector Streamlit frontend."""
from __future__ import annotations

import pandas as pd
import streamlit as st


def metric_card(label: str, value: str, help_text: str | None = None) -> None:
    help_attr = f'title="{help_text}"' if help_text else ""
    st.markdown(
        f'<div class="metric-card" {help_attr}>'
        f'<div class="metric-label">{label}</div>'
        f'<div class="metric-value">{value}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="section-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.caption(subtitle)


def format_number(value, decimals: int = 0) -> str:
    try:
        n = float(value)
        if decimals == 0:
            return f"{n:,.0f}"
        return f"{n:,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def searchable_table(df: pd.DataFrame, name_col: str = "player_name", height: int = 420, key_prefix: str = "leaderboard") -> pd.DataFrame:
    """Search and sort table; return the filtered rows for downstream selection."""
    left, right = st.columns([2, 1])
    with left:
        query = st.text_input("Search player", key=f"search_{key_prefix}_{name_col}", placeholder="Type a player name…")
    with right:
        sort_choice = st.selectbox("Sort by", ["Official rank", "Index: high to low", "Index: low to high"], key=f"sort_{key_prefix}_{name_col}")
    filtered = df.copy()
    if query.strip() and name_col in filtered.columns:
        filtered = filtered[filtered[name_col].astype(str).str.contains(query.strip(), case=False, na=False)]
    if sort_choice == "Index: high to low" and "reliability_score" in filtered.columns:
        filtered = filtered.sort_values("reliability_score", ascending=False)
    elif sort_choice == "Index: low to high" and "reliability_score" in filtered.columns:
        filtered = filtered.sort_values("reliability_score", ascending=True)
    elif "rank" in filtered.columns:
        filtered = filtered.sort_values("rank", ascending=True)
    event = st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        height=height,
        on_select="rerun",
        selection_mode="single-row",
        key=f"leaderboard_table_{key_prefix}_{name_col}",
        column_config={
            "rank": st.column_config.NumberColumn("Rank", format="%d"),
            "reliability_score": st.column_config.NumberColumn("Index", format="%.2f"),
            "final_index": st.column_config.NumberColumn("Index", format="%.2f"),
            "positive_match_share_pct": st.column_config.NumberColumn("Positive match share", format="%.1f%%"),
            "mean_pressure_adjusted_vs_peer_pct": st.column_config.NumberColumn("Pressure vs peers", format="%.1f%%"),
            "mean_uplift_vs_ordinary_pct_points": st.column_config.NumberColumn("Uplift vs ordinary", format="%.1f pp"),
        },
    )
    st.caption(f"Showing {len(filtered)} of {len(df)} records. Sort columns by clicking headers; select a row to open its player profile.")
    selected = None
    try:
        selected_rows = event.selection.rows
        if selected_rows:
            selected = filtered.iloc[int(selected_rows[0])]
    except (AttributeError, IndexError, TypeError, ValueError):
        selected = None
    return filtered, selected


def status_pill(text: str, tone: str = "neutral") -> None:
    allowed = {"neutral", "good", "warning", "danger"}
    if tone not in allowed:
        tone = "neutral"
    st.markdown(f'<span class="pill pill-{tone}">{text}</span>', unsafe_allow_html=True)
