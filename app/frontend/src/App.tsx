import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import RootRedirect from './auth/RootRedirect';
import LoginPage from './pages/LoginPage';
import RecoveryAccessPage from './pages/RecoveryAccessPage';
import DashboardPage from './pages/DashboardPage';
import PerformancePage from './pages/PerformancePage';
import AiIntelligencePage from './pages/AiIntelligencePage';
import CollectorWorkbenchPage from './pages/CollectorWorkbenchPage';
import CustomerDetailPage from './pages/CustomerDetailPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/access" element={<RecoveryAccessPage />} />
        <Route path="/" element={<RootRedirect />} />
        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <DashboardPage />
            </RequireAuth>
          }
        />
        <Route
          path="/performance"
          element={
            <RequireAuth>
              <PerformancePage />
            </RequireAuth>
          }
        />
        <Route
          path="/ai-intelligence"
          element={
            <RequireAuth>
              <AiIntelligencePage />
            </RequireAuth>
          }
        />
        <Route
          path="/workbench"
          element={
            <RequireAuth>
              <CollectorWorkbenchPage />
            </RequireAuth>
          }
        />
        <Route
          path="/customers/:id"
          element={
            <RequireAuth>
              <CustomerDetailPage />
            </RequireAuth>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
