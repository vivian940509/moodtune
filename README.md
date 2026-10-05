# MoodTune

MoodTune is a Flask MVP for daily listening mood analysis. Users search a song through the iTunes Search API, choose a mood and context, and receive a listening mood report.

## Deploy With Vercel + Supabase

Use this setup when you want everyone to open MoodTune through a public URL.

### 1. Create Supabase Tables

1. Open Supabase.
2. Create a new project.
3. Open SQL Editor.
4. Paste and run `database/schema_supabase.sql`.

The Supabase schema creates:

- `users`
- `user_preferences`
- `mood_entries`
- `song_inputs`
- `analysis_results`

If this project was deployed before the preference and mood journal features were added,
run `database/migrate_mood_journal_supabase.sql` once in Supabase SQL Editor instead of
recreating the existing tables.

### 2. Copy The Supabase Database URL

In Supabase, open `Connect` and choose the pooled connection string for serverless deployment.

Use the transaction pooler when deploying on Vercel:

```text
postgresql://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres
```

Replace `<password>` with the real database password. If the password has special characters such as `#`, `?`, `&`, or a space, percent-encode it before putting it in Vercel.

### 3. Set Vercel Environment Variables

In Vercel project settings, add:

```text
DATABASE_URL=<Supabase pooled Postgres URL>
SECRET_KEY=<random string>
AI_PROVIDER=
AI_API_KEY=
```

Then deploy from GitHub. Vercel detects `app.py` as the Flask entrypoint.
`vercel.json` rewrites all routes to the Flask app, so `/`, `/history`, `/api/search`, and `/analyze` are served by the same application.

After deployment, open the production URL and test:

- Search for a song.
- Run one analysis.
- Open `/history` and confirm the saved result appears.

## Local Setup With Supabase

Use this setup when you want to run Flask on your computer, but store history in Supabase.

### 1. Create Supabase Tables

1. Open Supabase and create a project.
2. Open SQL Editor.
3. Paste and run `database/schema_supabase.sql`.

### 2. Set `.env`

Copy `.env.supabase.example` into `.env`, then replace the placeholders:

```text
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@<pooler-host>:6543/postgres
SECRET_KEY=dev-moodtune-local
AI_PROVIDER=
AI_API_KEY=
```

For local Flask and Vercel, the pooled connection string on port `6543` is usually the safest choice. If the database password contains special characters such as `#`, `?`, `&`, `%`, or a space, percent-encode it before saving it.

### 3. Run Locally

```powershell
py -m pip install -r requirements.txt
py app.py
```

Open `http://127.0.0.1:5000`, run an analysis, then open `/history`.

## Local Setup With XAMPP MySQL

1. Open XAMPP and start MySQL.
2. Open phpMyAdmin.
3. Create a database named `moodtune`.
4. Import `database/schema.sql`.
5. Copy `.env.example` to `.env`.
6. Keep this local database URL unless your XAMPP password is different:

```text
DATABASE_URL=mysql+pymysql://root:@localhost/moodtune
```

For an existing MySQL database, run `database/migrate_mood_journal_mysql.sql` once.
Do not run the migration repeatedly because its `ALTER TABLE` statements are intended
for a one-time upgrade.

Install dependencies and run:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Open:

```text
http://127.0.0.1:5000
```

Run tests before deploying changes:

```powershell
py -m pytest
```

## Railway MySQL

Set these variables in Railway:

```text
DATABASE_URL=<Railway MySQL or MariaDB connection URL>
SECRET_KEY=<random string>
AI_PROVIDER=
AI_API_KEY=
```

Run `database/schema.sql` on the Railway database before using history.

## Notes

- MoodTune still works without `AI_API_KEY`; it uses the local rule-based analysis in `mood_analysis.py`.
- First-time visitors can save a language, genre, and optional K-pop group preference without creating an account.
- Mood text, diary text, and history are associated with an anonymous browser session ID stored in Flask's signed session cookie.
- The history page needs a reachable database. If saving fails, analysis still renders, but the result will not appear in `/history`.
- Do not commit real `.env` values. Keep production secrets in Vercel, Railway, or Supabase settings.
