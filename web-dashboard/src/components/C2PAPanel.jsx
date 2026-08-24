import React from 'react'
import { FileCheck, ShieldCheck, ShieldAlert, ExternalLink } from 'lucide-react'

export default function C2PAPanel({ c2paResult }) {
  if (!c2paResult) {
    return (
      <div className="glass-card p-5">
        <h3 className="text-sm font-semibold text-surface-300 uppercase tracking-wider mb-4 flex items-center gap-2">
          <FileCheck className="w-4 h-4" />
          C2PA Provenance
        </h3>
        <div className="text-center py-6 text-surface-500 text-sm">
          Upload a file to validate C2PA metadata
        </div>
      </div>
    )
  }

  const { has_c2pa, manifest_count, trust_chain_valid, tampering_detected, warnings } = c2paResult

  return (
    <div className="glass-card p-5">
      <h3 className="text-sm font-semibold text-surface-300 uppercase tracking-wider mb-4 flex items-center gap-2">
        <FileCheck className="w-4 h-4" />
        C2PA Provenance
      </h3>

      {/* Status Banner */}
      <div className={`
        flex items-center gap-3 p-3 rounded-xl mb-4
        ${has_c2pa && trust_chain_valid
          ? 'bg-sasriakal-500/10 border border-sasriakal-500/20'
          : has_c2pa
            ? 'bg-amber-500/10 border border-amber-500/20'
            : 'bg-surface-800/50 border border-surface-700/50'
        }
      `}>
        {has_c2pa && trust_chain_valid ? (
          <ShieldCheck className="w-6 h-6 text-sasriakal-500" />
        ) : (
          <ShieldAlert className="w-6 h-6 text-amber-400" />
        )}
        <div>
          <div className="text-sm font-semibold text-surface-200">
            {has_c2pa ? 'C2PA Data Found' : 'No C2PA Metadata'}
          </div>
          <div className="text-xs text-surface-400">
            {has_c2pa
              ? `${manifest_count} manifest(s) • Trust: ${trust_chain_valid ? 'VALID' : 'INVALID'}`
              : 'File does not contain C2PA provenance information'
            }
          </div>
        </div>
      </div>

      {/* Details */}
      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-surface-400">C2PA Present</span>
          <span className={has_c2pa ? 'text-sasriakal-500' : 'text-surface-400'}>
            {has_c2pa ? 'Yes' : 'No'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-400">Manifests</span>
          <span className="text-surface-200 font-mono">{manifest_count}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-400">Trust Chain</span>
          <span className={trust_chain_valid ? 'text-sasriakal-500' : 'text-red-400'}>
            {trust_chain_valid ? 'Valid' : 'Invalid'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-surface-400">Tampering</span>
          <span className={tampering_detected ? 'text-red-400' : 'text-sasriakal-500'}>
            {tampering_detected ? 'DETECTED' : 'None'}
          </span>
        </div>
      </div>

      {/* Active Manifest */}
      {c2paResult.active_manifest && (
        <div className="mt-4 p-3 bg-surface-800/50 rounded-lg">
          <div className="text-xs font-semibold text-surface-400 mb-2">ACTIVE MANIFEST</div>
          <div className="space-y-1 text-xs">
            <div className="flex justify-between">
              <span className="text-surface-400">Generator</span>
              <span className="text-surface-300">{c2paResult.active_manifest.claim_generator || 'Unknown'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-surface-400">Issuer</span>
              <span className="text-surface-300">{c2paResult.active_manifest.issuer || 'Unknown'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-surface-400">Created</span>
              <span className="text-surface-300 font-mono">
                {c2paResult.active_manifest.created
                  ? new Date(c2paResult.active_manifest.created).toLocaleDateString()
                  : 'N/A'}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Warnings */}
      {warnings?.length > 0 && (
        <div className="mt-3 space-y-1">
          {warnings.map((warn, i) => (
            <div key={i} className="text-xs text-amber-400 bg-amber-500/10 px-2 py-1 rounded">
              {warn}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
