const searchInput = document.querySelector("#songSearch");
const searchButton = document.querySelector("#searchButton");
const trackResults = document.querySelector("#trackResults");
const searchHint = document.querySelector("#searchHint");
const songJson = document.querySelector("#songJson");
const selectedSong = document.querySelector("#selectedSong");
const analyzeButton = document.querySelector("#analyzeButton");
const moodText = document.querySelector("#moodText");
const moodSuggestion = document.querySelector("#moodSuggestion");
const moodInputs = Array.from(document.querySelectorAll('input[name="mood"]'));
let moodManuallySelected = false;

const moodKeywords = [
  { mood: "開心", words: ["開心", "快樂", "興奮", "期待", "順利"] },
  { mood: "累", words: ["累", "疲倦", "沒精神", "想睡", "加班"] },
  { mood: "煩", words: ["煩", "焦慮", "緊張", "壓力", "擔心"] },
  { mood: "難過", words: ["難過", "傷心", "失戀", "低落", "想哭"] },
  { mood: "想專心", words: ["專心", "讀書", "工作", "報告", "考試"] },
  { mood: "平靜", words: ["平靜", "放鬆", "舒服", "安心", "普通"] },
];

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function selectTrack(track, button) {
  document.querySelectorAll(".track-card").forEach((card) => card.classList.remove("selected"));
  button.classList.add("selected");
  songJson.value = JSON.stringify(track);
  selectedSong.innerHTML = `<strong>${escapeHtml(track.track_name)}</strong><br>${escapeHtml(track.artist_name)} · ${escapeHtml(track.genre)}`;
  analyzeButton.disabled = false;
}

function renderTracks(tracks) {
  trackResults.innerHTML = "";
  if (!tracks.length) {
    searchHint.textContent = "找不到歌曲，換一個關鍵字試試。";
    return;
  }
  searchHint.textContent = "選一首最符合今天心情的歌。";
  tracks.forEach((track) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "track-card";
    button.innerHTML = `
      <img src="${escapeHtml(track.artwork_url)}" alt="${escapeHtml(track.track_name)} 專輯封面">
      <span>
        <strong>${escapeHtml(track.track_name)}</strong>
        <span>${escapeHtml(track.artist_name)}</span>
        <span>${escapeHtml(track.genre || "Music")}</span>
      </span>
    `;
    button.addEventListener("click", () => selectTrack(track, button));
    trackResults.appendChild(button);
  });
}

async function search() {
  const query = searchInput.value.trim();
  if (!query) {
    searchHint.textContent = "請先輸入歌名或歌手。";
    return;
  }
  searchButton.disabled = true;
  searchHint.textContent = "搜尋中...";
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "搜尋失敗");
    renderTracks(payload.tracks || []);
  } catch (error) {
    trackResults.innerHTML = "";
    searchHint.textContent = error.message;
  } finally {
    searchButton.disabled = false;
  }
}

searchButton.addEventListener("click", search);
searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    search();
  }
});

moodInputs.forEach((input) => {
  input.addEventListener("change", () => {
    moodManuallySelected = true;
    moodSuggestion.textContent = `已選擇「${input.value}」，你可以繼續輸入或修改。`;
  });
});

moodText.addEventListener("input", () => {
  const text = moodText.value.trim();
  if (!text) {
    moodSuggestion.textContent = "輸入後會協助選擇接近的心情，你仍然可以自己調整。";
    return;
  }

  const match = moodKeywords.find(({ words }) => words.some((word) => text.includes(word)));
  if (!match) {
    moodSuggestion.textContent = "這份心情比較複雜，先保留目前選擇，也可以手動調整。";
    return;
  }

  if (!moodManuallySelected) {
    const target = moodInputs.find((input) => input.value === match.mood);
    if (target) target.checked = true;
  }
  moodSuggestion.textContent = `文字看起來接近「${match.mood}」，需要時可以手動修改。`;
});


const analysisForm = document.querySelector("form.workspace");
if (analysisForm) {
  analysisForm.addEventListener("submit", () => {
    if (analyzeButton && !analyzeButton.disabled) {
      analyzeButton.disabled = true;
      analyzeButton.dataset.originalText = analyzeButton.textContent;
      analyzeButton.textContent = "正在分析並找推薦歌曲…";
      if (searchHint) searchHint.textContent = "正在整理你的心情與推薦歌曲，請稍候…";
    }
  });
}
