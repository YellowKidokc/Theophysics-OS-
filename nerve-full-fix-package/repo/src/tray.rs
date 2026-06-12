use crate::AppEvent;
use anyhow::Result;
use tao::event_loop::EventLoopProxy;
use tray_icon::menu::{Menu, MenuEvent, MenuItem};
use tray_icon::{TrayIcon, TrayIconBuilder};
use tracing::info;

/// Create the system tray icon with menu
pub fn create_tray(proxy: &EventLoopProxy<AppEvent>) -> Result<TrayIcon> {
    let menu = Menu::new();

    let item_clipboard = MenuItem::new("Clipboard  (Ctrl+Alt+C)", true, None);
    let item_prompts = MenuItem::new("Prompts    (Ctrl+Alt+P)", true, None);
    let item_links = MenuItem::new("Links      (Ctrl+Alt+L)", true, None);
    let item_research = MenuItem::new("Research   (Ctrl+Alt+R)", true, None);
    let item_chat = MenuItem::new("AI Chat    (Ctrl+Alt+A)", true, None);
    let item_dashboard = MenuItem::new("Dashboard  (Ctrl+Alt+G)", true, None);
    let item_settings = MenuItem::new("Settings", true, None);
    let item_separator = tray_icon::menu::PredefinedMenuItem::separator();
    let item_quit = MenuItem::new("Quit", true, None);

    menu.append(&item_clipboard)?;
    menu.append(&item_prompts)?;
    menu.append(&item_links)?;
    menu.append(&item_research)?;
    menu.append(&item_chat)?;
    menu.append(&item_dashboard)?;
    menu.append(&item_separator)?;
    menu.append(&item_settings)?;
    menu.append(&item_separator)?;
    menu.append(&item_quit)?;

    let clipboard_id = item_clipboard.id().clone();
    let prompts_id = item_prompts.id().clone();
    let links_id = item_links.id().clone();
    let research_id = item_research.id().clone();
    let chat_id = item_chat.id().clone();
    let dashboard_id = item_dashboard.id().clone();
    let settings_id = item_settings.id().clone();
    let quit_id = item_quit.id().clone();

    let proxy_clone = proxy.clone();
    std::thread::spawn(move || {
        loop {
            if let Ok(event) = MenuEvent::receiver().recv() {
                if event.id == clipboard_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("clipboard".into()));
                } else if event.id == prompts_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("prompts".into()));
                } else if event.id == links_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("links".into()));
                } else if event.id == research_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("research".into()));
                } else if event.id == chat_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("chat".into()));
                } else if event.id == dashboard_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("dashboard".into()));
                } else if event.id == settings_id {
                    let _ = proxy_clone.send_event(AppEvent::TogglePanel("settings".into()));
                } else if event.id == quit_id {
                    let _ = proxy_clone.send_event(AppEvent::Quit);
                }
            }
        }
    });

    let icon = create_icon();

    let tray = TrayIconBuilder::new()
        .with_menu(Box::new(menu))
        .with_tooltip("ClipSync Agent")
        .with_icon(icon)
        .build()?;

    info!("System tray created");
    Ok(tray)
}

/// Create a simple 16x16 RGBA icon (cyan "C" on dark background)
fn create_icon() -> tray_icon::Icon {
    let size = 16u32;
    let mut rgba = vec![0u8; (size * size * 4) as usize];

    for y in 0..size {
        for x in 0..size {
            let idx = ((y * size + x) * 4) as usize;
            rgba[idx] = 0x1a;
            rgba[idx + 1] = 0x1a;
            rgba[idx + 2] = 0x2e;
            rgba[idx + 3] = 0xff;

            let in_c = (y >= 3 && y <= 12)
                && ((x >= 3 && x <= 5)
                    || (y >= 3 && y <= 5 && x >= 3 && x <= 11)
                    || (y >= 10 && y <= 12 && x >= 3 && x <= 11));

            if in_c {
                rgba[idx] = 0x60;
                rgba[idx + 1] = 0xd0;
                rgba[idx + 2] = 0xff;
            }
        }
    }

    tray_icon::Icon::from_rgba(rgba, size, size).expect("Failed to create tray icon")
}
