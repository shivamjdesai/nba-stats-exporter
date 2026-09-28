"""Reusable table cleaning, filtering, and sorting helpers."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
import unicodedata

import pandas as pd

from .config import TEXT_COLUMNS


def normalize_unicode_text(value: object) -> object:
    """Trim and normalize strings while leaving null/non-string values intact."""
    if not isinstance(value, str):
        return value
    return unicodedata.normalize("NFC", value.strip())


def _search_key(value: object) -> str:
    """Create a case- and accent-insensitive representation for player search."""
    if pd.isna(value):
        return ""
    decomposed = unicodedata.normalize("NFKD", str(value))
    return "".join(character for character in decomposed if not unicodedata.combining(character)).casefold()


def _flatten_columns(columns: pd.Index) -> list[str]:
    flattened: list[str] = []
    for column in columns:
        if isinstance(column, tuple):
            parts = [str(part).strip() for part in column]
            usable = [part for part in parts if part and not part.startswith("Unnamed:")]
            name = usable[-1] if usable else parts[-1]
        else:
            name = str(column).strip()
        flattened.append(name)

    # Pandas permits duplicate labels, but selections/exporters behave better with
    # stable unique names. Suffixes are only added if the source truly repeats one.
    counts: dict[str, int] = {}
    unique: list[str] = []
    for name in flattened:
        counts[name] = counts.get(name, 0) + 1
        unique.append(name if counts[name] == 1 else f"{name}_{counts[name]}")
    return unique


def clean_basketball_reference_table(
    dataframe: pd.DataFrame,
    *,
    remove_rank: bool = True,
) -> pd.DataFrame:
    """Clean source artifacts without aggregating or deduplicating players."""
    df = dataframe.copy()
    df.columns = _flatten_columns(df.columns)

    # Standardize blank cells while preserving nulls rather than filling with zero.
    for column in df.columns:
        if pd.api.types.is_object_dtype(df[column]):
            df[column] = df[column].map(normalize_unicode_text)
            df[column] = df[column].replace("", pd.NA)

    df = df.dropna(how="all")

    repeated_header = pd.Series(False, index=df.index)
    if "Player" in df.columns:
        repeated_header |= df["Player"].astype("string").str.strip().eq("Player").fillna(False)
        valid_player = df["Player"].notna() & df["Player"].astype("string").str.strip().ne("")
        df = df.loc[valid_player & ~repeated_header]
    elif "Rk" in df.columns:
        repeated_header |= df["Rk"].astype("string").str.strip().eq("Rk").fillna(False)
        df = df.loc[~repeated_header]

    if remove_rank and "Rk" in df.columns:
        df = df.drop(columns="Rk")

    # Convert a column only when every non-null source value is numeric. This keeps
    # text columns and unexpected source annotations intact.
    for column in df.columns:
        if column in TEXT_COLUMNS or pd.api.types.is_numeric_dtype(df[column]):
            continue
        original = df[column]
        non_null_count = int(original.notna().sum())
        if non_null_count == 0:
            continue
        converted = pd.to_numeric(original, errors="coerce")
        if int(converted.notna().sum()) == non_null_count:
            df[column] = converted

    return df.reset_index(drop=True)


def remove_blank_rows(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Remove rows containing only null, empty, or whitespace-only cells."""
    if dataframe.empty:
        return dataframe.copy().reset_index(drop=True)

    has_content = pd.Series(False, index=dataframe.index)
    for column in dataframe.columns:
        values = dataframe[column]
        column_has_content = values.notna()
        if pd.api.types.is_object_dtype(values) or pd.api.types.is_string_dtype(values):
            column_has_content &= values.astype("string").str.strip().ne("").fillna(False)
        has_content |= column_has_content
    return dataframe.loc[has_content].reset_index(drop=True)


def add_nba_season_column(dataframe: pd.DataFrame, season: str) -> pd.DataFrame:
    """Add the selected season first and place common player identifiers next."""
    frame = dataframe.drop(columns=["NBA Season"], errors="ignore").copy()
    frame.insert(0, "NBA Season", season)

    ordered = ["NBA Season"]
    lookup = {str(column).casefold(): str(column) for column in frame.columns}
    for aliases in (("Player",), ("Team", "Tm"), ("Pos", "Position"), ("Age",)):
        for alias in aliases:
            column = lookup.get(alias.casefold())
            if column and column not in ordered:
                ordered.append(column)
                break
    ordered.extend(column for column in frame.columns if column not in ordered)
    return frame.loc[:, ordered]


def get_available_columns(dataframe: pd.DataFrame) -> list[str]:
    return dataframe.columns.tolist()


def find_column(dataframe: pd.DataFrame, candidates: Iterable[str]) -> str | None:
    """Return the first existing alias, case-insensitively."""
    lookup = {str(column).casefold(): str(column) for column in dataframe.columns}
    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return None


def apply_filters(
    dataframe: pd.DataFrame,
    *,
    teams: Sequence[str] | None = None,
    positions: Sequence[str] | None = None,
    player_search: str = "",
    minimum_games: int = 0,
) -> pd.DataFrame:
    """Return filtered rows while preserving source order and duplicate players."""
    df = dataframe.copy()
    team_column = find_column(df, ("Team", "Tm"))
    position_column = find_column(df, ("Pos", "Position"))
    player_column = find_column(df, ("Player",))
    games_column = find_column(df, ("G",))

    if team_column and teams is not None:
        df = df[df[team_column].astype("string").isin(list(teams))]
    if position_column and positions is not None:
        df = df[df[position_column].astype("string").isin(list(positions))]
    if player_column and player_search.strip():
        search_term = _search_key(player_search.strip())
        player_names = df[player_column].map(_search_key)
        df = df[player_names.str.contains(search_term, regex=False, na=False)]
    if games_column and minimum_games > 0:
        games = pd.to_numeric(df[games_column], errors="coerce")
        df = df[games.ge(minimum_games)]
    return df.reset_index(drop=True)


def get_numeric_columns(
    dataframe: pd.DataFrame,
    selected_columns: Sequence[str] | None = None,
) -> list[str]:
    candidates = list(selected_columns) if selected_columns is not None else dataframe.columns.tolist()
    return [
        column
        for column in candidates
        if column in dataframe.columns and pd.api.types.is_numeric_dtype(dataframe[column])
    ]


def sort_stats(
    dataframe: pd.DataFrame,
    sort_by: str | None,
    *,
    ascending: bool = False,
) -> pd.DataFrame:
    if not sort_by or sort_by not in dataframe.columns:
        return dataframe.reset_index(drop=True)
    return dataframe.sort_values(
        by=sort_by,
        ascending=ascending,
        na_position="last",
        kind="stable",
    ).reset_index(drop=True)
