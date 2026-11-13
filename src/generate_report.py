"""Generate the audited SupeRR Selector report from current project outputs."""
from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt, RGBColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

NAVY = "17365D"
GOLD = "C29A45"
PALE = "EAF0F6"
GREY = "5B6573"


def _read_json(out: Path, name: str) -> dict:
    return json.loads((out / name).read_text(encoding="utf-8"))


def _shade(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    tc_pr.append(shd)


def _set_cell(cell, text, *, bold=False, color=None, size=8.1, fill=None):
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    run = p.add_run(str(text))
    run.bold = bold
    run.font.name = "Liberation Sans"
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor.from_string(color)
    if fill:
        _shade(cell, fill)
    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def _table(doc, headers, rows, widths=None, *, font=8.0, header_font=8.1, repeat=True):
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    try:
        table.style = "Table Grid"
    except KeyError:
        pass
    if repeat:
        trpr = table.rows[0]._tr.get_or_add_trPr()
        flag = OxmlElement("w:tblHeader")
        flag.set(qn("w:val"), "true")
        trpr.append(flag)
    for cell, header in zip(table.rows[0].cells, headers):
        _set_cell(cell, header, bold=True, color="FFFFFF", size=header_font, fill=NAVY)
    for ridx, row in enumerate(rows):
        cells = table.add_row().cells
        trpr = table.rows[-1]._tr.get_or_add_trPr()
        cant = OxmlElement("w:cantSplit")
        trpr.append(cant)
        for cell, value in zip(cells, row):
            _set_cell(cell, value, size=font, fill=("F5F7FA" if ridx % 2 == 1 else None))
    if widths:
        for row in table.rows:
            for idx, width in enumerate(widths):
                row.cells[idx].width = Inches(width)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)
    return table


def _heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(5 if level == 1 else 3)
    p.paragraph_format.space_after = Pt(3)
    return p


def _p(doc, text, *, bold_prefix=None, size=None, color=None, italic=False):
    para = doc.add_paragraph()
    para.paragraph_format.space_after = Pt(4)
    para.paragraph_format.line_spacing = 1.02
    if bold_prefix and text.startswith(bold_prefix):
        r = para.add_run(bold_prefix)
        r.bold = True
        rest = para.add_run(text[len(bold_prefix):])
        runs = [r, rest]
    else:
        runs = [para.add_run(text)]
    for r in runs:
        r.font.name = "Liberation Sans"
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = RGBColor.from_string(color)
        r.italic = italic
    return para


def _bullet(doc, text, *, size=8.8):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.left_indent = Inches(0.2)
    p.paragraph_format.first_line_indent = Inches(-0.12)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.0
    r = p.add_run(text)
    r.font.name = "Liberation Sans"
    r.font.size = Pt(size)
    return p


def _page(doc):
    doc.add_page_break()


def _add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = paragraph.add_run("PAGE ")
    r.font.size = Pt(8)
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    paragraph._p.append(fld)


def _fmt_num(x, decimals=2):
    try:
        return f"{float(x):,.{decimals}f}"
    except (TypeError, ValueError):
        return str(x)


def _source_bibliography(doc):
    _heading(doc, "External references for the RR and 2027 planning appendix", 2)
    references = [
        "Rajasthan Royals, IPL 2026 squad and player roles/stats: https://www.rajasthanroyals.com/rr-players (accessed 13 November 2026).",
        "Rajasthan Royals, official IPL 2026 season statistics: https://www.rajasthanroyals.com/stats (accessed 13 November 2026).",
        "BBC Sport, IPL 2026 squads (published 16 December 2025; updated 27 March 2026): https://www.bbc.co.uk/sport/cricket/articles/cp891x46p65o (accessed 13 November 2026).",
        "IPL/BCCI, Rishabh Pant and Kuldeep Yadav complete DC–LSG trade (23 June 2026): https://www.iplt20.com/news/article/rishabh-pant-and-kuldeep-yadav-complete-high-profile-trade-between-dc-and-lsg (accessed 13 November 2026).",
        "IPL/BCCI, CSK–SRH four-player trade (5 November 2026): https://www.iplt20.com/news/article/csk-and-srh-agree-to-four-player-trade (accessed 13 November 2026).",
        "IPL/BCCI, TATA IPL 2026 player retentions announced: https://www.iplt20.com/news/article/tata-ipl-2026-player-retentions-announced (accessed 13 November 2026).",
        "IPL/BCCI, TATA IPL Player Regulations 2025–27: https://www.iplt20.com/news/article/ipl-governing-council-announces-tata-ipl-player-regulations-2025-27 (accessed 13 November 2026).",
        "Cricbuzz, BCCI extends IPL retention deadline to November 17; mini-auction schedule reported for 16 December in Goa: https://www.cricbuzz.com/cricket-news/140762/bcci-extends-ipl-retention-deadline-to-november-17-cricbuzzcom (published 2 November 2026; accessed 12 November 2026).",
    ]
    for item in references:
        _bullet(doc, item, size=7.6)


def generate_methodology_report(output_dir="outputs", report_path="methodology_report.docx"):
    out = Path(output_dir)
    bat = pd.read_csv(out / "batting_rankings_top10.csv")
    bowl = pd.read_csv(out / "bowling_rankings_top10.csv")
    prior_sens = pd.read_csv(out / "ranking_sensitivity.csv")
    cutoff_sens = pd.read_csv(out / "pressure_threshold_ranking_stability.csv")
    metric_sens = pd.read_csv(out / "metric_weight_sensitivity.csv")
    rr = pd.read_csv(out / "rr_2026_squad_role_audit.csv")
    rr_fit = pd.read_csv(out / "rr_2027_ranked_player_fit.csv")
    bat_profiles = pd.read_csv(out / "top10_batter_evidence.csv")
    bowl_profiles = pd.read_csv(out / "top10_bowler_evidence.csv")
    role_depth = pd.read_csv(out / "rr_2027_role_depth_matrix.csv")
    bat_spotlights = pd.read_csv(out / "top10_batter_match_spotlights.csv")
    bowl_spotlights = pd.read_csv(out / "top10_bowler_match_spotlights.csv")
    boundary_sens = _read_json(out, "boundary_flag_sensitivity.json")
    scope = _read_json(out, "competition_scope_audit.json")
    scope_comparison = _read_json(out / "scope_comparison", "competition_scope_comparison.json")
    expanded_bat = pd.read_csv(out / "scope_comparison" / "expanded_batting_rankings_top10.csv")
    expanded_bowl = pd.read_csv(out / "scope_comparison" / "expanded_bowling_rankings_top10.csv")
    expanded_bat = pd.read_csv(out / "scope_comparison" / "expanded_batting_rankings_top10.csv")
    expanded_bowl = pd.read_csv(out / "scope_comparison" / "expanded_bowling_rankings_top10.csv")
    ctx = _read_json(out, "match_context_audit.json")
    press = _read_json(out, "pressure_detection_audit.json")
    batt_audit = _read_json(out, "batting_metrics_audit.json")
    bowl_audit = _read_json(out, "bowling_metrics_audit.json")
    baseline = _read_json(out, "player_baseline_audit.json")
    reliability = _read_json(out, "player_reliability_audit.json")
    rank_audit = _read_json(out, "ranking_audit.json")
    stability = _read_json(out, "ranking_stability_audit.json")
    rr_audit = _read_json(out, "rr_2026_squad_role_audit.json")
    metric_detail = _read_json(out, "metric_weight_sensitivity.json")

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(0.55)
    sec.bottom_margin = Inches(0.55)
    sec.left_margin = Inches(0.68)
    sec.right_margin = Inches(0.68)
    sec.header_distance = Inches(0.25)
    sec.footer_distance = Inches(0.25)

    styles = doc.styles
    styles["Normal"].font.name = "Liberation Sans"
    styles["Normal"].font.size = Pt(8.8)
    styles["Normal"].paragraph_format.space_after = Pt(4)
    for name, size in [("Title", 26), ("Heading 1", 15), ("Heading 2", 11.3), ("Heading 3", 9.8)]:
        styles[name].font.name = "Liberation Sans"
        styles[name].font.size = Pt(size)
        if name.startswith("Heading"):
            styles[name].font.color.rgb = RGBColor.from_string(NAVY)

    header = sec.header.paragraphs[0]
    header.text = "SUPERR SELECTOR SEASON 2  |  ROUND 1  |  AUDIT EDITION"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for run in header.runs:
        run.font.name = "Liberation Sans"
        run.font.size = Pt(7.3)
        run.font.color.rgb = RGBColor.from_string(GREY)
    footer = sec.footer.paragraphs[0]
    _add_page_number(footer)
    for run in footer.runs:
        run.font.name = "Liberation Sans"
        run.font.size = Pt(7.5)
        run.font.color.rgb = RGBColor.from_string(GREY)

    # PAGE 1 - Cover and executive summary
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(42)
    r = p.add_run("SUPERR SELECTOR")
    r.bold = True; r.font.name = "Liberation Sans"; r.font.size = Pt(28); r.font.color.rgb = RGBColor.from_string(NAVY)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run("SEASON 2  |  ROUND 1")
    r.bold = True; r.font.name = "Liberation Sans"; r.font.size = Pt(17); r.font.color.rgb = RGBColor.from_string(GOLD)
    p = doc.add_paragraph("Most Reliable Batters and Bowlers Under Pressure")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size = Pt(13); p.runs[0].font.italic = True
    p = doc.add_paragraph("Forensic data audit • Transparent scoring • Rajasthan Royals 2027 strategy")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size = Pt(9); p.runs[0].font.color.rgb = RGBColor.from_string(GREY)
    p = doc.add_paragraph("Prepared 13 November 2026")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size = Pt(8.5)

    _heading(doc, "Executive summary", 1)
    _p(doc, "This report presents two independently calculated ranking populations. The official Round 1 submission tables use the IPL (2022–2026) and T20I population specified in the brief. A second expanded research analysis adds the supplied Emerging Teams and Rising Stars T20 competitions. Pressure is operationalised through early-innings collapse and the death phase. Players are compared with context-matched peers and with their own ordinary baseline; small samples are shrunk toward peer rates and match-to-match consistency is included.")
    _table(doc, ["Decision item", "Primary result"], [
        ["Eligible player pool", f"96 batters; 156 bowlers"],
        ["Primary data scope", "IPL 2022–2026 + T20 Internationals"],
        ["Delivery-level sample", f"{scope['selected_counts']['ball_by_ball_rows']:,} records across {scope['selected_counts']['matches_with_ball_by_ball']:,} matches"],
        ["Pressure opportunities", f"{press['combined_pressure_records_without_double_counting']:,} unique delivery records"],
        ["Primary score", "0–100 relative composite; not a probability"],
        ["Expanded strategy", "Retrospective RR 2026 squad audit + conditional IPL 2027 auction plan"],
    ], widths=[2.1, 4.7], font=8.5)
    _p(doc, "Dual-scope decision: the IPL + T20I tables remain the official Round 1 submission rankings because they follow the competition population specified in the brief. The expanded IPL + T20I + Emerging Teams + Rising Stars analysis is presented as a major, separately rerun research result. It identifies the effect of broader competition coverage without silently changing the official submission population.", bold_prefix="Dual-scope decision:", size=8.7)
    _p(doc, "Interpret the order as the output of one explicit model, not a claim that a player is universally the best under every pressure situation. The sensitivity section shows how rankings move when reasonable modelling choices change.", size=8.7, color=GREY)

    # PAGE 2 - Scope
    _page(doc)
    _heading(doc, "1. Dataset scope and coverage", 1)
    _p(doc, "The supplied source pack contains six CSV files. The primary selection rule retains competitions whose format is T20I or whose competition name exactly matches IPL 20XX. The filter is applied from competition metadata and match IDs before any context, pressure, baseline or ranking calculation.")
    selected = scope["selected_counts"]
    scope_rows = [
        ["All source match rows", f"{scope['source_counts']['matches_rows']:,}"],
        ["All source ball-by-ball rows", f"{scope['source_counts']['ball_by_ball_rows']:,}"],
        ["Primary-scope match rows", f"{selected['matches']:,}"],
        ["Primary-scope matches with ball data", f"{selected['matches_with_ball_by_ball']:,}"],
        ["Primary-scope matches without ball data", f"{selected['matches_without_ball_by_ball']:,}"],
        ["Primary-scope deliveries", f"{selected['ball_by_ball_rows']:,}"],
        ["Primary-scope competition IDs", f"{selected['competition_ids']:,} (5 IPL; 131 T20I with matches)"],
        ["IPL matches, 2022–2026", "371 total; 367 with ball-by-ball"],
        ["T20I matches", "482 total; 470 with ball-by-ball"],
        ["Additional expanded-scope T20 competitions", "2 competitions; 30 matches"],
        ["Date range in primary matches", "22 Jan 2022 – 1 Nov 2026"],
    ]
    _table(doc, ["Coverage item", "Observed value"], scope_rows, widths=[3.0, 3.8], font=8.1)
    _p(doc, "Sixteen primary-scope matches have no corresponding delivery rows (4 IPL and 12 T20I). They remain counted in match coverage but cannot contribute ball-by-ball metrics. The 141-row competition metadata file includes 134 T20I competition entries; 131 T20I competition IDs are represented in the selected matches.", size=8.2)
    _p(doc, "The two additional T20 competitions are Mens T20 Emerging Teams Asia Cup 2024 (15 matches) and Asia Cup Rising Stars 2025 (15 matches). All 30 matches have ball-by-ball records, adding 6,985 delivery rows to the expanded run. They are valid supplied T20 data; their separate treatment is a scope decision, not a data-quality rejection.", size=8.2)
    _heading(doc, "Expanded-scope sensitivity: effect on the Top 10", 2)
    _table(doc, ["Measure", "Official: IPL + T20I", "Expanded research: all supplied T20 + T20I"], [
        ["Matches / matches with ball data", f"{scope_comparison['primary_scope']['matches']:,} / {scope_comparison['primary_scope']['matches_with_ball_by_ball']:,}", f"{scope_comparison['expanded_scope']['matches']:,} / {scope_comparison['expanded_scope']['matches_with_ball_by_ball']:,}"],
        ["Delivery records", f"{scope_comparison['primary_scope']['ball_by_ball_rows']:,}", f"{scope_comparison['expanded_scope']['ball_by_ball_rows']:,}"],
        ["Batter Top 10 overlap", "Primary reference", scope_comparison['batters']['top10_overlap_out_of_10']],
        ["Bowler Top 10 overlap", "Primary reference", scope_comparison['bowlers']['top10_overlap_out_of_10']],
    ], widths=[2.2, 2.3, 2.3], font=7.6, header_font=7.6)
    _p(doc, "Batter changes: " + "; ".join(
        [f"{name} enters" for name in scope_comparison['batters']['players_entering_expanded_top10']] +
        [f"{name} leaves" for name in scope_comparison['batters']['players_leaving_primary_top10']]
    ) + ". Bowler changes: " + "; ".join(
        [f"{name} enters" for name in scope_comparison['bowlers']['players_entering_expanded_top10']] +
        [f"{name} leaves" for name in scope_comparison['bowlers']['players_leaving_primary_top10']]
    ) + ". The shared players can also move in rank and score; the expanded run recomputes the peer-relative model and eligible candidate pool over the larger population. The expanded lists are a separately calculated research result; the official IPL + T20I ranking CSVs remain unchanged for the Unstop submission.", size=8.0)
    _p(doc, "Interpretation: this comparison demonstrates that competition selection changes the candidate pool, peer population and final ranks. It does not establish that the expanded ranking is inherently more accurate. The official Unstop tables remain IPL + T20I; the expanded tables are a substantial additional research result and are shown separately on the next page.", size=8.0, color=GREY)

    # PAGE 3 - Expanded research rankings
    _page(doc)
    _heading(doc, "2. Expanded research ranking: Emerging Teams + Rising Stars", 1)
    _p(doc, "This is the separately rerun expanded population: IPL 2022–2026, T20 Internationals, Men's T20 Emerging Teams Asia Cup 2024 and Asia Cup Rising Stars 2025. The two additional competitions contribute 30 matches and 6,985 deliveries. The expanded peer baselines, eligible candidate pool, performance components and consistency components are recalculated; these are not primary-scope scores copied into a larger table.")
    _heading(doc, "Expanded Top 10 batters", 2)
    _table(doc, ["Rank", "Player", "Expanded index"], [
        [int(r["rank"]), r["player_name"], _fmt_num(r["reliability_score"])]
        for _, r in expanded_bat.iterrows()
    ], widths=[0.75, 3.9, 1.4], font=8.2)
    _heading(doc, "Expanded Top 10 bowlers", 2)
    _table(doc, ["Rank", "Player", "Expanded index"], [
        [int(r["rank"]), r["player_name"], _fmt_num(r["reliability_score"])]
        for _, r in expanded_bowl.iterrows()
    ], widths=[0.75, 3.9, 1.4], font=8.2)
    _p(doc, "Interpretation and use: these expanded rankings are the primary result for the project's broader research question, while the IPL + T20I rankings remain the official Round 1 submission result. Do not mix scores across scopes: each score is relative to its own recalculated candidate and peer population. A rank or score change after expansion reflects a changed reference population, not necessarily a change in the player's underlying ability.", size=8.4)

    # PAGE 4 - Integrity
    _page(doc)
    _heading(doc, "2. Data integrity and field-level decisions", 1)
    _table(doc, ["Check", "Observed result", "Treatment"], [
        ["Delivery ordering", f"{ctx['delivery_records']:,} rows; {ctx['duplicate_delivery_numbers']} duplicate delivery numbers; {ctx['innings_groups_with_sequence_gaps']} innings with gaps", "Pass: use innings_ball_num for ordering"],
        ["Innings sequence starts", f"{ctx['innings_groups_not_starting_at_ball_1']} groups not starting at ball 1", "Pass"],
        ["Wicket state", "Monotonic; max 9 wickets before a delivery", "Count wickets before the current ball"],
        ["Regular / additional innings", f"{ctx['regular_innings_records']:,} regular; {ctx['additional_innings_records']} additional", "Innings 3+ retained but not pressure-rated"],
        ["Batting balls faced", f"{batt_audit['source_coverage']['balls_faced_records_primary_rule']:,}", "Exclude wides; include Overstep; retain 1 Penalty row"],
        ["Wide / Overstep records", f"{batt_audit['source_coverage']['wide_records']:,} / {batt_audit['source_coverage']['overstep_records_counted_as_faced']:,}", "Wide excluded; Overstep counted as faced / excluded from bowler candidate legal balls"],
        ["Boundary flag anomalies", "20 four-run rows and 3 six-run rows have no matching boundary flag", "Use supplied flags; do not infer missing flags"],
        ["Dismissal attribution", f"{batt_audit['dismissal_attribution_checks']['is_wicket_records']:,} wicket rows; {batt_audit['dismissal_attribution_checks']['dismissed_player_id_missing']} missing dismissed_player_id", "Attribute by dismissed_player_id; do not guess missing ID"],
    ], widths=[1.35, 2.7, 2.75], font=7.3, header_font=7.6)
    _heading(doc, "Why the run fields are labelled conservatively", 2)
    _p(doc, f"The source `runs` column sums to {batt_audit['source_coverage']['recorded_runs_sum']:,} in the primary dataset. However, the extras fields do not provide complete run amounts: for example, {bowl_audit['source_checks']['extras_breakdown']['byes']['records']:,} byes records and {bowl_audit['source_checks']['extras_breakdown']['legbyes']['records']:,} leg-byes records have zero in the source runs field. Consequently, batting rates use the label recorded_runs and bowling economy / true dot-ball rates are not produced.")
    _p(doc, f"Of {bowl_audit['source_checks']['all_wicket_records']:,} wicket records, {bowl_audit['source_checks']['bowler_credited_wicket_records']:,} are treated as bowler-creditable (Bowled, Caught, LBW, Stump, Hit Wicket); {bowl_audit['source_checks']['non_bowler_wicket_records']:,} are not. Run-outs are not credited to bowlers. The 25 bowler-creditable stumpings on wides remain credited, as dismissal credit is separate from ball legality.")

    # PAGE 4 - Pressure
    _page(doc)
    _heading(doc, "3. Pressure definition", 1)
    _heading(doc, "3.1 Early-collapse pressure", 2)
    _p(doc, "An innings enters early-collapse pressure if at least five wickets have fallen by the end of the first 50% of its allocated length. Pressure begins on the delivery after the fifth wicket falls. The fifth-wicket delivery itself is not counted as post-collapse pressure. In a standard 20-over innings, the cutoff is the end of over 10.")
    _heading(doc, "3.2 Death-phase pressure", 2)
    _p(doc, "The final 25% of allocated innings length is treated as the death phase. In a standard 20-over innings this is overs 16–20. The rule applies regardless of match closeness or wickets in hand. Shortened-innings boundaries scale with the allocated innings length, rounded to full overs.")
    _heading(doc, "3.3 Role-specific pressure", 2)
    _p(doc, "Batters are ranked in the de-duplicated union: early-collapse OR death phase. Bowlers are ranked on death-over context only. A batting-side collapse does not automatically mean the bowling side is under pressure; early-collapse bowling is retained as supporting analysis, not used as the bowler's primary pressure category.")
    _table(doc, ["Pressure event", "Delivery records"], [
        ["Early-collapse", f"{press['early_collapse_pressure_records']:,}"],
        ["Death phase", f"{press['death_phase_pressure_records']:,}"],
        ["Overlap", f"{press['overlapping_pressure_records']:,}"],
        ["Unique combined pressure", f"{press['combined_pressure_records_without_double_counting']:,}"],
        ["Early-collapse innings", f"{press['early_collapse_innings']:,} across {press['matches_with_early_collapse']:,} matches"],
    ], widths=[3.2, 3.6], font=8.4)
    _p(doc, "The rule is intentionally observable and reproducible. It does not claim to capture every pressure state. The source fields cannot reliably reconstruct required run rate, target, full team totals or match closeness; those unobservable states are not fabricated or included.", size=8.5)

    # PAGE 5 - metrics and baselines
    _page(doc)
    _heading(doc, "4. Metrics and peer baselines", 1)
    _heading(doc, "4.1 Batting metrics", 2)
    _table(doc, ["Metric", "Calculation", "Direction / weight"], [
        ["Recorded runs rate", "recorded_runs / balls_faced × 100", "Higher is better · 50%"],
        ["Dismissal rate", "dismissals attributed by dismissed_player_id / balls_faced × 100", "Lower is better · 30%"],
        ["Boundary rate", "(is_four + is_six flags) / balls_faced × 100", "Higher is better · 20%"],
    ], widths=[1.55, 3.8, 1.45], font=7.6)
    _heading(doc, "4.2 Bowling metrics", 2)
    _table(doc, ["Metric", "Calculation", "Direction / weight"], [
        ["Bowler wicket rate", "Bowler-creditable wickets / candidate legal balls × 100", "Higher is better · 60%"],
        ["Flagged boundary rate conceded", "(four + six flags) conceded / candidate legal balls × 100", "Lower is better · 40%"],
    ], widths=[1.65, 3.7, 1.45], font=7.6)
    _p(doc, "Candidate legal bowling balls exclude `wide` and `Overstep`; the single Penalty-coded record is retained in the primary denominator because its event semantics are not documented. A penalty-excluded variant differs by one ball. Economy rate and true dot-ball rate are deliberately omitted because the extras fields do not support them.", size=8.2)
    _heading(doc, "4.3 Peer comparison", 2)
    _bullet(doc, "Each player is compared with a leave-one-player-out, opportunity-weighted peer rate; the subject player is excluded from the comparator.")
    _bullet(doc, "Peer-context hierarchy: competition + innings + phase; then format + season + innings + phase; then format + innings + phase.")
    _bullet(doc, "Competition-level peer support requires at least 300 other-player opportunities and 8 other players; broader fallback requires at least 50 opportunities and 3 players.")
    _bullet(doc, "Phase boundaries use the same proportional allocation rule: powerplay = first 30%, death = final 25%, middle = intervening overs. This prevents comparing raw powerplay and death rates as though they were the same context.")
    _p(doc, f"Baseline coverage is {baseline['batting_context_coverage']['peer_coverage_pct']:.2f}% for batter context rows and {baseline['bowling_context_coverage']['peer_coverage_pct']:.2f}% for bowler context rows. Unmatched rows are not assigned invented peer rates.", size=8.2)

    # PAGE 6 - score/eligibility
    _page(doc)
    _heading(doc, "5. Reliability adjustment and scoring", 1)
    _heading(doc, "5.1 Shrinkage", 2)
    _p(doc, "For a player with observed numerator x, opportunity count n and a matched peer rate r (per 100 opportunities), the sample-adjusted rate is ((x + k × r / 100) / (n + k)) × 100. The primary player-level prior k is 60 opportunities; the sensitivity grid tests 30 and 100. Each player-match rate is similarly shrunk toward its matched peer using 12 prior opportunities.")
    _p(doc, "This is a transparent fixed-prior shrinkage method, not a fitted empirical-Bayes model. Its purpose is to reduce extreme rates from small samples while retaining the observed signal.")
    _heading(doc, "5.2 Composite score", 2)
    _table(doc, ["Component", "Construction"], [
        ["Performance (70%)", "For each metric: 50% percentile of sample-adjusted pressure level vs peer + 50% percentile of pressure uplift vs the player's ordinary peer-relative standing; then apply metric weights."],
        ["Consistency (30%)", "For each metric: 50% positive adjusted-match share percentile + 30% median adjusted match-performance percentile + 20% inverse dispersion percentile; then apply metric weights."],
        ["Final index", "0.70 × performance component + 0.30 × consistency component; relative percentile composite on a 0–100 scale."],
    ], widths=[1.55, 5.25], font=7.7)
    _heading(doc, "5.3 Eligibility before ranking", 2)
    _table(doc, ["Role", "Pressure sample", "Ordinary comparison", "Peer coverage"], [
        ["Batter", "≥100 combined-pressure balls and ≥10 pressure matches", "≥100 ordinary balls and ≥10 ordinary matches", "≥80% for all required metrics"],
        ["Bowler", "≥60 death-over candidate legal balls and ≥10 death matches", "≥60 ordinary candidate legal balls and ≥10 ordinary matches", "≥80% for all required metrics"],
    ], widths=[0.8, 2.05, 2.2, 1.75], font=7.3)
    _p(doc, f"These rules leave {rank_audit['batting']['players_with_all_metrics']} eligible batters and {rank_audit['bowling']['players_with_all_metrics']} eligible bowlers. All 20 selected players have 100% baseline coverage in the required metrics. The score is an ordering aid; 87.62 does not mean an 87.62% probability of succeeding under pressure.", size=8.4)

    # PAGE 7 - batters
    _page(doc)
    _heading(doc, "6. Primary top 10 — batters under pressure", 1)
    rows = []
    for _, r in bat.iterrows():
        rows.append([
            int(r["rank"]), r["player_name"], _fmt_num(r["reliability_score"]),
            f"{int(r['pressure_opportunities']):,}", int(r["pressure_matches"]),
            f"{r['positive_match_share_pct']:.1f}%", f"+{r['mean_uplift_vs_ordinary_pct_points']:.1f} pp"
        ])
    _table(doc, ["#", "Player", "Score", "Pressure balls", "Matches", "Positive matches", "Mean uplift"], rows,
           widths=[0.35, 1.55, 0.7, 0.85, 0.55, 1.0, 1.1], font=7.5, header_font=7.3)
    _heading(doc, "How to read the list", 2)
    _p(doc, "Najibullah Zadran leads with 127 combined-pressure balls across 12 matches. Sikandar Raza has a larger sample (231 balls, 19 matches) and a slightly higher performance component, but a lower consistency component; the final score is a 70/30 blend. Naman Dhir is third with 211 balls across 24 matches. The rank is driven by the declared composite, not by reputation or a manual override.")
    _p(doc, "The closeness of scores matters: Rinku Singh (81.71) and Tristan Stubbs (80.79) are separated by less than one point. The model does not justify treating that gap as a decisive cricketing difference. Use sample volume and role fit alongside the index.")
    _heading(doc, "Candidate evidence", 2)
    _p(doc, "The table shows opportunity volume, distinct pressure matches, the share of baseline-supported matches with positive peer-adjusted results, and mean pressure-versus-ordinary uplift. A positive share is not the same as a win rate; it is a share of match-level metric observations with a positive adjusted peer-relative result.", size=8.1)

    # PAGE 8 - bowlers
    _page(doc)
    _heading(doc, "7. Primary top 10 — bowlers under pressure", 1)
    rows = []
    for _, r in bowl.iterrows():
        rows.append([
            int(r["rank"]), r["player_name"], _fmt_num(r["reliability_score"]),
            f"{int(r['pressure_opportunities']):,}", int(r["pressure_matches"]),
            f"{r['positive_match_share_pct']:.1f}%", f"+{r['mean_uplift_vs_ordinary_pct_points']:.1f} pp"
        ])
    _table(doc, ["#", "Player", "Score", "Death balls", "Matches", "Positive matches", "Mean uplift"], rows,
           widths=[0.35, 1.55, 0.7, 0.85, 0.55, 1.0, 1.1], font=7.5, header_font=7.3)
    _heading(doc, "How to read the list", 2)
    _p(doc, "Sunil Narine leads with 216 death-over candidate legal balls across 35 matches. Rashid Khan has the largest sample among the top three (540 balls across 80 matches), while Hasan Mahmud ranks second with 108 balls across 12 matches. The difference is based on peer-adjusted wicket and boundary-flag rates plus match consistency.")
    _p(doc, "The bowling list is more sensitive to metric choice than the batting list. Under equal metric weights, only 7 of the primary 10 bowlers remain. This is a material limitation and should be disclosed in any judge presentation, not hidden behind the main score.")
    _p(doc, "Boundary flags are used as supplied. The model cannot fully reconstruct bowler-charged runs, so the bowling score is not an economy-rate ranking.", size=8.1)

    # PAGE 9 - robustness
    _page(doc)
    _heading(doc, "8. Robustness and sensitivity", 1)
    _heading(doc, "8.1 Pressure threshold", 2)
    rows = []
    for _, r in cutoff_sens.iterrows():
        rows.append([
            f"By over {int(r['collapse_cutoff_over_standard_20'])}",
            int(r["batting_candidate_count"]), int(r["bowling_candidate_count"]),
            f"{int(r['batting_top10_overlap_primary'])}/10", f"{int(r['bowling_top10_overlap_primary'])}/10"
        ])
    _table(doc, ["Collapse cutoff", "Eligible batters", "Eligible bowlers", "Batter overlap", "Bowler overlap"], rows,
           widths=[1.25, 1.25, 1.25, 1.45, 1.45], font=8)
    _p(doc, "At an 8-over collapse cutoff, 9/10 batter and 10/10 bowler places overlap the primary list. At 12 overs, overlap falls to 7/10 and 9/10. The batter ranking is therefore more dependent on the early-collapse boundary than the bowler ranking.", size=8.2)
    _heading(doc, "8.2 Prior and sample-threshold sensitivity", 2)
    # Keep only a compact top set of scenarios for legibility.
    choose = prior_sens[prior_sens["scenario"].isin([
        "prior30_bat100_bowl60_matches10", "prior100_bat100_bowl60_matches10",
        "prior60_bat80_bowl40_matches10", "prior60_bat120_bowl80_matches10",
        "prior60_bat100_bowl60_matches8"
    ])]
    primary_names = {
        "batters": set(bat["player_name"].astype(str)),
        "bowlers": set(bowl["player_name"].astype(str)),
    }
    sens_rows = []
    for _, r in choose.iterrows():
        scenario_names = set(str(r["top10_player_names"]).split(" | "))
        overlap = len(primary_names[r["role"]].intersection(scenario_names))
        sens_rows.append([r["scenario"], r["role"], int(r["candidate_count"]), f"{overlap}/10"])
    _table(doc, ["Scenario", "Role", "Eligible candidates", "Top-10 overlap"], sens_rows,
           widths=[3.0, 0.9, 1.4, 1.5], font=7.4)
    _heading(doc, "8.3 Metric-weight sensitivity", 2)
    rows = [[r["scenario"], f"{int(r['batter_top10_overlap_with_primary'])}/10", f"{int(r['bowler_top10_overlap_with_primary'])}/10"] for _, r in metric_sens.iterrows()]
    _table(doc, ["Weight scenario", "Batter overlap", "Bowler overlap"], rows,
           widths=[3.8, 1.5, 1.5], font=7.5)
    _p(doc, "The selected weights are reasoned modelling choices, not objectively optimal constants. If a judge prefers different weights, the alternative lists in `metric_weight_sensitivity.json` show the exact player-level results. Under a 120/80 opportunity eligibility rule, the batter top-10 overlap falls to 7/10; with an 8-match rule, the bowler overlap falls to 7/10.", size=8.1)
    _p(doc, "Shortened-innings audit: 134 second-innings delivery rows across two matches inherit the first-innings revised allocation when the second-innings field is blank and the observed second innings reaches the same over cap. Disabling this inheritance changes the unique pressure count from 50,874 to 50,880 but leaves all 20 top-10 names unchanged.", size=8.1)

    # PAGE 10 - RR squad
    _page(doc)
    _heading(doc, "9. Rajasthan Royals: 2026 squad and role audit", 1)
    _p(doc, "This section applies the Round 1 pressure-performance findings to Rajasthan Royals' IPL 2027 squad requirements, connecting the statistical rankings with role suitability and conditional recruitment decisions. It uses the supplied IPL 2026 squad mapping and player appearances, then checks the role structure against Rajasthan Royals' official 2026 squad page. The analysis is retrospective: it does not assume the 2026 squad will remain intact for IPL 2027.")
    _table(doc, ["2026 RR batting output", "Matches", "Recorded runs", "Balls faced", "Source cross-check"], [
        ["Vaibhav Sooryavanshi", 16, 776, 327, "Official RR season page: 776"],
        ["Dhruv Jurel", 16, 515, 333, "Official RR season page: 515"],
        ["Yashasvi Jaiswal", 16, 427, 280, "Official RR season page: 427"],
        ["Donovan Ferreira", 15, 317, 177, "Official RR squad page: 317"],
        ["Riyan Parag", 14, 309, 196, "Official RR squad page: 309"],
        ["Ravindra Jadeja", 14, 266, 197, "Official RR squad page: 266"],
    ], widths=[1.65, 0.65, 0.85, 0.85, 2.8], font=7.4)
    _p(doc, "The supplied ball-by-ball `runs` totals for these six 2026 RR batters match the published figures on the official RR squad page. This is a targeted cross-check, not proof that every player and every extras record in the full dataset is error-free.", size=8.1)
    _heading(doc, "Observed bowling deployment in 2026", 2)
    _table(doc, ["Bowler", "Matches", "PP legal balls", "Middle legal balls", "Death legal balls", "Credited wkts"], [
        ["Jofra Archer", 16, 204, 48, 108, 25],
        ["Brijesh Sharma", 13, 73, 108, 96, 14],
        ["Nandre Burger", 13, 156, 54, 51, 14],
        ["Ravi Bishnoi", 9, 12, 120, 24, 11],
        ["Ravindra Jadeja", 14, 0, 198, 0, 10],
        ["Yash Punja", 8, 6, 156, 18, 9],
        ["Sandeep Sharma", 6, 48, 18, 52, 5],
        ["Tushar Deshpande", 7, 48, 42, 48, 4],
    ], widths=[1.2, 0.55, 1.05, 1.15, 1.1, 1.0], font=7.1)
    _p(doc, "The deployment data shows multiple death-over options (Archer, Brijesh, Nandre, Sandeep and Tushar) and substantial middle-over spin from Jadeja, Bishnoi and Yash Punja. Therefore, a blanket claim that RR lacks death bowling or spin is not supported by its 2026 usage. The more defensible question is which of these players remain retained and available, and whether the role mix is resilient to absence/injury.", size=8.0)

    # PAGE 11 - Ranked batters and RR fit
    _page(doc)
    _heading(doc, "10. RR fit review — ranked batters", 1)
    _p(doc, "The statistical list and recruitment shortlist are different things. The table below reviews each batter on role fit against the 2026 RR structure. Franchise labels refer to published 2026 squad information, updated where a 2027 trade was officially confirmed by 13 November 2026. They do not establish retention, release, registration or availability for the auction.", size=8.3)
    bat_fit = rr_fit[rr_fit["role"] == "Batter"].sort_values("rank")
    bat_fit_rows = []
    short_bat_view = {
        "Najibullah Zadran": "Watchlist only; consider if RR lose a finisher.",
        "Sikandar Raza": "Flexible overseas all-rounder; overlaps current RR options.",
        "Naman Dhir": "Useful Indian middle-order depth if released by MI.",
        "Rinku Singh": "Strong Indian finisher fit; KKR/availability first.",
        "Tristan Stubbs": "Quality, but overlaps overseas middle-order/keeper cover.",
        "Nurul Hasan": "Low priority: RR already has wicketkeeping cover.",
        "Rishabh Pant": "Not practical: DC trade confirmed; Jurel is established.",
        "Ramandeep Singh": "Useful Indian lower-order utility if released.",
        "Babar Azam": "Do not shortlist; IPL registration/eligibility unverified.",
        "Glenn Phillips": "Versatile, but overseas middle-order role is covered.",
    }
    for _, r in bat_fit.iterrows():
        bat_fit_rows.append([int(r["rank"]), r["player_name"], f"{r['nationality_group']} · {r['role_profile']}", r["2026_team_status"], short_bat_view[r["player_name"]]])
    _table(doc, ["#", "Player", "Profile", "2026 squad / trade status", "RR view"], bat_fit_rows,
           widths=[0.3, 1.05, 1.45, 1.75, 2.25], font=7.0, header_font=7.0)
    _p(doc, "Interpretation: the most attractive role profiles are Indian middle-order/finishing options (Naman Dhir, Rinku Singh and Ramandeep Singh) because they can address depth without consuming an overseas slot. That is a conditional role-fit assessment only: none is an available target until the official 2027 list confirms release and registration. The top two statistical ranks are not automatically the best recruitment fits.", size=8.2)

    # PAGE 12 - Ranked bowlers and RR fit
    _page(doc)
    _heading(doc, "11. RR fit review — ranked bowlers", 1)
    _p(doc, "The bowler list is likewise screened for role complementarity, not merely score. RR's 2026 deployment already included pace across the powerplay and death, plus middle-over spin. A top-10 bowler should be considered only if the retained squad leaves a specific phase or skill gap.", size=8.3)
    bowl_fit = rr_fit[rr_fit["role"] == "Bowler"].sort_values("rank")
    bowl_fit_rows = []
    short_bowl_view = {
        "Sunil Narine": "Elite, but spin/all-rounder overlap; KKR status.",
        "Hasan Mahmud": "Conditional overseas pace option; verify registration/fitness.",
        "Rashid Khan": "High quality, but spin overlap and GT status/price.",
        "Akeal Hosein": "Left-arm spin overlap with current RR middle-over options.",
        "Dasun Shanaka": "RR 2026 member; assess retention and role-use.",
        "Riley Meredith": "Pace depth only after fitness and release checks.",
        "Adam Zampa": "Spin contingency only if current depth changes.",
        "Nandre Burger": "RR 2026 member; assess retention and fitness.",
        "Ben Dwarshuis": "Left-arm seam cover if released; overseas slot needed.",
        "Rahul Chahar": "Indian spin backup only if attrition creates a gap.",
    }
    for _, r in bowl_fit.iterrows():
        bowl_fit_rows.append([int(r["rank"]), r["player_name"], f"{r['nationality_group']} · {r['role_profile']}", r["2026_team_status"], short_bowl_view[r["player_name"]]])
    _table(doc, ["#", "Player", "Profile", "2026 squad / trade status", "RR view"], bowl_fit_rows,
           widths=[0.3, 1.05, 1.45, 1.75, 2.25], font=7.0, header_font=7.0)
    _p(doc, "For RR, retaining a functional phase-balanced core may be more valuable than buying another highly ranked overseas name. Dasun Shanaka and Nandre Burger are already in the 2026 RR group; they are retention/role decisions, not external targets. Hasan Mahmud, Riley Meredith and other players absent from the reviewed 2026 squad list are not assumed to be registered or available.", size=8.2)

    # PAGE 13 - Auction strategy
    _page(doc)
    _heading(doc, "12. IPL 2027 auction intelligence and conditional RR plan", 1)
    _p(doc, "As at 12 November 2026, the retention deadline is reported as 17 November 2026. Cricbuzz reports a mini-auction scheduled for 16 December 2026 in Goa, registration closing 23 November, and the final auction register expected on 3 December. Treat the auction date and venue as reported schedule information pending formal BCCI confirmation; player availability is not yet final.")
    _table(doc, ["Planning checkpoint", "Reported date / status", "Practical implication"], [
        ["RR retention/release submission", "17 Nov 2026", "Do not finalise team gap or purse before this list"],
        ["Player registration window closes", "23 Nov 2026", "Registration still does not prove a player is retained/released by a franchise"],
        ["Final auction register", "3 Dec 2026 (reported)", "Use this as the definitive purchasable-player universe"],
        ["Mini-auction", "16 Dec 2026, Goa (reported)", "Prepare role tiers and price ceilings, subject to confirmed register"],
        ["2027 total salary cap", "₹157 crore", "This is not RR's remaining auction purse"],
    ], widths=[1.75, 1.6, 3.05], font=7.4)
    _heading(doc, "Conditional recruitment priorities", 2)
    _bullet(doc, "Priority 1 — protect a reliable death-overs pace core. Retain/replace based on actual availability among the 2026 death-usage group; only seek an additional specialist if retentions, injury/fitness or role duplication create a genuine gap.")
    _bullet(doc, "Priority 2 — preserve middle-over wicket-taking options. Jadeja, Bishnoi and Yash Punja carried meaningful 2026 middle-over workloads. A new spinner is a succession/contingency decision, not an automatic gap.")
    _bullet(doc, "Priority 3 — assess finishing depth after retentions. Ferreira, Hetmyer and Shubham Dubey all recorded 2026 middle/death usage; review role clarity and Indian/overseas balance before bidding for another finisher.")
    _bullet(doc, "Priority 4 — maintain an Indian pace succession option if the 2027 retained group leaves limited domestic fast-bowling cover. Set reserve prices only after the released-player list and purse are confirmed.")
    _p(doc, "The 2027 salary-cap rule states ₹157 crore for the total salary cap. It must not be presented as the franchise's auction purse: the remaining purse depends on salaries retained, releases, trades and applicable rules. The final team-wise auction balance should be recalculated from the confirmed retention list and contracts.", size=8.1)
    _p(doc, "No named player is labelled a confirmed RR target or an available auction player in this report. The statistical top-10 lists are performance evidence, not availability evidence. Existing franchise contract, registration, overseas-player rules, final auction register, fitness, price and squad-slot constraints must all be verified before naming a target.", size=8.1, color=GREY)

    # PAGE 14 - validation and judge questions
    _page(doc)
    _heading(doc, "13. Technical validation and reproducibility", 1)
    test_result_path = out / "test_results.txt"
    test_result_text = test_result_path.read_text(encoding="utf-8") if test_result_path.exists() else ""
    import re
    test_match = re.search(r"(\d+) passed", test_result_text)
    test_count = int(test_match.group(1)) if test_match else 0
    _p(doc, f"The project is implemented as separate Python modules, with a reproducible command-line pipeline and unit tests. The final recorded automated test run passed {test_count} tests. The scope-comparison tests check stable-ID matching, overlap and entry/exit identification, duplicate detection, ten-player requirements and excluded-competition ball-by-ball coverage.")
    _heading(doc, "Regression checks covered", 2)
    for item in [
        "The delivery taking the fifth wicket is not treated as the first post-collapse pressure delivery; the next delivery is.",
        "Death phase uses allocated innings length; a standard 20-over innings starts death pressure in over 16.",
        "Overlapping early-collapse/death records are counted once in the combined batting pressure set.",
        "Run-outs and other non-bowler dismissals do not count as bowler-creditable wickets.",
        "Wides and Overstep are excluded from candidate legal bowling balls; sample eligibility is enforced.",
        "Competition scope includes only IPL 2022+ and T20I by default; expanded T20 scope is explicit.",
        "Sensitivity options recalculate rankings; the pressure-ranking stability flag no longer silently does nothing.",
        "Primary and expanded competition-scope runs are independently executed; expanded outputs are stored separately and cannot overwrite the primary rankings.",
    ]:
        _bullet(doc, item, size=8.1)
    _heading(doc, "Reproduce from the six supplied CSVs", 2)
    _p(doc, "Place the six source CSVs in the project's `data/` folder, install the version-constrained requirements, then run:", size=8.1)
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.18)
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("python -m pip install -r requirements.txt\npython -m pytest -q\npython main.py --audit-context --audit-pressure --audit-batting --audit-bowling --audit-baselines --audit-reliability --audit-rankings --audit-pressure-ranking-stability --audit-rr-squad\npython build_supplemental_outputs.py\npython run_scope_comparison.py\npython generate_report.py")
    r.font.name = "Liberation Mono"; r.font.size = Pt(7.4); r.font.color.rgb = RGBColor.from_string(NAVY)
    _heading(doc, "Judge-ready explanations", 2)
    _bullet(doc, "Why not required run rate? The source pack does not contain complete extras/total fields; required runs and full team totals cannot be safely reconstructed.", size=7.9)
    _bullet(doc, "Why 60-opportunity prior? It is a declared shrinkage choice; 30 and 100 are tested, and the result changes modestly but not identically.", size=7.9)
    _bullet(doc, "Why death only for bowlers? Early batting collapse is pressure on the batter; it does not automatically make the bowler's task high-pressure.", size=7.9)
    _bullet(doc, "Why are weights not optimal? They encode the project's chosen balance among run output, survival, boundary scoring, wicket taking and boundary suppression; sensitivity tables disclose the consequences of alternatives.", size=7.9)

    # PAGE 15 - limits and sources
    _page(doc)
    _heading(doc, "14. Limitations, interpretation and final recommendation", 1)
    for item in [
        "The pressure model is an observable proxy, not a complete model of psychological or match-state pressure. It does not use required run rate, wickets in hand, target, or match closeness.",
        "The revised-overs field has no data dictionary. Values are interpreted as ball allocations because supplied values are multiples of six; the two narrow second-innings inheritance cases are separately audited.",
        "The source runs/extras fields are incomplete for full score reconciliation. Batting metrics are named recorded_runs; bowling economy and true dot-ball rates are excluded.",
        "Twenty-three deliveries with 4 or 6 recorded runs lack the matching boundary flag. The analysis uses flags as supplied rather than inferring missing events.",
        "Fixed priors, score weights, cutoffs and eligibility thresholds are modelling decisions. Sensitivity shows material ranking changes, particularly for bowlers under equal metric weights and batters under a 12-over cutoff.",
        "The 2027 squad, final player register and RR auction purse were not known at the 12 November 2026 cut-off. Recruitment advice is conditional and role-based.",
        "The 0–100 score is a relative composite percentile, not probability, confidence or a guarantee of future performance.",
    ]:
        _bullet(doc, item, size=8.2)
    _heading(doc, "Final recommendation", 2)
    _p(doc, "Use the strict IPL+T20I top-10 lists as the primary Round 1 submission, retain the model audit files with the report, and defend the pressure rule as a clear operational definition rather than as the only possible form of cricket pressure. Disclose the sensitivity results prominently. For RR 2027, wait for confirmed retentions and the final auction register before naming purchasable targets or calculating the available purse.", size=8.8)
    _source_bibliography(doc)
    _p(doc, "Data provenance: supplied competition and match CSVs; derived tables and audit JSONs are generated by this project's code. External sources above support only the RR squad and 2027 rules/calendar context.", size=7.6, color=GREY, italic=True)

    # APPENDIX A - Worked examples and direct player comparisons
    _page(doc)
    _heading(doc, "Appendix A. Worked scoring examples", 1)
    _p(doc, "The calculations below use the actual primary-run candidate-score rows. Rates are shown per 100 opportunities. The peer rate is leave-one-player-out and opportunity-weighted within the selected context cohort. The peer baseline estimates what comparable players produced in the same competition/innings/phase context; leaving the subject player out prevents their own performance from inflating their comparator. Shrinkage then pulls a player's observed rate toward that peer rate by the declared 60-opportunity prior, reducing extreme small-sample estimates without giving extra score points merely for having more balls. For dismissal and boundary-conceded rates, lower is better; relative advantage is direction-adjusted.", size=8.3)
    _heading(doc, "A1. Batter example — Najibullah Zadran", 2)
    _table(doc, ["Input", "Observed value"], [
        ["Recorded runs / pressure balls", "247 / 127"],
        ["Raw recorded-runs rate", "247 ÷ 127 × 100 = 194.49"],
        ["Matched peer rate", "151.41 recorded runs per 100 balls"],
        ["Prior", "60 opportunities at the peer rate"],
        ["Shrunk rate", "(247 + 60 × 1.5141) ÷ (127 + 60) × 100 = 180.67"],
        ["Adjusted relative advantage", "(180.67 ÷ 151.41 − 1) × 100 = +19.32%"],
    ], widths=[2.1, 4.7], font=8.0)
    _p(doc, "For the runs metric, Najibullah's pressure-level percentile is 92.71 and his pressure-uplift percentile is 100.00; their 50/50 average is 96.35. Applying the 50% runs weight contributes 48.18 points to the performance component. The same operation is performed for dismissals (30%) and boundary flags (20%). The resulting performance component is 91.04; consistency is 79.65; final index = 0.70 × 91.04 + 0.30 × 79.65 = 87.62.", size=8.1)
    _heading(doc, "A2. Bowler example — Hasan Mahmud", 2)
    _table(doc, ["Input", "Observed value"], [
        ["Bowler-creditable wickets / death balls", "12 / 108"],
        ["Raw wicket rate", "12 ÷ 108 × 100 = 11.11"],
        ["Matched peer wicket rate", "8.39 per 100 candidate legal balls"],
        ["Shrunk wicket rate", "(12 + 60 × 0.083904) ÷ (108 + 60) × 100 = 10.14"],
        ["Adjusted relative advantage", "(10.14 ÷ 8.39 − 1) × 100 = +20.85%"],
        ["Boundary control", "18 flags / 108 balls; peer 20.16; shrunk rate 17.91 = 11.14% lower than peer"],
    ], widths=[2.1, 4.7], font=8.0)
    _p(doc, "Hasan's wicket and boundary performance percentiles are 88.46 and 82.37. Applying the 60/40 weights gives a performance component of 86.03. His consistency component is 78.67; final index = 0.70 × 86.03 + 0.30 × 78.67 = 83.82.", size=8.1)
    _heading(doc, "A3. Why the two close comparisons resolve this way", 2)
    _table(doc, ["Comparison", "Player A", "Player B", "Model explanation"], [
        ["Batter", "Najibullah: 87.62; P 91.04; C 79.65; 127 balls / 12 matches", "Rinku: 81.71; P 86.09; C 71.47; 605 balls / 62 matches", "Rinku has much more evidence volume and a slightly higher mean peer-relative pressure result, but Najibullah scores higher on the model's combined pressure-level/uplift percentiles and match-consistency component. Sample size is an eligibility/evidence safeguard, not a bonus that automatically raises rank."],
        ["Bowler", "Hasan: 83.82; P 86.03; C 78.67; 108 balls / 12 matches", "Rashid: 82.54; P 84.29; C 78.44; 540 balls / 80 matches", "Rashid has a stronger wicket-rate peer percentile, but his boundary metric has negative pressure uplift (−2.48 pp). Hasan's more balanced wicket/boundary pressure-plus-uplift composite produces the higher performance component. Their consistency components are nearly equal."],
    ], widths=[0.65, 1.45, 1.45, 3.25], font=7.0, header_font=7.1)
    _p(doc, "These explanations describe this model's ranking logic, not a claim that the lower-ranked player is categorically inferior. The differences are conditional on the declared pressure definition, peer cohorts, weights and eligibility rules.", size=8.0, color=GREY)

    # APPENDIX B - Player-specific evidence
    _page(doc)
    _heading(doc, "Appendix B. Player-by-player evidence — batters", 1)
    _p(doc, "Each selected batter's row shows the evidence behind inclusion: pressure opportunity volume, match count, share of positive peer-adjusted match observations, average pressure standing versus peers, uplift from the player's ordinary peer-relative standing, and the two score components. Evidence-volume bands are descriptive only: higher volume = at least 250 pressure balls and 20 matches; moderate volume = at least 150 balls and 15 matches; otherwise qualified smaller sample. They are not confidence levels or probabilities.", size=8.1)
    bat_rows=[]
    for _, r in bat_profiles.sort_values("rank").iterrows():
        bat_rows.append([int(r['rank']),r['player_name'],f"{int(r['pressure_opportunities'])} / {int(r['pressure_matches'])}",f"{r['positive_match_share_pct']:.1f}%",f"{r['mean_pressure_adjusted_vs_peer_pct']:+.1f}%",f"{r['mean_uplift_vs_ordinary_pct_points']:+.1f} pp",f"{r['performance_component']:.1f} / {r['consistency_component']:.1f}",f"{r['final_index']:.2f}",r['evidence_volume_label']])
    _table(doc,["#","Batter","Pressure balls / matches","Positive match share","Pressure vs peers","Uplift vs ordinary","P / C","Index","Evidence volume"],bat_rows,widths=[0.25,0.9,0.82,0.72,0.72,0.75,0.58,0.48,0.85],font=6.7,header_font=6.6)
    _heading(doc,"How to interpret the individual profiles",2)
    for _,r in bat_profiles.sort_values('rank').iterrows():
        _bullet(doc,f"{r['player_name']} (#{int(r['rank'])}): {int(r['pressure_opportunities'])} pressure balls in {int(r['pressure_matches'])} matches; {r['positive_match_share_pct']:.1f}% positive match share; mean pressure-relative result {r['mean_pressure_adjusted_vs_peer_pct']:+.1f}%; mean uplift {r['mean_uplift_vs_ordinary_pct_points']:+.1f} pp. Performance {r['performance_component']:.2f}, consistency {r['consistency_component']:.2f}, final index {r['final_index']:.2f}. Evidence volume: {r['evidence_volume_label'].lower()}.",size=7.2)

    _page(doc)
    _heading(doc, "Appendix C. Player-by-player evidence — bowlers", 1)
    _p(doc, "Bowler opportunities are death-phase candidate legal balls. Wickets are restricted to the declared bowler-creditable dismissal types; boundary figures use supplied flags. A high pressure-versus-peer result and a high pressure-uplift result are separate signals. Bowler evidence-volume bands are descriptive only: higher volume = at least 200 death balls and 20 matches; moderate volume = at least 100 balls and 12 matches; otherwise qualified smaller sample. They are not confidence levels or probabilities.", size=8.1)
    bowl_rows=[]
    for _, r in bowl_profiles.sort_values("rank").iterrows():
        bowl_rows.append([int(r['rank']),r['player_name'],f"{int(r['pressure_opportunities'])} / {int(r['pressure_matches'])}",f"{r['positive_match_share_pct']:.1f}%",f"{r['mean_pressure_adjusted_vs_peer_pct']:+.1f}%",f"{r['mean_uplift_vs_ordinary_pct_points']:+.1f} pp",f"{r['performance_component']:.1f} / {r['consistency_component']:.1f}",f"{r['final_index']:.2f}",r['evidence_volume_label']])
    _table(doc,["#","Bowler","Death balls / matches","Positive match share","Pressure vs peers","Uplift vs ordinary","P / C","Index","Evidence volume"],bowl_rows,widths=[0.25,0.9,0.82,0.72,0.72,0.75,0.58,0.48,0.85],font=6.7,header_font=6.6)
    for _,r in bowl_profiles.sort_values('rank').iterrows():
        _bullet(doc,f"{r['player_name']} (#{int(r['rank'])}): {int(r['pressure_opportunities'])} death balls in {int(r['pressure_matches'])} matches; {r['positive_match_share_pct']:.1f}% positive match share; mean pressure-relative result {r['mean_pressure_adjusted_vs_peer_pct']:+.1f}%; mean uplift {r['mean_uplift_vs_ordinary_pct_points']:+.1f} pp. Performance {r['performance_component']:.2f}, consistency {r['consistency_component']:.2f}, final index {r['final_index']:.2f}. Evidence volume: {r['evidence_volume_label'].lower()}.",size=7.2)

    # APPENDIX D - Match-level player spotlights
    _page(doc)
    _heading(doc, "Appendix D. Match-level performance spotlights", 1)
    _p(doc, "These examples show what a selected player's pressure-labelled segment looked like in a specific match. They are illustrative evidence, not cherry-picked inputs to the ranking: each player's final score uses all eligible pressure and ordinary observations across the dataset. Runs are labelled recorded_runs because the source extras fields do not support full scorecard reconciliation.", size=8.0)
    _heading(doc, "D1. Batting pressure segments", 2)
    selected_bat = bat_spotlights[bat_spotlights['player_name'].isin(['Najibullah Zadran','Naman Dhir','Rinku Singh','Ramandeep Singh'])]
    bat_spot_rows=[]
    for _,r in selected_bat.iterrows():
        bat_spot_rows.append([r['player_name'],str(r['match_date']),r['competition'],r['opponent'],f"{int(r['pressure_recorded_runs'])} off {int(r['pressure_balls'])}",f"{int(r['flagged_fours'])}×4, {int(r['flagged_sixes'])}×6"])
    _table(doc,["Player","Date","Competition","Opponent","Recorded runs / pressure balls","Boundary flags"],bat_spot_rows,widths=[1.05,0.75,1.55,1.0,1.25,1.2],font=7.0)
    _p(doc,"Najibullah's 42 recorded runs from 13 pressure-labelled balls against Bangladesh and Rinku's 56 from 24 against Lucknow are concrete examples of high-output segments. Naman Dhir's 57 from 24 against Lucknow and Ramandeep Singh's 30 from 16 against Chennai show why their middle/lower-order role profiles are relevant to the RR appendix. These isolated innings do not replace the full-sample model.",size=7.9)
    _heading(doc,"D2. Bowling death-over segments",2)
    selected_bowl=bowl_spotlights[bowl_spotlights['player_name'].isin(['Hasan Mahmud','Rashid Khan'])]
    bowl_spot_rows=[]
    for _,r in selected_bowl.iterrows():
        bowl_spot_rows.append([r['player_name'],str(r['match_date']),r['competition'],r['opponent'],f"{int(r['bowler_credited_wickets'])} wickets / {int(r['death_candidate_legal_balls'])} legal balls",f"{int(r['flagged_fours_conceded'])} fours, {int(r['flagged_sixes_conceded'])} sixes"])
    _table(doc,["Player","Date","Competition","Opponent","Credited wickets / death balls","Boundary flags conceded"],bowl_spot_rows,widths=[1.0,0.75,1.55,1.0,1.35,1.15],font=7.0)
    _p(doc,"Hasan Mahmud's two wickets from 12 death-over candidate legal balls against England (9 March 2023) and Rashid Khan's three from 12 against Zimbabwe (31 October 2025) illustrate wicket-taking under the model's death-phase definition. These match examples are consistent with the broader sample evidence but are not the reason either player qualifies on their own.",size=7.9)

    # APPENDIX D - Sensitivity detail and boundary flag audit
    _page(doc)
    _heading(doc, "Appendix D. Sensitivity: what changes and why", 1)
    _heading(doc, "D1. Equal metric weights: exact bowling changes", 2)
    _p(doc, "The primary bowling model assigns 60% to bowler-creditable wickets and 40% to flagged boundaries conceded. Equal weighting changes this to 50/50. This increases the relative influence of boundary suppression and reduces the weight on wicket-taking; it does not mean the alternative is more correct. The 60/40 choice gives wickets the larger share because they are a direct dismissal outcome, while retaining a substantial 40% contribution for boundary control. No weights were fitted to maximise the observed Top 10.", size=8.1)
    _table(doc,["Leaves primary Top 10","Enters under equal weights"],[["Riley Meredith","Rasikh Salam"],["Adam Zampa","Sakib Hussain"],["Ben Dwarshuis","Spencer Johnson"]],widths=[3.4,3.4],font=8.2)
    _p(doc,"The batter Top 10 remains 10/10 under equal weights. Under the alternative runs-and-wickets emphasis, Babar Azam leaves and Liam Livingstone enters; under the survival-and-boundary-control scenario, Glenn Phillips leaves and Matthew Wade enters. Exact alternative lists and scores are retained in `metric_weight_sensitivity.json`.",size=8.0)
    _table(doc,["Alternative scenario","Batter change (out → in)","Bowler change (out → in)"],[
        ["Equal metric weights","None","Riley Meredith, Adam Zampa, Ben Dwarshuis → Rasikh Salam, Sakib Hussain, Spencer Johnson"],
        ["Runs / wickets emphasis","Babar Azam → Liam Livingstone","Rahul Chahar → Mitchell Starc"],
        ["Survival / boundary-control emphasis","Glenn Phillips → Matthew Wade","Riley Meredith, Adam Zampa, Ben Dwarshuis → Rasikh Salam, Sakib Hussain, Spencer Johnson"],
        ["Boundary emphasis","None","Rahul Chahar → Mitchell Starc"],
        ["Consistency heavier (40%)","None","Rahul Chahar → Rasikh Salam"],
        ["Performance heavier (80%)","None","Nandre Burger → Sakib Hussain"],
    ],widths=[1.55,2.1,3.15],font=6.7,header_font=6.8)
    _heading(doc,"D2. Missing boundary flags: deletion stress test",2)
    _p(doc,f"The source contains {boundary_sens['suspect_records']} records with recorded runs of 4 or 6 but neither boundary flag set ({boundary_sens['suspect_recorded_runs_breakdown'].get('4',0)} four-run records and {boundary_sens['suspect_recorded_runs_breakdown'].get('6',0)} six-run records). Rather than silently infer the missing flags, the sensitivity test removes all 23 records from the analytical frame and fully recalculates peer baselines, reliability and rankings. This is deliberately a conservative whole-delivery deletion test, not a correction of the source fields.",size=8.1)
    _table(doc,["Role","Top-10 membership overlap","Rank order unchanged","Interpretation"],[["Batters",f"{boundary_sens['batters']['top10_overlap']}/10",str(boundary_sens['batters']['unchanged_rank_order']),"No selected batter changed position."],["Bowlers",f"{boundary_sens['bowlers']['top10_overlap']}/10",str(boundary_sens['bowlers']['unchanged_rank_order']),"No selected bowler changed position."]],widths=[0.9,1.5,1.35,3.05],font=8.0)
    _p(doc,"Result: the primary Top 10 names and rank order are unchanged for both roles. This supports robustness to these 23 suspect rows, but it does not establish that every boundary flag in the dataset is correct.",size=8.1)
    _heading(doc,"D3. Weight and cutoff sensitivity",2)
    _p(doc,"Equal metric weights retain 7/10 bowlers; the pressure-threshold alternatives retain 9/10 batters and 10/10 bowlers at an 8-over collapse cutoff, and 7/10 batters and 9/10 bowlers at 12 overs. These are material modelling sensitivities. The primary model is selected for interpretability and cricketing logic, not because it maximises overlap.",size=8.1)
    chart_path=out/"charts"/"pressure_cutoff_top10_overlap.png"
    if chart_path.exists():
        doc.add_picture(str(chart_path),width=Inches(4.6))
        cap=doc.add_paragraph("Figure D1. Top-10 overlap under alternative collapse cut-offs. The chart shows how many primary-list players remain when the early-collapse boundary moves; it does not show score quality or statistical significance.")
        cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
        for rrn in cap.runs: rrn.font.size=Pt(7.3); rrn.italic=True

    # APPENDIX E - RR role depth and decision table
    _page(doc)
    _heading(doc,"Appendix E. Rajasthan Royals role-depth matrix",1)
    _p(doc,"The matrix is a retrospective reading of the supplied IPL 2026 RR squad and observed phase usage. 'First choice', 'backup', 'injury cover' and 'successor watch' are planning labels based on observed usage and squad mapping; they are not an official 2027 depth chart, a fitness report or a retention prediction.",size=8.0)
    role_rows=[]
    for _,r in role_depth.iterrows():
        role_rows.append([r['role'],r['first_choice_2026'],r['backup_2026'],r['injury_cover_2026'],r['successor_watch']])
    _table(doc,["Role","First choice (2026 usage)","Backup","Injury cover","Successor watch"],role_rows,widths=[1.1,1.45,1.25,1.35,1.35],font=6.5,header_font=6.5)
    _heading(doc,"E1. What the player rankings mean for RR",2)
    _table(doc,["Player","Role-based reason","RR decision logic"],[
        ["Rinku Singh","Indian finisher profile; 605 pressure balls across 62 matches in the ranking dataset; index 81.71.","Potentially valuable because an Indian finisher preserves an overseas slot. Only assess if KKR releases him and the auction register confirms eligibility; price and role vacancy still matter."],
        ["Naman Dhir","Indian middle-order/utility profile; 211 pressure balls across 24 matches; index 82.69.","Could strengthen domestic middle-order depth behind/alongside Jurel and Parag. MI's release decision and RR's retained batting order must be checked first."],
        ["Ramandeep Singh","Indian batting all-rounder/lower-order profile; 106 pressure balls across 18 matches; index 75.19.","Offers lower-order flexibility rather than a like-for-like top-order bat. A depth option only if the retained all-rounder/finisher mix leaves a slot."],
        ["Indian death specialist","No Indian specialist fast/death bowler appears in the statistical bowling Top 10; Rahul Chahar is the only Indian bowler in that list and is a leg-spinner.","Do not infer RR lacks death bowling: its 2026 usage included Indian Brijesh, Sandeep and Tushar. The need is a succession/cover question after retention and fitness checks."],
    ],widths=[1.0,2.55,2.95],font=7.0,header_font=7.0)
    _heading(doc,"E2. Final conditional decision table",2)
    _table(doc,["Priority","Decision","Evidence trigger before action"],[
        ["1","Protect pace/death coverage","Confirm retention, workload and fitness of Archer, Brijesh, Nandre, Sandeep and Tushar; only recruit if a real vacancy remains."],
        ["2","Maintain middle-over spin depth","Review Jadeja, Bishnoi and Yash Punja retention/development; no automatic spinner purchase."],
        ["3","Secure Indian finishing/middle-order depth","Evaluate Rinku, Naman or Ramandeep only if released, registered, affordable and role-compatible."],
        ["4","Do not treat model ranks as auction availability","As of 13 Nov 2026, retention deadline is reported as 17 Nov; final auction register is expected 3 Dec. Verify official lists before naming a purchasable target."],
    ],widths=[0.65,1.9,3.95],font=7.1)
    _p(doc,"The IPL 2027 retention/release process is not yet complete at this report cut-off. The current reported retention deadline is 17 November 2026; the final auction register is expected on 3 December and the mini-auction is reported for 16 December in Goa. No ranked player is represented as currently available to RR.",size=8.0,color=GREY)

    # APPENDIX F - reproducibility, data and environment
    _page(doc)
    _heading(doc,"Appendix F. Clean-run reproducibility and environment",1)
    _p(doc,"This release includes the six original competition-supplied CSVs in `data/` so a reviewer can reproduce the analysis without locating a separate download. They are unmodified input files. Keep them within the competition/submission context and do not redistribute them publicly unless the organiser's terms explicitly permit it.",size=8.2)
    _heading(doc,"Clean-run commands",2)
    cmd="python -m pip install -r requirements.txt\npython -m pytest -q\npython main.py --audit-context --audit-pressure --audit-batting --audit-bowling --audit-baselines --audit-reliability --audit-rankings --audit-pressure-ranking-stability --audit-rr-squad\npython build_supplemental_outputs.py\npython run_scope_comparison.py\npython generate_report.py"
    p=doc.add_paragraph(); p.paragraph_format.left_indent=Inches(0.18)
    r=p.add_run(cmd); r.font.name="Liberation Mono"; r.font.size=Pt(7.2); r.font.color.rgb=RGBColor.from_string(NAVY)
    _table(doc,["Component","Version tested"],[
        ["Python","3.13.5"],["pandas","2.2.3"],["NumPy","2.3.5"],["Matplotlib","3.10.8"],["pytest","9.0.2"],["python-docx","1.2.0"]
    ],widths=[2.0,4.8],font=8.0)
    _p(doc,f"The test suite passed {test_count} tests in the final environment. The machine-readable results are stored in `outputs/test_results.txt`; scope comparison metrics and player-level changes are stored in `outputs/scope_comparison/`.",size=8.1)
    _p(doc,"The ranking CSVs remain authoritative for the primary order. The report tables and profile outputs are generated from those CSVs; no manual name substitution or score override is applied.",size=8.1)

    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(path)
    return str(path)
