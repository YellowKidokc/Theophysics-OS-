"""NLP Model Bridge — connects auto_sort to the X:\05_MODELS arsenal.

Tier 2 engines:
  - DeBERTa NLI: zero-shot classification for low-confidence files
  - BART Summarizer: generate descriptive names
  - CLIP Vision: classify images by content
"""

import json
import os
from pathlib import Path
from typing import Optional

MODELS_ROOT = os.environ.get("FIS_MODELS_ROOT", r"X:\05_MODELS")
SUMMARIZER_MODEL_CANDIDATES = ("M13_bart_summarizer", "M01_summarizer")


def resolve_model_path(*parts: str) -> str:
    return os.path.join(MODELS_ROOT, *parts)


def first_existing_model(*names: str) -> str:
    for name in names:
        candidate = resolve_model_path(name)
        if os.path.exists(candidate):
            return candidate
    return resolve_model_path(names[0])

# Domain labels for zero-shot classification
DOMAIN_LABELS = [
    "theology and religion",
    "physics and mathematics",
    "software development and programming",
    "stock trading and finance",
    "business and marketing",
    "artificial intelligence and machine learning",
    "computer infrastructure and networking",
    "media production and editing",
    "personal documents and records",
    "academic research paper",
]

LABEL_TO_DOMAIN = {
    "theology and religion": "THEOPHYSICS",
    "physics and mathematics": "THEOPHYSICS",
    "software development and programming": "DEVELOPMENT",
    "stock trading and finance": "DATA_TRADING",
    "business and marketing": "BUSINESS",
    "artificial intelligence and machine learning": "AI_ML",
    "computer infrastructure and networking": "INFRASTRUCTURE",
    "media production and editing": "MEDIA",
    "personal documents and records": "PERSONAL",
    "academic research paper": "DOCUMENTS",
}

# Lazy-loaded models
_deberta_pipe = None
_summarizer_pipe = None
_clip_model = None
_clip_processor = None


def get_deberta():
    """Load DeBERTa NLI for zero-shot classification."""
    global _deberta_pipe
    if _deberta_pipe is None:
        from transformers import pipeline
        model_path = resolve_model_path("deberta_nli")
        _deberta_pipe = pipeline(
            "zero-shot-classification",
            model=model_path,
            device=-1,  # CPU
        )
        print("  [NLP] DeBERTa NLI loaded")
    return _deberta_pipe


def get_summarizer():
    """Load BART summarizer."""
    global _summarizer_pipe
    if _summarizer_pipe is None:
        from transformers import pipeline
        model_path = first_existing_model(*SUMMARIZER_MODEL_CANDIDATES)
        _summarizer_pipe = pipeline(
            "summarization",
            model=model_path,
            device=-1,
        )
        print("  [NLP] BART summarizer loaded")
    return _summarizer_pipe


def get_clip():
    """Load CLIP vision model."""
    global _clip_model, _clip_processor
    if _clip_model is None:
        from transformers import CLIPModel, CLIPProcessor
        model_path = resolve_model_path("M14_clip_vision")
        _clip_model = CLIPModel.from_pretrained(model_path)
        _clip_processor = CLIPProcessor.from_pretrained(model_path)
        print("  [NLP] CLIP vision loaded")
    return _clip_model, _clip_processor


def classify_with_deberta(text: str) -> Optional[dict]:
    """Zero-shot classify text into domain categories."""
    if not text.strip() or len(text.strip()) < 20:
        return None
    try:
        pipe = get_deberta()
        # Truncate to avoid OOM
        result = pipe(text[:1500], DOMAIN_LABELS, multi_label=False)
        top_label = result['labels'][0]
        top_score = result['scores'][0]
        domain = LABEL_TO_DOMAIN.get(top_label, 'UNCATEGORIZED')
        return {
            'domain': domain,
            'confidence': round(top_score * 100, 1),
            'label': top_label,
            'all_labels': dict(zip(result['labels'][:5], [round(s*100,1) for s in result['scores'][:5]])),
            'source': 'deberta_nli',
        }
    except Exception as e:
        print(f"  [NLP] DeBERTa error: {e}")
        return None


def summarize_with_bart(text: str, max_length: int = 30) -> Optional[str]:
    """Generate a short summary for file naming."""
    if not text.strip() or len(text.strip()) < 50:
        return None
    try:
        pipe = get_summarizer()
        result = pipe(text[:1024], max_length=max_length, min_length=5, do_sample=False)
        return result[0]['summary_text']
    except Exception as e:
        print(f"  [NLP] BART error: {e}")
        return None


def classify_image_with_clip(image_path: str) -> Optional[dict]:
    """Classify an image into domain categories using CLIP."""
    try:
        from PIL import Image
        model, processor = get_clip()
        image = Image.open(image_path).convert('RGB')
        labels = [
            "a screenshot of code or programming",
            "a chart or graph of data",
            "a diagram or architecture drawing",
            "a photograph of a person",
            "a photograph of a landscape or building",
            "a screenshot of a website",
            "a document or text page",
            "a religious or spiritual image",
            "a meme or social media post",
            "a product or retail image",
        ]
        inputs = processor(text=labels, images=image, return_tensors="pt", padding=True)
        outputs = model(**inputs)
        logits = outputs.logits_per_image[0]
        probs = logits.softmax(dim=0).detach().numpy()
        ranked = sorted(zip(labels, probs), key=lambda x: -x[1])
        return {
            'top_label': ranked[0][0],
            'confidence': round(float(ranked[0][1]) * 100, 1),
            'all_labels': {l: round(float(p)*100,1) for l, p in ranked[:5]},
            'source': 'clip_vision',
        }
    except Exception as e:
        print(f"  [NLP] CLIP error: {e}")
        return None
