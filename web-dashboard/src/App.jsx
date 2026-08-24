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

const API_BASE = 'http://localhost:8000'
const WS_URL = 'ws://localhost:8000/ws/stream'

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
      addLog('WebSocket disconnected, reconnecting in 3s...', 'warning')
      setTimeout(connectWebSocket, 3000)
    }

    wsRef.current = ws
  }, [addLog])

  // Send frame to backend
  const sendFrame = useCallback((frameBase64) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

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

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column: Video + Controls */}
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

          {/* Right column: Metrics + Panels */}
          <div className="space-y-6">
            <ErrorBoundary fallbackLabel="Metrics panel error">
              <MetricsPanel
                currentResult={currentResult}
                history={history}
              />
            </ErrorBoundary>

            <ErrorBoundary fallbackLabel="AV Desync error">
              <AVDesyncPanel
                currentResult={currentResult}
              />
            </ErrorBoundary>

            <ErrorBoundary fallbackLabel="C2PA panel error">
              <C2PAPanel
                c2paResult={c2paResult}
              />
            </ErrorBoundary>

            <ErrorBoundary fallbackLabel="PDF exporter error">
              <PDFExporter
                sessionId={currentResult?.frame_hash || 'session-' + Date.now()}
                onExportStart={() => addLog('Generating evidence PDF...', 'info')}
                onExportComplete={() => addLog('PDF exported successfully', 'success')}
              />
            </ErrorBoundary>
          </div>
        </div>
      </main>
    </div>
  )
}
