from mood_analysis import analyze_mood, normalize_itunes_track
from database import fetch_history, get_database_url, save_analysis
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
