import os
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError


DEFAULT_DATABASE_URL = "mysql+pymysql://root:@localhost/moodtune"


def get_database_url():
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if database_url.startswith("mysql://"):
        return database_url.replace("mysql://", "mysql+pymysql://", 1)
    return database_url


def get_engine():
    return create_engine(get_database_url(), pool_pre_ping=True, future=True)


@contextmanager
def db_connection():
    engine = get_engine()
    with engine.begin() as connection:
        yield connection


def save_analysis(song, mood, context, result):
    try:
        with db_connection() as connection:
            entry = connection.execute(
                text(
                    """
                    INSERT INTO mood_entries (mood, listening_context)
                    VALUES (:mood, :context)
                    """
                ),
                {"mood": mood, "context": context},
            )
            entry_id = entry.lastrowid

            song_insert = connection.execute(
                text(
                    """
                    INSERT INTO song_inputs (
                        mood_entry_id, itunes_track_id, track_name, artist_name,
                        album_name, genre, artwork_url, preview_url
                    )
                    VALUES (
                        :entry_id, :track_id, :track_name, :artist_name,
                        :album_name, :genre, :artwork_url, :preview_url
                    )
                    """
                ),
                {
                    "entry_id": entry_id,
                    "track_id": song.get("track_id"),
                    "track_name": song.get("track_name"),
                    "artist_name": song.get("artist_name"),
                    "album_name": song.get("album_name"),
                    "genre": song.get("genre"),
                    "artwork_url": song.get("artwork_url"),
                    "preview_url": song.get("preview_url"),
                },
            )
            song_id = song_insert.lastrowid

            analysis = connection.execute(
                text(
                    """
                    INSERT INTO analysis_results (
                        mood_entry_id, song_input_id, temperature, drift_need,
                        music_profile, analysis_text, suggestion_text
                    )
                    VALUES (
                        :entry_id, :song_id, :temperature, :drift_need,
                        :music_profile, :analysis_text, :suggestion_text
                    )
                    """
                ),
                {
                    "entry_id": entry_id,
                    "song_id": song_id,
                    "temperature": result["temperature"],
                    "drift_need": result["drift_need"],
                    "music_profile": result["music_profile"],
                    "analysis_text": result["analysis"],
                    "suggestion_text": result["suggestion"],
                },
            )
            return analysis.lastrowid, None
    except SQLAlchemyError as exc:
        return None, str(exc)


def fetch_history(limit=30):
    try:
        with db_connection() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        ar.id,
                        me.created_at,
                        me.mood,
                        me.listening_context,
                        si.track_name,
                        si.artist_name,
                        si.artwork_url,
                        ar.temperature,
                        ar.drift_need,
                        ar.music_profile
                    FROM analysis_results ar
                    JOIN mood_entries me ON me.id = ar.mood_entry_id
                    JOIN song_inputs si ON si.id = ar.song_input_id
                    ORDER BY me.created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def fetch_trends(limit=7):
    rows, error = fetch_history(limit=limit)
    if error or not rows:
        return None, error

    average_temperature = round(
        sum(int(row["temperature"] or 0) for row in rows) / len(rows)
    )
    mood_counts = {}
    context_counts = {}
    for row in rows:
        mood_counts[row["mood"]] = mood_counts.get(row["mood"], 0) + 1
        context_counts[row["listening_context"]] = context_counts.get(row["listening_context"], 0) + 1

    top_mood = max(mood_counts, key=mood_counts.get)
    top_context = max(context_counts, key=context_counts.get)
    return {
        "count": len(rows),
        "average_temperature": average_temperature,
        "top_mood": top_mood,
        "top_context": top_context,
        "recent_tracks": rows[:3],
    }, None
