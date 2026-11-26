//! The desktop shell. It starts the Python engine from the app's resources, waits for the engine's first stdout
//! line (`BLUXTECH_READY {"port", "token", ...}`), opens the main window on the engine's boot link (which sets the
//! session cookie), and stops the engine's whole process tree when the app exits.
//!
//! Dev: set BLUXTECH_ENGINE_URL (for example `http://127.0.0.1:8766/boot/<token>`) and the shell opens that URL
//! instead of starting an engine.

use std::ffi::OsString;
use std::io::{BufRead, BufReader};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::{Manager, RunEvent, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::{DialogExt, MessageDialogKind};

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

fn resources(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    let dir = plain(app.path().resource_dir().map_err(|e| e.to_string())?);
    // `bundle.resources: ["resources/**/*"]` keeps the folder name under the resource dir.
    let nested = dir.join("resources");
    Ok(if nested.is_dir() { nested } else { dir })
}

fn spawn_engine(app: &tauri::AppHandle) -> Result<(Child, Ready), String> {
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

fn stop_engine(app: &tauri::AppHandle) {
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

fn fail(app: &tauri::AppHandle, msg: &str) {
    app.dialog()
        .message(format!("{msg}\n\nReinstall BluxTech Studio, or contact support with this message."))
        .title("BluxTech Studio could not start")
        .kind(MessageDialogKind::Error)
        .blocking_show();
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(Engine(Mutex::new(None)))
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
