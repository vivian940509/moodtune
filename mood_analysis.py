from urllib.parse import quote_plus


MOOD_SETTINGS = {
    "開心": {"temperature": 82, "drift_need": "低", "tone": "明亮", "profile": "明亮・流動"},
    "平靜": {"temperature": 64, "drift_need": "中高", "tone": "沉澱", "profile": "沉澱"},
    "累": {"temperature": 52, "drift_need": "高", "tone": "休息", "profile": "放鬆・低速"},
    "煩": {"temperature": 48, "drift_need": "高", "tone": "釋放", "profile": "釋放・轉換"},
    "難過": {"temperature": 42, "drift_need": "高", "tone": "陪伴", "profile": "情緒・陪伴"},
    "想專心": {"temperature": 76, "drift_need": "低", "tone": "專注", "profile": "專注・節奏"},
}

CONTEXT_LABELS = {
    "通勤": "移動",
    "讀書": "專注",
    "上班": "整理",
    "睡前": "夜晚",
    "失戀": "情緒修復",
    "放空": "放空",
}

RECOMMENDATION_TERMS = {
    "開心": ["feel good pop", "happy mandopop", "city pop"],
    "平靜": ["acoustic chill", "soft mandopop", "lofi calm"],
    "累": ["sleepy acoustic", "gentle piano", "slow mandopop"],
    "煩": ["indie rock release", "r&b chill", "lofi reset"],
    "難過": ["sad mandopop", "healing ballad", "piano ballad"],
    "想專心": ["lofi focus", "study beats", "instrumental focus"],
}

CONTEXT_RECOMMENDATION_TERMS = {
    "通勤": "commute pop",
    "讀書": "study beats",
    "上班": "focus playlist",
    "睡前": "sleep acoustic",
    "失戀": "breakup ballad",
    "放空": "ambient chill",
}


def build_platform_links(track_name, artist_name, apple_music_url=""):
    query = quote_plus(f"{track_name} {artist_name}".strip())
    return {
        "youtube_music": f"https://music.youtube.com/search?q={query}",
        "spotify": f"https://open.spotify.com/search/{query}",
        "soundcloud": f"https://soundcloud.com/search?q={query}",
        "apple_music": apple_music_url or "",
    }


def normalize_itunes_track(raw):
    artwork = raw.get("artworkUrl100") or ""
    artwork = artwork.replace("100x100bb", "300x300bb")
    track_name = raw.get("trackName") or "未知歌曲"
    artist_name = raw.get("artistName") or "未知歌手"
    platform_links = build_platform_links(
        track_name=track_name,
        artist_name=artist_name,
        apple_music_url=raw.get("trackViewUrl") or "",
    )
    return {
        "track_id": str(raw.get("trackId") or ""),
        "track_name": track_name,
        "artist_name": artist_name,
        "album_name": raw.get("collectionName") or "",
        "genre": raw.get("primaryGenreName") or "Pop",
        "artwork_url": artwork,
        "preview_url": raw.get("previewUrl") or "",
        "apple_music_url": platform_links["apple_music"],
        "youtube_music_url": platform_links["youtube_music"],
        "spotify_url": platform_links["spotify"],
        "soundcloud_url": platform_links["soundcloud"],
    }


def _genre_label(genre):
    lowered = (genre or "").lower()
    if "mandopop" in lowered or "chinese" in lowered or "華語" in genre:
        return "華語流行"
    if "j-pop" in lowered or "jpop" in lowered:
        return "日系流行"
    if "k-pop" in lowered or "kpop" in lowered:
        return "韓系流行"
    if "rock" in lowered:
        return "搖滾"
    if "hip-hop" in lowered or "rap" in lowered:
        return "嘻哈"
    if "classical" in lowered:
        return "古典"
    if "soundtrack" in lowered:
        return "影視原聲"
    return "流行"


def analyze_mood(song, mood, context):
    setting = MOOD_SETTINGS.get(mood, MOOD_SETTINGS["平靜"])
    context_label = CONTEXT_LABELS.get(context, context or "日常")
    genre_label = _genre_label(song.get("genre", ""))
    music_profile = f"{genre_label}・{setting['profile']}・{context_label}"

    analysis = (
        f"你今天選擇的歌曲「{song.get('track_name', '這首歌')}」和目前「{mood}」"
        f"以及「{context}」的狀態有呼應。這份結果比較像一張心情速寫，"
        f"代表你可能正在用音樂幫自己{setting['tone']}，讓當下的節奏變得比較好整理。"
    )
    suggestion = (
        f"今日建議：保留一首熟悉的歌當作陪伴，再加入一到兩首能幫助你"
        f"{'專注' if mood == '想專心' or context == '讀書' else '轉換情緒'}的歌曲，"
        "讓今天的播放清單有一點呼吸空間。"
    )

    return {
        "temperature": setting["temperature"],
        "drift_need": setting["drift_need"],
        "music_profile": music_profile,
        "analysis": analysis,
        "suggestion": suggestion,
    }


def recommendation_terms(mood, context, song=None):
    terms = list(RECOMMENDATION_TERMS.get(mood, RECOMMENDATION_TERMS["平靜"]))
    context_term = CONTEXT_RECOMMENDATION_TERMS.get(context)
    if context_term:
        terms.insert(0, context_term)

    genre = (song or {}).get("genre")
    if genre:
        terms.append(genre)

    seen = set()
    unique_terms = []
    for term in terms:
        normalized = term.lower()
        if normalized not in seen:
            unique_terms.append(term)
            seen.add(normalized)
    return unique_terms[:4]
