import React from 'react'
import ReactDOM from 'react-dom/client'
import { ChatLayout } from './components/chat/ChatLayout'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ChatLayout />
  </React.StrictMode>,
)
