use crate::config::Config;
use crate::AppEvent;
use anyhow::Result;
use std::sync::{Arc, Mutex};
use tao::event_loop::EventLoopProxy;
use tracing::{error, info, warn};

/// Push a clipboard entry to the Cloudflare API
pub async fn push_clip(cfg: &Arc<Mutex<Config>>, content: &str) -> Result<()> {
    let (api_url, api_token) = {
        let c = cfg.lock().unwrap();
        (c.api_url.clone(), c.api_token.clone())
    };

    if api_token.is_empty() {
        return Ok(()); // No API configured yet
    }

    let client = reqwest::Client::new();
    let resp = client
        .post(format!("{}/clipboard/push", api_url))
        .header("Authorization", format!("Bearer {}", api_token))
        .json(&serde_json::json!({
            "content": content,
            "source": "desktop"
        }))
        .send()
        .await;

    match resp {
        Ok(r) if r.status().is_success() => {
            info!("Clip pushed to remote");
        }
        Ok(r) => {
            warn!("Push clip failed: {}", r.status());
        }
        Err(e) => {
            warn!("Push clip error: {}", e);
        }
    }

    Ok(())
}

/// Background sync loop — periodically pulls config updates from Cloudflare
pub async fn sync_loop(proxy: EventLoopProxy<AppEvent>, cfg: Arc<Mutex<Config>>) -> Result<()> {
    loop {
        let interval = {
            let c = cfg.lock().unwrap();
            c.sync_interval_secs
        };

        tokio::time::sleep(tokio::time::Duration::from_secs(interval)).await;

        if let Err(e) = pull_config(&cfg).await {
            error!("Config sync error: {}", e);
        } else {
            let _ = proxy.send_event(AppEvent::ConfigReloaded);
        }
    }
}

/// Pull updated config (hotstrings, prompts, etc.) from Cloudflare
async fn pull_config(cfg: &Arc<Mutex<Config>>) -> Result<()> {
    let (api_url, api_token) = {
        let c = cfg.lock().unwrap();
        (c.api_url.clone(), c.api_token.clone())
    };

    if api_token.is_empty() {
        return Ok(());
    }

    let client = reqwest::Client::new();

    // Pull hotstrings
    let resp = client
        .get(format!("{}/config/hotstrings", api_url))
        .header("Authorization", format!("Bearer {}", api_token))
        .send()
        .await;

    if let Ok(r) = resp {
        if r.status().is_success() {
            if let Ok(hotstrings) = r.json::<Vec<crate::config::Hotstring>>().await {
                let mut c = cfg.lock().unwrap();
                c.hotstrings = hotstrings;
                info!("Synced {} hotstrings from remote", c.hotstrings.len());
            }
        }
    }

    // Pull clip history for slots
    let resp = client
        .get(format!("{}/clipboard/history?limit=10", api_url))
        .header("Authorization", format!("Bearer {}", api_token))
        .send()
        .await;

    if let Ok(r) = resp {
        if r.status().is_success() {
            if let Ok(clips) = r.json::<Vec<RemoteClip>>().await {
                let mut c = cfg.lock().unwrap();
                c.clip_slots = clips
                    .into_iter()
                    .map(|rc| crate::config::ClipSlot {
                        content: rc.content,
                        timestamp: rc.timestamp.unwrap_or_default(),
                    })
                    .collect();
            }
        }
    }

    // Save config locally
    {
        let c = cfg.lock().unwrap();
        if let Err(e) = c.save() {
            warn!("Failed to save config: {}", e);
        }
    }

    Ok(())
}

#[derive(serde::Deserialize)]
struct RemoteClip {
    content: String,
    timestamp: Option<String>,
}
