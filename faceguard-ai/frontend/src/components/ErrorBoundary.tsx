import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from '@/components/ui/button'
import { translate } from '@/i18n'

/** Keeps one broken page from blanking the whole app. Details go to the console, not to the user. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error('UI error:', error, info.componentStack) }
  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="mx-auto mt-20 max-w-md space-y-3 rounded-xl border border-danger/30 bg-danger/5 p-6 text-center">
        <p className="font-medium">{translate('Something went wrong on this page.')}</p>
        <p className="text-sm text-muted">{translate('Your data is safe. Reload the page, or go back to the dashboard.')}</p>
        <div className="flex justify-center gap-2">
          <Button onClick={() => window.location.reload()}>{translate('Reload')}</Button>
          <Button variant="outline" onClick={() => { window.location.href = '/' }}>{translate('Dashboard')}</Button>
        </div>
      </div>
    )
  }
}
