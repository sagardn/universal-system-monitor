import { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useWs } from '../hooks/useWebSocket'

const NAV = [
  { to: '/',          icon: '📊', label: 'Overview',   key: '1' },
  { to: '/processes', icon: '⚙️', label: 'Processes',  key: '2' },
  { to: '/gpu',       icon: '🎮', label: 'GPU',        key: '3' },
  { to: '/thermal',   icon: '🌡️', label: 'Thermal',    key: '0' },
  { to: '/docker',    icon: '🐳', label: 'Docker',     key: '4' },
  { to: '/services',  icon: '🗄️', label: 'Services',   key: '5' },
  { divider: true },
  { to: '/network',   icon: '🌐', label: 'Network',    key: '6' },
  { to: '/security',  icon: '🛡️', label: 'Security',   key: '7' },
  { to: '/battery',   icon: '🔋', label: 'Battery',    key: '8' },
  { to: '/audio',     icon: '🔊', label: 'Audio',      key: '9' },
  { to: '/disks',     icon: '💽', label: 'Disk Health' },
  { divider: true },
  { to: '/packages',  icon: '📦', label: 'Packages' },
  { to: '/snapshots', icon: '📸', label: 'Snapshots' },
  { to: '/scheduler', icon: '🧠', label: 'Scheduler' },
  { to: '/alerts',    icon: '🔔', label: 'Alerts' },
  { divider: true },
  { to: '/speedtest', icon: '🚀', label: 'Speed Test' },
  { to: '/startup',   icon: '⚡', label: 'Startup Apps' },
  { to: '/cronjobs',  icon: '⏰', label: 'Cron Jobs' },
  { to: '/cleanup',   icon: '🧹', label: 'Cleanup' },
]

const TITLES = {
  '/': 'Overview', '/processes': 'Processes', '/gpu': 'GPU', '/thermal': 'Thermal',
  '/docker': 'Docker', '/services': 'Services', '/network': 'Network',
  '/security': 'Security', '/battery': 'Battery & Power', '/audio': 'Audio',
  '/disks': 'Disk Health', '/packages': 'Packages', '/snapshots': 'Snapshots', '/scheduler': 'Scheduler',
  '/alerts': 'Alerts', '/speedtest': 'Speed Test', '/startup': 'Startup Apps', '/cronjobs': 'Cron Jobs',
  '/cleanup': 'System Cleanup',
}

export default function Layout({ children }) {
  const [collapsed, setCollapsed] = useState(false)
  const [clock, setClock] = useState('')
  const [theme, setTheme] = useState(() => localStorage.getItem('usm-theme') || 'dark')
  const location = useLocation()
  const ws = useWs()
  const title = TITLES[location.pathname] || 'USM'

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('usm-theme', theme)
  }, [theme])

  const toggleTheme = () => setTheme(t => t === 'dark' ? 'light' : 'dark')

  useEffect(() => {
    const t = setInterval(() => setClock(new Date().toLocaleTimeString(undefined, {
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    })), 1000)
    return () => clearInterval(t)
  }, [])

  // Keyboard nav
  useEffect(() => {
    function onKey(e) {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return
      const pages = ['/', '/processes', '/gpu', '/docker', '/services', '/network', '/security', '/battery', '/audio']
      if (e.key >= '1' && e.key <= '9' && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        const idx = parseInt(e.key) - 1
        if (idx < pages.length) window.location.hash = pages[idx]
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <>
      {/* Sidebar */}
      <aside className={`fixed top-0 left-0 h-screen bg-glass-bg backdrop-blur-[20px] border-r border-glass-border flex flex-col z-50 transition-all duration-300 overflow-hidden ${collapsed ? 'w-[68px]' : 'w-[230px]'}`}>
        {/* Logo */}
        <div className="flex items-center justify-between p-4 min-h-[56px]">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🖥️</span>
            <span className={`text-base font-bold text-primary whitespace-nowrap transition-opacity duration-200 ${collapsed ? 'opacity-0 w-0 overflow-hidden' : ''}`}>
              USM
            </span>
          </div>
          <button onClick={() => setCollapsed(!collapsed)}
            className="text-txt-muted hover:text-txt p-1 rounded-sm transition-colors cursor-pointer bg-transparent border-none">
            {collapsed ? '▶' : '◀'}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto overflow-x-hidden p-2 flex flex-col gap-0.5">
          {NAV.map((item, i) =>
            item.divider ? (
              <div key={i} className="h-px bg-border mx-3 my-2" />
            ) : (
              <NavLink key={item.to} to={item.to}
                className={({ isActive }) =>
                  `flex items-center gap-3 py-2 px-3 rounded-sm min-h-[38px] whitespace-nowrap no-underline transition-all duration-150 relative
                   ${isActive ? 'bg-primary-muted text-primary' : 'text-txt-secondary hover:bg-bg-hover hover:text-txt'}`
                }>
                {({ isActive }) => (
                  <>
                    {isActive && <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 bg-primary rounded-r" />}
                    <span className="text-base shrink-0">{item.icon}</span>
                    <span className={`flex-1 text-[0.8125rem] font-medium transition-opacity duration-200 ${collapsed ? 'opacity-0 w-0 overflow-hidden' : ''}`}>
                      {item.label}
                    </span>
                    {!collapsed && item.key && (
                      <kbd className="text-[0.625rem] text-txt-muted bg-bg-surface border border-border rounded px-1 min-w-[20px] h-5 inline-flex items-center justify-center">
                        {item.key}
                      </kbd>
                    )}
                  </>
                )}
              </NavLink>
            )
          )}
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-border flex items-center gap-2">
          <div className="flex items-center gap-2 text-[0.6875rem] text-txt-muted">
            <span className={`w-2 h-2 rounded-full ${ws?.status === 'connected' ? 'bg-success animate-pulse-glow' : ws?.status === 'reconnecting' ? 'bg-warning animate-pulse-glow' : 'bg-danger'}`} />
            <span className={`transition-opacity duration-200 ${collapsed ? 'opacity-0 w-0 overflow-hidden' : ''}`}>
              {ws?.status === 'connected' ? 'Connected' : ws?.status === 'reconnecting' ? 'Reconnecting…' : 'Offline'}
            </span>
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className={`flex-1 h-screen flex flex-col transition-all duration-300 overflow-hidden ${collapsed ? 'ml-[68px]' : 'ml-[230px]'}`}>
        {/* Header */}
        <header className="flex items-center justify-between px-6 min-h-[56px] bg-glass-bg backdrop-blur-[20px] border-b border-glass-border z-40">
          <h1 className="text-xl font-bold">{title}</h1>
          <div className="flex items-center gap-4">
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-sm transition-all duration-200 cursor-pointer bg-transparent border-none text-txt-muted hover:text-txt hover:bg-bg-hover text-base"
              title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            >
              {theme === 'dark' ? '☀️' : '🌙'}
            </button>
            <span className="text-xs text-txt-muted tabular-nums font-medium">{clock}</span>
          </div>
        </header>

        {/* Page */}
        <div className="flex-1 overflow-y-auto p-6">
          <div key={location.pathname} className="animate-slide-up">
            {children}
          </div>
        </div>
      </main>
    </>
  )
}
