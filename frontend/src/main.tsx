import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { RootLayout } from './routes/RootLayout'
import { OwnPlatformLayout } from './routes/OwnPlatformLayout'
import './index.css'

const LegacyChatPage = lazy(() => import('./routes/chat'))
const UiLabPage = lazy(() => import('./routes/ui-lab'))
const AppShellDemo = lazy(() => import('./routes/AppShellDemo'))
const OwnGPTContainer = lazy(() => import('./components/own-platform/OwnGPTContainer'))
const DashboardPage = lazy(() => import('./components/own-platform/DashboardPage'))
const OwnAnalyticsPage = lazy(() => import('./components/own-platform/OwnAnalyticsPage'))
const OwnExperimentsPage = lazy(() => import('./components/own-platform/OwnExperimentsPage'))
const KnowledgeBasePage = lazy(() => import('./components/documents/KnowledgeBasePage'))
const OwnLearnQualityPage = lazy(() => import('./components/own-platform/OwnLearnQualityPage'))
const OwnCapabilitiesPage = lazy(() => import('./components/own-platform/OwnCapabilitiesPage'))
const OwnFlowPage = lazy(() => import('./components/own-platform/OwnFlowPage'))
const OwnFindingsPage = lazy(() => import('./components/own-platform/OwnFindingsPage'))
const OwnRecommendationsPage = lazy(() => import('./components/own-platform/OwnRecommendationsPage'))
const OwnDecisionsPage = lazy(() => import('./components/own-platform/OwnDecisionsPage'))
const OwnArtifactsPage = lazy(() => import('./components/own-platform/OwnArtifactsPage'))
const OwnConfigPage = lazy(() => import('./components/own-platform/OwnConfigPage'))
const OwnMemoriesPage = lazy(() => import('./components/own-platform/OwnMemoriesPage'))
const PlaceholderPage = lazy(() => import('./components/own-platform/PlaceholderPage'))

function RouteSuspense({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-screen bg-background">
        <div className="w-6 h-6 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      </div>
    }>
      {children}
    </Suspense>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<RootLayout />}>
          <Route path="legacy" element={<RouteSuspense><AppShellDemo /></RouteSuspense>} />
          <Route path="legacy/chat" element={<RouteSuspense><LegacyChatPage /></RouteSuspense>} />
          <Route path="legacy/ui-lab" element={<RouteSuspense><UiLabPage /></RouteSuspense>} />
        </Route>

        <Route index element={<RouteSuspense><OwnGPTContainer /></RouteSuspense>} />
        <Route path="conversation" element={<RouteSuspense><OwnGPTContainer /></RouteSuspense>} />

        <Route element={<OwnPlatformLayout />}>
          <Route path="dashboard" element={<RouteSuspense><DashboardPage /></RouteSuspense>} />
          <Route path="operations" element={<RouteSuspense><PlaceholderPage title="OwnOps" description="Operational workspace — findings, evaluation, and incident management." /></RouteSuspense>} />
          <Route path="monitor" element={<RouteSuspense><PlaceholderPage title="OwnMonitor" description="Monitor recommendations, decisions, and system health." /></RouteSuspense>} />
          <Route path="learn" element={<RouteSuspense><KnowledgeBasePage /></RouteSuspense>} />
          <Route path="learn/quality" element={<RouteSuspense><OwnLearnQualityPage /></RouteSuspense>} />
          <Route path="automation" element={<RouteSuspense><OwnFlowPage /></RouteSuspense>} />
          <Route path="evaluation" element={<RouteSuspense><PlaceholderPage title="Continuous Evaluation" description="View evaluation scores, trends, and drill into per-capability detail." /></RouteSuspense>} />
          <Route path="findings" element={<RouteSuspense><OwnFindingsPage /></RouteSuspense>} />
          <Route path="recommendations" element={<RouteSuspense><OwnRecommendationsPage /></RouteSuspense>} />
          <Route path="experiments" element={<RouteSuspense><OwnExperimentsPage /></RouteSuspense>} />
          <Route path="analytics" element={<RouteSuspense><OwnAnalyticsPage /></RouteSuspense>} />
          <Route path="config/snapshots" element={<RouteSuspense><OwnConfigPage /></RouteSuspense>} />
          <Route path="decisions" element={<RouteSuspense><OwnDecisionsPage /></RouteSuspense>} />
          <Route path="capabilities" element={<RouteSuspense><OwnCapabilitiesPage /></RouteSuspense>} />
          <Route path="artifacts" element={<RouteSuspense><OwnArtifactsPage /></RouteSuspense>} />
          <Route path="history" element={<RouteSuspense><PlaceholderPage title="Conversation History" description="Browse and search past conversations." /></RouteSuspense>} />
          <Route path="memories" element={<RouteSuspense><OwnMemoriesPage /></RouteSuspense>} />
          <Route path="settings" element={<RouteSuspense><PlaceholderPage title="Settings" description="Configure platform preferences and model parameters." /></RouteSuspense>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
