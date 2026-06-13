use crate::{config::Config, tts};
use crate::window_mgmt;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use tao::dpi::{LogicalPosition, LogicalSize};
use tao::event_loop::{EventLoopProxy, EventLoopWindowTarget};
#[cfg(target_os = "windows")]
use tao::platform::windows::WindowBuilderExtWindows;
use tao::window::WindowBuilder;
use tracing::{error, info, warn};
use wry::WebViewBuilder;

use crate::AppEvent;

/// Manages open webview panel windows
pub struct PanelManager {
    /// Panel name → window + webview (we store the Window to control visibility)
    windows: HashMap<String, PanelWindow>,
    proxy: Option<EventLoopProxy<AppEvent>>,
}

struct PanelWindow {
    window: tao::window::Window,
    _webview: wry::WebView,
    visible: bool,
}

impl PanelManager {
    pub fn new() -> Self {
        Self {
            windows: HashMap::new(),
            proxy: None,
        }
    }

    pub fn set_proxy(&mut self, proxy: EventLoopProxy<AppEvent>) {
        self.proxy = Some(proxy);
    }

    /// Open a panel (create if not exists, show if hidden)
    pub fn open(
        &mut self,
        name: &str,
        event_loop: &EventLoopWindowTarget<AppEvent>,
        cfg: &Arc<Mutex<Config>>,
    ) {
        if let Some(panel) = self.windows.get_mut(name) {
            panel.window.set_visible(true);
            panel.window.set_focus();
            panel.visible = true;
            return;
        }

        // Create new panel window
        self.create_panel(name, event_loop, cfg);
    }

    /// Toggle a panel's visibility
    pub fn toggle(
        &mut self,
        name: &str,
        event_loop: &EventLoopWindowTarget<AppEvent>,
        cfg: &Arc<Mutex<Config>>,
    ) {
        if let Some(panel) = self.windows.get_mut(name) {
            panel.visible = true;
            panel.window.set_visible(true);
            panel.window.set_minimized(false);
            panel.window.set_focus();
            return;
        }

        // Doesn't exist yet — create and show
        self.create_panel(name, event_loop, cfg);
    }

    fn create_panel(
        &mut self,
        name: &str,
        event_loop: &EventLoopWindowTarget<AppEvent>,
        cfg: &Arc<Mutex<Config>>,
    ) {
        let cfg_lock = cfg.lock().unwrap();
        let panel_def = match cfg_lock.panel(name) {
            Some(p) => p.clone(),
            None => {
                error!("No panel definition for '{}'", name);
                return;
            }
        };
        drop(cfg_lock);

        let mut builder = WindowBuilder::new()
            .with_title(&panel_def.title)
            .with_inner_size(LogicalSize::new(panel_def.width, panel_def.height))
            .with_decorations(true)
            .with_always_on_top(panel_def.always_on_top);

        #[cfg(target_os = "windows")]
        {
            builder = builder.with_skip_taskbar(true);
        }

        // Restore saved position
        if let (Some(x), Some(y)) = (panel_def.x, panel_def.y) {
            builder = builder.with_position(LogicalPosition::new(x, y));
        }

        let window = match builder.build(event_loop) {
            Ok(w) => w,
            Err(e) => {
                error!("Failed to create window for '{}': {}", name, e);
                return;
            }
        };

        // Apply dark title bar on Windows 11
        window_mgmt::set_dark_titlebar(&window);

        let url = &panel_def.url;
        let proxy = self.proxy.clone();
        let panel_name = name.to_string();

        let webview = match WebViewBuilder::new()
            .with_url(url)
            .with_initialization_script(
                r#"
                if (!window.chrome) window.chrome = {};
                if (!window.chrome.webview) {
                  window.chrome.webview = {
                    postMessage: function (msg) { window.ipc.postMessage(msg); }
                  };
                }
                "#,
            )
            .with_ipc_handler(move |request| {
                if let Some(proxy) = &proxy {
                    let _ = proxy.send_event(AppEvent::PanelIpc {
                        panel: panel_name.clone(),
                        payload: request.body().to_string(),
                    });
                }
            })
            .with_devtools(cfg!(debug_assertions))
            .with_transparent(false)
            .build(&window)
        {
            Ok(wv) => wv,
            Err(e) => {
                error!("Failed to create webview for '{}': {}", name, e);
                return;
            }
        };

        info!("Panel '{}' opened → {}", name, url);

        self.windows.insert(
            name.to_string(),
            PanelWindow {
                window,
                _webview: webview,
                visible: true,
            },
        );
    }

    pub fn handle_ipc(&mut self, panel: &str, payload: &str, cfg: &Arc<Mutex<Config>>) {
        let parsed: serde_json::Value = match serde_json::from_str(payload) {
            Ok(v) => v,
            Err(e) => {
                warn!("Panel IPC parse failed for '{}': {}", panel, e);
                return;
            }
        };

        let msg_type = parsed.get("type").and_then(|v| v.as_str()).unwrap_or("");
        match msg_type {
            "get_config" => {
                let json = match serde_json::to_string(&*cfg.lock().unwrap()) {
                    Ok(j) => j,
                    Err(e) => {
                        warn!("Config serialize failed: {}", e);
                        return;
                    }
                };
                self.eval(panel, &format!("window.config = {}; if (window.populateUI) window.populateUI();", json));
            }
            "save_config" => {
                if let Some(tts_cfg) = parsed.get("config").and_then(|c| c.get("tts")) {
                    let mut lock = cfg.lock().unwrap();
                    if let Some(v) = tts_cfg.get("voice").and_then(|v| v.as_str()) {
                        lock.tts.voice = v.to_string();
                    }
                    if let Some(v) = tts_cfg.get("engine").and_then(|v| v.as_str()) {
                        lock.tts.engine = normalize_engine(v);
                    }
                    if let Some(v) = tts_cfg.get("speed").and_then(|v| v.as_i64()) {
                        lock.tts.speed = v as i32;
                    }
                    if let Some(v) = tts_cfg.get("volume").and_then(|v| v.as_u64()) {
                        lock.tts.volume = v as u32;
                    }
                    if let Err(e) = lock.save() {
                        warn!("Config save failed: {}", e);
                    }
                }
            }
            "list_voices" => {
                let names = tts::list_voices();
                let json = serde_json::to_string(&names).unwrap_or_else(|_| "[]".into());
                self.eval(panel, &format!("if (window.populateVoices) window.populateVoices({});", json));
            }
            "speak_text" => {
                let text = parsed.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
                if text.trim().is_empty() {
                    return;
                }
                let engine = parsed.get("engine").and_then(|v| v.as_str()).map(normalize_engine)
                    .unwrap_or_else(|| cfg.lock().unwrap().tts.engine.clone());
                let voice = parsed.get("voice").and_then(|v| v.as_str()).unwrap_or("default").to_string();
                let speed = parsed.get("speed").and_then(|v| v.as_i64()).unwrap_or(2) as i32;
                let volume = parsed.get("volume").and_then(|v| v.as_u64()).unwrap_or(100) as u32;
                std::thread::spawn(move || {
                    tts::configure(&voice, speed, &engine, volume);
                    if let Err(e) = tts::speak(&text) {
                        warn!("TTS speak_text failed: {}", e);
                    }
                });
            }
            "tts_stop" => tts::stop(),
            "tts_pause" => tts::stop(),
            "tts_download" => {
                let text = parsed.get("text").and_then(|v| v.as_str()).unwrap_or("").to_string();
                if text.trim().is_empty() {
                    return;
                }
                let path = dirs::data_local_dir()
                    .unwrap_or_else(|| std::path::PathBuf::from("."))
                    .join("ClipSync")
                    .join(format!("tts-{}.mp3", chrono_like_timestamp()));
                if let Some(parent) = path.parent() {
                    let _ = std::fs::create_dir_all(parent);
                }
                std::thread::spawn(move || tts::save_audio(&text, &path.to_string_lossy()));
            }
            _ => info!("Unhandled panel IPC from '{}': {}", panel, msg_type),
        }
    }

    fn eval(&self, panel: &str, script: &str) {
        if let Some(p) = self.windows.get(panel) {
            if let Err(e) = p._webview.evaluate_script(script) {
                warn!("Panel eval failed for '{}': {}", panel, e);
            }
        }
    }
}

fn normalize_engine(engine: &str) -> String {
    match engine {
        "windows" => "sapi".into(),
        other => other.into(),
    }
}

fn chrono_like_timestamp() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}
