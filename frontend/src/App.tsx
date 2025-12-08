import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import ProjectsPage from './pages/Projects/ProjectsPage'
import SettingsPage from './pages/Settings/SettingsPage'
import ScriptPage from './pages/Script/ScriptPage'
import StylesPage from './pages/Styles/StylesPage'
import CharactersPage from './pages/Characters/CharactersPage'
import ScenesPage from './pages/Scenes/ScenesPage'
import PropsPage from './pages/Props/PropsPage'
import FramesPage from './pages/Frames/FramesPage'
import VideosPage from './pages/Videos/VideosPage'
import GalleryPage from './pages/Gallery/GalleryPage'
import StudioPage from './pages/Studio/StudioPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainLayout />}>
          <Route index element={<Navigate to="/projects" replace />} />
          <Route path="projects" element={<ProjectsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="project/:projectId">
            <Route path="script" element={<ScriptPage />} />
            <Route path="styles" element={<StylesPage />} />
            <Route path="characters" element={<CharactersPage />} />
            <Route path="scenes" element={<ScenesPage />} />
            <Route path="props" element={<PropsPage />} />
            <Route path="frames" element={<FramesPage />} />
            <Route path="videos" element={<VideosPage />} />
            <Route path="gallery" element={<GalleryPage />} />
            <Route path="studio" element={<StudioPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
