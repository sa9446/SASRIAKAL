"""
SASRIAKAL - Centralized Configuration
All environment-specific values in one place. Loaded from env vars with sane defaults.
"""

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_ROOT = Path(__file__).parent
MODELS_DIR = BACKEND_ROOT / "models"

# ── Server ─────────────────────────────────────────────────────────────────────

HOST = os.getenv("SASRIAKAL_HOST", "0.0.0.0")
PORT = int(os.getenv("SASRIAKAL_PORT", "8000"))
RELOAD = os.getenv("SASRIAKAL_RELOAD", "true").lower() == "true"
WORKERS = int(os.getenv("SASRIAKAL_WORKERS", "1"))

# ── CORS ───────────────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "SASRIAKAL_CORS_ORIGINS",
        "http://localhost:3000,http://localhost:5173,chrome-extension://*",
    ).split(",")
]

# ── Model ──────────────────────────────────────────────────────────────────────

DEVICE = os.getenv("SASRIAKAL_DEVICE", "auto")  # "auto", "cpu", "cuda"
CONFIDENCE_THRESHOLD = float(os.getenv("SASRIAKAL_THRESHOLD", "0.65"))
MESO_WEIGHT = float(os.getenv("SASRIAKAL_MESO_WEIGHT", "0.4"))
RESNET_WEIGHT = float(os.getenv("SASRIAKAL_RESNET_WEIGHT", "0.6"))
MODEL_INPUT_SIZE = (256, 256)

# ── Upload Limits ──────────────────────────────────────────────────────────────

MAX_UPLOAD_BYTES = int(os.getenv("SASRIAKAL_MAX_UPLOAD_MB", "100")) * 1024 * 1024
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".webm", ".mkv"}

# ── WebSocket ──────────────────────────────────────────────────────────────────

WS_MAX_CONNECTIONS = int(os.getenv("SASRIAKAL_MAX_WS", "50"))
WS_FRAME_RATE_LIMIT = float(os.getenv("SASRIAKAL_WS_FPS_LIMIT", "30"))

# ── DWT Denoising ──────────────────────────────────────────────────────────────

DWT_WAVELET = "db4"
DWT_THRESHOLD_FACTOR = 1.2

# ── Logging ────────────────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("SASRIAKAL_LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv(
    "SASRIAKAL_LOG_FORMAT",
    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)


def get_device():
    """Resolve torch device from config string."""
    import torch

    if DEVICE == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(DEVICE)
