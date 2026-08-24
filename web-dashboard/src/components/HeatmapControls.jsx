import React from 'react'
import { SlidersHorizontal, Eye, EyeOff } from 'lucide-react'

export default function HeatmapControls({
  heatmapEnabled,
  threshold,
  onToggleHeatmap,
  onThresholdChange,
}) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SlidersHorizontal className="w-5 h-5 text-surface-400" />
          <span className="text-sm font-semibold text-surface-200">Heatmap Controls</span>
        </div>

        <button
          onClick={() => onToggleHeatmap(!heatmapEnabled)}
          className={`
            flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition
            ${heatmapEnabled
              ? 'bg-sasriakal-500/15 border border-sasriakal-500/30 text-sasriakal-500'
              : 'bg-surface-800 border border-surface-700 text-surface-400'
            }
          `}
        >
          {heatmapEnabled ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          {heatmapEnabled ? 'Visible' : 'Hidden'}
        </button>
      </div>

      <div className="mt-4">
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs text-surface-400 uppercase tracking-wider">
            Detection Threshold
          </label>
          <span className="text-sm font-mono text-surface-300">
            {(threshold * 100).toFixed(0)}%
          </span>
        </div>

        <input
          type="range"
          min="0.1"
          max="0.99"
          step="0.01"
          value={threshold}
          onChange={(e) => onThresholdChange(parseFloat(e.target.value))}
          className="w-full h-2 rounded-full appearance-none cursor-pointer
            bg-surface-800
            [&::-webkit-slider-thumb]:appearance-none
            [&::-webkit-slider-thumb]:w-4
            [&::-webkit-slider-thumb]:h-4
            [&::-webkit-slider-thumb]:rounded-full
            [&::-webkit-slider-thumb]:bg-sasriakal-500
            [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,255,136,0.4)]
            [&::-webkit-slider-thumb]:cursor-pointer"
        />

        <div className="flex justify-between text-xs text-surface-500 mt-1">
          <span>Sensitive (10%)</span>
          <span>Strict (99%)</span>
        </div>
      </div>
    </div>
  )
}
