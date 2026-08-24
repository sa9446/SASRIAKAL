# SASRIAKAL — Real-Time Deepfake Detection Platform

A production-ready, real-time deepfake detection platform featuring local browser inference (ONNX WebAssembly), high-throughput FastAPI streaming fallback, custom heatmap overlays, and a court-ready evidence reporting engine.

---

## Architecture Overview

```
sasriakal-ai/
├── extension/                   # Manifest V3 Chrome Extension
│   ├── manifest.json
│   ├── background.js           # Offscreen Canvas Worker & WebSocket Manager
│   ├── content.js              # DOM Interception & Canvas Overlay Injector
│   ├── overlay.js              # Real-time Gradient Heatmap Renderer
│   └── popup/                  # Extension UI Dashboard
├── backend/                     # FastAPI & Python Engine
│   ├── main.py                 # FastAPI Application & WebSocket Routes
│   ├── core/
│   │   ├── preprocess.py       # DWT Denoising & Face Cropping
│   │   ├── model.py            # PyTorch MesoInception-4 & ResNet-50 Ensemble
│   │   ├── av_sync.py          # Phoneme-Viseme AV Desync Engine
│   │   └── c2pa_parser.py      # C2PA Metadata & Signature Inspector
│   ├── utils/
│   │   └── pdf_generator.py    # Legal Evidence PDF Builder (ReportLab)
│   └── models/                 # ONNX Export Script
├── web-dashboard/               # React + Tailwind Frontend
│   ├── src/
│   │   ├── components/         # Live Video, Heatmap, Metrics, Panels
│   │   └── App.jsx
│   └── package.json
└── README.md
```

---

## Quick Start

### 1. Backend (FastAPI)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Start the server
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

**Key Endpoints:**
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/stream` | WebSocket | Real-time frame streaming |
| `/api/detect` | POST | Single frame detection |
| `/api/detect/upload` | POST | File upload (image/video) |
| `/api/av-desync` | POST | AV sync analysis |
| `/api/validate-c2pa` | POST | C2PA provenance check |
| `/api/generate-report` | POST | Generate evidence PDF |
| `/api/health` | GET | System health check |

### 2. Web Dashboard (React)

```bash
cd web-dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

The dashboard will be available at `http://localhost:5173`

### 3. Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `extension/` directory
5. The SASRIAKAL icon will appear in your toolbar

---

## Features

### Real-Time Detection Pipeline

```
Video Frame → DWT Denoising → MesoInception-4 ─┐
                                                ├── Ensemble → Confidence + Heatmap
                → ResNet-50 Feature Extractor ──┘
```

- **Glass-to-glass latency** target: < 100ms
- **DWT preprocessing** removes WhatsApp/Telegram compression artifacts
- **Dual-model ensemble** combines mesoscopic analysis (MesoInception-4) with semantic features (ResNet-50)
- **Spatial heatmap** highlights manipulated facial regions with glowing red/amber overlays

### Audio-Visual Desync Detection

```
Video Frames → MediaPipe Face Mesh → Viseme Extraction ──┐
                                                         ├── DTW Alignment → Desync Score
Audio Stream → Spectral Analysis → Phoneme Extraction ──┘
```

- Detects **voice cloning** and **face swapping** via temporal misalignment
- Uses **Dynamic Time Warping (DTW)** for phoneme-viseme alignment
- Flags specific time ranges with significant desynchronization

### C2PA Provenance Validation

- Parses JUMBF containers in JPEG/PNG
- Validates ISO Base Media File Format (MP4) UUID boxes
- Checks cryptographic signatures and hash integrity
- Detects tampering indicators in metadata

### Evidence PDF Generation

Generates court-ready forensic reports with:
- **Executive Summary** with detection verdict
- **Detection Results** table with per-frame confidence scores
- **AV Desync Analysis** with flagged segments
- **Chain of Custody** metadata
- **Cryptographic Integrity** verification
- **Legal Disclaimer** for admissibility

### Chrome Extension

- **DOM Video Hooking**: Automatically detects `<video>` elements on YouTube, social media, etc.
- **Offscreen Processing**: Runs inference without blocking the main thread
- **Local ONNX WASM**: Zero-latency in-browser inference for supported models
- **Canvas Overlay**: Injects transparent heatmap over detected manipulation

---

## Model Export (ONNX)

Export MesoInception-4 for browser inference:

```bash
cd backend
python -m models.export_onnx --output ../extension/models/ --quantize fp16 --benchmark --js-wrapper
```

Options:
- `--quantize`: `fp16` (default), `int8`, or `none`
- `--benchmark`: Run inference speed test
- `--js-wrapper`: Generate JavaScript wrapper for browser use

---

## Configuration

### Confidence Threshold

Default threshold: **0.65** (65%)

Adjust via the dashboard controls or the Chrome Extension popup. When confidence exceeds the threshold:
- Heatmap overlay is displayed with glowing red/amber gradients
- Frame is flagged in the detection log
- Alert badge appears on the video overlay

### Inference Modes

| Mode | Description |
|------|-------------|
| **Local WASM** | Browser-only ONNX inference via WebAssembly |
| **Backend WS** | WebSocket streaming to FastAPI backend |
| **Ensemble** | Combined local + backend predictions |

---

## API Reference

### POST `/api/detect`

```json
{
  "frame": "<base64-encoded-image>",
  "tab_id": "optional-tab-id",
  "source": "extension"
}
```

**Response:**
```json
{
  "confidence": 0.8234,
  "heatmap": [{"x": 120, "y": 45, "w": 80, "h": 90, "score": 0.8234}],
  "av_desync": {"score": 0.15},
  "frame_hash": "a1b2c3d4e5f67890",
  "processing_time_ms": 42.5,
  "model_version": "v1.0.0"
}
```

### WebSocket `/ws/stream`

Send JSON frames:
```json
{
  "frame": "<base64>",
  "tab_id": "tab-123",
  "timestamp": 1700000000000,
  "audio": "<base64-optional>"
}
```

Receive detection results in the same format as `/api/detect`.

---

## Technical Details

### MesoInception-4 Architecture

- Lightweight 8-layer inception network specialized for mesoscopic image analysis
- Inception blocks with parallel 1×1 and 3×3 convolutions
- Spatial attention map for heatmap generation
- Designed for <50ms inference on CPU

### ResNet-50 Feature Extractor

- Pretrained on ImageNet with transfer learning
- Grad-CAM for gradient-weighted class activation mapping
- Custom classification head (2048 → 512 → 128 → 1)
- Dropout regularization (0.4, 0.3)

### Ensemble Weighting

| Model | Weight | Rationale |
|-------|--------|-----------|
| MesoInception-4 | 0.4 | Specialized for mesoscopic artifacts |
| ResNet-50 | 0.6 | Broader semantic understanding |

### DWT Denoising

- **Wavelet**: Daubechies-4 (db4)
- **Decomposition Level**: 2
- **Thresholding**: Soft thresholding with MAD noise estimation
- **Effect**: Removes high-frequency compression artifacts from messaging apps

---

## License

MIT

---

## Credits

Built with:
- **PyTorch** — Neural network framework
- **FastAPI** — Async WebSocket streaming
- **MediaPipe** — Face mesh landmark detection
- **ReportLab** — PDF evidence generation
- **ONNX Runtime Web** — Browser WASM inference
- **React + Tailwind CSS** — Dashboard UI
