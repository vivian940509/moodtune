# MoodTune Agent Guide

This project is a Flask MVP for AI song / streaming mood analysis.

## Product Direction

Build the first version as a public website where users:

- Search songs through the iTunes Search API.
- Pick a mood and listening context.
- See a daily listening mood report.
- View saved analysis history.

Do not add Spotify OAuth, YouTube API, login, payments, or full lyrics analysis unless the user explicitly asks.

## Database

Local development may use XAMPP MySQL. Production deployment should prefer Supabase Postgres when deploying on Vercel.

Expected local environment:

```text
DATABASE_URL=mysql+pymysql://root:@localhost/moodtune
AI_API_KEY=
AI_PROVIDER=
```

Expected Vercel/Supabase environment:

```text
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres
SECRET_KEY=<random string>
AI_API_KEY=
AI_PROVIDER=
```

The app must still work without an AI key by using local rule-based analysis.

## Architecture

Prefer these module boundaries:

- `app.py`: Flask routes only.
- `music_api.py`: iTunes Search API and track normalization.
- `mood_analysis.py`: local scoring and stable analysis result schema.
- `database.py`: database connection and persistence helpers.
- `database/schema.sql`: MySQL schema.
- `database/schema_supabase.sql`: Supabase/Postgres schema.
- `templates/`: Jinja pages.
- `static/`: CSS and browser JavaScript.

## Safety

MoodTune is entertainment/reflection, not medical diagnosis.

Use wording like:

> 根據你選的歌曲與情境，產生今日聽歌心情參考。

Avoid claims like:

> AI 判斷你有憂鬱症。

Do not commit secrets. Keep real API keys and production database URLs in environment variables.

## Testing

Use `py -m pytest` on this Windows machine.

Add or update tests before changing behavior in `mood_analysis.py`, `music_api.py`, or database helpers.
