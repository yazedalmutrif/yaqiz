import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Shell } from './components/Shell'
import { LiveProvider } from './lib/live'
import { Calibration } from './pages/Calibration'
import { Log } from './pages/Log'
import { Monitor } from './pages/Monitor'
import { PlanLive } from './pages/PlanLive'
import { Report } from './pages/Report'
import { Risk } from './pages/Risk'
import { SettingsPage } from './pages/Settings'
import { Zones } from './pages/Zones'

export function App() {
  return (
    <BrowserRouter>
      <LiveProvider>
        <Routes>
          <Route element={<Shell />}>
            <Route index element={<Monitor />} />
            <Route path="plan" element={<PlanLive />} />
            <Route path="zones" element={<Zones />} />
            <Route path="calibration" element={<Calibration />} />
            <Route path="log" element={<Log />} />
            <Route path="risk" element={<Risk />} />
            <Route path="report" element={<Report />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="*" element={<Monitor />} />
          </Route>
        </Routes>
      </LiveProvider>
    </BrowserRouter>
  )
}
