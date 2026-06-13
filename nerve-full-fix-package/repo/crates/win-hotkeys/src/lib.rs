#[cfg(windows)]
use std::cell::RefCell;
use std::fmt;
use std::marker::PhantomData;
use std::sync::{
    atomic::{AtomicBool, AtomicU32, Ordering},
    Arc,
};
#[cfg(windows)]
use windows::Win32::Foundation::{LPARAM, LRESULT, WPARAM};
#[cfg(windows)]
use windows::Win32::System::Threading::GetCurrentThreadId;
#[cfg(windows)]
use windows::Win32::UI::Input::KeyboardAndMouse::GetAsyncKeyState;
#[cfg(windows)]
use windows::Win32::UI::WindowsAndMessaging::{
    CallNextHookEx, DispatchMessageW, GetMessageW, PeekMessageW, PostThreadMessageW,
    SetWindowsHookExW, TranslateMessage, UnhookWindowsHookEx, KBDLLHOOKSTRUCT, MSG, PM_NOREMOVE,
    WH_KEYBOARD_LL, WM_KEYDOWN, WM_KEYUP, WM_QUIT, WM_SYSKEYDOWN, WM_SYSKEYUP,
};

#[derive(Debug, Clone)]
pub struct WHKError(String);

impl fmt::Display for WHKError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.0)
    }
}

impl std::error::Error for WHKError {}

#[derive(Debug, Copy, Clone, PartialEq, Eq)]
pub enum VKey {
    Back,
    Tab,
    Return,
    Shift,
    Control,
    Menu,
    Escape,
    Space,
    Delete,
    Capital,
    LWin,
    RWin,
    LShift,
    RShift,
    LControl,
    RControl,
    LMenu,
    RMenu,
    F1,
    F2,
    F3,
    F4,
    F5,
    F6,
    F7,
    F8,
    F9,
    F10,
    F11,
    F12,
    Vk0,
    Vk1,
    Vk2,
    Vk3,
    Vk4,
    Vk5,
    Vk6,
    Vk7,
    Vk8,
    Vk9,
    A,
    B,
    C,
    D,
    E,
    F,
    G,
    H,
    I,
    J,
    K,
    L,
    M,
    N,
    O,
    P,
    Q,
    R,
    S,
    T,
    U,
    V,
    W,
    X,
    Y,
    Z,
    CustomKeyCode(u16),
}

impl VKey {
    pub const fn to_vk_code(&self) -> u16 {
        match self {
            VKey::Back => 0x08,
            VKey::Tab => 0x09,
            VKey::Return => 0x0D,
            VKey::Shift => 0x10,
            VKey::Control => 0x11,
            VKey::Menu => 0x12,
            VKey::Escape => 0x1B,
            VKey::Space => 0x20,
            VKey::Delete => 0x2E,
            VKey::Capital => 0x14,
            VKey::LWin => 0x5B,
            VKey::RWin => 0x5C,
            VKey::Vk0 => 0x30,
            VKey::Vk1 => 0x31,
            VKey::Vk2 => 0x32,
            VKey::Vk3 => 0x33,
            VKey::Vk4 => 0x34,
            VKey::Vk5 => 0x35,
            VKey::Vk6 => 0x36,
            VKey::Vk7 => 0x37,
            VKey::Vk8 => 0x38,
            VKey::Vk9 => 0x39,
            VKey::A => 0x41,
            VKey::B => 0x42,
            VKey::C => 0x43,
            VKey::D => 0x44,
            VKey::E => 0x45,
            VKey::F => 0x46,
            VKey::G => 0x47,
            VKey::H => 0x48,
            VKey::I => 0x49,
            VKey::J => 0x4A,
            VKey::K => 0x4B,
            VKey::L => 0x4C,
            VKey::M => 0x4D,
            VKey::N => 0x4E,
            VKey::O => 0x4F,
            VKey::P => 0x50,
            VKey::Q => 0x51,
            VKey::R => 0x52,
            VKey::S => 0x53,
            VKey::T => 0x54,
            VKey::U => 0x55,
            VKey::V => 0x56,
            VKey::W => 0x57,
            VKey::X => 0x58,
            VKey::Y => 0x59,
            VKey::Z => 0x5A,
            VKey::F1 => 0x70,
            VKey::F2 => 0x71,
            VKey::F3 => 0x72,
            VKey::F4 => 0x73,
            VKey::F5 => 0x74,
            VKey::F6 => 0x75,
            VKey::F7 => 0x76,
            VKey::F8 => 0x77,
            VKey::F9 => 0x78,
            VKey::F10 => 0x79,
            VKey::F11 => 0x7A,
            VKey::F12 => 0x7B,
            VKey::LShift => 0xA0,
            VKey::RShift => 0xA1,
            VKey::LControl => 0xA2,
            VKey::RControl => 0xA3,
            VKey::LMenu => 0xA4,
            VKey::RMenu => 0xA5,
            VKey::CustomKeyCode(code) => *code,
        }
    }

    pub const fn from_vk_code(vk_code: u16) -> VKey {
        VKey::CustomKeyCode(vk_code)
    }

    pub fn from_keyname(name: &str) -> Result<VKey, WHKError> {
        let normalized = name.trim().to_lowercase();
        let key = match normalized.as_str() {
            "ctrl" | "control" | "vk_control" => VKey::Control,
            "lctrl" | "lcontrol" | "vk_lcontrol" => VKey::LControl,
            "rctrl" | "rcontrol" | "vk_rcontrol" => VKey::RControl,
            "alt" | "menu" | "vk_menu" => VKey::Menu,
            "lalt" | "lmenu" | "vk_lmenu" => VKey::LMenu,
            "ralt" | "rmenu" | "vk_rmenu" => VKey::RMenu,
            "shift" | "vk_shift" => VKey::Shift,
            "win" | "lwin" | "vk_lwin" => VKey::LWin,
            "rwin" | "vk_rwin" => VKey::RWin,
            "space" | "vk_space" => VKey::Space,
            "return" | "enter" | "vk_return" => VKey::Return,
            "tab" | "vk_tab" => VKey::Tab,
            "escape" | "esc" | "vk_escape" => VKey::Escape,
            "back" | "backspace" | "vk_back" => VKey::Back,
            "delete" | "del" | "vk_delete" => VKey::Delete,
            "caps" | "capslock" | "caps_lock" | "vk_capital" => VKey::Capital,
            "0" | "vk_0" => VKey::Vk0,
            "1" | "vk_1" => VKey::Vk1,
            "2" | "vk_2" => VKey::Vk2,
            "3" | "vk_3" => VKey::Vk3,
            "4" | "vk_4" => VKey::Vk4,
            "5" | "vk_5" => VKey::Vk5,
            "6" | "vk_6" => VKey::Vk6,
            "7" | "vk_7" => VKey::Vk7,
            "8" | "vk_8" => VKey::Vk8,
            "9" | "vk_9" => VKey::Vk9,
            "a" | "vk_a" => VKey::A,
            "b" | "vk_b" => VKey::B,
            "c" | "vk_c" => VKey::C,
            "d" | "vk_d" => VKey::D,
            "e" | "vk_e" => VKey::E,
            "f" | "vk_f" => VKey::F,
            "g" | "vk_g" => VKey::G,
            "h" | "vk_h" => VKey::H,
            "i" | "vk_i" => VKey::I,
            "j" | "vk_j" => VKey::J,
            "k" | "vk_k" => VKey::K,
            "l" | "vk_l" => VKey::L,
            "m" | "vk_m" => VKey::M,
            "n" | "vk_n" => VKey::N,
            "o" | "vk_o" => VKey::O,
            "p" | "vk_p" => VKey::P,
            "q" | "vk_q" => VKey::Q,
            "r" | "vk_r" => VKey::R,
            "s" | "vk_s" => VKey::S,
            "t" | "vk_t" => VKey::T,
            "u" | "vk_u" => VKey::U,
            "v" | "vk_v" => VKey::V,
            "w" | "vk_w" => VKey::W,
            "x" | "vk_x" => VKey::X,
            "y" | "vk_y" => VKey::Y,
            "z" | "vk_z" => VKey::Z,
            "f1" | "vk_f1" => VKey::F1,
            "f2" | "vk_f2" => VKey::F2,
            "f3" | "vk_f3" => VKey::F3,
            "f4" | "vk_f4" => VKey::F4,
            "f5" | "vk_f5" => VKey::F5,
            "f6" | "vk_f6" => VKey::F6,
            "f7" | "vk_f7" => VKey::F7,
            "f8" | "vk_f8" => VKey::F8,
            "f9" | "vk_f9" => VKey::F9,
            "f10" | "vk_f10" => VKey::F10,
            "f11" | "vk_f11" => VKey::F11,
            "f12" | "vk_f12" => VKey::F12,
            _ => return Err(WHKError(format!("unknown key name '{name}'"))),
        };
        Ok(key)
    }
}

#[allow(dead_code)]
struct Hotkey {
    id: i32,
    trigger_key: VKey,
    mod_keys: Vec<VKey>,
    callback: Box<dyn Fn() + Send + 'static>,
    active: bool,
}

struct ManagerState {
    hotkeys: Vec<Hotkey>,
    interrupted: Arc<AtomicBool>,
}

#[cfg(windows)]
thread_local! {
    static ACTIVE_STATE: RefCell<Option<*mut ManagerState>> = const { RefCell::new(None) };
}

#[derive(Clone)]
pub struct InterruptHandle {
    interrupted: Arc<AtomicBool>,
    thread_id: Arc<AtomicU32>,
}

impl InterruptHandle {
    pub fn interrupt(&self) {
        self.interrupted.store(true, Ordering::SeqCst);
        let thread_id = self.thread_id.load(Ordering::SeqCst);
        if thread_id != 0 {
            #[cfg(windows)]
            unsafe {
                let _ = PostThreadMessageW(thread_id, WM_QUIT, WPARAM(0), LPARAM(0));
            }
        }
    }
}

pub struct HotkeyManager<T = ()> {
    state: ManagerState,
    next_id: i32,
    thread_id: Arc<AtomicU32>,
    _marker: PhantomData<T>,
}

impl<T: Send + 'static> HotkeyManager<T> {
    pub fn new() -> Self {
        Self {
            state: ManagerState {
                hotkeys: Vec::new(),
                interrupted: Arc::new(AtomicBool::new(false)),
            },
            next_id: 1,
            thread_id: Arc::new(AtomicU32::new(0)),
            _marker: PhantomData,
        }
    }

    pub fn register_hotkey(
        &mut self,
        trigger_key: VKey,
        mod_keys: &[VKey],
        callback: impl Fn() -> T + Send + 'static,
    ) -> Result<i32, WHKError> {
        let id = self.next_id;
        self.next_id += 1;
        self.state.hotkeys.push(Hotkey {
            id,
            trigger_key,
            mod_keys: mod_keys.to_vec(),
            callback: Box::new(move || {
                let _ = callback();
            }),
            active: false,
        });
        Ok(id)
    }

    pub fn unregister_hotkey(&mut self, hotkey_id: i32) {
        self.state.hotkeys.retain(|hotkey| hotkey.id != hotkey_id);
    }

    pub fn unregister_all(&mut self) {
        self.state.hotkeys.clear();
    }

    pub fn interrupt_handle(&self) -> InterruptHandle {
        InterruptHandle {
            interrupted: Arc::clone(&self.state.interrupted),
            thread_id: Arc::clone(&self.thread_id),
        }
    }

    #[cfg(windows)]
    pub fn event_loop(&mut self) {
        unsafe {
            // Force Windows to create this thread's message queue before the
            // interrupt handle publishes the thread id. Without this,
            // PostThreadMessageW can race startup and fail, leaving GetMessageW
            // blocked during config reload or quit.
            let mut bootstrap_msg = MSG::default();
            let _ = PeekMessageW(&mut bootstrap_msg, None, 0, 0, PM_NOREMOVE);
        }
        self.thread_id
            .store(unsafe { GetCurrentThreadId() }, Ordering::SeqCst);
        let state_ptr: *mut ManagerState = &mut self.state;
        ACTIVE_STATE.with(|state| *state.borrow_mut() = Some(state_ptr));

        let hook =
            match unsafe { SetWindowsHookExW(WH_KEYBOARD_LL, Some(keyboard_hook_proc), None, 0) } {
                Ok(hook) => hook,
                Err(_) => {
                    ACTIVE_STATE.with(|state| *state.borrow_mut() = None);
                    self.thread_id.store(0, Ordering::SeqCst);
                    return;
                }
            };

        unsafe {
            let mut msg = MSG::default();
            while !self.state.interrupted.load(Ordering::SeqCst)
                && GetMessageW(&mut msg, None, 0, 0).into()
            {
                let _ = TranslateMessage(&msg);
                DispatchMessageW(&msg);
            }
            let _ = UnhookWindowsHookEx(hook);
        }

        ACTIVE_STATE.with(|state| *state.borrow_mut() = None);
        self.thread_id.store(0, Ordering::SeqCst);
    }

    #[cfg(not(windows))]
    pub fn event_loop(&mut self) {
        while !self.state.interrupted.load(Ordering::SeqCst) {
            std::thread::sleep(std::time::Duration::from_millis(100));
        }
    }
}

impl<T: Send + 'static> Default for HotkeyManager<T> {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(windows)]
unsafe extern "system" fn keyboard_hook_proc(code: i32, wparam: WPARAM, lparam: LPARAM) -> LRESULT {
    if code < 0 {
        return CallNextHookEx(None, code, wparam, lparam);
    }

    if wparam.0 == WM_KEYDOWN as usize
        || wparam.0 == WM_SYSKEYDOWN as usize
        || wparam.0 == WM_KEYUP as usize
        || wparam.0 == WM_SYSKEYUP as usize
    {
        let kb = *(lparam.0 as *const KBDLLHOOKSTRUCT);
        let key_is_down = wparam.0 == WM_KEYDOWN as usize || wparam.0 == WM_SYSKEYDOWN as usize;
        ACTIVE_STATE.with(|state| {
            if let Some(state_ptr) = *state.borrow() {
                let state = &mut *state_ptr;
                if !state.interrupted.load(Ordering::SeqCst) {
                    for hotkey in &mut state.hotkeys {
                        if kb.vkCode as u16 == hotkey.trigger_key.to_vk_code() {
                            if key_is_down
                                && !hotkey.active
                                && hotkey.mod_keys.iter().all(|key| is_pressed(*key))
                            {
                                hotkey.active = true;
                                (hotkey.callback)();
                            } else if !key_is_down {
                                hotkey.active = false;
                            }
                        }
                    }
                }
            }
        });
    }

    CallNextHookEx(None, code, wparam, lparam)
}

#[cfg(windows)]
fn is_pressed(key: VKey) -> bool {
    let vk = key.to_vk_code() as i32;
    unsafe { (GetAsyncKeyState(vk) & (0x8000u16 as i16)) != 0 }
}
