import json
import os
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from time import perf_counter

from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


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


@lru_cache(maxsize=4)
def _build_engine(database_url):
    if database_url.startswith("postgresql+psycopg2://"):
        return create_engine(
            database_url,
            connect_args={"sslmode": "require", "connect_timeout": 3},
            pool_size=1,
            max_overflow=0,
            pool_timeout=5,
            pool_recycle=300,
            pool_pre_ping=True,
            future=True,
        )
    if database_url.startswith("sqlite:///"):
        database_path = Path(database_url.replace("sqlite:///", "", 1))
        database_path.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, pool_pre_ping=True, future=True)
    return create_engine(database_url, pool_pre_ping=True, future=True)


def get_engine():
    """Reuse one small connection pool per database URL on warm instances."""
    return _build_engine(get_database_url())


def _log_database_timing(engine, checkout_ms, total_ms):
    if not (os.getenv("VERCEL") or os.getenv("PERFORMANCE_LOGS") == "1"):
        return
    print(
        json.dumps(
            {
                "event": "database_timing",
                "dialect": engine.url.get_backend_name(),
                "checkout_ms": round(checkout_ms, 1),
                "total_ms": round(total_ms, 1),
            }
        ),
        flush=True,
    )


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
            "email_verified_at": "ALTER TABLE users ADD COLUMN email_verified_at TEXT",
        }.items():
            if column_name not in user_columns:
                connection.execute(text(statement))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email)"))
        favorite_columns = {row[1] for row in connection.execute(text("PRAGMA table_info(favorite_songs)"))}
        if "visitor_id" not in favorite_columns:
            connection.execute(text("ALTER TABLE favorite_songs ADD COLUMN visitor_id TEXT"))
        connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_favorite_owner_song ON favorite_songs (visitor_id, track_name, artist_name)"))
        connection.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_recipient_sender ON messages (recipient_id, sender_id, created_at)"))
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_mood_entries_visitor_created "
                "ON mood_entries (visitor_id, created_at DESC)"
            )
        )
    _initialized_sqlite_urls.add(database_url)


@contextmanager
def db_connection():
    started_at = perf_counter()
    engine = get_engine()
    _initialize_sqlite(engine)
    checkout_started_at = perf_counter()
    checkout_ms = 0.0
    try:
        with engine.begin() as connection:
            checkout_ms = (perf_counter() - checkout_started_at) * 1000
            if connection.dialect.name == "sqlite":
                connection.execute(text("PRAGMA foreign_keys = ON"))
            yield connection
    finally:
        _log_database_timing(
            engine,
            checkout_ms=checkout_ms,
            total_ms=(perf_counter() - started_at) * 1000,
        )


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


def save_song_feedback(visitor_id, song, feedback_type):
    if feedback_type not in {"dislike", "tag_mismatch"}:
        return False, "無效的歌曲回饋。"
    try:
        with db_connection() as connection:
            params = {
                "visitor_id": visitor_id,
                "track_id": song.get("track_id"),
                "track_name": song.get("track_name"),
                "artist_name": song.get("artist_name"),
                "genre": song.get("genre"),
                "feedback_type": feedback_type,
            }
            if connection.dialect.name == "postgresql":
                statement = """
                    INSERT INTO song_feedback
                    (visitor_id, itunes_track_id, track_name, artist_name, genre, feedback_type)
                    VALUES (:visitor_id, :track_id, :track_name, :artist_name, :genre, :feedback_type)
                    ON CONFLICT (visitor_id, track_name, artist_name, feedback_type) DO NOTHING
                """
            elif connection.dialect.name == "mysql":
                statement = """
                    INSERT IGNORE INTO song_feedback
                    (visitor_id, itunes_track_id, track_name, artist_name, genre, feedback_type)
                    VALUES (:visitor_id, :track_id, :track_name, :artist_name, :genre, :feedback_type)
                """
            else:
                statement = """
                    INSERT OR IGNORE INTO song_feedback
                    (visitor_id, itunes_track_id, track_name, artist_name, genre, feedback_type)
                    VALUES (:visitor_id, :track_id, :track_name, :artist_name, :genre, :feedback_type)
                """
            connection.execute(text(statement), params)
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def fetch_song_feedback(visitor_id):
    try:
        with db_connection() as connection:
            rows = connection.execute(text("""
                SELECT itunes_track_id, track_name, artist_name, genre, feedback_type
                FROM song_feedback WHERE visitor_id = :visitor_id
            """), {"visitor_id": visitor_id})
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def delete_favorite_song(favorite_id, visitor_id=None):
    """Delete one favorite only when it belongs to the current visitor/account."""
    try:
        with db_connection() as connection:
            result = connection.execute(
                text(
                    """
                    DELETE FROM favorite_songs
                    WHERE id = :favorite_id AND visitor_id = :visitor_id
                    """
                ),
                {"favorite_id": favorite_id, "visitor_id": visitor_id},
            )
            return result.rowcount > 0, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def save_journal_entry(visitor_id, title, body, mood=""):
    try:
        with db_connection() as connection:
            entry_id = _insert_and_get_id(
                connection,
                """
                INSERT INTO journal_entries (visitor_id, title, body, mood)
                VALUES (:visitor_id, :title, :body, :mood)
                """,
                {"visitor_id": visitor_id, "title": title or None, "body": body, "mood": mood or None},
            )
            return entry_id, None
    except SQLAlchemyError as exc:
        return None, str(exc)


def fetch_journal_entries(visitor_id, limit=50):
    try:
        with db_connection() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, title, body, mood, created_at
                    FROM journal_entries
                    WHERE visitor_id = :visitor_id
                    ORDER BY created_at DESC, id DESC
                    LIMIT :limit
                    """
                ),
                {"visitor_id": visitor_id, "limit": limit},
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def search_users(query, current_user_id):
    try:
        with db_connection() as connection:
            rows = connection.execute(
                text(
                    """
                    SELECT id, email, display_name
                    FROM users
                    WHERE id <> :current_user_id
                      AND (LOWER(email) LIKE :query OR LOWER(display_name) LIKE :query)
                    ORDER BY display_name, email
                    LIMIT 20
                    """
                ),
                {"current_user_id": current_user_id, "query": f"%{query.lower().strip()}%"},
            )
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def send_friend_request(requester_id, addressee_id):
    if requester_id == addressee_id:
        return False, "不能加自己為好友。"
    try:
        with db_connection() as connection:
            existing = connection.execute(
                text(
                    """
                    SELECT id, status FROM friendships
                    WHERE (requester_id = :requester_id AND addressee_id = :addressee_id)
                       OR (requester_id = :addressee_id AND addressee_id = :requester_id)
                    LIMIT 1
                    """
                ),
                {"requester_id": requester_id, "addressee_id": addressee_id},
            ).first()
            if existing:
                return False, "好友申請已存在或你們已經是好友。"
            _insert_and_get_id(
                connection,
                "INSERT INTO friendships (requester_id, addressee_id, status) VALUES (:requester_id, :addressee_id, 'pending')",
                {"requester_id": requester_id, "addressee_id": addressee_id},
            )
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def fetch_friend_data(user_id):
    try:
        with db_connection() as connection:
            friends = connection.execute(text("""
                SELECT u.id, u.display_name, u.email
                FROM friendships f JOIN users u ON u.id = CASE
                    WHEN f.requester_id = :user_id THEN f.addressee_id ELSE f.requester_id END
                WHERE (f.requester_id = :user_id OR f.addressee_id = :user_id) AND f.status = 'accepted'
                ORDER BY u.display_name
            """), {"user_id": user_id})
            pending = connection.execute(text("""
                SELECT f.id, u.id AS user_id, u.display_name, u.email
                FROM friendships f JOIN users u ON u.id = f.requester_id
                WHERE f.addressee_id = :user_id AND f.status = 'pending'
                ORDER BY f.created_at DESC
            """), {"user_id": user_id})
            return ([dict(row._mapping) for row in friends], [dict(row._mapping) for row in pending]), None
    except SQLAlchemyError as exc:
        return ([], []), str(exc)


def respond_friend_request(friendship_id, user_id, status):
    if status not in {"accepted", "declined"}:
        return False, "無效的好友申請狀態。"
    try:
        with db_connection() as connection:
            result = connection.execute(text("""
                UPDATE friendships SET status = :status
                WHERE id = :id AND addressee_id = :user_id AND status = 'pending'
            """), {"id": friendship_id, "user_id": user_id, "status": status})
            return result.rowcount > 0, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def send_message(sender_id, recipient_id, body):
    try:
        with db_connection() as connection:
            allowed = connection.execute(text("""
                SELECT id FROM friendships
                WHERE ((requester_id = :sender_id AND addressee_id = :recipient_id)
                    OR (requester_id = :recipient_id AND addressee_id = :sender_id))
                  AND status = 'accepted'
            """), {"sender_id": sender_id, "recipient_id": recipient_id}).first()
            if not allowed:
                return None, "請先成為好友才能聊天。"
            message_id = _insert_and_get_id(connection, """
                INSERT INTO messages (sender_id, recipient_id, body)
                VALUES (:sender_id, :recipient_id, :body)
            """, {"sender_id": sender_id, "recipient_id": recipient_id, "body": body})
            return message_id, None
    except SQLAlchemyError as exc:
        return None, str(exc)


def fetch_messages(user_id, friend_id, limit=100):
    try:
        with db_connection() as connection:
            rows = connection.execute(text("""
                SELECT m.id, m.sender_id, m.recipient_id, m.body, m.created_at,
                       u.display_name AS sender_name
                FROM messages m JOIN users u ON u.id = m.sender_id
                WHERE ((m.sender_id = :user_id AND m.recipient_id = :friend_id)
                    OR (m.sender_id = :friend_id AND m.recipient_id = :user_id))
                ORDER BY m.created_at ASC, m.id ASC LIMIT :limit
            """), {"user_id": user_id, "friend_id": friend_id, "limit": limit})
            return [dict(row._mapping) for row in rows], None
    except SQLAlchemyError as exc:
        return [], str(exc)


def create_account_token(user_id, token_hash, token_type, expires_at):
    try:
        with db_connection() as connection:
            _insert_and_get_id(connection, """
                INSERT INTO account_tokens (user_id, token_hash, token_type, expires_at)
                VALUES (:user_id, :token_hash, :token_type, :expires_at)
            """, {"user_id": user_id, "token_hash": token_hash, "token_type": token_type, "expires_at": expires_at})
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def consume_account_token(token_hash, token_type, now):
    try:
        with db_connection() as connection:
            row = connection.execute(text("""
                SELECT id, user_id FROM account_tokens
                WHERE token_hash = :token_hash AND token_type = :token_type
                  AND used_at IS NULL AND expires_at > :now
                LIMIT 1
            """), {"token_hash": token_hash, "token_type": token_type, "now": now}).first()
            if not row:
                return None, None
            connection.execute(text("UPDATE account_tokens SET used_at=:now WHERE id=:id"), {"now": now, "id": row.id})
            return row.user_id, None
    except SQLAlchemyError as exc:
        return None, str(exc)


def mark_email_verified(user_id, verified_at):
    try:
        with db_connection() as connection:
            result = connection.execute(text("UPDATE users SET email_verified_at=:verified_at WHERE id=:user_id"), {"verified_at": verified_at, "user_id": user_id})
            return result.rowcount > 0, None
    except SQLAlchemyError as exc:
        return False, str(exc)


def update_user_password(user_id, password_hash):
    try:
        with db_connection() as connection:
            result = connection.execute(text("UPDATE users SET password_hash=:password_hash WHERE id=:user_id"), {"password_hash": password_hash, "user_id": user_id})
            return result.rowcount > 0, None
    except SQLAlchemyError as exc:
        return False, str(exc)

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


def _migrate_visitor_on_connection(connection, old_visitor_id, account_visitor_id):
    connection.execute(
        text("UPDATE mood_entries SET visitor_id=:new WHERE visitor_id=:old"),
        {"new": account_visitor_id, "old": old_visitor_id},
    )
    old_pref = connection.execute(
        text(
            "SELECT music_language, favorite_genre, kpop_group "
            "FROM user_preferences WHERE visitor_id=:old"
        ),
        {"old": old_visitor_id},
    ).first()
    if old_pref:
        connection.execute(
            text("DELETE FROM user_preferences WHERE visitor_id=:new"),
            {"new": account_visitor_id},
        )
        connection.execute(
            text("UPDATE user_preferences SET visitor_id=:new WHERE visitor_id=:old"),
            {"new": account_visitor_id, "old": old_visitor_id},
        )


def create_user_and_migrate(email, display_name, password_hash, old_visitor_id=None):
    """Create an account and migrate anonymous data in one transaction/checkout."""
    try:
        with db_connection() as connection:
            user_id = _insert_and_get_id(
                connection,
                """
                INSERT INTO users (email, display_name, password_hash)
                VALUES (:email, :display_name, :password_hash)
                """,
                {
                    "email": email.lower().strip(),
                    "display_name": display_name.strip(),
                    "password_hash": password_hash,
                },
            )
            if old_visitor_id:
                _migrate_visitor_on_connection(
                    connection,
                    old_visitor_id=old_visitor_id,
                    account_visitor_id=f"user:{user_id}",
                )
            return user_id, None
    except IntegrityError:
        return None, "duplicate_email"
    except SQLAlchemyError as exc:
        return None, str(exc)


def fetch_user_by_email(email):
    try:
        with db_connection() as connection:
            row = connection.execute(text("""
                SELECT id, email, display_name, password_hash FROM users WHERE email = :email
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
            _migrate_visitor_on_connection(
                connection,
                old_visitor_id=old_visitor_id,
                account_visitor_id=account_visitor_id,
            )
            return True, None
    except SQLAlchemyError as exc:
        return False, str(exc)
