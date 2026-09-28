"""Streamlit user interface for the NBA Stats Exporter."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from src.cleaning import (
    add_nba_season_column,
    apply_filters,
    clean_basketball_reference_table,
    find_column,
    get_available_columns,
    get_numeric_columns,
    remove_blank_rows,
    sort_stats,
)
from src.config import (
    CACHE_TTL_SECONDS,
    CONFERENCE_METRIC_DEFINITIONS,
    DEFAULT_COLUMNS,
    PLAYER_METRIC_DEFINITIONS,
    STAT_TYPES,
)
from src.exporters import export_csv, export_excel
from src.scraper import BasketballReferenceError, retrieve_stats
from src.season_data import (
    retrieve_all_stars,
    retrieve_awards_and_honors,
    retrieve_conference_standings,
    retrieve_playoff_series,
)


DATA_CACHE_VERSION = 4
APP_PAGES = (
    "Player Statistics",
    "Conference Standings",
    "Playoff Series",
    "Awards & Honors",
)


st.set_page_config(
    page_title="NBA Stats Exporter",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_STYLES = """
<style>
    [data-testid="stSidebar"] {
        min-width: 350px;
        max-width: 350px;
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] {
        padding-top: 0.75rem;
    }
    [data-testid="stSidebar"] hr {
        margin: 1.1rem 0;
    }
    .sidebar-brand {
        font-size: 1.55rem;
        font-weight: 750;
        letter-spacing: -0.025em;
        line-height: 1.2;
        margin: 0.2rem 0 0.25rem;
    }
    .sidebar-tagline {
        color: rgba(128, 128, 128, 0.95);
        font-size: 0.88rem;
        line-height: 1.4;
        margin-bottom: 0.4rem;
    }
    .sidebar-section {
        font-size: 0.76rem;
        font-weight: 750;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: rgba(128, 128, 128, 0.95);
        margin: 0.25rem 0 0.6rem;
    }
    [data-testid="stMetric"] {
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 0.75rem;
        padding: 0.85rem 1rem;
        background: rgba(128, 128, 128, 0.045);
    }
    [data-testid="stDataFrame"] {
        border: 1px solid rgba(128, 128, 128, 0.18);
        border-radius: 0.75rem;
        overflow: hidden;
    }
    .results-caption {
        color: rgba(128, 128, 128, 0.95);
        margin-top: -0.55rem;
        margin-bottom: 1.1rem;
    }
</style>
"""


def latest_completed_season_start(today: date | None = None) -> int:
    """Return the start year of the latest likely completed NBA season."""
    today = today or date.today()
    return today.year - 1 if today.month >= 7 else today.year - 2


def season_options(first_start_year: int = 1950) -> list[str]:
    latest = latest_completed_season_start()
    # Include the upcoming/current season so the URL scheme remains forward-ready,
    # while defaulting to the most recently completed season.
    return [
        f"{year}-{(year + 1) % 100:02d}"
        for year in range(latest + 1, first_start_year - 1, -1)
    ]


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_stats(
    season: str,
    statistic_type: str,
    cache_version: int,
) -> pd.DataFrame:
    """Fetch once per season/type; all UI transformations happen after caching."""
    del cache_version  # Its value intentionally participates in the cache key.
    raw = retrieve_stats(season, statistic_type)
    return clean_basketball_reference_table(raw, remove_rank=True)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_conference_standings(season: str, cache_version: int) -> pd.DataFrame:
    del cache_version
    return retrieve_conference_standings(season)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_playoff_series(season: str, cache_version: int) -> pd.DataFrame:
    del cache_version
    return retrieve_playoff_series(season)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_awards_and_honors(
    season: str,
    cache_version: int,
) -> dict[str, pd.DataFrame]:
    del cache_version
    return retrieve_awards_and_honors(season)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def load_all_stars(season: str, cache_version: int) -> pd.DataFrame:
    del cache_version
    return retrieve_all_stars(season)


def existing_defaults(columns: list[str]) -> list[str]:
    defaults = [column for column in DEFAULT_COLUMNS if column in columns]
    if "Player" in columns and "Player" not in defaults:
        defaults.insert(0, "Player")
    return defaults


def _set_selection(key: str, values: list[str]) -> None:
    """Button callback that updates a multiselect before Streamlit reruns."""
    st.session_state[key] = list(values)


def _selection_summary(selected: list[str], total: int) -> str:
    if not selected:
        return "None"
    if len(selected) == total:
        return "All"
    return f"{len(selected)} selected"


def dataframe_height(row_count: int, *, maximum: int = 600) -> int:
    """Fit short tables to their content while keeping long tables scrollable."""
    return min(maximum, 38 + (max(row_count, 1) * 35))


def render_multiselect_popover(
    label: str,
    options: list[str],
    *,
    state_key: str,
    default_values: list[str],
    reset_values: list[str] | None = None,
) -> list[str]:
    """Render a compact sidebar selector with bulk-selection actions."""
    valid_values = [
        value for value in st.session_state.get(state_key, default_values) if value in options
    ]
    st.session_state[state_key] = valid_values
    summary = _selection_summary(valid_values, len(options))

    with st.popover(f"{label}  ·  {summary}", width="stretch"):
        action_columns = st.columns(2)
        action_columns[0].button(
            "Select All",
            key=f"{state_key}_select_all",
            on_click=_set_selection,
            args=(state_key, options),
            width="stretch",
        )
        action_columns[1].button(
            "Remove All",
            key=f"{state_key}_remove_all",
            on_click=_set_selection,
            args=(state_key, []),
            width="stretch",
        )
        if reset_values is not None:
            st.button(
                "Reset to Recommended",
                key=f"{state_key}_reset",
                on_click=_set_selection,
                args=(state_key, reset_values),
                width="stretch",
            )
        selected = st.multiselect(
            label,
            options,
            key=state_key,
            label_visibility="collapsed",
            placeholder=f"Choose {label.lower()}",
        )
    return selected


def render_metric_definitions(
    columns: list[str],
    definitions: dict[str, str],
    *,
    note: str | None = None,
) -> None:
    """Show definitions for the metrics available on the current page."""
    with st.popover("ⓘ Metric Definitions", width="stretch"):
        if note:
            st.caption(note)
        for column in columns:
            definition = definitions.get(
                column,
                "Basketball-Reference source field for the selected dataset.",
            )
            st.markdown(f"**{column}** — {definition}")


def render_downloads(
    dataframe: pd.DataFrame,
    *,
    base_filename: str,
    sheet_name: str,
    key_prefix: str,
) -> None:
    downloads = st.columns(2)
    downloads[0].download_button(
        "Download CSV",
        data=export_csv(dataframe),
        file_name=f"{base_filename}.csv",
        mime="text/csv",
        key=f"{key_prefix}_csv",
        width="stretch",
    )
    downloads[1].download_button(
        "Download Excel",
        data=export_excel(dataframe, sheet_name),
        file_name=f"{base_filename}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"{key_prefix}_xlsx",
        width="stretch",
    )


def render_player_statistics_page(season: str, statistic_type: str) -> None:
    try:
        with st.spinner("Loading player statistics…"):
            stats = load_stats(season, statistic_type, DATA_CACHE_VERSION)
    except BasketballReferenceError as exc:
        st.error(str(exc))
        st.info("Try another available season or wait before requesting the page again.")
        return
    except Exception:
        st.error("Unable to process the selected Basketball-Reference dataset.")
        st.info("Please try again later or check the terminal for developer diagnostics.")
        return

    if stats.empty:
        st.warning("No data is currently available for this season.")
        return

    columns = get_available_columns(stats)
    team_column = find_column(stats, ("Team", "Tm"))
    position_column = find_column(stats, ("Pos", "Position"))
    games_column = find_column(stats, ("G",))
    team_options = (
        sorted(stats[team_column].dropna().astype(str).unique().tolist())
        if team_column
        else []
    )
    position_options = (
        sorted(stats[position_column].dropna().astype(str).unique().tolist())
        if position_column
        else []
    )

    selection_id = f"{season}|{statistic_type}"
    if st.session_state.get("selection_id") != selection_id:
        st.session_state["selection_id"] = selection_id
        st.session_state["selected_columns"] = existing_defaults(columns)
        st.session_state["selected_teams"] = team_options
        st.session_state["selected_positions"] = position_options
        st.session_state["player_search"] = ""
        st.session_state["minimum_games"] = 0
        st.session_state["sort_choice"] = "Source order"
        st.session_state["sort_direction"] = "Descending"

    with st.sidebar:
        st.divider()
        st.markdown('<div class="sidebar-section">Columns</div>', unsafe_allow_html=True)
        selected_columns = render_multiselect_popover(
            "Columns",
            columns,
            state_key="selected_columns",
            default_values=existing_defaults(columns),
            reset_values=existing_defaults(columns),
        )
        st.caption(f"{len(selected_columns)} of {len(columns)} columns selected")

        st.divider()
        st.markdown('<div class="sidebar-section">Filters</div>', unsafe_allow_html=True)
        teams = render_multiselect_popover(
            "Teams",
            team_options,
            state_key="selected_teams",
            default_values=team_options,
        )
        positions = render_multiselect_popover(
            "Positions",
            position_options,
            state_key="selected_positions",
            default_values=position_options,
        )
        player_search = st.text_input(
            "Search Player",
            key="player_search",
            placeholder="e.g. curry",
        )
        max_games = (
            int(pd.to_numeric(stats[games_column], errors="coerce").max())
            if games_column and pd.to_numeric(stats[games_column], errors="coerce").notna().any()
            else 0
        )
        if int(st.session_state.get("minimum_games", 0)) > max_games:
            st.session_state["minimum_games"] = max_games
        minimum_games = st.number_input(
            "Minimum Games Played",
            min_value=0,
            max_value=max_games,
            step=1,
            key="minimum_games",
        )

        st.divider()
        st.markdown('<div class="sidebar-section">Sorting</div>', unsafe_allow_html=True)
        numeric_selected = get_numeric_columns(stats, selected_columns)
        sort_options = ["Source order", *numeric_selected]
        if st.session_state.get("sort_choice") not in sort_options:
            st.session_state["sort_choice"] = "Source order"
        sort_choice = st.selectbox(
            "Sort By",
            sort_options,
            key="sort_choice",
        )
        sort_direction = st.segmented_control(
            "Sort Direction",
            ("Descending", "Ascending"),
            key="sort_direction",
            width="stretch",
        )
        st.caption("Source: Basketball-Reference")

    filtered = apply_filters(
        stats,
        teams=teams if team_column else None,
        positions=positions if position_column else None,
        player_search=player_search,
        minimum_games=int(minimum_games),
    )
    sorted_data = sort_stats(
        filtered,
        None if sort_choice == "Source order" else sort_choice,
        ascending=sort_direction == "Ascending",
    )
    final_data = sorted_data.loc[:, selected_columns] if selected_columns else sorted_data.iloc[:, 0:0]

    st.header(f"{season} NBA Player Statistics — {statistic_type}")
    st.markdown(
        '<div class="results-caption">Your current selections are reflected in the table and both downloads.</div>',
        unsafe_allow_html=True,
    )
    render_metric_definitions(
        ["NBA Season", *columns],
        PLAYER_METRIC_DEFINITIONS,
        note=(
            "Counting statistics are displayed as per-game averages when Per Game is selected "
            "and as season totals when Totals is selected."
        ),
    )
    metrics = st.columns(4)
    player_column = find_column(filtered, ("Player",))
    unique_players = (
        int(filtered[player_column].nunique(dropna=True)) if player_column else len(filtered)
    )
    metrics[0].metric("Players / rows", f"{unique_players} / {len(filtered)}")
    metrics[1].metric("Selected metrics", len(selected_columns))
    metrics[2].metric("Season", season)
    metrics[3].metric("Statistic type", statistic_type)

    if not selected_columns:
        st.warning("Select at least one column to preview and export data.")
        return

    final_data = add_nba_season_column(final_data, season)
    if final_data.empty:
        st.warning("No rows match the current filters.")
        return

    st.dataframe(
        final_data,
        width="stretch",
        hide_index=True,
        height=dataframe_height(len(final_data)),
    )

    file_slug = str(STAT_TYPES[statistic_type]["slug"])
    render_downloads(
        final_data,
        base_filename=f"nba_{season}_{file_slug}",
        sheet_name="NBA Stats",
        key_prefix="player_stats",
    )


def render_standard_page(
    dataframe: pd.DataFrame,
    *,
    season: str,
    title: str,
    caption: str,
    base_filename: str,
    sheet_name: str,
    key_prefix: str,
) -> None:
    dataframe = add_nba_season_column(remove_blank_rows(dataframe), season)
    st.header(title)
    st.markdown(
        f'<div class="results-caption">{caption}</div>',
        unsafe_allow_html=True,
    )
    summary = st.columns(3)
    summary[0].metric("Rows", len(dataframe))
    summary[1].metric("Columns", len(dataframe.columns))
    summary[2].metric("Season", season)
    if dataframe.empty:
        st.warning("No data is currently available for this season.")
        return
    st.dataframe(
        dataframe,
        width="stretch",
        hide_index=True,
        height=dataframe_height(len(dataframe)),
    )
    render_downloads(
        dataframe,
        base_filename=base_filename,
        sheet_name=sheet_name,
        key_prefix=key_prefix,
    )


def render_conference_standings_page(season: str) -> None:
    try:
        with st.spinner("Loading conference standings…"):
            standings = load_conference_standings(season, DATA_CACHE_VERSION)
    except BasketballReferenceError as exc:
        st.error(str(exc))
        return

    standings = remove_blank_rows(standings)
    st.header(f"{season} NBA Conference Standings")
    st.markdown(
        '<div class="results-caption">Eastern and Western Conference standings, including playoff qualification markers.</div>',
        unsafe_allow_html=True,
    )
    render_metric_definitions(
        ["NBA Season", *standings.columns.tolist()],
        CONFERENCE_METRIC_DEFINITIONS,
    )

    conference_column = find_column(standings, ("Conference",))
    conference_tabs = st.tabs(("Eastern Conference", "Western Conference"))
    for tab, conference in zip(conference_tabs, ("Eastern", "Western")):
        with tab:
            if conference_column:
                conference_standings = standings.loc[
                    standings[conference_column].astype(str).str.casefold()
                    == conference.casefold()
                ].reset_index(drop=True)
            else:
                conference_standings = pd.DataFrame(columns=standings.columns)

            st.caption(f"{len(conference_standings)} teams")
            if conference_standings.empty:
                st.warning(f"No {conference} Conference standings are currently available.")
                continue

            conference_standings = add_nba_season_column(
                conference_standings,
                season,
            )
            st.dataframe(
                conference_standings,
                width="stretch",
                hide_index=True,
                height=dataframe_height(len(conference_standings)),
            )
            conference_slug = conference.casefold()
            render_downloads(
                conference_standings,
                base_filename=f"nba_{season}_{conference_slug}_conference_standings",
                sheet_name=f"{conference} Standings",
                key_prefix=f"standings_{conference_slug}",
            )


def render_playoff_series_page(season: str) -> None:
    try:
        with st.spinner("Loading playoff series…"):
            series = load_playoff_series(season, DATA_CACHE_VERSION)
    except BasketballReferenceError as exc:
        st.error(str(exc))
        return
    render_standard_page(
        series,
        season=season,
        title=f"{season} NBA Playoff Series",
        caption="One row per completed playoff matchup; individual game rows are excluded.",
        base_filename=f"nba_{season}_playoff_series",
        sheet_name="Playoff Series",
        key_prefix="playoffs",
    )


def render_awards_and_honors_page(season: str) -> None:
    try:
        with st.spinner("Loading awards and honor teams…"):
            datasets = load_awards_and_honors(season, DATA_CACHE_VERSION)
    except BasketballReferenceError as exc:
        st.error(str(exc))
        return

    try:
        with st.spinner("Loading All-Star selections…"):
            datasets["All-Stars"] = load_all_stars(season, DATA_CACHE_VERSION)
    except BasketballReferenceError:
        # Keep the awards page usable if All-Star selections are not available yet.
        datasets["All-Stars"] = pd.DataFrame()

    st.header(f"{season} NBA Awards & Honors")
    st.markdown(
        '<div class="results-caption">League award winners, official honor teams, and All-Star selections.</div>',
        unsafe_allow_html=True,
    )
    tabs = st.tabs(list(datasets))
    for tab, (dataset_name, dataframe) in zip(tabs, datasets.items()):
        with tab:
            dataframe = remove_blank_rows(dataframe)
            st.caption(f"{len(dataframe)} selections")
            if dataframe.empty:
                st.warning(f"No {dataset_name} data is currently available for this season.")
                continue
            dataframe = add_nba_season_column(
                dataframe,
                season,
                after_season=("Award", "Selection"),
            )
            st.dataframe(
                dataframe,
                width="stretch",
                hide_index=True,
                height=dataframe_height(len(dataframe), maximum=520),
            )
            slug = dataset_name.casefold().replace(" ", "_").replace("-", "_")
            render_downloads(
                dataframe,
                base_filename=f"nba_{season}_{slug}",
                sheet_name=dataset_name,
                key_prefix=f"honors_{slug}",
            )


def main() -> None:
    st.markdown(APP_STYLES, unsafe_allow_html=True)
    seasons = season_options()
    latest = latest_completed_season_start()
    default_season = f"{latest}-{(latest + 1) % 100:02d}"

    with st.sidebar:
        st.markdown('<div class="sidebar-brand">🏀 NBA Stats Exporter</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="sidebar-tagline">Explore and export season-level NBA data.</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown('<div class="sidebar-section">Explore</div>', unsafe_allow_html=True)
        page = st.radio("Page", APP_PAGES, label_visibility="collapsed")
        st.divider()
        st.markdown('<div class="sidebar-section">Dataset</div>', unsafe_allow_html=True)
        season = st.selectbox("NBA Season", seasons, index=seasons.index(default_season))
        statistic_type = None
        if page == "Player Statistics":
            statistic_type = st.radio("Statistic Type", list(STAT_TYPES), horizontal=True)
        st.caption("Source: Basketball-Reference")

    try:
        if page == "Player Statistics" and statistic_type is not None:
            render_player_statistics_page(season, statistic_type)
        elif page == "Conference Standings":
            render_conference_standings_page(season)
        elif page == "Playoff Series":
            render_playoff_series_page(season)
        elif page == "Awards & Honors":
            render_awards_and_honors_page(season)
    except BasketballReferenceError as exc:
        st.error(str(exc))
        st.info("Try another completed season or wait before requesting the page again.")
    except Exception:
        st.error("Unable to process the selected Basketball-Reference dataset.")
        st.info("Please try another completed season or check the terminal for developer diagnostics.")


if __name__ == "__main__":
    main()
