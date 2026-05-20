from __future__ import annotations

import json
import re
from pathlib import Path

from dash import Dash, Input, Output, State, clientside_callback, ctx, dcc, html
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
DATA_SHARED = ROOT / "data" / "shared"
DATA_PROCESSED = ROOT / "data" / "processed"
GITHUB_REPO_URL = "https://github.com/Frankyangz/chicago-crime-patterns-explorer"

YEARS = [2021, 2022, 2023, 2024, 2025]
YEAR_OPTIONS = [{"label": "All Years", "value": "all"}] + [{"label": str(year), "value": year} for year in YEARS]
METRICS = [
    {"label": "Incident Count", "value": "incidents"},
    {"label": "Arrest Rate", "value": "arrest_rate"},
    {"label": "Incidents per 100k", "value": "incidents_per_100k"},
]
METRIC_LABELS = {item["value"]: item["label"] for item in METRICS}

monthly = pd.read_csv(DATA_SHARED / "monthly_crime_counts.csv", parse_dates=["month"])
community_counts = pd.read_csv(DATA_SHARED / "community_area_yearly_counts.csv")
heatmap = pd.read_csv(DATA_PROCESSED / "day_hour_heatmap.csv")
with (DATA_SHARED / "community_area_boundaries.geojson").open("r", encoding="utf-8") as file:
    community_geojson = json.load(file)

CRIME_TYPES = ["All Types"] + sorted(t for t in monthly["primary_type"].dropna().unique() if t != "All Types")
CRIME_TYPE_OPTIONS = [{"label": item, "value": item} for item in CRIME_TYPES]
COMMUNITY_OPTIONS = [{"label": "All Community Areas", "value": 0}] + [
    {"label": row.community_name, "value": int(row.community_area)}
    for row in community_counts[["community_area", "community_name"]].drop_duplicates().sort_values("community_area").itertuples(index=False)
]
COMMUNITY_AREA_COUNT = int(community_counts[community_counts["community_area"] != 0]["community_area"].nunique())

ANALYSIS_START = pd.Timestamp("2021-01-01")
ANALYSIS_END = pd.Timestamp("2025-12-31")
MONTH_STARTS = pd.date_range(ANALYSIS_START, "2025-12-01", freq="MS")
MONTH_MARKS = {
    index: {"label": str(month.year), "style": {"fontWeight": "700"}}
    for index, month in enumerate(MONTH_STARTS)
    if month.month == 1
}
MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAY_ORDER = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}
DAY_LABELS = list(DAY_ORDER.keys())
HOUR_BANDS = [(0, "00-04"), (4, "04-08"), (8, "08-12"), (12, "12-16"), (16, "16-20"), (20, "20-24")]
HOUR_BAND_LABELS = {
    "00-04": "12 AM-4 AM",
    "04-08": "4 AM-8 AM",
    "08-12": "8 AM-12 PM",
    "12-16": "12 PM-4 PM",
    "16-20": "4 PM-8 PM",
    "20-24": "8 PM-12 AM",
}

app = Dash(__name__, title="Chicago Crime Patterns Explorer")
server = app.server


def material_icon(name: str) -> html.Span:
    return html.Span(name, className="material-symbols-outlined", **{"aria-hidden": "true"})


def format_number(value: float | int) -> str:
    return f"{int(round(value)):,}"


def format_percent(value: float | int) -> str:
    return f"{float(value):.1f}%"


def blend_hex(start: str, end: str, ratio: float) -> str:
    ratio = max(0, min(float(ratio), 1))
    start_rgb = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
    mixed = tuple(round(start_value + (end_value - start_value) * ratio) for start_value, end_value in zip(start_rgb, end_rgb))
    return "#" + "".join(f"{value:02x}" for value in mixed)


def arrest_rate_colors(values: list[float], low_color: str, high_color: str) -> list[str]:
    if not values:
        return []
    low = min(values)
    high = max(values)
    if high == low:
        return [blend_hex(low_color, high_color, 0.5) for _ in values]
    return [blend_hex(low_color, high_color, (value - low) / (high - low)) for value in values]


def compact_color_key(title: str, low_label: str, high_label: str, low_color: str, high_color: str):
    return [
        html.Span(title, className="color-key-title"),
        html.Div(className="color-key-ramp", style={"background": f"linear-gradient(90deg, {low_color}, {high_color})"}),
        html.Div(
            className="color-key-labels",
            children=[html.Span(low_label), html.Span(high_label)],
        ),
    ]


def category_color_key(values: list[float], low_color: str, high_color: str):
    if not values:
        return []
    low = min(values)
    high = max(values)
    return compact_color_key("Arrest rate", format_percent(low), format_percent(high), low_color, high_color)


def heatmap_color_key(year: int | str, crime_type: str, community_area: int, low_color: str, high_color: str):
    data = filtered_heatmap_data(year, crime_type, community_area)
    if data.empty:
        return []
    low = int(data["incidents"].min())
    high = int(data["incidents"].max())
    return compact_color_key("Incidents", format_number(low), format_number(high), low_color, high_color)


def kpi_card(label: str, value: str, detail: str, icon: str, trend: str | None = None, trend_class: str = "good") -> html.Div:
    return html.Div(
        className="kpi-card",
        children=[
            html.Div(className="kpi-glow"),
            html.Div(label, className="kpi-label"),
            html.Div(
                className="kpi-main",
                children=[
                    html.Div([html.Div(value, className="kpi-value"), html.Div(detail, className="kpi-detail")]),
                    html.Div(material_icon(icon), className="kpi-icon"),
                ],
            ),
            html.Div(trend, className=f"kpi-trend {trend_class}") if trend else None,
        ],
    )


def card(title: str, subtitle: str, graph_id: str, class_name: str = "", footer_children=None, header_extra=None) -> html.Section:
    return html.Section(
        className=f"panel chart-card {class_name}",
        children=[
            html.Div(className="panel-header", children=[html.Div([html.H3(title), html.P(subtitle)]), header_extra]),
            dcc.Graph(id=graph_id, className="graph", config={"displayModeBar": False, "responsive": True}),
            *(footer_children or []),
        ],
    )


def trend_slider() -> html.Div:
    return html.Div(
        className="trend-slider",
        children=[
            dcc.RangeSlider(
                id="trend-range",
                min=0,
                max=len(MONTH_STARTS) - 1,
                step=1,
                value=[0, len(MONTH_STARTS) - 1],
                marks=MONTH_MARKS,
                allowCross=False,
                tooltip={"placement": "bottom", "always_visible": False},
                className="time-range-slider",
            ),
            html.Div(
                className="trend-range-labels",
                children=[
                    html.Span("Jan 2021"),
                    html.Span([html.Span("Dec 2025"), html.Small("2026 excluded")], className="range-end-label"),
                ],
            ),
        ],
    )


def themed_layout(fig: go.Figure, theme: str, margin: dict | None = None) -> go.Figure:
    dark = theme == "dark"
    template = "plotly_dark" if dark else "plotly_white"
    text_color = "#eff1f3" if dark else "#191c1e"
    grid_color = "rgba(239, 241, 243, 0.12)" if dark else "rgba(25, 28, 30, 0.10)"
    fig.update_layout(
        template=template,
        margin=margin or dict(l=20, r=20, t=10, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=text_color,
    )
    fig.update_xaxes(gridcolor=grid_color, zerolinecolor=grid_color)
    fig.update_yaxes(gridcolor=grid_color, zerolinecolor=grid_color)
    return fig


def is_all_years(year: int | str) -> bool:
    return str(year) == "all"


def year_label(year: int | str) -> str:
    return "2021-2025 combined" if is_all_years(year) else str(year)


def by_year(data: pd.DataFrame, year: int | str) -> pd.DataFrame:
    return data.copy() if is_all_years(year) else data[data["year"] == int(year)].copy()


def filtered_annual_outcomes(year: int | str, crime_type: str, community_area: int) -> pd.DataFrame:
    data = community_counts[community_counts["primary_type"] == crime_type].copy()
    if community_area:
        data = data[data["community_area"] == int(community_area)]
    annual = data.groupby("year", as_index=False)[["incidents", "arrests"]].sum()
    annual = annual.set_index("year").reindex(YEARS, fill_value=0).reset_index()
    annual["arrest_rate"] = (annual["arrests"] / annual["incidents"] * 100).where(annual["incidents"] > 0, 0).round(2)
    annual["incident_label"] = annual["incidents"].map(format_number)
    annual["arrest_rate_label"] = annual["arrest_rate"].map(format_percent)
    annual["selected"] = False if is_all_years(year) else annual["year"] == int(year)
    return annual


def filtered_counts(year: int | str, crime_type: str, community_area: int) -> pd.DataFrame:
    data = by_year(community_counts, year)
    data = data[data["primary_type"] == crime_type].copy()
    if community_area:
        data = data[data["community_area"] == community_area]
    return data


def export_rows(year: int | str, crime_type: str, community_area: int) -> pd.DataFrame:
    data = filtered_counts(year, crime_type, community_area).copy()
    if community_area:
        export = data.sort_values(["year", "primary_type"]).copy()
        export["scope"] = export["community_name"]
        return export

    export = data.groupby(["year", "primary_type"], as_index=False)[["not_arrests", "arrests", "incidents"]].sum()
    export["community_area"] = 0
    export["community_name"] = "All Community Areas"
    export["scope"] = "citywide"
    export["arrest_rate"] = (export["arrests"] / export["incidents"] * 100).where(export["incidents"] > 0, 0).round(2)
    return export[["year", "community_area", "community_name", "scope", "primary_type", "not_arrests", "arrests", "incidents", "arrest_rate"]]


def aggregate_area_data(year: int | str, crime_type: str) -> pd.DataFrame:
    data = by_year(community_counts, year)
    data = data[data["primary_type"] == crime_type].copy()
    grouped = data.groupby(["community_area", "community_name"], as_index=False).agg(
        incidents=("incidents", "sum"),
        arrests=("arrests", "sum"),
        total_population=("total_population", "first"),
    )
    grouped["arrest_rate"] = (grouped["arrests"] / grouped["incidents"] * 100).round(2)
    grouped["incidents_per_100k"] = (grouped["incidents"] / grouped["total_population"] * 100000).round(2)
    grouped["community_area_str"] = grouped["community_area"].astype(int).astype(str)
    grouped["incident_rank"] = grouped["incidents"].rank(method="min", ascending=False).astype(int)
    grouped["per_100k_rank"] = grouped["incidents_per_100k"].rank(method="min", ascending=False).astype(int)
    grouped["arrest_rate_rank"] = grouped["arrest_rate"].rank(method="min", ascending=False).astype(int)
    return grouped


def selected_area_from_click(click_data: dict | None, fallback_area: int) -> int:
    if fallback_area:
        return int(fallback_area)
    if click_data and click_data.get("points"):
        location = click_data["points"][0].get("location")
        if location is not None:
            return int(location)
    return 0


def kpis_for_selection(year: int | str, crime_type: str, community_area: int) -> list[html.Div]:
    current = filtered_counts(year, crime_type, community_area)
    previous = filtered_counts(int(year) - 1, crime_type, community_area) if not is_all_years(year) and int(year) > min(YEARS) else pd.DataFrame()

    incidents = int(current["incidents"].sum()) if not current.empty else 0
    arrests = int(current["arrests"].sum()) if not current.empty else 0
    arrest_rate = arrests / incidents * 100 if incidents else 0

    if is_all_years(year):
        yoy_text = "2021-2025 total"
        yoy_class = "good"
    else:
        prev_incidents = int(previous["incidents"].sum()) if not previous.empty else 0
        yoy = (incidents - prev_incidents) / prev_incidents * 100 if prev_incidents else None
        yoy_text = None if yoy is None else f"{'Up' if yoy >= 0 else 'Down'} {abs(yoy):.1f}% YoY"
        yoy_class = "bad" if yoy and yoy > 0 else "good"

    scope = "citywide" if community_area == 0 else current["community_name"].iloc[0] if not current.empty else "selected area"

    type_base = by_year(community_counts, year)
    type_base = type_base[type_base["primary_type"] != "All Types"].copy()
    if community_area:
        type_base = type_base[type_base["community_area"] == community_area]
    top_type = type_base.groupby("primary_type", as_index=False)["incidents"].sum().sort_values("incidents", ascending=False).head(1)
    top_type_name = top_type["primary_type"].iloc[0] if not top_type.empty else "N/A"
    top_type_count = int(top_type["incidents"].iloc[0]) if not top_type.empty else 0

    area_base = by_year(community_counts, year)
    area_base = area_base[area_base["primary_type"] == crime_type].copy()
    top_area = area_base.groupby("community_name", as_index=False)["incidents"].sum().sort_values("incidents", ascending=False).head(1)
    area_name = top_area["community_name"].iloc[0] if not top_area.empty else "N/A"
    area_count = int(top_area["incidents"].iloc[0]) if not top_area.empty else 0

    return [
        kpi_card("Total Incidents", format_number(incidents), f"{scope}, {year_label(year)}", "monitoring", yoy_text, yoy_class),
        kpi_card("Avg Arrest Rate", format_percent(arrest_rate), f"{format_number(arrests)} arrests", "percent"),
        kpi_card("Most Frequent", top_type_name, f"{format_number(top_type_count)} incidents", "directions_run"),
        kpi_card("Highest Volume Area", area_name, f"{format_number(area_count)} incidents", "location_city"),
    ]


def filtered_heatmap_data(year: int | str, crime_type: str, community_area: int) -> pd.DataFrame:
    data = heatmap[heatmap["primary_type"] == crime_type].copy()
    if "year" in data.columns and not is_all_years(year):
        data = data[data["year"] == int(year)]
    if "community_area" in data.columns:
        selected_area = int(community_area) if community_area else 0
        area_data = data[data["community_area"] == selected_area]
        if area_data.empty and selected_area != 0:
            area_data = data[data["community_area"] == 0]
        data = area_data

    grouped = data.groupby(["day", "hour_band"], as_index=False)["incidents"].sum()
    complete = pd.MultiIndex.from_product([DAY_LABELS, [label for _, label in HOUR_BANDS]], names=["day", "hour_band"]).to_frame(index=False)
    grouped = complete.merge(grouped, on=["day", "hour_band"], how="left").fillna({"incidents": 0})
    grouped["day_order"] = grouped["day"].map(DAY_ORDER)
    grouped["hour_band_start"] = grouped["hour_band"].map({label: start for start, label in HOUR_BANDS})
    grouped["incidents"] = grouped["incidents"].astype(int)
    return grouped.sort_values(["day_order", "hour_band_start"])


def heatmap_figure(year: int | str, crime_type: str, community_area: int, theme: str) -> go.Figure:
    data = filtered_heatmap_data(year, crime_type, community_area)
    matrix = data.pivot(index="day", columns="hour_band", values="incidents").reindex(index=DAY_LABELS, columns=[label for _, label in HOUR_BANDS]).fillna(0)
    x_labels = [HOUR_BAND_LABELS[label] for label in matrix.columns]
    primary = "#075f73" if theme != "dark" else "#8bd5e6"
    accent = "#c25f00" if theme != "dark" else "#ffb960"
    fig = go.Figure(
        data=go.Heatmap(
            z=matrix.values,
            x=x_labels,
            y=list(matrix.index),
            xgap=2,
            ygap=2,
            colorscale=[[0, "#eef4f7"], [0.45, primary], [1, accent]] if theme != "dark" else [[0, "#12212a"], [0.45, primary], [1, accent]],
            showscale=False,
            hovertemplate="%{y}, %{x}<br>%{z:,} reported incidents<extra></extra>",
        )
    )
    fig.update_layout(xaxis={"type": "category", "categoryorder": "array", "categoryarray": x_labels}, xaxis_title=None, yaxis_title=None)
    fig.update_xaxes(tickfont={"size": 10}, automargin=True)
    fig.update_yaxes(tickfont={"size": 11}, automargin=True)
    fig.update_yaxes(autorange="reversed")
    return themed_layout(fig, theme)


def area_profile_panel(area_data: pd.DataFrame, selected_area: int, metric: str, year: int | str, crime_type: str) -> html.Section:
    if selected_area == 0:
        top = area_data.sort_values(metric, ascending=False).head(1)
        title = "All Community Areas"
        detail = f"{METRIC_LABELS[metric]}, {year_label(year)}"
        context = "Stats show the top area for this map metric."
        selected = top.iloc[0] if not top.empty else None
    else:
        selected_rows = area_data[area_data["community_area"] == selected_area]
        title = selected_rows["community_name"].iloc[0] if not selected_rows.empty else "Selected Area"
        detail = f"{crime_type}, {year_label(year)}"
        context = "Selected community profile for the active filters."
        selected = selected_rows.iloc[0] if not selected_rows.empty else None

    if selected is None:
        metrics = [html.P("No data available for the selected filters.", className="profile-context")]
    else:
        rank_column = {"incidents": "incident_rank", "incidents_per_100k": "per_100k_rank", "arrest_rate": "arrest_rate_rank"}[metric]
        metrics = [
            html.Div([html.Span("Incidents"), html.Strong(format_number(selected["incidents"]))], className="profile-stat"),
            html.Div([html.Span("Arrest rate"), html.Strong(format_percent(selected["arrest_rate"]))], className="profile-stat"),
            html.Div([html.Span("Per 100k"), html.Strong(format_number(selected["incidents_per_100k"]))], className="profile-stat"),
            html.Div([html.Span("Metric rank"), html.Strong(f"#{int(selected[rank_column])} of 77")], className="profile-stat"),
        ]

    return html.Section(
        className="panel geo-profile geo-profile-compact",
        children=[
            html.Div([html.H3(title), html.P(detail)], className="panel-header profile-header"),
            html.P(context, className="profile-context"),
            html.Div(metrics, className="profile-stats"),
            html.P("Tip: filter for a fixed profile, or click the map when viewing All Community Areas.", className="profile-tip"),
        ],
    )


def area_trend_figure(year: int | str, crime_type: str, selected_area: int, theme: str) -> go.Figure:
    data = community_counts[community_counts["primary_type"] == crime_type].copy()
    if selected_area:
        data = data[data["community_area"] == selected_area]
    trend = data.groupby("year", as_index=False)[["incidents", "arrests"]].sum()
    trend["arrest_rate"] = (trend["arrests"] / trend["incidents"] * 100).round(2)
    primary = "#7bd0ff" if theme == "dark" else "#00668a"
    accent = "#ffb960" if theme == "dark" else "#f1a02b"
    fig = go.Figure()
    fig.add_scatter(x=trend["year"], y=trend["incidents"], mode="lines+markers", name="Incidents", line={"color": primary, "width": 3})
    fig.add_scatter(x=trend["year"], y=trend["arrest_rate"], mode="lines+markers", yaxis="y2", name="Arrest rate", line={"color": accent, "width": 2})
    fig.update_layout(
        xaxis={"dtick": 1, "title": None},
        yaxis={"title": "Incidents"},
        yaxis2={"title": "Arrest %", "overlaying": "y", "side": "right", "ticksuffix": "%"},
        legend={"orientation": "h", "y": 1.02, "x": 0, "xanchor": "left", "yanchor": "bottom"},
    )
    return themed_layout(fig, theme, margin=dict(l=48, r=48, t=4, b=28))


def selected_month_window(trend_range: list[int] | None) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    range_start_index, range_end_index = trend_range or [0, len(MONTH_STARTS) - 1]
    range_start_index = max(0, min(int(range_start_index), len(MONTH_STARTS) - 1))
    range_end_index = max(range_start_index, min(int(range_end_index), len(MONTH_STARTS) - 1))
    trend_start = MONTH_STARTS[range_start_index]
    trend_end_month = MONTH_STARTS[range_end_index]
    axis_start = max(trend_start, ANALYSIS_START)
    axis_end = min(trend_end_month + pd.offsets.MonthEnd(0), ANALYSIS_END)
    return trend_start, trend_end_month, axis_start, axis_end


def filtered_monthly_trend(year: int | str, crime_type: str, trend_range: list[int] | None) -> pd.DataFrame:
    trend_start, trend_end_month, _, _ = selected_month_window(trend_range)
    data = monthly[monthly["primary_type"] == crime_type].copy()
    if not is_all_years(year):
        data = data[data["year"] == int(year)]
    data = data[(data["month"] >= trend_start) & (data["month"] <= trend_end_month)].sort_values("month")
    return data


def trend_insight_cards(year: int | str, crime_type: str, trend_range: list[int] | None) -> list[html.Div]:
    data = filtered_monthly_trend(year, crime_type, trend_range)
    if data.empty:
        return [
            kpi_card("Trend Window", "No Data", f"{crime_type}, {year_label(year)}", "query_stats"),
            kpi_card("Peak Month", "N/A", "No matching months", "calendar_month"),
            kpi_card("Lowest Month", "N/A", "No matching months", "event_busy"),
            kpi_card("Net Change", "N/A", "Adjust the year or range", "trending_flat"),
        ]

    peak = data.loc[data["incidents"].idxmax()]
    low = data.loc[data["incidents"].idxmin()]
    first = int(data.iloc[0]["incidents"])
    last = int(data.iloc[-1]["incidents"])
    change = last - first
    change_pct = change / first * 100 if first else 0
    avg_month = int(round(data["incidents"].mean()))
    trend_class = "bad" if change > 0 else "good"
    trend_label = f"{'Up' if change >= 0 else 'Down'} {abs(change_pct):.1f}%"

    return [
        kpi_card("Monthly Average", format_number(avg_month), f"{crime_type}, {year_label(year)}", "monitoring"),
        kpi_card("Peak Month", peak["month"].strftime("%b %Y"), f"{format_number(peak['incidents'])} incidents", "calendar_month"),
        kpi_card("Lowest Month", low["month"].strftime("%b %Y"), f"{format_number(low['incidents'])} incidents", "event_busy"),
        kpi_card("Net Change", format_number(abs(change)), "First to last visible month", "trending_up" if change >= 0 else "trending_down", trend_label, trend_class),
    ]


def trend_detail_figure(year: int | str, crime_type: str, trend_range: list[int] | None, theme: str) -> go.Figure:
    data = filtered_monthly_trend(year, crime_type, trend_range)
    _, _, axis_start, axis_end = selected_month_window(trend_range)
    primary = "#7bd0ff" if theme == "dark" else "#00668a"
    accent = "#ffb960" if theme == "dark" else "#f1a02b"
    fig = go.Figure()

    if not data.empty:
        data = data.copy()
        data["rolling_avg"] = data["incidents"].rolling(3, min_periods=1).mean()
        fig.add_scatter(x=data["month"], y=data["incidents"], mode="lines+markers", name="Monthly incidents", line={"color": primary, "width": 2}, marker={"size": 6}, hovertemplate="%{x|%b %Y}<br>%{y:,} incidents<extra></extra>")
        fig.add_scatter(x=data["month"], y=data["rolling_avg"], mode="lines", name="3-month moving average", line={"color": accent, "width": 4}, hovertemplate="%{x|%b %Y}<br>%{y:,.0f} avg incidents<extra></extra>")

    fig.update_layout(
        xaxis_title=None,
        yaxis_title="Incidents",
        xaxis={"range": [axis_start, axis_end]},
        legend={"orientation": "h", "y": 1.02, "x": 0, "xanchor": "left", "yanchor": "bottom"},
    )
    return themed_layout(fig, theme, margin=dict(l=50, r=18, t=4, b=30))


def year_over_year_figure(year: int | str, crime_type: str, trend_range: list[int] | None, theme: str) -> go.Figure:
    trend_start, trend_end_month, _, _ = selected_month_window(trend_range)
    data = monthly[monthly["primary_type"] == crime_type].copy()
    data = data[(data["month"] >= trend_start) & (data["month"] <= trend_end_month)]
    if not is_all_years(year):
        selected_year = int(year)
        comparison_years = [selected_year - 1, selected_year] if selected_year > min(YEARS) else [selected_year]
        data = data[data["year"].isin(comparison_years)]

    fig = go.Figure()
    for series_year in sorted(data["year"].dropna().unique()):
        year_data = data[data["year"] == series_year].sort_values("month_num")
        fig.add_scatter(
            x=year_data["month_num"],
            y=year_data["incidents"],
            mode="lines+markers",
            name=str(int(series_year)),
            hovertemplate="%{text} %{fullData.name}<br>%{y:,} incidents<extra></extra>",
            text=[MONTH_LABELS[int(month) - 1] for month in year_data["month_num"]],
        )

    fig.update_layout(
        xaxis={"tickmode": "array", "tickvals": list(range(1, 13)), "ticktext": MONTH_LABELS, "title": None},
        yaxis_title="Incidents",
        legend={"orientation": "h", "y": 1.02, "x": 0, "xanchor": "left", "yanchor": "bottom"},
    )
    return themed_layout(fig, theme, margin=dict(l=46, r=12, t=4, b=30))


def seasonality_figure(year: int | str, crime_type: str, trend_range: list[int] | None, theme: str) -> go.Figure:
    data = filtered_monthly_trend(year, crime_type, trend_range)
    primary = "#7bd0ff" if theme == "dark" else "#00668a"
    accent = "#ffb960" if theme == "dark" else "#f1a02b"
    seasonal = data.groupby("month_num", as_index=False)["incidents"].mean()
    seasonal["month_label"] = seasonal["month_num"].apply(lambda value: MONTH_LABELS[int(value) - 1])
    fig = px.bar(seasonal, x="month_label", y="incidents", color="incidents", color_continuous_scale=[primary, accent])
    fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f} avg incidents<extra></extra>")
    fig.update_layout(xaxis_title=None, yaxis_title="Average monthly incidents", coloraxis_showscale=False)
    return themed_layout(fig, theme, margin=dict(l=52, r=12, t=4, b=30))


def compact_overview_figure(fig: go.Figure, kind: str) -> go.Figure:
    margins = {
        "trend": dict(l=42, r=12, t=4, b=26),
        "heatmap": dict(l=34, r=8, t=4, b=22),
        "annual": dict(l=42, r=44, t=4, b=24),
        "bar": dict(l=112, r=20, t=4, b=28),
        "map": dict(l=0, r=0, t=0, b=0),
    }
    fig.update_layout(margin=margins.get(kind, dict(l=20, r=20, t=4, b=24)))
    if kind == "annual":
        fig.update_layout(legend={"orientation": "h", "y": 1.02, "x": 0, "xanchor": "left", "yanchor": "bottom"}, yaxis2={"title": "Arrest %", "overlaying": "y", "side": "right", "ticksuffix": "%"})
    if kind == "map":
        fig.update_layout(coloraxis_colorbar={"thickness": 12, "len": 0.72, "x": 1.0})
    return fig


app.layout = html.Div(
    id="app-root",
    className="app-shell theme-light",
    children=[
        dcc.Store(id="theme-store", data="light"),
        dcc.Store(id="active-view", data="overview"),
        dcc.Download(id="export-download"),
        html.Aside(
            className="sidebar",
            children=[
                html.Div(
                    className="brand",
                    children=[
                        html.Div(material_icon("location_city"), className="brand-mark skyline-mark"),
                        html.Div([html.H1("Crime Patterns"), html.P("Chicago public data")]),
                    ],
                ),
                html.Div(
                    className="nav-links",
                    children=[
                        html.Button([material_icon("dashboard"), html.Span("Overview")], id="nav-overview", className="nav-link active", type="button"),
                        html.Button([material_icon("map"), html.Span("Geospatial Explorer")], id="nav-geo", className="nav-link", type="button"),
                        html.Button([material_icon("query_stats"), html.Span("Trend Analytics")], id="nav-trends", className="nav-link", type="button"),
                    ],
                ),
                html.Section(
                    className="sidebar-range-panel panel",
                    children=[
                        html.Div([html.H3("Analysis Window"), html.P("Shared month range")], className="panel-header range-header"),
                        trend_slider(),
                    ],
                ),
                html.Section(
                    className="sidebar-scope-panel panel",
                    children=[
                        html.Div("Data Scope", className="scope-title"),
                        html.Div(
                            className="scope-grid",
                            children=[
                                html.Div([html.Strong("2021-2025"), html.Span("reported years")]),
                                html.Div([html.Strong(str(COMMUNITY_AREA_COUNT)), html.Span("community areas")]),
                                html.Div([html.Strong("Public data"), html.Span("reported incidents")]),
                            ],
                        ),
                    ],
                ),
                html.Div(
                    className="sidebar-actions",
                    children=[
                        html.Button(
                            [
                                html.Span("light_mode", id="theme-icon", className="material-symbols-outlined", **{"aria-hidden": "true"}),
                                html.Span("Dark mode", id="theme-label", className="theme-toggle-label"),
                            ],
                            id="theme-toggle",
                            className="theme-toggle",
                            type="button",
                            title="Switch to dark mode",
                            **{"aria-label": "Switch to dark mode"},
                        ),
                        html.Button([material_icon("download"), html.Span("Export CSV")], id="export-button", className="primary-button", type="button"),
                    ],
                ),
            ],
        ),
        html.Div(
            className="content-shell",
            children=[
                html.Header(
                    className="topbar",
                    children=[
                        html.Div([html.H2("Chicago Crime Patterns Explorer", id="page-title"), html.P("Reported incidents, 2021-2025", id="page-subtitle")], className="topbar-title"),
                        html.Section(
                            className="topbar-filter-panel",
                            children=[
                                html.Div([html.Label("Year"), dcc.Dropdown(YEAR_OPTIONS, "all", id="year-filter", clearable=False, className="theme-dropdown")]),
                                html.Div([html.Label("Crime Type"), dcc.Dropdown(CRIME_TYPE_OPTIONS, "All Types", id="crime-filter", clearable=False, className="theme-dropdown")]),
                                html.Div([html.Label("Community Area"), dcc.Dropdown(COMMUNITY_OPTIONS, 0, id="area-filter", clearable=False, className="theme-dropdown")]),
                                html.Div([html.Label("Map Metric"), dcc.Dropdown(METRICS, "incidents", id="metric-filter", clearable=False, className="theme-dropdown")]),
                            ],
                        ),
                    ],
                ),
                html.Main(
                    className="dashboard-main",
                    children=[
                        html.Div(
                            id="overview-view",
                            className="overview-dense-view",
                            children=[
                                html.Section(id="kpi-grid", className="kpi-grid overview-kpi-strip"),
                                html.Section(
                                    className="overview-dense-grid overview-reference-layout",
                                    children=[
                                        html.Div(
                                            className="overview-feature-row",
                                            children=[
                                                card("Spatial Density: Community Areas", "Community-area choropleth from Chicago Data Portal boundaries", "community-map", "map-panel dense-panel overview-map-panel"),
                                                card(
                                                    "Ranked Categories & Arrest Rates",
                                                    "Top reported categories by volume; color shows arrest rate",
                                                    "category-bars",
                                                    "wide-panel dense-panel overview-ranked-panel",
                                                    header_extra=html.Div(id="category-color-key", className="category-color-key"),
                                                ),
                                            ],
                                        ),
                                        html.Div(
                                            className="overview-bottom-row",
                                            children=[
                                                card("Monthly Reported Incidents", "Selected crime type across the active analysis window", "monthly-trend", "trend-panel dense-panel"),
                                                card(
                                                    "Day and Hour Pattern",
                                                    "Reported incidents by weekday and 4-hour time band",
                                                    "day-hour-heatmap",
                                                    "heatmap-panel dense-panel",
                                                    header_extra=html.Div(id="day-hour-color-key", className="day-hour-color-key color-key"),
                                                ),
                                                card("Annual Outcomes", "2021-2025 reported incidents and arrest rate for the selected filters", "annual-outcomes", "annual-panel dense-panel"),
                                            ],
                                        ),
                                    ],
                                ),
                                html.Section(
                                    className="methodology-panel panel",
                                    children=[
                                        html.Div(
                                            className="panel-header",
                                            children=[
                                                html.Div(
                                                    [
                                                        html.H3("Methodology and Limitations"),
                                                        html.P("This dashboard uses aggregated reported incidents from the Chicago Data Portal. Counts are not a measure of all crime, and per-capita rates use ACS community-area population estimates."),
                                                    ]
                                                )
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            id="trend-view",
                            className="trend-dense-view",
                            style={"display": "none"},
                            children=[
                                html.Section(id="trend-insights", className="kpi-grid trend-insights trend-dense-kpis"),
                                html.Section(
                                    className="trend-analytics-grid trend-dense-grid",
                                    children=[
                                        card("Monthly Trend Detail", "Monthly incidents with a 3-month moving average", "trend-detail", "trend-detail-panel dense-panel"),
                                        html.Div(
                                            className="trend-side-stack",
                                            children=[
                                                card("Year-over-Year Comparison", "Monthly pattern comparison by calendar year", "trend-yoy", "trend-yoy-panel dense-panel"),
                                                card("Seasonality Profile", "Average incidents by month in the selected window", "trend-seasonality", "trend-seasonality-panel dense-panel"),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                        html.Div(
                            id="geospatial-view",
                            className="geospatial-dense-view",
                            style={"display": "none"},
                            children=[
                                html.Section(
                                    className="geo-layout geospatial-dense-grid",
                                    children=[
                                        card("Geospatial Explorer", "Large community-area map for focused spatial comparison", "geo-map", "geo-map-panel dense-panel"),
                                        html.Div(
                                            className="geo-side-stack",
                                            children=[
                                                html.Div(id="geo-profile"),
                                                card("Community Area Ranking", "Top areas by selected map metric", "geo-ranked", "geo-ranked-panel dense-panel"),
                                                card("Selected Area Trend", "Incidents and arrest rate over time", "geo-area-trend", "geo-trend-panel dense-panel"),
                                            ],
                                        ),
                                    ],
                                ),
                            ],
                        ),
                    ],
                ),
                html.Footer(
                    className="footer",
                    children=[
                        html.P("Analysis range: Jan. 1, 2021 through Dec. 31, 2025. Reported incidents only; 2026 is excluded."),
                        html.Div(
                            children=[
                                html.A("Crime Data", href="https://data.cityofchicago.org/d/ijzp-q8t2", target="_blank", rel="noopener noreferrer"),
                                html.A("Boundaries", href="https://data.cityofchicago.org/d/igwz-8jzy", target="_blank", rel="noopener noreferrer"),
                                html.A("ACS Estimates", href="https://data.cityofchicago.org/d/t68z-cikk", target="_blank", rel="noopener noreferrer"),
                                html.A(
                                    "GitHub Repo",
                                    href=GITHUB_REPO_URL or "#",
                                    target="_blank" if GITHUB_REPO_URL else None,
                                    rel="noopener noreferrer" if GITHUB_REPO_URL else None,
                                    className="pending-link" if not GITHUB_REPO_URL else None,
                                    title="Add GITHUB_REPO_URL after creating the public repository" if not GITHUB_REPO_URL else "View project repository",
                                    style={} if GITHUB_REPO_URL else {"display": "none"},
                                ),
                            ]
                        ),
                    ],
                ),
            ],
        ),
    ],
)


clientside_callback(
    """
    function(nClicks, currentTheme) {
        const nextTheme = nClicks && nClicks % 2 === 1 ? "dark" : "light";
        const isDark = nextTheme === "dark";
        const label = isDark ? "Light mode" : "Dark mode";
        const title = isDark ? "Switch to light mode" : "Switch to dark mode";
        return [
            "app-shell theme-" + nextTheme,
            isDark ? "dark_mode" : "light_mode",
            label,
            title,
            nextTheme
        ];
    }
    """,
    Output("app-root", "className"),
    Output("theme-icon", "children"),
    Output("theme-label", "children"),
    Output("theme-toggle", "title"),
    Output("theme-store", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme-store", "data"),
)


@app.callback(
    Output("active-view", "data"),
    Input("nav-overview", "n_clicks"),
    Input("nav-geo", "n_clicks"),
    Input("nav-trends", "n_clicks"),
    prevent_initial_call=True,
)
def set_active_view(_overview_clicks: int | None, _geo_clicks: int | None, _trend_clicks: int | None) -> str:
    if ctx.triggered_id == "nav-geo":
        return "geospatial"
    if ctx.triggered_id == "nav-trends":
        return "trends"
    return "overview"


@app.callback(
    Output("overview-view", "style"),
    Output("geospatial-view", "style"),
    Output("trend-view", "style"),
    Output("nav-overview", "className"),
    Output("nav-geo", "className"),
    Output("nav-trends", "className"),
    Output("page-title", "children"),
    Output("page-subtitle", "children"),
    Input("active-view", "data"),
)
def render_active_view(active_view: str):
    is_geo = active_view == "geospatial"
    is_trends = active_view == "trends"
    if is_geo:
        title = "Geospatial Explorer"
        subtitle = "Compare community areas by count, rate, and arrest outcomes"
    elif is_trends:
        title = "Trend Analytics"
        subtitle = "Explore monthly movement, seasonality, and year-over-year patterns"
    else:
        title = "Chicago Crime Patterns Explorer"
        subtitle = "Reported incidents, 2021-2025"
    return (
        {} if not is_geo and not is_trends else {"display": "none"},
        {} if is_geo else {"display": "none"},
        {} if is_trends else {"display": "none"},
        "nav-link active" if not is_geo and not is_trends else "nav-link",
        "nav-link active" if is_geo else "nav-link",
        "nav-link active" if is_trends else "nav-link",
        title,
        subtitle,
    )


@app.callback(
    Output("kpi-grid", "children"),
    Output("monthly-trend", "figure"),
    Output("category-bars", "figure"),
    Output("category-color-key", "children"),
    Output("community-map", "figure"),
    Output("day-hour-heatmap", "figure"),
    Output("day-hour-color-key", "children"),
    Output("annual-outcomes", "figure"),
    Input("year-filter", "value"),
    Input("crime-filter", "value"),
    Input("area-filter", "value"),
    Input("metric-filter", "value"),
    Input("theme-store", "data"),
    Input("trend-range", "value"),
)
def update_dashboard(year: int | str, crime_type: str, community_area: int, metric: str, theme: str, trend_range: list[int]):
    primary = "#7bd0ff" if theme == "dark" else "#00668a"
    accent = "#ffb960" if theme == "dark" else "#f1a02b"
    heatmap_low = "#12212a" if theme == "dark" else "#eef4f7"
    heatmap_high = accent
    map_style = "carto-darkmatter" if theme == "dark" else "carto-positron"

    trend_start, trend_end_month, axis_start, axis_end = selected_month_window(trend_range)

    trend_data = monthly[monthly["primary_type"] == crime_type].copy()
    if not is_all_years(year):
        trend_data = trend_data[trend_data["year"] == int(year)]
        year_start = pd.Timestamp(f"{int(year)}-01-01")
        year_end = pd.Timestamp(f"{int(year)}-12-31")
        if max(axis_start, year_start) <= min(axis_end, year_end):
            axis_start = max(axis_start, year_start)
            axis_end = min(axis_end, year_end)
    trend_data = trend_data[(trend_data["month"] >= trend_start) & (trend_data["month"] <= trend_end_month)]
    trend_data = trend_data.sort_values("month")
    trend_fig = px.line(trend_data, x="month", y="incidents", markers=False)
    trend_fig.update_traces(line={"color": primary, "width": 3}, hovertemplate="%{x|%b %Y}<br>%{y:,} incidents<extra></extra>")
    trend_fig.update_layout(
        xaxis_title=None,
        yaxis_title="Incidents",
        xaxis={
            "range": [axis_start, axis_end],
            "rangeselector": None,
        },
    )
    trend_fig = themed_layout(trend_fig, theme)
    trend_fig = compact_overview_figure(trend_fig, "trend")

    bar_data = by_year(community_counts, year)
    bar_data = bar_data[bar_data["primary_type"] != "All Types"].copy()
    if community_area:
        bar_data = bar_data[bar_data["community_area"] == community_area]
    bar_data = bar_data.groupby("primary_type", as_index=False)[["incidents", "arrests"]].sum()
    bar_data["arrest_rate"] = (bar_data["arrests"] / bar_data["incidents"] * 100).round(2)
    # Dense layout test: previous versions used horizontal bars, then a Plotly Express coloraxis.
    bar_data = bar_data.sort_values("incidents", ascending=False).head(8)
    category_labels = [str(value) for value in bar_data["primary_type"].tolist()]
    incident_values = [int(value) for value in bar_data["incidents"].tolist()]
    arrest_rate_values = [float(value) for value in bar_data["arrest_rate"].tolist()]
    bar_colors = arrest_rate_colors(arrest_rate_values, primary, accent)
    color_key = category_color_key(arrest_rate_values, primary, accent)
    ranked_rows = list(zip(category_labels, incident_values, arrest_rate_values, bar_colors))
    ranked_rows.reverse()
    bar_fig = go.Figure(
        data=[
            go.Bar(
                x=[row[1] for row in ranked_rows],
                y=[row[0] for row in ranked_rows],
                orientation="h",
                marker={"color": [row[3] for row in ranked_rows], "line": {"color": "rgba(25, 28, 30, 0.18)", "width": 1}},
                customdata=[row[2] for row in ranked_rows],
                text=[f"{row[2]:.1f}%" for row in ranked_rows],
                textposition="auto",
                cliponaxis=False,
                hovertemplate="%{y}<br>%{x:,} reported incidents<br>%{customdata:.1f}% arrest rate<extra></extra>",
            )
        ]
    )
    bar_fig.update_layout(xaxis_title="Incidents", yaxis_title=None, bargap=0.24, showlegend=False)
    bar_fig.update_xaxes(tickfont={"size": 10}, automargin=True)
    bar_fig.update_yaxes(tickfont={"size": 10}, automargin=True)
    bar_fig = themed_layout(bar_fig, theme)
    bar_fig = compact_overview_figure(bar_fig, "bar")

    map_data = aggregate_area_data(year, crime_type)
    map_fig = px.choropleth_map(
        map_data,
        geojson=community_geojson,
        locations="community_area_str",
        featureidkey="properties.area_num_1",
        color=metric,
        hover_name="community_name",
        hover_data={"community_area_str": False, "incidents": ":,", "arrest_rate": ":.1f", "incidents_per_100k": ":.1f"},
        color_continuous_scale=["#c4e7ff", primary, accent],
        center={"lat": 41.84, "lon": -87.68},
        zoom=9.2,
        opacity=0.78,
        map_style=map_style,
    )
    map_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor="rgba(0,0,0,0)", font_color="#eff1f3" if theme == "dark" else "#191c1e", coloraxis_colorbar_title=METRIC_LABELS[metric])
    map_fig = compact_overview_figure(map_fig, "map")

    annual_data = filtered_annual_outcomes(year, crime_type, community_area)
    annual_colors = [accent if selected else primary for selected in annual_data["selected"]]
    annual_fig = go.Figure()
    annual_fig.add_bar(x=annual_data["year"], y=annual_data["incidents"], name="Incidents", marker_color=annual_colors, customdata=annual_data[["incident_label", "arrest_rate_label"]], hovertemplate="%{x}<br>%{customdata[0]} reported incidents<br>%{customdata[1]} arrest rate<extra></extra>")
    annual_fig.add_scatter(x=annual_data["year"], y=annual_data["arrest_rate"], name="Arrest rate", mode="lines+markers", yaxis="y2", line={"color": accent, "width": 3}, marker={"size": 8}, hovertemplate="%{x}<br>%{y:.1f}% arrest rate<extra></extra>")
    annual_fig.update_layout(xaxis={"dtick": 1, "title": None}, yaxis={"title": "Incidents"}, yaxis2={"title": "Arrest %", "overlaying": "y", "side": "right", "ticksuffix": "%"}, legend={"orientation": "h", "y": 1.12, "x": 0}, bargap=0.35)
    annual_fig = themed_layout(annual_fig, theme)
    annual_fig = compact_overview_figure(annual_fig, "annual")

    heatmap_fig = compact_overview_figure(heatmap_figure(year, crime_type, community_area, theme), "heatmap")
    day_hour_key = heatmap_color_key(year, crime_type, community_area, heatmap_low, heatmap_high)

    return kpis_for_selection(year, crime_type, community_area), trend_fig, bar_fig, color_key, map_fig, heatmap_fig, day_hour_key, annual_fig


@app.callback(
    Output("trend-insights", "children"),
    Output("trend-detail", "figure"),
    Output("trend-yoy", "figure"),
    Output("trend-seasonality", "figure"),
    Input("year-filter", "value"),
    Input("crime-filter", "value"),
    Input("theme-store", "data"),
    Input("trend-range", "value"),
)
def update_trend_analytics(year: int | str, crime_type: str, theme: str, trend_range: list[int]):
    return (
        trend_insight_cards(year, crime_type, trend_range),
        trend_detail_figure(year, crime_type, trend_range, theme),
        year_over_year_figure(year, crime_type, trend_range, theme),
        seasonality_figure(year, crime_type, trend_range, theme),
    )


@app.callback(
    Output("geo-map", "figure"),
    Output("geo-ranked", "figure"),
    Output("geo-area-trend", "figure"),
    Output("geo-profile", "children"),
    Input("year-filter", "value"),
    Input("crime-filter", "value"),
    Input("area-filter", "value"),
    Input("metric-filter", "value"),
    Input("geo-map", "clickData"),
    Input("theme-store", "data"),
)
def update_geospatial(year: int | str, crime_type: str, community_area: int, metric: str, click_data: dict | None, theme: str):
    primary = "#7bd0ff" if theme == "dark" else "#00668a"
    accent = "#ffb960" if theme == "dark" else "#f1a02b"
    map_style = "carto-darkmatter" if theme == "dark" else "carto-positron"
    selected_area = selected_area_from_click(click_data, community_area)
    area_data = aggregate_area_data(year, crime_type)

    geo_map = px.choropleth_map(
        area_data,
        geojson=community_geojson,
        locations="community_area_str",
        featureidkey="properties.area_num_1",
        color=metric,
        hover_name="community_name",
        hover_data={"community_area_str": False, "incidents": ":,", "arrest_rate": ":.1f", "incidents_per_100k": ":.1f", "incident_rank": True},
        color_continuous_scale=["#c4e7ff", primary, accent],
        center={"lat": 41.84, "lon": -87.68},
        zoom=9.35,
        opacity=0.82,
        map_style=map_style,
    )
    geo_map.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#eff1f3" if theme == "dark" else "#191c1e",
        coloraxis_colorbar_title=METRIC_LABELS[metric],
        coloraxis_colorbar={"thickness": 12, "len": 0.72, "x": 1.0},
    )

    rank = area_data.sort_values(metric, ascending=False).head(15).sort_values(metric)
    ranked_fig = px.bar(rank, x=metric, y="community_name", orientation="h", color=metric, color_continuous_scale=[primary, accent], hover_data={"incidents": ":,", "arrest_rate": ":.1f", "incidents_per_100k": ":.1f"})
    ranked_fig.update_layout(
        xaxis_title=METRIC_LABELS[metric],
        yaxis_title=None,
        yaxis={
            "tickmode": "array",
            "tickvals": rank["community_name"],
            "ticktext": rank["community_name"],
            "tickfont": {"size": 9},
        },
        coloraxis_showscale=False,
        bargap=0.16,
    )
    ranked_fig = themed_layout(ranked_fig, theme, margin=dict(l=128, r=10, t=2, b=26))

    trend_fig = area_trend_figure(year, crime_type, selected_area, theme)
    profile = area_profile_panel(area_data, selected_area, metric, year, crime_type)
    return geo_map, ranked_fig, trend_fig, profile


@app.callback(
    Output("export-download", "data"),
    Input("export-button", "n_clicks"),
    State("year-filter", "value"),
    State("crime-filter", "value"),
    State("area-filter", "value"),
    prevent_initial_call=True,
)
def export_filtered_data(_clicks: int | None, year: int | str, crime_type: str, community_area: int):
    export = export_rows(year, crime_type, int(community_area))
    year_part = "2021-2025" if is_all_years(year) else str(year)
    type_part = re.sub(r"[^a-z0-9]+", "-", str(crime_type).lower()).strip("-")
    scope_part = "all-areas" if not int(community_area) else f"area-{int(community_area)}"
    filename = f"chicago-crime-{year_part}-{type_part}-{scope_part}.csv"
    return dcc.send_data_frame(export.to_csv, filename, index=False)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8050, debug=False)
