# MoodTune 效能與功能修正紀錄

## 本次修正

### 1. 修正 `/analyze` 的 Method Not Allowed

`/analyze` 原本只接受 `POST`。使用者重新整理分析結果，或直接開啟 `/analyze` 時會送出 `GET`，因此出現 `405 Method Not Allowed`。

現在 `GET /analyze` 會顯示提示並導回首頁；正常的分析流程仍使用 `POST /analyze`。

### 2. 支援 LINE 內建瀏覽器的分享卡

原本只使用瀏覽器的下載連結。LINE 內建瀏覽器可能不支援 `download` 屬性，導致下載或分享沒有反應。

現在結果頁有兩個操作：

- **下載分享卡**：一般瀏覽器下載 PNG。
- **分享圖片**：支援 Web Share API 的手機瀏覽器直接分享；LINE 不支援時會開啟圖片，使用者可以長按圖片儲存或分享。

### 3. 上一輪登入／註冊效能修正

- 重用 SQLAlchemy database engine 與小型連線池。
- 註冊、建立帳號、搬移訪客資料合併成同一個 transaction。
- Email 查詢改用可命中索引的 `email = :email`。
- 登入後將顯示名稱放入 session，避免每次渲染頁面再次查詢使用者。
- 加入 `Server-Timing` 與 Vercel 結構化耗時紀錄。
- 啟用 Vercel Fluid Compute。

## 驗證

- Python 測試：`23 passed`
- JavaScript 語法檢查：`node --check static/js/share-card.js`
- `GET /analyze` 不再回傳 405，會導回 `/`。

## 部署

推送 `main` 後，Vercel GitHub integration 會自動建立 production deployment。部署後請測試：

1. 完成一次歌曲分析。
2. 按「下載分享卡」。
3. 在手機或 LINE 內建瀏覽器按「分享圖片」。
4. 直接重新整理 `/analyze`，確認會回首頁而不是 405。

