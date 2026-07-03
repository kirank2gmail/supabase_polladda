import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { AdminRoute } from "./routes/AdminRoute";
import { LoginPage } from "./pages/LoginPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";
import AdminPage from "./AdminPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/leaderboard"
            element={
              <ProtectedRoute>
                <LeaderboardPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/admin"
            element={
              <AdminRoute>
                <AdminPage />
              </AdminRoute>
            }
          />
          <Route path="/" element={<Navigate to="/leaderboard" replace />} />
          <Route path="*" element={<Navigate to="/leaderboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
