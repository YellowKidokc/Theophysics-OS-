# Media Transformation Layer
*Auto-maintained. Last updated: {{timestamp}}*

## The Question

The classifier answers: **what IS this?**
The media router answers: **what should it BECOME?**

These are different questions. A Convergence article IS a paper.
But it needs to BECOME three things: HTML (web), TTS (podcast), thumbnail (social).

## Media Routes

| Route | Input | Output | When |
|-------|-------|--------|------|
| `text_to_html` | .md, .txt | HTML page | Papers, articles, notes |
| `text_to_tts` | .md, .txt, .html | Audio file (.mp3) | Articles with "podcast/audio" tag |
| `text_to_video` | .md, .txt | Video with slides | Content tagged "video/youtube" |
| `audio_to_text` | .mp3, .wav, .m4a | Transcript (.md) | Raw recordings, voice memos |
| `data_normalize` | .csv, .json, .xlsx | Cleaned data | Raw datasets |
| `generate_thumbnail` | .md, .html | Image (.png) | Anything headed for publish |

## Forking

A single file can trigger MULTIPLE routes simultaneously.
When this happens, the file is COPIED (not moved) to each media queue.
The original continues through the main text pipeline.

Example: `Convergence_P3.md` arrives
1. Classifier: paper, Laws L5/L9/L10
2. Media Router detects: text content + publish-bound
3. Forks to:
   - `D:\FAP\media\html-queue\` (for web build)
   - `D:\FAP\media\tts-queue\` (podcast episode)
   - `D:\FAP\media\thumbnails\` (social card)
4. Original continues: lossless → vectorize → grade → axiom map

## Media Queue Folders

```
D:\FAP\media\
├── html-queue\        ← files waiting for HTML build
├── tts-queue\         ← files waiting for TTS rendering
├── tts-done\          ← completed audio files
├── video-queue\       ← files waiting for video render
├── transcripts\       ← audio → text results
├── thumbnails\        ← generated social images
└── data-normalized\   ← cleaned datasets
```

## TTS Pipeline (sub-pipeline)

```
tts-queue → script prep (LLM: clean for narration)
         → TTS render (OpenAI TTS API or local)
         → audio QA (length check, silence check)
         → tts-done → R2 upload
```

## Video Pipeline (sub-pipeline)

```
video-queue → script prep (LLM: add visual cues)
           → slide generation (from content structure)
           → render (ffmpeg composite)
           → upload
```

## Transformation Detection

The media router scores each route based on:
1. **File extension** — .mp3 obviously goes to audio_to_text
2. **Doc type** from classifier — papers get text_to_html
3. **Keyword matching** — filename or content contains "podcast", "video", etc.
4. **Classification metadata** — Ollama's topic tags

Score ≥ 2 triggers the route. Multiple routes can fire simultaneously.

## Links

- [[System Overview]] — full architecture
- [[Pipeline Stations]] — station registry
- [[LLM Hub]] — AI processing hierarchy
