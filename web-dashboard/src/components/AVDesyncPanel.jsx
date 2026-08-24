import React from 'react'
import { AudioLines, AlertTriangle, CheckCircle } from 'lucide-react'

export default function AVDesyncPanel({ currentResult }) {
  const av = currentResult?.av_desync
  const score = av?.score || 0
  const offset = av?.offset_ms || 0
  const flaggedSegments = av?.flagged_segments || []

  const scorePct = (score * 100).toFixed(1)
  const isDesynced = score > 0.5

  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold text-surface-300 uppercase tracking-wider mb-4 flex items-center gap-2">
        <AudioLines className="w-4 h-4" />
        AV Sync Analysis
      </h3>

      <div className="flex items-center gap-3 mb-4">
        {isDesynced ? (
          <AlertTriangle className="w-8 h-8 text-red-400" />
        ) : (
          <CheckCircle className="w-8 h-8 text-sasriakal-500" />
        )}
        <div>
          <div className={`text-2xl font-bold font-mono ${isDesynced ? 'text-red-400' : 'text-sasriakal-500'}`}>
            {scorePct}%
          </div>
          <div className="text-xs text-surface-400">
            {isDesynced ? 'DESYNCHRONIZED' : 'Synchronized'}
          </div>
        </div>
      </div>

      {/* Sync Bar */}
      <div className="h-3 bg-surface-800 rounded-full overflow-hidden mb-4">
        <div
          className={`h-full rounded-full transition-all duration-500 ${
            score > 0.5
              ? 'bg-gradient-to-r from-red-500 to-red-600'
              : score > 0.25
                ? 'bg-gradient-to-r from-amber-500 to-amber-600'
                : 'bg-gradient-to-r from-sasriakal-500 to-sasriakal-600'
          }`}
          style={{ width: `${Math.min(100, scorePct)}%` }}
        />
      </div>

      {/* Metrics */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-surface-400">Temporal Offset</span>
          <span className="text-surface-200 font-mono">{offset.toFixed(1)} ms</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-400">Phonemes Detected</span>
          <span className="text-surface-200 font-mono">{av?.phonemes?.length || 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-400">Visemes Detected</span>
          <span className="text-surface-200 font-mono">{av?.visemes?.length || 0}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-400">Flagged Segments</span>
          <span className={`font-mono ${flaggedSegments.length > 0 ? 'text-red-400' : 'text-sasriakal-500'}`}>
            {flaggedSegments.length}
          </span>
        </div>
      </div>

      {/* Flagged Segments */}
      {flaggedSegments.length > 0 && (
        <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 rounded-lg">
          <div className="text-xs font-semibold text-red-400 mb-2">⚠ FLAGGED SEGMENTS</div>
          <div className="space-y-1 max-h-32 overflow-y-auto">
            {flaggedSegments.slice(0, 5).map((seg, i) => (
              <div key={i} className="flex justify-between text-xs">
                <span className="text-surface-400">
                  {(seg.start_ms / 1000).toFixed(2)}s — {(seg.end_ms / 1000).toFixed(2)}s
                </span>
                <span className="text-red-400 font-mono">
                  {(seg.desync_score * 100).toFixed(1)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
