"""
SASRIAKAL - Noise Preprocessing Pipeline
Implements 2D Discrete Wavelet Transform (DWT) pre-filtering to remove
WhatsApp/Telegram lossy compression artifacts before neural network inference.
Includes face detection and cropping via OpenCV Haar cascades.
"""

import cv2
import numpy as np
import pywt
from dataclasses import dataclass
from typing import Optional


@dataclass
class FaceROI:
    """Detected face region of interest."""
    x: int
    y: int
    w: int
    h: int
    confidence: float = 1.0


class NoisePreprocessor:
    """
    Preprocessing pipeline for deepfake detection:
    1. DWT-based denoising (removes compression artifacts)
    2. Face detection and cropping
    3. Tensor normalization for model input
    """

    WAVELET = "db4"  # Daubechies-4 wavelet — good balance of denoising and detail preservation
    DENOISE_THRESHOLD_FACTOR = 1.2
    FACE_CASCADE_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    MODEL_INPUT_SIZE = (256, 256)

    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(self.FACE_CASCADE_PATH)
        if self.face_cascade.empty():
            raise RuntimeError(f"Failed to load face cascade: {self.FACE_CASCADE_PATH}")

    def dwt_denoise(self, image: np.ndarray) -> np.ndarray:
        """
        Apply 2D Discrete Wavelet Transform denoising.

        Algorithm:
        1. Decompose each color channel using DWT (Daubechies-4)
        2. Apply soft thresholding to detail coefficients
        3. Reconstruct via inverse DWT
        4. Clip to valid range

        This effectively removes high-frequency noise introduced by
        lossy compression (H.264/H.265 in messaging apps).
        """
        if image.ndim == 2:
            channels = [image]
        else:
            channels = cv2.split(image)

        denoised_channels = []
        for ch in channels:
            ch_float = ch.astype(np.float64)

            # 2-level DWT decomposition
            coeffs = pywt.wavedec2(ch_float, self.WAVELET, level=2)

            # Compute noise estimate from finest-level detail coefficients
            # Use MAD (Median Absolute Deviation) for robust estimation
            detail_coeffs = coeffs[-1]  # finest level (cH, cV, cD)
            sigma = self._estimate_noise_sigma(detail_coeffs)

            # Adaptive threshold based on noise level
            threshold = sigma * self.DENOISE_THRESHOLD_FACTOR

            # Soft thresholding on all detail sub-bands (preserve approximation)
            denoised_coeffs = [coeffs[0]]  # keep approximation coefficients
            for level_coeffs in coeffs[1:]:
                denoised_level = tuple(
                    pywt.threshold(sub, threshold, mode="soft") for sub in level_coeffs
                )
                denoised_coeffs.append(denoised_level)

            # Inverse DWT reconstruction
            reconstructed = pywt.waverec2(denoised_coeffs, self.WAVELET)

            # Ensure same dimensions as original (waverec2 may add 1 pixel)
            reconstructed = reconstructed[: ch.shape[0], : ch.shape[1]]
            denoised_channels.append(np.clip(reconstructed, 0, 255).astype(np.uint8))

        if len(denoised_channels) == 1:
            return denoised_channels[0]
        return cv2.merge(denoised_channels)

    def _estimate_noise_sigma(self, detail_coeffs: tuple) -> float:
        """
        Estimate noise standard deviation using MAD estimator.
        sigma = MAD(cD) / 0.6745
        where cD is the finest-level diagonal detail coefficients.
        """
        cD = detail_coeffs[2]  # diagonal detail coefficients
        mad = np.median(np.abs(cD - np.median(cD)))
        return mad / 0.6745

    def detect_faces(self, image: np.ndarray) -> list[FaceROI]:
        """
        Detect faces using Haar cascade classifier.
        Returns list of FaceROI objects sorted by area (largest first).
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

        # Enhance contrast for better detection
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        faces = self.face_cascade.detectMultiScale(
            enhanced,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE,
        )

        rois = []
        if len(faces) > 0:
            for (x, y, w, h) in faces:
                # Add padding around detected face (20%)
                pad_w = int(w * 0.2)
                pad_h = int(h * 0.2)
                x_padded = max(0, x - pad_w)
                y_padded = max(0, y - pad_h)
                w_padded = min(image.shape[1] - x_padded, w + 2 * pad_w)
                h_padded = min(image.shape[0] - y_padded, h + 2 * pad_h)

                rois.append(FaceROI(
                    x=x_padded,
                    y=y_padded,
                    w=w_padded,
                    h=h_padded,
                    confidence=1.0,
                ))

            # Sort by area, largest first
            rois.sort(key=lambda r: r.w * r.h, reverse=True)

        return rois

    def crop_and_resize(
        self,
        image: np.ndarray,
        roi: FaceROI,
        target_size: tuple = (256, 256),
    ) -> np.ndarray:
        """Crop face ROI and resize to target dimensions."""
        face_crop = image[roi.y : roi.y + roi.h, roi.x : roi.x + roi.w]
        return cv2.resize(face_crop, target_size, interpolation=cv2.INTER_LANCZOS4)

    def denoise_frame(self, frame: np.ndarray) -> np.ndarray:
        """
        Full preprocessing pipeline for a single video frame:
        1. DWT denoising
        2. Return cleaned frame (face detection done at model level)
        """
        return self.dwt_denoise(frame)

    def prepare_tensor(self, image: np.ndarray) -> np.ndarray:
        """
        Prepare image tensor for model inference:
        - Normalize to [0, 1] float32
        - Transpose to CHW format (channels, height, width)
        - Add batch dimension
        """
        img = image.astype(np.float32) / 255.0
        if img.ndim == 2:
            img = np.stack([img, img, img], axis=0)
        elif img.ndim == 3:
            img = img.transpose(2, 0, 1)  # HWC -> CHW
        return np.expand_dims(img, axis=0)  # Add batch dim

    def preprocess_full_pipeline(
        self, frame: np.ndarray, target_size: tuple = (256, 256)
    ) -> tuple[np.ndarray, list[FaceROI]]:
        """
        Complete preprocessing: denoise → detect faces → crop → prepare tensor.
        Returns the prepared tensor and list of face ROIs.
        """
        denoised = self.dwt_denoise(frame)
        faces = self.detect_faces(denoised)

        if not faces:
            # Fallback: use full frame if no face detected
            resized = cv2.resize(denoised, target_size, interpolation=cv2.INTER_LANCZOS4)
            tensor = self.prepare_tensor(resized)
            h, w = frame.shape[:2]
            faces = [FaceROI(x=0, y=0, w=w, h=h, confidence=0.5)]

        tensors = []
        for face in faces[:3]:  # Limit to 3 faces
            cropped = self.crop_and_resize(denoised, face, target_size)
            tensors.append(self.prepare_tensor(cropped))

        return tensors, faces
