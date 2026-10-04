const trendCanvas = document.querySelector("#moodTrendChart");

if (trendCanvas && window.Chart) {
  const chartData = JSON.parse(trendCanvas.dataset.chart || "{}");
  const temperatures = chartData.temperatures || [];

  new Chart(trendCanvas, {
    type: "line",
    data: {
      labels: chartData.labels || [],
      datasets: [
        {
          label: "情緒溫度",
          data: temperatures,
          borderColor: "#1c8077",
          backgroundColor: "rgba(28, 128, 119, .14)",
          fill: true,
          tension: 0.36,
          pointBackgroundColor: "#d96b76",
          pointBorderColor: "#ffffff",
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: {
          callbacks: {
            afterLabel(context) {
              const index = context.dataIndex;
              const mood = chartData.moods?.[index] || "";
              const track = chartData.tracks?.[index] || "";
              return [mood, track].filter(Boolean);
            },
          },
        },
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          ticks: {
            stepSize: 20,
          },
          grid: {
            color: "rgba(100, 114, 134, .18)",
          },
        },
        x: {
          grid: {
            display: false,
          },
        },
      },
    },
  });
}
