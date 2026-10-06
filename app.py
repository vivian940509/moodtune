import json
import os
import uuid
from time import perf_counter

from dotenv import load_dotenv
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_user_and_migrate,
    fetch_favorite_songs,
    fetch_history,
    fetch_user_by_email,
    fetch_preferences,
    fetch_song_leaderboard,
    fetch_trends,
    save_analysis,
    save_favorite_song,
    save_preferences,
)
from mood_analysis import analyze_mood, build_platform_links, recommendation_terms
from music_api import fetch_top_songs, search_tracks


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-moodtune")

MOODS = ["開心", "平靜", "累", "煩", "難過", "想專心"]
CONTEXTS = ["通勤", "讀書", "上班", "睡前", "失戀", "放空"]
MUSIC_LANGUAGES = ["華語", "西洋", "日文", "韓文／K-pop"]
MUSIC_GENRES = ["流行", "抒情", "搖滾", "R&B", "電子", "獨立音樂"]
KPOP_GROUPS = [
    "BTS",
    "BLACKPINK",
    "SEVENTEEN",
    "TWICE",
    "Stray Kids",
    "aespa",
    "IVE",
    "LE SSERAFIM",
]


def ensure_platform_links(song):
    links = build_platform_links(
        track_name=song.get("track_name", ""),
        artist_name=song.get("artist_name", ""),
        apple_music_url=song.get("apple_music_url", ""),
    )
    song.setdefault("apple_music_url", links["apple_music"])
    song.setdefault("youtube_music_url", links["youtube_music"])
    song.setdefault("spotify_url", links["spotify"])
    song.setdefault("soundcloud_url", links["soundcloud"])
    song.setdefault("genius_lyrics_url", links["genius_lyrics"])
    song.setdefault("google_lyrics_url", links["google_lyrics"])
    return song


def build_history_chart(rows):
    recent_rows = list(reversed(rows[:30]))
    return {
        "labels": [
            str(row.get("created_at", ""))[:10] or row.get("track_name", "紀錄")
            for row in recent_rows
        ],
        "temperatures": [int(row.get("temperature") or 0) for row in recent_rows],
        "moods": [row.get("mood", "") for row in recent_rows],
        "tracks": [row.get("track_name", "") for row in recent_rows],
    }


def build_weekly_report(rows):
    recent_rows = rows[:7]
    if not recent_rows:
        return None

    average_temperature = round(
        sum(int(row.get("temperature") or 0) for row in recent_rows) / len(recent_rows)
    )
    mood_counts = {}
    context_counts = {}
    profile_counts = {}
    for row in recent_rows:
        mood_counts[row["mood"]] = mood_counts.get(row["mood"], 0) + 1
        context_counts[row["listening_context"]] = context_counts.get(row["listening_context"], 0) + 1
        profile_counts[row["music_profile"]] = profile_counts.get(row["music_profile"], 0) + 1

    top_mood = max(mood_counts, key=mood_counts.get)
    top_context = max(context_counts, key=context_counts.get)
    top_profile = max(profile_counts, key=profile_counts.get)

    if average_temperature >= 75:
        tone = "這週的聽歌狀態偏明亮，音樂比較像在幫你補充動能。"
        suggestion = "可以保留幾首節奏穩定的歌，讓好狀態不要太快被消耗。"
    elif average_temperature >= 55:
        tone = "這週的情緒溫度落在中段，音樂比較像在幫你整理節奏。"
        suggestion = "適合安排一段固定聽歌時間，把專注、休息和轉換情緒分開。"
    else:
        tone = "這週的情緒溫度偏低，音樂比較像陪伴與修復。"
        suggestion = "建議先選熟悉、壓力低的歌曲，再慢慢加入一點明亮節奏。"

    return {
        "count": len(recent_rows),
        "average_temperature": average_temperature,
        "top_mood": top_mood,
        "top_context": top_context,
        "top_profile": top_profile,
        "summary": f"最近 {len(recent_rows)} 次紀錄中，你最常出現「{top_mood}」的狀態，常在「{top_context}」時聽歌。",
        "tone": tone,
        "suggestion": suggestion,
    }


def get_recommendations(mood, context, song, preferences=None):
    """Return a coherent, fast recommendation set.

    First ask iTunes once for the selected artist/group, which intentionally allows
    multiple songs by the same artist. Only when that cannot fill the set do we make
    one fallback search using the user's preference or mood/context terms.
    """
    recommendations = []
    seen = {str(song.get("track_id") or "")}
    prefs = preferences or {}
    language = prefs.get("music_language")
    genre = prefs.get("favorite_genre")

    artist = (song.get("artist_name") or "").strip()
    terms = []
    if artist:
        terms.append(artist)
    fallback = prefs.get("kpop_group") or genre
    if fallback and fallback.casefold() != artist.casefold():
        terms.append(fallback)
    for term in recommendation_terms(mood, context, song):
        if term and all(term.casefold() != existing.casefold() for existing in terms):
            terms.append(term)

    # At most two network searches: artist first, then one fallback. This keeps the
    # analyze action responsive while still filling recommendations when possible.
    for term in terms[:2]:
        try:
            tracks = search_tracks(
                term,
                limit=8,
                music_language=language,
                favorite_genre=genre,
            )
        except Exception:
            continue
        for track in tracks:
            track_id = str(track.get("track_id") or "")
            signature = f"{track.get('track_name','')}|{track.get('artist_name','')}".casefold()
            if track_id in seen or signature in seen:
                continue
            recommendations.append(track)
            seen.add(track_id)
            seen.add(signature)
            if len(recommendations) == 4:
                return recommendations
    return recommendations


@app.before_request
def prepare_request():
    g.request_started_at = perf_counter()
    if session.get("user_id"):
        session["visitor_id"] = f"user:{session['user_id']}"
    elif "visitor_id" not in session:
        session["visitor_id"] = uuid.uuid4().hex


@app.after_request
def record_request_timing(response):
    started_at = getattr(g, "request_started_at", None)
    if started_at is None:
        return response
    duration_ms = (perf_counter() - started_at) * 1000
    response.headers["Server-Timing"] = f"app;dur={duration_ms:.1f}"
    if os.getenv("VERCEL") or os.getenv("PERFORMANCE_LOGS") == "1":
        print(
            json.dumps(
                {
                    "event": "request_timing",
                    "route": request.path,
                    "method": request.method,
                    "status": response.status_code,
                    "duration_ms": round(duration_ms, 1),
                    "request_id": request.headers.get("x-vercel-id"),
                }
            ),
            flush=True,
        )
    return response


@app.context_processor
def inject_current_user():
    user = None
    if session.get("user_id"):
        user = {
            "id": session["user_id"],
            "display_name": session.get("display_name") or "MoodTune 使用者",
        }
    return {"current_user": user}


@app.get("/")
def index():
    preferences, preference_error = fetch_preferences(session["visitor_id"])
    if preferences is None and not preference_error and not session.get("preferences_skipped"):
        return redirect(url_for("preferences"))

    search_suggestion = ""
    if preferences:
        search_suggestion = preferences.get("kpop_group") or preferences.get("favorite_genre") or ""

    return render_template(
        "index.html",
        moods=MOODS,
        contexts=CONTEXTS,
        preferences=preferences,
        preference_error=preference_error,
        search_suggestion=search_suggestion,
    )


@app.route("/preferences", methods=["GET", "POST"])
def preferences():
    current, load_error = fetch_preferences(session["visitor_id"])

    if request.method == "POST":
        if request.form.get("action") == "skip":
            session["preferences_skipped"] = True
            return redirect(url_for("index"))

        music_language = request.form.get("music_language", "")
        favorite_genre = request.form.get("favorite_genre", "")
        kpop_group = request.form.get("kpop_group", "")

        if music_language not in MUSIC_LANGUAGES or favorite_genre not in MUSIC_GENRES:
            flash("請選擇常聽語言與喜歡的曲風。")
        elif kpop_group and kpop_group not in KPOP_GROUPS:
            flash("韓團選項不正確，請重新選擇。")
        else:
            if music_language != "韓文／K-pop":
                kpop_group = ""
            ok, save_error = save_preferences(
                visitor_id=session["visitor_id"],
                music_language=music_language,
                favorite_genre=favorite_genre,
                kpop_group=kpop_group,
            )
            if ok:
                session.pop("preferences_skipped", None)
                flash("音樂偏好已儲存。")
                return redirect(url_for("index"))
            flash(f"偏好暫時無法儲存：{save_error}")

        current = {
            "music_language": music_language,
            "favorite_genre": favorite_genre,
            "kpop_group": kpop_group,
        }

    return render_template(
        "preferences.html",
        preferences=current,
        music_languages=MUSIC_LANGUAGES,
        music_genres=MUSIC_GENRES,
        kpop_groups=KPOP_GROUPS,
        error=load_error,
    )


@app.get("/api/search")
def api_search():
    term = request.args.get("q", "")
    limit = request.args.get("limit", 8, type=int)
    limit = max(1, min(limit or 8, 12))
    try:
        preferences_data, _ = fetch_preferences(session["visitor_id"])
        tracks = search_tracks(
            term, limit=limit,
            music_language=(preferences_data or {}).get("music_language"),
            favorite_genre=(preferences_data or {}).get("favorite_genre"),
        )
        return jsonify({"tracks": tracks, "music_language": (preferences_data or {}).get("music_language")})
    except Exception as exc:
        return jsonify({"error": f"搜尋暫時失敗：{exc}"}), 502


@app.post("/analyze")
def analyze():
    mood = request.form.get("mood", "平靜")
    context = request.form.get("context", "放空")
    mood_text = request.form.get("mood_text", "").strip()[:500]
    diary_text = request.form.get("diary_text", "").strip()[:1000]
    raw_song = request.form.get("song_json", "")

    if mood not in MOODS:
        mood = "平靜"
    if context not in CONTEXTS:
        context = "放空"
    if not raw_song:
        return redirect(url_for("index"))

    try:
        song = json.loads(raw_song)
    except (json.JSONDecodeError, TypeError) as exc:
        raise BadRequest("歌曲資料格式不正確，請回首頁重新選擇歌曲。") from exc

    if not isinstance(song, dict) or not song.get("track_name") or not song.get("artist_name"):
        raise BadRequest("歌曲資料不完整，請回首頁重新選擇歌曲。")

    song = ensure_platform_links(song)
    result = analyze_mood(song=song, mood=mood, context=context)
    preferences_data, _ = fetch_preferences(session["visitor_id"])
    recommendations = [
        ensure_platform_links(track)
        for track in get_recommendations(
            mood=mood,
            context=context,
            song=song,
            preferences=preferences_data,
        )
    ]
    saved_id, save_error = save_analysis(
        song=song,
        mood=mood,
        context=context,
        result=result,
        visitor_id=session["visitor_id"],
        mood_text=mood_text,
        diary_text=diary_text,
    )

    return render_template(
        "result.html",
        song=song,
        mood=mood,
        context=context,
        result=result,
        recommendations=recommendations,
        mood_text=mood_text,
        diary_text=diary_text,
        saved_id=saved_id,
        save_error=save_error,
    )


@app.get("/history")
def history():
    rows, error = fetch_history(visitor_id=session["visitor_id"])
    trends, trend_error = fetch_trends(visitor_id=session["visitor_id"])
    chart = build_history_chart(rows)
    weekly_report = build_weekly_report(rows)
    return render_template(
        "history.html",
        rows=rows,
        trends=trends,
        chart=chart,
        weekly_report=weekly_report,
        error=error or trend_error,
    )


@app.get("/leaderboard")
def leaderboard():
    songs, error = fetch_song_leaderboard()
    try:
        trending_songs = [ensure_platform_links(song) for song in fetch_top_songs(limit=10)]
        trending_error = None
    except Exception as exc:
        trending_songs = []
        trending_error = f"熱門榜單暫時無法讀取：{exc}"
    return render_template(
        "leaderboard.html",
        songs=songs,
        trending_songs=trending_songs,
        error=error,
        trending_error=trending_error,
    )


@app.post("/favorites/add")
def add_favorite():
    raw_song = request.form.get("song_json", "")
    next_url = request.form.get("next") or url_for("favorites")
    try:
        song = ensure_platform_links(json.loads(raw_song))
    except (json.JSONDecodeError, TypeError):
        flash("收藏失敗，歌曲資料格式不正確。")
        return redirect(next_url)

    if not song.get("track_name") or not song.get("artist_name"):
        flash("收藏失敗，歌曲資料不完整。")
        return redirect(next_url)

    ok, error = save_favorite_song(song, visitor_id=session["visitor_id"])
    flash("已加入收藏。" if ok and not error else f"收藏失敗：{error}")
    return redirect(next_url)


@app.get("/favorites")
def favorites():
    songs, error = fetch_favorite_songs(visitor_id=session["visitor_id"])
    return render_template("favorites.html", songs=songs, error=error)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()[:80]
        password = request.form.get("password", "")
        if "@" not in email or len(email) > 255:
            flash("請輸入有效的 Email。")
        elif not display_name:
            flash("請輸入顯示名稱。")
        elif len(password) < 8:
            flash("密碼至少需要 8 個字元。")
        else:
            old_visitor_id = session.get("visitor_id")
            user_id, error = create_user_and_migrate(
                email=email,
                display_name=display_name,
                password_hash=generate_password_hash(password),
                old_visitor_id=old_visitor_id,
            )
            if error == "duplicate_email":
                flash("這個 Email 已經註冊，請直接登入。")
            elif user_id:
                account_visitor_id = f"user:{user_id}"
                session.clear()
                session["user_id"] = user_id
                session["display_name"] = display_name
                session["visitor_id"] = account_visitor_id
                flash("註冊完成，已登入 MoodTune。")
                return redirect(url_for("index"))
            else:
                flash(f"註冊失敗：{error}")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user, error = fetch_user_by_email(email)
        if error:
            flash(f"登入暫時失敗：{error}")
        elif not user or not user.get("password_hash") or not check_password_hash(user["password_hash"], password):
            flash("Email 或密碼不正確。")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["display_name"] = user.get("display_name") or "MoodTune 使用者"
            session["visitor_id"] = f"user:{user['id']}"
            flash(f"歡迎回來，{user.get('display_name') or 'MoodTune 使用者'}。")
            return redirect(url_for("index"))
    return render_template("auth.html", mode="login")


@app.post("/logout")
def logout():
    session.clear()
    session["visitor_id"] = uuid.uuid4().hex
    flash("已登出。")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
