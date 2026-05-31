import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { WebSocketProvider } from './hooks/useWebSocket'
import { ToastProvider } from './components/Toast'
import './index.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <HashRouter>
      <WebSocketProvider>
        <ToastProvider>
          <App />
        </ToastProvider>
      </WebSocketProvider>
    </HashRouter>
  </StrictMode>
)
