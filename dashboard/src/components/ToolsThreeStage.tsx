"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

type ToolKind = "factcheck" | "tarot" | "discover";

type ToolView = {
  kind: ToolKind;
  scene: THREE.Scene;
  camera: THREE.PerspectiveCamera;
  root: THREE.Group;
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

function makeLineMaterial(color: THREE.Color, opacity = 1) {
  return new THREE.LineBasicMaterial({
    color,
    transparent: opacity < 1,
    opacity,
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
    const lineMaterial = makeLineMaterial(accent, 0.2);
    for (let index = 0; index < 5; index += 1) {
      const angle = -Math.PI / 2 + index / 5 * Math.PI * 2;
      const target = new THREE.Vector3(Math.cos(angle) * 1.45, Math.sin(angle) * 1.05, Math.sin(angle * 1.5) * 0.35);
      const node = new THREE.Mesh(new THREE.OctahedronGeometry(0.13, 1), makeMaterial(accent, 0.82));
      node.position.copy(target);
      root.add(node);
      root.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), target]), lineMaterial));
    }
    const orbit = new THREE.Mesh(new THREE.TorusGeometry(1.7, 0.009, 4, 100), makeMaterial(accent, 0.2));
    orbit.rotation.set(0.65, 0.35, 0.22);
    root.add(orbit);
  }

  return { kind, scene, camera, root };
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

      for (const view of views) {
        const rect = rects.get(view.kind);
        if (!rect) continue;
        const active = hovered === view.kind;
        if (!reduced) {
          view.root.rotation.y = seconds * (active ? 0.34 : 0.13);
          view.root.rotation.x = Math.sin(seconds * 0.55) * (active ? 0.12 : 0.045);
          const scale = view.root.scale.x + ((active ? 1.13 : 1) - view.root.scale.x) * 0.08;
          view.root.scale.setScalar(scale);
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
      render(time);
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
      const leave = () => { if (hovered === kind) hovered = null; if (reduced) render(0); };
      if (!coarse) {
        slot.addEventListener("pointerenter", enter);
        slot.addEventListener("pointerleave", leave);
        cleanups.push(() => {
          slot.removeEventListener("pointerenter", enter);
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
