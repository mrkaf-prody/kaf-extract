import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import LandingPage from './pages/LandingPage'
import ApiReferencePage from './pages/ApiReferencePage'
import TutorialPage from './pages/TutorialPage'

function MeshBackground() {
  return (
    <div className="mesh-bg">
      <div className="orb orb-1" />
      <div className="orb orb-2" />
      <div className="orb orb-3" />
    </div>
  )
}

export default function App() {
  return (
    <div className="min-h-screen relative">
      <MeshBackground />
      <div className="relative z-10">
        <Navbar />
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/api-reference" element={<ApiReferencePage />} />
          <Route path="/tutorial" element={<TutorialPage />} />
        </Routes>
        <Footer />
      </div>
    </div>
  )
}
