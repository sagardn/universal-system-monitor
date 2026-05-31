import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null, info: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
    this.setState({ info })
  }

  render() {
    if (this.state.error) {
      return (
        <div className="glass p-6 m-4">
          <h3 className="text-danger font-bold text-lg mb-2">⚠️ Page Error</h3>
          <div className="text-sm text-danger font-semibold mb-2 p-2 bg-danger-muted rounded-md">
            {this.state.error?.message || this.state.error?.toString()}
          </div>
          <pre className="text-xs text-txt-muted bg-bg-surface p-3 rounded-md overflow-auto max-h-[200px]">
            {this.state.error?.stack}
          </pre>
          <button
            onClick={() => this.setState({ error: null, info: null })}
            className="mt-3 px-4 py-2 text-xs font-semibold rounded-sm bg-primary text-white border-none cursor-pointer hover:brightness-110 transition-all"
          >
            🔄 Retry
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
