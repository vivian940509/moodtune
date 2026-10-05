import re
import time

import requests

from mood_analysis import normalize_itunes_track

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
ITUNES_TOP_SONGS_URL = "https://itunes.apple.com/{country}/rss/topsongs/limit={limit}/json"

LANGUAGE_COUNTRIES = {"華語": "TW", "西洋": "US", "日文": "JP", "韓文／K-pop": "KR"}
GENRE_TRANSLATIONS = {
    "流行": "pop", "抒情": "ballad", "搖滾": "rock", "R&B": "R&B",
    "電子": "electronic", "獨立音樂": "indie",
}
CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")
HAN_RE = re.compile(r"[\u3400-\u9fff]")
JP_RE = re.compile(r"[\u3040-\u30ff]")
KR_RE = re.compile(r"[\uac00-\ud7af]")

_HTTP = requests.Session()
_SEARCH_CACHE = {}
_SEARCH_CACHE_TTL = 300



def _matches_language(track, music_language):
    text = f"{track.get('track_name', '')} {track.get('artist_name', '')}"
    if music_language == "西洋":
        return not CJK_RE.search(text)
    if music_language == "日文":
        return bool(JP_RE.search(text))
    if music_language == "韓文／K-pop":
        return bool(KR_RE.search(text))
    if music_language == "華語":
        return bool(HAN_RE.search(text))
    return True


def search_tracks(term, limit=8, country=None, music_language=None, favorite_genre=None):
    query = (term or "").strip()
    if not query:
        return []

    country = country or LANGUAGE_COUNTRIES.get(music_language, "TW")
    if music_language != "華語" and query in GENRE_TRANSLATIONS:
        query = GENRE_TRANSLATIONS[query]
    elif favorite_genre and query == favorite_genre and music_language != "華語":
        query = GENRE_TRANSLATIONS.get(favorite_genre, query)

    # Cache identical iTunes searches briefly. Recommendation/search clicks often reuse
    # the same artist or genre, so this removes repeated network waits on Vercel.
    cache_key = (query.casefold(), country, music_language or "", favorite_genre or "", int(limit))
    now = time.monotonic()
    cached = _SEARCH_CACHE.get(cache_key)
    if cached and now - cached[0] < _SEARCH_CACHE_TTL:
        return [dict(track) for track in cached[1]]

    request_limit = min(max(limit * 3, limit), 30) if music_language else limit
    response = _HTTP.get(
        ITUNES_SEARCH_URL,
        params={"term": query, "country": country, "media": "music", "entity": "song", "limit": request_limit},
        timeout=(2.5, 5),
    )
    response.raise_for_status()
    tracks = [normalize_itunes_track(item) for item in response.json().get("results", [])]
    if music_language:
        filtered = [track for track in tracks if _matches_language(track, music_language)]
        if music_language == "西洋":
            tracks = filtered
        elif filtered:
            tracks = filtered
    result = tracks[:limit]
    _SEARCH_CACHE[cache_key] = (now, [dict(track) for track in result])
    # Keep memory bounded in long-running local processes.
    if len(_SEARCH_CACHE) > 128:
        oldest = min(_SEARCH_CACHE, key=lambda key: _SEARCH_CACHE[key][0])
        _SEARCH_CACHE.pop(oldest, None)
    return result


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
    return normalize_itunes_track({
        "trackId": (entry.get("id", {}).get("attributes") or {}).get("im:id", ""),
        "trackName": track_name, "artistName": artist_name,
        "collectionName": (entry.get("im:collection") or {}).get("im:name", {}).get("label", ""),
        "primaryGenreName": genre, "artworkUrl100": artwork_url, "previewUrl": "", "trackViewUrl": apple_music_url,
    })


def fetch_top_songs(limit=10, country="tw"):
    limit = max(1, min(int(limit or 10), 25))
    response = requests.get(ITUNES_TOP_SONGS_URL.format(country=country.lower(), limit=limit), timeout=8)
    response.raise_for_status()
    entries = response.json().get("feed", {}).get("entry", [])
    return [normalize_top_song(entry) for entry in entries]
