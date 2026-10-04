import os
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_URL = f"sqlite:///{(BASE_DIR / 'database' / 'moodtune.local.db').as_posix()}"
_initialized_sqlite_urls = set()


def get_database_url():
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    if database_url.startswith("mysql://"):
        return database_url.replace("mysql://", "mysql+pymysql://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg2://", 1)
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return database_url


def get_engine():
    database_url = get_database_url()
    if database_url.startswith("postgresql+psycopg2://"):
        return create_engine(
            database_url,
            connect_args={"sslmode": "require"},
            pool_pre_ping=True,
            poolclass=NullPool,
            future=True,
        )
    if database_url.startswith("sqlite:///"):
        database_path = Path(database_url.replace("sqlite:///", "", 1))
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, pool_pre_ping=True, future=True)
    return create_engine(database_url, pool_pre_ping=True, future=True)


def _initialize_sqlite(engine):
    database_url = str(engine.url)
    if engine.dialect.name != "sqlite" or database_url in _initialized_sqlite_urls:
        return

    schema_path = BASE_DIR / "database" / "schema_sqlite.sql"
    statements = [
        statement.strip()
        for statement in schema_path.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys = ON"))
        for statement in statements:
            connection.execute(text(statement))
    _initialized_sqlite_urls.add(database_url)


@contextmanager
def db_connection():
    engine = get_engine()
    _initialize_sqlite(engine)
    with engine.begin() as connection:
        if connection.dialect.name == "sqlite":
            connection.execute(text("PRAGMA foreign_keys = ON"))
        yield connection


def _insert_and_get_id(connection, statement, params):
    if connection.dialect.name == "postgresql":
        return connection.execute(text(f"{statement} RETURNING id"), params).scalar_one()
    result = connection.execute(text(statement), params)
    return result.lastrowid


def save_analysis(song, mood, context, result):
    try:
        with db_connection() as connection:
            entry_id = _insert_and_get_id(
                connection,
                """
                INSERT INTO mood_entries (mood, listening_context)
                VALUES (:mood, :context)
                """,
                {"mood": mood, "context": context},
            )

            song_id = _insert_and_get_id(
                connection,
                """
                INSERT INTO song_inputs (
                    mood_entry_id, itunes_track_id, track_name, artist_name,
                    album_name, genre, artwork_url, preview_url
                )
                VALUES (
                    :entry_id, :track_id, :track_name, :artist_name,
                    :album_name, :genre, :artwork_url, :preview_url
                )
                """,
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

            analysis_id = _insert_and_get_id(
                connection,
                """
                INSERT INTO analysis_results (
                    mood_entry_id, song_input_id, temperature, drift_need,
                    music_profile, analysis_text, suggestion_text
                )
                VALUES (
                    :entry_id, :song_id, :temperature, :drift_need,
                    :music_profile, :analysis_text, :suggestion_text
                )
                """,
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
            return analysis_id, None
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


def fetch_song_leaderboard(limit=10):
    try:
        with db_connection() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        si.track_name,
                        si.artist_name,
                        si.artwork_url,
                        si.genre,
                        COUNT(*) AS play_count,
                        ROUND(AVG(ar.temperature)) AS average_temperature,
                        MAX(me.created_at) AS last_played_at
                    FROM analysis_results ar
                    JOIN mood_entries me ON me.id = ar.mood_entry_id
                    JOIN song_inputs si ON si.id = ar.song_input_id
                    GROUP BY si.track_name, si.artist_name, si.artwork_url, si.genre
                    ORDER BY play_count DESC, average_temperature DESC, last_played_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def save_favorite_song(song):
    try:
        with db_connection() as connection:
            params = {
                "track_id": song.get("track_id"),
                "track_name": song.get("track_name"),
                "artist_name": song.get("artist_name"),
                "album_name": song.get("album_name"),
                "genre": song.get("genre"),
                "artwork_url": song.get("artwork_url"),
                "preview_url": song.get("preview_url"),
                "apple_music_url": song.get("apple_music_url"),
                "youtube_music_url": song.get("youtube_music_url"),
                "spotify_url": song.get("spotify_url"),
                "soundcloud_url": song.get("soundcloud_url"),
            }
            if connection.dialect.name == "postgresql":
                statement = """
                    INSERT INTO favorite_songs (
                        itunes_track_id, track_name, artist_name, album_name, genre,
                        artwork_url, preview_url, apple_music_url, youtube_music_url,
                        spotify_url, soundcloud_url
                    )
                    VALUES (
                        :track_id, :track_name, :artist_name, :album_name, :genre,
                        :artwork_url, :preview_url, :apple_music_url, :youtube_music_url,
                        :spotify_url, :soundcloud_url
                    )
                    ON CONFLICT (track_name, artist_name) DO NOTHING
                """
            elif connection.dialect.name == "mysql":
                statement = """
                    INSERT IGNORE INTO favorite_songs (
                        itunes_track_id, track_name, artist_name, album_name, genre,
                        artwork_url, preview_url, apple_music_url, youtube_music_url,
                        spotify_url, soundcloud_url
                    )
                    VALUES (
                        :track_id, :track_name, :artist_name, :album_name, :genre,
                        :artwork_url, :preview_url, :apple_music_url, :youtube_music_url,
                        :spotify_url, :soundcloud_url
                    )
                """
            else:
                statement = """
                    INSERT OR IGNORE INTO favorite_songs (
                        itunes_track_id, track_name, artist_name, album_name, genre,
                        artwork_url, preview_url, apple_music_url, youtube_music_url,
                        spotify_url, soundcloud_url
                    )
                    VALUES (
                        :track_id, :track_name, :artist_name, :album_name, :genre,
                        :artwork_url, :preview_url, :apple_music_url, :youtube_music_url,
                        :spotify_url, :soundcloud_url
                    )
                """
            connection.execute(text(statement), params)
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def fetch_favorite_songs(limit=50):
    try:
        with db_connection() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT
                        id,
                        itunes_track_id,
                        track_name,
                        artist_name,
                        album_name,
                        genre,
                        artwork_url,
                        preview_url,
                        apple_music_url,
                        youtube_music_url,
                        spotify_url,
                        soundcloud_url,
                        created_at
                    FROM favorite_songs
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)
