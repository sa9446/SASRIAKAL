"""Tests for SASRIAKAL noise preprocessing pipeline."""

import numpy as np
import pytest


@pytest.fixture
def sample_frame():
    """Generate a 256x256 BGR test frame with synthetic noise."""
    frame = np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)
    return frame


@pytest.fixture
def preprocessor():
    from core.preprocess import NoisePreprocessor
    return NoisePreprocessor()


def test_dwt_denoise_preserves_shape(preprocessor, sample_frame):
    """Denoised frame should have same shape as input."""
    result = preprocessor.dwt_denoise(sample_frame)
    assert result.shape == sample_frame.shape


def test_dwt_denoise_preserves_dtype(preprocessor, sample_frame):
    """Denoised frame should be uint8."""
    result = preprocessor.dwt_denoise(sample_frame)
    assert result.dtype == np.uint8


def test_dwt_denoise_reduces_noise(preprocessor):
    """Denoising should reduce variance in a noisy image."""
    # Create a smooth base with added noise
    base = np.ones((128, 128, 3), dtype=np.uint8) * 128
    noise = np.random.randint(-20, 20, (128, 128, 3), dtype=np.int16)
    noisy = np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    denoised = preprocessor.dwt_denoise(noisy)

    # Variance should decrease after denoising
    assert np.var(denoised.astype(np.float64)) <= np.var(noisy.astype(np.float64))


def test_dwt_denoise_handles_grayscale(preprocessor):
    """Should handle single-channel (grayscale) images."""
    gray = np.random.randint(0, 256, (128, 128), dtype=np.uint8)
    result = preprocessor.dwt_denoise(gray)
    assert result.ndim == 2
    assert result.shape == gray.shape


def test_detect_faces_returns_list(preprocessor, sample_frame):
    """Face detection should return a list of FaceROI objects."""
    faces = preprocessor.detect_faces(sample_frame)
    assert isinstance(faces, list)


def test_prepare_tensor_shape(preprocessor, sample_frame):
    """prepare_tensor should return (1, 3, H, W) float32 tensor."""
    tensor = preprocessor.prepare_tensor(sample_frame)
    assert tensor.ndim == 4
    assert tensor.shape[0] == 1
    assert tensor.shape[1] == 3
    assert tensor.dtype == np.float32


def test_prepare_tensor_normalized(preprocessor, sample_frame):
    """Tensor values should be in [0, 1] range."""
    tensor = preprocessor.prepare_tensor(sample_frame)
    assert tensor.min() >= 0.0
    assert tensor.max() <= 1.0


def test_estimate_noise_sigma(preprocessor):
    """MAD noise estimator should return a positive value."""
    coeffs = (
        np.random.randn(64, 64),
        np.random.randn(64, 64),
        np.random.randn(64, 64),
    )
    sigma = preprocessor._estimate_noise_sigma(coeffs)
    assert sigma >= 0.0
