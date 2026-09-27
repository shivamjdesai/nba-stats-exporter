import pandas as pd

from src.season_data import (
    extract_all_stars,
    extract_award_winners,
    extract_conference_standings,
    extract_honor_team,
    extract_playoff_series,
    get_awards_url,
    get_playoffs_url,
    get_season_summary_url,
)


STANDINGS_HTML = """
<html><body>
<!--
<table id="confs_standings_E">
  <thead><tr><th>Eastern Conference</th><th>W</th><th>L</th><th>W/L%</th><th>GB</th></tr></thead>
  <tbody>
    <tr><td>Cleveland Cavaliers*</td><td>64</td><td>18</td><td>.780</td><td>—</td></tr>
    <tr><td>Boston Celtics*</td><td>61</td><td>21</td><td>.744</td><td>3.0</td></tr>
  </tbody>
</table>
<table id="confs_standings_W">
  <thead><tr><th>Western Conference</th><th>W</th><th>L</th><th>W/L%</th><th>GB</th></tr></thead>
  <tbody><tr><td>Oklahoma City Thunder*</td><td>68</td><td>14</td><td>.829</td><td>—</td></tr></tbody>
</table>
-->
</body></html>
"""


PLAYOFFS_HTML = """
<html><body><h2>Playoff Series</h2>
<table id="playoffs"><tbody>
  <tr><th>Finals</th></tr>
  <tr><th>Finals</th><td>Oklahoma City Thunder over Indiana Pacers (4-3)</td><td>Series Stats</td></tr>
  <tr><th>Game 1</th><td>Indiana Pacers 111 @ Oklahoma City Thunder 110</td></tr>
  <tr><th>Eastern Conference Finals</th><td>Indiana Pacers over New York Knicks (4-2)</td></tr>
</tbody></table></body></html>
"""


AWARDS_HTML = """
<html><body>
<h2>Most Valuable Player (Michael Jordan Trophy)</h2>
<table><thead><tr><th>Rank</th><th>Player</th><th>Age</th><th>Tm</th><th>Share</th></tr></thead>
<tbody><tr><td>1</td><td>Shai Gilgeous-Alexander</td><td>26</td><td>OKC</td><td>.900</td></tr></tbody></table>
<h2>Defensive Player of the Year (Hakeem Olajuwon Trophy)</h2>
<!-- Basketball-Reference can place the table in a comment while leaving its heading visible. -->
<!--
<table><thead><tr><th>Rank</th><th>Player</th><th>Age</th><th>Tm</th><th>Share</th></tr></thead>
<tbody><tr><td>1</td><td>Evan Mobley</td><td>23</td><td>CLE</td><td>.750</td></tr></tbody></table>
-->
<h2>Rookie of the Year (Wilt Chamberlain Trophy)</h2>
<table><thead><tr><th>Rank</th><th>Player</th><th>Age</th><th>Tm</th><th>Share</th></tr></thead>
<tbody><tr><td>1</td><td>Stephon Castle</td><td>20</td><td>SAS</td><td>.980</td></tr></tbody></table>
<h2>All-NBA Teams</h2>
<table><thead><tr><th># Tm</th><th>Pos</th><th>Player</th><th>Age</th><th>Tm</th><th>G</th><th>PTS</th></tr></thead>
<tbody>
 <tr><td>1T</td><td>C</td><td>Nikola Jokić</td><td>29</td><td>DEN</td><td>70</td><td>29.6</td></tr>
 <tr><td>2T</td><td>G</td><td>Jalen Brunson</td><td>28</td><td>NYK</td><td>65</td><td>26.0</td></tr>
 <tr><td>ORV</td><td>G</td><td>Other Player</td><td>25</td><td>AAA</td><td>80</td><td>20.0</td></tr>
</tbody></table>
<h2>All-Defensive Teams</h2>
<table><thead><tr><th># Tm</th><th>Pos</th><th>Player</th><th>Tm</th><th>STL</th><th>BLK</th></tr></thead>
<tbody><tr><td>1st</td><td>F</td><td>Evan Mobley</td><td>CLE</td><td>0.9</td><td>1.6</td></tr></tbody></table>
<h2>All-Rookie Teams</h2>
<table><thead><tr><th># Tm</th><th>Player</th><th>Tm</th><th>PTS</th></tr></thead>
<tbody><tr><td>1st</td><td>Stephon Castle</td><td>SAS</td><td>14.7</td></tr></tbody></table>
</body></html>
"""


def test_season_urls_use_ending_year():
    assert get_season_summary_url("2024-25").endswith("/NBA_2025.html")
    assert get_playoffs_url("2024-25").endswith("/NBA_2025.html")
    assert get_awards_url("2024-25").endswith("/awards_2025.html")


def test_extract_conference_standings_from_commented_tables():
    frame = extract_conference_standings(STANDINGS_HTML)
    assert frame["Conference"].tolist() == ["Eastern", "Eastern", "Western"]
    assert frame["Team"].tolist()[0] == "Cleveland Cavaliers"
    assert frame["Playoff Team"].all()


def test_extract_playoff_series_ignores_game_rows():
    frame = extract_playoff_series(PLAYOFFS_HTML)
    assert frame.to_dict("records") == [
        {
            "Round": "Finals",
            "Winner": "Oklahoma City Thunder",
            "Loser": "Indiana Pacers",
            "Series": "4-3",
        },
        {
            "Round": "Eastern Conference Finals",
            "Winner": "Indiana Pacers",
            "Loser": "New York Knicks",
            "Series": "4-2",
        },
    ]


def test_extract_award_winners_and_honor_teams():
    awards = extract_award_winners(AWARDS_HTML)
    assert awards["Award"].tolist() == [
        "Most Valuable Player",
        "Defensive Player of the Year",
        "Rookie of the Year",
    ]
    assert awards["Player"].tolist()[0] == "Shai Gilgeous-Alexander"
    assert awards.loc[
        awards["Award"].eq("Defensive Player of the Year"), "Player"
    ].tolist() == ["Evan Mobley"]

    all_nba = extract_honor_team(AWARDS_HTML, "All-NBA Teams")
    assert all_nba["Selection"].tolist() == ["First Team", "Second Team"]
    assert all_nba["Player"].tolist()[0] == "Nikola Jokić"
    assert extract_honor_team(AWARDS_HTML, "All-Defensive Teams").iloc[0]["Player"] == "Evan Mobley"
    assert extract_honor_team(AWARDS_HTML, "All-Rookie Teams").iloc[0]["Player"] == "Stephon Castle"


def test_extract_all_stars_uses_exact_award_marker():
    stats = pd.DataFrame(
        {
            "Player": ["Nikola Jokić", "Luka Dončić", "Jalen Williams"],
            "Team": ["DEN", "LAL", "OKC"],
            "Pos": ["C", "PG", "SF"],
            "Age": [29, 25, 23],
            "Awards": ["MVP-2,AS,NBA1", "MVP-3", "AS"],
        }
    )
    frame = extract_all_stars(stats)
    assert frame["Player"].tolist() == ["Jalen Williams", "Nikola Jokić"]
