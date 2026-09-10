
import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path("bot.db")


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS music_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                track_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.commit()


def add_music_report(
    user_id: int,
    username: Optional[str],
    track_id: str,
) -> int:

    with get_connection() as connection:

        cursor = connection.execute(
            """
            INSERT INTO music_reports (
                user_id,
                username,
                track_id
            )
            VALUES (?, ?, ?)
            """,
            (
                user_id,
                username,
                track_id,
            ),
        )

        connection.commit()

        return int(cursor.lastrowid)


def get_music_reports(limit: int = 50):

    with get_connection() as connection:

        cursor = connection.execute(
            """
            SELECT
                id,
                user_id,
                username,
                track_id,
                created_at
            FROM music_reports
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

        return cursor.fetchall()
