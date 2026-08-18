"use client";

import { ChangeEvent, DragEvent, useMemo, useRef, useState } from "react";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { detectInputKind, extractHostnameLabel } from "@/lib/factcheck/input-detect";
import { useImageOcr } from "@/hooks/useImageOcr";

const MEDIA_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const MEDIA_MAX_IMAGE_BYTES = 4_000_000;

export function FactCheckInput({
  text,
  setText,
  onSubmit,
  onMediaSubmit,
  loading,
  mediaLoading,
  locale,
}: {
  text: string;
  setText: (v: string) => void;
  onSubmit: () => void;
  onMediaSubmit: (file: File) => void;
  loading: boolean;
  mediaLoading: boolean;
  locale: "VN" | "EN";
}) {
  const t = TEXT[locale];
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { processImage, ocrLoading, ocrError } = useImageOcr();
  const [dragging, setDragging] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);

  const urlHost = useMemo(() => extractHostnameLabel(text), [text]);
  const isUrl = detectInputKind(text) === "url";
  const busy = loading || mediaLoading || ocrLoading;
  const mediaSupported = Boolean(
    selectedImage
    && MEDIA_IMAGE_TYPES.has(selectedImage.type)
    && selectedImage.size > 0
    && selectedImage.size <= MEDIA_MAX_IMAGE_BYTES,
  );

  const selectFile = (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size <= 0) {
      setSelectedImage(null);
      setImageError(t.imageUnsupportedClient);
      return;
    }
    setImageError(null);
    setSelectedImage(file);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    selectFile(e.target.files?.[0]);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    selectFile(e.dataTransfer.files?.[0]);
  };

  const runImageOcr = async () => {
    if (!selectedImage || busy) return;
    const detected = await processImage(selectedImage);
    if (detected) setText(detected);
  };

  const loadingLabel = loading
    ? (isUrl ? t.readingUrl : t.submitting)
    : t.submit;

  return (
    <section className="oak-fact-input-panel">
      <header className="oak-fact-input-header">
        <div>
          <span className="oak-eyebrow">{t.input} / CLAIM TERMINAL</span>
          <h2>{t.textOrImage}</h2>
        </div>
        <span className="oak-char-meter">{text.length.toLocaleString()}/12,000</span>
      </header>

      <div
        className="oak-claim-editor"
        data-dragging={dragging ? "true" : undefined}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <div className="oak-editor-rail" aria-hidden="true"><span>01</span><span>02</span><span>03</span><span>04</span><span>05</span></div>
        <textarea
          rows={7}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={ocrLoading ? t.detectText : t.placeholder}
          disabled={busy}
          maxLength={12000}
        />
        {ocrLoading && (
          <div className="oak-ocr-overlay">
            <span className="oak-ocr-spinner" />
            <b>{t.detectText}</b>
          </div>
        )}
      </div>

      {isUrl && urlHost && (
        <div className="oak-url-chip" role="status">
          <span className="oak-eyebrow">{t.urlDetected}</span>
          <b>{urlHost}</b>
        </div>
      )}

      {selectedImage && (
        <div className="oak-image-intent" role="group" aria-label={t.imageSelected}>
          <div className="oak-image-intent-copy">
            <span className="oak-eyebrow">{t.imageSelected}</span>
            <b title={selectedImage.name}>{selectedImage.name}</b>
            <small>{(selectedImage.size / 1024).toFixed(0)} KB · {mediaSupported ? t.imageAuthenticityHint : t.imageUnsupportedClient}</small>
          </div>
          <div className="oak-image-intent-actions">
            <button type="button" onClick={runImageOcr} disabled={busy}>{t.imageClaims}</button>
            <button type="button" className="oak-image-auth-action" onClick={() => onMediaSubmit(selectedImage)} disabled={busy || !mediaSupported}>
              {mediaLoading ? t.mediaAnalyzing : t.imageAuthenticity}
            </button>
          </div>
        </div>
      )}

      {(ocrError || imageError) && <p className="oak-form-error">{ocrError || imageError}</p>}

      <div className="oak-fact-actions">
        <button type="button" className="oak-upload-action" onClick={() => fileInputRef.current?.click()} disabled={busy}>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v14H4z" /><path d="m6.5 16 4-4 2.5 2.5 2-2 2.5 3.5M9 9h.01" /></svg>
          <span>{t.uploadImage}</span>
          <small>{t.dragDrop}</small>
        </button>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          className="hidden"
          onChange={handleFileChange}
        />

        <button
          type="button"
          className="oak-primary-action oak-fact-submit"
          onClick={onSubmit}
          disabled={busy || !text.trim()}
        >
          {loading ? <><span className="oak-button-spinner" /> <b>{loadingLabel}</b></> : <><b>{t.submit}</b><i>→</i></>}
        </button>
      </div>
    </section>
  );
}
