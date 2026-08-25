/**
 * SASRIAKAL - Background Service Worker
 * Handles offscreen processing, WebSocket streaming to backend,
 * and ONNX WASM inference for local deepfake detection.
 */

const BACKEND_WS_URL = "ws://localhost:8000/ws/stream";
const INFERENCE_FPS = 15;
const FRAME_INTERVAL_MS = 1000 / INFERENCE_FPS;
const CONFIDENCE_THRESHOLD = 0.65;

let offscreenDocumentCreated = false;
let wsConnection = null;
let isProcessing = false;
let lastFrameTime = 0;
let framesSent = 0;
let framesSkipped = 0;

// ── Offscreen Document Management ──────────────────────────────────────────────

async function ensureOffscreenDocument() {
  if (offscreenDocumentCreated) return;
  try {
    await chrome.offscreen.createDocument({
      url: "offscreen.html",
      reasons: ["WORKERS"],
      justification: "ONNX WASM inference requires dedicated worker context",
    });
    offscreenDocumentCreated = true;
  } catch (err) {
    if (err.message?.includes("already exists")) {
      offscreenDocumentCreated = true;
    } else {
      console.error("[SASRIAKAL] Failed to create offscreen document:", err);
    }
  }
}

// ── WebSocket Connection Manager ───────────────────────────────────────────────

function connectWebSocket() {
  if (wsConnection && wsConnection.readyState === WebSocket.OPEN) return;

  try {
    console.log("[SASRIAKAL] Connecting WebSocket to", BACKEND_WS_URL);
    wsConnection = new WebSocket(BACKEND_WS_URL);

    wsConnection.onopen = () => {
      console.log("[SASRIAKAL] WebSocket connected to backend");
      chrome.storage.local.set({ wsStatus: "connected" });
    };

    wsConnection.onmessage = (event) => {
      try {
        const result = JSON.parse(event.data);
        handleDetectionResult(result);
      } catch (err) {
        console.error("[SASRIAKAL] Failed to parse detection result:", err);
      }
    };

    wsConnection.onerror = (err) => {
      console.error("[SASRIAKAL] WebSocket error:", err);
      chrome.storage.local.set({ wsStatus: "error" });
    };

    wsConnection.onclose = () => {
      console.log("[SASRIAKAL] WebSocket disconnected, reconnecting in 3s...");
      wsConnection = null;
      chrome.storage.local.set({ wsStatus: "disconnected" });
      if (isProcessing) {
        setTimeout(connectWebSocket, 3000);
      }
    };
  } catch (err) {
    console.error("[SASRIAKAL] WebSocket connection failed:", err);
    if (isProcessing) {
      setTimeout(connectWebSocket, 5000);
    }
  }
}

function sendFrameToBackend(base64Frame, tabId, timestamp) {
  if (!wsConnection || wsConnection.readyState !== WebSocket.OPEN) {
    framesSkipped++;
    if (framesSkipped % 30 === 1) {
      console.warn(
        `[SASRIAKAL] WebSocket not open — ${framesSkipped} frames skipped`
      );
    }
    return;
  }

  try {
    wsConnection.send(
      JSON.stringify({
        frame: base64Frame,
        tab_id: tabId,
        timestamp: timestamp,
        source: "extension",
      })
    );
    framesSent++;
    if (framesSent % 30 === 1) {
      console.log(`[SASRIAKAL] ${framesSent} frames sent to backend`);
    }
  } catch (err) {
    console.error("[SASRIAKAL] Failed to send frame:", err);
  }
}

// ── Detection Result Handler ───────────────────────────────────────────────────

function handleDetectionResult(result) {
  const { tab_id, confidence, heatmap, av_desync, frame_hash } = result;

  // Store latest result for popup display
  chrome.storage.local.set({
    [`detection_${tab_id}`]: {
      confidence,
      heatmap,
      av_desync,
      frame_hash,
      timestamp: Date.now(),
    },
  });

  // Send result to content script for overlay rendering
  chrome.tabs
    .sendMessage(tab_id, {
      type: "DETECTION_RESULT",
      payload: {
        confidence,
        heatmap,
        av_desync,
        threshold: CONFIDENCE_THRESHOLD,
      },
    })
    .catch(() => {
      // Tab might not have content script loaded
    });
}

// ── Message Router ─────────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const { type, payload } = message;
  const tabId = sender.tab?.id || payload?.tabId;

  switch (type) {
    case "CAPTURE_FRAME": {
      const now = Date.now();
      if (now - lastFrameTime < FRAME_INTERVAL_MS) {
        sendResponse({ skipped: true });
        return false;
      }
      lastFrameTime = now;

      // Forward frame to backend via WebSocket
      if (payload?.base64Frame) {
        sendFrameToBackend(payload.base64Frame, tabId, now);
      }
      sendResponse({ processed: true });
      return false;
    }

    case "START_DETECTION": {
      isProcessing = true;
      framesSent = 0;
      framesSkipped = 0;
      connectWebSocket();
      chrome.storage.local.set({ detectionActive: true });
      sendResponse({ status: "started" });
      return false;
    }

    case "STOP_DETECTION": {
      isProcessing = false;
      chrome.storage.local.set({ detectionActive: false });
      sendResponse({ status: "stopped" });
      return false;
    }

    case "GET_DETECTION_STATUS": {
      chrome.storage.local.get(
        [`detection_${tabId}`, "detectionActive", "wsStatus"],
        (data) => {
          sendResponse({
            active: data.detectionActive || false,
            wsStatus: data.wsStatus || "disconnected",
            lastResult: data[`detection_${tabId}`] || null,
          });
        }
      );
      return true; // async response
    }

    case "REQUEST_PDF_REPORT": {
      // Forward to backend REST endpoint
      fetch("http://localhost:8000/api/generate-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
        .then((res) => res.arrayBuffer())
        .then((buf) => {
          // Convert to base64 data URL (URL.createObjectURL is unavailable in MV3 service workers)
          const bytes = new Uint8Array(buf);
          let binary = "";
          for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
          }
          const dataUrl = "data:application/pdf;base64," + btoa(binary);
          chrome.downloads.download({
            url: dataUrl,
            filename: `sasriakal-evidence-${Date.now()}.pdf`,
            saveAs: true,
          });
          sendResponse({ status: "download_initiated" });
        })
        .catch((err) => {
          sendResponse({ status: "error", message: err.message });
        });
      return true;
    }

    default:
      sendResponse({ error: "Unknown message type" });
      return false;
  }
});

// ── Extension Lifecycle ────────────────────────────────────────────────────────

chrome.runtime.onInstalled.addListener(() => {
  console.log("[SASRIAKAL] Extension installed");
  chrome.storage.local.set({
    detectionActive: false,
    wsStatus: "disconnected",
    confidenceThreshold: CONFIDENCE_THRESHOLD,
    inferenceMode: "local", // "local" | "backend" | "ensemble"
  });
});

chrome.runtime.onStartup.addListener(() => {
  connectWebSocket();
});

console.log("[SASRIAKAL] Background service worker loaded");
