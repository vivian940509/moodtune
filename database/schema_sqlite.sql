CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE,
  display_name TEXT,
  password_hash TEXT,
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
