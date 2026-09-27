"""Season-level Basketball-Reference datasets beyond player statistics."""

from __future__ import annotations

from io import StringIO
import re
from typing import Iterable

from bs4 import BeautifulSoup, Comment, Tag
import pandas as pd

from .cleaning import clean_basketball_reference_table, find_column, normalize_unicode_text
from .scraper import (
    BASE_URL,
    TableNotFoundError,
    fetch_basketball_reference_page,
    retrieve_stats,
    season_end_year,
)


AWARDS_BASE_URL = "https://www.basketball-reference.com/awards"
PLAYOFFS_BASE_URL = "https://www.basketball-reference.com/playoffs"


def get_season_summary_url(season_label: str) -> str:
    return f"{BASE_URL}/NBA_{season_end_year(season_label)}.html"


def get_awards_url(season_label: str) -> str:
    return f"{AWARDS_BASE_URL}/awards_{season_end_year(season_label)}.html"


def get_playoffs_url(season_label: str) -> str:
    return f"{PLAYOFFS_BASE_URL}/NBA_{season_end_year(season_label)}.html"


def _document_roots(html: str) -> list[BeautifulSoup]:
    """Return a document with Basketball-Reference table comments expanded."""
    soup = BeautifulSoup(html, "html.parser")
    for comment in list(soup.find_all(string=lambda text: isinstance(text, Comment))):
        comment_text = str(comment)
        if "<table" in comment_text or "<h2" in comment_text or "<h3" in comment_text:
            fragment = BeautifulSoup(comment_text, "html.parser")
            replacement_nodes = list(fragment.contents)
            if replacement_nodes:
                comment.replace_with(*replacement_nodes)
    return [soup]


def _parse_table(table: Tag) -> pd.DataFrame:
    try:
        frames = pd.read_html(StringIO(str(table)), flavor="lxml")
    except (ValueError, ImportError) as exc:
        raise TableNotFoundError("Selected season table could not be parsed.") from exc
    if not frames:
        raise TableNotFoundError("Selected season table could not be parsed.")
    return frames[0]


def _find_table_by_ids(roots: Iterable[BeautifulSoup], table_ids: Iterable[str]) -> Tag | None:
    for root in roots:
        for table_id in table_ids:
            table = root.find("table", id=table_id)
            if isinstance(table, Tag):
                return table
    return None


def _find_table_after_heading(
    roots: Iterable[BeautifulSoup],
    heading_phrases: Iterable[str],
) -> Tag | None:
    phrases = [phrase.casefold() for phrase in heading_phrases]
    for root in roots:
        for heading in root.find_all(["h2", "h3", "h4"]):
            heading_text = heading.get_text(" ", strip=True).casefold()
            if not any(phrase in heading_text for phrase in phrases):
                continue
            next_element = heading.find_next(["table", "h2", "h3", "h4"])
            if isinstance(next_element, Tag) and next_element.name == "table":
                return next_element
    return None


def _standing_frame(table: Tag, conference: str) -> pd.DataFrame:
    frame = clean_basketball_reference_table(_parse_table(table), remove_rank=True)
    if frame.empty:
        return frame

    team_column = find_column(frame, (f"{conference} Conference", "Team", "Tm"))
    if team_column is None:
        team_column = str(frame.columns[0])
    frame = frame.rename(columns={team_column: "Team"})
    team_text = frame["Team"].astype("string")
    frame = frame[team_text.notna() & team_text.str.strip().ne("")].copy()
    frame.insert(0, "Conference", conference)
    frame.insert(2, "Playoff Team", frame["Team"].astype(str).str.endswith("*"))
    frame["Team"] = frame["Team"].astype(str).str.rstrip("*").str.strip()
    return frame.reset_index(drop=True)


def extract_conference_standings(html: str) -> pd.DataFrame:
    """Extract and combine Eastern and Western Conference standings."""
    roots = _document_roots(html)
    east = _find_table_by_ids(
        roots,
        ("confs_standings_E", "conference_standings_E", "standings_east"),
    )
    west = _find_table_by_ids(
        roots,
        ("confs_standings_W", "conference_standings_W", "standings_west"),
    )

    if east is None or west is None:
        for root in roots:
            for table in root.find_all("table"):
                header_text = " ".join(
                    cell.get_text(" ", strip=True) for cell in table.find_all(["th", "caption"])
                ).casefold()
                if east is None and "eastern conference" in header_text:
                    east = table
                if west is None and "western conference" in header_text:
                    west = table

    if east is None or west is None:
        raise TableNotFoundError("Conference standings could not be found for this season.")

    return pd.concat(
        [_standing_frame(east, "Eastern"), _standing_frame(west, "Western")],
        ignore_index=True,
    )


_ROUND_NAMES = (
    "NBA Finals",
    "Eastern Conference Finals",
    "Western Conference Finals",
    "Eastern Conference Semifinals",
    "Western Conference Semifinals",
    "Eastern Conference First Round",
    "Western Conference First Round",
    "Finals",
    "First Round",
)


def extract_playoff_series(html: str) -> pd.DataFrame:
    """Extract one row per playoff series, excluding individual game rows."""
    roots = _document_roots(html)
    table = _find_table_by_ids(roots, ("playoffs", "playoff_series", "series"))
    if table is None:
        table = _find_table_after_heading(roots, ("Playoff Series",))
    if table is None:
        raise TableNotFoundError("Playoff series could not be found for this season.")

    rows: list[dict[str, str]] = []
    current_round = ""
    seen: set[tuple[str, str, str]] = set()
    for row in table.find_all("tr"):
        cells = [
            str(normalize_unicode_text(cell.get_text(" ", strip=True)))
            for cell in row.find_all(["th", "td"])
        ]
        if not cells:
            continue
        row_text = " | ".join(cells).replace("Series Stats", "").strip()
        for round_name in _ROUND_NAMES:
            if round_name.casefold() in row_text.casefold():
                current_round = round_name
                break
        match = re.search(
            r"(?P<winner>[^|]+?)\s+over\s+(?P<loser>[^|(]+?)\s*\((?P<wins>\d+)\s*-\s*(?P<losses>\d+)\)",
            row_text,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        winner = match.group("winner").strip(" |")
        loser = match.group("loser").strip(" |")
        # Remove a round label if it was included in the same cell as the result.
        for round_name in _ROUND_NAMES:
            if winner.casefold().startswith(round_name.casefold()):
                winner = winner[len(round_name) :].strip(" |")
                current_round = round_name
                break
        key = (current_round, winner, loser)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "Round": current_round or "Playoffs",
                "Winner": winner,
                "Loser": loser,
                "Series": f"{match.group('wins')}-{match.group('losses')}",
            }
        )

    if not rows:
        raise TableNotFoundError("Playoff series could not be parsed for this season.")
    return pd.DataFrame(rows)


_AWARD_HEADINGS = {
    "Most Valuable Player": ("Most Valuable Player",),
    "Defensive Player of the Year": ("Defensive Player of the Year",),
    "Rookie of the Year": ("Rookie of the Year",),
}

_AWARD_TABLE_IDS = {
    "Most Valuable Player": ("mvp", "mvp_voting"),
    "Defensive Player of the Year": ("dpoy", "dpoy_voting"),
    "Rookie of the Year": ("roy", "roy_voting"),
}


def _rank_one_rows(frame: pd.DataFrame) -> pd.DataFrame:
    rank_column = find_column(frame, ("Rank", "Rk", "#"))
    if rank_column is None:
        return frame.head(1)
    ranks = frame[rank_column].astype("string").str.strip()
    winners = frame[ranks.str.match(r"^1(?:T|st)?$", case=False, na=False)]
    return winners if not winners.empty else frame.head(1)


def extract_award_winners(html: str) -> pd.DataFrame:
    """Extract MVP, DPOY, and Rookie of the Year winners."""
    roots = _document_roots(html)
    winners: list[dict[str, object]] = []
    for award, headings in _AWARD_HEADINGS.items():
        table = _find_table_by_ids(roots, _AWARD_TABLE_IDS[award])
        if table is None:
            table = _find_table_after_heading(roots, headings)
        if table is None:
            continue
        frame = clean_basketball_reference_table(_parse_table(table), remove_rank=False)
        for _, row in _rank_one_rows(frame).iterrows():
            player_column = find_column(frame, ("Player",))
            if player_column is None or pd.isna(row[player_column]):
                continue
            result: dict[str, object] = {"Award": award, "Player": row[player_column]}
            for output, aliases in (
                ("Age", ("Age",)),
                ("Team", ("Team", "Tm")),
                ("Vote Share", ("Share",)),
            ):
                column = find_column(frame, aliases)
                if column is not None:
                    result[output] = row[column]
            winners.append(result)

    if not winners:
        raise TableNotFoundError("MVP, DPOY, and Rookie of the Year tables were not found.")
    return pd.DataFrame(winners)


_HONOR_HEADINGS = {
    "All-NBA Teams": ("All-NBA Teams",),
    "All-Defensive Teams": ("All-Defensive Teams",),
    "All-Rookie Teams": ("All-Rookie Teams",),
}


def _selection_name(value: object) -> str | None:
    text = str(value).strip().casefold().replace(" ", "")
    if text == "firstteam" or re.match(r"^1(?:t|st|stteam)?$", text):
        return "First Team"
    if text == "secondteam" or re.match(r"^2(?:t|nd|ndteam)?$", text):
        return "Second Team"
    if text == "thirdteam" or re.match(r"^3(?:t|rd|rdteam)?$", text):
        return "Third Team"
    return None


def extract_honor_team(html: str, honor_name: str) -> pd.DataFrame:
    """Extract official All-NBA, All-Defensive, or All-Rookie selections."""
    if honor_name not in _HONOR_HEADINGS:
        raise ValueError(f"Unsupported honor table: {honor_name}")
    roots = _document_roots(html)
    table = _find_table_after_heading(roots, _HONOR_HEADINGS[honor_name])
    if table is None:
        raise TableNotFoundError(f"{honor_name} could not be found for this season.")
    frame = clean_basketball_reference_table(_parse_table(table), remove_rank=False)
    if frame.empty:
        raise TableNotFoundError(f"{honor_name} is empty for this season.")

    selection_column = find_column(frame, ("# Tm", "Selection", "Team Selection"))
    if selection_column is None:
        selection_column = str(frame.columns[0])
    selections = frame[selection_column].map(_selection_name)
    frame = frame[selections.notna()].copy()
    frame.insert(0, "Selection", selections[selections.notna()].tolist())

    team_column = find_column(frame, ("Tm", "Team"))
    if team_column is not None and team_column != selection_column:
        frame = frame.rename(columns={team_column: "Team"})

    preferred = [
        "Selection",
        "Pos",
        "Player",
        "Age",
        "Team",
        "G",
        "MP",
        "PTS",
        "TRB",
        "AST",
        "STL",
        "BLK",
    ]
    available = [column for column in preferred if column in frame.columns]
    if "Player" not in available:
        raise TableNotFoundError(f"{honor_name} player names could not be parsed.")
    return frame.loc[:, available].reset_index(drop=True)


def extract_all_stars(player_stats: pd.DataFrame) -> pd.DataFrame:
    """Build the season's All-Star list from exact ``AS`` award markers."""
    awards_column = find_column(player_stats, ("Awards",))
    player_column = find_column(player_stats, ("Player",))
    if awards_column is None or player_column is None:
        raise TableNotFoundError("All-Star selection markers were not found for this season.")

    def has_all_star_marker(value: object) -> bool:
        if pd.isna(value):
            return False
        return "AS" in {part.strip() for part in str(value).split(",")}

    selected = player_stats[player_stats[awards_column].map(has_all_star_marker)].copy()
    preferred = ["Player", "Team", "Tm", "Pos", "Age", "G", "PTS", "TRB", "AST"]
    available = [column for column in preferred if column in selected.columns]
    selected = selected.loc[:, available]
    if "Tm" in selected.columns and "Team" not in selected.columns:
        selected = selected.rename(columns={"Tm": "Team"})
    selected = selected.drop_duplicates(subset=[player_column], keep="first")
    return selected.sort_values(player_column, kind="stable").reset_index(drop=True)


def retrieve_conference_standings(season_label: str) -> pd.DataFrame:
    return extract_conference_standings(
        fetch_basketball_reference_page(get_season_summary_url(season_label))
    )


def retrieve_playoff_series(season_label: str) -> pd.DataFrame:
    return extract_playoff_series(
        fetch_basketball_reference_page(get_playoffs_url(season_label))
    )


def retrieve_awards_and_honors(season_label: str) -> dict[str, pd.DataFrame]:
    html = fetch_basketball_reference_page(get_awards_url(season_label))
    datasets: dict[str, pd.DataFrame] = {}
    try:
        datasets["League Awards"] = extract_award_winners(html)
    except TableNotFoundError:
        datasets["League Awards"] = pd.DataFrame()
    for honor_name in _HONOR_HEADINGS:
        try:
            datasets[honor_name] = extract_honor_team(html, honor_name)
        except TableNotFoundError:
            # Some honors did not exist in earlier seasons, and future/current
            # seasons may not have announced them yet.
            datasets[honor_name] = pd.DataFrame()
    if all(frame.empty for frame in datasets.values()):
        raise TableNotFoundError("Awards and honor teams are not available for this season.")
    return datasets


def retrieve_all_stars(season_label: str) -> pd.DataFrame:
    stats = clean_basketball_reference_table(
        retrieve_stats(season_label, "Totals"),
        remove_rank=True,
    )
    return extract_all_stars(stats)
