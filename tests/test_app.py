from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

import src.scraper
import src.season_data


def test_streamlit_results_first_layout(monkeypatch):
    monkeypatch.setattr(
        src.scraper,
        "retrieve_stats",
        lambda season, stat_type: pd.DataFrame(
            {
                "Rk": [1, 2],
                "Player": ["Nikola Jokić", "Luka Dončić"],
                "Team": ["AAA", "BBB"],
                "Pos": ["PG", "C"],
                "Age": [25, 29],
                "G": [82, 70],
                "PTS": [24.1, 18.5],
                "TRB": [4.2, 10.1],
                "AST": [8.2, 2.0],
                "FG%": [0.48, 0.55],
            }
        ),
    )

    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert not app.exception
    assert app.header[0].value.endswith("NBA Player Statistics — Per Game")
    assert app.dataframe[0].value.shape == (2, 10)
    assert app.dataframe[0].value.columns[:5].tolist() == [
        "NBA Season",
        "Player",
        "Team",
        "Pos",
        "Age",
    ]
    assert app.dataframe[0].value["NBA Season"].tolist() == ["2025-26", "2025-26"]
    assert app.dataframe[0].value["Player"].tolist() == ["Nikola Jokić", "Luka Dončić"]
    assert len(app.get("download_button")) == 2
    assert not any(item.value == "Select Columns" for item in app.subheader)
    assert not any("Additional source columns" in item.value for item in app.markdown)
    assert any("Field-goal percentage" in item.value for item in app.markdown)

    # Team Remove All and Select All affect only that sidebar filter.
    app.button[4].click().run()
    assert app.multiselect[1].value == []
    assert len(app.dataframe) == 0
    assert any("No rows match" in item.value for item in app.warning)

    app.button[3].click().run()
    assert app.multiselect[1].value == ["AAA", "BBB"]
    assert len(app.dataframe[0].value) == 2

    # Unaccented input still finds and displays the correctly accented name.
    app.text_input[0].input("jokic").run()
    assert app.dataframe[0].value["Player"].tolist() == ["Nikola Jokić"]
    app.text_input[0].input("").run()

    # Column removal suppresses preview/downloads until defaults are restored.
    app.button[1].click().run()
    assert app.multiselect[0].value == []
    assert len(app.dataframe) == 0
    assert any("Select at least one column" in item.value for item in app.warning)

    app.button[2].click().run()
    assert len(app.dataframe) == 1
    assert len(app.get("download_button")) == 2


def test_streamlit_navigation_loads_each_page_lazily(monkeypatch):
    monkeypatch.setattr(
        src.scraper,
        "retrieve_stats",
        lambda season, stat_type: pd.DataFrame(
            {
                "Player": ["Nikola Jokić"],
                "Team": ["DEN"],
                "Pos": ["C"],
                "G": [70],
                "PTS": [29.6],
                "Awards": ["AS,NBA1"],
            }
        ),
    )
    monkeypatch.setattr(
        src.season_data,
        "retrieve_conference_standings",
        lambda season: pd.DataFrame(
            {
                "Conference": ["Eastern", "Western"],
                "Team": ["CLE", "OKC"],
                "W": [64, 68],
                "L": [18, 14],
                "GB": ["—", "—"],
            }
        ),
    )
    monkeypatch.setattr(
        src.season_data,
        "retrieve_playoff_series",
        lambda season: pd.DataFrame(
            {"Round": ["Finals"], "Winner": ["OKC"], "Loser": ["IND"], "Series": ["4-3"]}
        ),
    )
    monkeypatch.setattr(
        src.season_data,
        "retrieve_awards_and_honors",
        lambda season: {
            "League Awards": pd.DataFrame({"Award": ["MVP"], "Player": ["SGA"]}),
            "All-NBA Teams": pd.DataFrame({"Selection": ["First Team"], "Player": ["Nikola Jokić"]}),
            "All-Defensive Teams": pd.DataFrame({"Selection": ["First Team"], "Player": ["Evan Mobley"]}),
            "All-Rookie Teams": pd.DataFrame({"Selection": ["First Team"], "Player": ["Stephon Castle"]}),
        },
    )
    monkeypatch.setattr(
        src.season_data,
        "retrieve_all_stars",
        lambda season: pd.DataFrame({"Player": ["Nikola Jokić"], "Team": ["DEN"]}),
    )

    app_path = Path(__file__).parents[1] / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    expected = {
        "Conference Standings": ("NBA Conference Standings", 2, 4),
        "Playoff Series": ("NBA Playoff Series", 1, 2),
        "Awards & Honors": ("NBA Awards & Honors", 5, 10),
    }

    for page, (heading, table_count, download_count) in expected.items():
        app.radio[0].set_value(page).run()
        assert not app.exception
        assert heading in app.header[0].value
        assert len(app.dataframe) == table_count
        assert len(app.get("download_button")) == download_count
        assert all(
            dataframe.value.columns[0] == "NBA Season"
            for dataframe in app.dataframe
        )
        assert all(
            dataframe.value["NBA Season"].eq("2025-26").all()
            for dataframe in app.dataframe
        )

        if page == "Conference Standings":
            assert any("Games behind" in item.value for item in app.markdown)
            assert [tab.label for tab in app.tabs] == [
                "Eastern Conference",
                "Western Conference",
            ]
            assert app.dataframe[0].value["Team"].tolist() == ["CLE"]
            assert app.dataframe[1].value["Team"].tolist() == ["OKC"]

    assert "All-Stars" not in app.radio[0].options
    assert app.dataframe[0].value.columns[:2].tolist() == ["NBA Season", "Award"]
    assert all(
        dataframe.value.columns[:2].tolist() == ["NBA Season", "Selection"]
        for dataframe in app.dataframe[1:4]
    )
    assert app.dataframe[4].value["Player"].tolist() == ["Nikola Jokić"]
