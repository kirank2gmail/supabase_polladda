import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import { Navbar } from "../components/Navbar";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { user, loading, mustChangePassword } = useAuth();

  if (loading) {
    return <div className="p-8 text-center text-gray-500">Loading…</div>;
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (mustChangePassword) {
    return <Navigate to="/login" replace />;
  }
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      {children}
    </div>
  );
}
