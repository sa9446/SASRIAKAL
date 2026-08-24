import React, { useState, useCallback, useEffect, useRef } from 'react'
import ErrorBoundary from './components/ErrorBoundary'
import Header from './components/Header'
import VideoPlayer from './components/VideoPlayer'
import HeatmapControls from './components/HeatmapControls'
import MetricsPanel from './components/MetricsPanel'
import AVDesyncPanel from './components/AVDesyncPanel'
import C2PAPanel from './components/C2PAPanel'
import DetectionLog from './components/DetectionLog'
import PDFExporter from './components/PDFExporter'
import { Video, AudioLines, FileCheck, FileDown } from 'lucide-react'

const API_BASE = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/ws/stream'

function FeatureSection({ number, icon, title, subtitle, accentColor, children }) {
  const colorMap = {
    green: {
      badge: 'bg-sasriakal-500/15 border-sasriakal-500/30 text-sasriakal-500',
      line: 'from-sasriakal-500/60 to-transparent',
    },
    amber: {
      badge: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
      line: 'from-amber-500/60 to-transparent',
    },
    blue: {
      badge: 'bg-blue-500/15 border-blue-500/30 text-blue-400',
      line: 'from-blue-500/60 to-transparent',
    },
    purple: {
      badge: 'bg-purple-500/15 border-purple-500/30 text-purple-400',
      line: 'from-purple-500/60 to-transparent',
    },
  }

  const colors = colorMap[accentColor] || colorMap.green

  return (
    <section className="relative">
      {/* Accent line */}
      <div className={`h-px bg-gradient-to-r ${colors.line} mb-6`} />

      {/* Section Header */}
      <div className="flex items-start gap-4 mb-5">
        <div className={`flex items-center justify-center w-10 h-10 rounded-xl border text-sm font-bold ${colors.badge} shrink-0`}>
          {number}
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            {icon}
            <h2 className="text-lg font-bold text-white tracking-tight">{title}</h2>
          </div>
          <p className="text-sm text-surface-400">{subtitle}</p>
        </div>
      </div>

      {/* Section Content */}
      <div>{children}</div>
    </section>
  )
}

export default function App() {
  const [connectionStatus, setConnectionStatus] = useState('disconnected')
  const [isDetecting, setIsDetecting] = useState(false)
  const [currentResult, setCurrentResult] = useState(null)
  const [history, setHistory] = useState([])
  const [heatmapEnabled, setHeatmapEnabled] = useState(true)
  const [threshold, setThreshold] = useState(0.65)
  const [c2paResult, setC2paResult] = useState(null)
  const [logs, setLogs] = useState([])
  const wsRef = useRef(null)
  const videoRef = useRef(null)
  const isDetectingRef = useRef(false)
  const awaitingResponse = useRef(false)

  // Keep ref in sync with state
  useEffect(() => {
    isDetectingRef.current = isDetecting
  }, [isDetecting])

  const addLog = useCallback((message, level = 'info') => {
    const entry = {
      id: Date.now() + Math.random(),
      timestamp: new Date().toISOString(),
      message,
      level,
    }
    setLogs(prev => [entry, ...prev].slice(0, 100))
  }, [])

  // WebSocket connection
  const connectWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(WS_URL)

    ws.onopen = () => {
      setConnectionStatus('connected')
      addLog('WebSocket connected to backend', 'success')
    }

    ws.onmessage = (event) => {
      try {
        const result = JSON.parse(event.data)
        awaitingResponse.current = false
        setCurrentResult(result)
        setHistory(prev => [result, ...prev].slice(0, 200))

        if (result.confidence >= 0.65) {
          addLog(`⚠ DEEPFAKE DETECTED: ${(result.confidence * 100).toFixed(1)}% confidence`, 'danger')
        }
      } catch (err) {
        addLog(`Failed to parse result: ${err.message}`, 'error')
      }
    }

    ws.onerror = () => {
      setConnectionStatus('error')
      addLog('WebSocket error', 'error')
    }

    ws.onclose = () => {
      setConnectionStatus('disconnected')
      awaitingResponse.current = false
      // Only auto-reconnect if detection is still active
      if (isDetectingRef.current) {
        addLog('WebSocket disconnected, reconnecting in 3s...', 'warning')
        setTimeout(() => {
          if (isDetectingRef.current) connectWebSocket()
        }, 3000)
      } else {
        addLog('WebSocket disconnected', 'info')
      }
    }

    wsRef.current = ws
  }, [addLog])

  // Send frame to backend — only if WebSocket is open and not waiting for a response
  const sendFrame = useCallback((frameBase64) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
    if (awaitingResponse.current) return

    awaitingResponse.current = true
    wsRef.current.send(JSON.stringify({
      frame: frameBase64,
      timestamp: Date.now(),
      source: 'web-dashboard',
    }))
  }, [])

  // Toggle detection
  const toggleDetection = useCallback(() => {
    if (!isDetecting) {
      connectWebSocket()
    } else {
      wsRef.current?.close()
      wsRef.current = null
      setConnectionStatus('disconnected')
    }
    setIsDetecting(!isDetecting)
    addLog(isDetecting ? 'Detection stopped' : 'Detection started', 'info')
  }, [isDetecting, connectWebSocket, addLog])

  // Upload file for analysis
  const uploadFile = useCallback(async (file) => {
    addLog(`Uploading file: ${file.name}`, 'info')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/api/detect/upload`, {
        method: 'POST',
        body: formData,
      })
      const result = await res.json()

      if (result.error) {
        addLog(`Upload error: ${result.error}`, 'error')
      } else {
        addLog(`Analysis complete: ${(result.avg_confidence || result.confidence) * 100}% confidence`, 'info')
        setCurrentResult(result)
        setHistory(prev => [result, ...prev])
      }
    } catch (err) {
      addLog(`Upload failed: ${err.message}`, 'error')
    }
  }, [addLog])

  // C2PA validation
  const validateC2PA = useCallback(async (file) => {
    addLog('Validating C2PA provenance...', 'info')
    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch(`${API_BASE}/api/validate-c2pa`, {
        method: 'POST',
        body: formData,
      })
      const result = await res.json()
      setC2paResult(result)
      addLog(
        result.has_c2pa
          ? `C2PA found: ${result.manifest_count} manifest(s), trust: ${result.trust_chain_valid ? 'VALID' : 'INVALID'}`
          : 'No C2PA metadata found',
        result.has_c2pa ? 'success' : 'warning'
      )
    } catch (err) {
      addLog(`C2PA validation failed: ${err.message}`, 'error')
    }
  }, [addLog])

  return (
    <div className="min-h-screen bg-surface-950">
      <Header
        connectionStatus={connectionStatus}
        isDetecting={isDetecting}
        onToggleDetection={toggleDetection}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-2">

        {/* ═══════════════════════════════════════════════════
            FEATURE 1: Real-Time Video Deepfake Detection Pipeline
        ═══════════════════════════════════════════════════ */}
        <FeatureSection
          number="01"
          icon={<Video className="w-5 h-5 text-sasriakal-500" />}
          title="Real-Time Video Deepfake Detection Pipeline"
          subtitle="Live webcam or file upload with frame-by-frame neural network analysis, confidence scoring, and heatmap overlay"
          accentColor="green"
        >
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left: Video + Controls */}
            <div className="lg:col-span-2 space-y-6">
              <ErrorBoundary fallbackLabel="Video player error">
                <VideoPlayer
                  ref={videoRef}
                  isDetecting={isDetecting}
                  currentResult={currentResult}
                  heatmapEnabled={heatmapEnabled}
                  threshold={threshold}
                  onFrameCapture={sendFrame}
                  onFileUpload={uploadFile}
                  onC2PAValidate={validateC2PA}
                />
              </ErrorBoundary>

              <ErrorBoundary fallbackLabel="Heatmap controls error">
                <HeatmapControls
                  heatmapEnabled={heatmapEnabled}
                  threshold={threshold}
                  onToggleHeatmap={setHeatmapEnabled}
                  onThresholdChange={setThreshold}
                />
              </ErrorBoundary>

              <ErrorBoundary fallbackLabel="Detection log error">
                <DetectionLog logs={logs} />
              </ErrorBoundary>
            </div>

            {/* Right: Metrics */}
            <div>
              <ErrorBoundary fallbackLabel="Metrics panel error">
                <MetricsPanel
                  currentResult={currentResult}
                  history={history}
                />
              </ErrorBoundary>
            </div>
          </div>
        </FeatureSection>

        {/* ═══════════════════════════════════════════════════
            FEATURE 2: Audio-Visual (AV) Desync Detection
        ═══════════════════════════════════════════════════ */}
        <FeatureSection
          number="02"
          icon={<AudioLines className="w-5 h-5 text-amber-400" />}
          title="Audio-Visual (AV) Desync Detection"
          subtitle="Detects lip-sync anomalies between audio phonemes and visual visemes — a key indicator of manipulated or synthesized video"
          accentColor="amber"
        >
          <div className="max-w-2xl">
            <ErrorBoundary fallbackLabel="AV Desync error">
              <AVDesyncPanel
                currentResult={currentResult}
              />
            </ErrorBoundary>
          </div>
        </FeatureSection>

        {/* ═══════════════════════════════════════════════════
            FEATURE 3: C2PA Provenance & Signature Validation
        ═══════════════════════════════════════════════════ */}
        <FeatureSection
          number="03"
          icon={<FileCheck className="w-5 h-5 text-blue-400" />}
          title="C2PA Provenance & Signature Validation"
          subtitle="Verifies Content Authenticity Initiative (CAI) C2PA manifests, trust chains, and detects tampering in media metadata"
          accentColor="blue"
        >
          <div className="max-w-2xl">
            <ErrorBoundary fallbackLabel="C2PA panel error">
              <C2PAPanel
                c2paResult={c2paResult}
              />
            </ErrorBoundary>
          </div>
        </FeatureSection>

        {/* ═══════════════════════════════════════════════════
            FEATURE 4: Court-Ready Forensic Evidence PDF Reports
        ═══════════════════════════════════════════════════ */}
        <FeatureSection
          number="04"
          icon={<FileDown className="w-5 h-5 text-purple-400" />}
          title="Court-Ready Forensic Evidence PDF Reports"
          subtitle="Generates legally admissible forensic evidence packages with SHA-256 hashes, detection scores, AV sync analysis, C2PA status, and chain of custody metadata"
          accentColor="purple"
        >
          <div className="max-w-md">
            <ErrorBoundary fallbackLabel="PDF exporter error">
              <PDFExporter
                sessionId={currentResult?.frame_hash || 'session-' + Date.now()}
                onExportStart={() => addLog('Generating evidence PDF...', 'info')}
                onExportComplete={() => addLog('PDF exported successfully', 'success')}
              />
            </ErrorBoundary>
          </div>
        </FeatureSection>

      </main>
    </div>
  )
}
