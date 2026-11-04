// Panel: WebSocket olaylarını grafiklere, durum kartına, API kaydına ve sonuç tablosuna işler.
const N = 120;                       // grafikte tutulan saniye sayısı
const $ = (id) => document.getElementById(id);
const fmtTime = (t) => new Date(t * 1000).toLocaleTimeString("tr-TR", { hour12: false });

let qod = { status: null, expiresAt: null, targetKbps: null };
const markers = [];                  // {label, text, color}

// Grafiklerde QoD açılış/kapanış anlarına dikey çizgi çizen küçük eklenti.
const markerPlugin = {
  id: "markers",
  afterDatasetsDraw(chart) {
    const { ctx, chartArea: a, scales: { x } } = chart;
    for (const m of markers) {
      const i = chart.data.labels.indexOf(m.label);
      if (i < 0) continue;
      const px = x.getPixelForValue(i);
      ctx.save();
      ctx.strokeStyle = m.color; ctx.setLineDash([4, 4]); ctx.lineWidth = 2;
      ctx.beginPath(); ctx.moveTo(px, a.top); ctx.lineTo(px, a.bottom); ctx.stroke();
      ctx.setLineDash([]); ctx.fillStyle = m.color; ctx.font = "12px system-ui";
      ctx.fillText(m.text, Math.min(px + 4, a.right - 70), a.top + 12);
      ctx.restore();
    }
  },
};

const baseOpts = (yTitle) => ({
  animation: false, responsive: true, maintainAspectRatio: false,
  interaction: { mode: "index", intersect: false },
  scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { beginAtZero: true, title: { display: true, text: yTitle } } },
  plugins: { legend: { position: "bottom", labels: { boxWidth: 14 } } },
});

const rateChart = new Chart($("ch-rate"), {
  type: "line",
  data: { labels: [], datasets: [
    { label: "Alınan video hızı", data: [], borderColor: "#0f6e61", borderWidth: 2.5, pointRadius: 0 },
    { label: "GCC tahmini", data: [], borderColor: "#b4501c", borderWidth: 1.5, pointRadius: 0 },
    { label: "Bağlantı kapasitesi", data: [], borderColor: "#8a939b", borderDash: [6, 4], borderWidth: 1.5, pointRadius: 0 },
    { label: "QoD profil hızı", data: [], borderColor: "#2563a8", borderDash: [2, 3], borderWidth: 2, pointRadius: 0, spanGaps: false },
  ] },
  options: baseOpts("kbps"),
  plugins: [markerPlugin],
});

const delayChart = new Chart($("ch-delay"), {
  type: "line",
  data: { labels: [], datasets: [
    { label: "Uçtan uca gecikme (ms)", data: [], borderColor: "#17212b", borderWidth: 2, pointRadius: 0, yAxisID: "y" },
    { label: "Paket kaybı (%)", data: [], borderColor: "#b42318", borderWidth: 1.5, pointRadius: 0, yAxisID: "y1" },
  ] },
  options: { ...baseOpts("ms"), scales: {
    x: { ticks: { maxTicksLimit: 8 } },
    y: { beginAtZero: true, title: { display: true, text: "ms" } },
    y1: { beginAtZero: true, position: "right", max: 100, grid: { drawOnChartArea: false }, title: { display: true, text: "%" } },
  } },
  plugins: [markerPlugin],
});

function push(chart, label, values) {
  chart.data.labels.push(label);
  values.forEach((v, i) => chart.data.datasets[i].data.push(v));
  if (chart.data.labels.length > N) {
    chart.data.labels.shift();
    chart.data.datasets.forEach((d) => d.data.shift());
  }
}

function onStats(e, draw) {
  const label = fmtTime(e.t);
  const profile = qod.status === "AVAILABLE" ? qod.targetKbps : null;
  push(rateChart, label, [e.rx_kbps, e.remb_kbps, e.capacity_kbps, profile]);
  push(delayChart, label, [e.e2e_ms, e.loss_pct]);
  if (draw) { rateChart.update(); delayChart.update(); }
  $("c-e2e").textContent = `gecikme ${e.e2e_ms == null ? "—" : Math.round(e.e2e_ms)} ms`;
  $("c-rx").textContent = `${Math.round(e.rx_kbps)} kbps`;
  $("c-fps").textContent = `${Math.round(e.fps)} fps`;
  setLoad(e.load);
  setPolicy(e.policy);
}

function setLoad(on) {
  $("c-load").textContent = on ? "ağ yoğun" : "ağ boş";
  const b = $("b-load");
  b.textContent = on ? "Ağı rahatlat" : "Ağı yoğunlaştır";
  b.classList.toggle("on", !!on);
  b.dataset.on = on ? "1" : "";
}

function setPolicy(p) {
  if (!p) return;
  $("b-P2").classList.toggle("on", p === "P2");
  $("b-P3").classList.toggle("on", p === "P3");
}

function onQod(e) {
  qod.status = e.qosStatus;
  if (e.targetKbps) qod.targetKbps = e.targetKbps;
  qod.expiresAt = e.qosStatus === "AVAILABLE" && e.expiresAt ? Date.parse(e.expiresAt) : null;
  const pill = $("qod-pill");
  pill.textContent = e.qosStatus; pill.className = `pill ${e.qosStatus}`;
  const info = {
    REQUESTED: `İstendi: ${qod.targetKbps} kbps profil, ağın onayı bekleniyor`,
    AVAILABLE: `Öncelik açık: video ${qod.targetKbps} kbps'lik ayrılmış kapasitede`,
    UNAVAILABLE: `Bitti: ${e.statusInfo === "DURATION_EXPIRED" ? "süre doldu" : e.statusInfo === "DELETE_REQUESTED" ? "silindi" : e.statusInfo || ""}`,
  }[e.qosStatus] || "";
  $("qod-info").textContent = info;
  const label = rateChart.data.labels[rateChart.data.labels.length - 1];
  if (label && e.qosStatus === "AVAILABLE") markers.push({ label, text: "QoD açık", color: "#0f6e61" });
  if (label && e.qosStatus === "UNAVAILABLE") markers.push({ label, text: "QoD bitti", color: "#b42318" });
  if (e.qosStatus !== "AVAILABLE") $("qod-left").textContent = "";
}

function onApiLog(e) {
  const d = document.createElement("details");
  const ok = e.status == null ? "note" : e.status < 300 ? "ok" : "bad";
  const status = e.status == null ? "bildirim alındı" : `→ ${e.status}`;
  d.innerHTML = `<summary>${fmtTime(e.t)} <b>${e.method}</b> ${e.path} <span class="${ok}">${status}</span></summary>`;
  const pre = document.createElement("pre");
  pre.textContent = (e.request ? "İstek:\n" + JSON.stringify(e.request, null, 2) + "\n" : "") +
                    (e.response ? "Cevap:\n" + JSON.stringify(e.response, null, 2) : "");
  if (pre.textContent) d.appendChild(pre);
  $("log").prepend(d);
}

function onResult(e) {
  const p = e.policy;
  $(`r-${p}-ttt`).textContent = e.t_to_target_s == null
    ? `ulaşamadı (en yüksek ${Math.round(e.max_kbps)} kbps)` : `${e.t_to_target_s.toFixed(1)} sn`;
  $(`r-${p}-util`).textContent = `%${Math.round(e.utilization * 100)}`;
  $(`r-${p}-spike`).textContent = `${Math.round(e.closing_spike_ms)} ms`;
}

function handle(e, draw = true) {
  switch (e.type) {
    case "stats": return onStats(e, draw);
    case "qod_state": return onQod(e);
    case "api_log": return onApiLog(e);
    case "result": return onResult(e);
    case "load": return setLoad(e.on);
    case "policy": return setPolicy(e.policy);
    case "p3": $("p3log").textContent = `P3: ${e.action} → ${e.kbps} kbps (${fmtTime(e.t)})`; return;
    case "scenario": $("scen-status").textContent = `Senaryo ${e.policy}: ${e.phase} (${fmtTime(e.t)})`; return;
    case "error": return toast(e.message);
  }
}

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.style.display = "block";
  clearTimeout(toast.h); toast.h = setTimeout(() => (t.style.display = "none"), 4000);
}

function connect() {
  const ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
  ws.onmessage = (m) => {
    const e = JSON.parse(m.data);
    if (e.type === "snapshot") {
      e.events.forEach((x) => handle(x, false));
      rateChart.update(); delayChart.update();
    } else handle(e);
  };
  ws.onclose = () => setTimeout(connect, 1500);
}

document.addEventListener("click", async (ev) => {
  const b = ev.target.closest("button");
  if (!b) return;
  let url = b.dataset.post;
  if (b.hasAttribute("data-toggle-load")) url = b.dataset.on ? "/api/load/off" : "/api/load/on";
  if (!url) return;
  const r = await fetch(url, { method: "POST" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    toast(body.error || `İstek başarısız (${r.status})`);
  }
});

setInterval(() => {
  if (qod.status === "AVAILABLE" && qod.expiresAt) {
    const left = Math.max(0, (qod.expiresAt - Date.now()) / 1000);
    $("qod-left").textContent = `${left.toFixed(0)} sn kaldı`;
  }
}, 250);

connect();
