import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { RootLayout } from './routes/RootLayout'
import { LegacyChatPage } from './routes/chat'
import { UiLabPage } from './routes/ui-lab'
import { AppShellDemo } from './routes/AppShellDemo'
import { OwnPlatformLayout } from './routes/OwnPlatformLayout'
import { OwnGPTContainer } from './components/own-platform/OwnGPTContainer'
import { DashboardPage } from './components/own-platform/DashboardPage'
import { PlaceholderPage } from './components/own-platform/PlaceholderPage'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Legacy routes */}
        <Route element={<RootLayout />}>
          <Route path="legacy" element={<AppShellDemo />} />
          <Route path="legacy/chat" element={<LegacyChatPage />} />
          <Route path="legacy/ui-lab" element={<UiLabPage />} />
        </Route>

        {/* OwnGPT — standalone, no NavigationShell wrapper (has its own sidebar) */}
        <Route index element={<OwnGPTContainer />} />
        <Route path="conversation" element={<OwnGPTContainer />} />

        {/* Own Platform modules — wrapped in NavigationShell */}
        <Route element={<OwnPlatformLayout />}>
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="operations" element={<PlaceholderPage title="OwnOps" description="Operational workspace — findings, evaluation, and incident management." />} />
          <Route path="monitor" element={<PlaceholderPage title="OwnMonitor" description="Monitor recommendations, decisions, and system health." />} />
          <Route path="learn" element={<PlaceholderPage title="OwnLearn" description="Learning system — capability registry and knowledge management." />} />
          <Route path="automation" element={<PlaceholderPage title="OwnFlow" description="Automation jobs, schedules, and pipeline orchestration." />} />
          <Route path="evaluation" element={<PlaceholderPage title="Continuous Evaluation" description="View evaluation scores, trends, and drill into per-capability detail." />} />
          <Route path="findings" element={<PlaceholderPage title="Findings" description="Browse and investigate generated findings across all capabilities." />} />
          <Route path="recommendations" element={<PlaceholderPage title="Recommendations" description="Review AI-generated recommendations for platform improvements." />} />
          <Route path="experiments" element={<PlaceholderPage title="Experiments" description="Design, run, and analyze configuration experiments." />} />
          <Route path="analytics" element={<PlaceholderPage title="Analytics" description="View query patterns, retrieval effectiveness, and system usage trends." />} />
          <Route path="config/snapshots" element={<PlaceholderPage title="Configuration Snapshots" description="Browse snapshots, inspect config diffs, and manage rollbacks." />} />
          <Route path="decisions" element={<PlaceholderPage title="Decisions" description="Review and approve decisions with full lineage context." />} />
          <Route path="capabilities" element={<PlaceholderPage title="Capability Registry" description="Browse all registered platform capabilities and their maturity." />} />
          <Route path="artifacts" element={<PlaceholderPage title="Artifact Explorer" description="Browse all immutable artifacts across the platform." />} />
          <Route path="history" element={<PlaceholderPage title="Conversation History" description="Browse and search past conversations." />} />
          <Route path="settings" element={<PlaceholderPage title="Settings" description="Configure platform preferences and model parameters." />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
