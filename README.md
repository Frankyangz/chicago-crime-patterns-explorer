# Chicago Crime Patterns Explorer

This is an interactive Dash dashboard I built to explore reported Chicago crime incidents from 2021 through 2025. The goal was to turn a large public dataset into something easier to scan, compare, and explain: monthly patterns, community-area differences, arrest-rate context, and day/hour reporting behavior.

I treated this as both a data visualization project and a UI/UX exercise. A lot of the work went into making the dashboard feel presentable for a portfolio: reducing clutter, tightening the layout, improving dark mode, making the filters behave consistently, and fitting the main charts into one screen for easier review.

## What the Dashboard Does

- Shows citywide KPIs for reported incidents, arrest rate, most frequent category, and highest-volume community area.
- Maps reported incidents by Chicago community area with selectable metrics.
- Compares ranked crime categories while using color to show arrest-rate differences.
- Shows monthly trends, annual outcomes, and a weekday/hour heatmap.
- Provides focused Geospatial and Trend Analytics pages for deeper comparison.
- Supports light/dark mode, shared filters, an analysis-window slider, and CSV export.

## Why I Built It

Crime data can be easy to misread when it is shown only as raw counts. I wanted this project to practice building a dashboard that is useful but careful: it highlights patterns without implying that reported incidents equal all crime, and it keeps methodology notes close to the analysis.

From a portfolio perspective, this project shows how I think through the full path from data preparation to visual design. I worked on the pipeline, chart logic, layout, interaction states, and final presentation instead of only producing static charts.

## Skills Demonstrated

- Python data cleaning and aggregation with pandas
- Dashboard development with Dash and Plotly
- Geospatial visualization using community-area GeoJSON boundaries
- Interactive filtering across linked charts
- UI layout refinement for dense analytical screens
- Dark mode and custom CSS polish
- Public-data interpretation and methodology communication

## Tech Stack

- Python
- Dash
- Plotly
- pandas
- HTML/CSS
- Chicago Data Portal public datasets

## Quick Start

```bash
pip install -r requirements.txt
cd dashboard
python app.py
```

Open `http://127.0.0.1:8050/` in your browser. The app runs locally only and is not deployed to a public server.

To re-fetch and rebuild all data files from the Chicago Data Portal:

```bash
python src/fetch_prepare_data.py
```

This pulls the latest data from the portal's API and regenerates the CSV and GeoJSON files under `data/`.

## Project Structure

```text
dashboard/         Dash app and UI assets
data/raw/          Source extracts used by the preparation pipeline
data/shared/       Shared dashboard-ready lookup, boundary, and count files
data/processed/    Processed summaries used by charts and KPIs
docs/              Methodology notes and interpretation caveats
src/               Data preparation script
```

## Data Sources

- Chicago Data Portal, Crimes - 2001 to Present: https://data.cityofchicago.org/d/ijzp-q8t2
- Chicago Data Portal, Community Area Boundaries: https://data.cityofchicago.org/d/igwz-8jzy
- Chicago Data Portal, ACS community-area estimates: https://data.cityofchicago.org/d/t68z-cikk

## Methodology Notes

This dashboard uses reported public-data incidents, not a complete measure of all crime. Counts can be affected by reporting behavior, enforcement patterns, data-entry practices, and policy changes. Per-capita estimates use available ACS community-area population estimates, so they should be read as contextual estimates rather than exact risk measures.

The dashboard currently focuses on 2021-2025 data to keep the analysis window consistent across the overview, geospatial, and trend views.

## Limitations

- This is reported crime data, not a complete count of all crime. Unreported incidents are not captured.
- 2025 data is still accumulating and year-over-year comparisons with 2025 should be read with that in mind.
- Per-capita rates use ACS estimates, not a census count, so they are approximations.
- Community-area comparisons can be misleading without context: high-traffic commercial areas may show elevated counts that reflect foot traffic rather than residential safety.
