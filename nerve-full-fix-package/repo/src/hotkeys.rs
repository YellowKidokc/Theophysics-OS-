use crate::config::Config;
use crate::AppEvent;
use anyhow::{anyhow, Result};
use tao::event_loop::EventLoopProxy;
use tracing::{error, info, warn};
use win_hotkeys::{HotkeyManager, InterruptHandle, VKey};

/// Register all hotkeys from config and run win-hotkeys on a dedicated
/// background thread.
///
/// win-hotkeys uses a WH_KEYBOARD_LL hook and callback dispatch, so it does not
/// require tao's Windows message pump to receive WM_HOTKEY messages.
pub fn register_all(cfg: &Config, proxy: EventLoopProxy<AppEvent>) -> Result<InterruptHandle> {
    let mut manager = HotkeyManager::<()>::new();
    let mut registered = 0usize;

    for binding in &cfg.hotkeys {
        match parse_hotkey(&binding.keys) {
            Ok((trigger_key, mod_keys)) => {
                let action = binding.action.clone();
                let keys = binding.keys.clone();
                let callback_proxy = proxy.clone();

                match manager.register_hotkey(trigger_key, &mod_keys, move || {
                    let _ = callback_proxy.send_event(AppEvent::HotkeyAction(action.clone()));
                }) {
                    Ok(id) => {
                        registered += 1;
                        info!("Hotkey: {} → {} (id {})", keys, binding.action, id);
                    }
                    Err(e) => warn!("Hotkey {} register: {}", binding.keys, e),
                }
            }
            Err(e) => error!("Invalid hotkey '{}': {}", binding.keys, e),
        }
    }

    if registered == 0 {
        return Err(anyhow!("No hotkeys were registered"));
    }

    let interrupt_handle = manager.interrupt_handle();
    std::thread::Builder::new()
        .name("nerve-win-hotkeys".into())
        .spawn(move || {
            info!(
                "win-hotkeys event loop started with {} registered hotkeys",
                registered
            );
            manager.event_loop();
            info!("win-hotkeys event loop stopped");
        })
        .map_err(|e| anyhow!("Failed to spawn hotkey thread: {}", e))?;

    Ok(interrupt_handle)
}

fn parse_hotkey(s: &str) -> Result<(VKey, Vec<VKey>)> {
    let parts: Vec<&str> = s
        .split('+')
        .map(|p| p.trim())
        .filter(|p| !p.is_empty())
        .collect();
    if parts.is_empty() {
        return Err(anyhow!("Hotkey is empty"));
    }

    let mut modifiers = Vec::new();
    let mut trigger = None;

    for part in parts {
        match part.to_lowercase().as_str() {
            "ctrl" | "control" => modifiers.push(VKey::Control),
            "alt" => modifiers.push(VKey::Menu),
            "shift" => modifiers.push(VKey::Shift),
            "win" | "super" | "meta" => modifiers.push(VKey::LWin),
            _ => {
                if trigger.is_some() {
                    return Err(anyhow!("Multiple trigger keys in hotkey '{}'", s));
                }
                trigger = Some(parse_key(part)?);
            }
        }
    }

    let trigger = trigger.ok_or_else(|| anyhow!("Missing trigger key in hotkey '{}'", s))?;
    Ok((trigger, modifiers))
}

fn parse_key(s: &str) -> Result<VKey> {
    let key = match s.to_lowercase().as_str() {
        "0" => VKey::Vk0,
        "1" => VKey::Vk1,
        "2" => VKey::Vk2,
        "3" => VKey::Vk3,
        "4" => VKey::Vk4,
        "5" => VKey::Vk5,
        "6" => VKey::Vk6,
        "7" => VKey::Vk7,
        "8" => VKey::Vk8,
        "9" => VKey::Vk9,
        "enter" => VKey::Return,
        "esc" => VKey::Escape,
        "backspace" => VKey::Back,
        "delete" | "del" => VKey::Delete,
        other => VKey::from_keyname(other).map_err(|e| anyhow!("Unknown key '{}': {}", s, e))?,
    };
    Ok(key)
}
