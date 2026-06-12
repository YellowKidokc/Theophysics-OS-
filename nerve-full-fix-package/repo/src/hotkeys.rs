use crate::config::Config;
use anyhow::{anyhow, Result};
use global_hotkey::hotkey::{Code, HotKey, Modifiers};
use global_hotkey::GlobalHotKeyManager;
use tracing::{error, info, warn};

/// Register all hotkeys from config. Must be called from the main thread.
/// Returns the manager (caller must keep it alive).
pub fn register_all(cfg: &Config) -> Result<GlobalHotKeyManager> {
    let manager = GlobalHotKeyManager::new()
        .map_err(|e| anyhow!("Failed to create hotkey manager: {}", e))?;

    for binding in &cfg.hotkeys {
        match parse_hotkey(&binding.keys) {
            Ok(hotkey) => {
                match manager.register(hotkey) {
                    Ok(()) => info!("Hotkey: {} → {}", binding.keys, binding.action),
                    Err(e) => warn!("Hotkey {} register: {}", binding.keys, e),
                }
            }
            Err(e) => error!("Invalid hotkey '{}': {}", binding.keys, e),
        }
    }

    Ok(manager)
}

/// Build the hotkey_map (id → action) on the config
pub fn build_hotkey_map(cfg: &mut Config) {
    cfg.hotkey_map.clear();
    for binding in &cfg.hotkeys {
        if let Ok(hotkey) = parse_hotkey(&binding.keys) {
            cfg.hotkey_map.insert(hotkey.id(), binding.action.clone());
        }
    }
}

fn parse_hotkey(s: &str) -> Result<HotKey> {
    let parts: Vec<&str> = s.split('+').map(|p| p.trim()).collect();
    let mut modifiers = Modifiers::empty();
    let mut key_str = "";

    for part in &parts {
        match part.to_lowercase().as_str() {
            "ctrl" | "control" => modifiers |= Modifiers::CONTROL,
            "alt" => modifiers |= Modifiers::ALT,
            "shift" => modifiers |= Modifiers::SHIFT,
            "win" | "super" | "meta" => modifiers |= Modifiers::SUPER,
            _ => key_str = part,
        }
    }

    let code = parse_key_code(key_str)?;
    Ok(HotKey::new(Some(modifiers), code))
}

fn parse_key_code(s: &str) -> Result<Code> {
    let code = match s.to_lowercase().as_str() {
        "a" => Code::KeyA, "b" => Code::KeyB, "c" => Code::KeyC, "d" => Code::KeyD,
        "e" => Code::KeyE, "f" => Code::KeyF, "g" => Code::KeyG, "h" => Code::KeyH,
        "i" => Code::KeyI, "j" => Code::KeyJ, "k" => Code::KeyK, "l" => Code::KeyL,
        "m" => Code::KeyM, "n" => Code::KeyN, "o" => Code::KeyO, "p" => Code::KeyP,
        "q" => Code::KeyQ, "r" => Code::KeyR, "s" => Code::KeyS, "t" => Code::KeyT,
        "u" => Code::KeyU, "v" => Code::KeyV, "w" => Code::KeyW, "x" => Code::KeyX,
        "y" => Code::KeyY, "z" => Code::KeyZ,
        "0" => Code::Digit0, "1" => Code::Digit1, "2" => Code::Digit2, "3" => Code::Digit3,
        "4" => Code::Digit4, "5" => Code::Digit5, "6" => Code::Digit6, "7" => Code::Digit7,
        "8" => Code::Digit8, "9" => Code::Digit9,
        "f1" => Code::F1, "f2" => Code::F2, "f3" => Code::F3, "f4" => Code::F4,
        "f5" => Code::F5, "f6" => Code::F6, "f7" => Code::F7, "f8" => Code::F8,
        "f9" => Code::F9, "f10" => Code::F10, "f11" => Code::F11, "f12" => Code::F12,
        "space" => Code::Space, "enter" | "return" => Code::Enter, "tab" => Code::Tab,
        "escape" | "esc" => Code::Escape, "backspace" => Code::Backspace,
        "delete" | "del" => Code::Delete,
        _ => return Err(anyhow!("Unknown key: {}", s)),
    };
    Ok(code)
}
