import { useCallback, useEffect, useMemo, useState } from "react";
import { request, IpcError } from "../ipc/bridge";
import type {
  Profile,
  ProfilesList,
  ProfileSecretClear,
  ProfileSecretStatus,
  ProfileStart,
  ProfileStop,
} from "../ipc/types";
import { useLocale } from "../contexts";

type DraftValue = string | boolean;
type ProfileDraft = Record<string, DraftValue>;

const TEXT_FIELDS = [
  ["profile_name", "Profile name"],
  ["path", "Terminal path"],
  ["magic", "Magic number"],
  ["symbol", "Symbol filter"],
  ["tele_chat", "Telegram chat ID"],
  ["tele_admin", "Telegram admin chat ID"],
] as const;

/** Rendered inside the Telegram section instead of the generic field grid. */
const TELEGRAM_TEXT_KEYS: ReadonlySet<string> = new Set(["tele_chat", "tele_admin"]);

const BOOL_FIELDS = [
  ["mt5_portable", "Portable terminal"],
] as const;

function toDraft(profile: Profile | undefined): ProfileDraft | null {
  if (!profile) return null;
  const draft: ProfileDraft = {};
  for (const [key] of TEXT_FIELDS) draft[key] = String(profile[key as keyof Profile] ?? "");
  for (const [key] of BOOL_FIELDS) draft[key] = asBoolean(profile[key as keyof Profile]);
  return draft;
}

function asBoolean(value: unknown): boolean {
  return value === true || value === 1 || value === "1" || value === "true" || value === "True";
}

/** Full non-secret profile map/editor mirroring Native Qt. */
export function ProfilesPage() {
  const { t } = useLocale();
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [deleteArmed, setDeleteArmed] = useState(false);
  const [newName, setNewName] = useState("");
  const [newPath, setNewPath] = useState("");
  const [newMagic, setNewMagic] = useState("");
  const [adding, setAdding] = useState(false);
  // Telegram bot token: write-only — never prefilled from the sidecar.
  const [secretStatus, setSecretStatus] = useState<ProfileSecretStatus | null>(null);
  const [tokenInput, setTokenInput] = useState("");
  const [tokenBusy, setTokenBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await request<ProfilesList>("profiles.list");
      const next = res.profiles ?? [];
      setProfiles(next);
      setSelected((current) => current && next.some((profile) => profile.profile_name === current)
        ? current
        : next[0]?.profile_name ?? "");
      setError(null);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const timer = window.setInterval(() => void refresh(), 3000);
    return () => window.clearInterval(timer);
  }, [refresh]);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.profile_name === selected),
    [profiles, selected],
  );
  const keyringDown = secretStatus !== null && !secretStatus.keyring_available;

  useEffect(() => {
    if (!dirty) setDraft(toDraft(selectedProfile));
  }, [dirty, selectedProfile]);

  const loadSecretStatus = useCallback(async (name: string) => {
    if (!name) {
      setSecretStatus(null);
      return;
    }
    try {
      setSecretStatus(await request<ProfileSecretStatus>("profile.secrets.status", { profile: name }));
    } catch {
      setSecretStatus(null);
    }
  }, []);

  useEffect(() => {
    setTokenInput("");
    void loadSecretStatus(selected);
  }, [selected, loadSecretStatus]);

  const selectProfile = (name: string) => {
    if (dirty && !window.confirm(t.unsavedChanges ?? "Discard unsaved changes?")) return;
    setSelected(name);
    setDirty(false);
    setNotice(null);
    setDeleteArmed(false);
  };

  const changeProfileState = async (profile: Profile) => {
    const running = profile.status === "running";
    setBusy(profile.profile_name);
    setError(null);
    try {
      const result = await request<ProfileStart | ProfileStop>(running ? "profile.stop" : "profile.start", { profile: profile.profile_name });
      if ("reason" in result && result.reason) setNotice(result.reason);
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const updateDraft = (key: string, value: DraftValue) => {
    setDraft((current) => current ? { ...current, [key]: value } : current);
    setDirty(true);
    setNotice(null);
    setDeleteArmed(false);
  };

  const save = async () => {
    if (!selected || !draft) {
      setNotice(t.noProfiles);
      return;
    }
    const updates: ProfileDraft = { ...draft };
    const magicText = String(updates.magic ?? "").trim();
    if (magicText !== "" && !/^-?\d+$/.test(magicText)) {
      setError(t.magicInvalid);
      return;
    }
    updates.magic = (magicText === "" ? -1 : Number(magicText)) as unknown as DraftValue;
    setBusy("save");
    setError(null);
    setNotice(null);
    try {
      const result = await request<Profile>("profile.update", { profile: selected, updates });
      setSelected(result.profile_name);
      setDirty(false);
      setNotice(t.profileSaved);
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const saveToken = async () => {
    if (!selected) {
      setNotice(t.noProfiles);
      return;
    }
    const token = tokenInput.trim();
    if (!token) {
      setError(t.teleTokenRequired);
      return;
    }
    setTokenBusy("token-save");
    setError(null);
    setNotice(null);
    try {
      const status = await request<ProfileSecretStatus>("profile.secrets.set_token", {
        profile: selected,
        token,
      });
      setSecretStatus(status);
      setTokenInput("");
      setNotice(t.teleTokenSaved);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setTokenBusy(null);
    }
  };

  const clearToken = async () => {
    if (!selected) {
      setNotice(t.noProfiles);
      return;
    }
    if (!window.confirm(`${t.teleTokenClearConfirm} (${selected})`)) return;
    setTokenBusy("token-clear");
    setError(null);
    setNotice(null);
    try {
      const result = await request<ProfileSecretClear>("profile.secrets.clear_token", { profile: selected });
      setSecretStatus({
        profile: result.profile,
        tele_token_configured: result.tele_token_configured,
        keyring_available: result.keyring_available,
      });
      setTokenInput("");
      if (result.cleared) setNotice(t.teleTokenCleared);
      else setError(t.teleTokenClearFailed);
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setTokenBusy(null);
    }
  };

  const duplicate = async () => {
    if (!selected) return;
    setBusy("duplicate");
    setError(null);
    try {
      const result = await request<Profile>("profile.duplicate", { profile: selected });
      setSelected(result.profile_name);
      setDirty(false);
      setNotice(t.profileDuplicated);
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
    try {
      const result = await request<Profile>("profile.add", {
        profile_name: newName.trim(),
        path: newPath.trim(),
        magic: newMagic ? Number(newMagic) : -1,
      });
      setNewName("");
      setNewPath("");
      setNewMagic("");
      setSelected(result.profile_name);
      setDirty(false);
      setNotice(t.profileAdded);
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError && /already exists/i.test(e.message)
        ? t.profileDuplicate
        : `${t.profileAddError} ${String(e instanceof IpcError ? e.message : e)}`);
    } finally {
      setAdding(false);
    }
  };

  const addBlankProfile = async () => {
    const names = new Set(profiles.map((profile) => profile.profile_name));
    const root = "NewProfile";
    let name = root;
    let index = 2;
    while (names.has(name)) name = `${root} ${index++}`;
    setBusy("add");
    setError(null);
    try {
      const result = await request<Profile>("profile.add", { profile_name: name, path: "", magic: -1 });
      setSelected(result.profile_name);
      setDirty(false);
      setNotice(t.profileAdded);
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  const deleteSelected = async () => {
    if (!selected) {
      setNotice(t.noProfiles);
      return;
    }
    if (!deleteArmed) {
      setDeleteArmed(true);
      setNotice(`${t.deleteConfirm} ${selected}`);
      return;
    }
    setBusy("delete");
    setError(null);
    try {
      await request("profile.delete", { profile: selected });
      setDeleteArmed(false);
      setDirty(false);
      setNotice(t.profileDeleted);
      await refresh();
    } catch (e) {
      setError(e instanceof IpcError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    const saveShortcut = () => { void save(); };
    const clearGuard = () => setDeleteArmed(false);
    window.addEventListener("oak:save", saveShortcut);
    window.addEventListener("oak:clear-guards", clearGuard);
    return () => {
      window.removeEventListener("oak:save", saveShortcut);
      window.removeEventListener("oak:clear-guards", clearGuard);
    };
  });

  return (
    <main className="content profiles-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">{t.profileMap}</p>
          <h1>{t.profilesTitle}</h1>
        </div>
        <button type="button" className="btn" onClick={() => void refresh()} disabled={loading}>{loading ? "…" : t.refresh}</button>
      </div>
      {error && <section className="panel error"><span className="badge error">{t.error}</span><p>{error}</p></section>}
      {notice && <p className="hint">{notice}</p>}

      <section className="panel add-profile-panel">
        <div className="panel-heading"><h2>{t.addProfile}</h2><span className="muted small">{t.profileStoredHint}</span></div>
        <div className="field-grid">
          <label className="field"><span>{t.profileName}</span><input type="text" value={newName} onChange={(e) => setNewName(e.target.value)} /></label>
          <label className="field"><span>{t.terminalPath}</span><input type="text" value={newPath} onChange={(e) => setNewPath(e.target.value)} /></label>
          <label className="field"><span>{t.magic}</span><input type="text" value={newMagic} onChange={(e) => setNewMagic(e.target.value)} /></label>
        </div>
        <div className="actions"><button type="button" className="btn primary" onClick={() => void addProfile()} disabled={adding}>{adding ? "…" : t.createProfile}</button></div>
      </section>

      <div className="profile-workspace">
        <section className="panel profile-map-panel">
          <div className="panel-heading"><h2>{t.profileMap}</h2><span className="mono muted">{profiles.length}</span></div>
          <div className="profile-list">
            {profiles.map((profile) => (
              <ProfileCard
                key={profile.profile_name}
                profile={profile}
                selected={selected === profile.profile_name}
                busy={busy === profile.profile_name}
                onSelect={() => selectProfile(profile.profile_name)}
                onToggle={() => void changeProfileState(profile)}
                t={t}
              />
            ))}
            {!loading && profiles.length === 0 && <p className="muted">{t.noProfiles}</p>}
          </div>
        </section>

        <section className="panel profile-editor-panel">
          <div className="panel-heading">
            <div><h2>{draft?.profile_name || t.noProfileSelected}</h2><p className="muted small">{dirty ? t.unsavedChanges : t.profileSavedHint}</p></div>
            <span className={`badge ${selectedProfile?.status === "running" ? "ok" : "neutral"}`}>{selectedProfile?.status ?? "idle"}</span>
          </div>
          <div className="actions profile-editor-actions">
            <button type="button" className="btn primary" onClick={() => void save()} disabled={!draft || busy !== null}>{busy === "save" ? "…" : t.save}</button>
            <button type="button" className="btn" onClick={() => void duplicate()} disabled={!selected || busy !== null}>{busy === "duplicate" ? "…" : t.duplicate}</button>
            <button type="button" className="btn" onClick={() => void addBlankProfile()} disabled={busy !== null}>{t.addNew}</button>
            <button type="button" className="btn danger" onClick={() => void deleteSelected()} disabled={!selected || busy !== null}>{busy === "delete" ? "…" : deleteArmed ? t.deleteAgain : t.delete}</button>
          </div>
          {draft ? (
            <>
              <div className="field-grid profile-editor-grid">
                {TEXT_FIELDS.filter(([key]) => !TELEGRAM_TEXT_KEYS.has(key)).map(([key, label]) => (
                  <label className="field" key={key}>
                    <span>{label}</span>
                    <input type="text" value={String(draft[key] ?? "")} onChange={(e) => updateDraft(key, e.target.value)} />
                  </label>
                ))}
                {BOOL_FIELDS.map(([key, label]) => (
                  <label className="field bool" key={key}>
                    <span>{label}</span>
                    <input type="checkbox" checked={Boolean(draft[key])} onChange={(e) => updateDraft(key, e.target.checked)} />
                  </label>
                ))}
              </div>
              <section className="panel telegram-section">
                <div className="panel-heading">
                  <h2>{t.telegramSection}</h2>
                  <div>
                    <span className={`badge ${secretStatus?.tele_token_configured ? "ok" : "neutral"}`}>
                      {secretStatus?.tele_token_configured ? t.teleTokenConfigured : t.teleTokenMissing}
                    </span>{" "}
                    <span className={`badge ${keyringDown ? "error" : "neutral"}`}>
                      {keyringDown ? t.keyringUnavailable : t.keyringAvailable}
                    </span>
                  </div>
                </div>
                <div className="field-grid">
                  <label className="field">
                    <span>{t.teleChat}</span>
                    <input type="text" value={String(draft.tele_chat ?? "")} onChange={(e) => updateDraft("tele_chat", e.target.value)} />
                  </label>
                  <label className="field">
                    <span>{t.teleAdmin}</span>
                    <input type="text" value={String(draft.tele_admin ?? "")} onChange={(e) => updateDraft("tele_admin", e.target.value)} />
                  </label>
                  <label className="field">
                    <span>{t.teleToken}</span>
                    <input
                      type="password"
                      autoComplete="off"
                      placeholder={t.teleTokenPlaceholder}
                      value={tokenInput}
                      onChange={(e) => setTokenInput(e.target.value)}
                    />
                  </label>
                </div>
                <p className="muted small">{t.teleTokenWriteOnly}</p>
                {keyringDown && <p className="hint">{t.keyringUnavailable}</p>}
                <div className="actions">
                  <button
                    type="button"
                    className="btn primary"
                    onClick={() => void saveToken()}
                    disabled={tokenBusy !== null || !tokenInput.trim() || keyringDown}
                  >
                    {tokenBusy === "token-save" ? "…" : t.teleTokenSave}
                  </button>
                  <button
                    type="button"
                    className="btn danger"
                    onClick={() => void clearToken()}
                    disabled={tokenBusy !== null || !secretStatus?.tele_token_configured}
                  >
                    {tokenBusy === "token-clear" ? "…" : t.teleTokenClear}
                  </button>
                </div>
              </section>
              <div className="masked-secrets">
                <strong>{t.maskedSecrets}</strong>
                <span className="mono">Telegram token: ••••</span>
                <span>{t.secretBoundary}</span>
              </div>
            </>
          ) : (
            <div className="empty-state"><p>{t.noProfileSelected}</p></div>
          )}
        </section>
      </div>
    </main>
  );
}

function ProfileCard({
  profile,
  selected,
  busy,
  onSelect,
  onToggle,
  t,
}: {
  profile: Profile;
  selected: boolean;
  busy: boolean;
  onSelect: () => void;
  onToggle: () => void;
  t: ReturnType<typeof useLocale>["t"];
}) {
  const running = profile.status === "running";
  return (
    <div className={`profile-card panel ${running ? "running" : ""} ${selected ? "selected" : ""}`}>
      <div className="profile-head">
        <span className={`status-dot ${running ? "online" : "offline"}`} aria-hidden="true" />
        <h2>{profile.profile_name}</h2>
        <span className="muted mono">{profile.pid ? `PID ${profile.pid}` : profile.path ? profile.path.split(/[\\/]/).pop() : "MT5"}</span>
      </div>
      <div className="profile-card-meta">
        <span className="badge neutral">{profile.copy_role || "None"}</span>
        <span className="badge neutral">SL/TP {asBoolean(profile.visible_sltp) ? t.yes : t.no}</span>
        <span className={`badge ${asBoolean(profile.copy_kill_switch) ? "error" : "ok"}`}>{asBoolean(profile.copy_kill_switch) ? "KILL" : "ARMED"}</span>
      </div>
      <div className="actions">
        <button type="button" className="btn" onClick={onSelect}>{selected ? t.selected : t.use}</button>
        <button type="button" className={running ? "btn danger" : "btn primary"} onClick={onToggle} disabled={busy}>{busy ? "…" : running ? t.stop : t.start}</button>
      </div>
    </div>
  );
}
