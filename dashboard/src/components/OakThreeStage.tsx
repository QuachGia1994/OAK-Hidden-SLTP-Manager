"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";

export type OakThreeVariant = "neotech" | "factcheck" | "tarot" | "discover";
export type DiscoverThreeState = "daily" | "dream" | "oracle" | "mood" | "compatibility";

type OakThreeStageProps = {
  variant: OakThreeVariant;
  active?: DiscoverThreeState;
  fallback?: ReactNode;
  className?: string;
};

const REDUCED_QUERY = "(prefers-reduced-motion: reduce)";
const COARSE_QUERY = "(pointer: coarse)";

function cssColor(element: HTMLElement, token: string, fallback: string) {
  return getComputedStyle(element).getPropertyValue(token).trim() || fallback;
}

function disposeScene(scene: THREE.Scene) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  const textures = new Set<THREE.Texture>();

  scene.traverse((object) => {
    const mesh = object as THREE.Mesh;
    if (mesh.geometry) geometries.add(mesh.geometry as THREE.BufferGeometry);
    const material = mesh.material;
    const list = Array.isArray(material) ? material : material ? [material] : [];
    for (const item of list) {
      materials.add(item);
      for (const value of Object.values(item)) {
        if (value instanceof THREE.Texture) textures.add(value);
      }
    }
  });

  for (const texture of textures) texture.dispose();
  for (const geometry of geometries) geometry.dispose();
  for (const material of materials) material.dispose();
}

export function OakThreeStage({ variant, active = "daily", fallback, className = "" }: OakThreeStageProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const activeRef = useRef<DiscoverThreeState>(active);
  activeRef.current = active;
  const [contextEpoch, setContextEpoch] = useState(0);

  useEffect(() => {
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    if (!stage || !canvas) return;

    const reduced = window.matchMedia(REDUCED_QUERY).matches;
    const coarse = window.matchMedia(COARSE_QUERY).matches;
    let renderer: THREE.WebGLRenderer;

    try {
      renderer = new THREE.WebGLRenderer({
        canvas,
        alpha: true,
        antialias: !coarse,
        powerPreference: "low-power",
      });
    } catch {
      stage.dataset.threeState = "fallback";
      return;
    }

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.15 : 1.65));
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 40);
    camera.position.set(0, 0, variant === "factcheck" ? 5.6 : 6.8);

    const root = new THREE.Group();
    scene.add(root);

    const themeMaterials: Array<THREE.Material & { color: THREE.Color }> = [];
    const makeBasic = (opacity = 1, wireframe = false) => {
      const material = new THREE.MeshBasicMaterial({
        transparent: opacity < 1,
        opacity,
        wireframe,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      themeMaterials.push(material);
      return material;
    };
    const makeLine = (opacity = 1) => {
      const material = new THREE.LineBasicMaterial({
        transparent: opacity < 1,
        opacity,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      themeMaterials.push(material);
      return material;
    };

    let animateVariant: (time: number) => void = () => {};

    if (variant === "neotech") {
      const core = new THREE.Mesh(new THREE.OctahedronGeometry(0.92, 2), makeBasic(0.6, true));
      const cage = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.IcosahedronGeometry(1.35, 1)),
        makeLine(0.2),
      );
      root.add(core, cage);

      const nodeMaterial = makeBasic(0.92);
      const nodeGeometry = new THREE.SphereGeometry(0.055, 10, 8);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(2.05, 0.008, 4, coarse ? 72 : 140), makeBasic(0.28));
      ring.rotation.x = 1.02;
      root.add(ring);

      const nodes: THREE.Mesh[] = [];
      for (let index = 0; index < 14; index += 1) {
        const angle = (index / 14) * Math.PI * 2;
        const node = new THREE.Mesh(nodeGeometry, nodeMaterial);
        node.position.set(Math.cos(angle) * 2.05, Math.sin(angle) * 2.05, 0);
        ring.add(node);
        nodes.push(node);
      }

      const shield = new THREE.Mesh(new THREE.CylinderGeometry(1.68, 1.68, 0.025, 6), makeBasic(0.08, true));
      shield.rotation.x = Math.PI / 2;
      root.add(shield);

      animateVariant = (time) => {
        const t = time * 0.001;
        core.rotation.x = t * 0.13;
        core.rotation.y = t * 0.18;
        cage.rotation.y = -t * 0.08;
        ring.rotation.z = t * 0.07;
        nodes.forEach((node, index) => {
          const angle = (index / nodes.length) * Math.PI * 2 + t * 0.16;
          node.position.set(Math.cos(angle) * 2.05, Math.sin(angle) * 2.05, 0);
        });
      };
    }

    if (variant === "factcheck") {
      const outer = new THREE.Mesh(new THREE.TorusGeometry(1.55, 0.035, 8, 120), makeBasic(0.5, true));
      const inner = new THREE.Mesh(new THREE.TorusGeometry(1.02, 0.012, 5, 100), makeBasic(0.3));
      outer.rotation.x = 0.18;
      inner.rotation.x = -0.12;
      root.add(outer, inner);

      const glass = new THREE.Mesh(new THREE.CircleGeometry(0.96, 48), makeBasic(0.045));
      glass.position.z = -0.08;
      root.add(glass);

      const pageMaterial = makeBasic(0.18, true);
      const pages = [
        [-1.52, 0.82, -0.42, -0.18],
        [1.5, 0.68, -0.5, 0.17],
        [-1.3, -0.95, -0.7, 0.12],
        [1.35, -0.9, -0.55, -0.14],
      ] as const;
      for (const [x, y, z, rz] of pages) {
        const page = new THREE.Mesh(new THREE.PlaneGeometry(0.72, 0.92, 3, 4), pageMaterial);
        page.position.set(x, y, z);
        page.rotation.z = rz;
        root.add(page);
      }

      const scan = new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(-1.2, 0, 0.1),
          new THREE.Vector3(1.2, 0, 0.1),
        ]),
        makeLine(0.5),
      );
      root.add(scan);

      const evidenceNodes: THREE.Mesh[] = [];
      const nodeMaterial = makeBasic(0.86);
      for (let index = 0; index < 8; index += 1) {
        const angle = (index / 8) * Math.PI * 2;
        const node = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), nodeMaterial);
        node.position.set(Math.cos(angle) * 1.55, Math.sin(angle) * 1.55, 0);
        outer.add(node);
        evidenceNodes.push(node);
      }

      animateVariant = (time) => {
        const t = time * 0.001;
        outer.rotation.z = t * 0.08;
        inner.rotation.z = -t * 0.12;
        evidenceNodes.forEach((node, index) => {
          const angle = (index / evidenceNodes.length) * Math.PI * 2 - t * 0.16;
          node.position.set(Math.cos(angle) * 1.55, Math.sin(angle) * 1.55, 0);
        });
        scan.position.y = Math.sin(t * 1.25) * 0.82;
      };
    }

    if (variant === "tarot") {
      const cardMaterial = makeBasic(0.36, true);
      const cards = new THREE.Group();
      [-0.72, 0, 0.72].forEach((x, index) => {
        const card = new THREE.Mesh(new THREE.BoxGeometry(1.08, 1.66, 0.055), cardMaterial);
        card.position.set(x, index === 1 ? 0.18 : -0.05, index === 1 ? 0.2 : 0);
        card.rotation.z = (index - 1) * 0.22;
        card.rotation.y = (index - 1) * -0.16;
        cards.add(card);
      });
      root.add(cards);

      const orbit = new THREE.Mesh(new THREE.TorusGeometry(1.82, 0.009, 4, 110), makeBasic(0.2));
      orbit.rotation.set(1.1, 0.18, 0.2);
      root.add(orbit);

      const star = new THREE.Mesh(new THREE.OctahedronGeometry(0.25, 1), makeBasic(0.5, true));
      star.position.set(0, 1.38, 0.24);
      root.add(star);

      animateVariant = (time) => {
        const t = time * 0.001;
        cards.rotation.y = Math.sin(t * 0.45) * 0.16;
        cards.rotation.x = Math.sin(t * 0.32) * 0.05;
        orbit.rotation.z = 0.2 + t * 0.07;
        star.rotation.x = t * 0.25;
        star.rotation.y = -t * 0.32;
      };
    }

    if (variant === "discover") {
      const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.52, 2), makeBasic(0.45, true));
      root.add(core);

      const keys: DiscoverThreeState[] = ["daily", "dream", "oracle", "mood", "compatibility"];
      const nodeMaterial = makeBasic(0.72);
      const nodeMap = new Map<DiscoverThreeState, THREE.Mesh>();

      const orbitA = new THREE.Mesh(new THREE.TorusGeometry(1.35, 0.008, 4, 100), makeBasic(0.16));
      const orbitB = new THREE.Mesh(new THREE.TorusGeometry(2.18, 0.007, 4, 120), makeBasic(0.22));
      orbitA.rotation.x = 1.12;
      orbitB.rotation.set(0.4, 0.72, 0.28);
      root.add(orbitA, orbitB);

      keys.forEach((key, index) => {
        const angle = -Math.PI / 2 + (index / keys.length) * Math.PI * 2;
        const geometry = key === "oracle"
          ? new THREE.OctahedronGeometry(0.2, 1)
          : key === "compatibility"
            ? new THREE.TorusKnotGeometry(0.14, 0.035, 40, 6)
            : key === "dream"
              ? new THREE.DodecahedronGeometry(0.2, 1)
              : key === "mood"
                ? new THREE.SphereGeometry(0.19, 14, 10)
                : new THREE.IcosahedronGeometry(0.2, 1);
        const node = new THREE.Mesh(geometry, nodeMaterial);
        node.position.set(Math.cos(angle) * 2.18, Math.sin(angle) * 2.18, 0);
        nodeMap.set(key, node);
        orbitB.add(node);
      });

      animateVariant = (time) => {
        const t = time * 0.001;
        core.rotation.x = t * 0.12;
        core.rotation.y = -t * 0.16;
        orbitA.rotation.z = t * 0.08;
        orbitB.rotation.z = 0.28 - t * 0.05;

        for (const [index, key] of keys.entries()) {
          const node = nodeMap.get(key);
          if (!node) continue;
          const angle = -Math.PI / 2 + (index / keys.length) * Math.PI * 2 + t * 0.07;
          node.position.set(Math.cos(angle) * 2.18, Math.sin(angle) * 2.18, 0);
          const selected = key === activeRef.current;
          const desired = selected ? 1.7 : 1;
          const scale = node.scale.x + (desired - node.scale.x) * 0.08;
          node.scale.setScalar(scale);
          node.rotation.x = t * (selected ? 0.7 : 0.2);
          node.rotation.y = t * (selected ? 0.85 : 0.25);
        }
      };
    }

    const starCount = coarse ? 48 : 110;
    const starPositions = new Float32Array(starCount * 3);
    for (let index = 0; index < starCount; index += 1) {
      const angle = index * 2.399963229728653;
      const radius = 2.2 + (index % 17) * 0.11;
      starPositions[index * 3] = Math.cos(angle) * radius;
      starPositions[index * 3 + 1] = Math.sin(angle * 1.13) * 2;
      starPositions[index * 3 + 2] = -1.8 + (index % 13) * 0.18;
    }
    const starGeometry = new THREE.BufferGeometry();
    starGeometry.setAttribute("position", new THREE.BufferAttribute(starPositions, 3));
    const starMaterial = new THREE.PointsMaterial({
      size: coarse ? 0.02 : 0.027,
      transparent: true,
      opacity: 0.26,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);

    const applyTheme = () => {
      const accent = cssColor(stage, "--three-accent", "#84e5c2");
      const strong = cssColor(stage, "--three-accent-strong", "#b0f7d9");
      themeMaterials.forEach((material, index) => material.color.set(index % 4 === 1 ? strong : accent));
      starMaterial.color.set(accent);
    };
    applyTheme();

    let width = 0;
    let height = 0;
    let frame = 0;
    let animationStart: number | null = null;
    let visible = true;
    let pointerX = 0;
    let pointerY = 0;
    let targetX = 0;
    let targetY = 0;
    let hover = 0;
    let targetHover = 0;

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
      pointerX += (targetX - pointerX) * 0.04;
      pointerY += (targetY - pointerY) * 0.04;
      hover += (targetHover - hover) * 0.075;
      if (!reduced) {
        animateVariant(time);
        root.rotation.x += (-pointerY * 0.2 * hover - root.rotation.x) * 0.06;
        root.rotation.y += (pointerX * 0.25 * hover - root.rotation.y) * 0.06;
        root.rotation.z += (pointerX * 0.06 * hover - root.rotation.z) * 0.06;
        root.position.z += (hover * 0.18 - root.position.z) * 0.06;
        root.scale.setScalar(1 + hover * 0.04);
      }
      renderer.render(scene, camera);
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
    const onPointerMove = (event: PointerEvent) => {
      const rect = stage.getBoundingClientRect();
      targetX = ((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2;
      targetY = ((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * 2;
    };
    const onPointerEnter = () => { targetHover = 1; };
    const onPointerLeave = () => {
      targetHover = 0;
      targetX = 0;
      targetY = 0;
    };
    const onVisibility = () => document.hidden ? stop() : start();
    let restoring = false;
    const onContextLost = (event: Event) => {
      event.preventDefault();
      stop();
      stage.dataset.threeState = "fallback";
    };
    const onContextRestored = () => {
      restoring = true;
      setContextEpoch((epoch) => epoch + 1);
    };

    const resizeObserver = new ResizeObserver(() => {
      resize();
      if (reduced) render(0);
    });
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      visible = entry?.isIntersecting ?? true;
      if (visible) start();
      else stop();
    }, { threshold: 0.03 });
    const themeObserver = new MutationObserver(() => {
      applyTheme();
      if (reduced) render(0);
    });

    resizeObserver.observe(stage);
    intersectionObserver.observe(stage);
    themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
    document.addEventListener("visibilitychange", onVisibility);
    canvas.addEventListener("webglcontextlost", onContextLost);
    canvas.addEventListener("webglcontextrestored", onContextRestored);
    if (!coarse && !reduced) {
      stage.addEventListener("pointerenter", onPointerEnter);
      stage.addEventListener("pointermove", onPointerMove, { passive: true });
      stage.addEventListener("pointerleave", onPointerLeave);
    }

    resize();
    render(0);
    stage.dataset.threeState = "ready";
    if (!reduced) start();

    return () => {
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      themeObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      canvas.removeEventListener("webglcontextlost", onContextLost);
      canvas.removeEventListener("webglcontextrestored", onContextRestored);
      stage.removeEventListener("pointermove", onPointerMove);
      stage.removeEventListener("pointerenter", onPointerEnter);
      stage.removeEventListener("pointerleave", onPointerLeave);
      disposeScene(scene);
      if (!restoring) renderer.forceContextLoss();
      renderer.dispose();
    };
  }, [variant, contextEpoch]);

  const classes = ("oak-three-stage " + className).trim();
  return (
    <div
      ref={stageRef}
      className={classes}
      data-three-state="pending"
      data-three-variant={variant}
      data-three-active={active}
      aria-hidden="true"
    >
      {fallback ? <div className="oak-three-fallback">{fallback}</div> : null}
      <canvas ref={canvasRef} className="oak-three-canvas" />
    </div>
  );
}
