export type PngDeliveryResult = "copied" | "shared" | "downloaded" | "cancelled";

type PngDeliveryOptions = {
  fileName: string;
  title: string;
};

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

export async function deliverPngBlob(blob: Blob, options: PngDeliveryOptions): Promise<PngDeliveryResult> {
  if (!(blob instanceof Blob) || blob.size <= 0) throw new Error("PNG blob is empty");

  if (navigator.clipboard?.write && typeof ClipboardItem !== "undefined") {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({ "image/png": blob }),
      ]);
      return "copied";
    } catch {
      // Firefox Android and some Chromium WebViews expose Clipboard API but
      // reject image/png writes. Fall through to the native share sheet.
    }
  }

  if (typeof navigator.share === "function" && typeof File !== "undefined") {
    const file = new File([blob], options.fileName, { type: "image/png", lastModified: Date.now() });
    const shareData: ShareData = { files: [file], title: options.title };
    let canShare = true;
    if (typeof navigator.canShare === "function") {
      try {
        canShare = navigator.canShare(shareData);
      } catch {
        canShare = false;
      }
    }
    if (canShare) {
      try {
        await navigator.share(shareData);
        return "shared";
      } catch (error) {
        if (isAbortError(error)) return "cancelled";
      }
    }
  }

  const url = URL.createObjectURL(blob);
  try {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = options.fileName;
    anchor.rel = "noopener";
    anchor.style.display = "none";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    return "downloaded";
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(url), 1500);
  }
}
