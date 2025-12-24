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
// 新增媒体模块
import AudioLibraryPage from './pages/AudioLibrary/AudioLibraryPage'
import VideoLibraryPage from './pages/VideoLibrary/VideoLibraryPage'
import TextLibraryPage from './pages/TextLibrary/TextLibraryPage'
import VideoStudioPage from './pages/VideoStudio/VideoStudioPage'
import AudioStudioPage from './pages/AudioStudio/AudioStudioPage'
// 登录页
import LoginPage from './pages/Login/LoginPage'
import { useAuthStore } from './stores/authStore'

// 路由保护组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore()
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  
  return <>{children}</>
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* 登录页 - 不需要认证 */}
        <Route path="/login" element={<LoginPage />} />
        
        {/* 需要认证的路由 */}
        <Route path="/" element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        }>
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
            {/* 新增媒体模块 */}
            <Route path="audio-library" element={<AudioLibraryPage />} />
            <Route path="video-library" element={<VideoLibraryPage />} />
            <Route path="text-library" element={<TextLibraryPage />} />
            <Route path="video-studio" element={<VideoStudioPage />} />
            <Route path="audio-studio" element={<AudioStudioPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
