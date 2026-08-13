// GLSL ES 3.00 sources for the Gray-Scott simulation and its display.
// Kept as template strings rather than separate .glsl files fetched at
// runtime - this stays correct whether the page is opened directly or
// served over HTTP, with no extra async loading step or build tool.

export const VERTEX_SRC = `#version 300 es
  in vec2 aPos;
  out vec2 vUv;
  void main() {
    vUv = aPos * 0.5 + 0.5;
    gl_Position = vec4(aPos, 0.0, 1.0);
  }
`;

// One simulation step: a nine-point discrete Laplacian for diffusion,
// then the Gray-Scott reaction term, plus optional pointer injection.
export const STEP_SRC = `#version 300 es
  precision highp float;
  in vec2 vUv;
  out vec4 outColor;

  uniform sampler2D uState;
  uniform vec2 uTexel;
  uniform float uF;
  uniform float uK;
  uniform float uDu;
  uniform float uDv;
  uniform float uDt;
  uniform vec2 uInjectPos;
  uniform float uInjectActive;
  uniform float uInjectRadius;

  void main() {
    vec2 c  = texture(uState, vUv).rg;
    vec2 n  = texture(uState, vUv + vec2(0.0,  uTexel.y)).rg;
    vec2 s  = texture(uState, vUv - vec2(0.0,  uTexel.y)).rg;
    vec2 e  = texture(uState, vUv + vec2(uTexel.x, 0.0)).rg;
    vec2 w  = texture(uState, vUv - vec2(uTexel.x, 0.0)).rg;
    vec2 ne = texture(uState, vUv + vec2(uTexel.x,  uTexel.y)).rg;
    vec2 nw = texture(uState, vUv + vec2(-uTexel.x, uTexel.y)).rg;
    vec2 se = texture(uState, vUv + vec2(uTexel.x, -uTexel.y)).rg;
    vec2 sw = texture(uState, vUv + vec2(-uTexel.x, -uTexel.y)).rg;

    vec2 lap = (n + s + e + w) * 0.2
             + (ne + nw + se + sw) * 0.05
             - c;

    float u = c.r;
    float v = c.g;
    float uvv = u * v * v;

    float du = uDu * lap.r - uvv + uF * (1.0 - u);
    float dv = uDv * lap.g + uvv - (uF + uK) * v;

    u += du * uDt;
    v += dv * uDt;

    if (uInjectActive > 0.5) {
      float d = distance(vUv, uInjectPos);
      float bump = smoothstep(uInjectRadius, 0.0, d);
      v = clamp(v + bump * 0.9, 0.0, 1.0);
      u = clamp(u - bump * 0.3, 0.0, 1.0);
    }

    outColor = vec4(clamp(u, 0.0, 1.0), clamp(v, 0.0, 1.0), 0.0, 1.0);
  }
`;

// Maps the V-channel concentration through a four-stop gradient
// (void -> indigo -> teal -> warm gold) for display.
export const RENDER_SRC = `#version 300 es
  precision highp float;
  in vec2 vUv;
  out vec4 outColor;
  uniform sampler2D uState;

  vec3 palette(float t) {
    vec3 c0 = vec3(0.035, 0.045, 0.07);
    vec3 c1 = vec3(0.16, 0.10, 0.32);
    vec3 c2 = vec3(0.09, 0.55, 0.52);
    vec3 c3 = vec3(0.95, 0.85, 0.55);
    vec3 a = mix(c0, c1, smoothstep(0.0, 0.38, t));
    vec3 b = mix(a, c2, smoothstep(0.30, 0.68, t));
    return mix(b, c3, smoothstep(0.62, 1.0, t));
  }

  void main() {
    vec2 uv = texture(uState, vUv).rg;
    float t = clamp((uv.g - 0.02) * 2.6, 0.0, 1.0);
    outColor = vec4(palette(t), 1.0);
  }
`;
