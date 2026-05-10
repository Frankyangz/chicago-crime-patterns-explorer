from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_SHARED = ROOT / "data" / "shared"
DATA_PROCESSED = ROOT / "data" / "processed"

CRIME_API = "https://data.cityofchicago.org/resource/ijzp-q8t2.json"
ACS_CSV = "https://data.cityofchicago.org/api/views/t68z-cikk/rows.csv?accessType=DOWNLOAD"
IUCR_CSV = "https://data.cityofchicago.org/api/views/c7ck-438e/rows.csv?accessType=DOWNLOAD"
BOUNDARIES_GEOJSON = "https://data.cityofchicago.org/api/geospatial/igwz-8jzy?method=export&format=GeoJSON"

START_DATE = "2021-01-01T00:00:00"
END_DATE = "2026-01-01T00:00:00"
YEARS = [2021, 2022, 2023, 2024, 2025]
DAY_NAMES = {
    0: "Sun",
    1: "Mon",
    2: "Tue",
    3: "Wed",
    4: "Thu",
    5: "Fri",
    6: "Sat",
}
DAY_ORDER = {"Mon": 1, "Tue": 2, "Wed": 3, "Thu": 4, "Fri": 5, "Sat": 6, "Sun": 7}


def ensure_dirs() -> None:
    for directory in (DATA_RAW, DATA_SHARED, DATA_PROCESSED):
        directory.mkdir(parents=True, exist_ok=True)


def socrata_query(query: str) -> pd.DataFrame:
    url = CRIME_API + "?" + urlencode({"$query": query})
    return pd.read_json(url)


def read_csv_url(url: str) -> pd.DataFrame:
    return pd.read_csv(url)


def fetch_geojson(url: str) -> dict:
    with urlopen(url, timeout=60) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def title_case_name(value: str) -> str:
    return " ".join(word.capitalize() for word in str(value).split())


def build_area_lookup(boundaries: dict) -> pd.DataFrame:
    rows = []
    for feature in boundaries["features"]:
        props = feature["properties"]
        area_num = int(props["area_num_1"])
        community_name = title_case_name(props["community"])
        rows.append({"community_area": area_num, "community_name": community_name})
    return pd.DataFrame(rows).sort_values("community_area")


def prepare_population(area_lookup: pd.DataFrame) -> pd.DataFrame:
    acs = read_csv_url(ACS_CSV)
    acs.columns = [c.strip().lower().replace(" ", "_") for c in acs.columns]
    latest_year = int(acs["acs_year"].max())
    population = acs.loc[acs["acs_year"] == latest_year, ["acs_year", "community_area", "total_population"]].copy()
    population["community_name"] = population["community_area"].map(title_case_name)
    population["total_population"] = pd.to_numeric(population["total_population"], errors="coerce")
    population = area_lookup.merge(population[["community_name", "acs_year", "total_population"]], on="community_name", how="left")
    population.to_csv(DATA_SHARED / "acs_community_area_population.csv", index=False)
    acs.to_csv(DATA_RAW / "acs_5_year_by_community_area.csv", index=False)
    return population


def prepare_iucr() -> None:
    iucr = read_csv_url(IUCR_CSV)
    iucr.to_csv(DATA_SHARED / "iucr_codes.csv", index=False)
    iucr.to_csv(DATA_RAW / "iucr_codes_raw.csv", index=False)


def prepare_monthly() -> pd.DataFrame:
    query = f"""
    SELECT date_trunc_ym(date) AS month, primary_type, count(*) AS incidents
    WHERE date >= '{START_DATE}' AND date < '{END_DATE}'
    GROUP BY date_trunc_ym(date), primary_type
    ORDER BY month
    LIMIT 50000
    """
    monthly = socrata_query(query)
    monthly["month"] = pd.to_datetime(monthly["month"])
    monthly["year"] = monthly["month"].dt.year
    monthly["month_num"] = monthly["month"].dt.month
    monthly["primary_type"] = monthly["primary_type"].str.title()
    monthly["incidents"] = pd.to_numeric(monthly["incidents"], errors="coerce").fillna(0).astype(int)

    all_types = monthly.groupby(["month", "year", "month_num"], as_index=False)["incidents"].sum()
    all_types["primary_type"] = "All Types"
    monthly = pd.concat([monthly, all_types], ignore_index=True).sort_values(["month", "primary_type"])
    monthly.to_csv(DATA_SHARED / "monthly_crime_counts.csv", index=False)
    return monthly


def prepare_community_counts(area_lookup: pd.DataFrame, population: pd.DataFrame) -> pd.DataFrame:
    query = f"""
    SELECT year, community_area, primary_type, arrest, count(*) AS incidents
    WHERE date >= '{START_DATE}' AND date < '{END_DATE}' AND community_area IS NOT NULL
    GROUP BY year, community_area, primary_type, arrest
    LIMIT 100000
    """
    counts = socrata_query(query)
    counts["year"] = pd.to_numeric(counts["year"], errors="coerce").astype("Int64")
    counts["community_area"] = pd.to_numeric(counts["community_area"], errors="coerce").astype("Int64")
    counts["primary_type"] = counts["primary_type"].str.title()
    counts["arrest"] = counts["arrest"].astype(bool)
    counts["incidents"] = pd.to_numeric(counts["incidents"], errors="coerce").fillna(0).astype(int)

    grouped = counts.pivot_table(
        index=["year", "community_area", "primary_type"],
        columns="arrest",
        values="incidents",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    grouped.columns.name = None
    if False not in grouped.columns:
        grouped[False] = 0
    if True not in grouped.columns:
        grouped[True] = 0
    grouped = grouped.rename(columns={False: "not_arrests", True: "arrests"})
    grouped["incidents"] = grouped["not_arrests"] + grouped["arrests"]

    all_types = grouped.groupby(["year", "community_area"], as_index=False)[["not_arrests", "arrests", "incidents"]].sum()
    all_types["primary_type"] = "All Types"
    grouped = pd.concat([grouped, all_types], ignore_index=True)

    grouped = grouped.merge(area_lookup, on="community_area", how="left")
    grouped = grouped.merge(population[["community_area", "acs_year", "total_population"]], on="community_area", how="left")
    grouped["arrest_rate"] = (grouped["arrests"] / grouped["incidents"] * 100).round(2)
    grouped["incidents_per_100k"] = (grouped["incidents"] / grouped["total_population"] * 100000).round(2)
    grouped.to_csv(DATA_SHARED / "community_area_yearly_counts.csv", index=False)

    top = grouped.groupby(["year", "primary_type"], as_index=False)[["incidents", "arrests"]].sum()
    top = top.loc[top["primary_type"] != "All Types"].copy()
    top["arrest_rate"] = (top["arrests"] / top["incidents"] * 100).round(2)
    top.to_csv(DATA_PROCESSED / "top_crime_types_by_year.csv", index=False)

    return grouped


def prepare_heatmap(area_lookup: pd.DataFrame) -> pd.DataFrame:
    query = f"""
    SELECT year, community_area, primary_type, date_extract_dow(date) AS day_num, date_extract_hh(date) AS hour, count(*) AS incidents
    WHERE date >= '{START_DATE}' AND date < '{END_DATE}'
    GROUP BY year, community_area, primary_type, date_extract_dow(date), date_extract_hh(date)
    LIMIT 500000
    """
    heat = socrata_query(query)
    heat["year"] = pd.to_numeric(heat["year"], errors="coerce").astype("Int64")
    heat["community_area"] = pd.to_numeric(heat["community_area"], errors="coerce").astype("Int64")
    heat["day_num"] = pd.to_numeric(heat["day_num"], errors="coerce").astype(int)
    heat["hour"] = pd.to_numeric(heat["hour"], errors="coerce").astype(int)
    heat["primary_type"] = heat["primary_type"].str.title()
    heat["incidents"] = pd.to_numeric(heat["incidents"], errors="coerce").fillna(0).astype(int)
    heat["day"] = heat["day_num"].map(DAY_NAMES)
    heat["day_order"] = heat["day"].map(DAY_ORDER)
    heat["hour_band_start"] = (heat["hour"] // 4) * 4
    heat["hour_band"] = heat["hour_band_start"].map(lambda h: f"{h:02d}-{h + 4:02d}")

    area_heat = heat.dropna(subset=["community_area"]).copy()
    area_heat["community_area"] = area_heat["community_area"].astype(int)
    area_heat = area_heat.merge(area_lookup, on="community_area", how="left")
    area_heat = area_heat.groupby(
        ["year", "primary_type", "community_area", "community_name", "day", "day_order", "hour_band", "hour_band_start"],
        as_index=False,
    )["incidents"].sum()

    area_all_types = area_heat.groupby(
        ["year", "community_area", "community_name", "day", "day_order", "hour_band", "hour_band_start"],
        as_index=False,
    )["incidents"].sum()
    area_all_types["primary_type"] = "All Types"

    citywide = heat.groupby(
        ["year", "primary_type", "day", "day_order", "hour_band", "hour_band_start"],
        as_index=False,
    )["incidents"].sum()
    citywide["community_area"] = 0
    citywide["community_name"] = "All Community Areas"

    citywide_all_types = citywide.groupby(
        ["year", "community_area", "community_name", "day", "day_order", "hour_band", "hour_band_start"],
        as_index=False,
    )["incidents"].sum()
    citywide_all_types["primary_type"] = "All Types"

    banded = pd.concat([area_heat, area_all_types, citywide, citywide_all_types], ignore_index=True)
    banded = banded[
        ["year", "primary_type", "community_area", "community_name", "day", "day_order", "hour_band", "hour_band_start", "incidents"]
    ].sort_values(["year", "community_area", "primary_type", "day_order", "hour_band_start"])

    banded.to_csv(DATA_PROCESSED / "day_hour_heatmap.csv", index=False)
    return banded

def prepare_kpi_summary(community_counts: pd.DataFrame) -> None:
    city = community_counts.loc[community_counts["primary_type"] == "All Types"].copy()
    yearly = city.groupby("year", as_index=False)[["incidents", "arrests"]].sum()
    yearly["arrest_rate"] = (yearly["arrests"] / yearly["incidents"] * 100).round(2)
    yearly = yearly.sort_values("year")
    yearly["yoy_change_pct"] = yearly["incidents"].pct_change().mul(100).round(2)
    yearly.to_csv(DATA_PROCESSED / "kpi_summary.csv", index=False)


def update_project_plan_boundary_id() -> None:
    plan_path = ROOT / "project_plan.md"
    if not plan_path.exists():
        return
    text = plan_path.read_text(encoding="utf-8")
    text = text.replace("Dataset ID: `cauq-8yn6`", "Dataset ID: `igwz-8jzy`")
    text = text.replace("https://data.cityofchicago.org/d/cauq-8yn6", "https://data.cityofchicago.org/d/igwz-8jzy")
    text = text.replace("https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Community-Areas-current-/cauq-8yn6/about", "https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Community-Areas-current-/igwz-8jzy/about")
    text = text.replace("https://data.cityofchicago.org/api/geospatial/cauq-8yn6?method=export&format=GeoJSON", BOUNDARIES_GEOJSON)
    plan_path.write_text(text, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    boundaries = fetch_geojson(BOUNDARIES_GEOJSON)
    (DATA_SHARED / "community_area_boundaries.geojson").write_text(json.dumps(boundaries), encoding="utf-8")
    area_lookup = build_area_lookup(boundaries)
    area_lookup.to_csv(DATA_SHARED / "community_area_lookup.csv", index=False)

    population = prepare_population(area_lookup)
    prepare_iucr()
    monthly = prepare_monthly()
    community_counts = prepare_community_counts(area_lookup, population)
    heat = prepare_heatmap(area_lookup)
    prepare_kpi_summary(community_counts)
    update_project_plan_boundary_id()

    summary = {
        "monthly_rows": len(monthly),
        "community_count_rows": len(community_counts),
        "heatmap_rows": len(heat),
        "community_areas": len(area_lookup),
        "analysis_years": YEARS,
        "boundary_dataset_id": "igwz-8jzy",
    }
    (DATA_PROCESSED / "pipeline_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
