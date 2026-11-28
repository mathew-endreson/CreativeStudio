//! The desktop shell. It starts the Python engine from the app's resources, waits for the engine's first stdout
//! line (`BLUXTECH_READY {"port", "token", ...}`), opens the main window on the engine's boot link (which sets the
//! session cookie), and stops the engine's whole process tree when the app exits.
//!
//! Dev: set BLUXTECH_ENGINE_URL (for example `http://127.0.0.1:8766/boot/<token>`) and the shell opens that URL
//! instead of starting an engine. Such a run never updates itself (see `update_policy`).
//!
//! Updates: the Tauri updater plugin against the release channel configured in tauri.conf.json (a GitHub release's
//! `latest.json`), driven by the three `update_*` commands so the UI can ask the customer first, show progress,
//! and so the engine is stopped before the installer replaces files. An operator may point an installed copy at
//! another manifest with `<app local data>\updater.json` (`{"endpoint": "https://..."}`): that is how a release
//! is rehearsed before it is published.

use std::ffi::OsString;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use serde::Serialize;
use tauri::{AppHandle, Emitter, Manager, RunEvent, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::{DialogExt, MessageDialogKind};
use tauri_plugin_updater::UpdaterExt;

#[derive(serde::Deserialize, Clone, Debug)]
struct Ready {
    port: u16,
    token: String,
}

struct Engine(Mutex<Option<Child>>);

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

/// `resource_dir()` comes back canonicalized, which on Windows means the `\\?\` verbatim prefix. A junction whose
/// target carries that prefix does not resolve, and PATH entries carrying it confuse some tools, so the engine gets
/// the plain `C:\...` form. (`\\?\UNC\` network paths are left alone.)
fn plain(p: PathBuf) -> PathBuf {
    let s = p.to_string_lossy();
    match s.strip_prefix(r"\\?\") {
        Some(rest) if !rest.starts_with("UNC\\") => PathBuf::from(rest),
        _ => p,
    }
}

fn resources(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = plain(app.path().resource_dir().map_err(|e| e.to_string())?);
    // `bundle.resources: ["resources/**/*"]` keeps the folder name under the resource dir.
    let nested = dir.join("resources");
    Ok(if nested.is_dir() { nested } else { dir })
}

fn spawn_engine(app: &AppHandle) -> Result<(Child, Ready), String> {
    let res = resources(app)?;
    let python = res.join("python").join("python.exe");
    let engine_dir = res.join("engine");
    if !python.exists() {
        return Err(format!("The Python runtime is missing:\n{}", python.display()));
    }
    if !engine_dir.join("bluxtech_engine").is_dir() {
        return Err(format!("The engine is missing:\n{}", engine_dir.display()));
    }
    let mut path = OsString::new();
    for d in [
        res.join("python"),
        res.join("python").join("Scripts"),
        res.join("node"),
        res.join("ffmpeg").join("bin"),
    ] {
        path.push(d.as_os_str());
        path.push(";");
    }
    path.push(std::env::var_os("PATH").unwrap_or_default());

    let mut cmd = Command::new(&python);
    cmd.args(["-m", "bluxtech_engine", "--resources"])
        .arg(&res)
        .args(["--port", "0"])
        .current_dir(&engine_dir)
        .env("PATH", path)
        .env("PYTHONIOENCODING", "utf-8")
        .env("PYTHONUTF8", "1")
        .env("PYTHONUNBUFFERED", "1")
        // the engine watches this process and exits with it (an installer replacing files must find no engine)
        .env("BLUXTECH_PARENT_PID", std::process::id().to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::inherit());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd.spawn().map_err(|e| format!("Could not start the engine: {e}"))?;
    let stdout = child.stdout.take().ok_or("no stdout from the engine")?;
    let mut reader = BufReader::new(stdout);
    let mut line = String::new();
    let start = Instant::now();
    loop {
        line.clear();
        let n = reader.read_line(&mut line).map_err(|e| e.to_string())?;
        if n == 0 {
            let _ = child.kill();
            return Err("The engine exited before it was ready.".to_string());
        }
        if let Some(json) = line.strip_prefix("BLUXTECH_READY ") {
            let ready: Ready = serde_json::from_str(json.trim()).map_err(|e| format!("bad READY line: {e}"))?;
            // Keep draining stdout so the engine never blocks on a full pipe.
            std::thread::spawn(move || {
                let mut buf = String::new();
                while let Ok(n) = reader.read_line(&mut buf) {
                    if n == 0 {
                        break;
                    }
                    buf.clear();
                }
            });
            return Ok((child, ready));
        }
        if start.elapsed() > Duration::from_secs(180) {
            let _ = child.kill();
            return Err("The engine took too long to start.".to_string());
        }
    }
}

fn stop_engine(app: &AppHandle) {
    if let Some(mut child) = app.state::<Engine>().0.lock().unwrap().take() {
        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            let _ = Command::new("taskkill")
                .args(["/PID", &child.id().to_string(), "/T", "/F"])
                .creation_flags(CREATE_NO_WINDOW)
                .output();
        }
        let _ = child.kill();
        let _ = child.wait();
    }
}

fn fail(app: &AppHandle, msg: &str) {
    app.dialog()
        .message(format!("{msg}\n\nReinstall BluxTech Studio, or contact support with this message."))
        .title("BluxTech Studio could not start")
        .kind(MessageDialogKind::Error)
        .blocking_show();
}

// ---------------------------------------------------------------- updates

/// The update found by the last check, kept until the customer asks to install it.
struct Pending(Mutex<Option<tauri_plugin_updater::Update>>);

/// Whether, and where, this instance may look for updates. Never a URL for the UI: the channel's name only.
#[derive(Serialize, Clone)]
struct UpdateStatus {
    enabled: bool,
    /// why not, in the customer's words (empty when enabled)
    reason: String,
    /// "release" (the published channel), "override" (an operator's manifest), or "" when off
    channel: String,
    current: String,
}

struct Policy {
    status: UpdateStatus,
    endpoint: Option<String>,
}

fn update_policy(app: &AppHandle) -> Policy {
    let current = app.package_info().version.to_string();
    let off = |reason: &str| Policy {
        status: UpdateStatus { enabled: false, reason: reason.to_string(), channel: String::new(), current: current.clone() },
        endpoint: None,
    };
    if std::env::var("BLUXTECH_UPDATES").map(|v| v == "off").unwrap_or(false) {
        return off("Updates are switched off on this PC.");
    }
    // a run against a developer's engine (BLUXTECH_ENGINE_URL) is not an installed copy: it never updates itself
    if app.state::<Engine>().0.lock().unwrap().is_none() {
        return off("This is a development run: updates come with the installed app.");
    }
    // an operator's override: <app local data>\updater.json {"endpoint": "https://.../latest.json"}
    if let Ok(dir) = app.path().app_local_data_dir() {
        let p = dir.join("updater.json");
        if let Ok(text) = std::fs::read_to_string(&p) {
            if let Ok(v) = serde_json::from_str::<serde_json::Value>(&text) {
                if let Some(ep) = v.get("endpoint").and_then(|e| e.as_str()).filter(|e| !e.is_empty()) {
                    return Policy {
                        status: UpdateStatus { enabled: true, reason: String::new(), channel: "override".into(), current: current.clone() },
                        endpoint: Some(ep.to_string()),
                    };
                }
            }
        }
    }
    // the release channel from tauri.conf.json (plugins.updater.endpoints)
    let configured = app
        .config()
        .plugins
        .0
        .get("updater")
        .and_then(|u| u.get("endpoints"))
        .and_then(|e| e.as_array())
        .map(|a| !a.is_empty())
        .unwrap_or(false);
    if !configured {
        return off("This build has no release channel.");
    }
    Policy {
        status: UpdateStatus { enabled: true, reason: String::new(), channel: "release".into(), current },
        endpoint: None,
    }
}

fn updater(app: &AppHandle, policy: &Policy) -> Result<tauri_plugin_updater::Updater, String> {
    let mut b = app.updater_builder();
    if let Some(ep) = &policy.endpoint {
        let url = ep.parse().map_err(|e| format!("the override endpoint is not a URL: {e}"))?;
        b = b.endpoints(vec![url]).map_err(|e| e.to_string())?;
    }
    // the installer must find no engine holding files open, and the app's own cleanup still runs
    let handle = app.clone();
    b = b.on_before_exit(move || {
        stop_engine(&handle);
        handle.cleanup_before_exit();
    });
    b.build().map_err(|e| e.to_string())
}

#[derive(Serialize)]
struct UpdateCheck {
    available: bool,
    current: String,
    version: Option<String>,
    notes: Option<String>,
    /// publication time, unix seconds (the UI formats it)
    date: Option<i64>,
}

#[tauri::command]
fn update_status(app: AppHandle) -> UpdateStatus {
    update_policy(&app).status
}

#[tauri::command]
async fn update_check(app: AppHandle, pending: State<'_, Pending>) -> Result<UpdateCheck, String> {
    let policy = update_policy(&app);
    if !policy.status.enabled {
        return Err(policy.status.reason);
    }
    let current = policy.status.current.clone();
    let up = updater(&app, &policy)?;
    match up.check().await {
        Ok(Some(u)) => {
            let info = UpdateCheck {
                available: true,
                current,
                version: Some(u.version.clone()),
                notes: u.body.clone(),
                date: u.date.map(|d| d.unix_timestamp()),
            };
            *pending.0.lock().unwrap() = Some(u);
            Ok(info)
        }
        Ok(None) => {
            *pending.0.lock().unwrap() = None;
            Ok(UpdateCheck { available: false, current, version: None, notes: None, date: None })
        }
        Err(e) => Err(e.to_string()),
    }
}

#[derive(Serialize, Clone)]
struct Progress {
    /// "download" | "verify" | "install"
    phase: &'static str,
    downloaded: u64,
    total: Option<u64>,
}

/// Download (with progress events), verify the signature, stop the engine and hand over to the installer, which
/// relaunches the app. Returns only on failure: on success this process exits.
#[tauri::command]
async fn update_install(app: AppHandle, pending: State<'_, Pending>) -> Result<(), String> {
    let update = pending.0.lock().unwrap().take().ok_or("Check for updates first.")?;
    let mut downloaded: u64 = 0;
    let emit_app = app.clone();
    let done_app = app.clone();
    let bytes = update
        .download(
            move |chunk, total| {
                downloaded += chunk as u64;
                let _ = emit_app.emit("update-progress", Progress { phase: "download", downloaded, total });
            },
            move || {
                let _ = done_app.emit("update-progress", Progress { phase: "verify", downloaded: 0, total: None });
            },
        )
        .await
        .map_err(|e| e.to_string())?;
    let _ = app.emit("update-progress", Progress { phase: "install", downloaded: 0, total: None });
    update.install(bytes).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .manage(Engine(Mutex::new(None)))
        .manage(Pending(Mutex::new(None)))
        .invoke_handler(tauri::generate_handler![update_status, update_check, update_install])
        .setup(|app| {
            let handle = app.handle().clone();
            let url = match std::env::var("BLUXTECH_ENGINE_URL") {
                Ok(u) if !u.is_empty() => u,
                _ => match spawn_engine(&handle) {
                    Ok((child, ready)) => {
                        *handle.state::<Engine>().0.lock().unwrap() = Some(child);
                        format!("http://127.0.0.1:{}/boot/{}", ready.port, ready.token)
                    }
                    Err(e) => {
                        fail(&handle, &e);
                        std::process::exit(1);
                    }
                },
            };
            WebviewWindowBuilder::new(app, "main", WebviewUrl::External(url.parse().expect("engine url")))
                .title("BluxTech Studio")
                .inner_size(1440.0, 900.0)
                .min_inner_size(1100.0, 680.0)
                .center()
                .build()?;
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building BluxTech Studio")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                stop_engine(app);
            }
        });
}
