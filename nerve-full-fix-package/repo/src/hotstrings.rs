use crate::config::Config;
use crate::AppEvent;
use anyhow::Result;
use std::sync::{Arc, Mutex};
use tao::event_loop::EventLoopProxy;
use tracing::info;
use windows::Win32::Foundation::{LPARAM, LRESULT, WPARAM};
use windows::Win32::UI::WindowsAndMessaging::*;

/// Runs the hotstring engine. Installs a low-level keyboard hook and
/// matches typed text against configured hotstrings.
///
/// Must run on its own thread with a Windows message pump.
pub fn engine(_proxy: EventLoopProxy<AppEvent>, cfg: Arc<Mutex<Config>>) -> Result<()> {
    // Store config in thread-local for the hook callback
    HOOK_CONFIG.with(|hc| {
        *hc.borrow_mut() = Some(cfg);
    });

    // Install low-level keyboard hook
    let hook = unsafe {
        SetWindowsHookExW(WH_KEYBOARD_LL, Some(keyboard_hook_proc), None, 0)?
    };

    info!("Hotstring keyboard hook installed");

    // Run message pump (required for hooks to work)
    unsafe {
        let mut msg = MSG::default();
        while GetMessageW(&mut msg, None, 0, 0).into() {
            let _ = TranslateMessage(&msg);
            DispatchMessageW(&msg);
        }
    }

    // Unhook on exit
    unsafe {
        let _ = UnhookWindowsHookEx(hook);
    }

    Ok(())
}

thread_local! {
    static HOOK_CONFIG: std::cell::RefCell<Option<Arc<Mutex<Config>>>> =
        std::cell::RefCell::new(None);
    static TYPED_BUFFER: std::cell::RefCell<String> = std::cell::RefCell::new(String::new());
    /// Flag to prevent re-entrancy when we're sending keystrokes
    static SENDING: std::cell::RefCell<bool> = std::cell::RefCell::new(false);
}

/// Low-level keyboard hook procedure
unsafe extern "system" fn keyboard_hook_proc(
    code: i32,
    wparam: WPARAM,
    lparam: LPARAM,
) -> LRESULT {
    if code < 0 {
        return CallNextHookEx(None, code, wparam, lparam);
    }

    // Don't process our own injected keystrokes
    let sending = SENDING.with(|s| *s.borrow());
    if sending {
        return CallNextHookEx(None, code, wparam, lparam);
    }

    if wparam.0 == WM_KEYDOWN as usize || wparam.0 == WM_SYSKEYDOWN as usize {
        let kb = *(lparam.0 as *const KBDLLHOOKSTRUCT);

        // Skip injected events (from SendInput)
        if kb.flags.0 & 0x10 != 0 {
            // LLKHF_INJECTED
            return CallNextHookEx(None, code, wparam, lparam);
        }

        let vk = kb.vkCode;

        // Convert virtual key to character
        if let Some(ch) = vk_to_char(vk) {
            TYPED_BUFFER.with(|buf| {
                let mut buf = buf.borrow_mut();
                buf.push(ch);

                // Keep buffer reasonable size
                if buf.len() > 64 {
                    let drain_to = buf.len() - 48;
                    buf.drain(..drain_to);
                }

                // Check for hotstring matches
                HOOK_CONFIG.with(|hc| {
                    let hc = hc.borrow();
                    if let Some(ref cfg_arc) = *hc {
                        if let Ok(cfg) = cfg_arc.lock() {
                            for hs in &cfg.hotstrings {
                                if buf.ends_with(&hs.trigger) {
                                    info!("Hotstring triggered: {}", hs.trigger);
                                    let expansion = hs.expansion.clone();
                                    let trigger_len = hs.trigger.len();
                                    let replace = hs.replace_trigger;

                                    // Clear the buffer
                                    buf.clear();

                                    // Expand in a separate thread to avoid blocking the hook
                                    let trigger_l = trigger_len;
                                    std::thread::spawn(move || {
                                        expand_hotstring(&expansion, trigger_l, replace);
                                    });
                                }
                            }
                        }
                    }
                });
            });
        } else if vk == 0x08 {
            // Backspace — remove last char from buffer
            TYPED_BUFFER.with(|buf| {
                buf.borrow_mut().pop();
            });
        } else if vk == 0x0D || vk == 0x1B || vk == 0x09 {
            // Enter, Escape, Tab — clear buffer
            TYPED_BUFFER.with(|buf| {
                buf.borrow_mut().clear();
            });
        }
    }

    CallNextHookEx(None, code, wparam, lparam)
}

/// Convert a virtual key code to a character (simplified)
fn vk_to_char(vk: u32) -> Option<char> {
    match vk {
        // A-Z → lowercase
        0x41..=0x5A => Some((vk as u8 + 32) as char), // 'a'..'z'
        // 0-9
        0x30..=0x39 => Some((vk as u8) as char),
        // Special keys that are part of triggers
        0xBF => Some('/'),  // VK_OEM_2 (/)
        0xBE => Some('.'),  // VK_OEM_PERIOD
        0xBD => Some('-'),  // VK_OEM_MINUS
        0xBA => Some(';'),  // VK_OEM_1 (;)
        0xBC => Some(','),  // VK_OEM_COMMA
        0xBB => Some('='),  // VK_OEM_PLUS (=)
        0xDB => Some('['),  // VK_OEM_4
        0xDD => Some(']'),  // VK_OEM_6
        0xDC => Some('\\'), // VK_OEM_5
        0xDE => Some('\''), // VK_OEM_7
        0xC0 => Some('`'),  // VK_OEM_3
        0x20 => Some(' '),  // Space
        _ => None,
    }
}

/// Expand a hotstring: delete the trigger text, then type the expansion
fn expand_hotstring(expansion: &str, trigger_len: usize, replace_trigger: bool) {
    use windows::Win32::UI::Input::KeyboardAndMouse::*;

    SENDING.with(|s| *s.borrow_mut() = true);

    // Small delay before starting
    std::thread::sleep(std::time::Duration::from_millis(20));

    if replace_trigger {
        // Send backspaces to delete the trigger
        for _ in 0..trigger_len {
            send_key(VK_BACK, false);
            send_key(VK_BACK, true);
            std::thread::sleep(std::time::Duration::from_millis(5));
        }
    }

    // Type the expansion by setting clipboard and pasting
    // (much faster and more reliable than sending individual keystrokes)
    if let Ok(()) = set_clipboard_for_paste(expansion) {
        std::thread::sleep(std::time::Duration::from_millis(20));
        // Send Ctrl+V
        send_key(VK_CONTROL, false);
        send_key(VK_V, false);
        send_key(VK_V, true);
        send_key(VK_CONTROL, true);
    }

    std::thread::sleep(std::time::Duration::from_millis(30));
    SENDING.with(|s| *s.borrow_mut() = false);
}

fn send_key(vk: windows::Win32::UI::Input::KeyboardAndMouse::VIRTUAL_KEY, key_up: bool) {
    use windows::Win32::UI::Input::KeyboardAndMouse::*;

    let flags = if key_up {
        KEYEVENTF_KEYUP
    } else {
        KEYBD_EVENT_FLAGS(0)
    };

    let input = INPUT {
        r#type: INPUT_KEYBOARD,
        Anonymous: INPUT_0 {
            ki: KEYBDINPUT {
                wVk: vk,
                wScan: 0,
                dwFlags: flags,
                time: 0,
                dwExtraInfo: 0,
            },
        },
    };

    unsafe {
        SendInput(&[input], std::mem::size_of::<INPUT>() as i32);
    }
}

fn set_clipboard_for_paste(text: &str) -> Result<()> {
    use clipboard_win::{formats, set_clipboard};
    set_clipboard(formats::Unicode, text)
        .map_err(|e| anyhow::anyhow!("clipboard write: {:?}", e))?;
    Ok(())
}
