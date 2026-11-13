# SupeRR Selector — Frontend Dashboard

A read-only Streamlit dashboard for the SupeRR Selector Season 2 project. It uses the project's **existing generated CSV and JSON outputs**; it does not recalculate, modify, or replace the official rankings.

## What is included

The dashboard has eight sections:

1. **Overview** — project objective, eligible candidate counts, match/delivery coverage and unique pressure deliveries.
2. **Top 10 Batters** — searchable/sortable official primary-scope leaderboard, index chart and profile shortcut.
3. **Top 10 Bowlers** — same functionality for the official bowling leaderboard.
4. **Player Intelligence** — evidence cards, components, peer-relative metric detail and supplied match spotlight for each of the 20 ranked players.
5. **Pressure Analysis** — early-collapse, death-phase, overlap and de-duplicated pressure distribution; definitions and source limitations.
6. **Scope Comparison** — official IPL + T20I and expanded all-supplied-T20 + T20I rankings, with entries/exits and rank/score changes.
7. **RR Auction Strategy** — 2026 usage-based role-depth matrix and conditional ranked-player fit screen.
8. **Methodology & Validation** — weights, peer baselines, shrinkage, source-data limitations and automated-test record.

## Where to put this folder

Copy the complete `frontend/` folder into the root of your existing **SupeRR_Selector_Season_2_Final_Complete** project. Do not put it inside `outputs/` or `src/`.

Expected layout:

```text
SupeRR_Selector_Season_2_Final_Complete/
├── frontend/
│   ├── app.py
│   ├── data_layer.py
│   ├── ui_helpers.py
│   ├── requirements.txt
│   ├── run_windows.bat
│   ├── run_mac_linux.sh
│   └── ...
├── outputs/
│   ├── batting_rankings_top10.csv
│   ├── bowling_rankings_top10.csv
│   ├── top10_batter_evidence.csv
│   ├── top10_bowler_evidence.csv
│   └── scope_comparison/
├── data/
├── src/
├── main.py
└── README.md
```

The dashboard needs the existing `outputs/` folder and its CSV/JSON files. It does not need to reload the raw ball-by-ball CSVs just to display the dashboard.

## Windows — easiest way to run

1. Install Python 3.10–3.13 from <https://www.python.org/downloads/>. During installation, enable **Add Python to PATH**.
2. Open the copied `frontend` folder.
3. Double-click `run_windows.bat`.
4. The first run creates a local `.venv`, installs the pinned dashboard dependencies, validates the project outputs, and starts Streamlit.
5. Open the local address printed in the terminal (normally `http://localhost:8501`).

Keep the terminal window open while using the dashboard. Press `Ctrl+C` in that window to stop it.

## macOS / Linux

From the project root:

```bash
cd frontend
chmod +x run_mac_linux.sh
./run_mac_linux.sh
```

Or run manually:

```bash
cd frontend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python validate_frontend.py
python -m streamlit run app.py
```

## Manual Windows command (alternative)

```powershell
cd frontend
py -3 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python validate_frontend.py
python -m streamlit run app.py
```

## Data handling and ranking integrity

- The official leaderboard pages load `outputs/batting_rankings_top10.csv` and `outputs/bowling_rankings_top10.csv`.
- The player profiles load the supplied evidence and match-spotlight CSVs.
- The expanded-scope leaderboard is loaded from `outputs/scope_comparison/` and is kept distinct from the primary ranking.
- The dashboard does not compare index values across scopes as if they shared one unchanged peer population.
- The dashboard does not infer economy rate, dot-ball rate, auction price, future availability, or statistics absent from the source outputs.
- RR fit labels are conditional. A 2026 team listing is not proof of a 2027 retention/release decision or auction eligibility.
- The six raw CSV inputs are not needed for read-only display, but are part of the full project for reproducible analysis.

## Troubleshooting

**“Could not find outputs/”** — confirm `frontend/` is copied directly beside `outputs/`.

**Missing output file / columns** — make sure this frontend is paired with the SupeRR Selector Season 2 Complete project release, not an older archive.

**Port 8501 already in use** — start with `python -m streamlit run app.py --server.port 8502` and open the URL shown in the terminal.

**Python command not found** — install Python 3.10–3.13 and reopen the terminal. On Windows, try `py -3` instead of `python`.

## Deployment note

This folder is designed for local review first. GitHub and hosting configuration are intentionally a separate next step. Before publishing, check the competition/data-pack licence and do not publish the six raw CSVs unless redistribution is permitted. The app is read-only and expects the existing outputs to be present alongside it.
