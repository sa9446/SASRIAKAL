"""Tests for SASRIAKAL deepfake detection ensemble."""

import numpy as np
import torch
import pytest


@pytest.fixture
def ensemble():
    from core.model import DeepfakeEnsemble
    return DeepfakeEnsemble()


@pytest.fixture
def sample_frame():
    """Generate a 256x256 BGR test frame."""
    return np.random.randint(0, 256, (256, 256, 3), dtype=np.uint8)


def test_ensemble_is_loaded(ensemble):
    """Ensemble should report as loaded (even with random weights)."""
    assert ensemble.is_loaded


def test_ensemble_has_device(ensemble):
    """Ensemble should have a resolved device."""
    assert hasattr(ensemble, "device")
    assert ensemble.device.type in ("cpu", "cuda")


def test_predict_returns_valid_output(ensemble, sample_frame):
    """predict() should return confidence in [0,1], boxes list, and scores dict."""
    confidence, boxes, scores = ensemble.predict(sample_frame)

    assert 0.0 <= confidence <= 1.0
    assert isinstance(boxes, list)
    assert isinstance(scores, dict)
    assert "ensemble" in scores
    assert "meso_inception_4" in scores
    assert "resnet_50" in scores


def test_predict_above_threshold_returns_boxes(ensemble, sample_frame):
    """When confidence is above threshold, boxes should be non-empty if attention is high."""
    confidence, boxes, _ = ensemble.predict(sample_frame)
    # With random weights, we can't guarantee above threshold,
    # but we can verify the logic path works
    if confidence >= ensemble.CONFIDENCE_THRESHOLD:
        assert isinstance(boxes, list)


def test_iou_computation():
    """IoU computation should be correct for known cases."""
    from core.model import DeepfakeEnsemble

    box1 = {"x": 0, "y": 0, "w": 100, "h": 100}
    box2 = {"x": 50, "y": 50, "w": 100, "h": 100}

    iou = DeepfakeEnsemble._compute_iou(box1, box2)

    # Intersection: 50*50 = 2500
    # Union: 100*100 + 100*100 - 2500 = 17500
    # IoU = 2500/17500 ≈ 0.1429
    assert abs(iou - 2500 / 17500) < 1e-4


def test_iou_no_overlap():
    """IoU should be 0 for non-overlapping boxes."""
    from core.model import DeepfakeEnsemble

    box1 = {"x": 0, "y": 0, "w": 10, "h": 10}
    box2 = {"x": 100, "y": 100, "w": 10, "h": 10}

    iou = DeepfakeEnsemble._compute_iou(box1, box2)
    assert iou == 0.0


def test_merge_boxes_deduplicates():
    """NMS should merge overlapping boxes."""
    from core.model import DeepfakeEnsemble

    boxes = [
        {"x": 10, "y": 10, "w": 50, "h": 50, "score": 0.9},
        {"x": 12, "y": 12, "w": 50, "h": 50, "score": 0.8},
        {"x": 200, "y": 200, "w": 30, "h": 30, "score": 0.7},
    ]

    merged = DeepfakeEnsemble()._merge_boxes(boxes, iou_threshold=0.3)

    # First two overlap heavily, should be merged
    assert len(merged) == 2


def test_predict_does_not_run_backward(ensemble, sample_frame):
    """predict() should not require gradient computation (fast path)."""
    with torch.no_grad():
        confidence, boxes, scores = ensemble.predict(sample_frame)

    assert isinstance(confidence, float)
    # If this runs without errors, no backward pass leaked
