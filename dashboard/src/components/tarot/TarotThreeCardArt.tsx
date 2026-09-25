"use client";

import { useEffect, useRef } from "react";
import * as THREE from "three";

export function TarotThreeCardArt({
  src,
  alt,
  reversed,
}: {
  src: string;
  alt: string;
  reversed: boolean;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const stage = stageRef.current;
    const canvas = canvasRef.current;
    if (!stage || !canvas) return;

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
      stage.dataset.threeState = "fallback";
      return;
    }

    renderer.setClearColor(0x000000, 0);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.1 : 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(32, 2 / 3, 0.1, 20);
    camera.position.z = 4.15;

    const group = new THREE.Group();
    scene.add(group);

    const style = getComputedStyle(stage);
    const accent = style.getPropertyValue("--tarot-accent").trim() || "#84e5c2";
    const gold = style.getPropertyValue("--tarot-gold").trim() || "#d8c27a";
    const line = style.getPropertyValue("--tarot-line").trim() || "#2e4941";

    const backMaterial = new THREE.MeshBasicMaterial({
      color: gold,
      transparent: true,
      opacity: 0.18,
      side: THREE.FrontSide,
      depthWrite: false,
    });
    const edgeMaterial = new THREE.LineBasicMaterial({
      color: accent,
      transparent: true,
      opacity: 0.55,
      depthWrite: false,
    });

    const back = new THREE.Mesh(new THREE.PlaneGeometry(2, 3), backMaterial);
    back.rotation.y = Math.PI;
    back.position.z = -0.025;
    group.add(back);

    const backFrame = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(2.04, 3.04, 0.06)),
      edgeMaterial,
    );
    group.add(backFrame);

    const loader = new THREE.TextureLoader();
    let texture: THREE.Texture | null = null;
    let frontMaterial: THREE.MeshBasicMaterial | null = null;
    let disposed = false;
    let frame = 0;
    let animationStart = 0;
    let hoverX = 0;
    let hoverY = 0;
    let targetHoverX = 0;
    let targetHoverY = 0;

    const resize = () => {
      const rect = stage.getBoundingClientRect();
      renderer.setSize(Math.max(1, Math.floor(rect.width)), Math.max(1, Math.floor(rect.height)), false);
      camera.aspect = Math.max(rect.width, 1) / Math.max(rect.height, 1);
      camera.updateProjectionMatrix();
    };

    const render = (time = 0) => {
      if (disposed) return;
      const elapsed = Math.max(0, time - animationStart);
      const progress = reduced ? 1 : Math.min(1, elapsed / 820);
      const eased = 1 - Math.pow(1 - progress, 3);
      hoverX += (targetHoverX - hoverX) * 0.1;
      hoverY += (targetHoverY - hoverY) * 0.1;
      group.rotation.y = Math.PI * (1 - eased) + hoverX * 0.08;
      group.rotation.x = hoverY * 0.07;
      group.position.y = Math.sin(progress * Math.PI) * 0.08;
      renderer.render(scene, camera);
      if (!reduced && (progress < 1 || Math.abs(targetHoverX - hoverX) > 0.003 || Math.abs(targetHoverY - hoverY) > 0.003)) {
        frame = window.requestAnimationFrame(render);
      } else {
        frame = 0;
      }
    };

    const requestRender = () => {
      if (!frame && !disposed) frame = window.requestAnimationFrame(render);
    };

    const onPointerMove = (event: PointerEvent) => {
      if (coarse || reduced) return;
      const rect = stage.getBoundingClientRect();
      targetHoverX = ((event.clientX - rect.left) / Math.max(rect.width, 1) - 0.5) * 2;
      targetHoverY = ((event.clientY - rect.top) / Math.max(rect.height, 1) - 0.5) * -2;
      requestRender();
    };
    const onPointerLeave = () => {
      targetHoverX = 0;
      targetHoverY = 0;
      requestRender();
    };

    const resizeObserver = new ResizeObserver(() => {
      resize();
      requestRender();
    });
    resizeObserver.observe(stage);
    if (!coarse && !reduced) {
      stage.addEventListener("pointermove", onPointerMove, { passive: true });
      stage.addEventListener("pointerleave", onPointerLeave);
    }

    resize();
    loader.load(
      src,
      (loaded) => {
        if (disposed) {
          loaded.dispose();
          return;
        }
        texture = loaded;
        texture.colorSpace = THREE.SRGBColorSpace;
        frontMaterial = new THREE.MeshBasicMaterial({ map: texture, side: THREE.FrontSide });
        const front = new THREE.Mesh(new THREE.PlaneGeometry(2, 3), frontMaterial);
        front.position.z = 0.03;
        front.rotation.z = reversed ? Math.PI : 0;
        group.add(front);
        stage.dataset.threeState = "ready";
        animationStart = performance.now();
        requestRender();
      },
      undefined,
      () => {
        stage.dataset.threeState = "fallback";
      },
    );

    return () => {
      disposed = true;
      if (frame) window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      stage.removeEventListener("pointermove", onPointerMove);
      stage.removeEventListener("pointerleave", onPointerLeave);
      texture?.dispose();
      frontMaterial?.dispose();
      backMaterial.dispose();
      edgeMaterial.dispose();
      scene.traverse((object) => {
        const mesh = object as THREE.Mesh;
        if (mesh.geometry) mesh.geometry.dispose();
      });
      renderer.dispose();
    };
  }, [src, reversed]);

  return (
    <div ref={stageRef} className="tarot-three-card-art" data-three-state="pending">
      <img src={src} alt={alt} loading="lazy" width={420} height={630} />
      <canvas ref={canvasRef} aria-hidden="true" />
    </div>
  );
}
