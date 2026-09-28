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

PLAYER_METRIC_DEFINITIONS = OrderedDict(
    {
        "NBA Season": "Selected NBA season represented by the row.",
        "Player": "Player name.",
        "Team": "Team abbreviation; multi-team totals may appear as 2TM, 3TM, or 4TM.",
        "Tm": "Team abbreviation; multi-team totals may appear as 2TM, 3TM, or 4TM.",
        "Pos": "Primary position played.",
        "Position": "Primary position played.",
        "Age": "Player age during the selected season.",
        "G": "Games played.",
        "GS": "Games started.",
        "MP": "Minutes played.",
        "FG": "Field goals made.",
        "FGA": "Field-goal attempts.",
        "FG%": "Field-goal percentage.",
        "3P": "Three-point field goals made.",
        "3PA": "Three-point field-goal attempts.",
        "3P%": "Three-point field-goal percentage.",
        "2P": "Two-point field goals made.",
        "2PA": "Two-point field-goal attempts.",
        "2P%": "Two-point field-goal percentage.",
        "eFG%": "Effective field-goal percentage, adjusted for the added value of three-pointers.",
        "FT": "Free throws made.",
        "FTA": "Free-throw attempts.",
        "FT%": "Free-throw percentage.",
        "ORB": "Offensive rebounds.",
        "DRB": "Defensive rebounds.",
        "TRB": "Total rebounds.",
        "AST": "Assists.",
        "STL": "Steals.",
        "BLK": "Blocks.",
        "TOV": "Turnovers.",
        "PF": "Personal fouls.",
        "PTS": "Points scored.",
        "Trp-Dbl": "Triple-doubles recorded.",
        "Awards": "Basketball-Reference season award and honor abbreviations.",
    }
)

CONFERENCE_METRIC_DEFINITIONS = OrderedDict(
    {
        "NBA Season": "Selected NBA season represented by the row.",
        "Conference": "Eastern or Western Conference.",
        "Team": "NBA team name.",
        "Playoff Team": "Whether the team qualified for the playoffs.",
        "W": "Wins.",
        "L": "Losses.",
        "W/L%": "Winning percentage.",
        "GB": "Games behind the conference leader.",
        "PS/G": "Points scored per game.",
        "PA/G": "Points allowed per game.",
        "SRS": "Simple Rating System; point differential adjusted for schedule strength.",
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
