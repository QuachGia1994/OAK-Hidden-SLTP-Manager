//! OAK Manager — Tauri v2 shell.
//!
//! Rust is deliberately thin (§1): app lifecycle, sidecar lifecycle,
//! stdin/stdout bridge, event forwarding. All business logic lives in the
//! Python oak-core sidecar.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod sidecar;

use sidecar::SidecarState;
use tauri::Manager;

fn main() {
    tauri::Builder::default()
        .manage(SidecarState::default())
        .invoke_handler(tauri::generate_handler![sidecar::sidecar_request, sidecar::open_classic_ui])
        .setup(|app| {
            #[cfg(not(debug_assertions))]
            sidecar::ensure_data_files(app.handle());
            sidecar::spawn(app.handle());
            Ok(())
        })
        .on_window_event(|window, event| {
            // Stop the sidecar when the main window closes (no orphan Python).
            if let tauri::WindowEvent::Destroyed = event {
                sidecar::shutdown(window.app_handle());
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
