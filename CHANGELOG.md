# MoodTune 修改紀錄

## 2026-10-07

### 日記、好友與聊天

- 新增獨立 `/journal` 心情日記頁面，可保存標題、心情與日記內容。
- 新增好友搜尋、好友申請、接受／略過好友申請。
- 新增好友一對一聊天功能。
- 聊天送出訊息改為背景請求，不再整頁重新載入。
- 聊天訊息泡泡改為橫向顯示，並新增聊天查詢索引改善速度。

### 帳號與安全

- 新增忘記密碼與一次性限時重設密碼連結。
- 新增 Email 驗證連結與 SMTP 設定。
- 新增 `REQUIRE_EMAIL_VERIFICATION` 環境變數，可強制登入前完成 Email 驗證。

### 歌曲回饋與收藏

- 新增「標籤不符／少推薦這類」歌曲回饋。
- 回饋會降低相同歌手與曲風歌曲的後續推薦。
- 收藏歌曲可刪除。
- 收藏歌曲可匯出 CSV 與 M3U 播放清單。
- 保留 Apple Music、Spotify、YouTube Music 完整播放入口；iTunes 仍只提供 30 秒試聽。

### 分析流程與部署

- 移除分析頁中的心情日記欄位，保留獨立日記功能。
- Supabase PostgreSQL schema 已執行。
- Vercel `DATABASE_URL` 已設定為 Supabase transaction pooler。
- 測試結果：28 項通過，JavaScript 語法檢查通過。
- 相關修改已推送至 GitHub `main` 分支。

## 2026-10-05

### 音樂偏好與心情日記

- 新增首次使用音樂偏好設定，可選歌曲語言、曲風與韓團。
- 選擇「韓文／K-pop」時才顯示韓團選單，偏好會套用到搜尋提示與推薦。
- 首頁流程改成先輸入心情文字與情境，再搜尋並選擇歌曲。
- 新增簡易文字關鍵字提示，協助選擇最接近的心情，仍可手動修正。
- 新增選填的心情日記，分析後會顯示在結果與歷史紀錄。
- 歷史紀錄依匿名瀏覽器工作階段區分，避免不同訪客互相看到日記。
- 情緒折線圖新增最近 7 次／30 次切換。
- SQLite 會自動升級舊資料表；MySQL 與 Supabase 新增一次性遷移檔。
- 測試增加至 19 項，涵蓋首次引導、偏好、日記與訪客紀錄隔離。

## 2026-10-04

### 歌曲排行榜

- 新增 `/leaderboard` 歌曲排行榜頁面。
- 依照歷史分析紀錄統計歌曲出現次數。
- 顯示前三名歌曲卡片與完整排行列表。
- 排行榜包含：
  - 分析次數
  - 平均情緒溫度
  - 歌手、曲風與封面
- 導覽列新增「排行榜」入口。
- 新增排行榜資料查詢與頁面渲染測試。

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

## 2026-10-05 - Accounts, language-aware search, compact chart
- Added email/password registration, login and logout (passwords stored as Werkzeug hashes).
- Account sessions use a stable account visitor key so history, preferences and favorites are separated per account.
- Registration migrates the current browser's anonymous history/preferences into the new account.
- Favorites are now scoped by account/visitor key.
- iTunes search now follows the selected music language market (TW/US/JP/KR), translates genre-only searches such as `獨立音樂` -> `indie` for non-Chinese markets, and filters Western results to remove CJK-titled results.
- Wrapped the Chart.js canvas in a fixed-height container to stop the history chart from expanding vertically.
- Extended Supabase/MySQL/SQLite schemas and migrations for account fields and per-user favorites.
