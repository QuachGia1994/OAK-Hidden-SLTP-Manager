"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

type ToolKind = "factcheck" | "tarot" | "discover";

type ToolView = {
  kind: ToolKind;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  root: THREE.Group;
  animate?: (seconds: number) => void;
};

const TOOL_KINDS: ToolKind[] = ["factcheck", "tarot", "discover"];

function makeMaterial(color: THREE.Color, opacity = 1, wireframe = false) {
  return new THREE.MeshBasicMaterial({
    color,
    transparent: opacity < 1,
    opacity,
    wireframe,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
}

function buildView(kind: ToolKind, accent: THREE.Color, strong: THREE.Color): ToolView {
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 30);
  camera.position.z = 5.2;
  const root = new THREE.Group();
  scene.add(root);
  let animate: ToolView["animate"];

  if (kind === "factcheck") {
    const outer = new THREE.Mesh(new THREE.TorusGeometry(1.32, 0.045, 8, 96), makeMaterial(accent, 0.62, true));
    const inner = new THREE.Mesh(new THREE.TorusGeometry(0.82, 0.012, 4, 72), makeMaterial(strong, 0.3));
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(1.05, 1.35, 4, 5), makeMaterial(accent, 0.17, true));
    plane.position.z = -0.22;
    plane.rotation.z = -0.16;
    root.add(outer, inner, plane);
  }

  if (kind === "tarot") {
    const cardMaterial = makeMaterial(accent, 0.36, true);
    [-0.5, 0, 0.5].forEach((x, index) => {
      const card = new THREE.Mesh(new THREE.BoxGeometry(1.02, 1.55, 0.05), cardMaterial);
      card.position.set(x, index === 1 ? 0.14 : -0.02, index === 1 ? 0.16 : 0);
      card.rotation.z = (index - 1) * 0.2;
      card.rotation.y = (index - 1) * -0.13;
      root.add(card);
    });
    const halo = new THREE.Mesh(new THREE.TorusGeometry(1.55, 0.009, 4, 90), makeMaterial(strong, 0.22));
    halo.rotation.x = 1.2;
    root.add(halo);
  }

  if (kind === "discover") {
    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.45, 1), makeMaterial(strong, 0.5, true));
    root.add(core);
    const orbit = new THREE.Mesh(new THREE.TorusGeometry(1.7, 0.009, 4, 100), makeMaterial(accent, 0.24));
    orbit.rotation.set(0.65, 0.35, 0.22);
    root.add(orbit);
    const nodes: THREE.Mesh[] = [];
    for (let index = 0; index < 5; index += 1) {
      const angle = -Math.PI / 2 + index / 5 * Math.PI * 2;
      const node = new THREE.Mesh(new THREE.OctahedronGeometry(0.13, 1), makeMaterial(accent, 0.82));
      node.position.set(Math.cos(angle) * 1.7, Math.sin(angle) * 1.7, 0);
      orbit.add(node);
      nodes.push(node);
    }
    animate = (seconds) => {
      nodes.forEach((node, index) => {
        const angle = -Math.PI / 2 + index / nodes.length * Math.PI * 2 + seconds * 0.12;
        node.position.set(Math.cos(angle) * 1.7, Math.sin(angle) * 1.7, 0);
      });
    };
  }

  return { kind, scene, camera, root, animate };
}

function disposeView(view: ToolView) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  view.scene.traverse((object) => {
    const mesh = object as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry as THREE.BufferGeometry);
    const material = mesh.material;
    if (Array.isArray(material)) material.forEach((item) => materials.add(item));
    else if (material) materials.add(material);
  });
  geometries.forEach((geometry) => geometry.dispose());
  materials.forEach((material) => material.dispose());
}

export function ToolsThreeStage({ className = "" }: { className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const directory = canvas?.parentElement;
    if (!canvas || !directory) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    let renderer: THREE.WebGLRenderer;

    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: !coarse,
        powerPreference: "low-power",
      });
    } catch {
      directory.dataset.threeState = "fallback";
      return;
    }

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.1 : 1.5));
    renderer.setScissorTest(true);
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const style = getComputedStyle(directory);
    const accent = new THREE.Color(style.getPropertyValue("--tools-accent").trim() || "#84e5c2");
    const strong = new THREE.Color(style.getPropertyValue("--tools-accent-strong").trim() || "#b0f7d9");
    const views = TOOL_KINDS.map((kind) => buildView(kind, accent, strong));
    const slots = new Map<ToolKind, HTMLElement>();
    const rects = new Map<ToolKind, { x: number; y: number; width: number; height: number }>();
    let hovered: ToolKind | null = null;
    let visible = true;
    let frame = 0;
    let animationStart: number | null = null;
    let lastSeconds = 0;
    const motion = new Map(TOOL_KINDS.map((kind) => [kind, {
      spin: 0,
      hover: 0,
      x: 0,
      y: 0,
      targetX: 0,
      targetY: 0,
    }]));

    for (const kind of TOOL_KINDS) {
      const slot = directory.querySelector<HTMLElement>('[data-three-tool="' + kind + '"]');
      if (slot) slots.set(kind, slot);
    }

    const measure = () => {
      const parentRect = directory.getBoundingClientRect();
      const width = Math.max(1, Math.floor(parentRect.width));
      const height = Math.max(1, Math.floor(parentRect.height));
      renderer.setSize(width, height, false);
      rects.clear();

      slots.forEach((slot, kind) => {
        const rect = slot.getBoundingClientRect();
        rects.set(kind, {
          x: Math.max(0, rect.left - parentRect.left),
          y: Math.max(0, parentRect.bottom - rect.bottom),
          width: Math.max(1, rect.width),
          height: Math.max(1, rect.height),
        });
      });
    };

    const render = (time = 0) => {
      renderer.setScissorTest(false);
      renderer.clear();
      renderer.setScissorTest(true);
      const seconds = time * 0.001;
      const delta = lastSeconds ? Math.min(0.05, Math.max(0, seconds - lastSeconds)) : 0;
      lastSeconds = seconds;

      for (const view of views) {
        const rect = rects.get(view.kind);
        if (!rect) continue;
        const active = hovered === view.kind;
        if (!reduced) {
          view.animate?.(seconds);
          const state = motion.get(view.kind);
          if (state) {
            state.hover += ((active ? 1 : 0) - state.hover) * 0.09;
            state.x += (state.targetX - state.x) * 0.08;
            state.y += (state.targetY - state.y) * 0.08;
            state.spin += delta * (0.13 + state.hover * 0.21);
            view.root.rotation.y = state.spin + state.x * 0.22 * state.hover;
            view.root.rotation.x = Math.sin(seconds * 0.55) * (0.045 + state.hover * 0.075) - state.y * 0.16 * state.hover;
            view.root.rotation.z = state.x * 0.06 * state.hover;
            view.root.position.z = state.hover * 0.14;
            view.root.scale.setScalar(1 + state.hover * 0.1);
          }
        }
        view.camera.aspect = rect.width / rect.height;
        view.camera.updateProjectionMatrix();
        renderer.setViewport(rect.x, rect.y, rect.width, rect.height);
        renderer.setScissor(rect.x, rect.y, rect.width, rect.height);
        renderer.render(view.scene, view.camera);
      }
    };

    const loop = (time: number) => {
      frame = 0;
      if (!visible || document.hidden) return;
      if (animationStart === null) animationStart = time;
      render(time - animationStart);
      frame = window.requestAnimationFrame(loop);
    };
    const start = () => {
      if (reduced || frame || !visible || document.hidden) return;
      frame = window.requestAnimationFrame(loop);
    };
    const stop = () => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
    };

    const cleanups: Array<() => void> = [];
    slots.forEach((slot, kind) => {
      const enter = () => { hovered = kind; if (reduced) render(0); };
      const move = (event: PointerEvent) => {
        const state = motion.get(kind);
        if (!state) return;
        const rect = slot.getBoundingClientRect();
        state.targetX = ((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2;
        state.targetY = ((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * 2;
      };
      const leave = () => {
        if (hovered === kind) hovered = null;
        const state = motion.get(kind);
        if (state) { state.targetX = 0; state.targetY = 0; }
        if (reduced) render(0);
      };
      if (!coarse) {
        slot.addEventListener("pointerenter", enter);
        slot.addEventListener("pointermove", move, { passive: true });
        slot.addEventListener("pointerleave", leave);
        cleanups.push(() => {
          slot.removeEventListener("pointerenter", enter);
          slot.removeEventListener("pointermove", move);
          slot.removeEventListener("pointerleave", leave);
        });
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      measure();
      if (reduced) render(0);
    });
    resizeObserver.observe(directory);
    slots.forEach((slot) => resizeObserver.observe(slot));

    const intersectionObserver = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true;
      if (visible) start();
      else stop();
    }, { threshold: 0.02 });
    intersectionObserver.observe(directory);

    const onVisibility = () => document.hidden ? stop() : start();
    const onContextLost = () => {
      stop();
      directory.dataset.threeState = "fallback";
    };
    document.addEventListener("visibilitychange", onVisibility);
    canvas.addEventListener("webglcontextlost", onContextLost);

    measure();
    render(0);
    directory.dataset.threeState = "ready";
    if (!reduced) start();

    return () => {
      stop();
      cleanups.forEach((cleanup) => cleanup());
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      views.forEach(disposeView);
      renderer.dispose();
    };
  }, []);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
