import { useCallback, useEffect, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import { Profile, ProfilesList, ProfileStart, ProfileStop } from "../ipc/types";
import { useLocale } from "../contexts";

/**
 * Phase 2 — Profiles page (§9).
 * Lists configured MT5 profiles, starts/stops one profile-worker each, and
 * shows per-profile status (running/stopped + pid).
 */
export function ProfilesPage() {
  const { t } = useLocale();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // add-profile form
  const [newName, setNewName] = useState("");
  const [newPath, setNewPath] = useState("");
  const [newMagic, setNewMagic] = useState("");
  const [adding, setAdding] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const res = await request<ProfilesList>("profiles.list");
      setProfiles(res.profiles ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const start = async (name: string) => {
    setBusy(name);
    setError(null);
    try {
      const res = await request<ProfileStart>("profile.start", { profile: name });
      if (!res.started && res.reason) {
        setError(`profile.start: ${res.reason}`);
      }
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const stop = async (name: string) => {
    setBusy(name);
    setError(null);
    try {
      const res = await request<ProfileStop>("profile.stop", { profile: name });
      if (!res.stopped && res.reason) {
        setError(`profile.stop: ${res.reason}`);
      }
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const addProfile = async () => {
    if (!newName.trim()) {
      setError(t.profileNameRequired);
      return;
    }
    setAdding(true);
    setError(null);
    setNotice(null);
    try {
      await request("profile.add", {
        profile_name: newName.trim(),
        path: newPath.trim(),
        magic: newMagic ? Number(newMagic) : -1,
      });
      setNotice(t.profileAdded);
      setNewName("");
      setNewPath("");
      setNewMagic("");
      await refresh();
    } catch (e) {
      if (e instanceof IpcError && /already exists/i.test(e.message)) {
        setError(t.profileDuplicate);
      } else {
        setError(t.profileAddError + " " + String(e instanceof IpcError ? e.message : e));
      }
    } finally {
      setAdding(false);
    }
  };

  return (
    <div className="content">
      <h1>{t.profilesTitle}</h1>
      {loading && <p className="muted">{t.loadingProfiles}</p>}
      {error && (
        <section className="panel error">
          <span className="badge error">{t.error}</span>
          <p>{error}</p>
        </section>
      )}
      {notice && <p className="hint">{notice}</p>}

      <section className="panel">
        <h2>{t.addProfile}</h2>
        <div className="field-grid">
          <label className="field">
            <span>{t.profileName}</span>
            <input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} />
          </label>
          <label className="field">
            <span>{t.terminalPath}</span>
            <input type="text" value={newPath} onChange={(e) => setNewPath(e.target.value)} />
          </label>
          <label className="field">
            <span>{t.magic}</span>
            <input type="text" value={newMagic} onChange={(e) => setNewMagic(e.target.value)} />
          </label>
        </div>
        <div className="actions">
          <button className="btn primary" onClick={() => void addProfile()} disabled={adding}>
            {adding ? "…" : t.createProfile}
          </button>
        </div>
      </section>

      {!loading && profiles.length === 0 && (
        <p className="muted">{t.noProfiles}</p>
      )}

      <div className="profile-list">
        {profiles.map((p) => (
          <ProfileCard
            key={p.profile_name}
            profile={p}
            busy={busy === p.profile_name}
            onStart={() => start(p.profile_name)}
            onStop={() => stop(p.profile_name)}
          />
        ))}
      </div>
    </div>
  );
}

function ProfileCard({
  profile,
  busy,
  onStart,
  onStop,
}: {
  profile: Profile;
  busy: boolean;
  onStart: () => void;
  onStop: () => void;
}) {
  const { t } = useLocale();
  const running = profile.status === "running";
  const tone = running ? "ok" : "neutral";
  const terminalName = profile.path ? profile.path.split(/[\\/]/).pop() : "—";

  return (
    <section className={`panel profile-card ${running ? "running" : ""}`}>
      <div className="profile-head">
        <span className={`badge ${tone}`}>{running ? t.running.toUpperCase() : t.stopped.toUpperCase()}</span>
        <h2 className="mono">{profile.profile_name}</h2>
        {profile.pid != null && (
          <span className="mono pid">pid {profile.pid}</span>
        )}
      </div>

      <dl className="kv">
        <dt>{t.terminal}</dt>
        <dd className="mono truncate" title={profile.path}>
          {terminalName}
        </dd>
        <dt>{t.visibleSltp}</dt>
        <dd>{profile.visible_sltp ? t.yes : t.no}</dd>
        <dt>{t.magic}</dt>
        <dd className="mono">{String(profile.magic ?? "—")}</dd>
        <dt>{t.sltpPair}</dt>
        <dd className="mono">
          {String(profile.sl ?? "—")} / {String(profile.tp ?? "—")}
        </dd>
        <dt>{t.copyRole}</dt>
        <dd>{profile.copy_role || "—"}</dd>
      </dl>

      <div className="actions">
        <button
          className={running ? "btn" : "btn primary"}
          onClick={onStart}
          disabled={busy || running}
        >
          {busy ? "…" : running ? t.running : t.start}
        </button>
        <button className="btn" onClick={onStop} disabled={busy || !running}>
          {t.stop}
        </button>
      </div>
    </section>
  );
}
