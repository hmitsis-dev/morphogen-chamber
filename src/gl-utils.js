// Generic WebGL2 helpers - nothing here knows about Gray-Scott
// specifically. Reusable as-is for any GPU ping-pong simulation
// (Conway's Game of Life, fluid sim, flocking, ...).

export function initGL(canvas) {
  const gl = canvas.getContext("webgl2", { antialias: false, preserveDrawingBuffer: false });
  if (!gl) throw new Error("This needs WebGL2, which this browser doesn't expose.");

  const floatExt = gl.getExtension("EXT_color_buffer_float");
  if (!floatExt) throw new Error("This needs floating-point render targets (EXT_color_buffer_float), which this browser doesn't expose.");

  return gl;
}

export function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(shader);
    gl.deleteShader(shader);
    throw new Error("Shader failed to compile: " + log);
  }
  return shader;
}

export function linkProgram(gl, vsSource, fsSource) {
  const program = gl.createProgram();
  gl.attachShader(program, compileShader(gl, gl.VERTEX_SHADER, vsSource));
  gl.attachShader(program, compileShader(gl, gl.FRAGMENT_SHADER, fsSource));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error("Program failed to link: " + gl.getProgramInfoLog(program));
  }
  return program;
}

// A single full-screen quad, shared by every program that draws one.
export function createQuad(gl) {
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
  return buffer;
}

export function bindQuad(gl, buffer, program, attribName = "aPos") {
  const loc = gl.getAttribLocation(program, attribName);
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.enableVertexAttribArray(loc);
  gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
}

// A square floating-point (RGBA16F) render target with wrapped,
// linearly-filtered sampling - suited to toroidal grid simulations.
export function createFloatFbo(gl, size) {
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, size, size, 0, gl.RGBA, gl.HALF_FLOAT, null);

  const fbo = gl.createFramebuffer();
  gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  const status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null);
  if (status !== gl.FRAMEBUFFER_COMPLETE) {
    throw new Error("Render target isn't supported on this device (status " + status + ").");
  }
  return { fbo, tex };
}
