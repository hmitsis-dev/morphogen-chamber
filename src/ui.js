import { PRESETS } from "./gray-scott.js";
import { analyze } from "./stability.js";

// Wires the control rail (sliders, presets, reseed) and pointer
// injection to a live GrayScott instance. Knows about the DOM;
// gray-scott.js never does.
export function setupUI(sim, canvas) {
  const feedSlider = document.getElementById("feed");
  const killSlider = document.getElementById("kill");
  const feedVal = document.getElementById("feedVal");
  const killVal = document.getElementById("killVal");
  const presetsEl = document.getElementById("presets");
  const reseedBtn = document.getElementById("reseed");
  const stabilityTrivial = document.getElementById("stability-trivial");
  const stabilityNontrivial = document.getElementById("stability-nontrivial");

  function syncReadouts() {
    feedVal.textContent = sim.params.F.toFixed(4);
    killVal.textContent = sim.params.K.toFixed(4);
    syncStability();
  }

  function syncStability() {
    const a = analyze(sim.params.F, sim.params.K);
    // a.trivialStable is provably true for every F,K > 0 - see stability.js -
    // so this is reported, not branched on.
    stabilityTrivial.innerHTML =
      `(1,0): <span class="accent">stable</span> to every wavenumber ` +
      `(&lambda;=&minus;F, &minus;(F+K)) &mdash; no pattern grows from noise here.`;

    if (a.nontrivialExists && a.nontrivial) {
      const [r1, r2] = a.nontrivial.roots;
      stabilityNontrivial.innerHTML =
        `Nontrivial state: <span class="accent">exists</span> ` +
        `(v=${r1.v.toFixed(3)} or v=${r2.v.toFixed(3)})`;
    } else {
      stabilityNontrivial.innerHTML =
        `Nontrivial state: <span class="accent">none</span> ` +
        `(margin ${a.existenceMargin.toFixed(4)}) &mdash; pattern here is ` +
        `finite-amplitude, not a small-noise instability.`;
    }
  }

  function clearActivePreset() {
    for (const btn of presetsEl.children) btn.classList.remove("active");
  }

  feedSlider.addEventListener("input", () => {
    sim.params.F = parseFloat(feedSlider.value);
    syncReadouts();
    clearActivePreset();
  });
  killSlider.addEventListener("input", () => {
    sim.params.K = parseFloat(killSlider.value);
    syncReadouts();
    clearActivePreset();
  });

  PRESETS.forEach((preset) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = preset.name;
    btn.addEventListener("click", () => {
      sim.params.F = preset.F;
      sim.params.K = preset.K;
      feedSlider.value = String(preset.F);
      killSlider.value = String(preset.K);
      syncReadouts();
      clearActivePreset();
      btn.classList.add("active");
      sim.reseed();
    });
    presetsEl.appendChild(btn);
  });

  reseedBtn.addEventListener("click", () => sim.reseed());

  function pointerToUv(evt) {
    const rect = canvas.getBoundingClientRect();
    const x = (evt.clientX - rect.left) / rect.width;
    const y = 1.0 - (evt.clientY - rect.top) / rect.height;
    return [x, y];
  }
  canvas.addEventListener("pointerdown", (e) => {
    sim.inject.active = true;
    [sim.inject.x, sim.inject.y] = pointerToUv(e);
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener("pointermove", (e) => {
    if (!sim.inject.active) return;
    [sim.inject.x, sim.inject.y] = pointerToUv(e);
  });
  window.addEventListener("pointerup", () => { sim.inject.active = false; });

  syncReadouts();
}
