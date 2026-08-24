"""Tests for SASRIAKAL audio-visual desync engine."""

import numpy as np
import pytest


@pytest.fixture
def engine():
    from core.av_sync import AVDesyncEngine
    return AVDesyncEngine()


@pytest.fixture
def sample_frame():
    """Generate a 128x128 BGR test frame."""
    return np.random.randint(0, 256, (128, 128, 3), dtype=np.uint8)


@pytest.fixture
def sample_audio():
    """Generate 1 second of synthetic audio at 16kHz."""
    sr = 16000
    t = np.linspace(0, 1, sr, dtype=np.float32)
    # Sine wave with some harmonics
    audio = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 880 * t)
    return audio


def test_extract_visemes_returns_viseme(engine, sample_frame):
    """extract_visemes should return a VisemeFrame or None."""
    from core.av_sync import VisemeFrame
    result = engine.extract_visemes(sample_frame, timestamp_ms=0.0)
    # May return None if no face detected
    assert result is None or isinstance(result, VisemeFrame)


def test_extract_phonemes_returns_list(engine, sample_audio):
    """extract_phonemes should return a list of PhonemeFrame objects."""
    from core.av_sync import PhonemeFrame
    phonemes = engine.extract_phonemes(sample_audio, sample_rate=16000)
    assert isinstance(phonemes, list)
    assert len(phonemes) > 0
    assert all(isinstance(p, PhonemeFrame) for p in phonemes)


def test_classify_viseme(engine):
    """Viseme classification should return valid labels."""
    valid_labels = {"sil", "p", "f", "th", "t", "s", "k", "ch", "aa", "oh", "uu", "ih", "ey"}

    label = engine._classify_viseme(openness=0.01, width=0.05, compression=0.005, jaw=0.005)
    assert label in valid_labels

    label = engine._classify_viseme(openness=0.2, width=0.2, compression=0.005, jaw=0.1)
    assert label == "aa"

    label = engine._classify_viseme(openness=0.0, width=0.0, compression=0.0, jaw=0.0)
    assert label == "sil"


def test_classify_phoneme(engine):
    """Phoneme classification should return valid labels."""
    assert engine._classify_phoneme(energy=0.001, centroid=100) == "sil"
    assert engine._classify_phoneme(energy=0.1, centroid=300) == "aa"
    assert engine._classify_phoneme(energy=0.1, centroid=2000) == "s"
    assert engine._classify_phoneme(energy=0.1, centroid=6000) == "t"


def test_dtw_alignment_identical_sequences(engine):
    """DTW on identical sequences should produce zero distance."""
    from core.av_sync import PhonemeFrame, VisemeFrame

    phonemes = [
        PhonemeFrame(timestamp_ms=i * 10, phoneme="aa", energy=0.5, frequency_centroid=300)
        for i in range(5)
    ]
    visemes = [
        VisemeFrame(
            timestamp_ms=i * 10, mouth_openness=0.1, lip_width=0.1,
            lip_compression=0.0, jaw_open=0.05, viseme_label="aa"
        )
        for i in range(5)
    ]

    score, offset, alignment, flagged = engine.compute_dtw_alignment(phonemes, visemes)
    assert score == 0.0
    assert len(alignment) == 5


def test_dtw_alignment_different_sequences(engine):
    """DTW on different sequences should produce non-zero distance."""
    from core.av_sync import PhonemeFrame, VisemeFrame

    phonemes = [
        PhonemeFrame(timestamp_ms=i * 10, phoneme="s", energy=0.5, frequency_centroid=3000)
        for i in range(5)
    ]
    visemes = [
        VisemeFrame(
            timestamp_ms=i * 10, mouth_openness=0.1, lip_width=0.1,
            lip_compression=0.0, jaw_open=0.05, viseme_label="aa"
        )
        for i in range(5)
    ]

    score, offset, alignment, flagged = engine.compute_dtw_alignment(phonemes, visemes)
    assert score > 0.0


def test_dtw_empty_inputs(engine):
    """DTW should handle empty inputs gracefully."""
    score, offset, alignment, flagged = engine.compute_dtw_alignment([], [])
    assert score == 0.0
    assert offset == 0.0
    assert alignment == []
    assert flagged == []


def test_dtw_max_sequence_truncation(engine):
    """DTW should truncate very long sequences to prevent OOM."""
    from core.av_sync import PhonemeFrame, VisemeFrame

    # Create sequences longer than MAX_DTW_SEQUENCE
    long_phonemes = [
        PhonemeFrame(timestamp_ms=i, phoneme="aa", energy=0.5, frequency_centroid=300)
        for i in range(engine.MAX_DTW_SEQUENCE + 100)
    ]
    long_visemes = [
        VisemeFrame(
            timestamp_ms=i, mouth_openness=0.1, lip_width=0.1,
            lip_compression=0.0, jaw_open=0.05, viseme_label="aa"
        )
        for i in range(engine.MAX_DTW_SEQUENCE + 100)
    ]

    # Should not raise or OOM
    score, offset, alignment, flagged = engine.compute_dtw_alignment(long_phonemes, long_visemes)
    assert isinstance(score, float)


def test_analyze_av_sync_returns_dict(engine, sample_frame, sample_audio):
    """analyze_av_sync should return a properly structured dict."""
    result = engine.analyze_av_sync(sample_frame, sample_audio)

    assert isinstance(result, dict)
    assert "score" in result
    assert "offset_ms" in result
    assert "phonemes" in result
    assert "visemes" in result
    assert "flagged_segments" in result
    assert 0.0 <= result["score"] <= 1.0
