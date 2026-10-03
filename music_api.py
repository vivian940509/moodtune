import requests

from mood_analysis import normalize_itunes_track


ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


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
