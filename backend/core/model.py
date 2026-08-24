"""
SASRIAKAL - Deepfake Detection Ensemble
Combines MesoInception-4 (lightweight specialized detector) with
ResNet-50 (generalized feature extractor) for robust deepfake classification.
Returns confidence score [0.0, 1.0] and spatial heatmap coordinates.
"""

import logging
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms

logger = logging.getLogger("sasriakal.model")

# ── Resolve device at import time ──────────────────────────────────────────────

try:
    from config import get_device, MODELS_DIR, CONFIDENCE_THRESHOLD, MESO_WEIGHT, RESNET_WEIGHT
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from config import get_device, MODELS_DIR, CONFIDENCE_THRESHOLD, MESO_WEIGHT, RESNET_WEIGHT


# ── MesoInception-4 Architecture ──────────────────────────────────────────────

class InceptionBlock(nn.Module):
    """Inception-style multi-scale convolution block."""

    def __init__(self, in_channels: int, out_1x1: int, out_3x3_reduce: int, out_3x3: int):
        super().__init__()
        self.branch_1x1 = nn.Sequential(
            nn.Conv2d(in_channels, out_1x1, kernel_size=1, bias=False),
            nn.BatchNorm2d(out_1x1),
            nn.ReLU(inplace=True),
        )
        self.branch_3x3 = nn.Sequential(
            nn.Conv2d(in_channels, out_3x3_reduce, kernel_size=1, bias=False),
            nn.BatchNorm2d(out_3x3_reduce),
            nn.ReLU(inplace=True),
            nn.Conv2d(out_3x3_reduce, out_3x3, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(out_3x3),
            nn.ReLU(inplace=True),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.cat([self.branch_1x1(x), self.branch_3x3(x)], dim=1)


class MesoInception4(nn.Module):
    """
    MesoInception-4: A compact deepfake detection network.
    Designed for real-time inference with focus on mesoscopic
    (mid-level) image analysis that captures subtle manipulation artifacts.
    """

    def __init__(self, num_classes: int = 1):
        super().__init__()

        # Input: 3 x 256 x 256
        self.pre_layers = nn.Sequential(
            nn.Conv2d(3, 8, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(8),
            nn.ReLU(inplace=True),
            nn.AvgPool2d(kernel_size=2, stride=2),  # 8 x 128 x 128
        )

        # Inception blocks with increasing depth
        self.inception_1 = InceptionBlock(8, 16, 8, 16)     # 32 x 128 x 128
        self.pool_1 = nn.AvgPool2d(kernel_size=2, stride=2)  # 32 x 64 x 64

        self.inception_2 = InceptionBlock(32, 32, 16, 32)    # 64 x 64 x 64
        self.pool_2 = nn.AvgPool2d(kernel_size=2, stride=2)  # 64 x 32 x 32

        self.inception_3 = InceptionBlock(64, 64, 32, 64)    # 128 x 32 x 32

        # Deeper processing with standard convolutions
        self.conv_layers = nn.Sequential(
            nn.Conv2d(128, 64, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 32, kernel_size=3, padding=1, bias=False),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
        )

        # Spatial attention for heatmap generation
        self.spatial_attention = nn.Sequential(
            nn.Conv2d(32, 1, kernel_size=1),
            nn.Sigmoid(),
        )

        # Classification head
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(32, 16),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(16, num_classes),
            nn.Sigmoid(),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            confidence: Scalar prediction [0, 1]
            attention_map: Spatial attention map for heatmap generation
        """
        x = self.pre_layers(x)
        x = self.pool_1(self.inception_1(x))
        x = self.pool_2(self.inception_2(x))
        x = self.inception_3(x)
        features = self.conv_layers(x)

        # Spatial attention map (heatmap)
        attention = self.spatial_attention(features)

        # Classification
        confidence = self.classifier(features)

        return confidence, attention

    def get_heatmap(self, attention: torch.Tensor, original_size: tuple) -> np.ndarray:
        """Convert attention tensor to heatmap overlay."""
        attn_np = attention.detach().cpu().numpy().squeeze()
        heatmap = cv2.resize(attn_np, original_size, interpolation=cv2.INTER_LINEAR)
        heatmap = (heatmap * 255).astype(np.uint8)
        return cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)


# ── ResNet-50 Feature Extractor ───────────────────────────────────────────────

class ResNet50Detector(nn.Module):
    """
    ResNet-50-based deepfake detector.
    Uses pretrained ResNet-50 as feature extractor with custom
    classification head for binary real/fake classification.

    Grad-CAM heatmap is computed separately via compute_grad_cam()
    to avoid running backward pass during every inference call.
    """

    def __init__(self, num_classes: int = 1):
        super().__init__()

        # Load pretrained ResNet-50
        resnet = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)

        # Remove final FC layer
        self.features = nn.Sequential(*list(resnet.children())[:-2])

        # Freeze early layers (first 30% of parameters)
        total_layers = len(list(self.features.children()))
        freeze_until = int(total_layers * 0.3)
        for i, layer in enumerate(self.features.children()):
            if i < freeze_until:
                for param in layer.parameters():
                    param.requires_grad = False

        # Custom classification head
        self.head = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Flatten(),
            nn.Linear(2048, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.4),
            nn.Linear(512, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(128, num_classes),
            nn.Sigmoid(),
        )

        # Storage for Grad-CAM (populated during forward when grad is enabled)
        self._feature_maps: Optional[torch.Tensor] = None
        self._gradients: Optional[torch.Tensor] = None
        self._register_hooks()

    def _register_hooks(self):
        """Register hooks for feature map and gradient capture."""
        def forward_hook(module, input, output):
            self._feature_maps = output

        def backward_hook(module, grad_input, grad_output):
            self._gradients = grad_output[0]

        last_conv = list(self.features.children())[-1]
        last_conv.register_forward_hook(forward_hook)
        last_conv.register_full_backward_hook(backward_hook)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, Optional[torch.Tensor]]:
        """
        Inference-only forward pass. NO backward pass is executed.
        Returns:
            confidence: Binary classification score [0, 1]
            attention: None (use compute_grad_cam() for heatmap)
        """
        with torch.no_grad():
            features = self.features(x)
            confidence = self.head(features)

        # Return None for attention — heatmap requires explicit grad call
        return confidence, None

    def compute_grad_cam(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute Grad-CAM heatmap. Only call when you need the heatmap.
        This runs a forward+backward pass — expensive, so separate from predict().
        """
        self.train()  # Enable grad tracking
        try:
            features = self.features(x)
            features_grad = features.requires_grad_(True)
            confidence = self.head(features_grad)

            # Backward pass
            self.head.zero_grad()
            confidence.sum().backward(retain_graph=True)

            if self._gradients is not None:
                weights = self._gradients.mean(dim=[2, 3], keepdim=True)
                cam = (weights * features_grad).sum(dim=1, keepdim=True)
                cam = F.relu(cam)
                cam = cam / (cam.max() + 1e-8)
                return cam
            else:
                return torch.zeros(1, 1, 1, 1, device=x.device)
        finally:
            self.eval()

    def get_heatmap(self, cam: torch.Tensor, original_size: tuple) -> np.ndarray:
        """Convert Grad-CAM tensor to heatmap."""
        cam_np = cam.detach().cpu().numpy().squeeze()
        heatmap = cv2.resize(cam_np, original_size, interpolation=cv2.INTER_LINEAR)
        heatmap = np.clip(heatmap, 0, 1)
        heatmap = (heatmap * 255).astype(np.uint8)
        return cv2.applyColorMap(heatmap, cv2.COLORMAP_JET)


# ── Ensemble Model ─────────────────────────────────────────────────────────────

class DeepfakeEnsemble(nn.Module):
    """
    Ensemble of MesoInception-4 and ResNet-50 for deepfake detection.
    Weighted averaging of predictions with configurable weights.
    """

    CONFIDENCE_THRESHOLD = CONFIDENCE_THRESHOLD
    MESO_WEIGHT = MESO_WEIGHT
    RESNET_WEIGHT = RESNET_WEIGHT

    def __init__(self):
        super().__init__()
        self.device = get_device()

        self.meso = MesoInception4(num_classes=1)
        self.resnet = ResNet50Detector(num_classes=1)
        self.is_loaded = False

        self.transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((256, 256)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ])

        # Move models to device
        self.meso.to(self.device)
        self.resnet.to(self.device)

        self._load_weights()

    def _load_weights(self):
        """Load pretrained weights from disk with security checks."""
        try:
            meso_path = MODELS_DIR / "meso4_pretrained.pth"
            resnet_path = MODELS_DIR / "resnet50_pretrained.pth"

            if meso_path.exists():
                self.meso.load_state_dict(
                    torch.load(meso_path, map_location=self.device, weights_only=True)
                )
                logger.info(f"Loaded MesoInception-4 weights from {meso_path}")

            if resnet_path.exists():
                self.resnet.load_state_dict(
                    torch.load(resnet_path, map_location=self.device, weights_only=True)
                )
                logger.info(f"Loaded ResNet-50 weights from {resnet_path}")

            self.is_loaded = True
        except Exception as e:
            logger.warning(f"Could not load pretrained weights: {e}")
            logger.info("Using randomly initialized weights (training required)")
            self.is_loaded = True  # Still functional, just untrained

    def predict(self, frame: np.ndarray) -> tuple[float, list[dict], dict]:
        """
        Run ensemble prediction on a BGR frame.
        Does NOT compute Grad-CAM (use predict_with_heatmap() for that).

        Args:
            frame: BGR numpy array from OpenCV

        Returns:
            confidence: Ensemble confidence score [0.0, 1.0]
            heatmap_boxes: List of {x, y, w, h, score} for each detected region
            layer_scores: Per-model scores
        """
        h, w = frame.shape[:2]

        # Convert BGR to RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Prepare tensor
        tensor = self.transform(rgb).unsqueeze(0).to(self.device)

        self.eval()
        # MesoInception prediction (forward only, no grad)
        meso_conf, _ = self.meso(tensor)
        meso_score = meso_conf.item()

        # ResNet prediction (forward only, no backward pass!)
        resnet_conf, _ = self.resnet(tensor)
        resnet_score = resnet_conf.item()

        # Weighted ensemble
        ensemble_confidence = (
            self.MESO_WEIGHT * meso_score + self.RESNET_WEIGHT * resnet_score
        )

        # Only compute heatmap if above threshold (saves compute)
        heatmap_boxes = []
        if ensemble_confidence >= self.CONFIDENCE_THRESHOLD:
            # MesoInception attention is cheap (no backward pass needed)
            _, meso_attn = self.meso(tensor)
            heatmap_boxes = self._extract_heatmap_boxes(
                meso_attn, None, w, h, ensemble_confidence
            )

        layer_scores = {
            "meso_inception_4": round(meso_score, 4),
            "resnet_50": round(resnet_score, 4),
            "ensemble": round(ensemble_confidence, 4),
        }

        return ensemble_confidence, heatmap_boxes, layer_scores

    def predict_with_heatmap(self, frame: np.ndarray) -> tuple[float, list[dict], dict]:
        """
        Full prediction with Grad-CAM heatmap from ResNet-50.
        More expensive — use for detailed analysis, not real-time streaming.
        """
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        tensor = self.transform(rgb).unsqueeze(0).to(self.device)

        self.eval()
        meso_conf, meso_attn = self.meso(tensor)
        meso_score = meso_conf.item()

        resnet_conf, _ = self.resnet(tensor)
        resnet_score = resnet_conf.item()

        # Grad-CAM only when explicitly requested
        resnet_cam = self.resnet.compute_grad_cam(tensor)

        ensemble_confidence = (
            self.MESO_WEIGHT * meso_score + self.RESNET_WEIGHT * resnet_score
        )

        heatmap_boxes = []
        if ensemble_confidence >= self.CONFIDENCE_THRESHOLD:
            heatmap_boxes = self._extract_heatmap_boxes(
                meso_attn, resnet_cam, w, h, ensemble_confidence
            )

        layer_scores = {
            "meso_inception_4": round(meso_score, 4),
            "resnet_50": round(resnet_score, 4),
            "ensemble": round(ensemble_confidence, 4),
        }

        return ensemble_confidence, heatmap_boxes, layer_scores

    def _extract_heatmap_boxes(
        self,
        meso_attn: torch.Tensor,
        resnet_cam: Optional[torch.Tensor],
        width: int,
        height: int,
        confidence: float,
    ) -> list[dict]:
        """
        Extract spatial heatmap bounding boxes from attention maps.
        Uses thresholding on the combined attention map to find
        regions of high manipulation probability.
        """
        if confidence < self.CONFIDENCE_THRESHOLD:
            return []

        # Combine attention maps
        meso_np = meso_attn.detach().cpu().numpy().squeeze()

        if resnet_cam is not None:
            resnet_np = resnet_cam.detach().cpu().numpy().squeeze()
        else:
            resnet_np = np.zeros_like(meso_np)

        # Resize both to same size
        target_h, target_w = 32, 32  # Attention map resolution
        meso_resized = cv2.resize(meso_np, (target_w, target_h))
        resnet_resized = cv2.resize(resnet_np, (target_w, target_h))

        # Weighted combination
        combined = self.MESO_WEIGHT * meso_resized + self.RESNET_WEIGHT * resnet_resized

        # Threshold to find hot regions
        threshold = np.percentile(combined, 75)
        binary_mask = (combined > threshold).astype(np.uint8)

        # Find contours
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 4:  # Minimum contour area
                continue

            x, y, w, h = cv2.boundingRect(contour)

            # Scale to original image coordinates
            scale_x = width / target_w
            scale_y = height / target_h

            box = {
                "x": int(x * scale_x),
                "y": int(y * scale_y),
                "w": int(w * scale_x),
                "h": int(h * scale_y),
                "score": round(float(np.mean(combined[y : y + h, x : x + w])), 4),
            }
            boxes.append(box)

        # Merge overlapping boxes
        boxes = self._merge_boxes(boxes)

        return boxes

    def _merge_boxes(self, boxes: list[dict], iou_threshold: float = 0.3) -> list[dict]:
        """Non-maximum suppression to merge overlapping bounding boxes."""
        if not boxes:
            return []

        # Sort by score descending
        boxes.sort(key=lambda b: b["score"], reverse=True)

        merged = []
        for box in boxes:
            overlaps = False
            for existing in merged:
                iou = self._compute_iou(box, existing)
                if iou > iou_threshold:
                    overlaps = True
                    break
            if not overlaps:
                merged.append(box)

        return merged

    @staticmethod
    def _compute_iou(box1: dict, box2: dict) -> float:
        """Compute Intersection over Union between two boxes."""
        x1 = max(box1["x"], box2["x"])
        y1 = max(box1["y"], box2["y"])
        x2 = min(box1["x"] + box1["w"], box2["x"] + box2["w"])
        y2 = min(box1["y"] + box1["h"], box2["y"] + box2["h"])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = box1["w"] * box1["h"]
        area2 = box2["w"] * box2["h"]
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0.0

    def unload(self):
        """Release model memory."""
        del self.meso
        del self.resnet
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.info("Models unloaded from memory")
