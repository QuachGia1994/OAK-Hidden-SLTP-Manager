"use client";

import { ChangeEvent, DragEvent, useEffect, useMemo, useRef, useState } from "react";
import { ToolArtwork } from "@/components/ToolArtwork";
import { TEXT } from "@/lib/factcheck/locale-copy";
import { detectInputKind, extractHostnameLabel } from "@/lib/factcheck/input-detect";
import { mediaClientStatus, normalizeClientImageMime } from "@/lib/factcheck/media-client";
import { useImageOcr } from "@/hooks/useImageOcr";
import styles from "./factcheck-workspace.module.css";

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
    <section className={`${styles.inputPanel} oak-fact-input-panel`} aria-labelledby="factcheck-input-title">
      <header className={`${styles.inputHeader} oak-fact-input-header`}>
        <div className={styles.inputHeading}>
          <span className={styles.sectionEyebrow}>{t.input}</span>
          <h2 id="factcheck-input-title">{locale === "EN" ? "What would you like to check?" : "Bạn muốn kiểm tra điều gì?"}</h2>
          <p>{locale === "EN" ? "Paste text or a link, or choose an image to begin. Your draft stays when you switch modes." : "Dán nội dung, liên kết hoặc chọn ảnh để bắt đầu. Bản nháp được giữ khi đổi chế độ."}</p>
        </div>
        <span className={`${styles.charMeter} oak-char-meter`} aria-live="polite">{text.length.toLocaleString()}/12,000</span>
      </header>

      <div className={`${styles.modeControls} oak-input-modes`} role="group" aria-label={locale === "EN" ? "Input type" : "Loại nội dung"}>
        <button className={styles.modeButton} type="button" aria-pressed={inputMode === "text"} onClick={() => setInputMode("text")} disabled={busy}>
          <span className={styles.modeIndex}>01</span>
          <span>{locale === "EN" ? "News / link" : "Tin / link"}</span>
        </button>
        <button className={styles.modeButton} type="button" aria-pressed={inputMode === "image"} onClick={() => setInputMode("image")} disabled={busy}>
          <span className={styles.modeIndex}>02</span>
          <span>{locale === "EN" ? "Image" : "Ảnh"}</span>
        </button>
      </div>
      <div hidden={inputMode !== "text"}>
      <div
        className={`${styles.editor} oak-claim-editor`}
        data-dragging={dragging ? "true" : undefined}
        onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <div className={styles.editorBar}>
          <span>{locale === "EN" ? "Your content" : "Nội dung cần kiểm tra"}</span>
          <span>{locale === "EN" ? "Text, link, or pasted excerpt" : "Văn bản, liên kết hoặc đoạn trích"}</span>
        </div>
        <textarea
          className={styles.textarea}
          aria-label={t.textOrImage}
          rows={4}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder={ocrLoading ? t.detectText : t.placeholder}
          disabled={busy}
          maxLength={12000}
        />
        {ocrLoading && (
          <div className={`${styles.ocrOverlay} oak-ocr-overlay`}>
            <span className={`${styles.spinner} oak-ocr-spinner`} />
            <b>{t.detectText}</b>
          </div>
        )}
      </div>

      {isUrl && urlHost && (
        <div className={`${styles.urlChip} oak-url-chip`} role="status">
          <span className="oak-eyebrow">{t.urlDetected}</span>
          <b>{urlHost}</b>
        </div>
      )}

      </div>
      <div hidden={inputMode !== "image"}>
      {!selectedImage && <button type="button" className={`${styles.imageDropzone} oak-image-dropzone`} disabled={busy} onClick={() => fileInputRef.current?.click()} onDragOver={event => event.preventDefault()} onDrop={handleDrop}>
        <ToolArtwork kind="factcheck" /><b>{t.uploadImage}</b><small>{locale === "EN" ? "Analyze image evidence or extract text to fact-check" : "Phân tích bằng chứng ảnh hoặc trích chữ để kiểm tra tin"}</small>
      </button>}
      {selectedImage && (
        <div className={`${styles.imageIntent} oak-image-intent`} role="group" aria-label={t.imageSelected} aria-busy={mediaLoading}>
          <div className="oak-image-intent-summary">
            {previewUrl ? <img className={`${styles.imagePreview} oak-image-intent-preview`} src={previewUrl} alt="" /> : null}
            <div className={`${styles.imageCopy} oak-image-intent-copy`}>
              <span className={styles.sectionEyebrow}>{t.imageSelected}</span>
              <b title={selectedImage.name}>{selectedImage.name}</b>
              <small>
                {(selectedImage.size / 1024).toFixed(0)} KB · {selectedMediaStatus === "too_large"
                  ? t.imageTooLargeClient
                  : mediaSupported
                    ? t.imageAuthenticityHint
                    : t.imageUnsupportedClient}
              </small>
              <div className={`${styles.inlineActions} oak-image-selection-actions`}>
                <button type="button" onClick={() => fileInputRef.current?.click()} disabled={busy}>{t.imageChange}</button>
                <button type="button" onClick={clearSelectedImage} disabled={busy}>{t.imageRemove}</button>
              </div>
            </div>
          </div>
          <p className={`${styles.disclosure} oak-image-auth-disclosure`}>{t.imageAuthenticityDisclosure}</p>
          {mediaLoading ? <p className={`${styles.analysisStatus} oak-image-analysis-status`} role="status" aria-live="polite">{t.mediaAnalyzing}</p> : null}
          <div className={`${styles.imageActions} oak-image-intent-actions`}>
            <button type="button" onClick={runImageOcr} disabled={busy}>{t.imageClaims}</button>
            <button type="button" className="oak-image-auth-action" onClick={() => onMediaSubmit(selectedImage)} disabled={busy || !mediaSupported}>
              {mediaLoading ? t.mediaAnalyzing : t.imageAuthenticity}
            </button>
          </div>
        </div>
      )}

      <aside className={`${styles.evidenceMethod} oak-image-evidence-method`} aria-label={t.imageEvidenceLayers}>
        <small>{t.imageEvidenceLayers}</small>
        <div className="oak-image-evidence-list">{t.imageEvidenceItems.map((item) => <span key={item}>{item}</span>)}</div>
        <p>{t.imageAuthenticityCaution}</p>
      </aside>
      </div>
      {(ocrError || imageError) && <p className={`${styles.formError} oak-form-error`} role="alert">{ocrError || imageError}</p>}

      <div className={`${styles.actionBar} oak-fact-actions`} data-mode={inputMode}>
        <button type="button" className={`${styles.secondaryAction} oak-upload-action`} hidden={inputMode === "image"} onClick={() => fileInputRef.current?.click()} disabled={busy}>
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
          className={`${styles.primaryAction} oak-primary-action oak-fact-submit`}
          hidden={inputMode !== "text"}
          onClick={onSubmit}
          disabled={busy || !text.trim()}
        >
          {loading ? <><span className={`${styles.spinner} oak-button-spinner`} /> <b>{loadingLabel}</b></> : <><b>{t.submit}</b><i>→</i></>}
        </button>
      </div>
    </section>
  );
}
