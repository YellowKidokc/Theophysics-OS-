use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::Mutex;
use std::sync::OnceLock;
use std::time::{Duration, Instant};
use tracing::{error, info, warn};

#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;

/// Hide console window when spawning processes
#[cfg(target_os = "windows")]
const CREATE_NO_WINDOW: u32 = 0x08000000;

/// Registry path for legacy SAPI voice tokens
const SAPI_VOICES_PATH: &str = "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices";

/// Registry path for OneCore/Neural voice tokens
const ONECORE_VOICES_PATH: &str = "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech_OneCore\\Voices";

/// Subprocess timeout for edge_tts --list-voices (Change 5)
const EDGE_TTS_TIMEOUT_SECS: u64 = 8;

/// Volume scale factor for OneCore voices (Change 6).
/// OneCore voices render ~10-15% louder than SAPI Desktop voices at the same
/// volume value.
const ONECORE_VOLUME_FACTOR: f32 = 0.87;

// ── Voice info ──────────────────────────────────────────────────────────────

/// Information about a single TTS voice, from any engine/hive.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VoiceInfo {
    /// Full token ID (registry path for SAPI/OneCore, ShortName for Edge)
    pub id: String,
    /// Human-readable display name
    pub name: String,
    /// Language/locale code
    pub lang: String,
    /// Source hive: "sapi", "onecore", or "edge"
    pub hive: String,
}

// ── TTS settings ────────────────────────────────────────────────────────────

/// TTS settings (loaded from config, changeable at runtime)
pub struct TtsSettings {
    pub voice: String,  // voice name for matching against enumerated list
    pub speed: i32,     // SAPI rate: -10 to 10 (0=normal, 2=slightly fast, 5=fast)
    pub engine: String, // "edge" or "sapi"
    pub volume: u32,    // 0-100
}

static TTS_SETTINGS: OnceLock<Mutex<TtsSettings>> = OnceLock::new();

fn settings() -> &'static Mutex<TtsSettings> {
    TTS_SETTINGS.get_or_init(|| {
        Mutex::new(TtsSettings {
            voice: "Brian".into(), // Microsoft Brian Online — natural male
            speed: 2,              // slightly fast
            engine: "sapi".into(), // works out of the box
            volume: 100,
        })
    })
}

/// PID of the currently speaking subprocess (for stop functionality)
static SPEAKING_PID: OnceLock<Mutex<Option<u32>>> = OnceLock::new();

fn speaking_pid() -> &'static Mutex<Option<u32>> {
    SPEAKING_PID.get_or_init(|| Mutex::new(None))
}

/// In-memory cache of the last successful voice enumeration, used for fast
/// lookups during speak() without re-enumerating.
static VOICE_LIST: OnceLock<Mutex<Vec<VoiceInfo>>> = OnceLock::new();

fn voice_list_store() -> &'static Mutex<Vec<VoiceInfo>> {
    VOICE_LIST.get_or_init(|| Mutex::new(Vec::new()))
}

/// Update TTS settings at runtime
pub fn configure(voice: &str, speed: i32, engine: &str, volume: u32) {
    let mut s = settings().lock().unwrap();
    s.voice = voice.into();
    s.speed = speed;
    s.engine = engine.into();
    s.volume = volume;
    info!(
        "TTS configured: voice={}, speed={}, engine={}, vol={}",
        voice, speed, engine, volume
    );
}

/// Populate the voice cache in the background so the first TTS request can
/// validate voices without doing slow registry or Edge TTS enumeration work.
pub fn warm_voice_cache() {
    std::thread::spawn(|| {
        let result = get_voices();
        if result.voices.is_empty() {
            warn!("TTS voice warmup found no voices: {:?}", result.errors);
        } else {
            info!(
                "TTS voice warmup cached {} voices{}",
                result.voices.len(),
                if result.stale { " (stale cache)" } else { "" }
            );
        }
    });
}

// ── Dual-hive SAPI voice enumeration (Change 1) ────────────────────────────

/// Enumerate voices from a specific SAPI registry hive using COM.
///
/// Uses `ISpObjectTokenCategory::SetId()` with the full registry path string
/// instead of the `SPCAT_VOICES` constant, which is the key to accessing the
/// OneCore hive (there is no SPCAT_ constant for it).
fn enumerate_from_path(path: &str, hive: &str) -> Result<Vec<VoiceInfo>, String> {
    use windows::core::PCWSTR;
    use windows::Win32::Media::Speech::{ISpObjectTokenCategory, SpObjectTokenCategory};
    use windows::Win32::System::Com::{
        CoCreateInstance, CoInitializeEx, CLSCTX_ALL, COINIT_APARTMENTTHREADED,
    };

    unsafe {
        // Ensure COM is initialized on this thread (ignored if already init'd)
        let _ = CoInitializeEx(None, COINIT_APARTMENTTHREADED);

        let category: ISpObjectTokenCategory =
            CoCreateInstance(&SpObjectTokenCategory, None, CLSCTX_ALL)
                .map_err(|e| format!("CoCreateInstance(SpObjectTokenCategory): {e}"))?;

        let wide_path: Vec<u16> = path.encode_utf16().chain(std::iter::once(0u16)).collect();

        // SetId accepts an arbitrary registry path string, not just SPCAT_
        // constants. This is the key to enumerating the OneCore hive.
        category
            .SetId(PCWSTR(wide_path.as_ptr()), false)
            .map_err(|e| format!("SetId({path}): {e}"))?;

        let enum_tokens = category
            .EnumTokens(PCWSTR::null(), PCWSTR::null())
            .map_err(|e| format!("EnumTokens({path}): {e}"))?;

        let mut count: u32 = 0;
        enum_tokens
            .GetCount(&mut count)
            .map_err(|e| format!("GetCount({path}): {e}"))?;

        let mut result = Vec::new();
        for i in 0..count {
            match enum_tokens.Item(i) {
                Ok(tok) => {
                    let id_ptr = tok.GetId().map_err(|e| format!("GetId: {e}"))?;
                    let id = id_ptr.to_string().unwrap_or_default();

                    let (name, lang) = match tok.OpenKey(windows::core::w!("Attributes")) {
                        Ok(attrs) => {
                            let name = attrs
                                .GetStringValue(windows::core::w!("Name"))
                                .ok()
                                .and_then(|v| v.to_string().ok())
                                .unwrap_or_else(|| id.clone());
                            let lang = attrs
                                .GetStringValue(windows::core::w!("Language"))
                                .ok()
                                .and_then(|v| v.to_string().ok())
                                .unwrap_or_default();
                            (name, lang)
                        }
                        Err(_) => (id.clone(), String::new()),
                    };

                    result.push(VoiceInfo {
                        id,
                        name,
                        lang,
                        hive: hive.to_string(),
                    });
                }
                Err(e) => {
                    warn!("EnumTokens.Item({i}) error in {hive} hive: {e}");
                    continue;
                }
            }
        }

        Ok(result)
    }
}

/// Enumerate all SAPI voices from both the legacy and OneCore hives.
///
/// CRITICAL: deduplicates by display name (not token ID) because David, Zira,
/// and Mark exist in both hives with different token paths but the same name.
pub fn enumerate_all_voices() -> Vec<VoiceInfo> {
    let mut voices = Vec::new();

    // Read each hive independently — never let one hive's failure prevent
    // the other from returning results.
    match enumerate_from_path(SAPI_VOICES_PATH, "sapi") {
        Ok(v) => {
            info!("SAPI hive: {} voices", v.len());
            voices.extend(v);
        }
        Err(e) => warn!("SAPI hive enumeration failed: {e}"),
    }

    match enumerate_from_path(ONECORE_VOICES_PATH, "onecore") {
        Ok(v) => {
            info!("OneCore hive: {} voices", v.len());
            voices.extend(v);
        }
        Err(e) => warn!("OneCore hive enumeration failed: {e}"),
    }

    // Dedup by Name, not ID.
    voices.sort_by(|a, b| a.name.cmp(&b.name));
    voices.dedup_by(|a, b| a.name == b.name);

    voices
}

// ── Edge TTS preflight + voice fetch (Changes 2, 5) ────────────────────────

/// Check that the Python launcher and edge-tts package are available.
/// Returns Ok(()) if both are working, or a specific, actionable error message.
pub fn check_edge_tts_available() -> Result<(), String> {
    // Step 1: confirm py launcher is on PATH and functional
    let py = new_hidden_command("py")
        .arg("--version")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|_| {
            "Python launcher 'py' not found on PATH. \
             Install Python from python.org and ensure the 'py' launcher is included."
                .to_string()
        })?;

    if !py.status.success() {
        return Err(
            "Python launcher 'py' is present but not functional. Reinstall Python.".to_string(),
        );
    }

    // Step 2: confirm edge-tts package is importable in the resolved Python
    let pkg = new_hidden_command("py")
        .args(["-c", "import edge_tts; print('ok')"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|e| format!("Failed to probe edge_tts package: {e}"))?;

    if !pkg.status.success() {
        let stderr = String::from_utf8_lossy(&pkg.stderr);
        return Err(format!(
            "edge-tts package not installed or broken. \
             Run: py -m pip install edge-tts\nDetails: {}",
            stderr.trim()
        ));
    }

    Ok(())
}

/// Fetch Edge TTS voices with preflight checks and subprocess timeout.
pub fn get_edge_voices() -> Result<Vec<VoiceInfo>, String> {
    check_edge_tts_available()?;

    let output = run_with_timeout(
        new_hidden_command("py")
            .args(["-m", "edge_tts", "--list-voices"])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped()),
        Duration::from_secs(EDGE_TTS_TIMEOUT_SECS),
    )?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("edge_tts --list-voices failed: {}", stderr.trim()));
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    parse_edge_voices(&stdout)
}

/// Run a command with a timeout (Change 5).
///
/// Uses a poll loop with `try_wait` instead of an external dependency.
/// Returns the output if the process finishes within the deadline, or kills
/// the process and returns an error on timeout.
fn run_with_timeout(cmd: &mut Command, timeout: Duration) -> Result<std::process::Output, String> {
    let mut child = cmd
        .spawn()
        .map_err(|e| format!("Subprocess spawn failed: {e}"))?;

    let start = Instant::now();
    loop {
        match child.try_wait() {
            Ok(Some(_)) => {
                return child
                    .wait_with_output()
                    .map_err(|e| format!("Failed to read subprocess output: {e}"));
            }
            Ok(None) => {
                if start.elapsed() > timeout {
                    let _ = child.kill();
                    let _ = child.wait(); // reap zombie
                    return Err(format!(
                        "Subprocess timed out after {} seconds. \
                         This usually means a network issue reaching \
                         speech.platform.bing.com.",
                        timeout.as_secs()
                    ));
                }
                std::thread::sleep(Duration::from_millis(100));
            }
            Err(e) => return Err(format!("Failed to check subprocess status: {e}")),
        }
    }
}

/// Parse the JSON output of `edge_tts --list-voices` into VoiceInfo entries.
fn parse_edge_voices(output: &str) -> Result<Vec<VoiceInfo>, String> {
    if output.trim_start().starts_with('[') {
        return parse_edge_voices_json(output);
    }

    parse_edge_voices_table(output)
}

fn parse_edge_voices_json(output: &str) -> Result<Vec<VoiceInfo>, String> {
    let entries: Vec<serde_json::Value> = serde_json::from_str(output)
        .map_err(|e| format!("Failed to parse edge_tts voice list as JSON: {e}"))?;

    let mut voices = Vec::new();
    for entry in &entries {
        let short_name = entry["ShortName"].as_str().unwrap_or_default();
        let locale = entry["Locale"].as_str().unwrap_or_default();
        let friendly = entry["FriendlyName"]
            .as_str()
            .or_else(|| entry["Name"].as_str())
            .unwrap_or(short_name);

        if !short_name.is_empty() {
            voices.push(VoiceInfo {
                id: short_name.to_string(),
                name: friendly.to_string(),
                lang: locale.to_string(),
                hive: "edge".to_string(),
            });
        }
    }

    Ok(voices)
}

fn parse_edge_voices_table(output: &str) -> Result<Vec<VoiceInfo>, String> {
    let mut voices = Vec::new();
    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with("Name ") || trimmed.starts_with("---") {
            continue;
        }

        let short_name = match trimmed.split_whitespace().next() {
            Some(name) if name.contains("Neural") => name,
            _ => continue,
        };
        let locale = short_name.split('-').take(2).collect::<Vec<_>>().join("-");

        voices.push(VoiceInfo {
            id: short_name.to_string(),
            name: short_name.to_string(),
            lang: locale,
            hive: "edge".to_string(),
        });
    }

    if voices.is_empty() {
        Err("No Edge voices parsed from edge_tts output".to_string())
    } else {
        Ok(voices)
    }
}

// ── Voice list cache fallback (Change 3) ────────────────────────────────────

fn cache_path() -> PathBuf {
    let mut p = dirs::data_local_dir().expect("LOCALAPPDATA not resolvable");
    p.push("ClipSync");
    p.push("voice_cache.json");
    p
}

fn save_voice_cache(voices: &[VoiceInfo]) {
    let path = cache_path();
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    match serde_json::to_string(voices) {
        Ok(json) => {
            if let Err(e) = std::fs::write(&path, json) {
                warn!("Failed to write voice cache: {e}");
            } else {
                info!(
                    "Voice cache saved: {} voices to {}",
                    voices.len(),
                    path.display()
                );
            }
        }
        Err(e) => warn!("Failed to serialize voice cache: {e}"),
    }
}

fn load_voice_cache() -> Option<Vec<VoiceInfo>> {
    let path = cache_path();
    let json = std::fs::read_to_string(&path).ok()?;
    let voices: Vec<VoiceInfo> = serde_json::from_str(&json).ok()?;
    if voices.is_empty() {
        None
    } else {
        info!(
            "Loaded {} voices from cache ({})",
            voices.len(),
            path.display()
        );
        Some(voices)
    }
}

// ── Public voice list (combines SAPI + Edge + cache) ────────────────────────

/// Result of a voice enumeration, indicating freshness and any errors.
#[derive(Debug, Clone, Serialize)]
pub struct VoiceListResult {
    pub voices: Vec<VoiceInfo>,
    pub stale: bool,
    pub errors: Vec<String>,
}

/// Get all available voices across all engines, with cache fallback.
///
/// This is the primary entry point for the settings UI to populate the voice
/// dropdown. It enumerates SAPI (both hives) and Edge TTS, saves to cache on
/// success, and falls back to cache on total failure.
pub fn get_voices() -> VoiceListResult {
    let mut voices = Vec::new();
    let mut errors = Vec::new();

    // SAPI + OneCore (COM dual-hive)
    let sapi_voices = enumerate_all_voices();
    if sapi_voices.is_empty() {
        errors.push("No SAPI voices found from either registry hive".to_string());
    }
    voices.extend(sapi_voices);

    // Edge TTS (with preflight checks + timeout)
    match get_edge_voices() {
        Ok(edge) => {
            info!("Edge TTS: {} voices", edge.len());
            voices.extend(edge);
        }
        Err(e) => {
            warn!("Edge TTS unavailable: {e}");
            errors.push(e);
        }
    }

    if !voices.is_empty() {
        // Fresh enumeration produced results — update both caches
        save_voice_cache(&voices);
        *voice_list_store().lock().unwrap() = voices.clone();
        VoiceListResult {
            voices,
            stale: false,
            errors,
        }
    } else {
        // Complete failure — fall back to file cache
        match load_voice_cache() {
            Some(cached) => {
                warn!("Using cached voice list ({} voices)", cached.len());
                errors.push("Using cached voice list — live enumeration failed".to_string());
                *voice_list_store().lock().unwrap() = cached.clone();
                VoiceListResult {
                    voices: cached,
                    stale: true,
                    errors,
                }
            }
            None => {
                errors.push("No voice cache available".to_string());
                VoiceListResult {
                    voices: Vec::new(),
                    stale: true,
                    errors,
                }
            }
        }
    }
}

/// Find a voice by name (case-insensitive partial match, matching the existing
/// PowerShell -match behavior) in a voice list.
fn find_voice(voices: &[VoiceInfo], name: &str) -> Option<VoiceInfo> {
    let lower = name.to_lowercase();
    voices
        .iter()
        .find(|v| v.name.to_lowercase().contains(&lower) || v.id.to_lowercase().contains(&lower))
        .cloned()
}

// ── Speech functions ────────────────────────────────────────────────────────

/// Read the currently selected text aloud.
pub fn read_selection() {
    send_ctrl_c();
    std::thread::sleep(Duration::from_millis(150));

    let text = match get_clipboard_text() {
        Ok(t) if !t.is_empty() => t,
        _ => {
            info!("TTS: no text selected");
            return;
        }
    };

    info!("TTS: reading {} chars", text.len());
    if let Err(e) = speak(&text) {
        error!("TTS speak failed: {}", e);
    }
}

/// Speak text with configured voice/speed.
///
/// Validates the configured voice against the known voice list (Change 4)
/// and applies volume normalization for OneCore voices (Change 6).
/// Returns an error if the configured voice is not available.
pub fn speak(text: &str) -> Result<(), String> {
    let s = settings().lock().unwrap();
    let voice_name = s.voice.clone();
    let speed = s.speed;
    let volume = s.volume;
    let engine = s.engine.clone();
    drop(s); // Release lock before spawning

    match engine.as_str() {
        "edge" => match speak_edge_tts(text, &voice_name, speed) {
            Ok(()) => Ok(()),
            Err(e) => {
                warn!("Edge TTS failed, falling back to SAPI: {}", e);
                let default_voice = VoiceInfo {
                    id: String::new(),
                    name: "default".to_string(),
                    lang: String::new(),
                    hive: "sapi".to_string(),
                };
                speak_sapi(text, &default_voice, speed, volume);
                Ok(())
            }
        },
        _ => {
            // For "default" or empty voice, skip validation — use SAPI default
            if voice_name.is_empty() || voice_name == "default" {
                let default_vi = VoiceInfo {
                    id: String::new(),
                    name: "default".into(),
                    lang: String::new(),
                    hive: "sapi".into(),
                };
                speak_sapi(text, &default_vi, speed, volume);
                return Ok(());
            }

            // Look up voice in the in-memory cache first, then file cache
            let voices = voice_list_store().lock().unwrap().clone();
            let voices = if voices.is_empty() {
                load_voice_cache().unwrap_or_default()
            } else {
                voices
            };

            // If no voice list available yet, skip validation to avoid blocking
            if voices.is_empty() {
                warn!(
                    "Voice list not populated yet, skipping validation for '{}'",
                    voice_name
                );
                let vi = VoiceInfo {
                    id: String::new(),
                    name: voice_name.clone(),
                    lang: String::new(),
                    hive: "sapi".into(),
                };
                speak_sapi(text, &vi, speed, volume);
                return Ok(());
            }

            // Token ID validation (Change 4)
            match find_voice(&voices, &voice_name) {
                Some(vi) => {
                    // Volume normalization for OneCore voices (Change 6)
                    let effective_volume = if vi.hive == "onecore" {
                        ((volume as f32) * ONECORE_VOLUME_FACTOR) as u32
                    } else {
                        volume
                    };
                    speak_sapi(text, &vi, speed, effective_volume);
                    Ok(())
                }
                None => Err(format!(
                    "Voice '{}' is no longer available. \
                     Please select a different voice from the dropdown.",
                    voice_name
                )),
            }
        }
    }
}

/// Stop any currently playing speech.
///
/// Kills the tracked speaking subprocess (PowerShell or edge-playback) by PID.
pub fn stop() {
    // Kill the tracked speaking subprocess, if any
    if let Some(pid) = speaking_pid().lock().unwrap().take() {
        let _ = new_hidden_command("taskkill")
            .args(["/PID", &pid.to_string(), "/F", "/T"])
            .output();
    }
    // Also kill edge-playback processes (spawned by speak_edge_tts)
    let _ = new_hidden_command("taskkill")
        .args(["/IM", "edge-playback.exe", "/F"])
        .output();
    info!("TTS: stopped");
}

fn speak_sapi(text: &str, voice: &VoiceInfo, speed: i32, volume: u32) {
    let escaped = text
        .replace('\'', "''")
        .replace('\n', " ")
        .replace('\r', "")
        .replace('`', "'");

    let rate = speed.clamp(-10, 10);

    let voice_setup = if voice.name.is_empty() || voice.name == "default" {
        String::new()
    } else {
        format!(
            "$match = $synth.GetInstalledVoices() | Where-Object {{ $_.VoiceInfo.Name -like '*{}*' }} | Select-Object -First 1; \
             if ($match) {{ $synth.SelectVoice($match.VoiceInfo.Name) }};",
            voice.name.replace('\'', "''")
        )
    };

    let script = format!(
        "Add-Type -AssemblyName System.Speech; \
         $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; \
         {}; \
         $synth.Rate = {}; \
         $synth.Volume = {}; \
         $synth.Speak('{}')",
        voice_setup, rate, volume, escaped
    );

    match new_hidden_command("powershell")
        .args(["-NoProfile", "-Command", &script])
        .spawn()
    {
        Ok(child) => {
            *speaking_pid().lock().unwrap() = Some(child.id());
            info!(
                "TTS SAPI: voice={}, hive={}, rate={}, vol={}",
                voice.name, voice.hive, rate, volume
            );
        }
        Err(e) => error!("TTS SAPI failed: {}", e),
    }
}

/// Speak using Edge TTS (pip install edge-tts for natural voices)
fn speak_edge_tts(text: &str, voice: &str, speed: i32) -> Result<(), String> {
    check_edge_playback_available()?;

    let normalized_text = text.replace('\n', " ").replace('\r', " ");
    let rate_pct = speed * 10;
    let rate_str = if rate_pct >= 0 {
        format!("+{}%", rate_pct)
    } else {
        format!("{}%", rate_pct)
    };
    let voice = if voice.is_empty() || voice == "default" {
        "en-US-GuyNeural"
    } else {
        voice
    };

    let mut child = new_hidden_command("py")
        .args([
            "-m",
            "edge_playback",
            "--voice",
            voice,
            "--rate",
            &rate_str,
            "--text",
            &normalized_text,
        ])
        .spawn()
        .map_err(|e| format!("Failed to launch edge_playback: {e}"))?;

    let pid = child.id();
    *speaking_pid().lock().unwrap() = Some(pid);
    std::thread::sleep(Duration::from_millis(350));

    match child.try_wait() {
        Ok(Some(status)) if !status.success() => {
            *speaking_pid().lock().unwrap() = None;
            Err(format!("edge_playback exited early with status {status}"))
        }
        Ok(_) => {
            info!("TTS Edge: voice={}, rate={}", voice, rate_str);
            Ok(())
        }
        Err(e) => {
            *speaking_pid().lock().unwrap() = None;
            Err(format!(
                "Failed to monitor edge_playback process {pid}: {e}"
            ))
        }
    }
}

fn check_edge_playback_available() -> Result<(), String> {
    check_edge_tts_available()?;

    let output = run_with_timeout(
        new_hidden_command("py")
            .args(["-m", "edge_playback", "--help"])
            .stdout(Stdio::null())
            .stderr(Stdio::piped()),
        Duration::from_secs(5),
    )?;

    if output.status.success() {
        Ok(())
    } else {
        let stderr = String::from_utf8_lossy(&output.stderr);
        Err(format!(
            "edge_playback module is unavailable. Run: py -m pip install edge-tts. Details: {}",
            stderr.trim()
        ))
    }
}

/// Save speech to audio file
#[allow(dead_code)]
pub fn save_audio(text: &str, output_path: &str) {
    let s = settings().lock().unwrap();
    let voice = s.voice.clone();
    let speed = s.speed;
    let engine = s.engine.clone();
    drop(s);

    let escaped = text
        .replace('\'', "''")
        .replace('\n', " ")
        .replace('\r', "");

    match engine.as_str() {
        "edge" => {
            let rate_pct = speed * 10;
            let rate_str = if rate_pct >= 0 {
                format!("+{}%", rate_pct)
            } else {
                format!("{}%", rate_pct)
            };
            let v = if voice.is_empty() || voice == "default" {
                "en-US-GuyNeural".into()
            } else {
                voice
            };
            let _ = new_hidden_command("py")
                .args([
                    "-m",
                    "edge_tts",
                    "--voice",
                    &v,
                    "--rate",
                    &rate_str,
                    "--text",
                    &escaped,
                    "--write-media",
                    output_path,
                ])
                .spawn();
        }
        _ => {
            let script = format!(
                "Add-Type -AssemblyName System.Speech; \
                 $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; \
                 $synth.Rate = {}; \
                 $synth.SetOutputToWaveFile('{}'); \
                 $synth.Speak('{}'); \
                 $synth.SetOutputToDefaultAudioDevice()",
                speed,
                output_path.replace('\'', "''"),
                escaped
            );
            let _ = new_hidden_command("powershell")
                .args(["-NoProfile", "-Command", &script])
                .spawn();
        }
    }
    info!("TTS: saving audio to {}", output_path);
}

/// List available voice names (backward-compatible wrapper around get_voices).
#[allow(dead_code)]
pub fn list_voices() -> Vec<String> {
    get_voices().voices.into_iter().map(|v| v.name).collect()
}

/// Create a Command that hides the console window on Windows
fn new_hidden_command(program: &str) -> Command {
    let mut cmd = Command::new(program);
    if let Some(path) = python_scripts_path() {
        let current = std::env::var("PATH").unwrap_or_default();
        cmd.env("PATH", format!("{};{}", path.display(), current));
    }
    #[cfg(target_os = "windows")]
    {
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd
}

fn python_scripts_path() -> Option<PathBuf> {
    let appdata = std::env::var_os("APPDATA")?;
    let python_dir = PathBuf::from(appdata).join("Python");
    let entries = std::fs::read_dir(python_dir).ok()?;
    for entry in entries.flatten() {
        let path = entry.path().join("Scripts");
        if path.join("edge-tts.exe").exists() {
            return Some(path);
        }
    }
    None
}

fn send_ctrl_c() {
    use windows::Win32::UI::Input::KeyboardAndMouse::*;

    let inputs = [
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
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_C,
                    wScan: 0,
                    dwFlags: KEYBD_EVENT_FLAGS(0),
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        },
        INPUT {
            r#type: INPUT_KEYBOARD,
            Anonymous: INPUT_0 {
                ki: KEYBDINPUT {
                    wVk: VK_C,
                    wScan: 0,
                    dwFlags: KEYEVENTF_KEYUP,
                    time: 0,
                    dwExtraInfo: 0,
                },
            },
        },
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

fn get_clipboard_text() -> anyhow::Result<String> {
    use clipboard_win::{formats, get_clipboard};
    let text: String =
        get_clipboard(formats::Unicode).map_err(|e| anyhow::anyhow!("clipboard: {:?}", e))?;
    Ok(text)
}
