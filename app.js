// app.js
// TODO: Renderでデプロイ後に発行される「https://〜.onrender.com」のURLに書き換えてください
const API_BASE = "https://your-backend-service.onrender.com";
const state = { jobId: null, timer: null };

const els = {
  form: document.querySelector("#downloadForm"),
  url: document.querySelector("#url"),
  mode: [...document.querySelectorAll("input[name='mode']")],
  retryLimit: document.querySelector("#retryLimit"),
  bitrate: document.querySelector("#bitrate"),
  start: document.querySelector("#startBtn"),
  clear: document.querySelector("#clearBtn"),
  bar: document.querySelector("#progressBar"),
  status: document.querySelector("#statusText"),
  speed: document.querySelector("#speedText"),
  eta: document.querySelector("#etaText"),
  message: document.querySelector("#messageText"),
  files: document.querySelector("#files")
};

function selectedMode() {
  return els.mode.find((item) => item.checked)?.value ?? "video";
}

function setBusy(isBusy) {
  els.start.disabled = isBusy;
  els.start.textContent = isBusy ? "実行中" : "開始";
}

function renderJob(job) {
  const progress = Math.max(0, Math.min(100, Number(job.progress || 0)));
  els.bar.style.width = `${progress}%`;
  els.status.textContent = job.status || "unknown";
  els.speed.textContent = job.speed || "-";
  els.eta.textContent = job.eta || "-";
  els.message.textContent = job.error || job.message || "処理中";
  els.files.innerHTML = "";

  if (Array.isArray(job.files) && job.files.length) {
    const title = document.createElement("strong");
    title.textContent = "完了ファイル";
    els.files.append(title);
    for (const file of job.files) {
      const link = document.createElement("a");
      link.href = `${API_BASE}${file.url}`;
      link.textContent = `${file.name} (${formatBytes(file.size)})`;
      link.download = file.name;
      els.files.append(link);
    }
  }

  if (job.status === "done" || job.status === "error") {
    stopPolling();
    setBusy(false);
  }
}

function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${size.toFixed(unit ? 1 : 0)} ${units[unit]}`;
}

function stopPolling() {
  if (state.timer) window.clearInterval(state.timer);
  state.timer = null;
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const response = await fetch(`${API_BASE}/api/jobs/${state.jobId}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "ジョブ取得に失敗しました");
    renderJob(data);
  } catch (error) {
    els.message.textContent = error.message;
    stopPolling();
    setBusy(false);
  }
}

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  stopPolling();
  setBusy(true);
  els.files.innerHTML = "";
  els.message.textContent = "ジョブを作成しています";
  els.bar.style.width = "0%";

  try {
    const response = await fetch(`${API_BASE}/api/jobs`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        url: els.url.value.trim(),
        mode: selectedMode(),
        retries: Number(els.retryLimit.value || 3),
        audioBitrate: Number(els.bitrate.value || 192)
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "開始できませんでした");
    
    state.jobId = data.id;
    
    // 1秒ごとに進捗をポーリング開始
    state.timer = window.setInterval(() => {
      pollJob();
    }, 1000);
    
    // 初回実行
    await pollJob();
  } catch (error) {
    els.message.textContent = error.message;
    els.status.textContent = "error";
    setBusy(false);
  }
});

els.clear.addEventListener("click", () => {
  stopPolling();
  state.jobId = null;
  setBusy(false);
  els.bar.style.width = "0%";
  els.status.textContent = "待機中";
  els.speed.textContent = "-";
  els.eta.textContent = "-";
  els.message.textContent = "URL を入力して開始してください。";
  els.files.innerHTML = "";
});