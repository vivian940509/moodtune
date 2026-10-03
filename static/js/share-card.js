const canvas = document.querySelector("#shareCanvas");
const downloadButton = document.querySelector("#downloadShareCard");

function fitText(ctx, text, x, y, maxWidth, lineHeight, maxLines = 2) {
  const words = String(text || "").split("");
  let line = "";
  let lines = [];

  words.forEach((char) => {
    const next = line + char;
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line);
      line = char;
    } else {
      line = next;
    }
  });
  if (line) lines.push(line);
  lines = lines.slice(0, maxLines);

  lines.forEach((item, index) => {
    const suffix = index === maxLines - 1 && words.join("").length > lines.join("").length ? "..." : "";
    ctx.fillText(item + suffix, x, y + index * lineHeight);
  });
}

function roundedRect(ctx, x, y, width, height, radius) {
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + width, y, x + width, y + height, radius);
  ctx.arcTo(x + width, y + height, x, y + height, radius);
  ctx.arcTo(x, y + height, x, y, radius);
  ctx.arcTo(x, y, x + width, y, radius);
  ctx.closePath();
}

async function loadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => resolve(image);
    image.onerror = reject;
    image.src = url;
  });
}

async function drawShareCard() {
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  const data = canvas.dataset;
  const temperature = Number(data.temperature || 0);

  const gradient = ctx.createLinearGradient(0, 0, 1080, 1350);
  gradient.addColorStop(0, "#f8fbfc");
  gradient.addColorStop(0.52, "#eef7f4");
  gradient.addColorStop(1, "#fff1df");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, 1080, 1350);

  ctx.fillStyle = "#17202a";
  ctx.font = "900 56px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("MoodTune", 86, 118);

  ctx.fillStyle = "#1c8077";
  ctx.font = "800 36px 'Microsoft JhengHei', sans-serif";
  ctx.fillText(`${data.mood} · ${data.context}`, 86, 210);

  roundedRect(ctx, 86, 270, 908, 908, 36);
  ctx.fillStyle = "rgba(255, 255, 255, .82)";
  ctx.fill();

  try {
    const artwork = await loadImage(data.artwork);
    roundedRect(ctx, 150, 334, 300, 300, 28);
    ctx.save();
    ctx.clip();
    ctx.drawImage(artwork, 150, 334, 300, 300);
    ctx.restore();
  } catch {
    ctx.fillStyle = "#dce4ec";
    ctx.fillRect(150, 334, 300, 300);
  }

  ctx.fillStyle = "#17202a";
  ctx.font = "900 58px 'Microsoft JhengHei', sans-serif";
  fitText(ctx, data.track, 500, 370, 410, 70, 2);

  ctx.fillStyle = "#647286";
  ctx.font = "700 34px 'Microsoft JhengHei', sans-serif";
  fitText(ctx, data.artist, 500, 526, 410, 44, 2);

  ctx.fillStyle = "#647286";
  ctx.font = "800 34px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("情緒溫度", 150, 735);

  ctx.fillStyle = "#17202a";
  ctx.font = "900 92px 'Microsoft JhengHei', sans-serif";
  ctx.fillText(`${temperature}`, 150, 842);
  ctx.font = "800 44px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("/ 100", 292, 842);

  ctx.fillStyle = "#e8eef4";
  roundedRect(ctx, 150, 895, 780, 28, 14);
  ctx.fill();

  const barGradient = ctx.createLinearGradient(150, 895, 930, 895);
  barGradient.addColorStop(0, "#f2b35f");
  barGradient.addColorStop(1, "#d96b76");
  ctx.fillStyle = barGradient;
  roundedRect(ctx, 150, 895, 780 * (temperature / 100), 28, 14);
  ctx.fill();

  ctx.fillStyle = "#17202a";
  ctx.font = "900 42px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("今日主旋律", 150, 1018);
  ctx.fillStyle = "#344557";
  ctx.font = "700 34px 'Microsoft JhengHei', sans-serif";
  fitText(ctx, data.profile, 150, 1078, 780, 48, 2);

  ctx.fillStyle = "#1c8077";
  ctx.font = "900 32px 'Microsoft JhengHei', sans-serif";
  ctx.fillText("根據歌曲、心情與情境產生的聽歌心情參考", 86, 1268);
}

if (canvas) {
  drawShareCard();
}

if (downloadButton && canvas) {
  downloadButton.addEventListener("click", async () => {
    await drawShareCard();
    const link = document.createElement("a");
    link.download = "moodtune-share-card.png";
    link.href = canvas.toDataURL("image/png");
    link.click();
  });
}
