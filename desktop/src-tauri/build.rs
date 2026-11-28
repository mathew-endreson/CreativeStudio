fn main() {
    // The window's page comes from the local engine (http://127.0.0.1:<port>), a remote origin to Tauri's ACL: the
    // app's own commands are only reachable from it when they have generated permissions (allow-update-status, ...)
    // that capabilities/main.json grants.
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(&["update_status", "update_check", "update_install"])),
    )
    .expect("failed to run tauri-build");
}
