use serde::Serialize;
use std::io::{BufRead, BufReader, Write};
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::{atomic::{AtomicU64, Ordering}, Mutex, OnceLock};
#[cfg(windows)]
use std::os::windows::process::CommandExt;

struct BackendWorker {
    child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

static BACKEND_WORKER: OnceLock<Mutex<Option<BackendWorker>>> = OnceLock::new();
static REQUEST_SEQ: AtomicU64 = AtomicU64::new(1);

fn backend_worker() -> &'static Mutex<Option<BackendWorker>> {
    BACKEND_WORKER.get_or_init(|| Mutex::new(None))
}

fn spawn_backend() -> Result<BackendWorker, String> {
    let bridge = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .ok_or_else(|| "Cannot resolve application root".to_string())?
        .join("backend_bridge.py");
    let mut command = Command::new("python");
    command
        .arg(&bridge)
        .arg("--server")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null());
    #[cfg(windows)]
    command.creation_flags(0x08000000); // CREATE_NO_WINDOW
    let mut child = command
        .spawn()
        .map_err(|error| format!("backend process failed: {error}"))?;
    let stdin = child.stdin.take().ok_or_else(|| "backend stdin unavailable".to_string())?;
    let stdout = child.stdout.take().ok_or_else(|| "backend stdout unavailable".to_string())?;
    Ok(BackendWorker { child, stdin, stdout: BufReader::new(stdout) })
}

pub mod commands {
    use super::*;

    #[derive(Clone, Serialize)]
    pub struct RuntimeStatus {
        pub app: &'static str,
        pub version: &'static str,
        pub engine: &'static str,
    }

    #[tauri::command]
    pub fn runtime_status() -> RuntimeStatus {
        RuntimeStatus { app: "ROBOT SLTP Pro", version: "0.1.0", engine: "Tauri 2 + React" }
    }

    #[tauri::command]
    pub async fn backend_call(command: String, payload: String) -> Result<String, String> {
        tauri::async_runtime::spawn_blocking(move || {
            let worker_mutex = backend_worker();
            let mut guard = worker_mutex.lock().map_err(|_| "backend worker lock poisoned".to_string())?;
            if guard.as_mut().and_then(|worker| worker.child.try_wait().ok()).flatten().is_some() {
                *guard = None;
            }
            if guard.is_none() {
                *guard = Some(spawn_backend()?);
            }
            let worker = guard.as_mut().ok_or_else(|| "backend worker unavailable".to_string())?;
            let request_id = REQUEST_SEQ.fetch_add(1, Ordering::Relaxed);
            writeln!(worker.stdin, "{}\t{}\t{}", request_id, command, payload).map_err(|error| format!("backend write failed: {error}"))?;
            worker.stdin.flush().map_err(|error| format!("backend flush failed: {error}"))?;
            let mut line = String::new();
            worker.stdout.read_line(&mut line).map_err(|error| format!("backend read failed: {error}"))?;
            if line.is_empty() {
                *guard = None;
                return Err("backend worker exited unexpectedly".to_string());
            }
            let (response_id, response_json) = line.trim_end().split_once('\t').ok_or_else(|| "backend response missing request id".to_string())?;
            if response_id != request_id.to_string() {
                *guard = None;
                return Err(format!("backend response mismatch: expected {request_id}, got {response_id}"));
            }
            let response = response_json.to_string();
            if let Ok(value) = serde_json::from_str::<serde_json::Value>(&response) {
                if let Some(error) = value.get("error").and_then(|item| item.as_str()) {
                    return Err(error.to_string());
                }
            }
            Ok(response)
        })
        .await
        .map_err(|error| format!("backend worker panicked: {error}"))?
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![commands::runtime_status, commands::backend_call])
        .run(tauri::generate_context!())
        .expect("error while running ROBOT SLTP Pro");
}
