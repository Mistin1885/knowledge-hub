import { Navigate, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import TokensPage from './pages/TokensPage';
import RootRedirect from './pages/RootRedirect';
import WorkspaceLayout from './components/layout/WorkspaceLayout';
import WorkspaceHome from './pages/WorkspaceHome';
import EditorPage from './pages/EditorPage';
import GraphPage from './pages/GraphPage';
import SearchPage from './pages/SearchPage';
import TagPage from './pages/TagPage';
import WorkspaceSettingsPage from './pages/WorkspaceSettingsPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/settings/tokens" element={<TokensPage />} />
      <Route path="/w/:slug" element={<WorkspaceLayout />}>
        <Route index element={<WorkspaceHome />} />
        <Route path="p/:pageId" element={<EditorPage />} />
        <Route path="graph" element={<GraphPage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="tags/:tag" element={<TagPage />} />
        <Route path="settings" element={<WorkspaceSettingsPage />} />
      </Route>
      <Route path="/" element={<RootRedirect />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
