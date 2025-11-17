import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { UserRole } from '../../hooks/usePermissions';
import { useRole } from '../../hooks/useRole';

interface ProtectedRouteProps {
  children?: React.ReactNode;  // children을 선택적으로 변경
  requiredRole?: UserRole;
  fallbackPath?: string;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({
  children,
  requiredRole,
  fallbackPath = '/login'
}) => {
  const { isAuthenticated, isLoading } = useAuth();
  const { hasRequiredRole } = useRole();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (requiredRole && !hasRequiredRole(requiredRole)) {
    return <Navigate to="/unauthorized" replace />;
  }

  if (children) {
    return <>{children}</>;
  }

  return <Outlet />;
};
