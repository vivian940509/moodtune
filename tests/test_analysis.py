from mood_analysis import analyze_mood, normalize_itunes_track


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
