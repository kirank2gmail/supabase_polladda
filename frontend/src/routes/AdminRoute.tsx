import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import { ProtectedRoute } from "./ProtectedRoute";

export function AdminRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth();

  return (
    <ProtectedRoute>
      {user?.role === "admin" ? children : <Navigate to="/leaderboard" replace />}
    </ProtectedRoute>
  );
}
