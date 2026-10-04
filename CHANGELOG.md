# MoodTune 修改紀錄

## 2026-10-04

### 外部音樂平台播放

- 歌曲資料新增外部平台連結：
  - YouTube Music 搜尋
  - Apple Music / iTunes 連結
  - Spotify 搜尋
  - SoundCloud 搜尋
- 分析結果頁新增外部播放按鈕。
- 推薦歌曲也會顯示外部平台按鈕。
- 保留 iTunes 30 秒試聽，不在站內自行串流完整 copyrighted 音訊。
- 新增測試確認外部平台連結會被產生與顯示。

### Phase 2 資料視覺化

- 歷史紀錄頁新增情緒折線圖。
- 使用 Chart.js 顯示最近最多 30 次情緒溫度變化。
- 圖表 tooltip 會顯示當次心情與歌曲名稱。
- 歷史紀錄頁新增 `AI Weekly Report` 區塊。
- 週報會根據最近 7 次紀錄產生：
  - 平均情緒溫度
  - 常見心情
  - 常見聽歌情境
  - 常見音樂傾向
  - 本週摘要與今日建議
- 新增 `/history` 頁面的 smoke test，確認圖表與週報區塊能正常渲染。

### 本機可直接使用

- 新增 SQLite 本機資料庫支援。
- 預設 `.env.example` 改為：

```text
DATABASE_URL=sqlite:///database/moodtune.local.db
```

- 新增 `database/schema_sqlite.sql`，第一次使用 SQLite 時會自動建立資料表。
- 新增 `.gitignore` 規則，避免把本機 `.db` 資料庫檔提交到 GitHub。

### Supabase 支援

- 保留並確認 Supabase PostgreSQL 支援。
- 新增 `.env.supabase.example`，方便切換成 Supabase 連線。
- README 新增「本機 Flask + Supabase」設定步驟。
- `database.py` 會自動把 `postgresql://` / `postgres://` 轉成 SQLAlchemy 可用的 `postgresql+psycopg2://`。
- Supabase 連線使用 SSL 設定，適合雲端資料庫。

### Vercel 部署

- 更新 `vercel.json`，新增 rewrite：

```json
{
  "source": "/(.*)",
  "destination": "/app.py"
}
```

- 讓 `/`、`/history`、`/api/search`、`/analyze` 都能正確交給 Flask 處理。

### 後端防呆

- `/api/search` 新增 `limit` 上限，避免一次請求太多 iTunes 搜尋結果。
- `/analyze` 新增歌曲 JSON 格式檢查。
- 當 mood 或 context 不合法時，會回到預設值。
- 壞掉或不完整的歌曲資料會回傳 400，不會讓 Flask 直接變成 500。

### 頁面文案

- 歷史紀錄頁的資料庫錯誤提示改成同時支援：
  - XAMPP MySQL
  - Supabase PostgreSQL
  - SQLite 本機資料庫
- 分析結果頁的儲存失敗提示改成檢查 `DATABASE_URL`、資料庫連線與 schema。

### 測試

- 新增 SQLite 自動建表與歷史紀錄儲存測試。
- 新增 `/analyze` 缺少歌曲資料與壞 JSON 的 route 測試。
- 目前測試結果：

```text
8 passed
```

### GitHub 更新

- 已建立 commit：

```text
1d7364a Add local SQLite and Supabase setup support
```

- 已推送到：

```text
origin/main
https://github.com/vivian940509/moodtune.git
```
