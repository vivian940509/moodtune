import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, url_for

from database import fetch_history, save_analysis
from mood_analysis import analyze_mood
from music_api import search_tracks


load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-moodtune")

MOODS = ["開心", "平靜", "累", "煩", "難過", "想專心"]
CONTEXTS = ["通勤", "讀書", "上班", "睡前", "失戀", "放空"]


@app.get("/")
def index():
    return render_template("index.html", moods=MOODS, contexts=CONTEXTS)


@app.get("/api/search")
def api_search():
    term = request.args.get("q", "")
    try:
        tracks = search_tracks(term)
        return jsonify({"tracks": tracks})
    except Exception as exc:
        return jsonify({"error": f"搜尋暫時失敗：{exc}"}), 502


@app.post("/analyze")
def analyze():
    mood = request.form.get("mood", "平靜")
    context = request.form.get("context", "放空")
    raw_song = request.form.get("song_json", "")

    if not raw_song:
        return redirect(url_for("index"))

    song = json.loads(raw_song)
    result = analyze_mood(song=song, mood=mood, context=context)
    saved_id, save_error = save_analysis(song=song, mood=mood, context=context, result=result)

    return render_template(
        "result.html",
        song=song,
        mood=mood,
        context=context,
        result=result,
        saved_id=saved_id,
        save_error=save_error,
    )


@app.get("/history")
def history():
    rows, error = fetch_history()
    return render_template("history.html", rows=rows, error=error)


if __name__ == "__main__":
    app.run(debug=True)
