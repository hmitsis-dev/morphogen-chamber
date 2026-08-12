(() => {
  "use strict";

  const canvas = document.getElementById("scene");
  const ctx = canvas.getContext("2d");

  const panel = document.getElementById("panel");
  const revealBtn = document.getElementById("reveal");
  const log = document.getElementById("log");
  const statRateEl = document.getElementById("stat-rate");
  const statTotalEl = document.getElementById("stat-total");
  const statLastEl = document.getElementById("stat-last");
  const viewersBadge = document.getElementById("viewers-badge");
  const statViewersEl = document.getElementById("stat-viewers");
  const statUptimeEl = document.getElementById("stat-uptime");
  const statLoadEl = document.getElementById("stat-load");

  revealBtn.addEventListener("click", () => panel.classList.toggle("open"));

  // ---- live state, smoothed toward whatever the wire tells us ----------
  const state = { hue: 0.55, energy: 0.5, speed: 0.4 };
  const target = { ...state };

  function lerp(a, b, t) { return a + (b - a) * t; }

  // ---- viewers / machine stats, from periodic "meta" broadcasts --------
  function applyMeta(msg) {
    viewersBadge.textContent = msg.viewers === 1 ? "1 other here" : `${msg.viewers} others here`;
    statViewersEl.textContent = String(msg.viewers);
    statUptimeEl.textContent = formatUptime(msg.uptimeS);
    statLoadEl.textContent = msg.load1 == null ? "n/a" : msg.load1.toFixed(2);
  }

  function formatUptime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  }

  // ---- websocket, reconnects forever ------------------------------------
  function connect() {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws`);

    ws.onmessage = (evt) => {
      let msg;
      try { msg = JSON.parse(evt.data); } catch { return; }

      if (msg.kind === "pulse") {
        target.hue = msg.hue;
        target.energy = msg.energy;
        target.speed = msg.speed;
        if (msg.burst > 0.05) spawnRing(W / 2, H * 0.42, "wire");
      } else if (msg.kind === "packet") {
        logPacket(msg);
      } else if (msg.kind === "meta") {
        applyMeta(msg);
      }
    };

    ws.onclose = () => setTimeout(connect, 1500);
    ws.onerror = () => ws.close();
  }
  connect();

  function logPacket(msg) {
    const line = document.createElement("div");
    const t = new Date(msg.ts).toISOString().split("T")[1].replace("Z", "");
    line.textContent = `${t}  ${msg.src.padEnd(15)}  ${msg.hex.slice(0, 40)}`;
    log.appendChild(line);
    while (log.childElementCount > 60) log.removeChild(log.firstChild);
    log.scrollTop = log.scrollHeight;

    recordPacketStat(msg.ts);
  }

  // ---- live packet-rate stats, shown in the reveal panel -----------------
  let totalPackets = 0;
  let recentTimestamps = [];

  function recordPacketStat(ts) {
    totalPackets++;
    recentTimestamps.push(ts);
    const cutoff = ts - 1000;
    while (recentTimestamps.length && recentTimestamps[0] < cutoff) recentTimestamps.shift();

    statTotalEl.textContent = totalPackets.toLocaleString();
    statRateEl.textContent = String(recentTimestamps.length);
    statLastEl.textContent = new Date(ts).toLocaleTimeString();
  }

  // ---- canvas sizing -----------------------------------------------------
  let W = 0, H = 0, DPR = Math.min(window.devicePixelRatio || 1, 2);
  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * DPR;
    canvas.height = H * DPR;
    canvas.style.width = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  window.addEventListener("resize", resize);
  resize();

  // ---- color: hue channel walks a cyan <-> magenta <-> amber wheel ------
  function paletteColor(h, alpha) {
    const hue = 190 + h * 220; // cyan(190) through magenta(330) into amber-ish(410%360=50)
    return `hsla(${hue % 360}, 95%, 62%, ${alpha})`;
  }

  // ---- cheap layered-sine "noise" field for particle flow ----------------
  function fieldAngle(x, y, t) {
    return (
      Math.sin(x * 0.0016 + t * 0.09) +
      Math.sin(y * 0.0021 - t * 0.07) +
      Math.sin((x + y) * 0.0011 + t * 0.05)
    ) * Math.PI;
  }

  // ---- particles -----------------------------------------------------
  const N = 220;
  const particles = Array.from({ length: N }, () => spawn());
  function spawn() {
    return {
      x: Math.random() * innerWidth,
      y: Math.random() * innerHeight,
      life: Math.random(),
    };
  }

  // ---- interaction: click/tap anywhere to nudge the sender for real -----
  // Two rings appear per click: a faint one right away at the click point
  // (pure local feedback, no network involved), and - a beat later - a
  // brighter one from the center once the sender's inflated burst actually
  // makes its way back through the real ICMP round trip. The gap between
  // them is the point: one is instant because it's fake, one is delayed
  // because it's real.
  let lastNudgeAt = 0;
  const NUDGE_CLIENT_COOLDOWN_MS = 280;

  function nudge(x, y) {
    const now = performance.now();
    if (now - lastNudgeAt < NUDGE_CLIENT_COOLDOWN_MS) return;
    lastNudgeAt = now;

    spawnRing(x, y, "local");
    fetch("/nudge", { method: "POST" }).catch(() => {});
  }

  canvas.addEventListener("pointerdown", (e) => nudge(e.clientX, e.clientY));

  let t0 = performance.now();
  const rings = []; // { x, y, progress, kind: "wire" | "local" }

  function spawnRing(x, y, kind) {
    rings.push({ x, y, progress: 0, kind });
  }

  function frame(now) {
    const t = (now - t0) / 1000;
    const smooth = 0.04;
    state.hue = lerp(state.hue, target.hue, smooth);
    state.energy = lerp(state.energy, target.energy, smooth);
    state.speed = lerp(state.speed, target.speed, smooth);

    ctx.fillStyle = "rgba(5, 4, 10, 0.16)"; // trailing fade, not a hard clear
    ctx.fillRect(0, 0, W, H);

    drawHorizonGrid(t);
    drawParticles(t);
    drawRings();

    requestAnimationFrame(frame);
  }

  function drawHorizonGrid(t) {
    const horizonY = H * 0.66;
    const vanishX = W / 2;
    const speed = 0.4 + state.speed * 1.6;
    const color = paletteColor(state.hue, 0.28 + state.energy * 0.25);

    ctx.save();
    ctx.strokeStyle = color;
    ctx.lineWidth = 1;

    // horizontal receding lines
    const lines = 14;
    for (let i = 0; i < lines; i++) {
      const p = ((i / lines + t * speed * 0.05) % 1);
      const y = horizonY + Math.pow(p, 2.2) * (H - horizonY);
      const alpha = 0.35 * (1 - p);
      ctx.globalAlpha = alpha;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(W, y);
      ctx.stroke();
    }

    // converging verticals
    const verticals = 16;
    ctx.globalAlpha = 0.22;
    for (let i = 0; i <= verticals; i++) {
      const fx = (i / verticals) * W;
      ctx.beginPath();
      ctx.moveTo(fx, H);
      ctx.lineTo(vanishX, horizonY);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawParticles(t) {
    const speed = 0.3 + state.speed * 1.4;
    ctx.save();
    ctx.globalCompositeOperation = "lighter";

    for (const p of particles) {
      const angle = fieldAngle(p.x, p.y, t);
      p.x += Math.cos(angle) * speed;
      p.y += Math.sin(angle) * speed;
      p.life += 0.004 + state.energy * 0.01;

      if (p.life > 1 || p.x < -20 || p.x > innerWidth + 20 || p.y < -20 || p.y > innerHeight + 20) {
        Object.assign(p, spawn());
      }

      const alpha = 0.15 + state.energy * 0.5 * (1 - p.life);
      const r = 0.6 + state.energy * 1.8;
      ctx.fillStyle = paletteColor(state.hue + p.life * 0.15, alpha);
      ctx.beginPath();
      ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawRings() {
    for (let i = rings.length - 1; i >= 0; i--) {
      const r = rings[i];
      r.progress += r.kind === "local" ? 0.03 : 0.018;

      const maxRadius = Math.max(W, H) * (r.kind === "local" ? 0.35 : 0.7);
      const radius = r.progress * maxRadius;
      const baseAlpha = r.kind === "local" ? 0.35 : 0.5;
      const alpha = Math.max(0, baseAlpha * (1 - r.progress));

      ctx.save();
      ctx.strokeStyle = paletteColor(state.hue, alpha);
      ctx.lineWidth = r.kind === "local" ? 1 : 2;
      ctx.beginPath();
      ctx.arc(r.x, r.y, radius, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      if (r.progress >= 1) rings.splice(i, 1);
    }
  }

  requestAnimationFrame(frame);
})();
