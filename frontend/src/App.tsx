import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./routes/ProtectedRoute";
import { LoginPage } from "./pages/LoginPage";
import { LeaderboardPage } from "./pages/LeaderboardPage";

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
          <Route path="/" element={<Navigate to="/leaderboard" replace />} />
          <Route path="*" element={<Navigate to="/leaderboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
