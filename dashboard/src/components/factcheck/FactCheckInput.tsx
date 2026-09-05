"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { detectInputKind, extractHostnameLabel } from "@/lib/factcheck/input-detect";
import { mediaClientStatus, normalizeClientImageMime } from "@/lib/factcheck/media-client";
import { useImageOcr } from "@/hooks/useImageOcr";

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
  const [inputMode, setInputMode] = useState<"text" | "image">("text");
  const [dragging, setDragging] = useState(false);
  const [selectedImage, setSelectedImage] = useState<File | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState("");

  const urlHost = useMemo(() => extractHostnameLabel(text), [text]);
  const isUrl = detectInputKind(text) === "url";
  const busy = loading || mediaLoading || ocrLoading;
  const selectedMediaStatus = selectedImage ? mediaClientStatus(selectedImage) : "unsupported";
  const mediaSupported = Boolean(selectedImage && selectedMediaStatus === "supported");

  useEffect(() => {
    if (!selectedImage) {
      setPreviewUrl("");
      return;
    }
    const url = URL.createObjectURL(selectedImage);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [selectedImage]);

  const selectFile = (file: File | undefined) => {
    if (!file) return;
    const declaredImage = file.type.toLowerCase().startsWith("image/");
    const normalizedMime = normalizeClientImageMime(file);
    if ((!declaredImage && !normalizedMime) || file.size <= 0) {
      setSelectedImage(null);
      setImageError(t.imageUnsupportedClient);
      return;
    }

    const status = mediaClientStatus(file);
    setSelectedImage(file);
    setInputMode("image");
    setImageError(status === "too_large"
      ? t.imageTooLargeClient
      : status === "unsupported"
        ? t.imageUnsupportedClient
        : null);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    selectFile(e.target.files?.[0]);
  };

  const clearSelectedImage = () => {
    setSelectedImage(null);
    setImageError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleDrop = (e: DragEvent<HTMLElement>) => {
    e.preventDefault();
    setDragging(false);
    selectFile(e.dataTransfer.files?.[0]);
  };

  const runImageOcr = async () => {
    if (!selectedImage || busy) return;
    const detected = await processImage(selectedImage);
    if (detected) { setText(detected); setInputMode("text"); }
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

      <div className="oak-input-modes" role="group" aria-label={locale === "EN" ? "Input type" : "Loại nội dung"}>
        <button type="button" aria-pressed={inputMode === "text"} onClick={() => setInputMode("text")} disabled={busy}>{locale === "EN" ? "News / Link" : "Tin / Link"}</button>
        <button type="button" aria-pressed={inputMode === "image"} onClick={() => setInputMode("image")} disabled={busy}>{locale === "EN" ? "Image" : "Ảnh"}</button>
      </div>
      <div hidden={inputMode !== "text"}>
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
          aria-label={t.textOrImage}
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

      </div>
      <div hidden={inputMode !== "image"}>
      {!selectedImage && <button type="button" className="oak-image-dropzone" disabled={busy} onClick={() => fileInputRef.current?.click()} onDragOver={event => event.preventDefault()} onDrop={handleDrop}>
        <span aria-hidden="true">▧</span><b>{t.uploadImage}</b><small>{locale === "EN" ? "Analyze image evidence or extract text to fact-check" : "Phân tích bằng chứng ảnh hoặc trích chữ để kiểm tra tin"}</small>
      </button>}
      {selectedImage && (
        <div className="oak-image-intent" role="group" aria-label={t.imageSelected} aria-busy={mediaLoading}>
          <div className="oak-image-intent-summary">
            {previewUrl ? <img className="oak-image-intent-preview" src={previewUrl} alt="" /> : null}
            <div className="oak-image-intent-copy">
              <span className="oak-eyebrow">{t.imageSelected}</span>
              <b title={selectedImage.name}>{selectedImage.name}</b>
              <small>
                {(selectedImage.size / 1024).toFixed(0)} KB · {selectedMediaStatus === "too_large"
                  ? t.imageTooLargeClient
                  : mediaSupported
                    ? t.imageAuthenticityHint
                    : t.imageUnsupportedClient}
              </small>
              <div className="oak-image-selection-actions">
                <button type="button" onClick={() => fileInputRef.current?.click()} disabled={busy}>{t.imageChange}</button>
                <button type="button" onClick={clearSelectedImage} disabled={busy}>{t.imageRemove}</button>
              </div>
            </div>
          </div>
          <p className="oak-image-auth-disclosure">{t.imageAuthenticityDisclosure}</p>
          {mediaLoading ? <p className="oak-image-analysis-status" role="status" aria-live="polite">{t.mediaAnalyzing}</p> : null}
          <div className="oak-image-intent-actions">
            <button type="button" onClick={runImageOcr} disabled={busy}>{t.imageClaims}</button>
            <button type="button" className="oak-image-auth-action" onClick={() => onMediaSubmit(selectedImage)} disabled={busy || !mediaSupported}>
              {mediaLoading ? t.mediaAnalyzing : t.imageAuthenticity}
            </button>
          </div>
        </div>
      )}

      </div>
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
          hidden={inputMode !== "text"}
          onClick={onSubmit}
          disabled={busy || !text.trim()}
        >
          {loading ? <><span className="oak-button-spinner" /> <b>{loadingLabel}</b></> : <><b>{t.submit}</b><i>→</i></>}
        </button>
      </div>
    </section>
  );
}
