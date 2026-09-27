"""Configuration shared by the scraper and Streamlit interface."""

from __future__ import annotations

from collections import OrderedDict


BASE_URL = "https://www.basketball-reference.com/leagues"

# Adding another dataset only requires a new entry with its URL slug/table id.
STAT_TYPES = OrderedDict(
    {
        "Per Game": {
            "slug": "per_game",
            "table_ids": ("per_game_stats", "per_game"),
        },
        "Totals": {
            "slug": "totals",
            "table_ids": ("totals_stats", "totals"),
        },
    }
)

DEFAULT_COLUMNS = (
    "Player",
    "Team",
    "Tm",
    "Pos",
    "Age",
    "G",
    "GS",
    "MP",
    "PTS",
    "TRB",
    "AST",
    "STL",
    "BLK",
    "FG%",
    "3P%",
    "FT%",
)

COLUMN_GROUPS = OrderedDict(
    {
        "Player Information": ("Player", "Age", "Team", "Tm", "Pos"),
        "Games / Playing Time": ("G", "GS", "MP"),
        "Scoring": (
            "PTS",
            "FG",
            "FGA",
            "FG%",
            "3P",
            "3PA",
            "3P%",
            "2P",
            "2PA",
            "2P%",
            "eFG%",
            "FT",
            "FTA",
            "FT%",
        ),
        "Rebounding": ("ORB", "DRB", "TRB"),
        "Playmaking": ("AST", "TOV"),
        "Defense": ("STL", "BLK"),
        "Other": ("PF", "Trp-Dbl", "Awards"),
    }
)

TEXT_COLUMNS = {
    "Player",
    "Team",
    "Tm",
    "Pos",
    "Awards",
}

REQUEST_TIMEOUT_SECONDS = 25
MIN_REQUEST_INTERVAL_SECONDS = 3.1
CACHE_TTL_SECONDS = 6 * 60 * 60

