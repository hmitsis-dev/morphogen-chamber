import { initGL, linkProgram, createQuad, bindQuad, createFloatFbo } from "./gl-utils.js";
import { VERTEX_SRC, STEP_SRC, RENDER_SRC } from "./shaders.js";

export const SIM = 256;
const STEPS_PER_FRAME = 16;

// Real named regions from the commonly-referenced Gray-Scott parameter
// map, not arbitrary points - each produces a visually distinct regime.
export const PRESETS = [
  { name: "Spots", F: 0.035, K: 0.065 },
  { name: "Coral", F: 0.058, K: 0.065 },
  { name: "Mitosis", F: 0.028, K: 0.062 },
  { name: "Worms", F: 0.078, K: 0.061 },
  { name: "Waves", F: 0.014, K: 0.045 },
  { name: "Solitons", F: 0.030, K: 0.057 },
  // F=0.04, K=0.06: the pair L.N. Trefethen uses in his Chebfun
  // Gray-Scott demo (reproduced in cselab/gray-scott) to show "rolls."
  // Same equations and the same Du:Dv=2:1 ratio as this file uses, on
  // a different non-dimensionalization - see README for the honest
  // caveat on why that means "analogous," not "pixel-identical."
  { name: "Rolls", F: 0.040, K: 0.060 },
];

function makeSeed() {
  const data = new Float32Array(SIM * SIM * 4);
  for (let i = 0; i < SIM * SIM; i++) {
    data[i * 4 + 0] = 1.0; // U
    data[i * 4 + 1] = 0.0; // V
    data[i * 4 + 2] = 0.0;
    data[i * 4 + 3] = 1.0;
  }
  const blobs = 5 + Math.floor(Math.random() * 4);
  for (let b = 0; b < blobs; b++) {
    const cx = Math.floor(SIM * (0.3 + Math.random() * 0.4));
    const cy = Math.floor(SIM * (0.3 + Math.random() * 0.4));
    const r = 4 + Math.floor(Math.random() * 5);
    for (let y = -r; y <= r; y++) {
      for (let x = -r; x <= r; x++) {
        if (x * x + y * y > r * r) continue;
        const px = ((cx + x) % SIM + SIM) % SIM;
        const py = ((cy + y) % SIM + SIM) % SIM;
        const idx = (py * SIM + px) * 4;
        data[idx + 0] = 0.5 + (Math.random() - 0.5) * 0.05;
        data[idx + 1] = 0.25 + (Math.random() - 0.5) * 0.05;
      }
    }
  }
  return data;
}

// The full engine: owns the GL context, both compiled programs, the
// ping-ponging simulation state, and drawing to the canvas. Everything
// Gray-Scott-specific lives here; gl-utils.js stays generic.
export class GrayScott {
  constructor(canvas) {
    const gl = initGL(canvas);
    this.gl = gl;
    this.canvas = canvas;

    this.stepProgram = linkProgram(gl, VERTEX_SRC, STEP_SRC);
    this.renderProgram = linkProgram(gl, VERTEX_SRC, RENDER_SRC);
    this.quad = createQuad(gl);

    this.stepU = {
      uState: gl.getUniformLocation(this.stepProgram, "uState"),
      uTexel: gl.getUniformLocation(this.stepProgram, "uTexel"),
      uF: gl.getUniformLocation(this.stepProgram, "uF"),
      uK: gl.getUniformLocation(this.stepProgram, "uK"),
      uDu: gl.getUniformLocation(this.stepProgram, "uDu"),
      uDv: gl.getUniformLocation(this.stepProgram, "uDv"),
      uDt: gl.getUniformLocation(this.stepProgram, "uDt"),
      uInjectPos: gl.getUniformLocation(this.stepProgram, "uInjectPos"),
      uInjectActive: gl.getUniformLocation(this.stepProgram, "uInjectActive"),
      uInjectRadius: gl.getUniformLocation(this.stepProgram, "uInjectRadius"),
    };
    this.renderU = {
      uState: gl.getUniformLocation(this.renderProgram, "uState"),
    };

    this.params = { F: 0.035, K: 0.062, Du: 1.0, Dv: 0.5, dt: 1.0 };
    this.inject = { active: false, x: 0.5, y: 0.5 };

    this.states = [createFloatFbo(gl, SIM), createFloatFbo(gl, SIM)];
    this.current = 0;
    this.reseed();
  }

  reseed() {
    const gl = this.gl;
    const data = makeSeed();
    for (const s of this.states) {
      gl.bindTexture(gl.TEXTURE_2D, s.tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, SIM, SIM, 0, gl.RGBA, gl.FLOAT, data);
    }
  }

  get texture() {
    return this.states[this.current].tex;
  }

  step() {
    const gl = this.gl;
    gl.viewport(0, 0, SIM, SIM);
    gl.useProgram(this.stepProgram);
    bindQuad(gl, this.quad, this.stepProgram);

    gl.uniform2f(this.stepU.uTexel, 1 / SIM, 1 / SIM);
    gl.uniform1f(this.stepU.uF, this.params.F);
    gl.uniform1f(this.stepU.uK, this.params.K);
    gl.uniform1f(this.stepU.uDu, this.params.Du);
    gl.uniform1f(this.stepU.uDv, this.params.Dv);
    gl.uniform1f(this.stepU.uDt, this.params.dt);
    gl.uniform1f(this.stepU.uInjectActive, this.inject.active ? 1.0 : 0.0);
    gl.uniform2f(this.stepU.uInjectPos, this.inject.x, this.inject.y);
    gl.uniform1f(this.stepU.uInjectRadius, 0.02);
    gl.activeTexture(gl.TEXTURE0);
    gl.uniform1i(this.stepU.uState, 0);

    for (let i = 0; i < STEPS_PER_FRAME; i++) {
      const from = this.states[this.current];
      const to = this.states[1 - this.current];
      gl.bindFramebuffer(gl.FRAMEBUFFER, to.fbo);
      gl.bindTexture(gl.TEXTURE_2D, from.tex);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      this.current = 1 - this.current;
    }
  }

  render() {
    const gl = this.gl;
    const canvas = this.canvas;
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);

    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.round(canvas.clientWidth * dpr);
    const h = Math.round(canvas.clientHeight * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }

    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.useProgram(this.renderProgram);
    bindQuad(gl, this.quad, this.renderProgram);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    gl.uniform1i(this.renderU.uState, 0);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
}
