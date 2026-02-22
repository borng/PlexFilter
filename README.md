# PlexFilter

Self-hosted content filtering for Plex Media Server. Pulls timestamped filter data from VidAngel's public API and generates [PlexAutoSkip](https://github.com/mdhiggins/PlexAutoSkip) `custom.json` for real-time skip/mute during playback.

## How It Works

```
Your Plex Library → PlexFilter scans it → Matches titles to VidAngel catalog
                                            ↓
                         Downloads 147-category filter tags with timestamps
                                            ↓
                    You pick filter profiles (Language, Nudity, Violence, etc.)
                                            ↓
                      Generates custom.json → PlexAutoSkip skips/mutes on playback
```

1. **Scan** — Connects to your Plex server, catalogs movies with TMDB/IMDB IDs
2. **Sync** — Searches VidAngel's public (unauthenticated) API for each title, downloads timestamped filter tags
3. **Filter** — Create profiles with three-level granularity:
   - **Group level**: Toggle all Language, all Nudity, all Violence
   - **Category level**: Toggle specific categories (f-word, Gore, Female Nudity, etc.)
   - **Tag level**: Override individual tags by description
4. **Generate** — Outputs `custom.json` that PlexAutoSkip reads to skip/mute segments during playback

Audio-only tags (profanity) get muted. Visual/audiovisual tags (nudity, violence) get skipped.

## Quick Start

### Option 1: Docker Compose (recommended)

```bash
git clone <repo-url> && cd plexfilter
cp .env.example .env
# Edit .env with your PLEX_URL and PLEX_TOKEN
docker compose up -d
# Open http://localhost:8000
```

### Option 2: Local Development

**Backend:**

```bash
cd backend
pip install -r requirements.txt
uvicorn plexfilter.main:app --port 8000 --reload
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173 (proxies API to :8000)
```

### Option 3: Production (no Docker)

```bash
cd frontend && npm run build
cp -r dist/ ../backend/static/
cd ../backend
uvicorn plexfilter.main:app --host 0.0.0.0 --port 8000
# Serves both API and React SPA from :8000
```

## Configuration

Environment variables (or `.env` file in `backend/`):

| Variable | Default | Description |
|----------|---------|-------------|
| `PLEXFILTER_PLEX_URL` | | Plex server URL (e.g. `http://localhost:32400`) |
| `PLEXFILTER_PLEX_TOKEN` | | Plex authentication token |
| `PLEXFILTER_DATABASE_PATH` | `plexfilter.db` | SQLite database path |
| `PLEXFILTER_PLEXAUTOSKIP_JSON_PATH` | `custom.json` | Output path for PlexAutoSkip |

**Getting your Plex token:** Open Plex Web, inspect any API request, find `X-Plex-Token` in the URL.

## PlexAutoSkip Integration

PlexFilter generates `custom.json` in the format PlexAutoSkip expects:

```json
{
  "markers": {
    "tmdb://845783": [
      {"start": 30000, "end": 31000, "mode": "volume"},
      {"start": 60000, "end": 65000, "mode": "skip"}
    ]
  }
}
```

- `mode: "volume"` — mutes audio (used for profanity)
- `mode: "skip"` — seeks past the segment (used for nudity/violence)
- Adjacent segments within 2 seconds auto-merge to avoid jarring playback

Point PlexAutoSkip's `custom_json` config at the same file PlexFilter writes to.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    React Frontend                    │
│  Library browser │ Filter profiles │ Title detail    │
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
│  └────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────┘
                       │
                       ▼ writes
              ┌────────────────┐
              │  custom.json   │ ← PlexAutoSkip reads this
              └────────────────┘
```

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLite, python-plexapi, httpx
- **Frontend:** React 18, Vite, Tailwind CSS, TanStack React Query
- **External:** PlexAutoSkip (separate process), Plex Media Server

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/library` | List library items with match status |
| GET | `/api/library/{id}` | Single item with all tags |
| GET | `/api/profiles` | List filter profiles |
| POST | `/api/profiles` | Create profile |
| PUT | `/api/profiles/{id}` | Update profile filters |
| DELETE | `/api/profiles/{id}` | Delete profile |
| GET | `/api/categories` | VidAngel category tree (cached) |
| POST | `/api/sync` | Start background sync of all titles |
| POST | `/api/sync/{id}` | Sync single title |
| GET | `/api/sync/status` | Sync progress |
| POST | `/api/generate` | Generate custom.json |
| GET | `/api/generate/preview/{id}` | Preview what would be filtered |
| POST | `/api/plex/connect` | Set Plex server connection |
| POST | `/api/plex/scan` | Scan Plex library |

## Filter Categories (v1)

PlexFilter exposes the big three category groups for v1:

- **Language** — Profanity (f-word, sh*t, etc.), blasphemy, slurs, crude language
- **Nudity/Sex** — All nudity and sexual content subcategories
- **Violence** — Gore, graphic, non-graphic, disturbing content

VidAngel provides 147 categories total across Language, Sex, Nudity, Violence, Substance, Kissing, Medical, and Credits. All are stored in the database; the UI currently surfaces Language, Nudity, Sex, and Violence.

## Data Source

All filter data comes from [VidAngel's public API](https://api.vidangel.com/api/). No authentication required. Tags include:

- Second-level timestamps (`start_approx`, `end_approx`)
- Human-written descriptions ("A man says the f-word while pointing a gun")
- Content type (`audio`, `visual`, `audiovisual`)
- 147 categories in a 3-level hierarchy

See the [VidAngel extractor project](../va/) for API documentation and discovery process.

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

27 tests covering: VidAngel API client, Plex scanner, profile management with three-level filter resolution, PlexAutoSkip JSON generator with segment merging, and an end-to-end smoke test running the full pipeline.

## Future Enhancements

- TV show support (VidAngel has episode-level tags)
- Fallback pipeline: WhisperX for profanity + NudeNet for nudity detection
- Per-Plex-user profile mapping
- Authentication for remote access
- Auto-sync on Plex library webhook events
- Common Sense Media / IMDb Parents Guide metadata enrichment
