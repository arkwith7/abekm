import { createContext, ReactNode, useContext, useEffect, useState } from 'react';
import { useGlobalApp } from '../contexts/GlobalAppContext';
import { authService, LoginRequest } from '../services/authService';
import { User } from '../types/user.types';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (empNo: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // GlobalApp context에서 clearAllDocumentsOnLogout 함수 가져오기
  const { actions } = useGlobalApp();

  useEffect(() => {
    checkAuthStatus();
  }, []);

  // ✅ authService.logout()가 발행하는 이벤트를 받아 SPA 메모리 상태까지 확실히 초기화
  useEffect(() => {
    const onLogout = () => {
      try {
        actions.clearAllDocumentsOnLogout();
      } catch {
        // ignore
      }
      setUser(null);
    };

    window.addEventListener('abekm:logout', onLogout as EventListener);
    return () => window.removeEventListener('abekm:logout', onLogout as EventListener);
  }, [actions]);

  const checkAuthStatus = async () => {
    try {
      const token = authService.getToken();
      if (token && authService.isAuthenticated()) {
        const userData = authService.getUser();
        if (userData) {
          setUser({
            id: userData.id.toString(),
            emp_no: userData.emp_no,
            name: userData.emp_name || userData.username,
            username: userData.username || userData.emp_no,
            email: userData.email,
            department: userData.dept_name || '',
            position: userData.position_name || '',
            role: (userData.role as 'USER' | 'MANAGER' | 'ADMIN') || (userData.is_admin ? 'ADMIN' : 'USER'),
            created_at: '',
            updated_at: userData.last_login || ''
          });
        }
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      authService.logout();
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (empNo: string, password: string) => {
    try {
      const credentials: LoginRequest = {
        employeeId: empNo,
        password: password
      };
      const response = await authService.login(credentials);

      setUser({
        id: response.user_info.id.toString(),
        emp_no: response.user_info.emp_no,
        name: response.user_info.emp_name || response.user_info.username,
        username: response.user_info.username || response.user_info.emp_no,
        email: response.user_info.email,
        department: response.user_info.dept_name || '',
        position: response.user_info.position_name || '',
        role: (response.user_info.role as 'USER' | 'MANAGER' | 'ADMIN') || (response.user_info.is_admin ? 'ADMIN' : 'USER'),
        created_at: '',
        updated_at: response.user_info.last_login || ''
      });
    } catch (error) {
      throw error;
    }
  };

  const logout = () => {
    // ✅ 로그아웃: localStorage/sessionStorage 먼저 완전 초기화(토큰 제거) →
    //    이후 발생할 수 있는 언마운트 flush(savePageState)가 이전 선택을 되살리지 않도록 함
    authService.logout();

    // ✅ 메모리 상태도 즉시 정리 (이벤트 리스너에서도 재차 방어)
    try {
      actions.clearAllDocumentsOnLogout();
    } catch {
      // ignore
    }
    setUser(null);
  };

  const value = {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
