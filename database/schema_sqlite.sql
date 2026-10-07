CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE,
  display_name TEXT,
  password_hash TEXT,
  email_verified_at TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  visitor_id TEXT NOT NULL UNIQUE,
  music_language TEXT NOT NULL,
  favorite_genre TEXT NOT NULL,
  kpop_group TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mood_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  visitor_id TEXT,
  mood TEXT NOT NULL,
  listening_context TEXT NOT NULL,
  mood_text TEXT,
  diary_text TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_mood_entries_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS song_inputs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mood_entry_id INTEGER NOT NULL,
  itunes_track_id TEXT,
  track_name TEXT NOT NULL,
  artist_name TEXT NOT NULL,
  album_name TEXT,
  genre TEXT,
  artwork_url TEXT,
  preview_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_song_inputs_entry
    FOREIGN KEY (mood_entry_id) REFERENCES mood_entries(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS analysis_results (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mood_entry_id INTEGER NOT NULL,
  song_input_id INTEGER NOT NULL,
  temperature INTEGER NOT NULL,
  drift_need TEXT NOT NULL,
  music_profile TEXT NOT NULL,
  analysis_text TEXT NOT NULL,
  suggestion_text TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_analysis_results_entry
    FOREIGN KEY (mood_entry_id) REFERENCES mood_entries(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_analysis_results_song
    FOREIGN KEY (song_input_id) REFERENCES song_inputs(id)
    ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS favorite_songs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  visitor_id TEXT,
  itunes_track_id TEXT,
  track_name TEXT NOT NULL,
  artist_name TEXT NOT NULL,
  album_name TEXT,
  genre TEXT,
  artwork_url TEXT,
  preview_url TEXT,
  apple_music_url TEXT,
  youtube_music_url TEXT,
  spotify_url TEXT,
  soundcloud_url TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(visitor_id, track_name, artist_name)
);

CREATE TABLE IF NOT EXISTS journal_entries (id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_id TEXT NOT NULL, title TEXT, body TEXT NOT NULL, mood TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_journal_visitor_created ON journal_entries (visitor_id, created_at DESC);
CREATE TABLE IF NOT EXISTS friendships (id INTEGER PRIMARY KEY AUTOINCREMENT, requester_id INTEGER NOT NULL, addressee_id INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(requester_id, addressee_id), FOREIGN KEY(requester_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY(addressee_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER NOT NULL, recipient_id INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(sender_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY(recipient_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (sender_id, recipient_id, created_at);
CREATE TABLE IF NOT EXISTS song_feedback (id INTEGER PRIMARY KEY AUTOINCREMENT, visitor_id TEXT NOT NULL, itunes_track_id TEXT, track_name TEXT NOT NULL, artist_name TEXT NOT NULL, genre TEXT, feedback_type TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(visitor_id, track_name, artist_name, feedback_type));
CREATE TABLE IF NOT EXISTS account_tokens (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, token_hash TEXT NOT NULL UNIQUE, token_type TEXT NOT NULL, expires_at INTEGER NOT NULL, used_at INTEGER, created_at INTEGER NOT NULL DEFAULT (strftime('%s','now')), FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
