CREATE TABLE IF NOT EXISTS users (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(255) NULL,
  display_name VARCHAR(80) NULL,
  password_hash VARCHAR(255) NULL,
  email_verified_at DATETIME NULL,
  UNIQUE KEY uq_users_email (email),
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS user_preferences (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  visitor_id VARCHAR(64) NOT NULL,
  music_language VARCHAR(30) NOT NULL,
  favorite_genre VARCHAR(50) NOT NULL,
  kpop_group VARCHAR(100) NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_preferences_visitor (visitor_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mood_entries (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NULL,
  visitor_id VARCHAR(64) NULL,
  mood VARCHAR(20) NOT NULL,
  listening_context VARCHAR(20) NOT NULL,
  mood_text TEXT NULL,
  diary_text TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_mood_entries_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE SET NULL,
  KEY idx_mood_entries_visitor_created (visitor_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS song_inputs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  mood_entry_id BIGINT UNSIGNED NOT NULL,
  itunes_track_id VARCHAR(64) NULL,
  track_name VARCHAR(255) NOT NULL,
  artist_name VARCHAR(255) NOT NULL,
  album_name VARCHAR(255) NULL,
  genre VARCHAR(120) NULL,
  artwork_url TEXT NULL,
  preview_url TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_song_inputs_entry
    FOREIGN KEY (mood_entry_id) REFERENCES mood_entries(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS analysis_results (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  mood_entry_id BIGINT UNSIGNED NOT NULL,
  song_input_id BIGINT UNSIGNED NOT NULL,
  temperature INT NOT NULL,
  drift_need VARCHAR(20) NOT NULL,
  music_profile VARCHAR(255) NOT NULL,
  analysis_text TEXT NOT NULL,
  suggestion_text TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_analysis_results_entry
    FOREIGN KEY (mood_entry_id) REFERENCES mood_entries(id)
    ON DELETE CASCADE,
  CONSTRAINT fk_analysis_results_song
    FOREIGN KEY (song_input_id) REFERENCES song_inputs(id)
    ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS favorite_songs (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  visitor_id VARCHAR(64) NULL,
  itunes_track_id VARCHAR(64) NULL,
  track_name VARCHAR(255) NOT NULL,
  artist_name VARCHAR(255) NOT NULL,
  album_name VARCHAR(255) NULL,
  genre VARCHAR(120) NULL,
  artwork_url TEXT NULL,
  preview_url TEXT NULL,
  apple_music_url TEXT NULL,
  youtube_music_url TEXT NULL,
  spotify_url TEXT NULL,
  soundcloud_url TEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uq_favorite_song (visitor_id, track_name, artist_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS journal_entries (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, visitor_id VARCHAR(64) NOT NULL, title VARCHAR(120), body TEXT NOT NULL, mood VARCHAR(20), created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, KEY idx_journal_visitor_created (visitor_id, created_at)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS friendships (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, requester_id BIGINT UNSIGNED NOT NULL, addressee_id BIGINT UNSIGNED NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'pending', created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uq_friendship_pair (requester_id, addressee_id), FOREIGN KEY (requester_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY (addressee_id) REFERENCES users(id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS messages (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, sender_id BIGINT UNSIGNED NOT NULL, recipient_id BIGINT UNSIGNED NOT NULL, body TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, KEY idx_messages_conversation (sender_id, recipient_id, created_at), KEY idx_messages_recipient_sender (recipient_id, sender_id, created_at), FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE, FOREIGN KEY (recipient_id) REFERENCES users(id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS song_feedback (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, visitor_id VARCHAR(64) NOT NULL, itunes_track_id VARCHAR(64), track_name VARCHAR(255) NOT NULL, artist_name VARCHAR(255) NOT NULL, genre VARCHAR(120), feedback_type VARCHAR(30) NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE KEY uq_song_feedback (visitor_id, track_name, artist_name, feedback_type)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
CREATE TABLE IF NOT EXISTS account_tokens (id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY, user_id BIGINT UNSIGNED NOT NULL, token_hash VARCHAR(128) NOT NULL UNIQUE, token_type VARCHAR(40) NOT NULL, expires_at BIGINT NOT NULL, used_at BIGINT NULL, created_at BIGINT NOT NULL, FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
