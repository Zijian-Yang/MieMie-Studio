import { Suspense, lazy } from 'react'
import { Spin } from 'antd'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import { useAuthStore } from './stores/authStore'
import ErrorBoundary from './components/ErrorBoundary'
import AdminRoute from './components/AdminRoute'

const ProjectsPage = lazy(() => import('./pages/Projects/ProjectsPage'))
const SettingsPage = lazy(() => import('./pages/Settings/SettingsPage'))
const ScriptPage = lazy(() => import('./pages/Script/ScriptPage'))
const StylesPage = lazy(() => import('./pages/Styles/StylesPage'))
const CharactersPage = lazy(() => import('./pages/Characters/CharactersPage'))
const ScenesPage = lazy(() => import('./pages/Scenes/ScenesPage'))
const PropsPage = lazy(() => import('./pages/Props/PropsPage'))
const FramesPage = lazy(() => import('./pages/Frames/FramesPage'))
const VideosPage = lazy(() => import('./pages/Videos/VideosPage'))
const GalleryPage = lazy(() => import('./pages/Gallery/GalleryPage'))
const StudioPage = lazy(() => import('./pages/Studio/StudioPage'))
const AudioLibraryPage = lazy(() => import('./pages/AudioLibrary/AudioLibraryPage'))
const VideoLibraryPage = lazy(() => import('./pages/VideoLibrary/VideoLibraryPage'))
const TextLibraryPage = lazy(() => import('./pages/TextLibrary/TextLibraryPage'))
const VideoStudioPage = lazy(() => import('./pages/VideoStudio/VideoStudioPage'))
const AudioStudioPage = lazy(() => import('./pages/AudioStudio/AudioStudioPage'))
const ImageBenchmarkPage = lazy(() => import('./pages/ImageBenchmark/ImageBenchmarkPage'))
const ImageBenchmarkDatasetsPage = lazy(() => import('./pages/ImageBenchmarkDatasets/ImageBenchmarkDatasetsPage'))
const ImageBenchmarkSharePage = lazy(() => import('./pages/ImageBenchmarkShare/ImageBenchmarkSharePage'))
const VideoBenchmarkPage = lazy(() => import('./pages/VideoBenchmark/VideoBenchmarkPage'))
const VideoBenchmarkDatasetsPage = lazy(() => import('./pages/VideoBenchmarkDatasets/VideoBenchmarkDatasetsPage'))
const LoginPage = lazy(() => import('./pages/Login/LoginPage'))
const AdminUsersPage = lazy(() => import('./pages/Admin/AdminUsersPage'))
const AdminAuditPage = lazy(() => import('./pages/Admin/AdminAuditPage'))
const AdminOverviewPage = lazy(() => import('./pages/Admin/AdminOverviewPage'))
const AdminBackupsPage = lazy(() => import('./pages/Admin/AdminBackupsPage'))
const AdminAlertsPage = lazy(() => import('./pages/Admin/AdminAlertsPage'))
const AdminLayout = lazy(() => import('./pages/Admin/AdminLayout'))

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
    <ErrorBoundary>
      <BrowserRouter>
        <Suspense fallback={
          <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Spin size="large" />
          </div>
        }>
          <Routes>
            {/* 登录页 - 不需要认证 */}
            <Route path="/login" element={<LoginPage />} />
            <Route path="/image-benchmark/share/:token" element={<ImageBenchmarkSharePage />} />

            {/* 需要认证的路由 */}
            <Route path="/" element={
              <ProtectedRoute>
                <MainLayout />
              </ProtectedRoute>
            }>
              <Route index element={<Navigate to="/projects" replace />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
                <Route index element={<Navigate to="/admin/overview" replace />} />
                <Route path="overview" element={<AdminOverviewPage />} />
                <Route path="users" element={<AdminUsersPage />} />
                <Route path="backups" element={<AdminBackupsPage />} />
                <Route path="alerts" element={<AdminAlertsPage />} />
                <Route path="audit" element={<AdminAuditPage />} />
              </Route>
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
                <Route path="audio-library" element={<AudioLibraryPage />} />
                <Route path="video-library" element={<VideoLibraryPage />} />
                <Route path="text-library" element={<TextLibraryPage />} />
                <Route path="video-studio" element={<VideoStudioPage />} />
                <Route path="audio-studio" element={<AudioStudioPage />} />
                <Route path="image-benchmark-datasets" element={<ImageBenchmarkDatasetsPage />} />
                <Route path="image-benchmark" element={<ImageBenchmarkPage />} />
                <Route path="video-benchmark-datasets" element={<VideoBenchmarkDatasetsPage />} />
                <Route path="video-benchmark" element={<VideoBenchmarkPage />} />
              </Route>
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ErrorBoundary>
  )
}

export default App
