import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth-context";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import AdminDashboard from "./pages/AdminDashboard";
import CandidateChat from "./pages/CandidateChat";
import DeliverablesPage from "./pages/DeliverablesPage";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-dark border-t-transparent" />
      </div>
    );
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/admin"
        element={
          <ProtectedRoute role="admin">
            <AdminDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedRoute role="candidate">
            <CandidateChat />
          </ProtectedRoute>
        }
      />
      <Route
        path="/deliverables"
        element={
          <ProtectedRoute>
            <DeliverablesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="*"
        element={
          <Navigate
            to={
              user ? (user.role === "admin" ? "/admin" : "/chat") : "/login"
            }
          />
        }
      />
    </Routes>
  );
}
