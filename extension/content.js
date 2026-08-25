/**
 * SASRIAKAL - Content Script
 * Monitors DOM for <video> elements, captures frames via offscreen canvas,
 * and injects transparent heatmap overlay canvases over detected videos.
 */

(function () {
  "use strict";

  const POLL_INTERVAL_MS = 2000;
  const CAPTURE_QUALITY = 0.85;
  const CANVAS_SCALE = 0.5;
  const SYNC_INTERVAL_MS = 2000;
  let managedVideos = new WeakMap();
  let overlayCanvases = new WeakMap();
  let isActive = false;
  let pollTimer = null;
  let syncTimer = null;
  let totalCaptures = 0;

  // ── Visible Page Indicator ───────────────────────────────────────────────────
  // Shows a small badge so you can tell the content script is alive without
  // opening DevTools.

  const badge = document.createElement("div");
  badge.id = "sasriakal-badge";
  badge.textContent = "🛡️ SASRIAKAL";
  badge.style.cssText = `
    position: fixed; bottom: 8px; right: 8px; z-index: 2147483647;
    padding: 4px 10px; border-radius: 6px; font-size: 11px; font-weight: 600;
    font-family: monospace; pointer-events: none;
    background: rgba(0,0,0,0.7); color: #00ff88;
    border: 1px solid rgba(0,255,136,0.3);
    transition: opacity 0.3s;
  `;
  (document.body || document.documentElement).appendChild(badge);

  function setBadge(msg, color) {
    badge.textContent = msg;
    badge.style.color = color || "#00ff88";
  }

  setBadge("🛡️ SASRIAKAL loaded", "#00ff88");
  console.log("[SASRIAKAL] Content script loaded on", window.location.href);

  // ── Video Discovery ──────────────────────────────────────────────────────────

  function discoverVideoElements() {
    const videos = document.querySelectorAll("video");
    let found = false;

    videos.forEach((video, i) => {
      const info = `video[${i}]: ${video.videoWidth}x${video.videoHeight} readyState=${video.readyState} paused=${video.paused}`;

      if (managedVideos.has(video)) return;

      if (video.videoWidth === 0 || video.videoHeight === 0) {
        console.log(`[SASRIAKAL] ${info} → skip: zero dimensions`);
        return;
      }
      if (video.readyState < 2) {
        console.log(`[SASRIAKAL] ${info} → skip: readyState < 2`);
        return;
      }

      console.log(`[SASRIAKAL] ${info} → setting up interception`);
      setupVideoInterception(video);
      found = true;
    });

    if (videos.length === 0) {
      console.log("[SASRIAKAL] No <video> elements found on page");
    }

    // Update badge
    const managedCount = countManaged();
    if (managedCount > 0) {
      setBadge(`🛡️ SASRIAKAL • ${managedCount} video(s) tracked`, isActive ? "#00ff88" : "#fbbf24");
    }
  }

  function countManaged() {
    let count = 0;
    // WeakMap isn't iterable, so count by checking all videos
    document.querySelectorAll("video").forEach((v) => {
      if (managedVideos.has(v)) count++;
    });
    return count;
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
        video._sasriakalRafId = requestAnimationFrame(captureLoop);
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
        chrome.runtime.sendMessage(
          {
            type: "CAPTURE_FRAME",
            payload: {
              base64Frame,
              videoId,
              width: video.videoWidth,
              height: video.videoHeight,
            },
          },
          (response) => {
            if (chrome.runtime.lastError) {
              console.warn("[SASRIAKAL] CAPTURE_FRAME failed:", chrome.runtime.lastError.message);
            }
          }
        );

        totalCaptures++;
        if (totalCaptures % 15 === 1) {
          console.log(`[SASRIAKAL] ✓ Captured ${totalCaptures} frames`);
          setBadge(`🛡️ SASRIAKAL • ${totalCaptures} frames`, "#00ff88");
        }

        const meta = managedVideos.get(video);
        if (meta) meta.frameCount++;
      } catch (err) {
        console.warn("[SASRIAKAL] Frame capture error:", err.message);
        if (err.name === "SecurityError") {
          setBadge("🛡️ SASRIAKAL • CORS blocked", "#ef4444");
        }
      }

      video._sasriakalRafId = requestAnimationFrame(captureLoop);
    };

    video._sasriakalRafId = requestAnimationFrame(captureLoop);

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

    console.log(`[SASRIAKAL] ✓ Interception set up (${video.videoWidth}x${video.videoHeight})`);
  }

  // ── Detection Result Handler ─────────────────────────────────────────────────

  chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === "DETECTION_RESULT") {
      const { confidence, heatmap, av_desync, threshold } = message.payload;
      renderOverlayResults(confidence, heatmap, av_desync, threshold);
    }
    if (message.type === "TOGGLE_DETECTION") {
      const shouldBeActive = message.payload.active;
      console.log(`[SASRIAKAL] TOGGLE_DETECTION: active=${shouldBeActive}`);
      if (shouldBeActive && !isActive) {
        startPolling();
      } else if (!shouldBeActive && isActive) {
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
        canvas.style.opacity = "0.85";

        heatmap.forEach((box) => {
          const { x, y, w, h, score } = box;
          const intensity = Math.min(1, (confidence - threshold) / (1 - threshold));
          const r = 255;
          const g = Math.round(255 * (1 - intensity));
          const b = 0;
          const alpha = 0.3 + intensity * 0.4;

          ctx.shadowColor = `rgba(${r}, ${g}, ${b}, 0.8)`;
          ctx.shadowBlur = 15 + intensity * 20;
          ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, 0.9)`;
          ctx.lineWidth = 3;
          ctx.strokeRect(x, y, w, h);
          ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
          ctx.fillRect(x, y, w, h);
          ctx.shadowBlur = 0;

          ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
          ctx.font = "bold 16px monospace";
          ctx.fillText(`${(score * 100).toFixed(1)}%`, x + 4, y - 6 > 14 ? y - 6 : y + 16);
        });

        if (av_desync && av_desync.score > 0.5) {
          ctx.fillStyle = "rgba(255, 60, 60, 0.9)";
          ctx.beginPath();
          if (ctx.roundRect) ctx.roundRect(canvas.width - 220, 10, 210, 36, 8);
          else ctx.rect(canvas.width - 220, 10, 210, 36);
          ctx.fill();
          ctx.fillStyle = "#ffffff";
          ctx.font = "bold 13px sans-serif";
          ctx.fillText(`⚠ AV DESYNC: ${(av_desync.score * 100).toFixed(1)}%`, canvas.width - 210, 34);
        }
      } else {
        canvas.style.opacity = "0";
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
    });
  }

  // ── Polling & Lifecycle ──────────────────────────────────────────────────────

  function startPolling() {
    if (isActive) return;
    isActive = true;
    console.log("[SASRIAKAL] ✓ Detection started — capturing frames");
    setBadge("🛡️ SASRIAKAL • scanning…", "#00ff88");
    discoverVideoElements();
    pollTimer = setInterval(discoverVideoElements, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    isActive = false;
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    document.querySelectorAll("video").forEach((video) => {
      if (video._sasriakalRafId) {
        cancelAnimationFrame(video._sasriakalRafId);
        video._sasriakalRafId = null;
      }
    });
    document.querySelectorAll("canvas[id^='sasriakal-overlay-']").forEach((c) => c.remove());
    setBadge("🛡️ SASRIAKAL • paused", "#fbbf24");
    console.log("[SASRIAKAL] Detection stopped");
  }

  // ── Periodic Storage Sync ────────────────────────────────────────────────────
  // Keeps content script in sync with the storage flag even if
  // TOGGLE_DETECTION was missed.

  function syncWithStorage() {
    try {
      chrome.storage.local.get("detectionActive", (data) => {
        if (chrome.runtime.lastError) {
          console.warn("[SASRIAKAL] Storage read error:", chrome.runtime.lastError.message);
          return;
        }
        const shouldBeActive = !!data.detectionActive;
        if (shouldBeActive && !isActive) {
          console.log("[SASRIAKAL] Storage sync → activating");
          startPolling();
        } else if (!shouldBeActive && isActive) {
          console.log("[SASRIAKAL] Storage sync → deactivating");
          stopPolling();
        }
      });
    } catch (e) {
      console.warn("[SASRIAKAL] Storage sync exception:", e.message);
    }
  }

  // ── Initialize ───────────────────────────────────────────────────────────────

  // Run immediately and then on interval
  syncWithStorage();
  syncTimer = setInterval(syncWithStorage, SYNC_INTERVAL_MS);

  // Also try to get status from background
  try {
    chrome.runtime.sendMessage({ type: "GET_DETECTION_STATUS" }, (response) => {
      if (chrome.runtime.lastError || !response) {
        console.log("[SASRIAKAL] GET_DETECTION_STATUS: no response (background may be sleeping)");
        return;
      }
      console.log("[SASRIAKAL] GET_DETECTION_STATUS:", JSON.stringify(response));
      if (response.active && !isActive) {
        startPolling();
      }
    });
  } catch (e) {
    console.warn("[SASRIAKAL] GET_DETECTION_STATUS failed:", e.message);
  }

  console.log("[SASRIAKAL] Content script initialized — sync every", SYNC_INTERVAL_MS, "ms");
})();
