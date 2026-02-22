import sqlite3
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
            library_id INTEGER NOT NULL REFERENCES library(id) UNIQUE,
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
