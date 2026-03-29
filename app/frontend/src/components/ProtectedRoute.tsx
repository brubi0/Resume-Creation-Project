import { Navigate } from "react-router-dom";
import { useAuth } from "../auth-context";
import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  role?: "admin" | "candidate";
}

export default function ProtectedRoute({ children, role }: Props) {
  const { user } = useAuth();

  if (!user) return <Navigate to="/login" />;
  if (role && user.role !== role) {
    return <Navigate to={user.role === "admin" ? "/admin" : "/chat"} />;
  }

  return <>{children}</>;
}
