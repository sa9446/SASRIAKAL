import React from 'react'
import { Shield, Wifi, WifiOff, Play, Square, Zap } from 'lucide-react'

export default function Header({ connectionStatus, isDetecting, onToggleDetection }) {
  const statusColors = {
    connected: 'text-sasriakal-500',
    disconnected: 'text-surface-400',
    error: 'text-red-500',
  }

  const statusLabels = {
    connected: 'Connected',
    disconnected: 'Disconnected',
    error: 'Error',
  }

  return (
    <header className="border-b border-surface-800/50 bg-surface-950/80 backdrop-blur-xl sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-sasriakal-500 to-sasriakal-600 flex items-center justify-center glow-green">
              <Shield className="w-6 h-6 text-surface-950" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">
                SASRIAKAL
              </h1>
              <p className="text-xs text-surface-400 -mt-0.5">
                Real-Time Deepfake Detection
              </p>
            </div>
          </div>

          {/* Status & Controls */}
          <div className="flex items-center gap-4">
            {/* Connection Status */}
            <div className="flex items-center gap-2 text-sm">
              {connectionStatus === 'connected' ? (
                <Wifi className={`w-4 h-4 ${statusColors[connectionStatus]}`} />
              ) : (
                <WifiOff className={`w-4 h-4 ${statusColors[connectionStatus]}`} />
              )}
              <span className={statusColors[connectionStatus]}>
                {statusLabels[connectionStatus]}
              </span>
            </div>

            {/* Detection Toggle */}
            <button
              onClick={onToggleDetection}
              className={`
                flex items-center gap-2 px-4 py-2 rounded-xl font-semibold text-sm
                transition-all duration-200
                ${isDetecting
                  ? 'bg-red-500/15 border border-red-500/30 text-red-400 hover:bg-red-500/25'
                  : 'bg-sasriakal-500/15 border border-sasriakal-500/30 text-sasriakal-500 hover:bg-sasriakal-500/25'
                }
              `}
            >
              {isDetecting ? (
                <>
                  <Square className="w-4 h-4" />
                  Stop
                </>
              ) : (
                <>
                  <Play className="w-4 h-4" />
                  Start Detection
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}
