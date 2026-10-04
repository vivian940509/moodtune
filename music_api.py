import requests

from mood_analysis import normalize_itunes_track


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_TOP_SONGS_URL = "https://itunes.apple.com/{country}/rss/topsongs/limit={limit}/json"


def search_tracks(term, limit=8, country="TW"):
    query = (term or "").strip()
    if not query:
        return []

    response = requests.get(
        ITUNES_SEARCH_URL,
        params={
            "term": query,
            "country": country,
            "media": "music",
            "entity": "song",
            "limit": limit,
        },
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    return [normalize_itunes_track(item) for item in payload.get("results", [])]


def normalize_top_song(entry):
    image_urls = entry.get("im:image") or []
    artwork_url = image_urls[-1].get("label", "") if image_urls else ""
    track_name = (entry.get("im:name") or {}).get("label", "未知歌曲")
    artist_name = (entry.get("im:artist") or {}).get("label", "未知歌手")
    category = entry.get("category") or {}
    genre = (category.get("attributes") or {}).get("label", "Music")
    links = entry.get("link") or []
    apple_music_url = ""
    if isinstance(links, list) and links:
        apple_music_url = (links[0].get("attributes") or {}).get("href", "")
    elif isinstance(links, dict):
        apple_music_url = (links.get("attributes") or {}).get("href", "")

    return normalize_itunes_track(
        {
            "trackId": (entry.get("id", {}).get("attributes") or {}).get("im:id", ""),
            "trackName": track_name,
            "artistName": artist_name,
            "collectionName": (entry.get("im:collection") or {}).get("im:name", {}).get("label", ""),
            "primaryGenreName": genre,
            "artworkUrl100": artwork_url,
            "previewUrl": "",
            "trackViewUrl": apple_music_url,
        }
    )


def fetch_top_songs(limit=10, country="tw"):
    limit = max(1, min(int(limit or 10), 25))
    response = requests.get(
        ITUNES_TOP_SONGS_URL.format(country=country.lower(), limit=limit),
        timeout=8,
    )
    response.raise_for_status()
    payload = response.json()
    entries = payload.get("feed", {}).get("entry", [])
    return [normalize_top_song(entry) for entry in entries]
