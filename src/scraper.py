"""Basketball-Reference URL construction, retrieval, and table extraction."""

from __future__ import annotations

from io import StringIO
import re
import threading
import time

from bs4 import BeautifulSoup, Comment, Tag
import pandas as pd
import requests

from .config import (
    BASE_URL,
    MIN_REQUEST_INTERVAL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    STAT_TYPES,
)


class BasketballReferenceError(RuntimeError):
    """Base exception safe to show in the app."""


class RateLimitError(BasketballReferenceError):
    """Raised when Sports Reference rejects or throttles a request."""


class TableNotFoundError(BasketballReferenceError):
    """Raised when the requested player table is absent."""


_request_lock = threading.Lock()
_last_request_at = 0.0


def season_end_year(season_label: str) -> int:
    """Convert an NBA label such as ``2025-26`` to URL year ``2026``."""
    match = re.fullmatch(r"(\d{4})-(\d{2})", season_label.strip())
    if not match:
        raise ValueError("Season must use the format YYYY-YY, for example 2025-26.")

    start_year = int(match.group(1))
    expected_suffix = (start_year + 1) % 100
    if int(match.group(2)) != expected_suffix:
        raise ValueError(f"Invalid NBA season label: {season_label}")
    return start_year + 1


def get_season_url(season_label: str, statistic_type: str) -> str:
    """Return the Basketball-Reference URL for a UI season/stat selection."""
    try:
        slug = STAT_TYPES[statistic_type]["slug"]
    except KeyError as exc:
        raise ValueError(f"Unsupported statistic type: {statistic_type}") from exc
    return f"{BASE_URL}/NBA_{season_end_year(season_label)}_{slug}.html"


def fetch_basketball_reference_page(url: str) -> str:
    """Fetch one page while enforcing a conservative process-wide interval."""
    global _last_request_at

    headers = {
        "User-Agent": (
            "NBAStatsExporter/1.0 (personal interactive data export; "
            "one request per selection)"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Charset": "utf-8",
    }

    # The lock prevents two simultaneous Streamlit sessions from bursting requests.
    with _request_lock:
        elapsed = time.monotonic() - _last_request_at
        if elapsed < MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise BasketballReferenceError(
                "Unable to retrieve Basketball-Reference data. Check your internet "
                "connection and try again."
            ) from exc
        finally:
            _last_request_at = time.monotonic()

    if response.status_code in {403, 429}:
        raise RateLimitError(
            "Basketball-Reference temporarily rate-limited the request. "
            "Please wait and try again later."
        )
    if response.status_code == 404:
        raise BasketballReferenceError(
            "No data is currently available for this season."
        )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        raise BasketballReferenceError(
            "Unable to retrieve Basketball-Reference data. "
            f"The site returned HTTP {response.status_code}."
        ) from exc
    # Basketball-Reference serves UTF-8 HTML, but its response headers do not
    # always give requests enough information to choose UTF-8. Using
    # ``response.text`` in that situation can turn Jokić into JokiÄ‡.
    try:
        return response.content.decode("utf-8")
    except UnicodeDecodeError:
        fallback_encoding = response.apparent_encoding or "utf-8"
        return response.content.decode(fallback_encoding, errors="replace")


def _find_table_in_soup(soup: BeautifulSoup, statistic_type: str) -> Tag | None:
    config = STAT_TYPES[statistic_type]
    for table_id in config["table_ids"]:
        table = soup.find("table", id=table_id)
        if isinstance(table, Tag):
            return table

    # Controlled fallback for modest markup changes: still require a player column
    # and an id related to the configured dataset.
    slug = str(config["slug"])
    for table in soup.find_all("table"):
        table_id = str(table.get("id", ""))
        header_text = " ".join(th.get_text(" ", strip=True) for th in table.find_all("th"))
        if slug in table_id and re.search(r"\bPlayer\b", header_text):
            return table
    return None


def _locate_stats_table(html: str, statistic_type: str) -> Tag:
    soup = BeautifulSoup(html, "html.parser")
    table = _find_table_in_soup(soup, statistic_type)
    if table is not None:
        return table

    # Some Basketball-Reference tables are wrapped in HTML comments.
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        if "<table" not in str(comment):
            continue
        comment_soup = BeautifulSoup(str(comment), "html.parser")
        table = _find_table_in_soup(comment_soup, statistic_type)
        if table is not None:
            return table

    raise TableNotFoundError(
        "Selected player-statistics table could not be found on the page."
    )


def extract_stats_table(html: str, statistic_type: str) -> pd.DataFrame:
    """Extract only the configured player-statistics table from page HTML."""
    if statistic_type not in STAT_TYPES:
        raise ValueError(f"Unsupported statistic type: {statistic_type}")
    table = _locate_stats_table(html, statistic_type)
    try:
        frames = pd.read_html(StringIO(str(table)), flavor="lxml")
    except (ValueError, ImportError) as exc:
        raise TableNotFoundError(
            "Selected player-statistics table could not be parsed."
        ) from exc
    if not frames:
        raise TableNotFoundError(
            "Selected player-statistics table could not be parsed."
        )
    return frames[0]


def retrieve_stats(season_label: str, statistic_type: str) -> pd.DataFrame:
    """Retrieve and extract the raw table for a season/statistic selection."""
    url = get_season_url(season_label, statistic_type)
    html = fetch_basketball_reference_page(url)
    return extract_stats_table(html, statistic_type)
