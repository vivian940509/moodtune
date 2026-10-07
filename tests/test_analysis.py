import json

from mood_analysis import analyze_mood, normalize_itunes_track
from database import (
    create_user_and_migrate,
    fetch_favorite_songs,
    delete_favorite_song,
    fetch_friend_data,
    fetch_journal_entries,
    fetch_messages,
    fetch_song_feedback,
    respond_friend_request,
    save_journal_entry,
    search_users,
    send_friend_request,
    send_message,
    save_song_feedback,
    fetch_history,
    fetch_preferences,
    fetch_song_leaderboard,
    fetch_user_by_email,
    get_engine,
    get_database_url,
    save_analysis,
    save_favorite_song,
    save_preferences,
)
from app import app


def test_analyze_mood_returns_scores_and_guidance_for_calm_sleep_context():
    song = {
        "track_name": "如果可以",
        "artist_name": "韋禮安",
        "genre": "Mandopop",
    }

    result = analyze_mood(song=song, mood="平靜", context="睡前")

    assert result["temperature"] == 64
    assert result["drift_need"] == "中高"
    assert "平靜" in result["analysis"]
    assert "睡前" in result["analysis"]
    assert result["music_profile"] == "華語流行・沉澱・夜晚"


def test_analyze_mood_handles_focus_context_with_higher_temperature():
    song = {
        "track_name": "Counting Stars",
        "artist_name": "OneRepublic",
        "genre": "Pop",
    }

    result = analyze_mood(song=song, mood="想專心", context="讀書")

    assert result["temperature"] == 76
    assert result["drift_need"] == "低"
    assert "專注" in result["suggestion"]


def test_normalize_itunes_track_maps_expected_fields():
    raw = {
        "trackId": 123,
        "trackName": "晴天",
        "artistName": "周杰倫",
        "collectionName": "葉惠美",
        "primaryGenreName": "Mandopop",
        "artworkUrl100": "https://example.test/100x100bb.jpg",
        "previewUrl": "https://example.test/preview.m4a",
        "trackViewUrl": "https://music.apple.com/tw/album/test/123",
    }

    track = normalize_itunes_track(raw)

    assert track == {
        "track_id": "123",
        "track_name": "晴天",
        "artist_name": "周杰倫",
        "album_name": "葉惠美",
        "genre": "Mandopop",
        "artwork_url": "https://example.test/300x300bb.jpg",
        "preview_url": "https://example.test/preview.m4a",
        "apple_music_url": "https://music.apple.com/tw/album/test/123",
        "youtube_music_url": "https://music.youtube.com/search?q=%E6%99%B4%E5%A4%A9+%E5%91%A8%E6%9D%B0%E5%80%AB",
        "spotify_url": "https://open.spotify.com/search/%E6%99%B4%E5%A4%A9+%E5%91%A8%E6%9D%B0%E5%80%AB",
        "soundcloud_url": "https://soundcloud.com/search?q=%E6%99%B4%E5%A4%A9+%E5%91%A8%E6%9D%B0%E5%80%AB",
        "genius_lyrics_url": "https://genius.com/search?q=%E6%99%B4%E5%A4%A9+%E5%91%A8%E6%9D%B0%E5%80%AB",
        "google_lyrics_url": "https://www.google.com/search?q=%E6%99%B4%E5%A4%A9+%E5%91%A8%E6%9D%B0%E5%80%AB+lyrics",
    }


def test_database_url_normalizes_mysql_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://user:pass@host:3306/db")

    assert get_database_url() == "mysql+pymysql://user:pass@host:3306/db"


def test_database_url_normalizes_supabase_postgres_driver(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgres://postgres.project-ref:pass@aws.pooler.supabase.com:6543/postgres",
    )

    assert (
        get_database_url()
        == "postgresql+psycopg2://postgres.project-ref:pass@aws.pooler.supabase.com:6543/postgres"
    )


def test_database_engine_is_reused_for_same_database_url(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-engine-cache.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    assert get_engine() is get_engine()


def test_create_user_and_migrate_uses_normalized_email_and_moves_preferences(
    monkeypatch, tmp_path
):
    database_path = tmp_path / "moodtune-account-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    old_visitor_id = "anonymous-before-register"
    ok, error = save_preferences(
        visitor_id=old_visitor_id,
        music_language="華語",
        favorite_genre="流行",
    )
    assert ok is True
    assert error is None

    user_id, create_error = create_user_and_migrate(
        email="  USER@EXAMPLE.COM ",
        display_name="測試使用者",
        password_hash="test-hash",
        old_visitor_id=old_visitor_id,
    )
    user, fetch_error = fetch_user_by_email("user@example.com")
    preferences, preference_error = fetch_preferences(f"user:{user_id}")

    assert create_error is None
    assert fetch_error is None
    assert preference_error is None
    assert user["email"] == "user@example.com"
    assert preferences["favorite_genre"] == "流行"


def test_create_user_and_migrate_reports_duplicate_email(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-duplicate-account.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    first_user_id, first_error = create_user_and_migrate(
        "user@example.com", "第一位", "hash-1"
    )
    duplicate_user_id, duplicate_error = create_user_and_migrate(
        "USER@example.com", "第二位", "hash-2"
    )

    assert first_user_id is not None
    assert first_error is None
    assert duplicate_user_id is None
    assert duplicate_error == "duplicate_email"


def test_sqlite_database_auto_initializes_and_persists_history(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {
        "track_id": "123",
        "track_name": "晴天",
        "artist_name": "周杰倫",
        "album_name": "葉惠美",
        "genre": "Mandopop",
        "artwork_url": "https://example.test/art.jpg",
        "preview_url": "https://example.test/preview.m4a",
    }
    result = analyze_mood(song=song, mood="平靜", context="睡前")

    saved_id, save_error = save_analysis(
        song=song,
        mood="平靜",
        context="睡前",
        result=result,
    )
    rows, fetch_error = fetch_history()

    assert save_error is None
    assert saved_id is not None
    assert fetch_error is None
    assert rows[0]["track_name"] == "晴天"
    assert rows[0]["mood"] == "平靜"


def test_analyze_route_rejects_invalid_song_json():
    client = app.test_client()

    response = client.post(
        "/analyze",
        data={"song_json": "{not json", "mood": "開心", "context": "通勤"},
    )

    assert response.status_code == 400


def test_analyze_route_redirects_when_song_missing():
    client = app.test_client()

    response = client.post("/analyze", data={"mood": "開心", "context": "通勤"})

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_analyze_get_redirects_instead_of_returning_method_not_allowed():
    response = app.test_client().get("/analyze")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")


def test_first_visit_redirects_to_music_preferences(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-first-visit.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    response = app.test_client().get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/preferences")


def test_kpop_preferences_are_saved_from_onboarding(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-onboarding.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["visitor_id"] = "feedback-api-visitor"

    response = client.post(
        "/preferences",
        data={
            "action": "save",
            "music_language": "韓文／K-pop",
            "favorite_genre": "流行",
            "kpop_group": "aespa",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "aespa".encode() in response.data
    assert "先說說心情".encode() in response.data


def test_visitors_can_skip_preferences(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-skip-preferences.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()

    response = client.post(
        "/preferences",
        data={"action": "skip"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'moodText' in response.data


def test_analyze_route_shows_external_platform_links(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-platforms.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()
    song = {
        "track_id": "789",
        "track_name": "夜曲",
        "artist_name": "周杰倫",
        "album_name": "十一月的蕭邦",
        "genre": "Mandopop",
        "artwork_url": "https://example.test/art.jpg",
        "preview_url": "",
    }

    response = client.post(
        "/analyze",
        data={"song_json": json.dumps(song), "mood": "平靜", "context": "睡前"},
    )

    assert response.status_code == 200
    assert "YouTube Music".encode() in response.data
    assert "Spotify".encode() in response.data
    assert b"music.youtube.com/search" in response.data
    assert b"shareShareCard" in response.data


def test_song_feedback_api_records_tag_mismatch(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-feedback-api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["visitor_id"] = "feedback-api-visitor"
    response = client.post(
        "/api/feedback",
        json={
            "song": {"track_id": "api-1", "track_name": "標籤錯誤", "artist_name": "MoodTune", "genre": "抒情"},
            "feedback_type": "tag_mismatch",
        },
    )
    rows, error = fetch_song_feedback("feedback-api-visitor")

    assert response.status_code == 200
    assert response.get_json()["track_id"] == "api-1"
    assert error is None
    assert rows[0]["feedback_type"] == "tag_mismatch"


def test_search_excludes_song_marked_as_tag_mismatch(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-search-feedback.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["visitor_id"] = "search-feedback-visitor"
    save_song_feedback(
        "search-feedback-visitor",
        {"track_id": "blocked-1", "track_name": "不想再看到", "artist_name": "MoodTune", "genre": "抒情"},
        "tag_mismatch",
    )
    monkeypatch.setattr(
        "app.search_tracks",
        lambda *args, **kwargs: [
            {"track_id": "blocked-1", "track_name": "不想再看到", "artist_name": "MoodTune", "genre": "抒情"},
            {"track_id": "allowed-1", "track_name": "保留歌曲", "artist_name": "Other", "genre": "流行"},
            {"track_id": "allowed-2", "track_name": "同曲風也可以", "artist_name": "Other", "genre": "抒情"},
        ],
    )

    response = client.get("/api/search?q=test")

    assert response.status_code == 200
    assert [track["track_id"] for track in response.get_json()["tracks"]] == ["allowed-1", "allowed-2"]


def test_search_fills_six_results_after_feedback_filter(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-search-fill.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["visitor_id"] = "search-fill-visitor"
    save_song_feedback(
        "search-fill-visitor",
        {"track_id": "blocked-1", "track_name": "已隱藏", "artist_name": "MoodTune", "genre": "抒情"},
        "tag_mismatch",
    )
    captured = {}

    def fake_search(*args, **kwargs):
        captured["limit"] = kwargs["limit"]
        return [
            {"track_id": "blocked-1", "track_name": "已隱藏", "artist_name": "MoodTune", "genre": "抒情"},
            *[
                {"track_id": f"allowed-{index}", "track_name": f"歌曲 {index}", "artist_name": "Other", "genre": "抒情"}
                for index in range(1, 7)
            ],
        ]

    monkeypatch.setattr("app.search_tracks", fake_search)

    response = client.get("/api/search?q=抒情")
    payload = response.get_json()

    assert response.status_code == 200
    assert captured["limit"] >= 6
    assert len(payload["tracks"]) == 6
    assert all(track["track_id"] != "blocked-1" for track in payload["tracks"])


def test_feedback_reset_restores_hidden_songs(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-feedback-reset.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["visitor_id"] = "reset-feedback-visitor"
    save_song_feedback(
        "reset-feedback-visitor",
        {"track_id": "hidden-1", "track_name": "恢復歌曲", "artist_name": "MoodTune", "genre": "抒情"},
        "tag_mismatch",
    )

    response = client.post("/api/feedback/reset")
    rows, error = fetch_song_feedback("reset-feedback-visitor")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert error is None and rows == []


def test_history_page_shows_chart_and_weekly_report(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-history.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {
        "track_id": "456",
        "track_name": "Test Song",
        "artist_name": "Test Artist",
        "album_name": "Test Album",
        "genre": "Pop",
        "artwork_url": "https://example.test/art.jpg",
        "preview_url": "",
    }
    result = analyze_mood(song=song, mood="開心", context="通勤")
    visitor_id = "history-test-visitor"
    save_analysis(
        song=song,
        mood="開心",
        context="通勤",
        result=result,
        visitor_id=visitor_id,
        mood_text="今天完成了重要工作，很開心。",
        diary_text="這首歌讓我想把好心情記下來。",
    )

    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["visitor_id"] = visitor_id

    response = client.get("/history")

    assert response.status_code == 200
    assert "moodTrendChart".encode() in response.data
    assert "AI Weekly Report".encode() in response.data
    assert "今天完成了重要工作".encode() in response.data
    assert "這首歌讓我想把好心情記下來".encode() not in response.data


def test_preferences_can_be_saved_and_loaded(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-preferences.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    ok, error = save_preferences(
        visitor_id="preference-test-visitor",
        music_language="韓文／K-pop",
        favorite_genre="流行",
        kpop_group="TWICE",
    )
    preferences, fetch_error = fetch_preferences("preference-test-visitor")

    assert ok is True
    assert error is None
    assert fetch_error is None
    assert preferences["music_language"] == "韓文／K-pop"
    assert preferences["kpop_group"] == "TWICE"


def test_history_is_filtered_by_anonymous_visitor(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-private-history.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {
        "track_id": "private-1",
        "track_name": "Private Song",
        "artist_name": "MoodTune",
        "album_name": "Journal",
        "genre": "Pop",
        "artwork_url": "https://example.test/private.jpg",
        "preview_url": "",
    }
    result = analyze_mood(song=song, mood="平靜", context="睡前")
    save_analysis(song, "平靜", "睡前", result, visitor_id="visitor-a")

    own_rows, own_error = fetch_history(visitor_id="visitor-a")
    other_rows, other_error = fetch_history(visitor_id="visitor-b")

    assert own_error is None
    assert other_error is None
    assert len(own_rows) == 1
    assert other_rows == []


def test_song_leaderboard_counts_repeated_tracks(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-leaderboard.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {
        "track_id": "999",
        "track_name": "排行榜之歌",
        "artist_name": "MoodTune",
        "album_name": "MoodTune",
        "genre": "Pop",
        "artwork_url": "https://example.test/art.jpg",
        "preview_url": "",
    }
    result = analyze_mood(song=song, mood="開心", context="通勤")

    save_analysis(song=song, mood="開心", context="通勤", result=result)
    save_analysis(song=song, mood="開心", context="通勤", result=result)
    songs, error = fetch_song_leaderboard()

    assert error is None
    assert songs[0]["track_name"] == "排行榜之歌"
    assert songs[0]["play_count"] == 2


def test_leaderboard_page_renders(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-leaderboard-page.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    response = app.test_client().get("/leaderboard")

    assert response.status_code == 200
    assert "歌曲排行榜".encode() in response.data


def test_favorite_songs_can_be_saved_and_listed(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-favorites.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {
        "track_id": "fav-1",
        "track_name": "收藏之歌",
        "artist_name": "MoodTune",
        "album_name": "Favorites",
        "genre": "Pop",
        "artwork_url": "https://example.test/fav.jpg",
        "preview_url": "",
        "apple_music_url": "",
        "youtube_music_url": "https://music.youtube.com/search?q=fav",
        "spotify_url": "https://open.spotify.com/search/fav",
        "soundcloud_url": "https://soundcloud.com/search?q=fav",
    }

    ok, error = save_favorite_song(song)
    songs, fetch_error = fetch_favorite_songs()

    assert ok is True
    assert error is None
    assert fetch_error is None
    assert songs[0]["track_name"] == "收藏之歌"


def test_favorite_can_only_be_deleted_by_its_owner(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-favorite-delete.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {
        "track_id": "fav-delete-1",
        "track_name": "可刪除的歌",
        "artist_name": "MoodTune",
    }

    ok, error = save_favorite_song(song, visitor_id="owner")
    songs, fetch_error = fetch_favorite_songs(visitor_id="owner")
    wrong_owner_ok, wrong_owner_error = delete_favorite_song(
        songs[0]["id"], visitor_id="someone-else"
    )
    deleted, delete_error = delete_favorite_song(
        songs[0]["id"], visitor_id="owner"
    )
    remaining, remaining_error = fetch_favorite_songs(visitor_id="owner")

    assert ok is True
    assert error is None
    assert fetch_error is None
    assert wrong_owner_ok is False
    assert wrong_owner_error is None
    assert deleted is True
    assert delete_error is None
    assert remaining_error is None
    assert remaining == []


def test_favorites_page_renders(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-favorites-page.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    response = app.test_client().get("/favorites")

    assert response.status_code == 200
    assert "我的收藏".encode() in response.data


def test_standalone_journal_is_saved_per_visitor(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-journal.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")

    entry_id, error = save_journal_entry("visitor-a", "今天", "我想慢慢休息。", "累")
    own, own_error = fetch_journal_entries("visitor-a")
    other, other_error = fetch_journal_entries("visitor-b")

    assert entry_id is not None
    assert error is None
    assert own_error is None and other_error is None
    assert own[0]["body"] == "我想慢慢休息。"
    assert other == []


def test_users_can_add_friends_and_chat(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-social.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    first, first_error = create_user_and_migrate("one@example.com", "第一位", "hash-1")
    second, second_error = create_user_and_migrate("two@example.com", "第二位", "hash-2")

    sent, request_error = send_friend_request(first, second)
    (_, pending), pending_error = fetch_friend_data(second)
    accepted, accept_error = respond_friend_request(pending[0]["id"], second, "accepted")
    message_id, message_error = send_message(first, second, "今天一起聽歌嗎？")
    messages, messages_error = fetch_messages(second, first)

    assert first and second and first_error is None and second_error is None
    assert sent is True and request_error is None
    assert pending_error is None and len(pending) == 1
    assert accepted is True and accept_error is None
    assert message_id is not None and message_error is None
    assert messages_error is None and messages[0]["body"] == "今天一起聽歌嗎？"


def test_song_feedback_is_saved_for_recommendation_filtering(monkeypatch, tmp_path):
    database_path = tmp_path / "moodtune-feedback.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path.as_posix()}")
    song = {"track_id": "feedback-1", "track_name": "不合口味", "artist_name": "某歌手", "genre": "電子"}

    ok, error = save_song_feedback("visitor-a", song, "dislike")
    rows, fetch_error = fetch_song_feedback("visitor-a")

    assert ok is True
    assert error is None and fetch_error is None
    assert rows[0]["feedback_type"] == "dislike"
