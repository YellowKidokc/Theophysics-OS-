#![cfg_attr(
    all(not(debug_assertions), target_os = "windows"),
    windows_subsystem = "windows"
)]

mod clipboard;
mod config;
mod hotkeys;
mod hotstrings;
mod panels;
mod sync_client;
mod tray;
mod tts;
#[allow(dead_code)]
mod window_mgmt;

use anyhow::Result;
use std::sync::{Arc, Mutex};
use tao::event::{Event, StartCause};
use tao::event_loop::{ControlFlow, EventLoopBuilder, EventLoopProxy};
use tracing::{error, info};

/// Custom events the system can send to the main event loop
#[derive(Debug, Clone)]
pub enum AppEvent {
    /// Clipboard changed — content string
    ClipboardChanged(String),
    /// Hotkey action triggered by win-hotkeys
    HotkeyAction(String),
    /// Open a webview panel by name
    OpenPanel(String),
    /// Toggle panel visibility
    TogglePanel(String),
    /// Quit the application
    Quit,
    /// Config was reloaded from remote
    ConfigReloaded,
    /// Webview panel IPC payload
    PanelIpc { panel: String, payload: String },
}

fn handle_hotkey_action(action: &str, proxy: &EventLoopProxy<AppEvent>) {
    match action {
        "toggle_clipboard" => send_toggle(proxy, "clipboard"),
        "toggle_prompts" => send_toggle(proxy, "prompts"),
        "toggle_chat" => send_toggle(proxy, "chat"),
        "toggle_links" => send_toggle(proxy, "links"),
        "toggle_research" => send_toggle(proxy, "research"),
        "toggle_dashboard" => send_toggle(proxy, "dashboard"),
        "toggle_settings" => send_toggle(proxy, "settings"),
        "toggle_nexus" => send_toggle(proxy, "nexus"),
        "toggle_task_calendar" => send_toggle(proxy, "task_calendar"),
        "toggle_theophysics_hub" => send_toggle(proxy, "theophysics_hub"),
        "toggle_clipboard3" => send_toggle(proxy, "clipboard3"),
        "toggle_7q_engine" => send_toggle(proxy, "7q_engine"),
        "toggle_tts_engine" => send_toggle(proxy, "tts_engine"),
        "toggle_hub" => send_toggle(proxy, "hub"),
        "toggle_shortcuts" => send_toggle(proxy, "shortcuts"),
        "toggle_service_dashboard" => send_toggle(proxy, "service_dashboard"),
        "tts_read_selection" => {
            info!("TTS: reading selection");
            std::thread::spawn(|| {
                tts::read_selection();
            });
        }
        "paste_slot_1" => clipboard::paste_slot(0),
        "paste_slot_2" => clipboard::paste_slot(1),
        "paste_slot_3" => clipboard::paste_slot(2),
        "paste_slot_4" => clipboard::paste_slot(3),
        "paste_slot_5" => clipboard::paste_slot(4),
        "paste_slot_6" => clipboard::paste_slot(5),
        "paste_slot_7" => clipboard::paste_slot(6),
        "paste_slot_8" => clipboard::paste_slot(7),
        "paste_slot_9" => clipboard::paste_slot(8),
        "paste_slot_10" => clipboard::paste_slot(9),
        "ai_rewrite_selection" => {
            info!("AI rewrite hotkey fired");
            let _ = proxy.send_event(AppEvent::OpenPanel("chat".into()));
        }
        other => info!("Hotkey action: {}", other),
    }
}

fn send_toggle(proxy: &EventLoopProxy<AppEvent>, panel: &str) {
    let _ = proxy.send_event(AppEvent::TogglePanel(panel.into()));
}

fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("clipsync_agent=info".parse().unwrap()),
        )
        .init();

    info!("ClipSync Agent starting...");

    // Load config
    let cfg = config::Config::load()?;
    tts::configure(
        &cfg.tts.voice,
        cfg.tts.speed,
        &cfg.tts.engine,
        cfg.tts.volume,
    );
    tts::warm_voice_cache();
    let cfg = Arc::new(Mutex::new(cfg));

    // Build event loop with custom events
    let event_loop = EventLoopBuilder::<AppEvent>::with_user_event().build();
    let proxy = event_loop.create_proxy();

    // Start clipboard monitor thread
    let clip_proxy = proxy.clone();
    let clip_cfg = Arc::clone(&cfg);
    std::thread::spawn(move || {
        if let Err(e) = clipboard::monitor(clip_proxy, clip_cfg) {
            error!("Clipboard monitor error: {}", e);
        }
    });

    // Start hotstring engine thread (low-level keyboard hook)
    let hs_proxy = proxy.clone();
    let hs_cfg = Arc::clone(&cfg);
    std::thread::spawn(move || {
        if let Err(e) = hotstrings::engine(hs_proxy, hs_cfg) {
            error!("Hotstring engine error: {}", e);
        }
    });

    // Start background sync thread (pulls config from Cloudflare periodically)
    let sync_proxy = proxy.clone();
    let sync_cfg = Arc::clone(&cfg);
    std::thread::spawn(move || {
        let rt = tokio::runtime::Builder::new_current_thread()
            .enable_all()
            .build()
            .unwrap();
        rt.block_on(async {
            if let Err(e) = sync_client::sync_loop(sync_proxy, sync_cfg).await {
                error!("Sync loop error: {}", e);
            }
        });
    });

    // Start win-hotkeys on its own low-level keyboard hook thread.
    let mut hotkey_handle = {
        let hk_cfg = cfg.lock().unwrap();
        match hotkeys::register_all(&hk_cfg, proxy.clone()) {
            Ok(handle) => Some(handle),
            Err(e) => {
                error!("Failed to register hotkeys: {}", e);
                None
            }
        }
    };

    // Create system tray
    let _tray = tray::create_tray(&proxy)?;

    // Panel manager — holds open webview windows
    let mut panel_mgr = panels::PanelManager::new();
    panel_mgr.set_proxy(proxy.clone());

    info!("ClipSync Agent ready.");

    // Main event loop
    event_loop.run(move |event, event_loop, control_flow| {
        *control_flow = ControlFlow::Wait;

        match event {
            Event::NewEvents(StartCause::Init) => {
                info!("Event loop initialized");
            }

            Event::UserEvent(app_event) => match app_event {
                AppEvent::HotkeyAction(action) => {
                    handle_hotkey_action(&action, &proxy);
                }

                AppEvent::ClipboardChanged(content) => {
                    info!("Clipboard: {} chars", content.len());
                    // Push to sync client (fire and forget)
                    let sync_cfg = Arc::clone(&cfg);
                    std::thread::spawn(move || {
                        let rt = tokio::runtime::Builder::new_current_thread()
                            .enable_all()
                            .build()
                            .unwrap();
                        rt.block_on(async {
                            let _ = sync_client::push_clip(&sync_cfg, &content).await;
                        });
                    });
                }

                AppEvent::OpenPanel(name) => {
                    panel_mgr.open(&name, event_loop, &cfg);
                }

                AppEvent::TogglePanel(name) => {
                    panel_mgr.toggle(&name, event_loop, &cfg);
                }

                AppEvent::ConfigReloaded => {
                    info!("Config reloaded from remote");
                    if let Some(handle) = hotkey_handle.take() {
                        handle.interrupt();
                    }
                    let cfg_lock = cfg.lock().unwrap();
                    hotkey_handle = match hotkeys::register_all(&cfg_lock, proxy.clone()) {
                        Ok(handle) => Some(handle),
                        Err(e) => {
                            error!("Failed to re-register hotkeys: {}", e);
                            None
                        }
                    };
                }

                AppEvent::PanelIpc { panel, payload } => {
                    panel_mgr.handle_ipc(&panel, &payload, &cfg);
                }

                AppEvent::Quit => {
                    info!("Quit requested");
                    if let Some(handle) = hotkey_handle.take() {
                        handle.interrupt();
                    }
                    *control_flow = ControlFlow::Exit;
                }

                _ => {}
            },

            _ => {}
        }
    });
}
