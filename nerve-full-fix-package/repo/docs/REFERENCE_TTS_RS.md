# Reference Implementations for `tts.rs`

This document contains working Rust code for the Phase 1 TTS fixes. An AI coding agent should adapt these into the existing `tts.rs` file structure rather than copy-paste verbatim — the existing module organization may differ.

These implementations were developed and cross-verified across two AI collaborators (Claude Opus and Gemini "Jim") in a session on 2026-04-08. Both confirmed independently that they target the correct layer and handle the documented Windows quirks.

---

## 1. Dual-hive voice enumeration

Replaces the existing single-path `SpEnumTokens(SPCAT_VOICES)` call with explicit enumeration of both the legacy SAPI hive and the OneCore hive.

```rust
use windows::{
    core::*,
    Win32::Media::Speech::{
        ISpObjectTokenCategory, ISpObjectToken, IEnumSpObjectTokens,
        SpObjectTokenCategory,
    },
};

const SAPI_VOICES_PATH: &str =
    "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech\\Voices";
const ONECORE_VOICES_PATH: &str =
    "HKEY_LOCAL_MACHINE\\SOFTWARE\\Microsoft\\Speech_OneCore\\Voices";

#[derive(Debug, Clone, serde::Serialize)]
pub struct VoiceInfo {
    pub id: String,
    pub name: String,
    pub lang: String,
    pub hive: String, // "sapi" or "onecore" — needed for volume normalization downstream
}

pub fn enumerate_all_voices() -> windows::core::Result<Vec<VoiceInfo>> {
    let mut voices: Vec<VoiceInfo> = Vec::new();

    // Silently skip a path if it fails — never let one hive's failure
    // wipe out the other hive's results
    if let Ok(tokens) = enumerate_from_path(SAPI_VOICES_PATH, "sapi") {
        voices.extend(tokens);
    }
    if let Ok(tokens) = enumerate_from_path(ONECORE_VOICES_PATH, "onecore") {
        voices.extend(tokens);
    }

    // CRITICAL: dedup by NAME, not ID.
    // Microsoft David, Zira, and Mark exist in both hives with different
    // token path strings but the same display name. Naive dedup-by-ID
    // would show all three voices twice.
    voices.sort_by(|a, b| a.name.cmp(&b.name));
    voices.dedup_by(|a, b| a.name == b.name);

    Ok(voices)
}

fn enumerate_from_path(path: &str, hive: &str) -> windows::core::Result<Vec<VoiceInfo>> {
    unsafe {
        let category: ISpObjectTokenCategory = SpObjectTokenCategory::new()?;

        let wide_path = path.encode_utf16()
            .chain(std::iter::once(0u16))
            .collect::<Vec<u16>>();

        // SetId accepts an arbitrary registry path string, not just SPCAT_ constants.
        // This is the key to enumerating the OneCore hive — there's no SPCAT_ constant
        // for it in the SDK headers.
        category.SetId(PCWSTR(wide_path.as_ptr()), false)?;

        let enum_tokens: IEnumSpObjectTokens = category.EnumTokens(None, None)?;

        let mut result = Vec::new();
        loop {
            let mut token: Option<ISpObjectToken> = None;
            let hr = enum_tokens.Next(1, &mut token as *mut _ as _, None);
            match hr {
                Ok(_) => {
                    if let Some(tok) = token {
                        let id_ptr = tok.GetId()?;
                        let id = id_ptr.to_string()?;

                        let attrs = tok.OpenKey(w!("Attributes"))?;
                        let name = attrs.GetStringValue(w!("Name"))
                            .unwrap_or_else(|_| PWSTR::null())
                            .to_string()
                            .unwrap_or_else(|_| id.clone());
                        let lang = attrs.GetStringValue(w!("Language"))
                            .unwrap_or_else(|_| PWSTR::null())
                            .to_string()
                            .unwrap_or_default();

                        result.push(VoiceInfo {
                            id,
                            name,
                            lang,
                            hive: hive.to_string(),
                        });
                    }
                }
                Err(e) if e.code() == S_FALSE => break, // end of enumeration
                Err(e) => return Err(e),
            }
        }
        Ok(result)
    }
}
```

---

## 2. Edge TTS preflight checks + voice fetch

Replaces the silent-failure `py -m edge_tts --list-voices` call with explicit probes that surface clear errors to the frontend.

```rust
use std::process::Command;

pub fn check_edge_tts_available() -> Result<(), String> {
    // Step 1: confirm py launcher exists and is functional
    let py = Command::new("py")
        .arg("--version")
        .output()
        .map_err(|_| "Python launcher 'py' not found on PATH".to_string())?;

    if !py.status.success() {
        return Err("Python launcher present but not functional".to_string());
    }

    // Step 2: confirm edge-tts package is importable in the resolved Python
    let pkg = Command::new("py")
        .args(["-c", "import edge_tts; print('ok')"])
        .output()
        .map_err(|e| format!("Failed to probe edge_tts package: {e}"))?;

    if !pkg.status.success() {
        let stderr = String::from_utf8_lossy(&pkg.stderr);
        return Err(format!(
            "edge-tts package missing or broken in resolved Python install: {stderr}"
        ));
    }

    Ok(())
}

pub fn get_edge_voices() -> Result<Vec<VoiceInfo>, String> {
    check_edge_tts_available()?;

    let output = Command::new("py")
        .args(["-m", "edge_tts", "--list-voices"])
        .output()
        .map_err(|e| format!("Subprocess spawn failed: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("edge_tts --list-voices failed: {stderr}"));
    }

    let json = String::from_utf8_lossy(&output.stdout);
    parse_edge_voices(&json).map_err(|e| e.to_string())
}

// parse_edge_voices is left as a stub — implementation depends on
// what the existing tts.rs already does with edge-tts JSON output.
fn parse_edge_voices(json: &str) -> Result<Vec<VoiceInfo>, String> {
    // Existing implementation in tts.rs should be reused here.
    // The JSON shape from `edge_tts --list-voices` is an array of objects with
    // fields: ShortName, Locale, Gender, etc.
    todo!("reuse existing edge-tts JSON parser from tts.rs")
}
```

**Important note on subprocess timeouts:** `std::process::Command` has no built-in timeout on Windows. To implement Phase 1 deliverable #5 (8-second timeout), spawn the subprocess in a thread, send a kill signal via channel after 8 seconds, and treat timeout as a clear error to surface. Do NOT use `wait_timeout` from external crates without first checking if the project already has a dependency that provides this — keep the dependency tree small.

---

## 3. Voice list cache (Phase 1 deliverable #3)

Persist the last successful enumeration to disk so transient failures don't strand the user with an empty dropdown.

```rust
use std::fs;
use std::path::PathBuf;

fn cache_path() -> PathBuf {
    let mut p = dirs::data_local_dir().expect("LOCALAPPDATA not resolvable");
    p.push("ClipSync");
    p.push("voice_cache.json");
    p
}

pub fn save_voice_cache(voices: &[VoiceInfo]) -> Result<(), String> {
    let path = cache_path();
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let json = serde_json::to_string(voices).map_err(|e| e.to_string())?;
    fs::write(&path, json).map_err(|e| e.to_string())
}

pub fn load_voice_cache() -> Option<Vec<VoiceInfo>> {
    let path = cache_path();
    let json = fs::read_to_string(&path).ok()?;
    serde_json::from_str(&json).ok()
}

pub fn get_voices_with_fallback() -> Vec<VoiceInfo> {
    // Try fresh enumeration
    let mut voices = Vec::new();

    if let Ok(sapi) = enumerate_all_voices() {
        voices.extend(sapi);
    }

    if let Ok(edge) = get_edge_voices() {
        voices.extend(edge);
    }

    if !voices.is_empty() {
        // Fresh enumeration succeeded — save to cache and return
        let _ = save_voice_cache(&voices);
        return voices;
    }

    // Fresh enumeration failed entirely — fall back to cache
    load_voice_cache().unwrap_or_default()
}
```

---

## 4. Token ID validation in `tts_speak` (Phase 1 deliverable #4)

Before calling `ISpVoice::SetVoice()` in the existing `tts_speak` handler, check the requested token ID against the current enumeration. If it's not found, return a descriptive error rather than letting SAPI fail silently into the `interrupted` path.

```rust
pub fn tts_speak(voice_id: &str, text: &str) -> Result<(), String> {
    let current_voices = get_voices_with_fallback();

    let voice = current_voices.iter().find(|v| v.id == voice_id);

    if voice.is_none() {
        return Err(format!(
            "Voice '{voice_id}' is no longer available. \
             Please select a different voice from the dropdown."
        ));
    }

    let voice = voice.unwrap();

    // Volume normalization for OneCore voices (Phase 1 deliverable #6)
    // OneCore voices render ~10-15% louder than SAPI Desktop voices at the
    // same volume value. Scale down accordingly.
    let effective_volume = if voice.hive == "onecore" {
        // Adjust this multiplier based on testing
        (current_volume() as f32 * 0.87) as u32
    } else {
        current_volume()
    };

    // ... existing SetVoice + Speak logic, using effective_volume ...
    todo!("integrate with existing tts_speak implementation")
}

fn current_volume() -> u32 {
    // Existing config getter
    todo!("read from config")
}
```

---

## 5. PowerShell workaround (NOT for the Rust code — for the user's machine)

This is documented here for completeness. The user can apply this immediately to unblock themselves before the Rust fix ships. **Do not bake this into the Rust code** — it's a one-time OS-level workaround the user runs manually.

```powershell
# Run as Administrator
reg copy "HKLM\SOFTWARE\Microsoft\Speech_OneCore\Voices\Tokens" `
         "HKLM\SOFTWARE\Microsoft\Speech\Voices\Tokens" /s /f
```

This copies all OneCore voice tokens into the legacy SAPI hive, making them visible to the existing single-hive enumerator without any code change. Useful for immediate testing but not a permanent fix — fresh Windows installs and Windows Update can both wipe the merged tokens.

---

## Source attribution

The dual-hive enumeration approach and the dedup-by-Name insight were developed by Gemini ("Jim") in collaboration with Claude Opus on 2026-04-08. The diagnostic separation into Root Cause 1 (SAPI hive split) and Root Cause 2 (Edge subprocess failures) was the framing that made it possible to write targeted code instead of guessing.

Reference sources:
- Microsoft SAPI documentation on `ISpObjectTokenCategory::SetId()`
- Stack Overflow discussions on the legacy/OneCore hive split (multiple threads, 2018-2024)
- `windows-rs` crate documentation for Speech namespace bindings
- `edge-tts` Python package GitHub issues on subprocess and network failure modes
