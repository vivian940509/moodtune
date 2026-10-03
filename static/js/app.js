const searchInput = document.querySelector("#songSearch");
const searchButton = document.querySelector("#searchButton");
const trackResults = document.querySelector("#trackResults");
const searchHint = document.querySelector("#searchHint");
const songJson = document.querySelector("#songJson");
const selectedSong = document.querySelector("#selectedSong");
const analyzeButton = document.querySelector("#analyzeButton");

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
