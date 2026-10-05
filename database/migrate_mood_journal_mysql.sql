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

ALTER TABLE mood_entries ADD COLUMN visitor_id VARCHAR(64) NULL;
ALTER TABLE mood_entries ADD COLUMN mood_text TEXT NULL;
ALTER TABLE mood_entries ADD COLUMN diary_text TEXT NULL;
CREATE INDEX idx_mood_entries_visitor_created
ON mood_entries (visitor_id, created_at);
