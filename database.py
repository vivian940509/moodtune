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
        existing_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(mood_entries)"))
        }
        sqlite_migrations = {
            "visitor_id": "ALTER TABLE mood_entries ADD COLUMN visitor_id TEXT",
            "mood_text": "ALTER TABLE mood_entries ADD COLUMN mood_text TEXT",
            "diary_text": "ALTER TABLE mood_entries ADD COLUMN diary_text TEXT",
        }
        for column_name, statement in sqlite_migrations.items():
            if column_name not in existing_columns:
                connection.execute(text(statement))
        user_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(users)"))}
        for column_name, statement in {
            "email": "ALTER TABLE users ADD COLUMN email TEXT",
            "password_hash": "ALTER TABLE users ADD COLUMN password_hash TEXT",
        }.items():
            if column_name not in user_columns:
                connection.execute(text(statement))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)"))
        favorite_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(favorite_songs)"))}
        if "visitor_id" not in favorite_columns:
            connection.execute(text("ALTER TABLE favorite_songs ADD COLUMN visitor_id TEXT"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_favorite_owner_song ON favorite_songs (visitor_id, track_name, artist_name)"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_mood_entries_visitor_created "
                "ON mood_entries (visitor_id, created_at DESC)"
            )
        )
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


def save_analysis(
    song,
    mood,
    context,
    result,
    visitor_id=None,
    mood_text="",
    diary_text="",
):
    try:
        with db_connection() as connection:
            entry_id = _insert_and_get_id(
                connection,
                """
                INSERT INTO mood_entries (
                    visitor_id, mood, listening_context, mood_text, diary_text
                )
                VALUES (:visitor_id, :mood, :context, :mood_text, :diary_text)
                """,
                {
                    "visitor_id": visitor_id,
                    "mood": mood,
                    "context": context,
                    "mood_text": mood_text or None,
                    "diary_text": diary_text or None,
                },
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


def fetch_history(limit=30, visitor_id=None):
    try:
        with db_connection() as connection:
            visitor_filter = ""
            params = {"limit": limit}
            if visitor_id:
                visitor_filter = "WHERE me.visitor_id = :visitor_id"
                params["visitor_id"] = visitor_id
            rows = connection.execute(
                text(
                    f"""
                    SELECT
                        ar.id,
                        me.created_at,
                        me.mood,
                        me.listening_context,
                        me.mood_text,
                        me.diary_text,
                        si.track_name,
                        si.artist_name,
                        si.artwork_url,
                        ar.temperature,
                        ar.drift_need,
                        ar.music_profile
                    FROM analysis_results ar
                    JOIN mood_entries me ON me.id = ar.mood_entry_id
                    JOIN song_inputs si ON si.id = ar.song_input_id
                    {visitor_filter}
                    ORDER BY me.created_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def fetch_trends(limit=7, visitor_id=None):
    rows, error = fetch_history(limit=limit, visitor_id=visitor_id)
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


def save_preferences(visitor_id, music_language, favorite_genre, kpop_group=""):
    try:
        with db_connection() as connection:
            params = {
                "visitor_id": visitor_id,
                "music_language": music_language,
                "favorite_genre": favorite_genre,
                "kpop_group": kpop_group or None,
            }
            if connection.dialect.name == "postgresql":
                statement = """
                    INSERT INTO user_preferences (
                        visitor_id, music_language, favorite_genre, kpop_group
                    )
                    VALUES (
                        :visitor_id, :music_language, :favorite_genre, :kpop_group
                    )
                    ON CONFLICT (visitor_id) DO UPDATE SET
                        music_language = EXCLUDED.music_language,
                        favorite_genre = EXCLUDED.favorite_genre,
                        kpop_group = EXCLUDED.kpop_group,
                        updated_at = NOW()
                """
            elif connection.dialect.name == "mysql":
                statement = """
                    INSERT INTO user_preferences (
                        visitor_id, music_language, favorite_genre, kpop_group
                    )
                    VALUES (
                        :visitor_id, :music_language, :favorite_genre, :kpop_group
                    )
                    ON DUPLICATE KEY UPDATE
                        music_language = VALUES(music_language),
                        favorite_genre = VALUES(favorite_genre),
                        kpop_group = VALUES(kpop_group),
                        updated_at = CURRENT_TIMESTAMP
                """
            else:
                statement = """
                    INSERT INTO user_preferences (
                        visitor_id, music_language, favorite_genre, kpop_group
                    )
                    VALUES (
                        :visitor_id, :music_language, :favorite_genre, :kpop_group
                    )
                    ON CONFLICT (visitor_id) DO UPDATE SET
                        music_language = excluded.music_language,
                        favorite_genre = excluded.favorite_genre,
                        kpop_group = excluded.kpop_group,
                        updated_at = CURRENT_TIMESTAMP
                """
            connection.execute(text(statement), params)
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def fetch_preferences(visitor_id):
    try:
        with db_connection() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT visitor_id, music_language, favorite_genre, kpop_group
                    FROM user_preferences
                    WHERE visitor_id = :visitor_id
                    """
                ),
                {"visitor_id": visitor_id},
            ).first()
            return (dict(row._mapping) if row else None), None
    except SQLAlchemyError as exc:
        return None, str(exc)


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


def save_favorite_song(song, visitor_id=None):
    try:
        with db_connection() as connection:
            params = {
                "visitor_id": visitor_id,
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
                        visitor_id, itunes_track_id, track_name, artist_name, album_name, genre,
                        artwork_url, preview_url, apple_music_url, youtube_music_url,
                        spotify_url, soundcloud_url
                    )
                    VALUES (
                        :visitor_id, :track_id, :track_name, :artist_name, :album_name, :genre,
                        :artwork_url, :preview_url, :apple_music_url, :youtube_music_url,
                        :spotify_url, :soundcloud_url
                    )
                    ON CONFLICT (visitor_id, track_name, artist_name) DO NOTHING
                """
            elif connection.dialect.name == "mysql":
                statement = """
                    INSERT IGNORE INTO favorite_songs (
                        visitor_id, itunes_track_id, track_name, artist_name, album_name, genre,
                        artwork_url, preview_url, apple_music_url, youtube_music_url,
                        spotify_url, soundcloud_url
                    )
                    VALUES (
                        :visitor_id, :track_id, :track_name, :artist_name, :album_name, :genre,
                        :artwork_url, :preview_url, :apple_music_url, :youtube_music_url,
                        :spotify_url, :soundcloud_url
                    )
                """
            else:
                statement = """
                    INSERT OR IGNORE INTO favorite_songs (
                        visitor_id, itunes_track_id, track_name, artist_name, album_name, genre,
                        artwork_url, preview_url, apple_music_url, youtube_music_url,
                        spotify_url, soundcloud_url
                    )
                    VALUES (
                        :visitor_id, :track_id, :track_name, :artist_name, :album_name, :genre,
                        :artwork_url, :preview_url, :apple_music_url, :youtube_music_url,
                        :spotify_url, :soundcloud_url
                    )
                """
            connection.execute(text(statement), params)
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def fetch_favorite_songs(limit=50, visitor_id=None):
    try:
        with db_connection() as connection:
            visitor_filter = "visitor_id IS NULL"
            params = {"limit": limit}
            if visitor_id is not None:
                visitor_filter = "visitor_id = :visitor_id"
                params["visitor_id"] = visitor_id
            rows = connection.execute(
                text(
                    f"""
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
                    WHERE {visitor_filter}
                    ORDER BY created_at DESC
                    LIMIT :limit
                    """
                ),
                params,
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)

# --- Account helpers (v2) ---
def create_user(email, display_name, password_hash):
    try:
        with db_connection() as connection:
            user_id = _insert_and_get_id(connection, """
                INSERT INTO users (email, display_name, password_hash)
                VALUES (:email, :display_name, :password_hash)
            """, {"email": email.lower().strip(), "display_name": display_name.strip(), "password_hash": password_hash})
            return user_id, None
    except SQLAlchemyError as exc:
        return None, str(exc)


def fetch_user_by_email(email):
    try:
        with db_connection() as connection:
            row = connection.execute(text("""
                SELECT id, email, display_name, password_hash FROM users WHERE LOWER(email) = :email
            """), {"email": email.lower().strip()}).first()
            return (dict(row._mapping) if row else None), None
    except SQLAlchemyError as exc:
        return None, str(exc)


def fetch_user_by_id(user_id):
    try:
        with db_connection() as connection:
            row = connection.execute(text("""
                SELECT id, email, display_name FROM users WHERE id = :id
            """), {"id": user_id}).first()
            return (dict(row._mapping) if row else None), None
    except SQLAlchemyError as exc:
        return None, str(exc)


def migrate_visitor_to_account(old_visitor_id, account_visitor_id):
    """Move this browser's pre-login history/preferences into the newly registered account."""
    try:
        with db_connection() as connection:
            connection.execute(text("UPDATE mood_entries SET visitor_id=:new WHERE visitor_id=:old"), {"new": account_visitor_id, "old": old_visitor_id})
            old_pref = connection.execute(text("SELECT music_language, favorite_genre, kpop_group FROM user_preferences WHERE visitor_id=:old"), {"old": old_visitor_id}).first()
            if old_pref:
                connection.execute(text("DELETE FROM user_preferences WHERE visitor_id=:new"), {"new": account_visitor_id})
                connection.execute(text("UPDATE user_preferences SET visitor_id=:new WHERE visitor_id=:old"), {"new": account_visitor_id, "old": old_visitor_id})
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)
