"use client";

import { useState } from "react";

export function useImageOcr() {
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);

  const processImage = async (file: File): Promise<string | null> => {
    setOcrLoading(true);
    setOcrError(null);
    try {
      const { createWorker } = await import("tesseract.js");
      const worker = await createWorker("vie+eng");
      const ret = await worker.recognize(file);
      await worker.terminate();
      const text = ret.data.text.trim();
      setOcrLoading(false);
      return text;
    } catch (err) {
      console.error("OCR process error:", err);
      setOcrError(err instanceof Error ? err.message : "OCR failed");
      setOcrLoading(false);
      return null;
    }
  };

  return { processImage, ocrLoading, ocrError };
}
