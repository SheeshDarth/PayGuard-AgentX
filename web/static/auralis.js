/* Auralis — WebGL ambient background (layered simplex noise + glow + film grain).
   Ported from the React/TypeScript component to vanilla JS: the GLSL below is
   byte-identical to the original, and React contributed nothing but canvas
   lifecycle, which is ~20 lines here. Keeps the project's zero-dependency,
   no-build, offline guarantee intact.

   Usage:  const stop = mountAuralis(canvasEl, { colors, speed, grain });
           stop();   // tears down RAF, observer, GL program

   Degrades silently to the element's CSS background when WebGL is unavailable,
   when a shader fails to compile, or when the viewer prefers reduced motion. */

"use strict";

const AURALIS_VERT = `
attribute vec2 position;
varying vec2 vUv;
void main() {
  vUv = position * 0.5 + 0.5;
  gl_Position = vec4(position, 0.0, 1.0);
}
`;

const AURALIS_FRAG = `
precision highp float;
varying vec2 vUv;

uniform vec2  u_resolution;
uniform float u_time;
uniform float u_grain;
uniform vec3  u_colors[3];

vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec2 mod289(vec2 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec3 permute(vec3 x) { return mod289(((x*34.0)+1.0)*x); }

float snoise(vec2 v) {
  const vec4 C = vec4(0.211324865405187, 0.366025403784439, -0.577350269189626, 0.024390243902439);
  vec2 i  = floor(v + dot(v, C.yy));
  vec2 x0 = v - i + dot(i, C.xx);
  vec2 i1 = (x0.x > x0.y) ? vec2(1.0, 0.0) : vec2(0.0, 1.0);
  vec4 x12 = x0.xyxy + C.xxzz;
  x12.xy -= i1;
  i = mod289(i);
  vec3 p = permute(permute(i.y + vec3(0.0, i1.y, 1.0)) + i.x + vec3(0.0, i1.x, 1.0));
  vec3 m = max(0.5 - vec3(dot(x0,x0), dot(x12.xy,x12.xy), dot(x12.zw,x12.zw)), 0.0);
  m = m*m; m = m*m;
  vec3 x = 2.0 * fract(p * C.www) - 1.0;
  vec3 h = abs(x) - 0.5;
  vec3 ox = floor(x + 0.5);
  vec3 a0 = x - ox;
  m *= 1.79284291400159 - 0.85373472095314 * (a0*a0 + h*h);
  vec3 g;
  g.x  = a0.x  * x0.x  + h.x  * x0.y;
  g.yz = a0.yz * x12.xz + h.yz * x12.yw;
  return 130.0 * dot(m, g);
}

void main() {
  vec2 uv = vUv;
  float ratio = u_resolution.x / u_resolution.y;
  vec2 p = uv * vec2(ratio, 1.0);
  float t = u_time * 0.2;

  float n1 = snoise(p * 0.5 + t);
  float n2 = snoise(p * 0.9 - t * 0.5 + n1);

  float light = pow(abs(n2), 2.5) * 0.5;

  vec3 col = vec3(0.02, 0.01, 0.01);

  col += u_colors[0] * smoothstep(0.1, 1.0, n1) * 0.5;
  col += u_colors[1] * light;

  float grain = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453 + u_time);
  col += (grain - 0.5) * u_grain * 0.5;

  float dist = length(uv - 0.5);
  col *= smoothstep(1.2, 0.2, dist);

  gl_FragColor = vec4(col, 1.0);
}
`;

/* Signature palette. Violet reads as "premium instrument" and — unlike the
   component's stock red — collides with none of the severity colours, so the
   ambient chrome can never be mistaken for an alert state. */
const AURALIS_DEFAULT_COLORS = ["#6D4AFF", "#8B5CF6", "#4C1D95"];

function auralisHexToRgb(hex) {
  const h = String(hex).replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

function mountAuralis(canvas, options) {
  const opts = options || {};
  const colors = opts.colors || AURALIS_DEFAULT_COLORS;
  const speed = opts.speed === undefined ? 0.3 : opts.speed;
  const grain = opts.grain === undefined ? 0.6 : opts.grain;
  if (!canvas) return () => {};
  const container = canvas.parentElement;

  let gl = null;
  try {
    gl = canvas.getContext("webgl", { antialias: true, alpha: false })
      || canvas.getContext("experimental-webgl", { antialias: true });
  } catch (e) {
    gl = null;
  }
  // No WebGL (old browser, blocked GPU, headless): leave the CSS ground showing.
  if (!gl) return () => {};

  const createShader = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    // The original swallows compile errors and renders black; fail loudly to the
    // console instead and let the caller fall back to the CSS background.
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      console.warn("Auralis shader failed to compile:", gl.getShaderInfoLog(s));
      gl.deleteShader(s);
      return null;
    }
    return s;
  };

  const vs = createShader(gl.VERTEX_SHADER, AURALIS_VERT);
  const fs = createShader(gl.FRAGMENT_SHADER, AURALIS_FRAG);
  if (!vs || !fs) return () => {};

  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.warn("Auralis program failed to link:", gl.getProgramInfoLog(program));
    return () => {};
  }
  gl.useProgram(program);

  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER,
    new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

  const pos = gl.getAttribLocation(program, "position");
  gl.enableVertexAttribArray(pos);
  gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

  const locs = {
    res: gl.getUniformLocation(program, "u_resolution"),
    time: gl.getUniformLocation(program, "u_time"),
    grain: gl.getUniformLocation(program, "u_grain"),
    colors: gl.getUniformLocation(program, "u_colors"),
  };

  // Uniform colours never change after mount, so upload them once rather than
  // rebuilding a Float32Array on every one of 60 frames per second.
  const flat = new Float32Array(colors.slice(0, 3).flatMap(auralisHexToRgb));
  gl.uniform3fv(locs.colors, flat);
  gl.uniform1f(locs.grain, grain);

  const resize = () => {
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    // Measure the canvas itself; fall back to the parent only if CSS has not
    // given the canvas a box of its own yet.
    const rect = canvas.getBoundingClientRect();
    const cw = rect.width || (container ? container.clientWidth : 0);
    const ch = rect.height || (container ? container.clientHeight : 0);
    const w = Math.max(1, Math.floor(cw * dpr));
    const h = Math.max(1, Math.floor(ch * dpr));
    // Only the drawing buffer changes here, never the CSS box, so observing the
    // canvas cannot feed back into itself.
    if (canvas.width === w && canvas.height === h) return;
    canvas.width = w;
    canvas.height = h;
    gl.viewport(0, 0, w, h);
  };
  resize();

  let ro = null;
  if (typeof ResizeObserver !== "undefined") {
    ro = new ResizeObserver(resize);
    ro.observe(canvas);
  } else {
    window.addEventListener("resize", resize);
  }

  const reduced = window.matchMedia
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  let raf = 0;
  let running = true;
  const draw = (tMs) => {
    gl.uniform2f(locs.res, canvas.width, canvas.height);
    gl.uniform1f(locs.time, tMs * 0.001 * speed);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  };

  const loop = (t) => {
    if (!running) return;
    draw(t);
    raf = requestAnimationFrame(loop);
  };

  if (reduced) {
    // Honour the OS setting: paint one static frame, never animate.
    draw(0);
  } else {
    raf = requestAnimationFrame(loop);
  }

  // A GPU shader running behind a hidden tab is pure battery burn.
  const onVisibility = () => {
    if (reduced) return;
    if (document.hidden) {
      running = false;
      cancelAnimationFrame(raf);
    } else if (!running) {
      running = true;
      raf = requestAnimationFrame(loop);
    }
  };
  document.addEventListener("visibilitychange", onVisibility);

  return function stop() {
    running = false;
    cancelAnimationFrame(raf);
    document.removeEventListener("visibilitychange", onVisibility);
    if (ro) ro.disconnect(); else window.removeEventListener("resize", resize);
    gl.deleteProgram(program);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    gl.deleteBuffer(buffer);
  };
}
