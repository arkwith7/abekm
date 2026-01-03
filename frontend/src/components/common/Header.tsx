import { Menu, X } from 'lucide-react';
import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useSidebar } from '../../contexts/SidebarContext';
import { useAuth } from '../../hooks/useAuth';
import { useRole } from '../../hooks/useRole';
import { getRoleDisplayName, getRoleIcon } from '../../utils/roleChecker';

interface HeaderProps {
  title?: string;
  showUserInfo?: boolean;
  className?: string;
}

export const Header: React.FC<HeaderProps> = ({
  title = 'IPBridge',
  showUserInfo = true,
  className = ''
}) => {
  const { user, logout } = useAuth();
  const { currentRole } = useRole();
  const { isOpen: isSidebarOpen, toggle: toggleSidebar } = useSidebar();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
  };

  const handleAdminClick = () => {
    if (user?.role === 'ADMIN') {
      navigate('/admin');
    } else if (user?.role === 'MANAGER') {
      navigate('/manager');
    }
  };

  return (
    <header className={`bg-white shadow-sm border-b border-gray-200 ${className}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* 햄버거 메뉴 + 로고 및 제목 */}
          <div className="flex items-center space-x-4">
            {/* 햄버거 메뉴 버튼 */}
            <button
              onClick={toggleSidebar}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
              title={isSidebarOpen ? "사이드바 닫기" : "사이드바 열기"}
            >
              {isSidebarOpen ? (
                <X className="w-5 h-5 text-gray-600" />
              ) : (
                <Menu className="w-5 h-5 text-gray-600" />
              )}
            </button>

            <h1 className="text-xl font-semibold text-gray-900">
              {title}
            </h1>
          </div>

          {/* 사용자 정보 및 메뉴 */}
          {showUserInfo && user && (
            <div className="flex items-center space-x-4">
              {/* 알림 */}
              <button className="text-gray-400 hover:text-gray-500">
                <span className="text-xl">🔔</span>
              </button>

              {/* 검색 */}
              <button className="text-gray-400 hover:text-gray-500">
                <span className="text-xl">🔍</span>
              </button>

              {/* 사용자 정보 */}
              <div className="relative group">
                <button className="flex items-center space-x-2 text-sm bg-white rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <span className="text-lg">
                    {currentRole ? getRoleIcon(currentRole) : '👤'}
                  </span>
                  <span className="text-gray-700 font-medium">{user.name}</span>
                  <span className="text-gray-500 text-xs">
                    {currentRole ? getRoleDisplayName(currentRole) : ''}
                  </span>
                </button>

                {/* 드롭다운 메뉴 */}
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200">
                  <div className="px-4 py-2 text-sm text-gray-700 border-b">
                    <div className="font-medium">{user.name}</div>
                    <div className="text-xs text-gray-500">{user.email}</div>
                    <div className="text-xs text-gray-500">{user.department}</div>
                  </div>

                  {/* 지식관리 메뉴 - MANAGER나 ADMIN만 표시 */}
                  {(user?.role === 'MANAGER' || user?.role === 'ADMIN') && (
                    <button
                      onClick={handleAdminClick}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <span className={`w-4 h-4 rounded text-xs flex items-center justify-center text-white font-bold ${user?.role === 'ADMIN' ? 'bg-red-600' : 'bg-blue-600'
                        }`}>
                        {user?.role === 'ADMIN' ? 'A' : 'M'}
                      </span>
                      <span>
                        {user?.role === 'ADMIN' ? '시스템관리' : '지식관리'}
                      </span>
                    </button>
                  )}

                  <button
                    onClick={() => {/* 프로필 설정 */ }}
                    className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    프로필 설정
                  </button>

                  <button
                    onClick={handleLogout}
                    className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100"
                  >
                    로그아웃
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};
