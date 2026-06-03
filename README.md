# Partita

A football analytics framework for decomposing club, manager and player identity into independently measurable fingerprints — and measuring how those fingerprints interact.

---

## The Core Idea

Every football club has three distinct identities that can be measured from data:

- **Club philosophy** — what persists across managers and player cohorts
- **Manager system** — the tactical fingerprint a manager imposes on available personnel
- **Player profile** — what a player contributes independently of the system they play in

The central question Partita is designed to answer: **given a manager's system, which players are genuinely compatible with it — and how do we separate player identity from system context?**

---

## The Analytical Framework

### Fingerprints

A fingerprint is not a snapshot — it is a trajectory. Each entity (club, manager, player) is represented as a vector of behavioural metrics that changes over time and across contexts.

**Manager fingerprint** — built from possession sequence data across all matches under that manager. Captures territorial patterns, directness, width, press intensity and creation patterns.

**Player fingerprint** — built as a *deviation* from the manager's system demand for that role. What a player does differently from what the system typically gets from players in their position is the independent signal.

**Club fingerprint** — the aggregate of what persists across multiple managers. What stays stable when the manager changes is the club identity.

### Compatibility Scoring

Compatibility between a player and a system is not a simple similarity score. It is measured as:

1. What does this manager's system demand from each positional role?
2. How does this player's fingerprint deviate from their current system's role demand?
3. Does that deviation pattern align with what the target system needs?

This approach means compatibility can be assessed across contexts — a player's fingerprint developed under one manager can be evaluated against a different manager's system demands.

### Cross-Context Analysis

The project's deepest analytical value comes from observing the same player across multiple contexts. When a player moves clubs or plays under a new manager:

- Their fingerprint shift, normalised for system difference, reveals how context-dependent their behaviour is
- Stable deviations across contexts indicate genuine player tendencies
- Variable deviations indicate system-dependent behaviour

Aggregating these shifts across many players moving into or out of a specific club reveals what that club systematically does to player fingerprints — a bottom-up measure of club identity.

---

## Data Sources

| Source | Type | Coverage | Used For |
|--------|------|----------|----------|
| WhoScored | Event-level spatial data | Premier League 2020/21 — 2025/26 | Possession sequences, spatial fingerprints |
| Understat | Pre-computed xG metrics | Premier League 2020/21 — 2025/26 | Output quality metrics per player per match |
| ESPN | Lineup and formation data | Premier League 2021/22 — 2025/26 | Position labels, formation context |

**Known limitations:**
- Defensive and attacking metrics share the same caveat: we observe the spatial footprint of actions on the ball, not off-ball shape or movement intent
- The fingerprint is a behavioural footprint, not a direct measure of tactical system
- ESPN lineup data is unavailable for 2020/21

---

## Architecture

The project uses a four-layer data architecture:

```
ingestion/          Raw source data — exact as received, nothing changed
preprocessing/      Clean and map — resolve IDs, handle nulls, standardise
processing/         Derive variables — sequences, zones, progressive actions
analysis/           Fingerprints and compatibility scores
```

### Database Schema

**Reference tables** — clubs, managers, players, seasons, appointments, matches, match_context

**Raw tables** — raw_ws_events, raw_espn_lineups, raw_espn_matches, raw_understat_player_stats, raw_understat_player_match_stats, raw_understat_schedule

**Clean tables** — clean_events, clean_lineups, clean_player_stats, clean_player_match_stats

**Processed tables** — proc_sequences, proc_sequence_events

**Analysis** — manager_fingerprint (view), player_fingerprint (view)

---

## Proof of Concept

The proof of concept uses four Premier League clubs chosen to test specific analytical questions:

| Club | Why chosen |
|------|-----------|
| Arsenal | Stable manager, consistent system. The clean baseline |
| Brentford | Manager changed but club philosophy persists. Tests whether tactical identity lives at club or coach level |
| Manchester United | Mid-season manager change with completely different philosophies. Tests how quickly tactical fingerprints shift |
| Chelsea | Maximum instability across players and managers. Does any coherent profile emerge? |

---

## Current Status

### Completed
- Full data ingestion pipeline for all three sources across six Premier League seasons
- Four-layer database architecture with 170,000+ clean events
- Possession sequence identification and storage for proof of concept matches
- Manager fingerprint view — spatial and output quality metrics
- Player fingerprint view — deviation-based individual profiles
- Pitch heatmap visualisations for manager and player fingerprints

### In Progress
- ESPN position labels for role demand calculation
- System role demand profiles by positional group
- Player deviation fingerprints
- Compatibility scoring mechanism

### Planned
- Full data pull for all four clubs across all six seasons
- Cross-context player fingerprint analysis
- Transfer fit prediction scoring
- Scale to additional leagues and clubs

---

## Setup

### Requirements
- Python 3.12
- PostgreSQL

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/football-fingerprint.git
cd football-fingerprint
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
DB_HOST=localhost
DB_NAME=partita
DB_USER=postgres
DB_PASSWORD=your_password
```

Run the schema setup:

```bash
python pipeline/schema.py
python pipeline/seed.py
```

---

## Project Name

**Partita** — Italian for both "match" and "partition". The project partitions the football match into three independently measurable identities.

---

## Known Limitations

- Attacking and defensive fingerprints are based on on-ball actions only. Off-ball positioning and movement are not captured
- Sequences ending with goalkeeper clearances are filtered from end-position heatmaps to reduce keeper bias
- Corner kick delivery positions are filtered from player spatial heatmaps
- ESPN data unavailable for 2020/21 season
- West Bromwich Albion (relegated after 2020/21) has limited ESPN coverage
- The framework requires at least one cross-context observation per player for full fingerprint decomposition