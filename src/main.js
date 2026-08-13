import { GrayScott } from "./gray-scott.js";
import { setupUI } from "./ui.js";

const canvas = document.getElementById("gl");
const fallback = document.getElementById("fallback");

function showFallback(message) {
  canvas.style.display = "none";
  fallback.style.display = "block";
  fallback.textContent = message;
}

let sim;
try {
  sim = new GrayScott(canvas);
} catch (err) {
  showFallback(err.message);
  throw err;
}

setupUI(sim, canvas);

function frame() {
  sim.step();
  sim.render();
  requestAnimationFrame(frame);
}
requestAnimationFrame(frame);
