const trendCanvas = document.querySelector("#moodTrendChart");

if (trendCanvas && window.Chart) {
  const chartData = JSON.parse(trendCanvas.dataset.chart || "{}");
  const temperatures = chartData.temperatures || [];
  const rangeSelect = document.querySelector("#chartRange");
  const rangeTitle = document.querySelector("#chartRangeTitle");

  function sliceChartData(range) {
    return {
      labels: (chartData.labels || []).slice(-range),
      temperatures: temperatures.slice(-range),
      moods: (chartData.moods || []).slice(-range),
      tracks: (chartData.tracks || []).slice(-range),
    };
  }

  let visibleData = sliceChartData(7);

  const chart = new Chart(trendCanvas, {
    type: "line",
    data: {
      labels: visibleData.labels,
      datasets: [
        {
          label: "情緒溫度",
          data: visibleData.temperatures,
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
              const mood = visibleData.moods?.[index] || "";
              const track = visibleData.tracks?.[index] || "";
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

  rangeSelect?.addEventListener("change", () => {
    const range = Number(rangeSelect.value);
    visibleData = sliceChartData(range);
    chart.data.labels = visibleData.labels;
    chart.data.datasets[0].data = visibleData.temperatures;
    rangeTitle.textContent = `最近 ${visibleData.temperatures.length} 次情緒溫度`;
    chart.update();
  });

  rangeTitle.textContent = `最近 ${visibleData.temperatures.length} 次情緒溫度`;
}
