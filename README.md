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
2. **Sync** — Searches VidAngel's public (unauthenticated) API for each title, downloads timestamped filter tags. If no VidAngel match is found, falls back to **local nudity detection** using NudeNet (with optional Freepik fast-pass classifier)
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
| `PLEXFILTER_LOCAL_DETECTION_ENABLED` | `true` | Enable NudeNet local fallback when VidAngel has no match |
| `PLEXFILTER_LOCAL_DETECTION_SAMPLE_INTERVAL_SEC` | `1.0` | Frame sampling interval for local detection |
| `PLEXFILTER_LOCAL_DETECTION_NUDENET_THRESHOLD` | `0.55` | NudeNet confidence threshold (0-1) |
| `PLEXFILTER_LOCAL_DETECTION_STAGE1_MODEL` | `freepik` | Stage-1 classifier model (`freepik` or `none`) |
| `PLEXFILTER_LOCAL_DETECTION_STAGE1_MIN_VRAM_GB` | `3.5` | Minimum GPU VRAM required to enable stage-1 classifier |
| `PLEXFILTER_LOCAL_DETECTION_STAGE1_REQUIRE_BF16` | `false` | Require BF16 support for stage-1 classifier |

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
│       │        ┌──────┴──────┐          │            │
│       │        │ Local       │          │            │
│       │        │ Detection   │(fallback)│            │
│       │        │ (NudeNet)   │          │            │
│       │        └──────┬──────┘          │            │
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

- **Backend:** Python 3.12, FastAPI, SQLite, python-plexapi, httpx, NudeNet (ONNX), OpenCV
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
| POST | `/api/local-detection/{id}` | Force local nudity detection for one title |
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

## Data Sources

**VidAngel (primary):** All filter data comes from [VidAngel's public API](https://api.vidangel.com/api/). No authentication required. Tags include:

- Second-level timestamps (`start_approx`, `end_approx`)
- Human-written descriptions ("A man says the f-word while pointing a gun")
- Content type (`audio`, `visual`, `audiovisual`)
- 147 categories in a 3-level hierarchy

See the [VidAngel extractor project](../va/) for API documentation and discovery process.

**Local Detection (fallback):** When a title isn't in VidAngel's catalog, PlexFilter can analyze the video directly using a two-stage pipeline:

1. **Stage 1 — Freepik classifier** (optional, requires GPU): Fast frame-level NSFW classification (neutral/low/medium/high) to filter out clean frames
2. **Stage 2 — NudeNet detector** (ONNX, works on CPU): Object detection identifying specific body parts (18 labels) mapped to PlexFilter nudity categories

The pipeline extracts frames via ffmpeg, runs detection, merges adjacent hits into skip segments, and stores them as tags in the same format as VidAngel data — so existing filter profiles and the PlexAutoSkip generator work without modification. See [detection model research](docs/local-detection-research.md) for model comparison details.

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

33 tests covering: VidAngel API client, Plex scanner, profile management with three-level filter resolution, PlexAutoSkip JSON generator with segment merging, local detection pipeline (fallback integration, stage-1 GPU checks, progress events), and an end-to-end smoke test running the full pipeline.

## Future Enhancements

- TV show support (VidAngel has episode-level tags)
- Local fallback profanity pipeline (WhisperX research pending)
- Per-Plex-user profile mapping
- Authentication for remote access
- Auto-sync on Plex library webhook events
- Common Sense Media / IMDb Parents Guide metadata enrichment
