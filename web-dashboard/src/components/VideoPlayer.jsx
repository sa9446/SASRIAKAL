import React, { useState, useRef, useEffect, useCallback, forwardRef } from 'react'
import { Video, Upload, Camera, FileVideo, AlertTriangle } from 'lucide-react'

const VideoPlayer = forwardRef(({
  isDetecting,
  currentResult,
  heatmapEnabled,
  threshold,
  onFrameCapture,
  onFileUpload,
  onC2PAValidate,
}, ref) => {
  const videoContainerRef = useRef(null)
  const canvasRef = useRef(null)
  const fileInputRef = useRef(null)
  const captureIntervalRef = useRef(null)
  const [source, setSource] = useState('none') // 'none' | 'webcam' | 'file'
  const [videoSrc, setVideoSrc] = useState(null)
  const [isWebcamActive, setIsWebcamActive] = useState(false)

  // Start webcam
  const startWebcam = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720, facingMode: 'user' },
        audio: true,
      })

      const video = videoContainerRef.current?.querySelector('video')
      if (video) {
        video.srcObject = stream
        video.play()
        setSource('webcam')
        setIsWebcamActive(true)
      }
    } catch (err) {
      console.error('Webcam access denied:', err)
    }
  }, [])

  // Stop webcam
  const stopWebcam = useCallback(() => {
    const video = videoContainerRef.current?.querySelector('video')
    if (video?.srcObject) {
      video.srcObject.getTracks().forEach(t => t.stop())
      video.srcObject = null
    }
    setIsWebcamActive(false)
    setSource('none')
  }, [])

  // Handle file upload
  const handleFileUpload = useCallback((e) => {
    const file = e.target.files?.[0]
    if (!file) return

    const url = URL.createObjectURL(file)
    setVideoSrc(url)
    setSource('file')

    // Determine validation type
    if (file.type.startsWith('image/') || file.type.startsWith('video/')) {
      onFileUpload(file)
    }

    // C2PA validation
    onC2PAValidate(file)
  }, [onFileUpload, onC2PAValidate])

  // Frame capture loop for live webcam
  useEffect(() => {
    if (isDetecting && isWebcamActive) {
      captureIntervalRef.current = setInterval(() => {
        const video = videoContainerRef.current?.querySelector('video')
        if (!video || video.paused || video.ended) return

        const canvas = document.createElement('canvas')
        canvas.width = video.videoWidth
        canvas.height = video.videoHeight
        const ctx = canvas.getContext('2d')
        ctx.drawImage(video, 0, 0)

        const base64 = canvas.toDataURL('image/jpeg', 0.85)
        onFrameCapture(base64)
      }, 1000 / 15) // 15 FPS
    }

    return () => {
      if (captureIntervalRef.current) {
        clearInterval(captureIntervalRef.current)
      }
    }
  }, [isDetecting, isWebcamActive, onFrameCapture])

  // Heatmap overlay rendering
  useEffect(() => {
    const canvas = canvasRef.current
    const container = videoContainerRef.current
    if (!canvas || !container) return

    const video = container.querySelector('video')
    if (!video) return

    canvas.width = video.videoWidth || 1280
    canvas.height = video.videoHeight || 720

    const ctx = canvas.getContext('2d')
    ctx.clearRect(0, 0, canvas.width, canvas.height)

    if (!heatmapEnabled || !currentResult?.heatmap) return
    if (currentResult.confidence < threshold) return

    currentResult.heatmap.forEach(box => {
      const { x, y, w, h, score } = box
      const intensity = Math.min(1, (currentResult.confidence - threshold) / (1 - threshold))

      // Glow
      const cx = x + w / 2
      const cy = y + h / 2
      const radius = Math.max(w, h) * 0.8
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, radius)
      glow.addColorStop(0, `rgba(255, ${Math.round(255 * (1 - intensity))}, 0, ${0.3 * intensity})`)
      glow.addColorStop(1, 'rgba(255, 0, 0, 0)')
      ctx.fillStyle = glow
      ctx.fillRect(x - w * 0.3, y - h * 0.3, w * 1.6, h * 1.6)

      // Box
      ctx.strokeStyle = `rgba(255, ${Math.round(40 + 160 * (1 - intensity))}, 0, 0.9)`
      ctx.lineWidth = 3
      ctx.strokeRect(x, y, w, h)

      // Label
      ctx.fillStyle = `rgba(0, 0, 0, 0.7)`
      ctx.fillRect(x, y - 22, 80, 20)
      ctx.fillStyle = `rgb(255, ${Math.round(40 + 160 * (1 - intensity))}, 0)`
      ctx.font = 'bold 13px monospace'
      ctx.fillText(`${(score * 100).toFixed(1)}%`, x + 4, y - 7)
    })
  }, [currentResult, heatmapEnabled, threshold])

  return (
    <div className="glass-card p-4">
      {/* Source Selection */}
      <div className="flex items-center gap-3 mb-4">
        <button
          onClick={startWebcam}
          disabled={isWebcamActive}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-800 border border-surface-700 text-sm text-surface-300 hover:bg-surface-700 transition disabled:opacity-40"
        >
          <Camera className="w-4 h-4" />
          Webcam
        </button>

        <button
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface-800 border border-surface-700 text-sm text-surface-300 hover:bg-surface-700 transition"
        >
          <Upload className="w-4 h-4" />
          Upload File
        </button>

        {isWebcamActive && (
          <button
            onClick={stopWebcam}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-500/15 border border-red-500/30 text-sm text-red-400 hover:bg-red-500/25 transition"
          >
            Stop Camera
          </button>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept="image/*,video/*"
          onChange={handleFileUpload}
          className="hidden"
        />
      </div>

      {/* Video Container */}
      <div
        ref={videoContainerRef}
        className="relative aspect-video bg-black rounded-xl overflow-hidden"
      >
        {source === 'none' && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-surface-500">
            <Video className="w-16 h-16 mb-4 opacity-30" />
            <p className="text-lg font-medium">No video source</p>
            <p className="text-sm mt-1">Start webcam or upload a file</p>
          </div>
        )}

        <video
          className="w-full h-full object-contain"
          playsInline
          muted
          loop
          src={videoSrc || undefined}
        />

        {/* Heatmap Overlay Canvas */}
        <canvas
          ref={canvasRef}
          className="absolute inset-0 w-full h-full pointer-events-none"
          style={{ mixBlendMode: 'screen' }}
        />

        {/* Confidence Badge */}
        {currentResult && (
          <div className={`
            absolute top-4 right-4 px-3 py-1.5 rounded-lg text-sm font-bold
            backdrop-blur-md border
            ${currentResult.confidence >= threshold
              ? 'bg-red-500/20 border-red-500/40 text-red-400'
              : 'bg-sasriakal-500/20 border-sasriakal-500/40 text-sasriakal-500'
            }
          `}>
            {currentResult.confidence >= threshold ? '⚠ ' : '✓ '}
            {((currentResult.confidence || 0) * 100).toFixed(1)}%
          </div>
        )}
      </div>
    </div>
  )
})

VideoPlayer.displayName = 'VideoPlayer'

export default VideoPlayer
