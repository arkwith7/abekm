import { useMemo } from 'react';
import { useAuth } from './useAuth';
import { UserRole } from './usePermissions';

const ROLE_HIERARCHY = {
  USER: 1,
  MANAGER: 2,
  ADMIN: 3
};

export const useRole = () => {
  const { user } = useAuth();

  const currentRole = useMemo(() => {
    return user?.role || null;
  }, [user]);

  const hasRequiredRole = (requiredRole: UserRole): boolean => {
    if (!currentRole) return false;
    return ROLE_HIERARCHY[currentRole] >= ROLE_HIERARCHY[requiredRole];
  };

  const isUser = (): boolean => {
    return currentRole === 'USER';
  };

  const isManager = (): boolean => {
    return currentRole === 'MANAGER';
  };

  const isAdmin = (): boolean => {
    return currentRole === 'ADMIN';
  };

  const isManagerOrAdmin = (): boolean => {
    return hasRequiredRole('MANAGER');
  };

  const canAccessUserFeatures = (): boolean => {
    return hasRequiredRole('USER');
  };

  const canAccessManagerFeatures = (): boolean => {
    return hasRequiredRole('MANAGER');
  };

  const canAccessAdminFeatures = (): boolean => {
    return hasRequiredRole('ADMIN');
  };

  const getDefaultRoute = (): string => {
    switch (currentRole) {
      case 'USER':
        return '/user';
      case 'MANAGER':
        return '/manager';
      case 'ADMIN':
        return '/admin';
      default:
        return '/login';
    }
  };

  const getAvailableRoutes = (): string[] => {
    const routes: string[] = [];
    
    if (canAccessUserFeatures()) {
      routes.push('/user');
    }
    
    if (canAccessManagerFeatures()) {
      routes.push('/manager');
    }
    
    if (canAccessAdminFeatures()) {
      routes.push('/admin');
    }
    
    return routes;
  };

  return {
    currentRole,
    hasRequiredRole,
    isUser,
    isManager,
    isAdmin,
    isManagerOrAdmin,
    canAccessUserFeatures,
    canAccessManagerFeatures,
    canAccessAdminFeatures,
    getDefaultRoute,
    getAvailableRoutes
  };
};
