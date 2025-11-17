import { UserRole } from '../hooks/usePermissions';
import { hasRequiredRole } from './permissions';

export const checkRole = (userRole: UserRole, requiredRole: UserRole): boolean => {
  return hasRequiredRole(userRole, requiredRole);
};

export const getRoleDisplayName = (role: UserRole): string => {
  const roleNames = {
    USER: '일반 사용자',
    MANAGER: '지식관리자',
    ADMIN: '시스템관리자'
  };
  return roleNames[role];
};

export const getRoleColor = (role: UserRole): string => {
  const roleColors = {
    USER: 'bg-blue-100 text-blue-800',
    MANAGER: 'bg-green-100 text-green-800',
    ADMIN: 'bg-red-100 text-red-800'
  };
  return roleColors[role];
};

export const getRoleIcon = (role: UserRole): string => {
  const roleIcons = {
    USER: '👤',
    MANAGER: '👔',
    ADMIN: '🔧'
  };
  return roleIcons[role];
};

export const isValidRole = (role: string): role is UserRole => {
  return ['USER', 'MANAGER', 'ADMIN'].includes(role);
};

export const getHigherRoles = (currentRole: UserRole): UserRole[] => {
  const allRoles: UserRole[] = ['USER', 'MANAGER', 'ADMIN'];
  const currentLevel = allRoles.indexOf(currentRole);
  return allRoles.slice(currentLevel + 1);
};

export const getLowerRoles = (currentRole: UserRole): UserRole[] => {
  const allRoles: UserRole[] = ['USER', 'MANAGER', 'ADMIN'];
  const currentLevel = allRoles.indexOf(currentRole);
  return allRoles.slice(0, currentLevel);
};
