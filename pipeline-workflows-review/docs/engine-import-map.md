# Engine Import Map

Opus identified the missing production engine layer from `D:\BIL`.

Imported into this repo:

| Source | Repo path | Notes |
| --- | --- | --- |
| `D:\BIL\engines\pipeline\station_base.py` | `engines/pipeline/station_base.py` | Station base classes, manifest, verdicts, signals |
| `D:\BIL\engines\pipeline\pipeline_engine.py` | `engines/pipeline/pipeline_engine.py` | Watchers, registry, routing, Postgres/local logging |
| `D:\BIL\engines\pipeline\llm_hub.py` | `engines/pipeline/llm_hub.py` | LLM queue/checkpoint hub |
| `D:\BIL\engines\pipeline\fap_boot.py` | `engines/pipeline/fap_boot.py` | Bootstrap for the current FAP folder tree |
| `D:\BIL\engines\pipeline\fap_schema.sql` | `engines/pipeline/fap_schema.sql` | Postgres schema |
| `D:\BIL\engines\pipeline\fap_healthcheck.py` | `engines/pipeline/fap_healthcheck.py` | Engine healthcheck |
| `D:\BIL\engines\pipeline\fap_postgres_sync.py` | `engines/pipeline/fap_postgres_sync.py` | JSONL-to-Postgres sync lane |
| `D:\BIL\engines\pipeline\fap_dashboard.html` | `engines/pipeline/fap_dashboard.html` | Local dashboard surface |
| `D:\BIL\engines\pipeline\stations\classifier.py` | `engines/pipeline/stations/classifier.py` | Working Station 1 |
| `D:\BIL\engines\pipeline\stations\media_transformer.py` | `engines/pipeline/stations/media_transformer.py` | Working Station 2 |
| `D:\BIL\engines\threshold_engine.py` | `engines/threshold_engine.py` | Adaptive confidence scoring |
| `D:\BIL\engines\embeddings\text_embedder.py` | `engines/embeddings/text_embedder.py` | Infinity embedding helper |
| `D:\BIL\engines\truth\truth_engine.py` | `engines/truth/truth_engine.py` | Truth/consistency helper |

Intentionally excluded:

- `D:\BIL\engines\pipeline\stations\media_router.py`: dead code, superseded by `media_transformer.py`
- all `__pycache__` files
- model weights, embeddings payloads, runtime databases, logs, and secrets

Imported prompt/spec material:

| Source | Repo path |
| --- | --- |
| `D:\FAP\wiki\prompts\classify_document.md` | `prompts/fap/classify_document.md` |
| `D:\FAP\wiki\prompts\grade_paper.md` | `prompts/fap/grade_paper.md` |
| `D:\FAP\wiki\prompts\vault_page_compiler.md` | `prompts/fap/vault_page_compiler.md` |
| `D:\FAP\wiki\system\PAGE_ARCHITECTURE.md` | `docs/imported/PAGE_ARCHITECTURE.md` |
| `D:\FAP\wiki\system\PAPER_RUBRIC_REF.md` | `docs/imported/PAPER_RUBRIC_REF.md` |
| `D:\FAP\wiki\system\LLM_Hub.md` | `docs/imported/LLM_Hub.md` |
| `D:\FAP\wiki\system\Media_Transform.md` | `docs/imported/Media_Transform.md` |
| `D:\FAP\wiki\system\00_OVERVIEW.md` | `docs/imported/FAP_OVERVIEW.md` |

Runtime values such as Postgres DSN and log locations can be overridden with:

- `FAP_PG_DSN`
- `FAP_LOG_DIR`
- `FAP_ENGINE_LOG_DIR`
- `FAP_SYNC_REPORT_DIR`
- `FAP_HEALTH_REPORT_DIR`
- `FAP_REPO_ROOT`
