# PlexFilter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-hosted web app that pulls VidAngel filter data and generates PlexAutoSkip `custom.json` for content filtering on Plex.

**Architecture:** FastAPI backend with three services (Plex Scanner, VidAngel Sync, JSON Generator) + React frontend with Vite/Tailwind. SQLite for all state. Outputs `custom.json` that PlexAutoSkip reads.

**Tech Stack:** Python 3.12, FastAPI, SQLite, python-plexapi, httpx, React 18, Vite, Tailwind CSS, React Query

**Design doc:** `docs/plans/2026-02-22-plexfilter-design.md`

---

## Task 1: Project Scaffolding

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/plexfilter/__init__.py`
- Create: `backend/plexfilter/main.py`
- Create: `backend/plexfilter/config.py`
- Create: `backend/plexfilter/database.py`
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/tsconfig.json`
- Create: `.gitignore`

**Step 1: Create backend scaffolding**

`backend/requirements.txt`:
```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
plexapi>=4.15.0
httpx>=0.27.0
pydantic>=2.9.0
pydantic-settings>=2.6.0
```

`backend/plexfilter/config.py`:
```python
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    database_path: str = "plexfilter.db"
    plex_url: str = ""
    plex_token: str = ""
    plexautoskip_json_path: str = "custom.json"
    vidangel_base_url: str = "https://api.vidangel.com/api"

    class Config:
        env_file = ".env"
        env_prefix = "PLEXFILTER_"

settings = Settings()
```

`backend/plexfilter/database.py`:
```python
import sqlite3
from pathlib import Path
from .config import settings

def get_db() -> sqlite3.Connection:
    db = sqlite3.connect(settings.database_path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plex_key TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            year INTEGER,
            tmdb_id TEXT,
            imdb_id TEXT,
            media_type TEXT NOT NULL DEFAULT 'movie',
            thumb_url TEXT,
            last_scanned TEXT
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vidangel_id INTEGER UNIQUE NOT NULL,
            tag_set_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            category_name TEXT NOT NULL,
            category_group TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL,
            start_sec REAL NOT NULL,
            end_sec REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            library_id INTEGER NOT NULL REFERENCES library(id),
            vidangel_work_id INTEGER NOT NULL,
            tag_set_id INTEGER NOT NULL,
            match_method TEXT NOT NULL DEFAULT 'tmdb',
            tag_count INTEGER DEFAULT 0,
            last_synced TEXT
        );

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            plex_user TEXT,
            filters TEXT NOT NULL DEFAULT '{}',
            mode TEXT NOT NULL DEFAULT 'skip',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_library_tmdb ON library(tmdb_id);
        CREATE INDEX IF NOT EXISTS idx_library_imdb ON library(imdb_id);
        CREATE INDEX IF NOT EXISTS idx_tags_tag_set ON tags(tag_set_id);
        CREATE INDEX IF NOT EXISTS idx_tags_category ON tags(category_group);
        CREATE INDEX IF NOT EXISTS idx_matches_library ON matches(library_id);
    """)
    db.close()
```

`backend/plexfilter/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db

app = FastAPI(title="PlexFilter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

`backend/plexfilter/__init__.py`: empty file.

**Step 2: Create frontend scaffolding**

`frontend/package.json`:
```json
{
  "name": "plexfilter-frontend",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "@tanstack/react-query": "^5.60.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }
}
```

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

`frontend/tailwind.config.js`:
```javascript
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

`frontend/postcss.config.js`:
```javascript
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
}
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "jsx": "react-jsx",
    "moduleResolution": "bundler",
    "strict": true,
    "noEmit": true,
    "skipLibCheck": true
  },
  "include": ["src"]
}
```

`frontend/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PlexFilter</title>
</head>
<body class="bg-gray-900 text-white">
  <div id="root"></div>
  <script type="module" src="/src/main.tsx"></script>
</body>
</html>
```

`frontend/src/main.tsx`:
```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

const queryClient = new QueryClient()

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
)
```

`frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

`frontend/src/App.tsx`:
```tsx
export default function App() {
  return (
    <div className="min-h-screen p-8">
      <h1 className="text-3xl font-bold">PlexFilter</h1>
      <p className="text-gray-400 mt-2">Content filtering for Plex</p>
    </div>
  )
}
```

`.gitignore`:
```
__pycache__/
*.pyc
*.db
.env
node_modules/
dist/
custom.json
.vite/
```

**Step 3: Install dependencies and verify**

```bash
cd /workspaces/playground/fam/plexfilter/backend && pip install -r requirements.txt
cd /workspaces/playground/fam/plexfilter/frontend && npm install
```

**Step 4: Verify backend starts**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m uvicorn plexfilter.main:app --port 8000 &
curl http://localhost:8000/api/health
# Expected: {"status":"ok"}
kill %1
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: scaffold PlexFilter project — FastAPI backend + React frontend"
```

---

## Task 2: VidAngel Client Service

**Files:**
- Create: `backend/plexfilter/services/__init__.py`
- Create: `backend/plexfilter/services/vidangel.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_vidangel.py`

**Step 1: Write the failing tests**

`backend/tests/test_vidangel.py`:
```python
import pytest
from plexfilter.services.vidangel import VidAngelClient

@pytest.fixture
def client():
    return VidAngelClient()

def test_get_categories(client):
    """Should return a list of category dicts with id, key, display_title, parent_id."""
    categories = client.get_categories()
    assert len(categories) > 100
    first = categories[0]
    assert "id" in first
    assert "display_title" in first
    assert "parent_id" in first

def test_build_category_tree(client):
    """Should build a nested tree: group -> category -> subcategory."""
    categories = client.get_categories()
    tree = client.build_category_tree(categories)
    # Should have root groups like Language, Sex, Nudity, Violence
    group_names = [g["display_title"] for g in tree]
    assert "Language" in group_names
    assert "Violence" in group_names

def test_search_works(client):
    """Should find movies by title search."""
    results = client.search_works("Operation Fortune", media_type="movie")
    assert len(results) > 0
    assert any("Operation Fortune" in r["title"] for r in results)

def test_get_movie_detail(client):
    """Should return movie detail with offerings containing tag_set_id."""
    # Operation Fortune: Ruse de Guerre
    detail = client.get_movie_detail(695260)
    assert detail["title"] == "Operation Fortune: Ruse de Guerre"
    assert len(detail["offerings"]) > 0
    tag_set_ids = [o["tag_set_id"] for o in detail["offerings"] if o.get("tag_set_id")]
    assert len(tag_set_ids) > 0

def test_get_tag_set(client):
    """Should return tags with timestamps for a tag_set_id."""
    # tag_set_id 58076 = Operation Fortune
    tag_set = client.get_tag_set(58076)
    assert "tags" in tag_set
    tags = tag_set["tags"]
    assert len(tags) > 50
    first_tag = tags[0]
    assert "start_approx" in first_tag
    assert "end_approx" in first_tag
    assert "category_id" in first_tag
    assert "description" in first_tag
    assert "type" in first_tag

def test_get_tag_set_with_category_names(client):
    """Should enrich tags with category_name and category_group."""
    categories = client.get_categories()
    cat_map = {c["id"]: c for c in categories}
    tag_set = client.get_tag_set(58076)
    enriched = client.enrich_tags(tag_set["tags"], cat_map)
    first = enriched[0]
    assert "category_name" in first
    assert "category_group" in first
```

**Step 2: Run tests to verify they fail**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_vidangel.py -v
# Expected: FAIL — ModuleNotFoundError: No module named 'plexfilter.services'
```

**Step 3: Implement the VidAngel client**

`backend/plexfilter/services/__init__.py`: empty file.

`backend/plexfilter/services/vidangel.py`:
```python
import httpx
from ..config import settings

class VidAngelClient:
    def __init__(self):
        self.base_url = settings.vidangel_base_url
        self.headers = {
            "User-Agent": "PlexFilter/0.1",
            "Accept": "application/json",
        }

    def get_categories(self) -> list[dict]:
        with httpx.Client() as client:
            resp = client.get(
                f"{self.base_url}/v2/tag-categorizations/",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    def build_category_tree(self, categories: list[dict]) -> list[dict]:
        by_id = {c["id"]: {**c, "children": []} for c in categories}
        roots = []
        for cat in categories:
            node = by_id[cat["id"]]
            if cat["parent_id"] is None:
                roots.append(node)
            elif cat["parent_id"] in by_id:
                by_id[cat["parent_id"]]["children"].append(node)
        roots.sort(key=lambda x: x.get("ordering", 0))
        for node in by_id.values():
            node["children"].sort(key=lambda x: x.get("ordering", 0))
        return roots

    def search_works(self, query: str, media_type: str = "movie", limit: int = 20) -> list[dict]:
        with httpx.Client() as client:
            resp = client.get(
                f"{self.base_url}/content/v2/works/",
                params={"type": media_type, "search": query, "limit": limit},
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    def get_movie_detail(self, work_id: int) -> dict:
        with httpx.Client() as client:
            resp = client.get(
                f"{self.base_url}/content/v2/movies/{work_id}/",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    def get_tag_set(self, tag_set_id: int) -> dict:
        with httpx.Client() as client:
            resp = client.get(
                f"{self.base_url}/tag-sets/{tag_set_id}/",
                headers=self.headers,
            )
            resp.raise_for_status()
            return resp.json()

    def enrich_tags(self, tags: list[dict], cat_map: dict[int, dict]) -> list[dict]:
        enriched = []
        for tag in tags:
            cat = cat_map.get(tag.get("category_id", 0), {})
            parent = cat_map.get(cat.get("parent_id"), {})
            grandparent = cat_map.get(parent.get("parent_id"), {})
            # Walk up to find the root group name
            if grandparent.get("display_title"):
                group = grandparent["display_title"]
            elif parent.get("display_title"):
                group = parent["display_title"]
            else:
                group = cat.get("display_title", "Unknown")
            enriched.append({
                **tag,
                "category_name": cat.get("display_title", f"cat-{tag.get('category_id')}"),
                "category_group": group,
            })
        return enriched
```

**Step 4: Run tests to verify they pass**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_vidangel.py -v
# Expected: all 6 tests PASS
```

Note: These tests hit the real VidAngel API. They are integration tests. For CI, we would mock httpx. For now, real calls confirm the API still works.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add VidAngel client service with category tree and tag enrichment"
```

---

## Task 3: Plex Scanner Service

**Files:**
- Create: `backend/plexfilter/services/plex_scanner.py`
- Create: `backend/tests/test_plex_scanner.py`

**Step 1: Write the failing tests**

`backend/tests/test_plex_scanner.py`:
```python
import sqlite3
import pytest
from plexfilter.database import init_db, get_db
from plexfilter.services.plex_scanner import PlexScanner

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("plexfilter.config.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.database.settings.database_path", db_path)
    init_db()
    return db_path

def test_store_library_item(test_db):
    """Should insert a library item into the database."""
    scanner = PlexScanner()
    scanner.store_item(
        plex_key="12345",
        title="Operation Fortune: Ruse de Guerre",
        year=2023,
        tmdb_id="845783",
        imdb_id="tt7339792",
        media_type="movie",
        thumb_url="/library/metadata/12345/thumb",
    )
    db = get_db()
    row = db.execute("SELECT * FROM library WHERE plex_key = '12345'").fetchone()
    assert row is not None
    assert row["title"] == "Operation Fortune: Ruse de Guerre"
    assert row["tmdb_id"] == "845783"
    db.close()

def test_store_item_upsert(test_db):
    """Should update existing item on rescan, not duplicate."""
    scanner = PlexScanner()
    scanner.store_item(plex_key="12345", title="Old Title", year=2023, tmdb_id="1", media_type="movie")
    scanner.store_item(plex_key="12345", title="New Title", year=2023, tmdb_id="1", media_type="movie")
    db = get_db()
    rows = db.execute("SELECT * FROM library WHERE plex_key = '12345'").fetchall()
    assert len(rows) == 1
    assert rows[0]["title"] == "New Title"
    db.close()

def test_get_library_items(test_db):
    """Should return paginated library items."""
    scanner = PlexScanner()
    for i in range(5):
        scanner.store_item(plex_key=str(i), title=f"Movie {i}", year=2023, tmdb_id=str(i), media_type="movie")
    items = scanner.get_items(limit=3, offset=0)
    assert len(items) == 3
    items2 = scanner.get_items(limit=3, offset=3)
    assert len(items2) == 2

def test_extract_guids():
    """Should parse TMDB and IMDB IDs from Plex GUID strings."""
    guids = [
        "tmdb://845783",
        "imdb://tt7339792",
        "tvdb://12345",
    ]
    result = PlexScanner.extract_guids(guids)
    assert result["tmdb_id"] == "845783"
    assert result["imdb_id"] == "tt7339792"
```

**Step 2: Run tests to verify they fail**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_plex_scanner.py -v
# Expected: FAIL — ModuleNotFoundError
```

**Step 3: Implement the Plex scanner**

`backend/plexfilter/services/plex_scanner.py`:
```python
from datetime import datetime, timezone
from ..database import get_db
from ..config import settings

class PlexScanner:
    def store_item(
        self,
        plex_key: str,
        title: str,
        year: int | None,
        tmdb_id: str | None = None,
        imdb_id: str | None = None,
        media_type: str = "movie",
        thumb_url: str | None = None,
    ):
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """INSERT INTO library (plex_key, title, year, tmdb_id, imdb_id, media_type, thumb_url, last_scanned)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(plex_key) DO UPDATE SET
                 title=excluded.title, year=excluded.year,
                 tmdb_id=excluded.tmdb_id, imdb_id=excluded.imdb_id,
                 media_type=excluded.media_type, thumb_url=excluded.thumb_url,
                 last_scanned=excluded.last_scanned""",
            (plex_key, title, year, tmdb_id, imdb_id, media_type, thumb_url, now),
        )
        db.commit()
        db.close()

    def get_items(self, limit: int = 50, offset: int = 0) -> list[dict]:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM library ORDER BY title LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        db.close()
        return [dict(r) for r in rows]

    def scan_plex(self):
        """Connect to Plex server and scan movie library."""
        from plexapi.server import PlexServer
        plex = PlexServer(settings.plex_url, settings.plex_token)
        movies = plex.library.section("Movies")
        count = 0
        for item in movies.all():
            guids = self.extract_guids([g.id for g in item.guids])
            self.store_item(
                plex_key=str(item.ratingKey),
                title=item.title,
                year=item.year,
                tmdb_id=guids.get("tmdb_id"),
                imdb_id=guids.get("imdb_id"),
                media_type="movie",
                thumb_url=item.thumb,
            )
            count += 1
        return count

    @staticmethod
    def extract_guids(guids: list[str]) -> dict:
        result = {}
        for guid in guids:
            if guid.startswith("tmdb://"):
                result["tmdb_id"] = guid.replace("tmdb://", "")
            elif guid.startswith("imdb://"):
                result["imdb_id"] = guid.replace("imdb://", "")
        return result
```

**Step 4: Run tests to verify they pass**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_plex_scanner.py -v
# Expected: all 4 tests PASS
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add Plex scanner service with library storage and GUID extraction"
```

---

## Task 4: VidAngel Sync Service (Matching + Tag Storage)

**Files:**
- Create: `backend/plexfilter/services/sync.py`
- Create: `backend/tests/test_sync.py`

**Step 1: Write the failing tests**

`backend/tests/test_sync.py`:
```python
import pytest
from plexfilter.database import init_db, get_db
from plexfilter.services.sync import SyncService

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("plexfilter.config.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.database.settings.database_path", db_path)
    init_db()
    return db_path

@pytest.fixture
def seeded_db(test_db):
    """Seed a library item that matches a known VidAngel movie."""
    db = get_db()
    db.execute(
        "INSERT INTO library (plex_key, title, year, tmdb_id, imdb_id, media_type) VALUES (?, ?, ?, ?, ?, ?)",
        ("99999", "Operation Fortune: Ruse de Guerre", 2023, "845783", "tt7339792", "movie"),
    )
    db.commit()
    db.close()
    return test_db

def test_sync_single_title(seeded_db):
    """Should match a library item to VidAngel and store tags."""
    svc = SyncService()
    result = svc.sync_library_item(library_id=1)
    assert result["matched"] is True
    assert result["tag_count"] > 50

    db = get_db()
    match = db.execute("SELECT * FROM matches WHERE library_id = 1").fetchone()
    assert match is not None
    assert match["tag_set_id"] > 0

    tags = db.execute("SELECT * FROM tags WHERE tag_set_id = ?", (match["tag_set_id"],)).fetchall()
    assert len(tags) > 50
    first = tags[0]
    assert first["category_name"] is not None
    assert first["category_group"] is not None
    db.close()

def test_store_tags_deduplicates(seeded_db):
    """Running sync twice should not create duplicate tags."""
    svc = SyncService()
    svc.sync_library_item(library_id=1)
    svc.sync_library_item(library_id=1)

    db = get_db()
    tags = db.execute("SELECT COUNT(*) as cnt FROM tags").fetchone()
    matches = db.execute("SELECT COUNT(*) as cnt FROM matches").fetchone()
    assert matches["cnt"] == 1  # one match, not two
    db.close()
```

**Step 2: Run tests to verify they fail**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_sync.py -v
# Expected: FAIL — ModuleNotFoundError
```

**Step 3: Implement the sync service**

`backend/plexfilter/services/sync.py`:
```python
import time
from datetime import datetime, timezone
from ..database import get_db
from .vidangel import VidAngelClient

class SyncService:
    def __init__(self):
        self.va = VidAngelClient()
        self._cat_map = None

    @property
    def cat_map(self) -> dict:
        if self._cat_map is None:
            categories = self.va.get_categories()
            self._cat_map = {c["id"]: c for c in categories}
        return self._cat_map

    def sync_library_item(self, library_id: int) -> dict:
        db = get_db()
        item = db.execute("SELECT * FROM library WHERE id = ?", (library_id,)).fetchone()
        if not item:
            db.close()
            return {"matched": False, "error": "Library item not found"}

        # Search VidAngel by title
        results = self.va.search_works(item["title"], media_type="movie")
        if not results:
            db.close()
            return {"matched": False, "error": "No VidAngel results"}

        # Find best match by title + year
        matched_work = None
        for r in results:
            if r.get("year") == item["year"]:
                matched_work = r
                break
        if not matched_work:
            matched_work = results[0]  # fallback to first result

        # Get movie detail for tag_set_id
        detail = self.va.get_movie_detail(matched_work["id"])
        tag_set_ids = [
            o["tag_set_id"]
            for o in detail.get("offerings", [])
            if o.get("tag_set_id")
        ]
        if not tag_set_ids:
            db.close()
            return {"matched": False, "error": "No tag_set_id in offerings"}

        tag_set_id = tag_set_ids[0]

        # Fetch and store tags
        tag_set = self.va.get_tag_set(tag_set_id)
        tags = tag_set.get("tags", [])
        enriched = self.va.enrich_tags(tags, self.cat_map)

        # Upsert match
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """INSERT INTO matches (library_id, vidangel_work_id, tag_set_id, match_method, tag_count, last_synced)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(library_id) DO UPDATE SET
                 vidangel_work_id=excluded.vidangel_work_id,
                 tag_set_id=excluded.tag_set_id,
                 tag_count=excluded.tag_count,
                 last_synced=excluded.last_synced""",
            (library_id, matched_work["id"], tag_set_id, "title_year", len(enriched), now),
        )

        # Upsert tags
        for tag in enriched:
            db.execute(
                """INSERT INTO tags (vidangel_id, tag_set_id, category_id, category_name, category_group, description, type, start_sec, end_sec)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(vidangel_id) DO UPDATE SET
                     category_name=excluded.category_name,
                     category_group=excluded.category_group,
                     description=excluded.description""",
                (
                    tag["id"], tag_set_id, tag["category_id"],
                    tag["category_name"], tag["category_group"],
                    tag.get("description", ""), tag.get("type", "audiovisual"),
                    tag.get("start_approx", 0) or 0, tag.get("end_approx", 0) or 0,
                ),
            )

        db.commit()
        db.close()
        return {"matched": True, "tag_count": len(enriched), "tag_set_id": tag_set_id}

    def sync_all(self, on_progress=None):
        db = get_db()
        items = db.execute("SELECT id FROM library").fetchall()
        db.close()

        total = len(items)
        results = {"matched": 0, "failed": 0, "total": total}
        for i, item in enumerate(items):
            try:
                result = self.sync_library_item(item["id"])
                if result["matched"]:
                    results["matched"] += 1
                else:
                    results["failed"] += 1
                time.sleep(0.5)  # rate limit
            except Exception:
                results["failed"] += 1
            if on_progress:
                on_progress(i + 1, total)
        return results
```

Note: The `matches` table needs a UNIQUE constraint on `library_id` for the upsert to work. We need to update `database.py` — change the matches table to include `UNIQUE(library_id)`:

In `backend/plexfilter/database.py`, update the matches CREATE TABLE to:
```sql
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    library_id INTEGER NOT NULL REFERENCES library(id) UNIQUE,
    vidangel_work_id INTEGER NOT NULL,
    tag_set_id INTEGER NOT NULL,
    match_method TEXT NOT NULL DEFAULT 'tmdb',
    tag_count INTEGER DEFAULT 0,
    last_synced TEXT
);
```

**Step 4: Run tests to verify they pass**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_sync.py -v
# Expected: both tests PASS
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add VidAngel sync service — match library items and store enriched tags"
```

---

## Task 5: Profile Management + Filter Resolution

**Files:**
- Create: `backend/plexfilter/services/profiles.py`
- Create: `backend/tests/test_profiles.py`

**Step 1: Write the failing tests**

`backend/tests/test_profiles.py`:
```python
import json
import pytest
from plexfilter.database import init_db, get_db
from plexfilter.services.profiles import ProfileService

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("plexfilter.config.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.database.settings.database_path", db_path)
    init_db()
    return db_path

def test_create_profile(test_db):
    svc = ProfileService()
    profile = svc.create("Kids", filters={"Language": True, "Violence": True}, mode="skip")
    assert profile["id"] is not None
    assert profile["name"] == "Kids"

def test_update_filters(test_db):
    svc = ProfileService()
    p = svc.create("Kids", filters={"Language": True})
    svc.update(p["id"], filters={"Language": True, "Language:f-word": False})
    updated = svc.get(p["id"])
    filters = json.loads(updated["filters"])
    assert filters["Language"] is True
    assert filters["Language:f-word"] is False

def test_filter_resolution_group_enabled(test_db):
    """Tag should be filtered when its group is enabled."""
    svc = ProfileService()
    filters = {"Language": True}
    tag = {"category_group": "Language", "category_name": "f-word", "id": 100}
    assert svc.should_filter(tag, filters) is True

def test_filter_resolution_category_override(test_db):
    """Tag should NOT be filtered when its specific category is disabled."""
    svc = ProfileService()
    filters = {"Language": True, "Language:f-word": False}
    tag = {"category_group": "Language", "category_name": "f-word", "id": 100}
    assert svc.should_filter(tag, filters) is False

def test_filter_resolution_tag_override(test_db):
    """Specific tag override should take precedence."""
    svc = ProfileService()
    filters = {"Language": True, "tag:100": False}
    tag = {"category_group": "Language", "category_name": "f-word", "id": 100}
    assert svc.should_filter(tag, filters) is False

def test_filter_resolution_group_disabled(test_db):
    """Tag should NOT be filtered when its group is not in filters."""
    svc = ProfileService()
    filters = {"Language": True}
    tag = {"category_group": "Violence", "category_name": "Gore", "id": 200}
    assert svc.should_filter(tag, filters) is False

def test_list_profiles(test_db):
    svc = ProfileService()
    svc.create("Kids", filters={})
    svc.create("Adults", filters={})
    profiles = svc.list_all()
    assert len(profiles) == 2

def test_delete_profile(test_db):
    svc = ProfileService()
    p = svc.create("Temp", filters={})
    svc.delete(p["id"])
    assert svc.get(p["id"]) is None
```

**Step 2: Run tests to verify they fail**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_profiles.py -v
```

**Step 3: Implement the profile service**

`backend/plexfilter/services/profiles.py`:
```python
import json
from datetime import datetime, timezone
from ..database import get_db

class ProfileService:
    def create(self, name: str, filters: dict, mode: str = "skip", plex_user: str | None = None) -> dict:
        db = get_db()
        now = datetime.now(timezone.utc).isoformat()
        cursor = db.execute(
            "INSERT INTO profiles (name, plex_user, filters, mode, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, plex_user, json.dumps(filters), mode, now),
        )
        db.commit()
        profile_id = cursor.lastrowid
        row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        db.close()
        return dict(row)

    def get(self, profile_id: int) -> dict | None:
        db = get_db()
        row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        db.close()
        return dict(row) if row else None

    def list_all(self) -> list[dict]:
        db = get_db()
        rows = db.execute("SELECT * FROM profiles ORDER BY name").fetchall()
        db.close()
        return [dict(r) for r in rows]

    def update(self, profile_id: int, name: str | None = None, filters: dict | None = None, mode: str | None = None, plex_user: str | None = None):
        db = get_db()
        current = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if not current:
            db.close()
            return None
        db.execute(
            "UPDATE profiles SET name=?, plex_user=?, filters=?, mode=? WHERE id=?",
            (
                name or current["name"],
                plex_user if plex_user is not None else current["plex_user"],
                json.dumps(filters) if filters is not None else current["filters"],
                mode or current["mode"],
                profile_id,
            ),
        )
        db.commit()
        db.close()

    def delete(self, profile_id: int):
        db = get_db()
        db.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        db.commit()
        db.close()

    @staticmethod
    def should_filter(tag: dict, filters: dict) -> bool:
        """Three-level filter resolution: group -> category -> tag ID.
        Specific overrides general."""
        tag_id = tag.get("id") or tag.get("vidangel_id")
        category_name = tag.get("category_name", "")
        group = tag.get("category_group", "")

        # Level 3: specific tag override (highest priority)
        tag_key = f"tag:{tag_id}"
        if tag_key in filters:
            return bool(filters[tag_key])

        # Level 2: specific category override
        cat_key = f"{group}:{category_name}"
        if cat_key in filters:
            return bool(filters[cat_key])

        # Level 1: group-level toggle
        if group in filters:
            return bool(filters[group])

        return False
```

**Step 4: Run tests to verify they pass**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_profiles.py -v
# Expected: all 8 tests PASS
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add profile service with three-level filter resolution"
```

---

## Task 6: PlexAutoSkip JSON Generator

**Files:**
- Create: `backend/plexfilter/services/generator.py`
- Create: `backend/tests/test_generator.py`

**Step 1: Write the failing tests**

`backend/tests/test_generator.py`:
```python
import json
import pytest
from plexfilter.database import init_db, get_db
from plexfilter.services.generator import Generator
from plexfilter.services.profiles import ProfileService

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr("plexfilter.config.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.database.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.config.settings.plexautoskip_json_path", str(tmp_path / "custom.json"))
    init_db()
    return tmp_path

def _seed(test_db):
    """Seed library + match + tags + profile."""
    db = get_db()
    db.execute(
        "INSERT INTO library (plex_key, title, year, tmdb_id, media_type) VALUES (?, ?, ?, ?, ?)",
        ("100", "Test Movie", 2023, "55555", "movie"),
    )
    db.execute(
        "INSERT INTO matches (library_id, vidangel_work_id, tag_set_id, match_method, tag_count) VALUES (?, ?, ?, ?, ?)",
        (1, 999, 5000, "tmdb", 3),
    )
    db.execute(
        "INSERT INTO tags (vidangel_id, tag_set_id, category_id, category_name, category_group, description, type, start_sec, end_sec) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1001, 5000, 10, "f-word", "Language", "says f-word", "audio", 30.0, 31.0),
    )
    db.execute(
        "INSERT INTO tags (vidangel_id, tag_set_id, category_id, category_name, category_group, description, type, start_sec, end_sec) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1002, 5000, 14, "Gore", "Violence", "graphic blood", "audiovisual", 60.0, 65.0),
    )
    db.execute(
        "INSERT INTO tags (vidangel_id, tag_set_id, category_id, category_name, category_group, description, type, start_sec, end_sec) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (1003, 5000, 20, "Female Nudity", "Nudity", "nude scene", "visual", 120.0, 130.0),
    )
    db.commit()
    db.close()

    svc = ProfileService()
    svc.create("Kids", filters={"Language": True, "Violence": True, "Nudity": True}, mode="skip")

def test_generate_json(test_db):
    _seed(test_db)
    gen = Generator()
    output = gen.generate(profile_id=1)

    assert "tmdb://55555" in output
    segments = output["tmdb://55555"]
    assert len(segments) == 3

def test_audio_tags_get_volume_mode(test_db):
    _seed(test_db)
    gen = Generator()
    output = gen.generate(profile_id=1)
    segments = output["tmdb://55555"]
    # First tag is audio (f-word) -> volume mode
    audio_seg = [s for s in segments if s["start"] == 30000][0]
    assert audio_seg["mode"] == "volume"

def test_visual_tags_get_skip_mode(test_db):
    _seed(test_db)
    gen = Generator()
    output = gen.generate(profile_id=1)
    segments = output["tmdb://55555"]
    # Second tag is audiovisual (gore) -> skip mode
    visual_seg = [s for s in segments if s["start"] == 60000][0]
    assert visual_seg["mode"] == "skip"

def test_merge_adjacent_segments(test_db):
    """Segments within 2s should merge."""
    db = get_db()
    # Clear and add adjacent tags
    db.execute("DELETE FROM tags")
    db.execute(
        "INSERT INTO tags (vidangel_id, tag_set_id, category_id, category_name, category_group, description, type, start_sec, end_sec) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2001, 5000, 10, "f-word", "Language", "f1", "audio", 30.0, 31.0),
    )
    db.execute(
        "INSERT INTO tags (vidangel_id, tag_set_id, category_id, category_name, category_group, description, type, start_sec, end_sec) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (2002, 5000, 10, "f-word", "Language", "f2", "audio", 32.5, 33.0),
    )
    db.execute("UPDATE matches SET tag_count = 2 WHERE library_id = 1")
    db.commit()
    db.close()

    _ensure_profile()
    gen = Generator()
    output = gen.generate(profile_id=1)
    segments = output["tmdb://55555"]
    assert len(segments) == 1  # merged
    assert segments[0]["start"] == 30000
    assert segments[0]["end"] == 33000

def _ensure_profile():
    db = get_db()
    row = db.execute("SELECT * FROM profiles WHERE id = 1").fetchone()
    db.close()
    if not row:
        svc = ProfileService()
        svc.create("Kids", filters={"Language": True}, mode="skip")

def test_write_custom_json(test_db):
    _seed(test_db)
    gen = Generator()
    gen.generate_and_write(profile_id=1)
    path = test_db / "custom.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert "markers" in data
    assert "tmdb://55555" in data["markers"]

def test_filtered_tags_excluded(test_db):
    """Profile with only Language enabled should skip Violence and Nudity tags."""
    _seed(test_db)
    db = get_db()
    db.execute("UPDATE profiles SET filters = ? WHERE id = 1", (json.dumps({"Language": True}),))
    db.commit()
    db.close()

    gen = Generator()
    output = gen.generate(profile_id=1)
    segments = output.get("tmdb://55555", [])
    assert len(segments) == 1  # only the f-word tag
    assert segments[0]["start"] == 30000
```

**Step 2: Run tests to verify they fail**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_generator.py -v
```

**Step 3: Implement the generator**

`backend/plexfilter/services/generator.py`:
```python
import json
from pathlib import Path
from ..database import get_db
from ..config import settings
from .profiles import ProfileService

class Generator:
    def __init__(self):
        self.profile_svc = ProfileService()

    def generate(self, profile_id: int) -> dict:
        """Generate PlexAutoSkip marker dict for a profile. Returns {guid: [segments]}."""
        profile = self.profile_svc.get(profile_id)
        if not profile:
            return {}
        filters = json.loads(profile["filters"])

        db = get_db()
        # Join library + matches to get all matched titles
        rows = db.execute(
            """SELECT l.tmdb_id, l.imdb_id, m.tag_set_id
               FROM library l
               JOIN matches m ON m.library_id = l.id"""
        ).fetchall()

        output = {}
        for row in rows:
            tmdb_id = row["tmdb_id"]
            tag_set_id = row["tag_set_id"]
            if not tmdb_id:
                continue

            tags = db.execute(
                "SELECT * FROM tags WHERE tag_set_id = ?", (tag_set_id,)
            ).fetchall()

            segments = []
            for tag in tags:
                tag_dict = dict(tag)
                tag_dict["id"] = tag_dict["vidangel_id"]
                if not self.profile_svc.should_filter(tag_dict, filters):
                    continue
                mode = "volume" if tag["type"] == "audio" else "skip"
                segments.append({
                    "start": int(tag["start_sec"] * 1000),
                    "end": int(tag["end_sec"] * 1000),
                    "mode": mode,
                })

            segments.sort(key=lambda s: s["start"])
            segments = self._merge_segments(segments)
            if segments:
                output[f"tmdb://{tmdb_id}"] = segments

        db.close()
        return output

    @staticmethod
    def _merge_segments(segments: list[dict], gap_ms: int = 2000) -> list[dict]:
        """Merge segments that are within gap_ms of each other and have the same mode."""
        if not segments:
            return []
        merged = [segments[0].copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            if seg["mode"] == prev["mode"] and seg["start"] - prev["end"] <= gap_ms:
                prev["end"] = max(prev["end"], seg["end"])
            else:
                merged.append(seg.copy())
        return merged

    def generate_and_write(self, profile_id: int):
        """Generate and write the PlexAutoSkip custom.json file."""
        markers = self.generate(profile_id=profile_id)
        output = {"markers": markers}
        path = Path(settings.plexautoskip_json_path)
        path.write_text(json.dumps(output, indent=2))
```

**Step 4: Run tests to verify they pass**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_generator.py -v
# Expected: all 6 tests PASS
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add PlexAutoSkip JSON generator with segment merging"
```

---

## Task 7: FastAPI Routes

**Files:**
- Create: `backend/plexfilter/routes/__init__.py`
- Create: `backend/plexfilter/routes/library.py`
- Create: `backend/plexfilter/routes/profiles.py`
- Create: `backend/plexfilter/routes/sync.py`
- Create: `backend/plexfilter/routes/categories.py`
- Create: `backend/plexfilter/routes/generate.py`
- Modify: `backend/plexfilter/main.py`

**Step 1: Implement all route files**

`backend/plexfilter/routes/__init__.py`: empty file.

`backend/plexfilter/routes/library.py`:
```python
from fastapi import APIRouter, BackgroundTasks
from ..services.plex_scanner import PlexScanner

router = APIRouter(prefix="/api/library", tags=["library"])

@router.get("")
def list_library(limit: int = 50, offset: int = 0):
    scanner = PlexScanner()
    items = scanner.get_items(limit=limit, offset=offset)
    # Attach match status
    from ..database import get_db
    db = get_db()
    for item in items:
        match = db.execute(
            "SELECT tag_count FROM matches WHERE library_id = ?", (item["id"],)
        ).fetchone()
        item["match_status"] = "matched" if match else "unmatched"
        item["tag_count"] = match["tag_count"] if match else 0
    db.close()
    return {"items": items, "limit": limit, "offset": offset}

@router.get("/{library_id}")
def get_library_item(library_id: int):
    from ..database import get_db
    db = get_db()
    item = db.execute("SELECT * FROM library WHERE id = ?", (library_id,)).fetchone()
    if not item:
        db.close()
        return {"error": "Not found"}, 404
    item = dict(item)
    match = db.execute("SELECT * FROM matches WHERE library_id = ?", (library_id,)).fetchone()
    item["match"] = dict(match) if match else None
    if match:
        tags = db.execute(
            "SELECT * FROM tags WHERE tag_set_id = ? ORDER BY start_sec", (match["tag_set_id"],)
        ).fetchall()
        item["tags"] = [dict(t) for t in tags]
    else:
        item["tags"] = []
    db.close()
    return item
```

`backend/plexfilter/routes/profiles.py`:
```python
from fastapi import APIRouter
from pydantic import BaseModel
from ..services.profiles import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])

class ProfileCreate(BaseModel):
    name: str
    filters: dict = {}
    mode: str = "skip"
    plex_user: str | None = None

class ProfileUpdate(BaseModel):
    name: str | None = None
    filters: dict | None = None
    mode: str | None = None
    plex_user: str | None = None

@router.get("")
def list_profiles():
    return ProfileService().list_all()

@router.post("")
def create_profile(body: ProfileCreate):
    return ProfileService().create(body.name, body.filters, body.mode, body.plex_user)

@router.get("/{profile_id}")
def get_profile(profile_id: int):
    profile = ProfileService().get(profile_id)
    if not profile:
        return {"error": "Not found"}, 404
    return profile

@router.put("/{profile_id}")
def update_profile(profile_id: int, body: ProfileUpdate):
    ProfileService().update(profile_id, body.name, body.filters, body.mode, body.plex_user)
    return ProfileService().get(profile_id)

@router.delete("/{profile_id}")
def delete_profile(profile_id: int):
    ProfileService().delete(profile_id)
    return {"ok": True}
```

`backend/plexfilter/routes/sync.py`:
```python
from fastapi import APIRouter, BackgroundTasks
from ..services.sync import SyncService
from ..services.plex_scanner import PlexScanner

router = APIRouter(prefix="/api", tags=["sync"])

_sync_status = {"running": False, "progress": 0, "total": 0, "result": None}

def _run_sync():
    global _sync_status
    _sync_status = {"running": True, "progress": 0, "total": 0, "result": None}
    svc = SyncService()
    def on_progress(current, total):
        _sync_status["progress"] = current
        _sync_status["total"] = total
    result = svc.sync_all(on_progress=on_progress)
    _sync_status["running"] = False
    _sync_status["result"] = result

@router.post("/sync")
def start_sync(background_tasks: BackgroundTasks):
    if _sync_status["running"]:
        return {"error": "Sync already running"}
    background_tasks.add_task(_run_sync)
    return {"status": "started"}

@router.post("/sync/{library_id}")
def sync_single(library_id: int):
    svc = SyncService()
    return svc.sync_library_item(library_id)

@router.get("/sync/status")
def sync_status():
    return _sync_status

@router.post("/plex/connect")
def connect_plex(url: str, token: str):
    from ..config import settings
    settings.plex_url = url
    settings.plex_token = token
    return {"status": "connected"}

@router.post("/plex/scan")
def scan_plex(background_tasks: BackgroundTasks):
    scanner = PlexScanner()
    count = scanner.scan_plex()
    return {"scanned": count}
```

`backend/plexfilter/routes/categories.py`:
```python
from fastapi import APIRouter
from ..services.vidangel import VidAngelClient

router = APIRouter(prefix="/api/categories", tags=["categories"])

_cache = None

@router.get("")
def get_categories():
    global _cache
    if _cache is None:
        va = VidAngelClient()
        cats = va.get_categories()
        _cache = va.build_category_tree(cats)
    return _cache
```

`backend/plexfilter/routes/generate.py`:
```python
from fastapi import APIRouter
from ..services.generator import Generator

router = APIRouter(prefix="/api/generate", tags=["generate"])

@router.post("")
def generate_json(profile_id: int = 1):
    gen = Generator()
    gen.generate_and_write(profile_id=profile_id)
    return {"status": "ok"}

@router.get("/preview/{profile_id}")
def preview(profile_id: int):
    gen = Generator()
    return gen.generate(profile_id=profile_id)
```

Update `backend/plexfilter/main.py` to include all routers:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routes import library, profiles, sync, categories, generate

app = FastAPI(title="PlexFilter", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

app.include_router(library.router)
app.include_router(profiles.router)
app.include_router(sync.router)
app.include_router(categories.router)
app.include_router(generate.router)

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

**Step 2: Verify server starts and routes are registered**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m uvicorn plexfilter.main:app --port 8000 &
curl http://localhost:8000/docs  # Should return OpenAPI HTML
curl http://localhost:8000/api/health
curl http://localhost:8000/api/profiles
kill %1
```

**Step 3: Commit**

```bash
git add -A && git commit -m "feat: add FastAPI routes — library, profiles, sync, categories, generate"
```

---

## Task 8: React Frontend — Shell + Navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/Nav.tsx`
- Create: `frontend/src/pages/Library.tsx`
- Create: `frontend/src/pages/Profiles.tsx`
- Create: `frontend/src/pages/Settings.tsx`
- Create: `frontend/src/api.ts`

**Step 1: Create the API client**

`frontend/src/api.ts`:
```typescript
const BASE = '/api'

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  return res.json()
}

export const api = {
  health: () => fetchJSON<{status: string}>('/health'),
  library: (limit = 50, offset = 0) =>
    fetchJSON<{items: any[]}>(`/library?limit=${limit}&offset=${offset}`),
  libraryItem: (id: number) => fetchJSON<any>(`/library/${id}`),
  profiles: () => fetchJSON<any[]>('/profiles'),
  createProfile: (data: any) =>
    fetchJSON<any>('/profiles', { method: 'POST', body: JSON.stringify(data) }),
  updateProfile: (id: number, data: any) =>
    fetchJSON<any>(`/profiles/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteProfile: (id: number) =>
    fetchJSON<any>(`/profiles/${id}`, { method: 'DELETE' }),
  categories: () => fetchJSON<any[]>('/categories'),
  tags: (libraryId: number) => fetchJSON<any>(`/library/${libraryId}`),
  sync: () => fetchJSON<any>('/sync', { method: 'POST' }),
  syncStatus: () => fetchJSON<any>('/sync/status'),
  syncSingle: (id: number) => fetchJSON<any>(`/sync/${id}`, { method: 'POST' }),
  generate: (profileId = 1) =>
    fetchJSON<any>(`/generate?profile_id=${profileId}`, { method: 'POST' }),
  preview: (profileId: number) => fetchJSON<any>(`/generate/preview/${profileId}`),
  plexConnect: (url: string, token: string) =>
    fetchJSON<any>(`/plex/connect?url=${encodeURIComponent(url)}&token=${encodeURIComponent(token)}`, { method: 'POST' }),
  plexScan: () => fetchJSON<any>('/plex/scan', { method: 'POST' }),
}
```

**Step 2: Create Nav + page shells**

`frontend/src/components/Nav.tsx`:
```tsx
type Page = 'library' | 'profiles' | 'settings'

export default function Nav({ page, setPage }: { page: Page; setPage: (p: Page) => void }) {
  const tabs: { key: Page; label: string }[] = [
    { key: 'library', label: 'Library' },
    { key: 'profiles', label: 'Profiles' },
    { key: 'settings', label: 'Settings' },
  ]
  return (
    <nav className="flex gap-1 bg-gray-800 p-2 rounded-lg mb-6">
      {tabs.map(t => (
        <button
          key={t.key}
          onClick={() => setPage(t.key)}
          className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
            page === t.key ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-700'
          }`}
        >
          {t.label}
        </button>
      ))}
    </nav>
  )
}
```

`frontend/src/pages/Library.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

export default function Library({ onSelect }: { onSelect: (id: number) => void }) {
  const { data, isLoading } = useQuery({ queryKey: ['library'], queryFn: () => api.library() })

  if (isLoading) return <div className="text-gray-400">Loading library...</div>

  const items = data?.items || []
  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Library ({items.length} titles)</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((item: any) => (
          <button
            key={item.id}
            onClick={() => onSelect(item.id)}
            className="bg-gray-800 p-4 rounded-lg text-left hover:bg-gray-700 transition-colors"
          >
            <div className="font-semibold">{item.title}</div>
            <div className="text-sm text-gray-400">{item.year} &middot; {item.media_type}</div>
            <div className="mt-2">
              <span className={`text-xs px-2 py-1 rounded-full ${
                item.match_status === 'matched'
                  ? 'bg-green-900 text-green-300'
                  : 'bg-yellow-900 text-yellow-300'
              }`}>
                {item.match_status === 'matched' ? `${item.tag_count} tags` : 'Unmatched'}
              </span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
```

`frontend/src/pages/Profiles.tsx`:
```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { useState } from 'react'

export default function Profiles() {
  const qc = useQueryClient()
  const { data: profiles, isLoading } = useQuery({ queryKey: ['profiles'], queryFn: api.profiles })
  const [newName, setNewName] = useState('')

  const createMut = useMutation({
    mutationFn: (name: string) => api.createProfile({ name, filters: {}, mode: 'skip' }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['profiles'] }); setNewName('') },
  })

  if (isLoading) return <div className="text-gray-400">Loading...</div>

  return (
    <div>
      <h2 className="text-xl font-bold mb-4">Filter Profiles</h2>
      <div className="flex gap-2 mb-6">
        <input
          value={newName}
          onChange={e => setNewName(e.target.value)}
          placeholder="New profile name..."
          className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white flex-1"
        />
        <button
          onClick={() => newName && createMut.mutate(newName)}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white font-medium"
        >
          Create
        </button>
      </div>
      <div className="space-y-3">
        {(profiles || []).map((p: any) => (
          <div key={p.id} className="bg-gray-800 p-4 rounded-lg flex justify-between items-center">
            <div>
              <div className="font-semibold">{p.name}</div>
              <div className="text-sm text-gray-400">Mode: {p.mode}</div>
            </div>
            <span className="text-xs text-gray-500">ID: {p.id}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
```

`frontend/src/pages/Settings.tsx`:
```tsx
import { useState } from 'react'
import { api } from '../api'

export default function Settings() {
  const [plexUrl, setPlexUrl] = useState('')
  const [plexToken, setPlexToken] = useState('')
  const [status, setStatus] = useState('')

  const connect = async () => {
    setStatus('Connecting...')
    await api.plexConnect(plexUrl, plexToken)
    setStatus('Connected! Scanning library...')
    const result = await api.plexScan()
    setStatus(`Scanned ${result.scanned} items. Starting sync...`)
    await api.sync()
    setStatus('Sync started. Check Library tab for progress.')
  }

  return (
    <div className="max-w-lg">
      <h2 className="text-xl font-bold mb-4">Settings</h2>
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-gray-400 mb-1">Plex Server URL</label>
          <input
            value={plexUrl}
            onChange={e => setPlexUrl(e.target.value)}
            placeholder="http://localhost:32400"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <div>
          <label className="block text-sm text-gray-400 mb-1">Plex Token</label>
          <input
            value={plexToken}
            onChange={e => setPlexToken(e.target.value)}
            type="password"
            placeholder="Your Plex token"
            className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          />
        </div>
        <button
          onClick={connect}
          className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded text-white font-medium"
        >
          Connect &amp; Scan
        </button>
        {status && <div className="text-sm text-gray-400 mt-2">{status}</div>}
      </div>
    </div>
  )
}
```

Update `frontend/src/App.tsx`:
```tsx
import { useState } from 'react'
import Nav from './components/Nav'
import Library from './pages/Library'
import Profiles from './pages/Profiles'
import Settings from './pages/Settings'

type Page = 'library' | 'profiles' | 'settings'

export default function App() {
  const [page, setPage] = useState<Page>('library')
  const [selectedItem, setSelectedItem] = useState<number | null>(null)

  return (
    <div className="min-h-screen p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold mb-2">PlexFilter</h1>
      <p className="text-gray-400 mb-6">Content filtering for Plex</p>
      <Nav page={page} setPage={(p) => { setPage(p); setSelectedItem(null) }} />
      {page === 'library' && <Library onSelect={setSelectedItem} />}
      {page === 'profiles' && <Profiles />}
      {page === 'settings' && <Settings />}
    </div>
  )
}
```

**Step 3: Verify frontend builds**

```bash
cd /workspaces/playground/fam/plexfilter/frontend && npm run build
# Expected: builds to dist/ without errors
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add React frontend — library grid, profiles, settings, nav shell"
```

---

## Task 9: Profile Filter Editor (Three-Level Category Tree)

**Files:**
- Create: `frontend/src/components/FilterEditor.tsx`
- Modify: `frontend/src/pages/Profiles.tsx` (add edit mode)

This is the core UI component — the three-level accordion with toggles.

**Step 1: Build the FilterEditor component**

`frontend/src/components/FilterEditor.tsx`:
```tsx
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'

type Filters = Record<string, boolean>

interface Props {
  filters: Filters
  onChange: (filters: Filters) => void
}

export default function FilterEditor({ filters, onChange }: Props) {
  const { data: tree } = useQuery({ queryKey: ['categories'], queryFn: api.categories })
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  if (!tree) return <div className="text-gray-400">Loading categories...</div>

  const toggle = (key: string) => {
    const next = { ...filters, [key]: !filters[key] }
    if (!next[key]) delete next[key]
    onChange(next)
  }

  const toggleExpand = (id: number) => {
    const next = new Set(expanded)
    next.has(id) ? next.delete(id) : next.add(id)
    setExpanded(next)
  }

  const isOn = (key: string) => !!filters[key]

  // Only show the big three groups for v1
  const v1Groups = ['Language', 'Nudity', 'Sex', 'Violence']

  return (
    <div className="space-y-2">
      {(tree as any[])
        .filter((g: any) => v1Groups.includes(g.display_title))
        .map((group: any) => {
          const groupKey = group.display_title
          return (
            <div key={group.id} className="bg-gray-700 rounded-lg overflow-hidden">
              {/* Level 1: Group */}
              <div className="flex items-center justify-between p-3">
                <button
                  onClick={() => toggleExpand(group.id)}
                  className="flex items-center gap-2 text-left flex-1"
                >
                  <span className="text-xs text-gray-400">
                    {expanded.has(group.id) ? '▼' : '▶'}
                  </span>
                  <span className="font-semibold">{groupKey}</span>
                </button>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isOn(groupKey)}
                    onChange={() => toggle(groupKey)}
                    className="w-4 h-4 rounded"
                  />
                </label>
              </div>

              {/* Level 2: Categories */}
              {expanded.has(group.id) && (
                <div className="border-t border-gray-600">
                  {(group.children || []).map((cat: any) => {
                    const catKey = `${groupKey}:${cat.display_title}`
                    const catEnabled = filters[catKey] !== undefined
                      ? !!filters[catKey]
                      : isOn(groupKey)
                    return (
                      <div key={cat.id}>
                        <div className="flex items-center justify-between px-6 py-2 hover:bg-gray-600">
                          <button
                            onClick={() => cat.children?.length && toggleExpand(cat.id)}
                            className="flex items-center gap-2 flex-1 text-sm"
                          >
                            {cat.children?.length > 0 && (
                              <span className="text-xs text-gray-500">
                                {expanded.has(cat.id) ? '▼' : '▶'}
                              </span>
                            )}
                            <span>{cat.display_title}</span>
                          </button>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={catEnabled}
                              onChange={() => toggle(catKey)}
                              className="w-4 h-4 rounded"
                            />
                          </label>
                        </div>

                        {/* Level 3: Subcategories */}
                        {expanded.has(cat.id) && cat.children?.map((sub: any) => {
                          const subKey = `${groupKey}:${sub.display_title}`
                          const subEnabled = filters[subKey] !== undefined
                            ? !!filters[subKey]
                            : catEnabled
                          return (
                            <div key={sub.id} className="flex items-center justify-between px-10 py-1.5 hover:bg-gray-600">
                              <span className="text-sm text-gray-300">{sub.display_title}</span>
                              <label className="flex items-center gap-2 cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={subEnabled}
                                  onChange={() => toggle(subKey)}
                                  className="w-4 h-4 rounded"
                                />
                              </label>
                            </div>
                          )
                        })}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
    </div>
  )
}
```

**Step 2: Wire it into Profiles page** — add edit mode that shows FilterEditor when clicking a profile. Update `frontend/src/pages/Profiles.tsx` to include an "Edit" button per profile that opens a detail view with FilterEditor.

**Step 3: Verify it builds**

```bash
cd /workspaces/playground/fam/plexfilter/frontend && npm run build
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add three-level FilterEditor component with category tree toggles"
```

---

## Task 10: Title Detail View with Timeline + Tag Descriptions

**Files:**
- Create: `frontend/src/pages/TitleDetail.tsx`
- Create: `frontend/src/components/Timeline.tsx`
- Modify: `frontend/src/App.tsx` (add title detail route)

**Step 1: Build the Timeline component**

`frontend/src/components/Timeline.tsx`:
```tsx
interface Segment {
  start_sec: number
  end_sec: number
  category_group: string
  type: string
}

const COLORS: Record<string, string> = {
  Language: 'bg-yellow-500',
  Violence: 'bg-red-500',
  Nudity: 'bg-pink-500',
  Sex: 'bg-purple-500',
}

export default function Timeline({ tags, runtime }: { tags: Segment[]; runtime: number }) {
  if (!runtime || runtime === 0) return null
  return (
    <div className="relative h-8 bg-gray-700 rounded overflow-hidden">
      {tags.map((tag, i) => {
        const left = (tag.start_sec / runtime) * 100
        const width = Math.max(((tag.end_sec - tag.start_sec) / runtime) * 100, 0.3)
        const color = COLORS[tag.category_group] || 'bg-gray-500'
        return (
          <div
            key={i}
            className={`absolute top-0 h-full ${color} opacity-70`}
            style={{ left: `${left}%`, width: `${width}%` }}
            title={`${tag.category_group} @ ${Math.floor(tag.start_sec / 60)}:${String(Math.floor(tag.start_sec % 60)).padStart(2, '0')}`}
          />
        )
      })}
      <div className="absolute inset-0 flex items-center justify-between px-2 text-xs text-gray-300 pointer-events-none">
        <span>0:00</span>
        <span>{Math.floor(runtime / 60)}:{String(Math.floor(runtime % 60)).padStart(2, '0')}</span>
      </div>
    </div>
  )
}
```

**Step 2: Build the TitleDetail page**

`frontend/src/pages/TitleDetail.tsx`:
```tsx
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import Timeline from '../components/Timeline'

export default function TitleDetail({ id, onBack }: { id: number; onBack: () => void }) {
  const { data, isLoading } = useQuery({ queryKey: ['library', id], queryFn: () => api.libraryItem(id) })

  if (isLoading) return <div className="text-gray-400">Loading...</div>
  if (!data) return <div className="text-gray-400">Not found</div>

  const tags = data.tags || []
  const runtime = data.match?.tag_count ? Math.max(...tags.map((t: any) => t.end_sec), 0) + 60 : 0

  // Group tags by category_group
  const grouped: Record<string, any[]> = {}
  for (const tag of tags) {
    const g = tag.category_group || 'Other'
    if (!grouped[g]) grouped[g] = []
    grouped[g].push(tag)
  }

  const fmtTime = (sec: number) => {
    const m = Math.floor(sec / 60)
    const s = Math.floor(sec % 60)
    return `${m}:${String(s).padStart(2, '0')}`
  }

  return (
    <div>
      <button onClick={onBack} className="text-blue-400 hover:text-blue-300 mb-4">&larr; Back</button>
      <h2 className="text-2xl font-bold">{data.title}</h2>
      <div className="text-gray-400 mb-4">{data.year} &middot; {data.media_type}</div>

      {data.match ? (
        <>
          <div className="mb-4 text-sm text-gray-400">
            {tags.length} filter tags &middot; Matched via {data.match.match_method}
          </div>
          <Timeline tags={tags} runtime={runtime} />
          <div className="mt-6 space-y-6">
            {Object.entries(grouped).map(([group, groupTags]) => (
              <div key={group}>
                <h3 className="text-lg font-semibold mb-2">{group} ({groupTags.length})</h3>
                <div className="space-y-1">
                  {groupTags.map((tag: any) => (
                    <div key={tag.id} className="flex items-start gap-3 text-sm bg-gray-800 px-3 py-2 rounded">
                      <span className="text-gray-500 w-16 shrink-0">{fmtTime(tag.start_sec)}</span>
                      <span className="text-gray-400 w-24 shrink-0">{tag.category_name}</span>
                      <span className="text-gray-300">{tag.description}</span>
                      <span className="ml-auto text-xs text-gray-600">{tag.type}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <div className="bg-yellow-900 text-yellow-300 p-4 rounded-lg">
          Not matched with VidAngel. Try syncing this title.
        </div>
      )}
    </div>
  )
}
```

**Step 3: Wire into App.tsx** — update App to show TitleDetail when `selectedItem` is set.

**Step 4: Verify build**

```bash
cd /workspaces/playground/fam/plexfilter/frontend && npm run build
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add title detail view with timeline visualization and tag descriptions"
```

---

## Task 11: Docker Compose for Deployment

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`

**Step 1: Create the Dockerfile**

`Dockerfile`:
```dockerfile
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /app/frontend/dist ./static

ENV PLEXFILTER_DATABASE_PATH=/data/plexfilter.db
ENV PLEXFILTER_PLEXAUTOSKIP_JSON_PATH=/data/custom.json
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "plexfilter.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Note: Also update `main.py` to serve static files from `./static` when the directory exists (add `StaticFiles` mount for the React build).

**Step 2: Create docker-compose.yml**

`docker-compose.yml`:
```yaml
services:
  plexfilter:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - plexfilter-data:/data
    environment:
      - PLEXFILTER_PLEX_URL=${PLEX_URL:-http://host.docker.internal:32400}
      - PLEXFILTER_PLEX_TOKEN=${PLEX_TOKEN}
    restart: unless-stopped

volumes:
  plexfilter-data:
```

**Step 3: Verify build**

```bash
cd /workspaces/playground/fam/plexfilter && docker compose build
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add Dockerfile and docker-compose for deployment"
```

---

## Task 12: End-to-End Smoke Test

**Files:**
- Create: `backend/tests/test_e2e.py`

**Step 1: Write an end-to-end test that exercises the full pipeline without Plex**

`backend/tests/test_e2e.py`:
```python
"""End-to-end test: seed library → sync → create profile → generate JSON."""
import json
import pytest
from plexfilter.database import init_db, get_db
from plexfilter.services.plex_scanner import PlexScanner
from plexfilter.services.sync import SyncService
from plexfilter.services.profiles import ProfileService
from plexfilter.services.generator import Generator

@pytest.fixture
def test_env(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    json_path = str(tmp_path / "custom.json")
    monkeypatch.setattr("plexfilter.config.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.database.settings.database_path", db_path)
    monkeypatch.setattr("plexfilter.config.settings.plexautoskip_json_path", json_path)
    init_db()
    return tmp_path

def test_full_pipeline(test_env):
    # 1. Simulate Plex scan by inserting a known movie
    scanner = PlexScanner()
    scanner.store_item(
        plex_key="12345",
        title="Operation Fortune: Ruse de Guerre",
        year=2023,
        tmdb_id="845783",
        imdb_id="tt7339792",
        media_type="movie",
    )

    # 2. Sync with VidAngel
    sync = SyncService()
    result = sync.sync_library_item(library_id=1)
    assert result["matched"] is True
    assert result["tag_count"] > 100

    # 3. Create a profile filtering Language + Violence
    profiles = ProfileService()
    profile = profiles.create("Family", filters={"Language": True, "Violence": True}, mode="skip")

    # 4. Generate PlexAutoSkip JSON
    gen = Generator()
    gen.generate_and_write(profile_id=profile["id"])

    # 5. Verify output
    json_path = test_env / "custom.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert "markers" in data
    # Should have at least one GUID key
    assert len(data["markers"]) > 0
    guid_key = list(data["markers"].keys())[0]
    assert guid_key.startswith("tmdb://")
    segments = data["markers"][guid_key]
    assert len(segments) > 0
    # Each segment should have start, end, mode
    for seg in segments:
        assert "start" in seg
        assert "end" in seg
        assert seg["mode"] in ("skip", "volume")
        assert seg["start"] < seg["end"] or seg["start"] == seg["end"]
```

**Step 2: Run it**

```bash
cd /workspaces/playground/fam/plexfilter/backend && python -m pytest tests/test_e2e.py -v
# Expected: PASS — full pipeline works end-to-end
```

**Step 3: Commit**

```bash
git add -A && git commit -m "test: add end-to-end smoke test for full pipeline"
```

---

## Summary

| Task | Description | Dependencies |
|------|-------------|-------------|
| 1 | Project scaffolding (FastAPI + React + SQLite) | None |
| 2 | VidAngel client service | Task 1 |
| 3 | Plex scanner service | Task 1 |
| 4 | VidAngel sync service (matching + tag storage) | Tasks 2, 3 |
| 5 | Profile management + filter resolution | Task 1 |
| 6 | PlexAutoSkip JSON generator | Tasks 4, 5 |
| 7 | FastAPI routes (all endpoints) | Tasks 2-6 |
| 8 | React frontend shell + navigation + pages | Task 7 |
| 9 | FilterEditor component (three-level tree) | Task 8 |
| 10 | Title detail view with timeline | Task 8 |
| 11 | Docker Compose for deployment | Tasks 7-10 |
| 12 | End-to-end smoke test | Tasks 2-6 |
