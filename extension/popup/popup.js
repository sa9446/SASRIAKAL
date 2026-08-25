/**
 * SASRIAKAL - Popup Dashboard Controller
 */

(function () {
  "use strict";

  const toggleBtn = document.getElementById("toggleBtn");
  const statusDot = document.getElementById("statusDot");
  const statusText = document.getElementById("statusText");
  const confidenceValue = document.getElementById("confidenceValue");
  const desyncValue = document.getElementById("desyncValue");
  const frameCount = document.getElementById("frameCount");
  const fpsValue = document.getElementById("fpsValue");
  const confidenceFill = document.getElementById("confidenceFill");
  const exportPdfBtn = document.getElementById("exportPdfBtn");
  const logContainer = document.getElementById("logContainer");
  const modeButtons = document.querySelectorAll(".mode-btn");

  let isRunning = false;
  let pollInterval = null;
  let frameHistory = [];

  // ── Initialize ───────────────────────────────────────────────────────────────

  chrome.storage.local.get(["detectionActive", "inferenceMode"], (data) => {
    isRunning = data.detectionActive || false;
    updateToggleUI(isRunning);

    const mode = data.inferenceMode || "local";
    modeButtons.forEach((btn) => {
      btn.classList.toggle("selected", btn.dataset.mode === mode);
    });
  });

  // ── Toggle Detection ─────────────────────────────────────────────────────────

  toggleBtn.addEventListener("click", () => {
    isRunning = !isRunning;
    updateToggleUI(isRunning);

    chrome.storage.local.set({ detectionActive: isRunning });

    // Notify background
    chrome.runtime.sendMessage({
      type: isRunning ? "START_DETECTION" : "STOP_DETECTION",
    });

    // Notify content script of active tab (swallow error if content script not loaded)
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (tabs[0]?.id) {
        chrome.tabs.sendMessage(
          tabs[0].id,
          { type: "TOGGLE_DETECTION", payload: { active: isRunning } },
          () => {
            void chrome.runtime.lastError; // suppress "Receiving end does not exist"
          }
        );
      }
    });

    addLog(isRunning ? "Detection activated" : "Detection paused", isRunning ? "safe" : "warning");

    if (isRunning) {
      startPolling();
    } else {
      stopPolling();
    }
  });

  function updateToggleUI(active) {
    toggleBtn.textContent = active ? "STOP" : "START";
    toggleBtn.classList.toggle("active", active);
    statusDot.classList.toggle("active", active);
    statusText.textContent = active ? "Scanning" : "Inactive";
    exportPdfBtn.disabled = !active;
  }

  // ── Mode Selection ───────────────────────────────────────────────────────────

  modeButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      modeButtons.forEach((b) => b.classList.remove("selected"));
      btn.classList.add("selected");
      chrome.storage.local.set({ inferenceMode: btn.dataset.mode });
      addLog(`Mode: ${btn.textContent}`, "safe");
    });
  });

  // ── Polling for Status ──────────────────────────────────────────────────────

  function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(updateMetrics, 500);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  function updateMetrics() {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]?.id) return;

      try {
        chrome.runtime.sendMessage(
          { type: "GET_DETECTION_STATUS", payload: { tabId: tabs[0].id } },
          (response) => {
            if (chrome.runtime.lastError || !response?.lastResult) return;

            const { confidence, av_desync, timestamp } = response.lastResult;

            // Confidence display
            const confPct = (confidence * 100).toFixed(1);
            confidenceValue.textContent = `${confPct}%`;

            if (confidence < 0.35) {
              confidenceValue.className = "metric-value safe";
              confidenceFill.style.background =
                "linear-gradient(90deg, #00ff88, #00ccff)";
            } else if (confidence < 0.65) {
              confidenceValue.className = "metric-value warning";
              confidenceFill.style.background =
                "linear-gradient(90deg, #fbbf24, #f59e0b)";
            } else {
              confidenceValue.className = "metric-value danger";
              confidenceFill.style.background =
                "linear-gradient(90deg, #ef4444, #dc2626)";
            }
            confidenceFill.style.width = `${confPct}%`;

            // AV Desync
            const desyncPct = ((av_desync?.score || 0) * 100).toFixed(1);
            desyncValue.textContent = `${desyncPct}%`;
            desyncValue.className =
              desyncPct > 50
                ? "metric-value danger"
                : desyncPct > 25
                  ? "metric-value warning"
                  : "metric-value safe";

            // FPS tracking
            frameHistory.push(timestamp);
            frameHistory = frameHistory.filter((t) => timestamp - t < 1000);
            fpsValue.textContent = frameHistory.length;
            frameCount.textContent = parseInt(frameCount.textContent) + 1;

            // Alert on high confidence
            if (confidence >= 0.65) {
              addLog(`⚠ DEEPFAKE DETECTED: ${confPct}%`, "danger");
            }
          }
        );
      } catch (err) {
        // Service worker not available
      }
    });
  }

  // ── PDF Export ──────────────────────────────────────────────────────────────

  exportPdfBtn.addEventListener("click", () => {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs[0]?.id) return;

      chrome.runtime.sendMessage(
        {
          type: "REQUEST_PDF_REPORT",
          payload: { tab_id: tabs[0].id },
        },
        (response) => {
          if (chrome.runtime.lastError) return;
          if (response?.status === "download_initiated") {
            addLog("Evidence PDF exported", "safe");
          } else {
            addLog(
              `PDF export failed: ${response?.message || "Unknown error"}`,
              "danger"
            );
          }
        }
      );
    });
  });

  // ── Logging ─────────────────────────────────────────────────────────────────

  function addLog(message, level = "") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${level}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${message}`;
    logContainer.appendChild(entry);
    logContainer.scrollTop = logContainer.scrollHeight;

    // Keep last 50 entries
    while (logContainer.children.length > 50) {
      logContainer.removeChild(logContainer.firstChild);
    }
  }
})();
