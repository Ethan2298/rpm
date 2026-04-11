import sqlite3
from pathlib import Path

from backend.config import settings


def dict_factory(cursor: sqlite3.Cursor, row: tuple) -> dict:
    """Convert sqlite3 rows to dicts."""
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


def get_db() -> sqlite3.Connection:
    """Return a database connection with dict row factory."""
    db_path = Path(settings.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables() -> None:
    """Create all application tables if they don't exist."""
    conn = get_db()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cars (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                make TEXT NOT NULL,
                model TEXT NOT NULL,
                trim TEXT,
                price REAL,
                mileage INTEGER,
                exterior_color TEXT,
                interior_color TEXT,
                engine TEXT,
                transmission TEXT,
                vin TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'available',
                condition TEXT DEFAULT 'used',
                description TEXT,
                highlights TEXT,
                image_url TEXT,
                date_listed TEXT DEFAULT (date('now')),
                views INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                phone TEXT,
                email TEXT,
                interested_car_id INTEGER,
                budget_range TEXT,
                timeline TEXT DEFAULT 'exploring',
                lead_score INTEGER DEFAULT 1,
                status TEXT DEFAULT 'new',
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (interested_car_id) REFERENCES cars(id)
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER NOT NULL,
                car_id INTEGER,
                appointment_type TEXT DEFAULT 'call',
                preferred_date TEXT,
                preferred_time TEXT,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (car_id) REFERENCES cars(id)
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                phone_number TEXT NOT NULL,
                messages TEXT DEFAULT '[]',
                started_at TEXT DEFAULT (datetime('now')),
                last_message_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'active',
                FOREIGN KEY (lead_id) REFERENCES leads(id)
            );
            """
        )
        conn.commit()
    finally:
        conn.close()
