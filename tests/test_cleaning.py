import pandas as pd

from src.cleaning import (
    add_nba_season_column,
    apply_filters,
    clean_basketball_reference_table,
    remove_blank_rows,
    sort_stats,
)


def sample_frame():
    return pd.DataFrame(
        {
            "Rk": ["1", "Rk", "2", "3"],
            "Player": ["Alpha", "Player", "Bravo", "Bravo"],
            "Team": ["AAA", "Team", "BBB", "2TM"],
            "Pos": ["PG", "Pos", "C", "C"],
            "G": ["10", "G", "20", "30"],
            "PTS": ["5.5", "PTS", "10.0", None],
        }
    )


def test_cleaning_removes_artifacts_but_preserves_multi_team_rows():
    cleaned = clean_basketball_reference_table(sample_frame())
    assert "Rk" not in cleaned.columns
    assert cleaned["Player"].tolist() == ["Alpha", "Bravo", "Bravo"]
    assert pd.api.types.is_numeric_dtype(cleaned["G"])
    assert pd.isna(cleaned.loc[2, "PTS"])


def test_filters_and_stable_sort():
    cleaned = clean_basketball_reference_table(sample_frame())
    filtered = apply_filters(
        cleaned,
        teams=["BBB", "2TM"],
        positions=["C"],
        player_search="brav",
        minimum_games=15,
    )
    assert len(filtered) == 2
    result = sort_stats(filtered, "G", ascending=False)
    assert result["G"].tolist() == [30, 20]


def test_unicode_names_are_normalized_and_search_is_accent_insensitive():
    # The source includes both precomposed and decomposed Unicode forms.
    frame = pd.DataFrame(
        {
            "Player": ["Nikola Jokic\u0301", "Luka Dončić", "Nikola Jokić"],
            "Team": ["DEN", "LAL", "DEN"],
            "Pos": ["C", "PG", "C"],
            "G": [70, 65, 72],
        }
    )
    cleaned = clean_basketball_reference_table(frame)

    assert cleaned.loc[0, "Player"] == "Nikola Jokić"
    assert apply_filters(cleaned, player_search="doncic")["Player"].tolist() == ["Luka Dončić"]
    assert apply_filters(cleaned, player_search="jokic")["Player"].tolist() == [
        "Nikola Jokić",
        "Nikola Jokić",
    ]


def test_remove_blank_rows_treats_whitespace_as_empty():
    frame = pd.DataFrame(
        {
            "Player": ["Nikola Jokić", "   ", None],
            "Team": ["DEN", "", pd.NA],
            "PTS": [29.6, None, float("nan")],
        }
    )

    cleaned = remove_blank_rows(frame)

    assert len(cleaned) == 1
    assert cleaned.loc[0, "Player"] == "Nikola Jokić"


def test_nba_season_is_first_and_player_identifiers_follow():
    frame = pd.DataFrame(
        {
            "Player": ["Nikola Jokić"],
            "Age": [31],
            "Team": ["DEN"],
            "Pos": ["C"],
            "PTS": [29.6],
        }
    )

    result = add_nba_season_column(frame, "2025-26")

    assert result.columns.tolist() == [
        "NBA Season",
        "Player",
        "Team",
        "Pos",
        "Age",
        "PTS",
    ]
    assert result["NBA Season"].tolist() == ["2025-26"]
