import json
import os
import uuid
import csv
import io
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from time import perf_counter, time

from dotenv import load_dotenv
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.exceptions import BadRequest
from werkzeug.security import check_password_hash, generate_password_hash

from database import (
    create_user_and_migrate,
    fetch_favorite_songs,
    fetch_song_feedback,
    clear_song_feedback,
    delete_favorite_song,
    fetch_history,
    fetch_user_by_email,
    fetch_preferences,
    fetch_song_leaderboard,
    fetch_trends,
    save_analysis,
    save_favorite_song,
    save_song_feedback,
    save_preferences,
    save_journal_entry,
    fetch_journal_entries,
    search_users,
    send_friend_request,
    fetch_friend_data,
    respond_friend_request,
    send_message,
    fetch_messages,
    create_account_token,
    consume_account_token,
    mark_email_verified,
    update_user_password,
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


def make_account_token():
    raw = secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode("utf-8")).hexdigest()


def send_account_email(recipient, subject, body):
    smtp_host = os.getenv("SMTP_HOST")
    if not smtp_host:
        print(json.dumps({"event": "account_email_dev", "recipient": recipient, "subject": subject, "body": body}, ensure_ascii=False), flush=True)
        return True
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "no-reply@moodtune.local"))
    message["To"] = recipient
    message.set_content(body)
    with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as server:
        server.starttls()
        if os.getenv("SMTP_USER"):
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)
    return True


def filter_tracks_by_feedback(tracks, feedback):
    feedback = feedback or []
    blocked_ids = {str(row.get("itunes_track_id") or "") for row in feedback if row.get("itunes_track_id")}
    blocked_signatures = {
        f"{(row.get('track_name') or '').casefold()}|{(row.get('artist_name') or '').casefold()}"
        for row in feedback
    }
    blocked_artists = {
        (row.get("artist_name") or "").casefold()
        for row in feedback
        if row.get("feedback_type") == "dislike" and row.get("artist_name")
    }
    blocked_genres = {
        (row.get("genre") or "").casefold()
        for row in feedback
        if row.get("feedback_type") == "dislike" and row.get("genre")
    }
    filtered = []
    for track in tracks:
        track_id = str(track.get("track_id") or "")
        signature = f"{(track.get('track_name') or '').casefold()}|{(track.get('artist_name') or '').casefold()}"
        artist = (track.get("artist_name") or "").casefold()
        genre = (track.get("genre") or "").casefold()
        if track_id in blocked_ids or signature in blocked_signatures or artist in blocked_artists or genre in blocked_genres:
            continue
        filtered.append(track)
    return filtered


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


def get_recommendations(mood, context, song, preferences=None, feedback=None):
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
    feedback = feedback or []

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
            if track_id in seen or signature in seen or not filter_tracks_by_feedback([track], feedback):
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
    limit = request.args.get("limit", 6, type=int)
    limit = max(1, min(limit or 6, 12))
    try:
        preferences_data, _ = fetch_preferences(session["visitor_id"])
        # Fetch extra candidates before applying persistent feedback, otherwise
        # previously hidden songs can leave the page with only one or two cards.
        tracks = search_tracks(
            term, limit=max(limit, 24),
            music_language=(preferences_data or {}).get("music_language"),
            favorite_genre=(preferences_data or {}).get("favorite_genre"),
        )
        feedback, _ = fetch_song_feedback(session["visitor_id"])
        before_feedback_count = len(tracks)
        tracks = filter_tracks_by_feedback(tracks, feedback)
        return jsonify({"tracks": tracks[:limit], "filtered_by_feedback": before_feedback_count - len(tracks), "music_language": (preferences_data or {}).get("music_language")})
    except Exception as exc:
        return jsonify({"error": f"搜尋暫時失敗：{exc}"}), 502


@app.get("/analyze")
def analyze_get():
    """Avoid a confusing 405 when a result URL is refreshed or opened directly."""
    flash("請從分析頁重新選擇歌曲並送出分析。")
    return redirect(url_for("index"))


@app.post("/analyze")
def analyze():
    mood = request.form.get("mood", "平靜")
    context = request.form.get("context", "放空")
    mood_text = request.form.get("mood_text", "").strip()[:500]
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
    feedback, _ = fetch_song_feedback(session["visitor_id"])
    recommendations = [
        ensure_platform_links(track)
        for track in get_recommendations(
            mood=mood,
            context=context,
            song=song,
            preferences=preferences_data,
            feedback=feedback,
        )
    ]
    saved_id, save_error = save_analysis(
        song=song,
        mood=mood,
        context=context,
        result=result,
        visitor_id=session["visitor_id"],
        mood_text=mood_text,
    )

    return render_template(
        "result.html",
        song=song,
        mood=mood,
        context=context,
        result=result,
        recommendations=recommendations,
        mood_text=mood_text,
        saved_id=saved_id,
        save_error=save_error,
        feedback=feedback,
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


@app.route("/journal", methods=["GET", "POST"])
def journal():
    if request.method == "POST":
        body = request.form.get("body", "").strip()[:3000]
        title = request.form.get("title", "").strip()[:120]
        mood = request.form.get("mood", "").strip()[:20]
        if not body:
            flash("請先寫下一點今天的心情。")
        else:
            entry_id, error = save_journal_entry(session["visitor_id"], title, body, mood)
            flash("心情日記已保存。" if entry_id else f"日記暫時無法保存：{error}")
            if entry_id:
                return redirect(url_for("journal"))
    entries, error = fetch_journal_entries(session["visitor_id"])
    return render_template("journal.html", entries=entries, error=error, moods=MOODS)


def require_login():
    if not session.get("user_id"):
        flash("請先登入才能使用好友與聊天功能。")
        return redirect(url_for("login", next=request.path))
    return None


@app.route("/friends", methods=["GET", "POST"])
def friends():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    if request.method == "POST":
        target_id = request.form.get("user_id", type=int)
        ok, error = send_friend_request(session["user_id"], target_id)
        flash("好友申請已送出。" if ok else error)
        return redirect(url_for("friends"))
    query = request.args.get("q", "").strip()
    results, search_error = search_users(query, session["user_id"]) if query else ([], None)
    (friend_list, pending), error = fetch_friend_data(session["user_id"])
    return render_template("friends.html", friends=friend_list, pending=pending, results=results, query=query, error=error or search_error)


@app.post("/friends/<int:friendship_id>/<action>")
def friend_request_action(friendship_id, action):
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    status = "accepted" if action == "accept" else "declined"
    ok, error = respond_friend_request(friendship_id, session["user_id"], status)
    flash("好友申請已接受。" if ok and status == "accepted" else ("好友申請已略過。" if ok else error))
    return redirect(url_for("friends"))


@app.route("/chat/<int:friend_id>", methods=["GET", "POST"])
def chat(friend_id):
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    if request.method == "POST":
        body = request.form.get("body", "").strip()[:1000]
        if body:
            _, error = send_message(session["user_id"], friend_id, body)
            if error:
                flash(error)
        return redirect(url_for("chat", friend_id=friend_id))
    (friend_list, _), error = fetch_friend_data(session["user_id"])
    friend = next((item for item in friend_list if item["id"] == friend_id), None)
    if not friend:
        flash("找不到這位好友，或你們尚未成為好友。")
        return redirect(url_for("friends"))
    messages, message_error = fetch_messages(session["user_id"], friend_id)
    return render_template("chat.html", friend=friend, messages=messages, error=error or message_error)


@app.post("/api/chat/<int:friend_id>")
def api_chat(friend_id):
    redirect_response = require_login()
    if redirect_response:
        return jsonify({"error": "請先登入。"}), 401
    payload = request.get_json(silent=True) or {}
    body = str(payload.get("body", "")).strip()[:1000]
    if not body:
        return jsonify({"error": "訊息不能是空白。"}), 400
    message_id, error = send_message(session["user_id"], friend_id, body)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({"ok": True, "id": message_id, "body": body, "sender_name": session.get("display_name", "我")})


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


@app.get("/favorites/export.csv")
def export_favorites_csv():
    songs, error = fetch_favorite_songs(visitor_id=session["visitor_id"], limit=500)
    if error:
        flash(f"播放清單匯出失敗：{error}")
        return redirect(url_for("favorites"))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["歌曲", "歌手", "專輯", "曲風", "Apple Music", "Spotify", "YouTube Music"])
    for song in songs:
        writer.writerow([song["track_name"], song["artist_name"], song["album_name"] or "", song["genre"] or "", song["apple_music_url"] or "", song["spotify_url"] or "", song["youtube_music_url"] or ""])
    response = app.response_class("\ufeff" + output.getvalue(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = "attachment; filename=moodtune-playlist.csv"
    return response


@app.get("/favorites/export.m3u")
def export_favorites_m3u():
    songs, error = fetch_favorite_songs(visitor_id=session["visitor_id"], limit=500)
    if error:
        flash(f"播放清單匯出失敗：{error}")
        return redirect(url_for("favorites"))
    lines = ["#EXTM3U"]
    for song in songs:
        # iTunes preview is the only direct audio URL we receive; platform links
        # remain available in the CSV for full-length playback by the user.
        audio_url = song.get("preview_url") or song.get("youtube_music_url") or song.get("spotify_url")
        if audio_url:
            lines.extend([f"#EXTINF:-1,{song['artist_name']} - {song['track_name']}", audio_url])
    response = app.response_class("\n".join(lines) + "\n", mimetype="audio/x-mpegurl")
    response.headers["Content-Disposition"] = "attachment; filename=moodtune-playlist.m3u"
    return response


@app.post("/feedback")
def feedback():
    try:
        song = json.loads(request.form.get("song_json", "{}"))
    except (json.JSONDecodeError, TypeError):
        flash("歌曲回饋資料格式不正確。")
        return redirect(request.form.get("next") or url_for("index"))
    feedback_type = request.form.get("feedback_type", "")
    ok, error = save_song_feedback(session["visitor_id"], song, feedback_type)
    labels = {"dislike": "已記住你的偏好，之後會減少推薦類似歌曲。", "tag_mismatch": "已記錄標籤不符，會降低相似曲風的推薦。"}
    flash(labels.get(feedback_type, "回饋已保存。") if ok else f"回饋保存失敗：{error}")
    return redirect(request.form.get("next") or url_for("index"))


@app.post("/api/feedback")
def api_feedback():
    payload = request.get_json(silent=True) or {}
    song = payload.get("song") if isinstance(payload.get("song"), dict) else {}
    feedback_type = payload.get("feedback_type", "")
    ok, error = save_song_feedback(session["visitor_id"], song, feedback_type)
    if not ok:
        return jsonify({"error": error or "回饋保存失敗。"}), 400
    return jsonify({"ok": True, "track_id": song.get("track_id"), "feedback_type": feedback_type})


@app.post("/api/feedback/reset")
def api_feedback_reset():
    ok, error = clear_song_feedback(session["visitor_id"])
    if not ok:
        return jsonify({"error": error or "無法重設歌曲回饋。"}), 500
    return jsonify({"ok": True})


@app.post("/favorites/<int:favorite_id>/delete")
def delete_favorite(favorite_id):
    ok, error = delete_favorite_song(
        favorite_id, visitor_id=session["visitor_id"]
    )
    if ok:
        flash("已取消收藏。")
    elif error:
        flash(f"取消收藏失敗：{error}")
    else:
        flash("找不到這筆收藏，或它不屬於目前使用者。")
    return redirect(request.form.get("next") or url_for("favorites"))


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
                raw_token, token_hash = make_account_token()
                create_account_token(user_id, token_hash, "email_verification", int(time()) + 86400)
                verify_url = url_for("verify_email", token=raw_token, _external=True)
                try:
                    send_account_email(email, "MoodTune Email 驗證", f"請開啟以下連結驗證 Email：\n\n{verify_url}\n\n連結 24 小時內有效。")
                    flash("註冊完成，驗證連結已寄出（開發環境會記錄在伺服器 log）。")
                except Exception:
                    flash("註冊完成，但驗證信寄送失敗，請稍後重新申請。")
                return redirect(url_for("index"))
            else:
                flash(f"註冊失敗：{error}")
    return render_template("auth.html", mode="register")


@app.get("/verify-email/<token>")
def verify_email(token):
    user_id, error = consume_account_token(hashlib.sha256(token.encode("utf-8")).hexdigest(), "email_verification", int(time()))
    if error:
        flash(f"Email 驗證暫時失敗：{error}")
    elif not user_id:
        flash("驗證連結無效或已過期，請重新申請。")
    else:
        ok, error = mark_email_verified(user_id, int(time()))
        flash("Email 驗證完成。" if ok else f"Email 驗證失敗：{error}")
    return redirect(url_for("login"))


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user, _ = fetch_user_by_email(email)
        if user:
            raw_token, token_hash = make_account_token()
            create_account_token(user["id"], token_hash, "password_reset", int(time()) + 3600)
            reset_url = url_for("reset_password", token=raw_token, _external=True)
            try:
                send_account_email(email, "MoodTune 重設密碼", f"請開啟以下連結重設密碼：\n\n{reset_url}\n\n連結 1 小時內有效。")
            except Exception:
                pass
        flash("如果這個 Email 有註冊，重設密碼連結已寄出。")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="forgot")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if request.method == "POST":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("密碼至少需要 8 個字元。")
            return render_template("auth.html", mode="reset", token=token)
        user_id, error = consume_account_token(hashlib.sha256(token.encode("utf-8")).hexdigest(), "password_reset", int(time()))
        if error or not user_id:
            flash("重設連結無效或已過期，請重新申請。")
        else:
            ok, error = update_user_password(user_id, generate_password_hash(password))
            flash("密碼已重設，請重新登入。" if ok else f"密碼重設失敗：{error}")
        return redirect(url_for("login"))
    return render_template("auth.html", mode="reset", token=token)


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
        elif os.getenv("REQUIRE_EMAIL_VERIFICATION", "0") == "1" and not user.get("email_verified_at"):
            flash("請先完成 Email 驗證，再登入 MoodTune。")
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
