# Methodology Notes

These notes record how I handled the interpretive problems in this dataset and what I decided to do about each one.

## Data Interpretation

The Chicago crime dataset records *reported* incidents, which is not a complete measure of all crime. Reporting behavior, policing patterns, population change, and data-collection practices all move these counts independently of underlying activity. I kept that framing visible in the dashboard itself rather than burying it here: the overview carries a methodology panel, and every chart is labeled in terms of reported incidents.

The analysis window is fixed at 2021 through 2025. That window is closed and complete — all twelve months of 2025 are present — so year-over-year comparisons across it are like-for-like. I excluded 2026 so the window would not shift as new data arrived.

## Geographic Interpretation

Raw community-area counts reflect population density, land area, commercial activity, tourism, and transit as much as they reflect risk. To avoid presenting counts as the only story, I added incidents per 100k residents as a selectable map metric, using ACS community-area population estimates. Those are estimates rather than a census count, so I treat the per-capita view as context rather than a precise rate.

I also kept arrest rate available as a third map metric, since volume and enforcement outcome answer different questions and collapsing them into one number would hide that.

## Empty Data and Honest Defaults

About 13% of crime-type and community-area combinations have no reported incidents at all. Where that happens, the day/hour heatmap renders an empty grid labeled "No reported incidents for these filters." An earlier version silently fell back to the citywide pattern in those cases, which meant a viewer could read a city-wide shape as one neighborhood's behavior. Showing nothing is the more honest default when there is nothing to show.

## Privacy and Ethics

The dashboard presents aggregated patterns, never individual incidents. I avoided visual language that labels neighborhoods as simply safe or unsafe, because these counts do not support that claim and the framing does real harm when it travels.
