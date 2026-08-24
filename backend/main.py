"""
SASRIAKAL - FastAPI Backend
Asynchronous WebSocket streaming for real-time deepfake detection,
REST endpoints for batch processing and evidence report generation.
"""

import asyncio
import base64
import hashlib
import json
import logging
import os
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel

try:
    from config import (
        ALLOWED_ORIGINS, HOST, PORT, RELOAD, WORKERS,
        MAX_UPLOAD_BYTES, ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT,
        WS_MAX_CONNECTIONS, CONFIDENCE_THRESHOLD, LOG_LEVEL, LOG_FORMAT,
    )
    from core.model import DeepfakeEnsemble
    from core.preprocess import NoisePreprocessor
    from core.av_sync import AVDesyncEngine
    from core.c2pa_parser import C2PAParser
    from utils.pdf_generator import EvidencePDFGenerator
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from config import (
        ALLOWED_ORIGINS, HOST, PORT, RELOAD, WORKERS,
        MAX_UPLOAD_BYTES, ALLOWED_IMAGE_EXT, ALLOWED_VIDEO_EXT,
        WS_MAX_CONNECTIONS, CONFIDENCE_THRESHOLD, LOG_LEVEL, LOG_FORMAT,
    )
    from core.model import DeepfakeEnsemble
    from core.preprocess import NoisePreprocessor
    from core.av_sync import AVDesyncEngine
    from core.c2pa_parser import C2PAParser
    from utils.pdf_generator import EvidencePDFGenerator

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger("sasriakal")

# ── Global State ───────────────────────────────────────────────────────────────

model: Optional[DeepfakeEnsemble] = None
preprocessor: Optional[NoisePreprocessor] = None
av_engine: Optional[AVDesyncEngine] = None
c2pa_parser: Optional[C2PAParser] = None
pdf_generator: Optional[EvidencePDFGenerator] = None
active_connections: dict[str, WebSocket] = {}

# In-memory session store (production: use Redis/PostgreSQL)
session_store: dict[str, dict] = {}


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize heavy resources on startup, release on shutdown."""
    global model, preprocessor, av_engine, c2pa_parser, pdf_generator

    logger.info("Loading SASRIAKAL models...")
    model = DeepfakeEnsemble()
    preprocessor = NoisePreprocessor()
    av_engine = AVDesyncEngine()
    c2pa_parser = C2PAParser()
    pdf_generator = EvidencePDFGenerator()
    logger.info(f"All models loaded successfully (device: {model.device})")

    yield

    logger.info("Shutting down SASRIAKAL...")
    if model:
        model.unload()


app = FastAPI(
    title="SASRIAKAL",
    description="Real-time deepfake detection engine",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def decode_frame_b64(frame_b64: str) -> tuple[bytes, np.ndarray]:
    """Decode base64 frame to bytes and OpenCV image. Raises ValueError on failure."""
    # Strip data URL prefix if present
    if "," in frame_b64[:100]:
        frame_b64 = frame_b64.split(",", 1)[1]

    frame_bytes = base64.b64decode(frame_b64)
    np_arr = np.frombuffer(frame_bytes, dtype=np.uint8)
    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if frame is None:
        raise ValueError("Failed to decode frame from base64")

    return frame_bytes, frame


def ensure_session(session_id: str) -> dict:
    """Get or create a session entry for detection results."""
    if session_id not in session_store:
        session_store[session_id] = {
            "detection_results": [],
            "av_desync": {"score": 0.0},
            "c2pa_valid": False,
        }
    return session_store[session_id]


def check_upload_size(contents: bytes):
    """Reject uploads exceeding the configured size limit."""
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(contents)} bytes (max {MAX_UPLOAD_BYTES})",
        )


def get_file_extension(filename: Optional[str]) -> str:
    """Get lowercase file extension."""
    if not filename:
        return ""
    return Path(filename).suffix.lower()


# ── Pydantic Models ────────────────────────────────────────────────────────────

class FrameRequest(BaseModel):
    frame: str  # base64 encoded
    tab_id: Optional[str] = None
    timestamp: Optional[float] = None
    source: str = "extension"


class DetectionResult(BaseModel):
    confidence: float
    heatmap: list[dict]
    av_desync: dict
    frame_hash: str
    processing_time_ms: float
    model_version: str = "v1.0.0"


class ReportRequest(BaseModel):
    tab_id: Optional[str] = None
    session_id: Optional[str] = None


# ── WebSocket Streaming Endpoint ──────────────────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    Asynchronous WebSocket endpoint for real-time video frame streaming.
    Accepts base64 or binary frames, processes through ensemble model,
    and returns detection results with heatmap coordinates.
    Server-side rate limiting enforced at WS_FRAME_RATE_LIMIT FPS.
    """
    if len(active_connections) >= WS_MAX_CONNECTIONS:
        await websocket.close(code=1013, reason="Too many connections")
        return

    await websocket.accept()
    conn_id = f"conn_{int(time.time() * 1000)}"
    active_connections[conn_id] = websocket
    logger.info(f"WebSocket connected: {conn_id} (total: {len(active_connections)})")

    frame_count = 0
    total_processing_time = 0.0
    min_frame_interval = 1.0 / 30  # Server-side 30 FPS cap
    last_frame_time = 0.0

    try:
        while True:
            raw = await websocket.receive_text()
            now = time.time()

            # Server-side rate limiting
            if now - last_frame_time < min_frame_interval:
                continue
            last_frame_time = now

            start_time = time.perf_counter()

            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"error": "Invalid JSON"})
                continue

            # Decode frame
            frame_b64 = data.get("frame", "")
            if not frame_b64:
                await websocket.send_json({"error": "No frame data"})
                continue

            try:
                frame_bytes, frame = decode_frame_b64(frame_b64)
            except Exception as e:
                await websocket.send_json({"error": f"Frame decode failed: {str(e)}"})
                continue

            # Run CPU-bound preprocessing + inference in a thread
            # to avoid blocking the asyncio event loop
            def _process_frame(f_bytes, f):
                cleaned = preprocessor.denoise_frame(f)
                conf, heat, scores = model.predict(cleaned)
                h = hashlib.sha256(f_bytes).hexdigest()[:16]
                return conf, heat, scores, h

            confidence, heatmap_boxes, layer_scores, frame_hash = await asyncio.to_thread(_process_frame, frame_bytes, frame)

            # AV Desync analysis (if audio data present)
            av_desync_result = {"score": 0.0, "phonemes": [], "visemes": [], "offset_ms": 0.0}
            audio_data = data.get("audio")
            if audio_data:
                try:
                    audio_np = np.frombuffer(base64.b64decode(audio_data), dtype=np.float32)
                    av_desync_result = await asyncio.to_thread(
                        av_engine.analyze_av_sync, frame, audio_np
                    )
                except Exception as e:
                    logger.warning(f"AV desync failed: {e}")

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            frame_count += 1
            total_processing_time += elapsed_ms

            # Store in session
            tab_id = data.get("tab_id", "default")
            session_id = data.get("session_id", tab_id)
            session = ensure_session(session_id)
            session["detection_results"].append({
                "frame": frame_count,
                "timestamp_s": round(data.get("timestamp", now), 2),
                "confidence": round(confidence, 4),
                "frame_hash": frame_hash,
            })
            session["av_desync"] = av_desync_result

            result = {
                "tab_id": tab_id,
                "session_id": session_id,
                "confidence": round(confidence, 4),
                "heatmap": heatmap_boxes,
                "av_desync": av_desync_result,
                "frame_hash": frame_hash,
                "processing_time_ms": round(elapsed_ms, 2),
                "frame_number": frame_count,
                "avg_processing_ms": round(total_processing_time / frame_count, 2),
                "model_version": "v1.0.0",
                "timestamp": data.get("timestamp", time.time()),
            }

            await websocket.send_json(result)

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {conn_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        active_connections.pop(conn_id, None)
        logger.info(f"WebSocket cleaned up: {conn_id} (total: {len(active_connections)})")


# ── REST Endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """System health check."""
    return {
        "status": "healthy",
        "model_loaded": model is not None and model.is_loaded,
        "device": str(model.device) if model else "unknown",
        "active_ws_connections": len(active_connections),
        "active_sessions": len(session_store),
        "version": "1.0.0",
    }


@app.post("/api/detect", response_model=DetectionResult)
async def detect_frame(request: FrameRequest):
    """Single frame detection endpoint."""
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    start_time = time.perf_counter()

    try:
        frame_bytes, frame = decode_frame_b64(request.frame)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Frame decode failed: {e}")

    cleaned = preprocessor.denoise_frame(frame)
    confidence, heatmap_boxes, _ = model.predict(cleaned)
    frame_hash = hashlib.sha256(frame_bytes).hexdigest()[:16]
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return DetectionResult(
        confidence=round(confidence, 4),
        heatmap=heatmap_boxes,
        av_desync={"score": 0.0},
        frame_hash=frame_hash,
        processing_time_ms=round(elapsed_ms, 2),
    )


@app.post("/api/detect/upload")
async def detect_upload(file: UploadFile = File(...)):
    """Upload a video/image file for batch detection."""
    contents = await file.read()
    check_upload_size(contents)

    ext = get_file_extension(file.filename)

    if ext in ALLOWED_VIDEO_EXT:
        return await process_video(contents, file.filename)
    elif ext in ALLOWED_IMAGE_EXT or not ext:
        frame = cv2.imdecode(np.frombuffer(contents, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(status_code=400, detail="Cannot decode file")

        cleaned = preprocessor.denoise_frame(frame)
        confidence, heatmap_boxes, _ = model.predict(cleaned)
        frame_hash = hashlib.sha256(contents).hexdigest()[:16]

        return {
            "filename": file.filename,
            "confidence": round(confidence, 4),
            "heatmap": heatmap_boxes,
            "frame_hash": frame_hash,
            "is_video": False,
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")


async def process_video(contents: bytes, filename: str) -> dict:
    """Process video file frame by frame."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp.write(contents)
        tmp.flush()
        tmp.close()

        cap = cv2.VideoCapture(tmp.name)
        if not cap.isOpened():
            raise HTTPException(status_code=400, detail="Cannot open video file")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_interval = max(1, int(fps / 5))  # Sample at ~5 FPS

        results = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                cleaned = preprocessor.denoise_frame(frame)
                confidence, heatmap_boxes, _ = model.predict(cleaned)
                results.append({
                    "frame": frame_idx,
                    "timestamp_s": round(frame_idx / fps, 2),
                    "confidence": round(confidence, 4),
                    "heatmap": heatmap_boxes,
                })

            frame_idx += 1

        cap.release()

        # Aggregate results
        if not results:
            return {"filename": filename, "error": "No frames processed"}

        avg_confidence = sum(r["confidence"] for r in results) / len(results)
        max_confidence = max(r["confidence"] for r in results)
        flagged_frames = [r for r in results if r["confidence"] >= 0.65]

        return {
            "filename": filename,
            "total_frames": total_frames,
            "sampled_frames": len(results),
            "avg_confidence": round(avg_confidence, 4),
            "max_confidence": round(max_confidence, 4),
            "flagged_frames": len(flagged_frames),
            "frame_results": results,
        }
    finally:
        os.unlink(tmp.name)


@app.post("/api/av-desync")
async def analyze_av_desync(video_file: UploadFile = File(...)):
    """Analyze audio-visual synchronization for voice clone / face swap detection."""
    contents = await video_file.read()
    check_upload_size(contents)

    tmp_video = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    try:
        tmp_video.write(contents)
        tmp_video.flush()
        tmp_video.close()

        result = av_engine.analyze_video_file(tmp_video.name)
        return result
    finally:
        os.unlink(tmp_video.name)


@app.post("/api/validate-c2pa")
async def validate_c2pa(file: UploadFile = File(...)):
    """Validate C2PA provenance metadata and cryptographic signatures."""
    contents = await file.read()
    check_upload_size(contents)

    result = c2pa_parser.parse(contents, file.filename)
    return result


@app.post("/api/generate-report")
async def generate_report(request: ReportRequest):
    """Generate a court-ready forensic evidence PDF report from session data."""
    tab_id = request.tab_id or "unknown"
    session_id = request.session_id or f"session_{int(time.time())}"

    # Pull actual session data (not empty placeholder)
    session = session_store.get(session_id, {
        "detection_results": [],
        "av_desync": {"score": 0.0},
        "c2pa_valid": False,
    })

    report_data = {
        "session_id": session_id,
        "tab_id": tab_id,
        "detection_results": session.get("detection_results", []),
        "av_desync": session.get("av_desync", {"score": 0.0}),
        "c2pa_valid": session.get("c2pa_valid", False),
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
    }

    pdf_bytes = pdf_generator.generate(report_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=sasriakal-evidence-{session_id}.pdf"
        },
    )


# ── Startup ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=RELOAD, workers=WORKERS)
