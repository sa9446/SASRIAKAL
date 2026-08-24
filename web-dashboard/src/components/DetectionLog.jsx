import React from 'react'
import { ScrollText } from 'lucide-react'

const levelStyles = {
  info: 'text-surface-400',
  success: 'text-sasriakal-500',
  warning: 'text-amber-400',
  danger: 'text-red-400',
  error: 'text-red-500',
}

const levelIcons = {
  info: '•',
  success: '✓',
  warning: '⚠',
  danger: '⚠',
  error: '✗',
}

export default function DetectionLog({ logs }) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-surface-300 uppercase tracking-wider flex items-center gap-2">
          <ScrollText className="w-4 h-4" />
          Detection Log
        </h3>
        <span className="text-xs text-surface-500">{logs.length} entries</span>
      </div>

      <div className="max-h-64 overflow-y-auto space-y-1 font-mono text-xs">
        {logs.length === 0 ? (
          <div className="text-surface-500 text-center py-4">
            No log entries yet
          </div>
        ) : (
          logs.map((entry) => (
            <div key={entry.id} className={`flex gap-2 ${levelStyles[entry.level] || 'text-surface-400'}`}>
              <span className="text-surface-600 w-16 shrink-0">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
              <span className="w-3 shrink-0 text-center">
                {levelIcons[entry.level] || '•'}
              </span>
              <span className="break-all">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
