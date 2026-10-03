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


def normalize_itunes_track(raw):
    artwork = raw.get("artworkUrl100") or ""
    artwork = artwork.replace("100x100bb", "300x300bb")
    return {
        "track_id": str(raw.get("trackId") or ""),
        "track_name": raw.get("trackName") or "未知歌曲",
        "artist_name": raw.get("artistName") or "未知歌手",
        "album_name": raw.get("collectionName") or "",
        "genre": raw.get("primaryGenreName") or "Pop",
        "artwork_url": artwork,
        "preview_url": raw.get("previewUrl") or "",
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
