-- Run once on an existing MySQL MoodTune database.
ALTER TABLE users ADD COLUMN email VARCHAR(255) NULL;
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255) NULL;
CREATE UNIQUE INDEX uq_users_email ON users (email);
ALTER TABLE favorite_songs ADD COLUMN visitor_id VARCHAR(64) NULL;
ALTER TABLE favorite_songs DROP INDEX uq_favorite_song;
CREATE UNIQUE INDEX uq_favorite_owner_song ON favorite_songs (visitor_id, track_name, artist_name);
