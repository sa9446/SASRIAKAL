import React, { useState } from 'react'
import { FileDown, Loader2, FileCheck } from 'lucide-react'

export default function PDFExporter({ sessionId, onExportStart, onExportComplete }) {
  const [isExporting, setIsExporting] = useState(false)
  const [exported, setExported] = useState(false)

  const handleExport = async () => {
    setIsExporting(true)
    onExportStart?.()

    try {
      const res = await fetch('http://localhost:8000/api/generate-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          tab_id: 'web-dashboard',
        }),
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const blob = await res.blob()
      const url = URL.createObjectURL(blob)

      // Trigger download
      const a = document.createElement('a')
      a.href = url
      a.download = `sasriakal-evidence-${sessionId?.slice(0, 12) || Date.now()}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      setExported(true)
      onExportComplete?.()

      // Reset exported state after 3s
      setTimeout(() => setExported(false), 3000)
    } catch (err) {
      console.error('PDF export failed:', err)
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold text-surface-300 uppercase tracking-wider mb-4 flex items-center gap-2">
        <FileDown className="w-4 h-4" />
        Evidence Export
      </h3>

      <p className="text-xs text-surface-400 mb-4">
        Generate a court-ready forensic evidence PDF with detection results,
        frame hashes, AV sync analysis, and chain of custody metadata.
      </p>

      <button
        onClick={handleExport}
        disabled={isExporting}
        className={`
          w-full flex items-center justify-center gap-2 px-4 py-3 rounded-xl
          font-semibold text-sm transition-all duration-200
          ${exported
            ? 'bg-sasriakal-500/15 border border-sasriakal-500/30 text-sasriakal-500'
            : 'bg-surface-800 border border-surface-700 text-surface-200 hover:bg-surface-700 hover:border-surface-600'
          }
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
      >
        {isExporting ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Generating...
          </>
        ) : exported ? (
          <>
            <FileCheck className="w-4 h-4" />
            Downloaded!
          </>
        ) : (
          <>
            <FileDown className="w-4 h-4" />
            Download Evidence PDF
          </>
        )}
      </button>

      <div className="mt-3 text-xs text-surface-500 text-center">
        Includes: SHA-256 hashes • Detection scores • AV sync • C2PA status • Chain of custody
      </div>
    </div>
  )
}
