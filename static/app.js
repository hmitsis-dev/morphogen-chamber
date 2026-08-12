(() => {
  "use strict";

  const revealBtn = document.getElementById("reveal");
  const panel = document.getElementById("panel");
  revealBtn.addEventListener("click", () => panel.classList.toggle("open"));

  const tickerTrack = document.getElementById("ticker-track");
  const callDirection = document.getElementById("call-direction");
  const callAsset = document.getElementById("call-asset");
  const callEntry = document.getElementById("call-entry");
  const callTarget = document.getElementById("call-target");
  const confidenceValue = document.getElementById("confidence-value");
  const confidenceFill = document.getElementById("confidence-fill");
  const commentaryEl = document.getElementById("commentary");
  const participantsValue = document.getElementById("participants-value");
  const sharpeValue = document.getElementById("sharpe-value");
  const canvas = document.getElementById("backtest-canvas");
  const ctx = canvas.getContext("2d");

  function fmtUsd(n) {
    if (n >= 1000) return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
    return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }

  function fmtPct(n) {
    const sign = n >= 0 ? "+" : "";
    return `${sign}${n.toFixed(2)}%`;
  }

  function renderTicker(prices) {
    const items = Object.entries(prices).map(([symbol, p]) => {
      const dir = p.usd_24h_change >= 0 ? "up" : "down";
      const arrow = p.usd_24h_change >= 0 ? "▲" : "▼";
      return `<span class="item">${symbol} ${fmtUsd(p.usd)} <span class="${dir}">${arrow} ${fmtPct(p.usd_24h_change)}</span></span>`;
    }).join("");
    // Duplicated once so the -50% keyframe loops seamlessly.
    tickerTrack.innerHTML = items + items;
  }

  function colorForConfidence(c) {
    if (c > 75) return "var(--green)";
    if (c > 58) return "var(--amber)";
    return "var(--red)";
  }

  function applyTick(msg) {
    renderTicker(msg.prices);

    callDirection.textContent = msg.call.direction;
    callDirection.className = "direction " + msg.call.direction;
    callAsset.textContent = msg.call.asset;
    callEntry.textContent = fmtUsd(msg.call.entry);
    callTarget.textContent = fmtUsd(msg.call.target);

    confidenceValue.textContent = msg.confidence.toFixed(1) + "%";
    const color = colorForConfidence(msg.confidence);
    confidenceValue.style.color = color;
    confidenceFill.style.width = Math.max(0, Math.min(100, msg.confidence)) + "%";
    confidenceFill.style.background = color;

    commentaryEl.textContent = msg.commentary;
    participantsValue.textContent = String(msg.viewers);
  }

  let lastCurve = null;

  function drawBacktest(curve) {
    lastCurve = curve;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const min = Math.min(...curve), max = Math.max(...curve);
    const pad = 6;
    const x = (i) => pad + (i / (curve.length - 1)) * (w - pad * 2);
    const y = (v) => h - pad - ((v - min) / (max - min || 1)) * (h - pad * 2);

    ctx.strokeStyle = "rgba(255, 176, 0, 0.15)";
    ctx.lineWidth = 1;
    for (let g = 0; g <= 3; g++) {
      const gy = pad + (g / 3) * (h - pad * 2);
      ctx.beginPath();
      ctx.moveTo(0, gy);
      ctx.lineTo(w, gy);
      ctx.stroke();
    }

    ctx.strokeStyle = "#39d98a";
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    curve.forEach((v, i) => {
      const px = x(i), py = y(v);
      if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
    });
    ctx.stroke();

    ctx.fillStyle = "rgba(57, 217, 138, 0.08)";
    ctx.lineTo(x(curve.length - 1), h - pad);
    ctx.lineTo(x(0), h - pad);
    ctx.closePath();
    ctx.fill();
  }

  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }

      if (msg.kind === "tick") {
        applyTick(msg);
      } else if (msg.kind === "backtest") {
        sharpeValue.textContent = "SHARPE " + msg.sharpe.toFixed(1);
        drawBacktest(msg.curve);
      }
    };

    ws.onclose = () => setTimeout(connect, 1500);
    ws.onerror = () => ws.close();
  }
  connect();

  window.addEventListener("resize", () => {
    if (lastCurve) drawBacktest(lastCurve);
  });
})();
