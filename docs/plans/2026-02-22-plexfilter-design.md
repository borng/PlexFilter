# PlexFilter Design Document

**Date:** 2026-02-22
**Status:** Approved
**Location:** `/workspaces/playground/fam/plexfilter/`

## Overview

PlexFilter is a self-hosted web app that brings VidAngel-style content filtering to Plex Media Server. It pulls timestamped filter data from VidAngel's public API, lets users create filter profiles with three-level granularity (category group → specific category → individual tag), and generates `custom.json` files consumed by PlexAutoSkip for real-time playback filtering.

**Approach:** PlexAutoSkip Orchestrator — our app handles data pipeline, matching, profile management, and UI. PlexAutoSkip (separate project) handles the hard part of real-time playback monitoring and skip/mute execution.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    React Frontend                    │
│  Filter profiles │ Library browser │ Match status    │
└──────────────────────┬──────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────┐
│                  FastAPI Backend                      │
│                                                      │
│  ┌──────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ Plex     │  │ VidAngel  │  │ PlexAutoSkip     │  │
│  │ Scanner  │  │ Sync      │  │ JSON Generator   │  │
│  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │
│       │              │                  │            │
│  ┌────▼──────────────▼──────────────────▼─────────┐  │
│  │              SQLite Database                    │  │
│  │  library │ tags │ matches │ profiles            │  │
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                       │
                       ▼ writes
              ┌────────────────┐
              │  custom.json   │ ← PlexAutoSkip reads this
              └────────────────┘
```

### Three Backend Services

1. **Plex Scanner** — Connects to Plex server via PlexAPI, catalogs library with TMDB/IMDB IDs
2. **VidAngel Sync** — Pulls filter tag data from VidAngel's public API, matches to library by GUID
3. **PlexAutoSkip JSON Generator** — Combines user filter profiles + matched tag data → writes `custom.json`

## Data Model

### library

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| plex_key | TEXT | Plex ratingKey |
| title | TEXT | Movie/episode title |
| year | INTEGER | Release year |
| tmdb_id | TEXT | TMDB ID (e.g. "32726") |
| imdb_id | TEXT | IMDB ID (e.g. "tt7339792") |
| media_type | TEXT | "movie" or "episode" |
| thumb_url | TEXT | Plex thumbnail URL |
| last_scanned | DATETIME | Last library scan time |

### tags

Denormalized — category_name/category_group stored alongside each tag to avoid joins on the hot path (JSON generation). VidAngel's 147 categories are static.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| vidangel_id | INTEGER | VidAngel's tag ID |
| tag_set_id | INTEGER | VidAngel tag set |
| category_id | INTEGER | VidAngel category ID |
| category_name | TEXT | e.g. "f-word", "Gore" |
| category_group | TEXT | e.g. "Language", "Violence" |
| description | TEXT | Human-readable description |
| type | TEXT | "audio", "visual", "audiovisual" |
| start_sec | REAL | Start timestamp in seconds |
| end_sec | REAL | End timestamp in seconds |

### matches

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| library_id | INTEGER FK | References library(id) |
| vidangel_work_id | INTEGER | VidAngel work ID |
| tag_set_id | INTEGER | VidAngel tag set ID |
| match_method | TEXT | "tmdb", "imdb", or "manual" |
| tag_count | INTEGER | Number of tags for this title |
| last_synced | DATETIME | Last tag sync time |

### profiles

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Auto-increment |
| name | TEXT | Profile name ("Kids", "Date Night") |
| plex_user | TEXT | Optional Plex managed user mapping |
| filters | JSON | Three-level filter selections |
| mode | TEXT | Default mode: "skip" or "mute" |
| created_at | DATETIME | Creation timestamp |

### Filter Resolution

The `filters` JSON supports three levels of granularity:

```json
{
  "Language": true,           // Level 1: whole group on
  "Language:f-word": false,   // Level 2: override specific category
  "tag:3893734": false        // Level 3: override specific tag by ID
}
```

**Resolution order:** specific overrides general. A tag is filtered if:
1. Its group is enabled (Level 1), AND
2. Its specific category is not explicitly disabled (Level 2), AND
3. That exact tag is not explicitly excluded (Level 3)

## API Design

### Plex Integration
- `POST /api/plex/connect` — Test connection, save server URL + token
- `POST /api/plex/scan` — Trigger library scan
- `GET /api/library` — Paginated library list with match status
- `GET /api/library/{id}` — Single title with tags + overrides

### VidAngel Sync
- `POST /api/sync` — Trigger full sync (match library → fetch tags)
- `POST /api/sync/{library_id}` — Sync single title
- `GET /api/sync/status` — Progress of current sync job

### Profiles
- `GET /api/profiles` — List all profiles
- `POST /api/profiles` — Create profile
- `PUT /api/profiles/{id}` — Update profile (name, filters, mode)
- `DELETE /api/profiles/{id}` — Delete profile

### Categories
- `GET /api/categories` — Full category tree (cached from VidAngel)

### Tags
- `GET /api/tags/{library_id}` — All tags for a title, grouped by category
- `PUT /api/tags/{library_id}/overrides` — Save per-tag overrides for a profile

### PlexAutoSkip Output
- `POST /api/generate` — Regenerate custom.json for all profiles
- `GET /api/generate/preview/{profile_id}` — Preview what would be skipped/muted

### Key Behaviors

- **Sync is async** — VidAngel API calls run in background tasks. UI polls `/api/sync/status`.
- **Matching pipeline** — For each Plex item: search VidAngel by title+year, confirm via TMDB/IMDB ID, fetch tag set.
- **Generate is idempotent** — Rebuilds entire `custom.json` from current state. Safe to call anytime.

## PlexAutoSkip JSON Generation

```python
# Pseudocode
for each matched title in library:
    tags = get_tags(title.tag_set_id)
    filtered_tags = apply_profile_filters(tags, profile)

    segments = []
    for tag in filtered_tags:
        mode = "volume" if tag.type == "audio" else "skip"
        segments.append({
            "start": int(tag.start_sec * 1000),   # ms
            "end": int(tag.end_sec * 1000),        # ms
            "mode": profile.default_mode or mode
        })

    # Merge overlapping/adjacent segments (within 2s gap)
    segments = merge_segments(segments)

    output[f"tmdb://{title.tmdb_id}"] = segments
```

**Smart merging** — Segments within 2 seconds of each other merge into one. Avoids jarring rapid skip-resume-skip.

**Audio vs visual logic:**
- `type: "audio"` → `mode: "volume"` (mute)
- `type: "visual"` or `"audiovisual"` → `mode: "skip"` (seek past)
- Profile default_mode can override

## UI Design

### Four Screens

**1. Library** — Grid/list of Plex movies. Match status badges:
- Green = matched with VidAngel, tags available
- Yellow = unmatched, needs manual match or not in VidAngel
- Grey = no tags available

Click to open title detail.

**2. Filter Profiles** — Create/edit profiles:
- Name and optional Plex user mapping
- Default mode (skip vs mute)
- Three-level category tree with toggles:
  - Accordion per group (Language, Nudity/Sex, Violence)
  - Expand → individual category toggles
  - On title detail view → expand further to see tag descriptions with per-tag overrides

**3. Title Detail** — Click a movie from Library:
- Poster, metadata, match info
- Timeline visualization showing filtered segment positions
- Tag list grouped by category with descriptions
- Per-tag override toggles (inherit from profile, can override)

**4. Settings** — Plex server connection, PlexAutoSkip output path, sync controls

**No auth for v1** — runs on localhost, your server. Auth comes later for the shareable version.

## Tech Stack

```
Backend:
  Python 3.12
  FastAPI + Uvicorn
  SQLite (sqlite3 stdlib)
  python-plexapi
  httpx (async HTTP for VidAngel API)

Frontend:
  React 18+ (Vite)
  Tailwind CSS
  React Query

External:
  PlexAutoSkip (separate process, reads our custom.json)
  Plex Media Server (user's existing server)

Deployment:
  Docker Compose (plexfilter + plexautoskip in one stack)
  Or bare metal: pip + npm build, systemd service
```

## Data Sources

### Primary: VidAngel API (unauthenticated)

- `GET /api/content/v2/works/?type=movie` — Movie listings
- `GET /api/content/v2/movies/{work_id}/` — Movie detail with tag_set_id
- `GET /api/tag-sets/{tag_set_id}/` — All tags with timestamps
- `GET /api/v2/tag-categorizations/` — 147 filter categories

### Filter categories of interest (v1)

- **Language** — Profanity, blasphemy, slurs, crude language
- **Nudity/Sex** — All nudity and sexual content subcategories
- **Violence** — Gore, graphic, non-graphic, disturbing

All 147 categories stored in DB; UI exposes Language + Nudity/Sex + Violence for v1, expandable later.

## Future Enhancements (not v1)

- TV show support (VidAngel has episode-level tags)
- Fallback pipeline: WhisperX for profanity + NudeNet for nudity detection (for titles not in VidAngel)
- Multiple PlexAutoSkip profiles (per Plex user)
- Authentication for remote access
- Common Sense Media / IMDb Parents Guide integration for metadata enrichment
- Auto-sync on Plex library webhook events
