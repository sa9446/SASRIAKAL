/**
 * SASRIAKAL - Content Script
 * Monitors DOM for <video> elements, captures frames via offscreen canvas,
 * and injects transparent heatmap overlay canvases over detected videos.
 */

(function () {
  "use strict";

  const POLL_INTERVAL_MS = 2000;
  const CAPTURE_QUALITY = 0.85;
  const CANVAS_SCALE = 0.5; // downscale for inference speed
  let managedVideos = new WeakMap();
  let overlayCanvases = new WeakMap();
  let isActive = false;
  let pollTimer = null;

  // ── Video Discovery ──────────────────────────────────────────────────────────

  function discoverVideoElements() {
    const videos = document.querySelectorAll("video");
    videos.forEach((video) => {
      if (managedVideos.has(video)) return;
      if (video.videoWidth === 0 || video.videoHeight === 0) return;
      if (video.readyState < 2) return; // HAVE_CURRENT_DATA minimum

      setupVideoInterception(video);
      managedVideos.set(video, { active: true, frameCount: 0 });
    });
  }

  function setupVideoInterception(video) {
    const videoId = `dg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

    // Create offscreen capture canvas
    const captureCanvas = document.createElement("canvas");
    captureCanvas.width = Math.round(video.videoWidth * CANVAS_SCALE);
    captureCanvas.height = Math.round(video.videoHeight * CANVAS_SCALE);
    const captureCtx = captureCanvas.getContext("2d", { willReadFrequently: true });

    // Create overlay canvas
    const overlayCanvas = document.createElement("canvas");
    overlayCanvas.id = `sasriakal-overlay-${videoId}`;
    overlayCanvas.style.cssText = `
      position: absolute;
      top: 0; left: 0;
      width: 100%; height: 100%;
      pointer-events: none;
      z-index: 999999;
      opacity: 0;
      transition: opacity 0.3s ease;
    `;
    overlayCanvases.set(video, overlayCanvas);

    // Position overlay relative to video
    const positionOverlay = () => {
      const rect = video.getBoundingClientRect();
      const parent = video.parentElement;
      if (!parent) return;

      const parentStyle = window.getComputedStyle(parent);
      if (parentStyle.position === "static") {
        parent.style.position = "relative";
      }

      overlayCanvas.width = video.videoWidth;
      overlayCanvas.height = video.videoHeight;
      overlayCanvas.style.width = `${rect.width}px`;
      overlayCanvas.style.height = `${rect.height}px`;

      if (!parent.contains(overlayCanvas)) {
        parent.appendChild(overlayCanvas);
      }
    };

    positionOverlay();
    const resizeObserver = new ResizeObserver(positionOverlay);
    resizeObserver.observe(video);

    // Frame capture loop
    const captureLoop = () => {
      if (!isActive || video.paused || video.ended || video.readyState < 2) {
        requestAnimationFrame(captureLoop);
        return;
      }

      try {
        captureCtx.drawImage(
          video,
          0, 0,
          captureCanvas.width,
          captureCanvas.height
        );

        const base64Frame = captureCanvas.toDataURL("image/jpeg", CAPTURE_QUALITY);

        // Send frame to background for processing
        chrome.runtime.sendMessage({
          type: "CAPTURE_FRAME",
          payload: {
            base64Frame,
            videoId,
            width: video.videoWidth,
            height: video.videoHeight,
          },
        });

        const meta = managedVideos.get(video);
        if (meta) meta.frameCount++;
      } catch (err) {
        // Canvas tainted by CORS - silently skip
        console.debug("[SASRIAKAL] Frame capture blocked (CORS):", err.message);
      }

      requestAnimationFrame(captureLoop);
    };

    requestAnimationFrame(captureLoop);

    // Store references
    managedVideos.set(video, {
      active: true,
      videoId,
      captureCanvas,
      captureCtx,
      overlayCanvas,
      captureLoop,
      resizeObserver,
      frameCount: 0,
    });
  }

  // ── Detection Result Handler ─────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "DETECTION_RESULT") {
      const { confidence, heatmap, av_desync, threshold } = message.payload;
      renderOverlayResults(confidence, heatmap, av_desync, threshold);
    }
    if (message.type === "TOGGLE_DETECTION") {
      isActive = message.payload.active;
      if (isActive) {
        startPolling();
      } else {
        stopPolling();
      }
    }
  });

  function renderOverlayResults(confidence, heatmap, av_desync, threshold) {
    const videos = document.querySelectorAll("video");
    videos.forEach((video) => {
      const meta = managedVideos.get(video);
      if (!meta || !meta.overlayCanvas) return;

      const canvas = meta.overlayCanvas;
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      if (confidence >= threshold && heatmap) {
        // Draw heatmap rectangles over detected manipulations
        canvas.style.opacity = "0.85";

        heatmap.forEach((box) => {
          const { x, y, w, h, score } = box;

          // Red/amber gradient based on severity
          const intensity = Math.min(1, (confidence - threshold) / (1 - threshold));
          const r = Math.round(255);
          const g = Math.round(255 * (1 - intensity));
          const b = 0;
          const alpha = 0.3 + intensity * 0.4;

          // Glow effect
          ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
          ctx.shadowBlur = 15 + intensity * 20;

          // Bounding box
          ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.9)`;
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, w, h);

          // Semi-transparent fill
          ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
          ctx.fillRect(x, y, w, h);

          // Reset shadow
          ctx.shadowBlur = 0;

          // Score label
          ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
          ctx.font = "bold 16px monospace";
          ctx.fillText(
            `${(score * 100).toFixed(1)}%`,
            x + 4,
            y - 6 > 14 ? y - 6 : y + 16
          );
        });

        // AV Desync warning badge
        if (av_desync && av_desync.score > 0.5) {
          ctx.fillStyle = "rgba(255, 60, 60, 0.9)";
          ctx.beginPath();
          if (ctx.roundRect) {
            ctx.roundRect(canvas.width - 220, 10, 210, 36, 8);
          } else {
            ctx.rect(canvas.width - 220, 10, 210, 36);
          }
          ctx.fill();
          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 13px sans-serif";
          ctx.fillText(
            `⚠ AV DESYNC: ${(av_desync.score * 100).toFixed(1)}%`,
            canvas.width - 210,
            34
          );
        }
      } else {
        canvas.style.opacity = "0";
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    });
  }

  // ── Polling & Lifecycle ──────────────────────────────────────────────────────

  function startPolling() {
    isActive = true;
    discoverVideoElements();
    pollTimer = setInterval(discoverVideoElements, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    isActive = false;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    // Clean up overlays
    document.querySelectorAll("canvas[id^='sasriakal-overlay-']").forEach((c) => c.remove());
  }

  // ── Initialize ───────────────────────────────────────────────────────────────

  // Listen for toggle from popup
  chrome.storage.local.get("detectionActive", (data) => {
    if (data.detectionActive) {
      startPolling();
    }
  });

  // Auto-start on load
  chrome.runtime.sendMessage({ type: "GET_DETECTION_STATUS" }, (response) => {
    if (response?.active) {
      startPolling();
    }
  });

  console.log("[SASRIAKAL] Content script loaded");
})();
