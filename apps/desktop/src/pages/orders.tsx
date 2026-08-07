import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { useLocale } from "../contexts";
import type { ProfilesList } from "../ipc/types";

/**
 * Order Management page — "Lệnh chờ xử lý".
 * Shows worker-executed session tasks backed by the File phiên làm việc
 * workspace (pending.summary). Scheduling is not performed from Tauri;
 * execution stays in the Python workers.
 */

interface LegacyPendingItem {
  id: string;
  kind: string;
  status: string;
  file_name: string;
  [key: string]: unknown;
}

interface LegacyPendingSummary {
  profile: string;
  files: { name: string; count: number }[];
  items: LegacyPendingItem[];
  total: number;
  waiting: number;
  done: number;
}

export function OrdersPage() {
  const { locale } = useLocale();
  const vn = locale === "VN";
  const L = {
    title: vn ? "Lệnh chờ xử lý" : "Pending Orders",
    subtitle: vn
      ? "Tác vụ chờ do worker Python thực thi — xem và quản lý file phiên làm việc"
      : "Worker-executed session tasks — view and manage session files",
    profile: vn ? "Hồ sơ" : "Profile",
  };
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [profiles, setProfiles] = useState<string[]>([]);
  const [selectedProfile, setSelectedProfile] = useState("");
  const [legacyPending, setLegacyPending] = useState<LegacyPendingSummary | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState("");
  const [pendingAction, setPendingAction] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void request<ProfilesList>("profiles.list").then((res) => {
      if (cancelled) return;
      const names = (res.profiles ?? []).map((profile) => profile.profile_name);
      setProfiles(names);
      setSelectedProfile((current) => current || names[0] || "");
    }).catch((e: unknown) => {
      if (!cancelled) setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    });
    return () => { cancelled = true; };
  }, []);

  const loadLegacyPending = useCallback(async (profile: string) => {
    if (!profile) {
      setLegacyPending(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const result = await request<LegacyPendingSummary>("pending.summary", { profile });
      setLegacyPending(result);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLegacyPending(selectedProfile);
  }, [loadLegacyPending, selectedProfile]);

  const deletePending = async (item: LegacyPendingItem) => {
    if (pendingDeleteId !== item.id) {
      setPendingDeleteId(item.id);
      setSavedMsg(vn ? "Nhấn Xóa lần nữa để xóa tác vụ này." : "Click Delete again to remove this task.");
      return;
    }
    setPendingAction(item.id);
    setError(null);
    try {
      await request("pending.item.delete", { profile: selectedProfile, item_id: item.id });
      setPendingDeleteId("");
      setSavedMsg(vn ? "Đã xóa tác vụ chờ." : "Pending task deleted.");
      await loadLegacyPending(selectedProfile);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setPendingAction(null);
    }
  };

  const clearDonePending = async () => {
    if (!selectedProfile) return;
    setPendingAction("clear");
    setError(null);
    try {
      const result = await request<{ cleared: number }>("pending.clear_done", { profile: selectedProfile });
      setSavedMsg(vn ? `Đã xóa ${result.cleared} tác vụ hoàn tất.` : `Cleared ${result.cleared} completed task(s).`);
      setPendingDeleteId("");
      await loadLegacyPending(selectedProfile);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setPendingAction(null);
    }
  };

  const copyPending = async (item: LegacyPendingItem) => {
    try {
      const copy: Record<string, unknown> = { ...item };
      delete copy.id;
      delete copy.file_name;
      await navigator.clipboard.writeText(JSON.stringify(copy, null, 2));
      setSavedMsg(vn ? "Đã sao chép tác vụ." : "Pending task copied.");
    } catch {
      setSavedMsg(vn ? "Không thể truy cập clipboard." : "Clipboard unavailable.");
    }
  };

  return (
    <div className="content">
      <h1>{L.title}</h1>
      <p className="muted small">{L.subtitle}</p>

      {error && (
        <section className="panel error">
          <span className="badge error">ERROR</span>
          <p>{error}</p>
        </section>
      )}
      {savedMsg && <p className="hint">{savedMsg}</p>}
      {loading && <p className="muted">{vn ? "Đang tải…" : "Loading…"}</p>}

      <section className="panel legacy-pending-panel">
        <div className="panel-heading">
          <div><h2>{vn ? "File phiên làm việc" : "Session files"}</h2><p className="muted small">{vn ? "Điều khiển tác vụ chờ theo từng hồ sơ." : "Pending controls are scoped to one profile."}</p></div>
          <div className="pending-controls">
            <select value={selectedProfile} onChange={(e) => setSelectedProfile(e.target.value)} aria-label={L.profile}>
              {profiles.map((name) => <option key={name} value={name}>{name}</option>)}
              {profiles.length === 0 && <option value="">—</option>}
            </select>
            <button type="button" className="btn" onClick={() => void loadLegacyPending(selectedProfile)} disabled={pendingAction !== null}>{vn ? "Làm mới" : "Refresh"}</button>
            <button type="button" className="btn" onClick={() => void clearDonePending()} disabled={pendingAction !== null || !selectedProfile}>{vn ? "Xóa tác vụ xong" : "Clear done"}</button>
          </div>
        </div>
        {legacyPending && (
          <>
            <div className="pending-summary-grid">
              <span><b>{legacyPending.total}</b> {vn ? "tổng" : "total"}</span>
              <span><b>{legacyPending.waiting}</b> {vn ? "đang chờ" : "waiting"}</span>
              <span><b>{legacyPending.done}</b> {vn ? "đã xong" : "done"}</span>
              {legacyPending.files.map((file) => <span key={file.name} className="muted mono">{file.name}: {file.count}</span>)}
            </div>
            {legacyPending.items.length === 0 ? (
              <div className="empty-state"><p>{vn ? "Không có tác vụ chờ trong file phiên làm việc." : "No pending tasks in the session file."}</p></div>
            ) : (
              <div className="pending-item-list">
                {legacyPending.items.map((item) => (
                  <div className={`pending-item ${isPendingWaiting(item.status) ? "waiting" : ""}`} key={item.id}>
                    <div className="pending-item-head">
                      <strong>{String(item.kind).toUpperCase()} | {String(item.symbol ?? item.sym ?? item.ticket ?? item.id)}</strong>
                      <span className={`badge ${pendingTone(item.status)}`}>{String(item.status || "waiting")}</span>
                    </div>
                    <span className="muted small">{pendingDetail(item)} · {item.file_name}</span>
                    <div className="actions">
                      <button type="button" className="btn mini" onClick={() => void copyPending(item)}>{vn ? "Sao chép" : "Copy"}</button>
                      <button type="button" className="btn mini danger" onClick={() => void deletePending(item)} disabled={pendingAction === item.id}>{pendingAction === item.id ? "…" : pendingDeleteId === item.id ? (vn ? "Xóa lần nữa" : "Delete again") : (vn ? "Xóa" : "Delete")}</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function isPendingWaiting(status: string): boolean {
  return !["done", "executed", "closed", "expired", "cancelled", "canceled"].includes(status.toLowerCase());
}

function pendingTone(status: string): "ok" | "warn" | "error" | "neutral" {
  const value = status.toLowerCase();
  if (["waiting", "pending", "ready"].includes(value)) return "ok";
  if (["error", "failed", "blocked"].includes(value)) return "error";
  if (["done", "executed", "closed", "expired", "cancelled", "canceled"].includes(value)) return "neutral";
  return "warn";
}

function pendingDetail(item: LegacyPendingItem): string {
  const when = [item.date, item.time].filter(Boolean).join(" ") || String(item.execute_at ?? "—");
  if (item.filter !== undefined) return `filter=${String(item.filter || "all")} · sym ${String(item.sym || "all")} · ${when}`;
  return `${pendingOrderType(item.type)} · lot ${String(item.lot ?? "—")} · ${when}`;
}

function pendingOrderType(value: unknown): string {
  const normalized = String(value ?? "").toUpperCase();
  if (normalized === "0" || normalized === "BUY") return "BUY";
  if (normalized === "1" || normalized === "SELL") return "SELL";
  return normalized || "—";
}
