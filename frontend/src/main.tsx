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
const KnowledgeBasePage = lazy(() => import('./components/documents/KnowledgeBasePage'))
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
          <Route path="automation" element={<RouteSuspense><PlaceholderPage title="OwnFlow" description="Automation jobs, schedules, and pipeline orchestration." /></RouteSuspense>} />
          <Route path="evaluation" element={<RouteSuspense><PlaceholderPage title="Continuous Evaluation" description="View evaluation scores, trends, and drill into per-capability detail." /></RouteSuspense>} />
          <Route path="findings" element={<RouteSuspense><PlaceholderPage title="Findings" description="Browse and investigate generated findings across all capabilities." /></RouteSuspense>} />
          <Route path="recommendations" element={<RouteSuspense><PlaceholderPage title="Recommendations" description="Review AI-generated recommendations for platform improvements." /></RouteSuspense>} />
          <Route path="experiments" element={<RouteSuspense><PlaceholderPage title="Experiments" description="Design, run, and analyze configuration experiments." /></RouteSuspense>} />
          <Route path="analytics" element={<RouteSuspense><PlaceholderPage title="Analytics" description="View query patterns, retrieval effectiveness, and system usage trends." /></RouteSuspense>} />
          <Route path="config/snapshots" element={<RouteSuspense><PlaceholderPage title="Configuration Snapshots" description="Browse snapshots, inspect config diffs, and manage rollbacks." /></RouteSuspense>} />
          <Route path="decisions" element={<RouteSuspense><PlaceholderPage title="Decisions" description="Review and approve decisions with full lineage context." /></RouteSuspense>} />
          <Route path="capabilities" element={<RouteSuspense><PlaceholderPage title="Capability Registry" description="Browse all registered platform capabilities and their maturity." /></RouteSuspense>} />
          <Route path="artifacts" element={<RouteSuspense><PlaceholderPage title="Artifact Explorer" description="Browse all immutable artifacts across the platform." /></RouteSuspense>} />
          <Route path="history" element={<RouteSuspense><PlaceholderPage title="Conversation History" description="Browse and search past conversations." /></RouteSuspense>} />
          <Route path="settings" element={<RouteSuspense><PlaceholderPage title="Settings" description="Configure platform preferences and model parameters." /></RouteSuspense>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
