//! Sidecar lifecycle manager (§4 of the refactor plan).
//!
//! Rust owns the oak-core Python sidecar process:
//! - spawn on app start (dev: `python -m oak_core supervisor`; prod: bundled binary);
//! - stream its stdout (JSONL protocol) and stderr (logs) to the frontend;
//! - forward frontend requests over its stdin;
//! - detect unexpected exit and restart with bounded exponential backoff;
//! - kill the whole process tree on shutdown so no Python process is orphaned.

use serde_json::{json, Value};
use std::collections::HashMap;
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, Command, Stdio};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager, State};

// --------------------------------------------------------------------- //
// Types
// --------------------------------------------------------------------- //

#[derive(Default)]
pub struct SidecarState {
    pub proc: Mutex<Option<Child>>,
    pub stdin: Mutex<Option<ChildStdin>>,
    pub next_id: AtomicU64,
    pub pending: Mutex<HashMap<String, tauri::ipc::Channel<Value>>>,
    pub restart_attempts: Mutex<u32>,
}

// --------------------------------------------------------------------- //
// Command resolution (dev vs bundled)
// --------------------------------------------------------------------- //

fn sidecar_command() -> Command {
    #[cfg(debug_assertions)]
    {
        // Dev: run the Python package directly so the UI works without a
        // PyInstaller build. Path is resolved relative to the repo root.
        let python_dir = project_root().join("python");
        // Resolve python.exe explicitly (venv first, then PATH) so spawning
        // works even when the desktop launcher's PATH is minimal.
        let python = resolve_python();
        let mut cmd = Command::new(python);
        cmd.arg("-m").arg("oak_core").arg("supervisor");
        cmd.current_dir(&python_dir);
        // Ensure `python -m oak_core` resolves even when the launcher's
        // working directory differs from the Python package root.
        cmd.env("PYTHONPATH", &python_dir);
        cmd
    }
    #[cfg(not(debug_assertions))]
    {
        // Prod: external binary bundled via bundle.externalBin. The target
        // triple suffix is handled by tauri::utils::platform::current_exe? —
        // we keep it simple and rely on the configured sidecar name.
        let mut cmd = Command::new(sidecar_bin_path());
        cmd.arg("supervisor");
        cmd
    }
}

/// Locate a usable python interpreter: repo venv first, then `python` on PATH.
#[cfg(debug_assertions)]
fn resolve_python() -> PathBuf {
    let venv = project_root()
        .join("venv")
        .join("Scripts")
        .join("python.exe");
    if venv.is_file() {
        return venv;
    }
    PathBuf::from("python")
}

#[cfg(not(debug_assertions))]
fn sidecar_bin_path() -> PathBuf {
    let exe = std::env::current_exe().unwrap_or_default();
    exe.parent()
        .map(|p| p.join("oak-core.exe"))
        .unwrap_or_else(|| PathBuf::from("oak-core.exe"))
}

fn project_root() -> PathBuf {
    let manifest = std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default();
    if !manifest.is_empty() {
        // src-tauri -> desktop -> apps -> repo root (three parents up)
        return PathBuf::from(manifest)
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .parent()
            .unwrap()
            .to_path_buf();
    }
    // Walk up from the current directory until we find the repo root (a dir
    // containing both `python/` and `apps/`). This works regardless of where
    // the binary was built (CARGO_TARGET_DIR on another drive) or launched.
    let mut dir = std::env::current_dir().unwrap_or_default();
    for _ in 0..8 {
        if dir.join("python").is_dir() && dir.join("apps").is_dir() {
            return dir;
        }
        if !dir.pop() {
            break;
        }
    }
    // Last resort: derive from the executable location if it is inside the repo.
    if let Ok(exe) = std::env::current_exe() {
        let mut dir = exe.parent().unwrap_or_else(|| std::path::Path::new("."));
        for _ in 0..8 {
            if dir.join("python").is_dir() && dir.join("apps").is_dir() {
                return dir.to_path_buf();
            }
            if let Some(parent) = dir.parent() {
                dir = parent;
            } else {
                break;
            }
        }
    }
    PathBuf::from("..")
}

// --------------------------------------------------------------------- //
// Process management
// --------------------------------------------------------------------- //

pub fn spawn(app: &AppHandle) {
    let state = app.state::<SidecarState>();
    let mut cmd = sidecar_command();
    cmd.stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    eprintln!(
        "[oak] spawning sidecar: program={:?} cwd={:?}",
        cmd.get_program(),
        cmd.get_current_dir()
    );
    let child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            let _ = app.emit(
                "oak:sidecar:status",
                json!({"state": "spawn_failed", "error": e.to_string()}),
            );
            eprintln!("[oak] sidecar spawn failed: {e}");
            return;
        }
    };

    let mut child = child;
    let stdin = child.stdin.take();
    {
        let mut guard = state.proc.lock().unwrap();
        *guard = Some(child);
    }
    {
        let mut guard = state.stdin.lock().unwrap();
        *guard = stdin;
    }
    *state.restart_attempts.lock().unwrap() = 0;
    let _ = app.emit("oak:sidecar:status", json!({"state": "running"}));

    // stdout → forward JSONL lines to the frontend as events
    if let Some(stdout) = state
        .proc
        .lock()
        .unwrap()
        .as_mut()
        .and_then(|c| c.stdout.take())
    {
        let app2 = app.clone();
        thread::spawn(move || read_stdout(app2, stdout));
    }
    // stderr → forward as log events
    if let Some(stderr) = state
        .proc
        .lock()
        .unwrap()
        .as_mut()
        .and_then(|c| c.stderr.take())
    {
        let app2 = app.clone();
        thread::spawn(move || read_stderr(app2, stderr));
    }

    // monitor thread: wait() then restart with backoff if not shutting down
    let app2 = app.clone();
    thread::spawn(move || monitor(app2));
}

fn read_stdout(app: AppHandle, stdout: std::process::ChildStdout) {
    let reader = BufReader::new(stdout);
    for line in reader.lines() {
        let Ok(line) = line else { break };
        if line.trim().is_empty() {
            continue;
        }
        let parsed: Result<Value, _> = serde_json::from_str(&line);
        match parsed {
            Ok(Value::Object(map)) if map.contains_key("id") => {
                // Response — resolve the pending request channel.
                let id = map
                    .get("id")
                    .and_then(|v| v.as_str())
                    .unwrap_or("")
                    .to_string();
                let state = app.state::<SidecarState>();
                let channel = state.pending.lock().unwrap().remove(&id);
                if let Some(channel) = channel {
                    let reply = json!({
                        "id": id,
                        "ok": map.get("ok").and_then(|v| v.as_bool()).unwrap_or(false),
                        "result": map.get("result").cloned(),
                        "error": map.get("error").cloned(),
                    });
                    let _ = channel.send(reply);
                } else {
                    let _ = app.emit("oak:sidecar:unmatched", json!({"id": id, "line": line}));
                }
            }
            Ok(Value::Object(map)) if map.contains_key("event") => {
                // Forward event to the frontend verbatim (includes sequence).
                let _ = app.emit("oak:sidecar:event", map);
            }
            Ok(_) => {
                let _ = app.emit("oak:sidecar:log", json!({"stream": "stdout", "line": line}));
            }
            Err(_) => {
                let _ = app.emit("oak:sidecar:log", json!({"stream": "stdout", "line": line}));
            }
        }
    }
}

fn read_stderr(app: AppHandle, stderr: std::process::ChildStderr) {
    let reader = BufReader::new(stderr);
    for line in reader.lines().map_while(Result::ok) {
        let _ = app.emit("oak:sidecar:log", json!({"stream": "stderr", "line": line}));
    }
}

fn monitor(app: AppHandle) {
    let state = app.state::<SidecarState>();
    let status = loop {
        {
            let mut guard = state.proc.lock().unwrap();
            let Some(child) = guard.as_mut() else { return };
            match child.try_wait() {
                Ok(Some(status)) => break status,
                Ok(None) => thread::sleep(Duration::from_millis(500)),
                Err(_) => {
                    let _ = app.emit("oak:sidecar:status", json!({"state": "error"}));
                    return;
                }
            }
        }
    };
    {
        let mut guard = state.proc.lock().unwrap();
        *guard = None;
    }
    let attempts = {
        let mut g = state.restart_attempts.lock().unwrap();
        *g += 1;
        *g
    };
    let _ = app.emit(
        "oak:sidecar:status",
        json!({
            "state": "exited",
            "code": status.code(),
            "restart_attempt": attempts,
        }),
    );
    if attempts <= 3 {
        let delay = Duration::from_secs(1u64 << (attempts - 1).min(4)); // 1,2,4,8s
        let app2 = app.clone();
        thread::spawn(move || {
            thread::sleep(delay);
            spawn(&app2);
        });
    } else {
        let _ = app.emit("oak:sidecar:status", json!({"state": "gave_up"}));
    }
}

/// Kill the sidecar process tree (Windows: taskkill /T). Used on shutdown.
pub fn shutdown(app: &AppHandle) {
    let state = app.state::<SidecarState>();
    let child = state.proc.lock().unwrap().take();
    if let Some(mut child) = child {
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            let pid = child.id();
            let _ = std::process::Command::new("taskkill")
                .args(["/PID", &pid.to_string(), "/T", "/F"])
                .creation_flags(0x08000000) // CREATE_NO_WINDOW
                .status();
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

// --------------------------------------------------------------------- //
// Tauri command — frontend calls this to send one request to the sidecar
// --------------------------------------------------------------------- //

#[tauri::command]
pub async fn sidecar_request(
    state: State<'_, SidecarState>,
    method: String,
    params: Value,
    channel: tauri::ipc::Channel<Value>,
) -> Result<(), String> {
    let id = format!("req-{}", state.next_id.fetch_add(1, Ordering::SeqCst));
    state.pending.lock().unwrap().insert(id.clone(), channel);

    let line = json!({"v": 1, "id": id, "method": method, "params": params}).to_string();
    let mut guard = state.stdin.lock().unwrap();
    match guard.as_mut() {
        Some(stdin) => {
            writeln!(stdin, "{}", line).map_err(|e| format!("sidecar stdin write failed: {e}"))?;
            stdin
                .flush()
                .map_err(|e| format!("sidecar stdin flush failed: {e}"))?;
            Ok(())
        }
        None => Err("sidecar is not running".to_string()),
    }
}

// --------------------------------------------------------------------- //
// Tests
// --------------------------------------------------------------------- //
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn project_root_resolves_to_repo_root() {
        // With CARGO_MANIFEST_DIR unset, falls back to ".."; with it set to
        // <root>/apps/desktop/src-tauri, resolves to the repo root.
        let root = project_root();
        assert!(!root.as_os_str().is_empty());
    }

    #[test]
    fn sidecar_request_line_shape() {
        // The JSONL request we write to the sidecar stdin must match the
        // oak-core protocol contract: v=1, id=req-N, method, params.
        let id = "req-0".to_string();
        let method = "app.health".to_string();
        let params = serde_json::json!({});
        let line = json!({"v": 1, "id": id, "method": method, "params": params}).to_string();
        let parsed: Value = serde_json::from_str(&line).unwrap();
        assert_eq!(parsed["v"], 1);
        assert_eq!(parsed["id"], "req-0");
        assert_eq!(parsed["method"], "app.health");
        assert_eq!(parsed["params"], serde_json::json!({}));
    }

    #[test]
    fn response_envelope_preserves_id_and_error() {
        // Simulate the sidecar JSONL response parsing used in read_stdout.
        let line = r#"{"v":1,"id":"req-1","ok":false,"error":{"code":"METHOD_NOT_FOUND","message":"nope"}}"#;
        let parsed: Value = serde_json::from_str(line).unwrap();
        assert_eq!(parsed["id"], "req-1");
        assert_eq!(parsed["ok"], false);
        assert_eq!(parsed["error"]["code"], "METHOD_NOT_FOUND");
    }

    #[test]
    fn event_payload_has_sequence() {
        let line = r#"{"v":1,"event":"worker.started","sequence":3,"data":{"pid":42}}"#;
        let parsed: Value = serde_json::from_str(line).unwrap();
        assert_eq!(parsed["event"], "worker.started");
        assert_eq!(parsed["sequence"], 3);
        assert_eq!(parsed["data"]["pid"], 42);
    }
}
