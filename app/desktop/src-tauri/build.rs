fn main() {
    println!("cargo:rerun-if-env-changed=WORKBENCH_BUILD_ID");
    println!("cargo:rerun-if-env-changed=WORKBENCH_SOURCE_FINGERPRINT");
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "initial_route", "engine_status", "retry_engine", "close_startup", "open_workbench",
            "open_logs", "native_intake", "native_clipboard_intake", "native_stream_save", "native_save", "native_client_state", "native_window_recovery", "native_window_action", "native_accessibility"
        ])
    )).expect("Desktop permission manifest failed");
}
