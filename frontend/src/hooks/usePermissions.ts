import { useMemo } from 'react';
import { useAuth } from './useAuth';

export type UserRole = 'USER' | 'MANAGER' | 'ADMIN';
export type Permission = string;

const PERMISSIONS = {
  // 일반 사용자 권한
  USER: [
    'document:read',
    'document:upload',
    'document:comment',
    'search:basic',
    'chat:ask',
    'profile:update'
  ],
  
  // 지식관리자 권한 (사용자 권한 + 관리 권한)
  MANAGER: [
    'document:read',
    'document:upload',
    'document:comment',
    'search:basic',
    'chat:ask',
    'profile:update',
    'container:manage',
    'permission:approve',
    'quality:review',
    'user:support',
    'analytics:view'
  ],
  
  // 시스템관리자 권한 (모든 권한)
  ADMIN: [
    'document:read',
    'document:upload',
    'document:comment',
    'search:basic',
    'chat:ask',
    'profile:update',
    'container:manage',
    'permission:approve',
    'quality:review',
    'user:support',
    'analytics:view',
    'system:monitor',
    'user:manage',
    'security:configure',
    'audit:view',
    'backup:manage'
  ]
};

export const usePermissions = () => {
  const { user } = useAuth();

  const permissions = useMemo(() => {
    if (!user) return [];
    return PERMISSIONS[user.role] || [];
  }, [user]);

  const hasPermission = (permission: Permission): boolean => {
    return permissions.includes(permission);
  };

  const hasAnyPermission = (requiredPermissions: Permission[]): boolean => {
    return requiredPermissions.some(permission => hasPermission(permission));
  };

  const hasAllPermissions = (requiredPermissions: Permission[]): boolean => {
    return requiredPermissions.every(permission => hasPermission(permission));
  };

  const canAccess = (resource: string, action: string): boolean => {
    const permission = `${resource}:${action}`;
    return hasPermission(permission);
  };

  return {
    permissions,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    canAccess
  };
};
