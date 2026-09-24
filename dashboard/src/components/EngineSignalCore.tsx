"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitBrandMark } from "@/components/OrbitBrandMark";

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";
const COARSE_POINTER_QUERY = "(pointer: coarse)";

function readThemeColor(element: HTMLElement, token: string, fallback: string) {
  const value = getComputedStyle(element).getPropertyValue(token).trim();
  return value || fallback;
}

export function EngineSignalCore({ label = "H1", showGrid = false }: { label?: string; showGrid?: boolean }) {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    if (!stage || !canvas) return;

    const reduced = window.matchMedia(REDUCED_MOTION_QUERY).matches;
    const coarse = window.matchMedia(COARSE_POINTER_QUERY).matches;
    let renderer: THREE.WebGLRenderer;

    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: !coarse,
        powerPreference: "low-power",
        preserveDrawingBuffer: false,
      });
    } catch {
      stage.dataset.webgl = "fallback";
      return;
    }

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.25 : 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 50);
    camera.position.set(0, 0.1, 7.5);

    const root = new THREE.Group();
    root.rotation.set(-0.12, 0.18, -0.08);
    scene.add(root);

    const coreMaterial = new THREE.MeshBasicMaterial({
      wireframe: true,
      transparent: true,
      opacity: 0.62,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const cageMaterial = new THREE.LineBasicMaterial({
      transparent: true,
      opacity: 0.24,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const ringMaterials: THREE.MeshBasicMaterial[] = [];
    const nodeMaterial = new THREE.MeshBasicMaterial({
      transparent: true,
      opacity: 0.95,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const lineMaterial = new THREE.LineBasicMaterial({
      transparent: true,
      opacity: 0.14,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const pulseMaterial = new THREE.MeshBasicMaterial({
      wireframe: true,
      transparent: true,
      opacity: 0.06,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const starMaterial = new THREE.PointsMaterial({
      size: coarse ? 0.022 : 0.028,
      transparent: true,
      opacity: 0.34,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });

    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(1.06, 2), coreMaterial);
    root.add(core);

    const cageSource = new THREE.DodecahedronGeometry(1.42, 0);
    const cageEdges = new THREE.EdgesGeometry(cageSource);
    cageSource.dispose();
    const cage = new THREE.LineSegments(cageEdges, cageMaterial);
    root.add(cage);

    const nodeGeometry = new THREE.SphereGeometry(0.052, 10, 8);

    const makeOrbit = (radius: number, rotation: [number, number, number], nodeCount: number, opacity: number) => {
      const group = new THREE.Group();
      group.rotation.set(...rotation);
      const material = new THREE.MeshBasicMaterial({
        transparent: true,
        opacity,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      ringMaterials.push(material);
      group.add(new THREE.Mesh(new THREE.TorusGeometry(radius, 0.009, 4, coarse ? 96 : 160), material));
      for (let index = 0; index < nodeCount; index += 1) {
        const angle = (index / nodeCount) * Math.PI * 2 + index * 0.7;
        const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
        node.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, 0);
        group.add(node);
      }
      root.add(group);
      return group;
    };

    const orbitA = makeOrbit(2.04, [1.08, 0.02, 0.16], 4, 0.42);
    const orbitB = makeOrbit(1.82, [0.25, 1.18, -0.2], 3, 0.28);
    const orbitC = makeOrbit(2.22, [0.62, 0.74, 0.7], 5, 0.2);

    const pulse = new THREE.Mesh(new THREE.SphereGeometry(1.62, coarse ? 16 : 24, coarse ? 12 : 16), pulseMaterial);
    root.add(pulse);

    const anchors = [
      new THREE.Vector3(-2.22, 1.04, -0.25),
      new THREE.Vector3(2.32, 0.8, 0.25),
      new THREE.Vector3(1.78, -1.52, -0.5),
      new THREE.Vector3(-1.62, -1.48, 0.35),
    ];
    for (const target of anchors) {
      root.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), target]),
        lineMaterial,
      ));
      const dot = new THREE.Mesh(nodeGeometry, nodeMaterial);
      dot.position.copy(target);
      root.add(dot);
    }

    const starCount = coarse ? 70 : 150;
    const starPositions = new Float32Array(starCount * 3);
    for (let index = 0; index < starCount; index += 1) {
      const progress = index / starCount;
      const angle = index * 2.399963229728653;
      const radius = 2.55 + Math.sqrt(progress) * 3.2;
      starPositions[index * 3] = Math.cos(angle) * radius;
      starPositions[index * 3 + 1] = Math.sin(angle * 1.17) * 2.6;
      starPositions[index * 3 + 2] = -2.7 + (index % 19) * 0.18;
    }
    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const stars = new THREE.Points(starGeometry, starMaterial);
    root.add(stars);

    const grid = new THREE.GridHelper(11, coarse ? 14 : 22);
    grid.position.set(0, -2.22, -1.2);
    grid.rotation.z = -0.05;
    const gridMaterials = Array.isArray(grid.material) ? grid.material : [grid.material];
    for (const material of gridMaterials) {
      material.transparent = true;
      material.opacity = showGrid ? 0.22 : 0.11;
      material.depthWrite = false;
    }
    scene.add(grid);

    const applyTheme = () => {
      const accent = readThemeColor(stage, "--engine-accent", "#84e5c2");
      const strong = readThemeColor(stage, "--engine-accent-strong", "#b0f7d9");
      const line = readThemeColor(stage, "--engine-line", "#2e4941");
      coreMaterial.color.set(accent);
      cageMaterial.color.set(strong);
      nodeMaterial.color.set(strong);
      lineMaterial.color.set(accent);
      pulseMaterial.color.set(accent);
      starMaterial.color.set(accent);
      for (const material of ringMaterials) material.color.set(accent);
      for (const material of gridMaterials) material.color.set(line);
    };
    applyTheme();

    let width = 0;
    let height = 0;
    let frame = 0;
    let visible = true;
    let disposed = false;
    let pointerX = 0;
    let pointerY = 0;
    let targetX = 0;
    let targetY = 0;

    const resize = () => {
      const rect = stage.getBoundingClientRect();
      const nextWidth = Math.max(1, Math.floor(rect.width));
      const nextHeight = Math.max(1, Math.floor(rect.height));
      if (nextWidth === width && nextHeight === height) return;
      width = nextWidth;
      height = nextHeight;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };

    const render = (time = 0) => {
      pointerX += (targetX - pointerX) * 0.045;
      pointerY += (targetY - pointerY) * 0.045;
      const seconds = time * 0.001;
      if (!reduced) {
        core.rotation.y = seconds * 0.17;
        core.rotation.x = seconds * 0.09;
        cage.rotation.y = -seconds * 0.08;
        cage.rotation.z = seconds * 0.05;
        orbitA.rotation.z = 0.16 + seconds * 0.17;
        orbitB.rotation.x = 0.25 - seconds * 0.13;
        orbitC.rotation.z = 0.7 - seconds * 0.09;
        pulse.scale.setScalar(1 + Math.sin(seconds * 1.25) * 0.035);
        pulseMaterial.opacity = 0.055 + Math.sin(seconds * 1.25) * 0.022;
        stars.rotation.z = seconds * 0.008;
        root.rotation.y = 0.18 + pointerX * 0.12;
        root.rotation.x = -0.12 - pointerY * 0.075;
        camera.position.x = pointerX * 0.16;
        camera.position.y = 0.1 - pointerY * 0.1;
        camera.lookAt(0, 0, 0);
      }
      renderer.render(scene, camera);
    };

    const loop = (time: number) => {
      frame = 0;
      if (disposed || !visible || document.hidden) return;
      render(time);
      frame = window.requestAnimationFrame(loop);
    };
    const start = () => {
      if (disposed || reduced || frame || !visible || document.hidden) return;
      frame = window.requestAnimationFrame(loop);
    };
    const stop = () => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = 0;
    };

    const onPointerMove = (event: PointerEvent) => {
      const rect = stage.getBoundingClientRect();
      targetX = ((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2;
      targetY = ((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * 2;
    };
    const onVisibility = () => {
      if (document.hidden) stop();
      else start();
    };
    const onContextLost = () => {
      stop();
      stage.dataset.webgl = "fallback";
    };

    const resizeObserver = new ResizeObserver(() => {
      resize();
      if (reduced) render(0);
    });
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true;
      if (visible) start();
      else stop();
    }, { threshold: 0.05 });
    const themeObserver = new MutationObserver(() => {
      applyTheme();
      if (reduced) render(0);
    });

    resizeObserver.observe(stage);
    intersectionObserver.observe(stage);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    document.addEventListener("visibilitychange", onVisibility);
    canvas.addEventListener("webglcontextlost", onContextLost);
    if (!coarse && !reduced) stage.addEventListener("pointermove", onPointerMove, { passive: true });

    resize();
    stage.dataset.webgl = "ready";
    if (reduced) render(0);
    else start();

    return () => {
      disposed = true;
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      themeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      stage.removeEventListener("pointermove", onPointerMove);

      const geometries = new Set<THREE.BufferGeometry>();
      const materials = new Set<THREE.Material>();
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) geometries.add(mesh.geometry as THREE.BufferGeometry);
        const material = (object as THREE.Mesh).material;
        if (Array.isArray(material)) {
          for (const item of material) materials.add(item);
        } else if (material) {
          materials.add(material);
        }
      });
      for (const geometry of geometries) geometry.dispose();
      for (const material of materials) material.dispose();
      renderer.dispose();
    };
  }, [showGrid]);

  return (
    <div ref={stageRef} className="engine-three-core" data-webgl="pending" aria-hidden="true">
      <OrbitBrandMark label={label} showGrid={showGrid} />
      <canvas ref={canvasRef} className="engine-three-core-canvas" />
      <div className="engine-three-core-label"><b>{label}</b></div>
    </div>
  );
}
