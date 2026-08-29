"use client";

import { useEffect, useRef } from "react";

const PARTICLE_COUNT = 180;
const STATIC_PARTICLE_COUNT = 80;

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("WebGL shader allocation failed");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const info = gl.getShaderInfoLog(shader) || "unknown shader error";
    gl.deleteShader(shader);
    throw new Error(info);
  }
  return shader;
}

function createProgram(gl: WebGLRenderingContext): WebGLProgram {
  const vertex = compileShader(gl, gl.VERTEX_SHADER, `
    precision mediump float;
    attribute vec3 a_position;
    attribute float a_seed;
    uniform float u_time;
    uniform vec2 u_pointer;
    uniform vec2 u_resolution;
    varying float v_alpha;

    void main() {
      vec3 p = a_position;
      float wave = sin(u_time * 0.00022 + a_seed * 6.2831) * 0.025;
      float drift = cos(u_time * 0.00016 + a_seed * 4.1) * 0.018;
      p.x += wave + (u_pointer.x - 0.5) * 0.055 * (1.0 - p.z);
      p.y += drift - (u_pointer.y - 0.5) * 0.035 * (1.0 - p.z);
      float perspective = 1.0 / (1.22 + p.z * 0.72);
      vec2 projected = p.xy * perspective;
      projected.x *= u_resolution.y / max(u_resolution.x, 1.0);
      gl_Position = vec4(projected, 0.0, 1.0);
      gl_PointSize = mix(1.2, 3.6, 1.0 - p.z) * perspective;
      v_alpha = mix(0.12, 0.54, 1.0 - p.z);
    }
  `);
  const fragment = compileShader(gl, gl.FRAGMENT_SHADER, `
    precision mediump float;
    varying float v_alpha;

    void main() {
      vec2 uv = gl_PointCoord - vec2(0.5);
      float core = 1.0 - smoothstep(0.0, 0.5, length(uv));
      gl_FragColor = vec4(0.30, 0.62, 1.0, core * v_alpha);
    }
  `);
  const program = gl.createProgram();
  if (!program) throw new Error("WebGL program allocation failed");
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const info = gl.getProgramInfoLog(program) || "unknown program error";
    gl.deleteProgram(program);
    throw new Error(info);
  }
  return program;
}

function createParticles(count: number): Float32Array {
  const values = new Float32Array(count * 4);
  for (let index = 0; index < count; index += 1) {
    const i = index * 4;
    const ring = index / count;
    const angle = index * 2.399963229728653;
    const radius = 0.16 + Math.sqrt(ring) * 1.18;
    values[i] = Math.cos(angle) * radius;
    values[i + 1] = Math.sin(angle) * radius * 0.62 - 0.02;
    values[i + 2] = (index % 37) / 37;
    values[i + 3] = (index * 17 % count) / count;
  }
  return values;
}

export function SpatialHudCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const root = document.documentElement;
    let pointerFrame = 0;
    let pointerX = window.innerWidth / 2;
    let pointerY = window.innerHeight / 2;
    let targetX = pointerX;
    let targetY = pointerY;

    const syncPointerVars = () => {
      pointerFrame = 0;
      pointerX += (targetX - pointerX) * 0.18;
      pointerY += (targetY - pointerY) * 0.18;
      root.style.setProperty("--hud-pointer-x", `${pointerX}px`);
      root.style.setProperty("--hud-pointer-y", `${pointerY}px`);
      root.style.setProperty("--hud-pointer-nx", `${Math.max(0, Math.min(1, pointerX / Math.max(window.innerWidth, 1))).toFixed(4)}`);
      root.style.setProperty("--hud-pointer-ny", `${Math.max(0, Math.min(1, pointerY / Math.max(window.innerHeight, 1))).toFixed(4)}`);
    };

    const onPointerMove = (event: PointerEvent) => {
      targetX = event.clientX;
      targetY = event.clientY;
      if (!pointerFrame) pointerFrame = window.requestAnimationFrame(syncPointerVars);
    };

    window.addEventListener("pointermove", onPointerMove, { passive: true });
    syncPointerVars();

    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      if (pointerFrame) window.cancelAnimationFrame(pointerFrame);
    };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const android = document.documentElement.classList.contains("oak-android");
    const gl = canvas.getContext("webgl", {
      alpha: true,
      antialias: false,
      depth: false,
      powerPreference: "low-power",
      preserveDrawingBuffer: false,
    });

    if (!gl) {
      canvas.dataset.fallback = "true";
      return;
    }

    let frame = 0;
    let width = 0;
    let height = 0;
    let running = false;
    let disposed = false;
    const program = createProgram(gl);
    const buffer = gl.createBuffer();
    if (!buffer) return;
    const particles = createParticles(reduced || coarse || android ? STATIC_PARTICLE_COUNT : PARTICLE_COUNT);
    const positionLocation = gl.getAttribLocation(program, "a_position");
    const seedLocation = gl.getAttribLocation(program, "a_seed");
    const timeLocation = gl.getUniformLocation(program, "u_time");
    const pointerLocation = gl.getUniformLocation(program, "u_pointer");
    const resolutionLocation = gl.getUniformLocation(program, "u_resolution");

    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, particles, gl.STATIC_DRAW);
    gl.useProgram(program);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE);

    const resize = () => {
      const ratio = Math.min(window.devicePixelRatio || 1, coarse || android ? 1.25 : 1.75);
      width = Math.max(1, Math.floor(window.innerWidth * ratio));
      height = Math.max(1, Math.floor(window.innerHeight * ratio));
      canvas.width = width;
      canvas.height = height;
      gl.viewport(0, 0, width, height);
    };

    const render = (time: number) => {
      if (disposed || !running) return;
      const pointerX = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--hud-pointer-nx")) || 0.5;
      const pointerY = Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--hud-pointer-ny")) || 0.5;
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(program);
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.enableVertexAttribArray(positionLocation);
      gl.vertexAttribPointer(positionLocation, 3, gl.FLOAT, false, 16, 0);
      gl.enableVertexAttribArray(seedLocation);
      gl.vertexAttribPointer(seedLocation, 1, gl.FLOAT, false, 16, 12);
      gl.uniform1f(timeLocation, reduced ? 0 : time);
      gl.uniform2f(pointerLocation, pointerX, pointerY);
      gl.uniform2f(resolutionLocation, width, height);
      gl.drawArrays(gl.POINTS, 0, particles.length / 4);
      if (!reduced && !coarse && !android) frame = window.requestAnimationFrame(render);
    };

    const start = () => {
      if (running || disposed) return;
      running = true;
      frame = window.requestAnimationFrame(render);
    };

    const stop = () => {
      running = false;
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
    };

    const onVisibility = () => {
      if (document.hidden) stop();
      else start();
    };

    resize();
    window.addEventListener("resize", resize, { passive: true });
    document.addEventListener("visibilitychange", onVisibility);
    start();

    return () => {
      disposed = true;
      stop();
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
    };
  }, []);

  return (
    <div className="oak-spatial-stage" aria-hidden="true">
      <canvas ref={canvasRef} id="oak-hud-spatial-canvas" className="oak-spatial-canvas" />
      <div className="oak-spatial-grid" />
      <div className="oak-spatial-vignette" />
      <div className="oak-spatial-grain" />
    </div>
  );
}
