import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './context/AuthContext.jsx'
import Layout from './components/Layout.jsx'
import Auth from './pages/Auth.jsx'
import Overview from './pages/Overview.jsx'
import DatasetExplorer from './pages/DatasetExplorer.jsx'
import DataQuality from './pages/DataQuality.jsx'
import ProcessingStudio from './pages/ProcessingStudio.jsx'
import ClusteringLab from './pages/ClusteringLab.jsx'
import ClusterIntelligence from './pages/ClusterIntelligence.jsx'
import Geographic from './pages/Geographic.jsx'
import Temporal from './pages/Temporal.jsx'
import Anomalies from './pages/Anomalies.jsx'
import SimilarEvents from './pages/SimilarEvents.jsx'
import MultiHazard from './pages/MultiHazard.jsx'
import Impact from './pages/Impact.jsx'
import LiveAlerts from './pages/LiveAlerts.jsx'
import RouteAssistance from './pages/RouteAssistance.jsx'
import Incidents from './pages/Incidents.jsx'
import Resources from './pages/Resources.jsx'
import Coordination from './pages/Coordination.jsx'
import Assistant from './pages/Assistant.jsx'
import Reports from './pages/Reports.jsx'
import Settings from './pages/Settings.jsx'

function AuthRoute({ mode }) {
  const { user, ready } = useAuth()
  if (ready && user) return <Navigate to="/" replace />
  return <Auth key={mode} initialMode={mode} />
}

export default function App() {
  return (
    <Routes>
      <Route path="/signup" element={<AuthRoute mode="register" />} />
      <Route path="/login" element={<AuthRoute mode="login" />} />
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="dataset" element={<DatasetExplorer />} />
        <Route path="quality" element={<DataQuality />} />
        <Route path="processing" element={<ProcessingStudio />} />
        <Route path="clustering" element={<ClusteringLab />} />
        <Route path="clusters" element={<ClusterIntelligence />} />
        <Route path="geography" element={<Geographic />} />
        <Route path="temporal" element={<Temporal />} />
        <Route path="anomalies" element={<Anomalies />} />
        <Route path="similar" element={<SimilarEvents />} />
        <Route path="multi-hazard" element={<MultiHazard />} />
        <Route path="impact" element={<Impact />} />
        <Route path="alerts" element={<LiveAlerts />} />
        <Route path="routes" element={<RouteAssistance />} />
        <Route path="incidents" element={<Incidents />} />
        <Route path="resources" element={<Resources />} />
        <Route path="coordination" element={<Coordination />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="reports" element={<Reports />} />
        <Route path="settings" element={<Settings />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
