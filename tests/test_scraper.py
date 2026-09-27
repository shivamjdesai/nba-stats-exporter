import pytest

import src.scraper
from src.scraper import (
    extract_stats_table,
    fetch_basketball_reference_page,
    get_season_url,
    season_end_year,
)


TABLE = """
<table id="per_game_stats">
  <thead><tr><th>Rk</th><th>Player</th><th>Team</th><th>G</th><th>PTS</th></tr></thead>
  <tbody><tr><td>1</td><td>A Player</td><td>AAA</td><td>82</td><td>20.5</td></tr></tbody>
</table>
"""


def test_season_mapping():
    assert season_end_year("2025-26") == 2026
    assert get_season_url("2024-25", "Totals").endswith("/NBA_2025_totals.html")
    assert get_season_url("2020-21", "Per Game").endswith("/NBA_2021_per_game.html")


def test_invalid_season_label():
    with pytest.raises(ValueError):
        season_end_year("2025-27")


def test_extracts_configured_live_table():
    frame = extract_stats_table(f"<html><body>{TABLE}</body></html>", "Per Game")
    assert frame.loc[0, "Player"] == "A Player"


def test_extracts_commented_table():
    html = f"<html><body><!--{TABLE}--></body></html>"
    frame = extract_stats_table(html, "Per Game")
    assert frame.loc[0, "PTS"] == 20.5


def test_fetch_decodes_utf8_even_when_response_text_is_mojibake(monkeypatch):
    class FakeResponse:
        status_code = 200
        content = "Nikola Jokić, Luka Dončić".encode("utf-8")
        text = content.decode("latin-1")
        apparent_encoding = "utf-8"

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(src.scraper.requests, "get", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(src.scraper.time, "sleep", lambda *_: None)
    monkeypatch.setattr(src.scraper, "_last_request_at", 0.0)

    html = fetch_basketball_reference_page("https://example.test/stats")

    assert html == "Nikola Jokić, Luka Dončić"
    assert "JokiÄ" not in html
