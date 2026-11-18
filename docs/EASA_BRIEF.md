# Checking an open GPS-interference archive against Europe's official warnings

*DRAFT for Walker's approval. Not for publication. Every sentence with a number
or a claim is checked against `docs/EASA_STAGE0.md` to `docs/EASA_STAGE3.md`.*

## Key findings

- **The archive recovers the airspace EASA ranks worst.** The European Union
  Aviation Safety Agency (EASA) publishes a ranked table of the flight information regions
  (FIRs) most affected by interference with GNSS, satellite navigation that includes GPS. Across 20 of those tables, from
  May 2025 to November 2026, DeadReckoning's own ranking contained a median of
  94.2% of EASA's top 20, counting only FIRs with enough aircraft to score. The pass mark, written down and committed before the comparison ran, was 70%. A random list would score
  about 29%.
- **It does not reproduce EASA's order or its edges.** About half of the
  archive's list does not appear in EASA's table, because the bottom of a list
  that long holds airspace with only 2 to 3% of aircraft degraded. Within the
  FIRs both lists share, rank agreement is weak: a median Spearman correlation of 0.205, where 1 would mean the same order and 0 no relation.
- **One clear case of a warning arriving after the interference.** The
  archive shows persistent interference in the Tallinn FIR (Estonia) from
  June 2023. EASA first named Tallinn on its list dated 5 July 2024, 388 days
  later (375 under a stricter boundary rule).
- **Four cases run the other way.** EASA named Sweden (southern part), Athens
  (eastern part), Budapest and Bratislava in July 2024 while the archive had
  them under daily coverage and saw no persistent interference.

This brief compares one open archive with EASA's published warnings in two
ways: how its dates line up with EASA's named lists (2023 to 2025), and how
its rankings line up with EASA's ranked tables (2025 to 2026). It makes no
claim about who caused any interference.

## What was compared

**The archive.** DeadReckoning aggregates ADS-B broadcasts (the position reports aircraft transmit by radio) from the open adsb.lol network, one UTC day at a time, from 16 February 2023 to 16 November
2026 (1,364 daily files). Each aircraft reports a Navigation Integrity
Category (NIC), a measure of how far it trusts its own GPS position. The
archive counts an aircraft as degraded at NIC 6 or below, in hexagonal
cells about 45 km across, and shows no value where fewer than five aircraft passed.

**EASA's warnings.** EASA's Safety Information Bulletin 2022-02 named
affected FIRs in its text in February 2023 (revision 1, 21 FIRs) and November
2023 (revision 2). Revision 3, issued 5 July 2024, moved the list to EASA's
website, where it named 29 FIRs. By 14 May 2025 that page showed a ranked
table instead. According to the page, the table comes from aircraft ADS-B NIC
reports, treats NIC 7 as "the frontier between good and bad," and averages a
daily share of affected aircraft over 7 and 30 days. Archived copies of the
page on the Internet Archive supplied 19 of the 20 table dates used here. The
twentieth was read live. The switch from list to table happened between the
copies of 17 February and 20 May 2025.

**FIRs.** The archive has no FIR field, so its cells were assigned to FIR
outlines from the VATSIM flight-simulation community. These are not official
boundaries. The five FIRs that carry findings below still need checking
against official charts.

## Agreement with the ranked tables

The pass mark and every rule were written down and committed to the project's repository before any agreement figure was computed. For each EASA table, DeadReckoning ranked every FIR with enough aircraft to score by its
own share of degraded aircraft over the same 7 or 30 days, and kept as many
as EASA listed (40 to 58). The measure was the share of EASA's top 20 inside
that list.

| Tables | Median share of EASA's top 20 found | Range |
|---|---|---|
| 30-day, worldwide (primary) | 94.2% | 82.4% to 100% |
| 30-day, Americas excluded | 100% | 87.5% to 100% |
| 7-day, worldwide | 93.3% | 76.5% to 100% |

The misses are few and repeat: Istanbul, Bangkok, Jeddah, Cairo and Delhi account for
most of them.

- **About half the archive's list is not in EASA's table.** A list as long as EASA's reaches down to FIRs
  where 2 to 3% of aircraft report degraded integrity. Several central
  European FIRs sit there in almost every table. That level is background in the archive's measure, and EASA's table leaves those FIRs out.
- **The order differs.** Within FIRs on both lists, the archive's ranking correlates weakly with EASA's, and in three 2026 tables the correlation is below zero (the orders run slightly opposite).
- **Some of EASA's top FIRs are out of reach.** In some tables, Baghdad,
  Baku, Lahore, Asmara, Addis Ababa and several Russian and Kazakh FIRs had
  too little coverage to score. These count as no data, not disagreement.

## Dates against the named lists

**Tallinn.** The first archive cell to show persistent interference wholly
inside the Tallinn FIR sits in Voru county, in southeast Estonia, from
26 June 2023. EASA's November 2023 revision did not add Tallinn; the July 2024
list did.

**Named while quiet.** Southern Sweden, eastern Athens, Budapest and
Bratislava each had hundreds of covered days before July 2024 and no
persistent interference by the archive's rule. Sweden showed it from October
2024. Budapest and Bratislava showed it from September 2026. Athens has not.
EASA's February 2023 bulletin says its list drew on "data from the Network
of Analysts and open sources." The archive cannot see those sources, so it
cannot say why these FIRs were named.

**Seen first by the archive.** Eleven areas (ten FIRs plus one simulator
outline over the UK) showed persistent interference before February
2025 without appearing on any named list. Five are Russian or
Belarusian, and the lists do not say whether they meant to cover that
airspace. Kaliningrad appears in the 2023 bulletins only as a reference point.
Most of these FIRs first appear in the earliest ranked table on record (May
2025). That date marks EASA's change of method, so it gives no lag. Six US FIRs with persistent interference also appear, outside
EASA's apparent scope. EASA's tables list no FIR in the Americas.

## What this does not show

A lag here is the gap between two dates, and nothing more. EASA's page says its table is cross-checked against reported occurrences, which this archive cannot see. The agreement is between two related instruments, and EASA's method is only partly published, so neither one is ground truth. Where commercial aircraft do not fly, the archive has no data.

## What to watch

The archived copies show EASA's table changing many times since May 2025,
and the archive adds a day every night. Saving each table as it appears
would turn a 20-date sample into a full series. The open question for the
archive is what drives its background level in central Europe.

*Sources: EASA SIB 2022-02 R1 to R4; EASA, "Global Navigation Satellite System
(GNSS) Outages and Alterations" (live page and Internet Archive copies,
2024-07-09 to 2026-11-17); VATSIM vatspy-data-project boundaries (CC BY-SA
4.0); flight data © adsb.lol (ODbL 1.0). Full method and every count:
`docs/EASA_STAGE0.md` to `docs/EASA_STAGE3.md` and the registration,
`docs/EASA_STAGE3_REGISTRATION.md`.*
