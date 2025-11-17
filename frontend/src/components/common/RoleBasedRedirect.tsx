import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';

export const RoleBasedRedirect: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">로딩 중...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // 역할별 리다이렉트
  switch (user?.role) {
    case 'ADMIN':
      return <Navigate to="/admin" replace />;
    case 'MANAGER':
      return <Navigate to="/manager" replace />;
    case 'USER':
    default:
      return <Navigate to="/user" replace />;
  }
};

export default RoleBasedRedirect;
