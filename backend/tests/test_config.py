"""Tests for SASRIAKAL configuration module."""

import os
import pytest


def test_config_loads_defaults():
    """Config should load with sensible defaults when no env vars are set."""
    # Clear any existing env overrides
    for key in ["SASRIAKAL_PORT", "SASRIAKAL_HOST", "SASRIAKAL_THRESHOLD"]:
        os.environ.pop(key, None)

    from config import PORT, HOST, CONFIDENCE_THRESHOLD, MAX_UPLOAD_BYTES

    assert PORT == 8000
    assert HOST == "0.0.0.0"
    assert CONFIDENCE_THRESHOLD == 0.65
    assert MAX_UPLOAD_BYTES > 0


def test_config_respects_env(monkeypatch):
    """Config should read from environment variables."""
    monkeypatch.setenv("SASRIAKAL_PORT", "9000")
    monkeypatch.setenv("SASRIAKAL_THRESHOLD", "0.8")

    import importlib
    import config
    importlib.reload(config)

    assert config.PORT == 9000
    assert config.CONFIDENCE_THRESHOLD == 0.8


def test_get_device_returns_torch_device():
    """get_device() should return a valid torch device."""
    import torch
    from config import get_device

    device = get_device()
    assert isinstance(device, torch.device)
    assert device.type in ("cpu", "cuda")


def test_allowed_extensions():
    """Should have sensible file extension sets."""
    from config import ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT

    assert ".jpg" in ALLOWED_IMAGE_EXT
    assert ".png" in ALLOWED_IMAGE_EXT
    assert ".mp4" in ALLOWED_VIDEO_EXT
    assert ".webm" in ALLOWED_VIDEO_EXT
