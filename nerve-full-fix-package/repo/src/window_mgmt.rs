use tao::window::Window;
#[allow(unused_imports)]
use tracing::warn;

/// Apply dark title bar to a window using DWM (Windows 11+)
pub fn set_dark_titlebar(window: &Window) {
    #[cfg(target_os = "windows")]
    {
        use tao::platform::windows::WindowExtWindows;
        use windows::Win32::Foundation::BOOL;
        use windows::Win32::Graphics::Dwm::{DwmSetWindowAttribute, DWMWA_USE_IMMERSIVE_DARK_MODE};

        let hwnd = window.hwnd();
        let hwnd = windows::Win32::Foundation::HWND(hwnd as *mut _);
        let value = BOOL::from(true);

        unsafe {
            let result = DwmSetWindowAttribute(
                hwnd,
                DWMWA_USE_IMMERSIVE_DARK_MODE,
                &value as *const BOOL as *const _,
                std::mem::size_of::<BOOL>() as u32,
            );
            if result.is_err() {
                warn!("Failed to set dark title bar");
            }
        }
    }
}

/// Set a window to always-on-top
pub fn set_always_on_top(window: &Window, on_top: bool) {
    window.set_always_on_top(on_top);
}

/// Get window position for saving
pub fn get_window_position(window: &Window) -> Option<(i32, i32)> {
    match window.outer_position() {
        Ok(pos) => Some((pos.x, pos.y)),
        Err(_) => None,
    }
}
