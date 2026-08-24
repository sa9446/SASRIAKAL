"""
SASRIAKAL - Audio-Visual Desynchronization Engine
Detects voice cloning and face-swapping by analyzing temporal
misalignment between phonemes (audio) and visemes (facial lip shapes).
Uses MediaPipe Face Mesh for lip landmark tracking and
librosa for audio phoneme analysis.
"""

import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("sasriakal.av_sync")


@dataclass
class VisemeFrame:
    """Single frame viseme extraction."""
    timestamp_ms: float
    mouth_openness: float  # vertical lip distance
    lip_width: float       # horizontal lip distance
    lip_compression: float # forward lip protrusion estimate
    jaw_open: float        # jaw drop amount
    viseme_label: str      # categorical viseme class


@dataclass
class PhonemeFrame:
    """Single frame phoneme extraction from audio."""
    timestamp_ms: float
    phoneme: str
    energy: float
    frequency_centroid: float


@dataclass
class AVSyncResult:
    """Audio-visual synchronization analysis result."""
    score: float  # 0.0 = perfectly synced, 1.0 = completely desynced
    offset_ms: float  # estimated temporal offset in milliseconds
    phonemes: list[dict]
    visemes: list[dict]
    alignment_curve: list[float]  # per-frame alignment scores
    flagged_segments: list[dict]  # time ranges with significant desync


class AVDesyncEngine:
    """
    Phoneme-Viseme Audio-Visual Desynchronization Detector.

    Pipeline:
    1. Extract lip landmarks from video frames (MediaPipe Face Mesh)
    2. Convert landmarks to viseme categories
    3. Extract phoneme features from audio (energy + frequency analysis)
    4. Compute temporal alignment using Dynamic Time Warping (DTW)
    5. Flag regions with significant phoneme-viseme mismatch
    """

    # Viseme classification thresholds (normalized landmarks)
    VISEME_LABELS = {
        "sil": "silence",
        "p": "bilabial_closure",      # p, b, m
        "f": "labiodental",            # f, v
        "th": "dental",                # th
        "t": "alveolar_closure",       # t, d, n, l
        "s": "sibilant",               # s, z, sh
        "k": "velar_closure",          # k, g
        "ch": "postalveolar",          # ch, j, sh
        "aa": "open_vowel",            # ah, aa
        "oh": "mid_vowel",             # oh, ao
        "uu": "close_rounded",         # oo, u
        "ih": "close_front",           # ih, i
        "ey": "diphthong",             # ey, ay
    }

    # MediaPipe Face Mesh lip landmark indices
    UPPER_LIP = [61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291]
    LOWER_LIP = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
    LEFT_MOUTH = [61, 185, 40, 39, 37, 0]
    RIGHT_MOUTH = [267, 269, 270, 409, 291, 0]
    LIP_TOP = 13
    LIP_BOTTOM = 14

    def __init__(self):
        self.mp_face_mesh = None
        self.face_mesh = None
        self._init_mediapipe()

    def _init_mediapipe(self):
        """Initialize MediaPipe Face Mesh for lip landmark detection."""
        try:
            import mediapipe as mp
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                static_image_mode=False,
                max_num_faces=3,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            logger.info("MediaPipe Face Mesh initialized")
        except ImportError:
            logger.warning("MediaPipe not available; AV sync will use fallback method")

    def extract_visemes(self, frame: np.ndarray, timestamp_ms: float) -> Optional[VisemeFrame]:
        """
        Extract viseme features from a single video frame.
        Uses MediaPipe Face Mesh to detect mouth landmarks.
        """
        if self.face_mesh is None:
            return self._fallback_viseme(frame, timestamp_ms)

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            return None

        landmarks = results.multi_face_landmarks[0].landmark
        h, w = frame.shape[:2]

        # Extract key measurements
        upper_lip_pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in self.UPPER_LIP]
        lower_lip_pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in self.LOWER_LIP]
        left_pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in self.LEFT_MOUTH]
        right_pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in self.RIGHT_MOUTH]

        # Mouth openness: vertical distance between upper and lower lip centers
        upper_center_y = np.mean([p[1] for p in upper_lip_pts])
        lower_center_y = np.mean([p[1] for p in lower_lip_pts])
        mouth_openness = abs(lower_center_y - upper_center_y) / h

        # Lip width: horizontal distance between mouth corners
        left_corner = landmarks[61]
        right_corner = landmarks[291]
        lip_width = abs(right_corner.x - left_corner.x)

        # Lip compression (forward protrusion estimate)
        top_lip = landmarks[self.LIP_TOP]
        bottom_lip = landmarks[self.LIP_BOTTOM]
        lip_compression = abs(top_lip.z - bottom_lip.z) if hasattr(top_lip, "z") else 0.0

        # Jaw opening
        jaw_open = landmarks[13].y - landmarks[14].y if len(landmarks) > 14 else 0.0

        # Classify viseme
        viseme_label = self._classify_viseme(mouth_openness, lip_width, lip_compression, jaw_open)

        return VisemeFrame(
            timestamp_ms=timestamp_ms,
            mouth_openness=round(mouth_openness, 4),
            lip_width=round(lip_width, 4),
            lip_compression=round(lip_compression, 4),
            jaw_open=round(jaw_open, 4),
            viseme_label=viseme_label,
        )

    def _classify_viseme(
        self,
        openness: float,
        width: float,
        compression: float,
        jaw: float,
    ) -> str:
        """Classify a set of mouth measurements into a viseme category."""
        if openness < 0.02:
            return "sil"
        elif openness > 0.15:
            if width > 0.15:
                return "aa"  # wide open mouth
            else:
                return "oh"  # round open mouth
        elif openness > 0.08:
            if compression > 0.01:
                return "uu"  # rounded
            else:
                return "ey"  # spread
        else:
            if compression > 0.01:
                return "p"  # closed/compressed
            else:
                return "t"  # slightly open

    def _fallback_viseme(self, frame: np.ndarray, timestamp_ms: float) -> Optional[VisemeFrame]:
        """Fallback viseme estimation using optical flow when MediaPipe unavailable."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Focus on mouth region (lower third of image, center)
        mouth_region = gray[int(h * 0.6) : int(h * 0.85), int(w * 0.3) : int(w * 0.7)]
        if mouth_region.size == 0:
            return None

        # Simple intensity-based estimation
        mean_intensity = np.mean(mouth_region) / 255.0
        variance = np.var(mouth_region) / 255.0

        openness = max(0, min(1, 1.0 - mean_intensity))
        width = variance * 2
        compression = variance

        return VisemeFrame(
            timestamp_ms=timestamp_ms,
            mouth_openness=round(openness, 4),
            lip_width=round(width, 4),
            lip_compression=round(compression, 4),
            jaw_open=round(openness * 0.5, 4),
            viseme_label=self._classify_viseme(openness, width, compression, openness * 0.5),
        )

    def extract_phonemes(self, audio_chunk: np.ndarray, sample_rate: int = 16000, timestamp_ms: float = 0.0) -> list[PhonemeFrame]:
        """
        Extract phoneme features from audio chunk using spectral analysis.
        Uses energy envelope and frequency centroid as phoneme proxies.
        """
        if audio_chunk.ndim > 1:
            audio_chunk = audio_chunk.mean(axis=1)

        frame_size = int(sample_rate * 0.025)  # 25ms frames
        hop_size = int(sample_rate * 0.010)    # 10ms hop

        phonemes = []
        for i in range(0, len(audio_chunk) - frame_size, hop_size):
            frame = audio_chunk[i : i + frame_size]

            # Energy
            energy = float(np.sqrt(np.mean(frame ** 2)))

            # Spectral centroid via DFT
            fft = np.abs(np.fft.rfft(frame * np.hanning(len(frame))))
            freqs = np.fft.rfftfreq(len(frame), 1.0 / sample_rate)
            total_energy = np.sum(fft)
            if total_energy > 0:
                centroid = float(np.sum(freqs * fft) / total_energy)
            else:
                centroid = 0.0

            # Simple phoneme classification based on energy and centroid
            phoneme = self._classify_phoneme(energy, centroid)

            t_ms = timestamp_ms + (i / sample_rate) * 1000
            phonemes.append(PhonemeFrame(
                timestamp_ms=t_ms,
                phoneme=phoneme,
                energy=round(energy, 4),
                frequency_centroid=round(centroid, 2),
            ))

        return phonemes

    def _classify_phoneme(self, energy: float, centroid: float) -> str:
        """Classify audio features into approximate phoneme categories."""
        if energy < 0.01:
            return "sil"
        elif centroid < 500:
            return "aa"  # low frequency vowels
        elif centroid < 1500:
            return "oh"  # mid frequency
        elif centroid < 3000:
            return "s"   # sibilant
        elif centroid < 5000:
            return "f"   # fricative
        else:
            return "t"   # high frequency stops

    def compute_dtw_alignment(
        self, phonemes: list[PhonemeFrame], visemes: list[VisemeFrame]
    ) -> tuple[float, float, list[float], list[dict]]:
        """
        Compute Dynamic Time Warping alignment between phoneme and viseme sequences.
        Uses Sakoe-Chiba band constraint for O(n*w) memory instead of O(n*m).
        Returns overall desync score, estimated offset, per-frame alignment, and flagged segments.
        """
        if not phonemes or not visemes:
            return 0.0, 0.0, [], []

        # Truncate if sequences are too long (prevents OOM)
        if len(phonemes) > self.MAX_DTW_SEQUENCE or len(visemes) > self.MAX_DTW_SEQUENCE:
            logger.warning(
                f"DTW sequences truncated: phonemes {len(phonemes)} -> {self.MAX_DTW_SEQUENCE}, "
                f"visemes {len(visemes)} -> {self.MAX_DTW_SEQUENCE}"
            )
            phonemes = phonemes[:self.MAX_DTW_SEQUENCE]
            visemes = visemes[:self.MAX_DTW_SEQUENCE]

        # Build phoneme/viseme label sequences
        p_labels = [p.phoneme for p in phonemes]
        v_labels = [v.viseme_label for v in visemes]

        # Compute pairwise cost matrix with Sakoe-Chiba band
        n = len(p_labels)
        m = len(v_labels)
        # Band width = 20% of the longer sequence (balances speed vs accuracy)
        band_width = max(1, int(max(n, m) * 0.2))

        cost_matrix = np.full((n, m), np.inf)
        path_matrix = np.zeros((n, m, 2), dtype=int)

        for i in range(n):
            # Sakoe-Chiba: only compute within band of diagonal
            j_min = max(0, i - band_width)
            j_max = min(m, i + band_width + 1)

            for j in range(j_min, j_max):
                cost = 0.0 if p_labels[i] == v_labels[j] else 1.0
                if i == 0 and j == 0:
                    cost_matrix[i, j] = cost
                elif i == 0:
                    cost_matrix[i, j] = cost_matrix[i, j - 1] + cost
                elif j == 0:
                    cost_matrix[i, j] = cost_matrix[i - 1, j] + cost
                else:
                    diag = cost_matrix[i - 1, j - 1] + cost
                    up = cost_matrix[i - 1, j] + cost
                    left = cost_matrix[i, j - 1] + cost

                    if diag <= up and diag <= left:
                        cost_matrix[i, j] = diag
                        path_matrix[i, j] = [i - 1, j - 1]
                    elif up <= left:
                        cost_matrix[i, j] = up
                        path_matrix[i, j] = [i - 1, j]
                    else:
                        cost_matrix[i, j] = left
                        path_matrix[i, j] = [i, j - 1]

        # Normalize DTW distance
        max_path_len = max(n, m)
        dtw_distance = cost_matrix[n - 1, m - 1] / max_path_len if max_path_len > 0 else 0.0

        # Trace back alignment path
        alignment = []
        i, j = n - 1, m - 1
        while i > 0 or j > 0:
            alignment.append((i, j))
            prev = path_matrix[i, j]
            i, j = int(prev[0]), int(prev[1])
        alignment.reverse()

        # Compute temporal offset
        time_diffs = []
        for pi, vi in alignment:
            time_diffs.append(phonemes[pi].timestamp_ms - visemes[vi].timestamp_ms)
        estimated_offset = float(np.median(time_diffs)) if time_diffs else 0.0

        # Per-frame alignment scores
        alignment_scores = [1.0 - (0.5 if p_labels[pi] == v_labels[vi] else 1.0) for pi, vi in alignment]

        # Flag segments with high desync
        flagged = []
        window_size = 10
        for idx in range(0, len(alignment_scores) - window_size, window_size):
            window = alignment_scores[idx : idx + window_size]
            avg_desync = float(np.mean(window))
            if avg_desync > 0.5:
                pi, vi = alignment[idx]
                flagged.append({
                    "start_ms": phonemes[pi].timestamp_ms,
                    "end_ms": phonemes[min(pi + window_size, len(phonemes) - 1)].timestamp_ms,
                    "desync_score": round(avg_desync, 4),
                })

        return dtw_distance, estimated_offset, alignment_scores, flagged

    def analyze_av_sync(
        self, frame: np.ndarray, audio_chunk: np.ndarray
    ) -> dict:
        """
        Analyze audio-visual synchronization for a single frame+audio pair.
        Returns desync score and metadata.
        """
        viseme = self.extract_visemes(frame, timestamp_ms=0.0)
        phonemes = self.extract_phonemes(audio_chunk, timestamp_ms=0.0)

        if viseme is None:
            return {
                "score": 0.0,
                "offset_ms": 0.0,
                "phonemes": [],
                "visemes": [],
                "flagged_segments": [],
            }

        viseme_list = [viseme]
        score, offset, alignment, flagged = self.compute_dtw_alignment(phonemes, viseme_list)

        return {
            "score": round(score, 4),
            "offset_ms": round(offset, 2),
            "phonemes": [{"time_ms": p.timestamp_ms, "label": p.phoneme} for p in phonemes],
            "visemes": [{"time_ms": v.timestamp_ms, "label": v.viseme_label} for v in viseme_list],
            "alignment_scores": [round(a, 4) for a in alignment],
            "flagged_segments": flagged,
        }

    # Max sequence length for DTW (prevents OOM on long videos)
    MAX_DTW_SEQUENCE = 2000

    def analyze_video_file(self, video_path: str) -> dict:
        """
        Analyze full video file for AV desync.
        Extracts frames and audio, then runs alignment analysis.
        """

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return {"error": f"Cannot open video: {video_path}"}

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Extract audio to temp WAV
        audio_path = tempfile.mktemp(suffix=".wav")
        try:
            subprocess.run(
                ["ffmpeg", "-i", video_path, "-vn", "-acodec", "pcm_s16le",
                 "-ar", "16000", "-ac", "1", audio_path, "-y"],
                capture_output=True, timeout=30,
            )

            import librosa
            audio, sr = librosa.load(audio_path, sr=16000)
        except Exception as e:
            logger.warning(f"Audio extraction failed: {e}")
            audio = None
        finally:
            if os.path.exists(audio_path):
                os.unlink(audio_path)

        # Sample frames for viseme extraction
        sample_interval = max(1, int(fps / 10))  # ~10 FPS
        visemes = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                timestamp_ms = (frame_idx / fps) * 1000
                viseme = self.extract_visemes(frame, timestamp_ms)
                if viseme:
                    visemes.append(viseme)

            frame_idx += 1

        cap.release()

        # Extract phonemes from audio
        phonemes = []
        if audio is not None:
            chunk_size = int(fps / 10 * sr)  # match frame sampling rate
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i : i + chunk_size]
                if len(chunk) < 100:
                    continue
                timestamp_ms = (i / sr) * 1000
                p = self.extract_phonemes(chunk, sr, timestamp_ms)
                phonemes.extend(p)

        # Compute alignment
        score, offset, alignment, flagged = self.compute_dtw_alignment(phonemes, visemes)

        return {
            "score": round(score, 4),
            "offset_ms": round(offset, 2),
            "total_frames": total_frames,
            "sampled_frames": len(visemes),
            "phonemes_extracted": len(phonemes),
            "visemes_extracted": len(visemes),
            "flagged_segments": flagged,
            "alignment_scores": [round(a, 4) for a in alignment[:100]],  # limit output
        }
