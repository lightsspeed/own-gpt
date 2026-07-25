import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { RootLayout } from './routes/RootLayout'
import { LegacyChatPage } from './routes/chat'
import { UiLabPage } from './routes/ui-lab'
import { AppShellDemo } from './routes/AppShellDemo'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<RootLayout />}>
          <Route index element={<AppShellDemo />} />
          <Route path="chat" element={<LegacyChatPage />} />
          <Route path="ui-lab" element={<UiLabPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)
