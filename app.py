import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import BadRequest

from database import fetch_history, fetch_trends, save_analysis
from mood_analysis import analyze_mood, recommendation_terms
from music_api import search_tracks


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-moodtune")

MOODS = ["開心", "平靜", "累", "煩", "難過", "想專心"]
CONTEXTS = ["通勤", "讀書", "上班", "睡前", "失戀", "放空"]


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


def get_recommendations(mood, context, song):
    recommendations = []
    seen = {song.get("track_id")}
    for term in recommendation_terms(mood, context, song):
        try:
            tracks = search_tracks(term, limit=3)
        except Exception:
            continue
        for track in tracks:
            track_id = track.get("track_id")
            if track_id in seen:
                continue
            recommendations.append(track)
            seen.add(track_id)
            if len(recommendations) == 3:
                return recommendations
    return recommendations


@app.get("/")
def index():
    return render_template("index.html", moods=MOODS, contexts=CONTEXTS)


@app.get("/api/search")
def api_search():
    term = request.args.get("q", "")
    limit = request.args.get("limit", 8, type=int)
    limit = max(1, min(limit or 8, 12))
    try:
        tracks = search_tracks(term, limit=limit)
        return jsonify({"tracks": tracks})
    except Exception as exc:
        return jsonify({"error": f"搜尋暫時失敗：{exc}"}), 502


@app.post("/analyze")
def analyze():
    mood = request.form.get("mood", "平靜")
    context = request.form.get("context", "放空")
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

    result = analyze_mood(song=song, mood=mood, context=context)
    recommendations = get_recommendations(mood=mood, context=context, song=song)
    saved_id, save_error = save_analysis(song=song, mood=mood, context=context, result=result)

    return render_template(
        "result.html",
        song=song,
        mood=mood,
        context=context,
        result=result,
        recommendations=recommendations,
        saved_id=saved_id,
        save_error=save_error,
    )


@app.get("/history")
def history():
    rows, error = fetch_history()
    trends, trend_error = fetch_trends()
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


if __name__ == "__main__":
    app.run(debug=True)
