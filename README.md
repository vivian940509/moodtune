# MoodTune

MoodTune is a Flask MVP for daily listening mood analysis. Users search a song through the iTunes Search API, choose a mood and context, and receive a listening mood report.

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

Install dependencies and run:

```powershell
py -m pip install -r requirements.txt
py app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Railway

Set these variables in Railway:

```text
DATABASE_URL=<Railway MySQL or MariaDB connection URL>
SECRET_KEY=<random string>
AI_PROVIDER=
AI_API_KEY=
```

Run `database/schema.sql` on the Railway database before using history.
