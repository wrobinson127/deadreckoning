# Data License — Open Database License (ODbL) 1.0

## Summary
The **data outputs** published in this repository — everything under `data/`
(`data/daily/*.json`, `data/baselines.json`, `data/regions/*.json`) — are a
**derivative database** produced from [adsb.lol](https://www.adsb.lol) open
data. They are made available under the
**[Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/)**.

This is distinct from the repository's **code**, which is licensed MIT (see
`LICENSE`).

## Source attribution
Underlying flight data © [adsb.lol](https://www.adsb.lol) feeders and partners,
published as daily dumps at
[github.com/adsblol/globe_history_2026](https://github.com/adsblol/globe_history_2026)
under ODbL 1.0. adsb.lol data itself incorporates contributions from adsb.lol
feeders, [FlyItalyADSB](https://flyitalyadsb.com/), and
[TheAirTraffic.com](https://theairtraffic.com).

Basemap tiles © OpenStreetMap contributors (via
[OpenFreeMap](https://openfreemap.org)), ODbL 1.0.

## What ODbL requires of you
If you use, adapt, or redistribute the data under `data/`:
- **Attribute** adsb.lol and this project.
- **Share-Alike**: if you publicly use an adapted version of this database, you
  must offer that adapted database under ODbL as well.
- **Keep open**: if you redistribute the database (or a works produced from it)
  with technical restrictions, you must also provide an unrestricted version.

## What we aggregate
We compute per-day, per-H3-hex summaries of ADS-B Navigation Integrity Category
(NIC). No raw traces or personally-identifying feeder data are republished — only
spatial aggregates (see `docs/METHODOLOGY.md`). Raw dumps are deleted after
processing.
