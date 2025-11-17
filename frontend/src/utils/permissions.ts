import { UserRole } from '../hooks/usePermissions';

export const ROLE_HIERARCHY = {
  USER: 1,
  MANAGER: 2,
  ADMIN: 3
};

export const hasRequiredRole = (userRole: UserRole, requiredRole: UserRole): boolean => {
  return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[requiredRole];
};

export const PERMISSIONS = {
  // 일반 사용자 권한
  USER: [
    'document:read',
    'document:upload',
    'document:comment',
    'search:basic',
    'chat:ask',
    'profile:update'
  ],
  
  // 지식관리자 권한
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
  
  // 시스템관리자 권한
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

export const hasPermission = (userRole: UserRole, permission: string): boolean => {
  return PERMISSIONS[userRole]?.includes(permission) || false;
};

export const getUserPermissions = (userRole: UserRole): string[] => {
  return PERMISSIONS[userRole] || [];
};

export const canAccessRoute = (userRole: UserRole, route: string): boolean => {
  const routePermissions: Record<string, UserRole> = {
    '/user': 'USER',
    '/manager': 'MANAGER',
    '/admin': 'ADMIN'
  };

  const requiredRole = routePermissions[route];
  if (!requiredRole) return true; // 공통 라우트는 접근 허용

  return hasRequiredRole(userRole, requiredRole);
};
