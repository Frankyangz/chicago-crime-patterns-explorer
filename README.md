# Chicago Crime Patterns Explorer

An interactive civic analytics dashboard for exploring reported Chicago crime patterns from 2021 through 2025. The project turns public incident data into a portfolio-ready Dash application with spatial comparison, trend analysis, day/hour behavior, arrest-rate context, and exportable filtered data.

## Portfolio Focus

This project showcases my ability to build an end-to-end data visualization product: preparing public datasets, designing a usable analytics interface, implementing interactive filters, and communicating limitations clearly. The dashboard is designed for recruiters and reviewers to quickly see both technical execution and product judgment.

## Skills Demonstrated

- Data cleaning and aggregation with Python and pandas
- Interactive dashboard development with Dash and Plotly
- Geospatial visualization with community-area GeoJSON boundaries
- UI/UX iteration for dense civic analytics dashboards
- Responsive layout design, dark mode styling, and accessibility-minded controls
- Clear communication of methodology, limitations, and data interpretation risks

## Dashboard Highlights

- **Overview:** KPI cards, community-area density map, ranked crime categories with arrest-rate color encoding, monthly trend, day/hour heatmap, and annual outcomes.
- **Geospatial Explorer:** map-focused community comparison with selected-area profile, ranking, and trend panels.
- **Trend Analytics:** monthly detail, year-over-year comparison, seasonality profile, and a shared analysis window.
- **Usability:** searchable dropdown filters, light/dark mode, compact one-screen desktop layouts, and CSV export for the active selection.

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

Open `http://127.0.0.1:8050/` in your browser.

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

## Methodology and Limitations

The dashboard visualizes reported public-data incidents, not all crime. Counts can be affected by reporting behavior, enforcement patterns, data-entry practices, and policy changes. Per-capita estimates use available ACS community-area population estimates, so they should be interpreted as contextual approximations rather than exact risk measures.

The project intentionally uses aggregated 2021-2025 data for a clear portfolio workflow: data preparation, dashboard interaction, visual comparison, and careful public-data communication.
