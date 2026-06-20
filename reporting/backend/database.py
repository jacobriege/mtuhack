import sqlite3

DB_PATH = "reporting.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id        TEXT PRIMARY KEY,
            robot_id  TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            data      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS images (
            id        TEXT PRIMARY KEY,
            filename  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS violations (
            violationId TEXT PRIMARY KEY,
            type        TEXT NOT NULL,
            timestamp   INTEGER NOT NULL,
            flagged     INTEGER NOT NULL DEFAULT 0,
            read        INTEGER NOT NULL DEFAULT 0,
            image       TEXT NOT NULL,
            blackbox    TEXT NOT NULL,
            headbox     TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
