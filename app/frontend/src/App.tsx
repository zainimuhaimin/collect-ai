import { BrowserRouter, Routes, Route } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import RootRedirect from './auth/RootRedirect';
import LoginPage from './pages/LoginPage';
import RecoveryAccessPage from './pages/RecoveryAccessPage';
import DashboardPage from './pages/DashboardPage';
import AiIntelligencePage from './pages/AiIntelligencePage';
import CustomerListPage from './pages/CustomerListPage';
import CustomerDetailPage from './pages/CustomerDetailPage';
import ContractListPage from './pages/ContractListPage';
import ContractDetailPage from './pages/ContractDetailPage';
import RestructuringApprovalPage from './pages/RestructuringApprovalPage';
import RestructuringGroupDetailPage from './pages/RestructuringGroupDetailPage';

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
          path="/customers"
          element={
            <RequireAuth>
              <CustomerListPage />
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
        <Route
          path="/contracts"
          element={
            <RequireAuth>
              <ContractListPage />
            </RequireAuth>
          }
        />
        <Route
          path="/contracts/:contractNo"
          element={
            <RequireAuth>
              <ContractDetailPage />
            </RequireAuth>
          }
        />
        <Route
          path="/restructuring-approval"
          element={
            <RequireAuth>
              <RestructuringApprovalPage />
            </RequireAuth>
          }
        />
        <Route
          path="/restructuring-approval/:id"
          element={
            <RequireAuth>
              <RestructuringGroupDetailPage />
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
      </Routes>
    </BrowserRouter>
  );
}
