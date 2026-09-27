# NBA Stats Exporter

A local multi-page Streamlit application that retrieves season data from Basketball-Reference, previews the exact result, and exports every dataset to CSV or formatted Excel.

## How the application works

- A displayed season such as `2025-26` maps to Basketball-Reference's ending-year URL: `NBA_2026`.
- `Per Game` maps to `_per_game.html`; `Totals` maps to `_totals.html`.
- The scraper selects the configured player table by HTML id and also supports tables wrapped in HTML comments.
- The available metric list is discovered from each retrieved table; statistics are not hard-coded into the scraper.
- Dataset, column, filter, and sorting controls live in the compact sidebar so the main page remains focused on the results.
- Streamlit caches the cleaned table for six hours by season and statistic type. Changing columns, filters, or sorting uses the cached data and does not request the website again.
- Multi-team player records remain separate. Only empty rows, repeated in-table headers, and the rank column are removed.
- Player names are decoded and normalized as Unicode, preserving accents such as `Dončić`, `Jokić`, and `Vučević` in the app, CSV files, and Excel workbooks. Player search is accent-insensitive, so `Doncic` also matches `Dončić`.
- Fully blank source rows are removed, and short previews resize to their content instead of showing empty grid outlines.

## Available pages

- **Player Statistics:** the original Per Game and Totals dataset builder with dynamic columns, filters, and sorting.
- **Conference Standings:** separate Eastern and Western Conference tabs from the selected season summary, each with its own CSV and Excel downloads.
- **Playoff Series:** one row per playoff matchup and final series score; individual game rows are excluded.
- **Awards & Honors:** separate tabs for MVP/DPOY/ROTY winners, All-NBA Teams, All-Defensive Teams, All-Rookie Teams, and All-Stars. All-Stars are identified by Basketball-Reference's `AS` award marker.

The pages are lazy-loaded: selecting one page requests only the source needed for that page. Each season/page result is cached for six hours to avoid unnecessary repeat traffic.

## Requirements

- Python 3.10 or newer
- An internet connection while retrieving a new season/table

Check your Python version:

```bash
python --version
```

On macOS or Linux, use `python3` instead of `python` below if that is how Python is installed on your system.

## Run locally

### One-click live preview on macOS

Clone the repository once with GitHub Desktop, open the project folder in Finder, and double-click `start_live_preview.command`. On its first run, the launcher creates the Python environment, installs the requirements, and opens the app in your browser. Keep the launcher window open while using the app.

While it is running, the launcher checks GitHub every 15 seconds. When a clean local copy receives an update, Streamlit detects the changed files and refreshes the browser automatically. Automatic updates pause if you have uncommitted local changes, so your work is never overwritten.

If macOS blocks the launcher the first time, Control-click it, choose **Open**, and confirm **Open**.

### macOS / Linux

Open Terminal, go to the downloaded project folder, and run:

```bash
cd /path/to/nba-stats-exporter
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```

### Windows PowerShell

Open PowerShell, go to the downloaded project folder, and run:

```powershell
cd C:\path\to\nba-stats-exporter
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

If PowerShell blocks activation, either run `Set-ExecutionPolicy -Scope Process Bypass` for that one window or use Command Prompt instead.

Streamlit will print a local address, normally `http://localhost:8501`, and usually opens it automatically. Stop the app with `Ctrl+C`. On future runs, activate the environment and run only:

```bash
python -m streamlit run app.py
```

## Use the app

1. Choose a page and NBA season in the sidebar.
2. On Player Statistics, choose `Per Game` or `Totals`, select columns, filter, and sort as needed.
3. On Conference Standings, choose the Eastern Conference or Western Conference tab.
4. On Awards & Honors, choose League Awards, an honor-team tab, or All-Stars in the main page.
5. Preview the dataset and download it as CSV or Excel.

Both downloads use the same final DataFrame shown in the preview, including all active filters, selected columns, and sorting.

## Run tests

Install the development dependencies and run the test suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

The automated tests cover season URLs, regular and comment-wrapped table extraction, cleaning, filters, sorting, CSV output, and Excel formatting. They use local fixture HTML, so they do not send test traffic to Basketball-Reference.

## Project structure

```text
nba-stats-exporter/
├── app.py                 # Streamlit UI and cache boundary
├── src/
│   ├── config.py          # Dataset mappings, defaults, and limits
│   ├── scraper.py         # URL building, throttled requests, table extraction
│   ├── season_data.py     # Standings, playoffs, awards, honor teams, All-Stars
│   ├── cleaning.py        # Cleaning, filters, numeric detection, sorting
│   └── exporters.py       # CSV and formatted Excel generation
├── tests/                 # Offline automated tests
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Adding another Basketball-Reference dataset

Add its display name, URL slug, and expected table id to `STAT_TYPES` in `src/config.py`. The season selector, URL builder, cache key, filename, and dynamic column selector use that mapping automatically. Verify the source table id before enabling a new dataset.

## Rate limits and errors

The app waits at least 3.1 seconds between uncached requests within the process and does not retry rejected requests. HTTP 403/429 responses produce a friendly rate-limit message. A 404 produces a no-data message. The app does not use proxies or any access-control circumvention.

Basketball-Reference may change its page structure or access policy. Use the data responsibly and follow the site's terms and rate limits.
