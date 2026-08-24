import React, { useMemo } from 'react'
import { Activity, Clock, Cpu, AlertTriangle, CheckCircle } from 'lucide-react'

export default function MetricsPanel({ currentResult, history }) {
  const metrics = useMemo(() => {
    if (!currentResult) {
      return {
        confidence: 0,
        processingTime: 0,
        frameNumber: 0,
        detected: false,
      }
    }

    return {
      confidence: currentResult.confidence || currentResult.avg_confidence || 0,
      processingTime: currentResult.processing_time_ms || 0,
      frameNumber: currentResult.frame_number || 0,
      detected: (currentResult.confidence || 0) >= 0.65,
    }
  }, [currentResult])

  const confPct = (metrics.confidence * 100).toFixed(1)
  const confColor = metrics.confidence >= 0.65
    ? 'text-red-400'
    : metrics.confidence >= 0.35
      ? 'text-amber-400'
      : 'text-sasriakal-500'

  const glowClass = metrics.confidence >= 0.65
    ? 'glow-red'
    : metrics.confidence >= 0.35
      ? 'glow-amber'
      : 'glow-green'

  return (
    <div className={`glass-card p-5 ${glowClass}`}>
      <h3 className="text-sm font-semibold text-surface-300 uppercase tracking-wider mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4" />
        Detection Metrics
      </h3>

      {/* Confidence Gauge */}
      <div className="text-center mb-6">
        <div className={`text-5xl font-bold font-mono ${confColor} transition-colors duration-300`}>
          {confPct}%
        </div>
        <div className="text-sm text-surface-400 mt-1">Confidence Score</div>

        {/* Progress bar */}
        <div className="mt-3 h-2 bg-surface-800 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              metrics.confidence >= 0.65
                ? 'bg-gradient-to-r from-amber-500 to-red-500'
                : metrics.confidence >= 0.35
                  ? 'bg-gradient-to-r from-sasriakal-500 to-amber-500'
                  : 'bg-gradient-to-r from-sasriakal-600 to-sasriakal-400'
            }`}
            style={{ width: `${Math.min(100, confPct)}%` }}
          />
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 gap-3">
        <MetricCard
          icon={<Clock className="w-4 h-4" />}
          label="Latency"
          value={`${metrics.processingTime.toFixed(1)}ms`}
          color={metrics.processingTime < 50 ? 'text-sasriakal-500' : 'text-amber-400'}
        />
        <MetricCard
          icon={<Cpu className="w-4 h-4" />}
          label="Frame #"
          value={metrics.frameNumber.toString()}
          color="text-blue-400"
        />
        <MetricCard
          icon={metrics.detected ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          label="Status"
          value={metrics.detected ? 'FLAGGED' : 'CLEAR'}
          color={metrics.detected ? 'text-red-400' : 'text-sasriakal-500'}
        />
        <MetricCard
          icon={<Activity className="w-4 h-4" />}
          label="Samples"
          value={history.length.toString()}
          color="text-purple-400"
        />
      </div>
    </div>
  )
}

function MetricCard({ icon, label, value, color }) {
  return (
    <div className="bg-surface-800/50 rounded-xl p-3">
      <div className="flex items-center gap-1.5 text-surface-400 text-xs mb-1">
        {icon}
        {label}
      </div>
      <div className={`text-lg font-bold font-mono ${color}`}>
        {value}
      </div>
    </div>
  )
}
