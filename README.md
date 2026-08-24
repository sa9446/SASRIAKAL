<div align="center">

# 🛡️ SASRIAKAL

### Real-Time Deepfake Detection Platform

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-2.1+-EE4C2C?style=flat&logo=pytorch&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

**Local browser inference (ONNX WASM) · FastAPI streaming fallback · Custom heatmap overlays · Court-ready evidence reports**

[Quick Start](#-quick-start) · [Features](#-features) · [API](#-api-reference) · [Docker](#-docker) · [Architecture](#-architecture)

</div>

---

## 📁 Project Structure

```
sasriakal/
├── extension/                        # Manifest V3 Chrome Extension
│   ├── manifest.json
│   ├── background.js                # Offscreen worker & WebSocket manager
│   ├── content.js                   # DOM video interception & canvas overlay
│   ├── overlay.js                   # Real-time gradient heatmap renderer
│   ├── offscreen.html               # ONNX WASM inference context
│   └── popup/                       # Extension dashboard UI
│       ├── popup.html
│       └── popup.js
├── backend/                          # FastAPI & Python Engine
│   ├── main.py                      # FastAPI app, WebSocket & REST routes
│   ├── config.py                    # Centralized env-based configuration
│   ├── core/
│   │   ├── preprocess.py            # 2D DWT denoising & face detection
│   │   ├── model.py                 # MesoInception-4 + ResNet-50 ensemble
│   │   ├── av_sync.py               # Phoneme-viseme AV desync engine
│   │   └── c2pa_parser.py           # C2PA provenance & signature inspector
│   ├── utils/
│   │   └── pdf_generator.py         # Court-ready evidence PDF (ReportLab)
│   ├── models/                      # ONNX export script
│   ├── tests/                       # Unit tests (pytest)
│   │   ├── test_config.py
│   │   ├── test_preprocess.py
│   │   ├── test_model.py
│   │   └── test_av_sync.py
│   ├── Dockerfile
│   └── requirements.txt
├── web-dashboard/                    # React + Tailwind Frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── VideoPlayer.jsx
│   │   │   ├── HeatmapControls.jsx
│   │   │   ├── MetricsPanel.jsx
│   │   │   ├── AVDesyncPanel.jsx
│   │   │   ├── C2PAPanel.jsx
│   │   │   ├── DetectionLog.jsx
│   │   │   ├── PDFExporter.jsx
│   │   │   └── ErrorBoundary.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── index.css
│   ├── package.json
│   ├── Dockerfile
│   ├── tailwind.config.js
│   └── vite.config.js
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 🚀 Quick Start

### Option A: Docker (Recommended)

```bash
git clone https://github.com/sa9446/SASRIAKAL.git
cd SASRIAKAL

# Copy environment config
cp .env.example .env

# Start everything
docker compose up --build
```

- **Dashboard:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000`

### Option B: Manual Setup

#### 1. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env
python main.py
```

#### 2. Dashboard

```bash
cd web-dashboard
npm install
npm run dev
```

#### 3. Chrome Extension

1. Navigate to `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked** → select `extension/` directory

---

## ✨ Features

### 🔍 Real-Time Detection Pipeline

```
Video Frame ──→ DWT Denoising ──→ MesoInception-4 ──┐
                                                     ├──→ Ensemble ──→ Confidence + Heatmap
         ──→ ResNet-50 Feature Extractor ────────────┘
```

| Feature | Detail |
|---------|--------|
| **Glass-to-glass latency** | < 100ms target |
| **DWT preprocessing** | Removes WhatsApp/Telegram compression artifacts |
| **Dual-model ensemble** | MesoInception-4 (mesoscopic) + ResNet-50 (semantic) |
| **Spatial heatmap** | Glowing red/amber overlays on manipulated regions |
| **GPU acceleration** | Auto-detects CUDA, falls back to CPU |

### 🎤 Audio-Visual Desync Detection

```
Video Frames ──→ MediaPipe Face Mesh ──→ Viseme Extraction ──┐
                                                             ├──→ DTW Alignment ──→ Desync Score
Audio Stream ──→ Spectral Analysis ───→ Phoneme Extraction ──┘
```

- Detects **voice cloning** and **face swapping** via temporal misalignment
- **Dynamic Time Warping** with Sakoe-Chiba band constraint
- Flags specific time ranges with significant desync

### 📜 C2PA Provenance Validation

- Parses JUMBF containers (JPEG/PNG)
- Validates ISO Base Media File Format UUID boxes (MP4)
- Verifies cryptographic signatures and hash integrity
- Detects tampering indicators

### 📄 Court-Ready Evidence PDFs

- Executive summary with detection verdict
- Per-frame confidence scores and frame hashes
- AV desync analysis with flagged segments
- Chain of custody metadata
- Cryptographic integrity verification
- Legal disclaimer for admissibility

### 🌐 Chrome Extension

- DOM `<video>` detection on YouTube, social media, WebRTC
- Offscreen Canvas processing (no DOM thread blocking)
- Local ONNX WASM inference
- Transparent heatmap overlay with pulsing glow animation

---

## 📡 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ws/stream` | WebSocket | Real-time frame streaming |
| `/api/detect` | POST | Single frame detection |
| `/api/detect/upload` | POST | Image/video file upload |
| `/api/av-desync` | POST | Audio-visual sync analysis |
| `/api/validate-c2pa` | POST | C2PA provenance check |
| `/api/generate-report` | POST | Generate evidence PDF |
| `/api/health` | GET | System health check |

### POST `/api/detect`

**Request:**
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

**Send:**
```json
{
  "frame": "<base64>",
  "tab_id": "tab-123",
  "timestamp": 1700000000000,
  "audio": "<base64-optional>"
}
```

**Receive:** Same format as `/api/detect` response.

---

## 🐳 Docker

```bash
# Start full stack (backend + dashboard)
docker compose up --build

# Backend only
docker compose up backend

# With GPU support (requires nvidia-container-toolkit)
docker compose up --build
```

Environment variables are configured via `.env` (see `.env.example`).

---

## ⚙️ Configuration

All settings are managed via environment variables. Copy `.env.example` to `.env` and adjust:

| Variable | Default | Description |
|----------|---------|-------------|
| `SASRIAKAL_PORT` | `8000` | Backend API port |
| `SASRIAKAL_DEVICE` | `auto` | `auto`, `cpu`, or `cuda` |
| `SASRIAKAL_THRESHOLD` | `0.65` | Detection confidence threshold |
| `SASRIAKAL_MAX_UPLOAD_MB` | `100` | Max upload file size |
| `SASRIAKAL_MAX_WS` | `50` | Max concurrent WebSocket connections |
| `SASRIAKAL_WS_FPS_LIMIT` | `30` | Server-side frame rate cap |
| `SASRIAKAL_LOG_LEVEL` | `INFO` | Logging verbosity |

---

## 🧪 Testing

```bash
cd backend
pip install pytest
pytest tests/ -v
```

Tests cover:
- Configuration loading and env overrides
- DWT denoising pipeline (shape, dtype, noise reduction)
- Ensemble model (predict, IoU, NMS, GPU device)
- AV desync engine (viseme/phoneme extraction, DTW alignment, edge cases)

---

## 🏗️ Architecture

### MesoInception-4

Lightweight 8-layer inception network specialized for mesoscopic image analysis:
- Parallel 1×1 and 3×3 convolution branches
- Spatial attention map for heatmap generation
- <50ms inference on CPU

### ResNet-50 Feature Extractor

- Pretrained on ImageNet with transfer learning
- Grad-CAM heatmap (computed separately, not during fast inference)
- Classification head: 2048 → 512 → 128 → 1
- Dropout regularization (0.4, 0.3)

### Ensemble Weighting

| Model | Weight | Rationale |
|-------|--------|-----------|
| MesoInception-4 | 0.4 | Specialized for mesoscopic artifacts |
| ResNet-50 | 0.6 | Broader semantic understanding |

### DWT Denoising

- **Wavelet:** Daubechies-4 (db4)
- **Levels:** 2-level decomposition
- **Thresholding:** Soft thresholding with MAD noise estimation
- **Effect:** Removes H.264/H.265 compression artifacts from messaging apps

---

## 📜 License

MIT

---

<div align="center">

**Built with** PyTorch · FastAPI · MediaPipe · ReportLab · ONNX Runtime · React · Tailwind CSS

</div>
