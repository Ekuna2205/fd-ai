import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { GuestRoute, ProtectedRoute } from '@/components/ProtectedRoute'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { AuthProvider } from '@/hooks/useAuth'
import { ThemeProvider, useTheme } from '@/hooks/useTheme'
import { LanguageProvider, useT } from '@/i18n'
import AppLayout from '@/layouts/AppLayout'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import NotFoundPage from '@/pages/NotFoundPage'
import RegisterPage from '@/pages/RegisterPage'

const AdminPage = lazy(() => import('@/pages/AdminPage'))
const ChallengePage = lazy(() => import('@/pages/ChallengePage'))
const CollectPage = lazy(() => import('@/pages/CollectPage'))
const DatasetDetailPage = lazy(() => import('@/pages/DatasetDetailPage'))
const DatasetsPage = lazy(() => import('@/pages/DatasetsPage'))
const ForgotPasswordPage = lazy(() => import('@/pages/ForgotPasswordPage'))
const HistoryPage = lazy(() => import('@/pages/HistoryPage'))
const ModelsPage = lazy(() => import('@/pages/ModelsPage'))
const ReportsPage = lazy(() => import('@/pages/ReportsPage'))
const ResetPasswordPage = lazy(() => import('@/pages/ResetPasswordPage'))
const SettingsPage = lazy(() => import('@/pages/SettingsPage'))
const UploadPage = lazy(() => import('@/pages/UploadPage'))
const VerificationDetailPage = lazy(() => import('@/pages/VerificationDetailPage'))
const VerifyPage = lazy(() => import('@/pages/VerifyPage'))

function PageLoader() {
  const { t } = useT()
  return <div className="grid h-64 place-items-center" role="status" aria-label={t('Loading page')}><div className="size-6 animate-spin rounded-full border-2 border-border border-t-primary" /></div>
}

const queryClient = new QueryClient({ defaultOptions: { queries: { refetchOnWindowFocus: false } } })

function ThemedToaster() {
  const { theme } = useTheme()
  return <Toaster theme={theme} position="bottom-right" />
}

export default function App() {
  return (
    <LanguageProvider>
    <ThemeProvider>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <ErrorBoundary>
          <Suspense fallback={<PageLoader />}>
          <Routes>
            <Route element={<GuestRoute />}>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />
            </Route>
            <Route path="/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/reset-password" element={<ResetPasswordPage />} />
            <Route path="/collect/:token" element={<CollectPage />} />
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="/verify" element={<VerifyPage />} />
                <Route path="/uploads" element={<UploadPage />} />
                <Route path="/verifications/:id" element={<VerificationDetailPage />} />
                <Route path="/challenge" element={<ChallengePage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/models" element={<ModelsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                <Route element={<ProtectedRoute roles={['researcher', 'administrator']} />}>
                  <Route path="/datasets" element={<DatasetsPage />} />
                  <Route path="/datasets/:id" element={<DatasetDetailPage />} />
                </Route>
                <Route element={<ProtectedRoute roles={['administrator']} />}><Route path="/admin" element={<AdminPage />} /></Route>
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Route>
          </Routes>
          </Suspense>
          </ErrorBoundary>
        </AuthProvider>
      </BrowserRouter>
      <ThemedToaster />
    </QueryClientProvider>
    </ThemeProvider>
    </LanguageProvider>
  )
}
