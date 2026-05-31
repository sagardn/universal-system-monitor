import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import ErrorBoundary from './components/ErrorBoundary'
import Overview from './pages/Overview'
import Processes from './pages/Processes'
import GPU from './pages/GPU'
import Docker from './pages/Docker'
import Services from './pages/Services'
import Network from './pages/Network'
import Security from './pages/Security'
import Battery from './pages/Battery'
import Audio from './pages/Audio'
import Packages from './pages/Packages'
import Snapshots from './pages/Snapshots'
import Scheduler from './pages/Scheduler'
import Alerts from './pages/Alerts'
import Thermal from './pages/Thermal'
import Disks from './pages/Disks'
import SpeedTest from './pages/SpeedTest'
import Startup from './pages/Startup'
import CronJobs from './pages/CronJobs'
import Cleanup from './pages/Cleanup'

function Page({ children }) {
  return <ErrorBoundary>{children}</ErrorBoundary>
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Page><Overview /></Page>} />
        <Route path="/processes" element={<Page><Processes /></Page>} />
        <Route path="/gpu" element={<Page><GPU /></Page>} />
        <Route path="/docker" element={<Page><Docker /></Page>} />
        <Route path="/services" element={<Page><Services /></Page>} />
        <Route path="/network" element={<Page><Network /></Page>} />
        <Route path="/security" element={<Page><Security /></Page>} />
        <Route path="/battery" element={<Page><Battery /></Page>} />
        <Route path="/audio" element={<Page><Audio /></Page>} />
        <Route path="/packages" element={<Page><Packages /></Page>} />
        <Route path="/snapshots" element={<Page><Snapshots /></Page>} />
        <Route path="/scheduler" element={<Page><Scheduler /></Page>} />
        <Route path="/alerts" element={<Page><Alerts /></Page>} />
        <Route path="/thermal" element={<Page><Thermal /></Page>} />
        <Route path="/disks" element={<Page><Disks /></Page>} />
        <Route path="/speedtest" element={<Page><SpeedTest /></Page>} />
        <Route path="/startup" element={<Page><Startup /></Page>} />
        <Route path="/cronjobs" element={<Page><CronJobs /></Page>} />
        <Route path="/cleanup" element={<Page><Cleanup /></Page>} />
      </Routes>
    </Layout>
  )
}
