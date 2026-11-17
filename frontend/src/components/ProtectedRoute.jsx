import { Navigate, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { PageLoader } from "./ui";

export function ProtectedRoute({ roles }) {
  const { isAuthenticated, loading, user, homePath } = useAuth();
  const location = useLocation();

  if (loading) return <PageLoader />;
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to={homePath} replace />;
  return <Outlet />;
}

export function PublicOnlyRoute() {
  const { isAuthenticated, loading, homePath } = useAuth();
  if (loading) return <PageLoader />;
  if (isAuthenticated) return <Navigate to={homePath} replace />;
  return <Outlet />;
}
