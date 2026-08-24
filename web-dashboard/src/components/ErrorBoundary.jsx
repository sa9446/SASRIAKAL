import React from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ errorInfo })
    console.error('[SASRIAKAL] Component error:', error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="glass-card p-6 border-red-500/30">
          <div className="flex items-center gap-3 mb-4">
            <AlertTriangle className="w-8 h-8 text-red-400" />
            <div>
              <h3 className="text-lg font-bold text-red-400">Component Error</h3>
              <p className="text-sm text-surface-400">
                {this.props.fallbackLabel || 'A component crashed'}
              </p>
            </div>
          </div>

          <div className="bg-surface-800/50 rounded-lg p-3 mb-4 max-h-32 overflow-auto">
            <code className="text-xs text-red-300 font-mono break-all">
              {this.state.error?.message || 'Unknown error'}
            </code>
          </div>

          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-surface-800 border border-surface-700 text-surface-300 hover:bg-surface-700 transition text-sm"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
