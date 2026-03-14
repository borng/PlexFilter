# Local NSFW Detection — Model Research

*Research date: 2026-03-14*

**Status: IMPLEMENTED** — The two-stage pipeline (Freepik fast pass + NudeNet detail pass) with NudeNet-only fallback is implemented in `backend/plexfilter/services/local_detection.py`. See `backend/plexfilter/routes/sync.py` for the API endpoint and `backend/tests/test_local_detection_*.py` for tests.

PlexFilter uses VidAngel's public API as its primary data source. This document evaluates open-source models for the local fallback pipeline that provides nudity detection when titles aren't in VidAngel's catalog.

## Requirements

For PlexFilter's use case, the ideal model needs to:

1. **Process video frames** — extract frames at intervals and classify/detect nudity
2. **Produce timestamps** — map flagged frames back to start/end times for skip segments
3. **Support category granularity** — distinguish *what* is exposed (to map to PlexFilter's profile-based filtering)
4. **Run on consumer hardware** — CPU or modest GPU, not a data-center requirement

## Model Comparison

### Object Detection (locates specific body parts)

| Model | Architecture | Labels | Accuracy | Speed | GPU Required | Notes |
|-------|-------------|--------|----------|-------|-------------|-------|
| [NudeNet v3.4.2](https://pypi.org/project/nudenet/) | YOLOv8 (ONNX) | 18 body-part labels | ~90-95% | Fast on CPU | No | Best granularity for filter profiles |

**NudeNet detected labels:**
`FEMALE_GENITALIA_COVERED/EXPOSED`, `FEMALE_BREAST_COVERED/EXPOSED`, `BUTTOCKS_COVERED/EXPOSED`, `BELLY_COVERED/EXPOSED`, `FACE_FEMALE/MALE`, `MALE_BREAST_EXPOSED`, `MALE_GENITALIA_EXPOSED`, `ANUS_COVERED/EXPOSED`, `FEET_COVERED/EXPOSED`, `ARMPITS_COVERED/EXPOSED`

### Image Classification (labels whole frame as NSFW/SFW)

| Model | Architecture | Categories | Accuracy | Speed | GPU Required | Notes |
|-------|-------------|-----------|----------|-------|-------------|-------|
| [Freepik/nsfw_image_detector](https://huggingface.co/Freepik/nsfw_image_detector) | EVA ViT | 4-level (neutral/low/medium/high) | 99.5% (high), 97% (medium) | 10ms/frame GPU | Yes (BF16) | Best accuracy, best on AI-generated content |
| [Marqo/nsfw-image-detection-384](https://huggingface.co/Marqo/nsfw-image-detection-384) | ViT tiny | Binary (SFW/NSFW) | 98.56% | Fast | No | 18-20x smaller than alternatives |
| [AdamCodd/vit-base-nsfw-detector](https://huggingface.co/AdamCodd/vit-base-nsfw-detector) | ViT base | Binary (SFW/NSFW) | 96.54% | Moderate | No | 86M params, struggles with AI-generated content (drops to 86%) |
| [Falconsai/nsfw_image_detection](https://huggingface.co/Falconsai/nsfw_image_detection) | ViT | Binary (SFW/NSFW) | 98.04% | 52 img/s | No | Popular but weak on subtle/low categories (31% on "low") |

### Freepik Benchmark Detail (NVIDIA RTX 3090)

| Batch Size | Time (ms) | VRAM (MB) | Format |
|-----------|-----------|-----------|---------|
| 1 | 10 | 540 | BF16 Tensor |
| 4 | 33 | 640 | BF16 Tensor |
| 16 | 102 | 1144 | BF16 Tensor |

### Freepik vs. Competitors — Accuracy by Category

| Category | Freepik | Falconsai | AdamCodd |
|----------|---------|-----------|----------|
| High | 99.54% | 97.92% | 98.62% |
| Medium | 97.02% | 78.54% | 91.65% |
| Low | 98.31% | 31.25% | 89.66% |
| Neutral | 99.87% | 99.27% | 98.37% |

On AI-generated content, Freepik hits 100% on high/low/neutral while AdamCodd drops to 66% on neutral and Falconsai drops to 84% on high.

## Recommendation

### Best approach: Two-stage pipeline

| Stage | Model | Purpose |
|-------|-------|---------|
| **Fast pass** | Freepik classifier | Flag frames as neutral/low/medium/high (~10ms/frame on GPU) |
| **Detail pass** | NudeNet detector | On flagged frames, identify which body parts are exposed |

**Why two stages:**
- Skip ~90% of frames immediately with the fast classifier (most frames are neutral)
- NudeNet's body-part labels map directly to PlexFilter's category-based filter profiles
- Freepik's 4-level severity enables user-configurable sensitivity ("skip high only" vs. "skip everything including suggestive")

### Simpler alternative: NudeNet only

For CPU-only environments or simpler deployments, NudeNet alone is sufficient:
- Runs on CPU via ONNX (no GPU required)
- Body-part labels already provide the granularity PlexFilter needs
- `pip install nudenet` — zero config, model included in package

### Usage examples

**NudeNet:**
```python
from nudenet import NudeDetector
detector = NudeDetector()
detections = detector.detect('frame.jpg')
# Returns: [{"class": "FEMALE_BREAST_EXPOSED", "score": 0.87, "box": [x1, y1, x2, y2]}, ...]
```

**Freepik:**
```python
from nsfw_image_detector import NSFWDetector
import torch

detector = NSFWDetector(dtype=torch.bfloat16, device="cuda")
is_nsfw = detector.is_nsfw(image, "medium")  # True if medium or higher
probs = detector.predict_proba(image)         # {"neutral": 0.01, "low": 0.02, ...}
```

## Existing Video Pipeline Reference

[NSFW_Censoring](https://github.com/theusamaaslam/NSFW_Censoring) is an open-source project that already implements:
- Frame extraction from video files
- NSFW detection per frame (uses Falconsai + AdamCodd — could be swapped for better models)
- Timestamp segment generation → `nsfw_detection_report.json`
- Audio profanity detection via Whisper with word-level timestamps
- Configurable censoring (blur/pixelate/black for video, mute/beep for audio)

Its architecture is close to what PlexFilter's local detection pipeline would need. Worth studying for the frame-sampling and segment-merging logic.

## Proposed Video Processing Pipeline

```
Video file (from Plex media path)
    │
    ▼
Frame extraction (ffmpeg/OpenCV, sample every N seconds)
    │
    ▼
Stage 1: Freepik classifier (batch frames, flag non-neutral)
    │
    ▼
Stage 2: NudeNet detector (flagged frames only → body-part labels)
    │
    ▼
Map labels to PlexFilter categories (FEMALE_BREAST_EXPOSED → "Nudity:Female Nudity")
    │
    ▼
Merge adjacent flagged frames into time segments (with configurable gap tolerance)
    │
    ▼
Store as tags in PlexFilter database (same schema as VidAngel tags)
    │
    ▼
Generate custom.json via existing PlexAutoSkip generator
```

## Open Questions

- **Frame sample rate**: Every 0.5s? 1s? 2s? Trade-off between accuracy and processing time.
- **Confidence thresholds**: What NudeNet score threshold triggers a skip? (0.5? 0.7? User-configurable?)
- **GPU availability**: Should Freepik stage be optional, falling back to NudeNet-only on CPU?
- **Processing trigger**: On-demand per title? Background job for full library? Both?
- **WhisperX integration**: For profanity detection fallback — separate research needed.
