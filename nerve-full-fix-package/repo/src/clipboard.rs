use crate::config::Config;
use crate::AppEvent;
use anyhow::Result;
use std::sync::{Arc, Mutex};
use tao::event_loop::EventLoopProxy;
use tracing::error;

/// Monitor the system clipboard for changes. Runs in its own thread.
pub fn monitor(proxy: EventLoopProxy<AppEvent>, cfg: Arc<Mutex<Config>>) -> Result<()> {
    let mut last_content = String::new();

    // Read initial clipboard content
    if let Ok(text) = get_clipboard_text() {
        last_content = text;
    }

    loop {
        let interval = {
            let c = cfg.lock().unwrap();
            c.clipboard_interval_ms
        };

        std::thread::sleep(std::time::Duration::from_millis(interval));

        match get_clipboard_text() {
            Ok(text) => {
                if !text.is_empty() && text != last_content {
                    last_content = text.clone();

                    // Update clip slots (push to front, keep 10)
                    {
                        let mut c = cfg.lock().unwrap();
                        c.clip_slots.insert(
                            0,
                            crate::config::ClipSlot {
                                content: text.clone(),
                                timestamp: chrono_now(),
                            },
                        );
                        c.clip_slots.truncate(10);
                    }

                    // Notify main loop
                    if proxy.send_event(AppEvent::ClipboardChanged(text)).is_err() {
                        break; // Event loop closed
                    }
                }
            }
            Err(_) => {
                // Clipboard might be locked by another app, just skip
            }
        }
    }

    Ok(())
}

/// Get current clipboard text using clipboard-win
fn get_clipboard_text() -> Result<String> {
    use clipboard_win::{formats, get_clipboard};
    let text: String = get_clipboard(formats::Unicode)
        .map_err(|e| anyhow::anyhow!("clipboard read: {:?}", e))?;
    Ok(text)
}

/// Set clipboard text
fn set_clipboard_text(text: &str) -> Result<()> {
    use clipboard_win::{formats, set_clipboard};
    set_clipboard(formats::Unicode, text)
        .map_err(|e| anyhow::anyhow!("clipboard write: {:?}", e))?;
    Ok(())
}

/// Paste from a clip slot by index
pub fn paste_slot(index: usize) {
    // We can't access config here directly since this is called from the event loop.
    // Instead we read from a static. But for now, use a simpler approach:
    // The caller should pass the content. For the global hotkey handler,
    // we'll use a different approach — store slots in a thread-safe global.
    PASTE_SENDER.with(|_| {});
    // This will be wired up properly through the event system
    tracing::info!("Paste slot {} requested", index);
}

/// Paste text by setting clipboard and sending Ctrl+V
pub fn paste_text(text: &str) {
    if let Err(e) = set_clipboard_text(text) {
        error!("Failed to set clipboard: {}", e);
        return;
    }

    // Small delay to let clipboard settle
    std::thread::sleep(std::time::Duration::from_millis(30));

    // Send Ctrl+V using Windows API
    send_ctrl_v();
}

/// Send Ctrl+V keystroke via Windows SendInput API
fn send_ctrl_v() {
    use windows::Win32::UI::Input::KeyboardAndMouse::*;

    let inputs = [
        // Ctrl down
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_CONTROL,
                    wScan: 0,
                    dwFlags: KEYBD_EVENT_FLAGS(0),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        },
        // V down
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_V,
                    wScan: 0,
                    dwFlags: KEYBD_EVENT_FLAGS(0),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        },
        // V up
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_V,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        },
        // Ctrl up
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_CONTROL,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        },
    ];

    unsafe {
        SendInput(&inputs, std::mem::size_of::<INPUT>() as i32);
    }
}

/// Simple timestamp (no chrono dependency — just use SystemTime)
fn chrono_now() -> String {
    use std::time::SystemTime;
    let dur = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    format!("{}", dur.as_secs())
}

// Thread-local placeholder — paste_slot will be refactored to use Arc<Mutex<Config>>
thread_local! {
    static PASTE_SENDER: () = ();
}
