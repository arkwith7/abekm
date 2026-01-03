import {
  BarChart3,
  Bell,
  Brain,
  ChevronDown,
  Database,
  FileText,
  FolderOpen,
  LogOut,
  Menu,
  Monitor,
  Settings,
  Shield,
  Users,
  X
} from 'lucide-react';
import React, { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useSidebar } from '../contexts/SidebarContext';
import { useAuth } from '../hooks/useAuth';

// 페이지 컴포넌트들 임포트
import AdminDashboard from '../pages/admin/AdminDashboard';
import AIManagement from '../pages/admin/AIManagement';
import AuditLog from '../pages/admin/AuditLog';
import KnowledgeBaseManagement from '../pages/admin/KnowledgeBaseManagement';
import SecurityPolicy from '../pages/admin/SecurityPolicy';
import SystemMonitoring from '../pages/admin/SystemMonitoring';
import UserManagement from '../pages/admin/UserManagement';
import ContainerManagement from '../pages/manager/ContainerManagement';

const adminMenuItems = [
  {
    name: '시스템 대시보드',
    path: '/admin',
    icon: Monitor,
    exact: true,
    id: 'dashboard'
  },
  {
    name: '시스템 모니터링',
    path: '/admin/monitoring',
    icon: BarChart3,
    id: 'monitoring'
  },
  {
    name: '지식컨테이너 관리',
    path: '/admin/containers',
    icon: FolderOpen,
    id: 'containers'
  },
  {
    name: '사용자 관리',
    path: '/admin/users',
    icon: Users,
    id: 'users'
  },
  {
    name: '보안 정책',
    path: '/admin/security',
    icon: Shield,
    id: 'security'
  },
  {
    name: '감사 로그',
    path: '/admin/audit',
    icon: FileText,
    id: 'audit'
  },
  {
    name: '지식베이스 관리',
    path: '/admin/knowledge-base',
    icon: Database,
    id: 'knowledge-base'
  },
  {
    name: 'AI 사용량 관리',
    path: '/admin/ai',
    icon: Brain,
    id: 'ai'
  },
];

export const AdminLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { isOpen: isSidebarOpen, toggle: toggleSidebar } = useSidebar();

  // 🎯 상태 보존을 위한 활성 메뉴 상태
  const [activeMenu, setActiveMenu] = useState(() => {
    // URL에 따라 초기 활성 메뉴 설정
    if (location.pathname === '/admin') return 'dashboard';
    if (location.pathname.startsWith('/admin/monitoring')) return 'monitoring';
    if (location.pathname.startsWith('/admin/containers')) return 'containers';
    if (location.pathname.startsWith('/admin/users')) return 'users';
    if (location.pathname.startsWith('/admin/security')) return 'security';
    if (location.pathname.startsWith('/admin/audit')) return 'audit';
    if (location.pathname.startsWith('/admin/knowledge-base')) return 'knowledge-base';
    if (location.pathname.startsWith('/admin/ai')) return 'ai';
    return 'dashboard';
  });

  const [showUserMenu, setShowUserMenu] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // URL 변경 감지하여 activeMenu 동기화
  useEffect(() => {
    if (location.pathname === '/admin') setActiveMenu('dashboard');
    else if (location.pathname.startsWith('/admin/monitoring')) setActiveMenu('monitoring');
    else if (location.pathname.startsWith('/admin/containers')) setActiveMenu('containers');
    else if (location.pathname.startsWith('/admin/users')) setActiveMenu('users');
    else if (location.pathname.startsWith('/admin/security')) setActiveMenu('security');
    else if (location.pathname.startsWith('/admin/audit')) setActiveMenu('audit');
    else if (location.pathname.startsWith('/admin/knowledge-base')) setActiveMenu('knowledge-base');
    else if (location.pathname.startsWith('/admin/ai')) setActiveMenu('ai');
  }, [location.pathname]);

  // 메뉴 클릭 핸들러 - 상태 기반 네비게이션
  const handleMenuClick = (menuId: string, path: string) => {
    console.log(`🎯 관리자 메뉴 클릭: ${menuId} -> ${path}`);
    setActiveMenu(menuId);

    // URL도 업데이트 (브라우저 뒤로가기 등을 위해)
    if (location.pathname !== path) {
      navigate(path, { replace: true });
    }
  };

  // NOTE: isActive helper was unused; removed to satisfy eslint.

  const handleLogout = () => {
    logout();
  };

  // 사용자 화면으로 토글
  const handleUserToggle = () => {
    navigate('/user');
  };

  // 외부 클릭 감지
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* 상단 헤더 - 전체 너비 */}
      <header className="bg-white shadow-sm border-b border-gray-200 h-16 flex items-center">
        <div className="flex items-center justify-between w-full">
          {/* 좌측: 햄버거 메뉴 + 로고 영역 */}
          <div className={`${isSidebarOpen ? 'w-64' : 'w-16'} px-6 border-r border-gray-200 h-16 flex items-center transition-all duration-300`}>
            <div className="flex items-center space-x-3 w-full">
              {/* 햄버거 메뉴 버튼 */}
              <button
                onClick={toggleSidebar}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                title={isSidebarOpen ? "사이드바 닫기" : "사이드바 열기"}
              >
                {isSidebarOpen ? (
                  <X className="w-5 h-5 text-gray-600" />
                ) : (
                  <Menu className="w-5 h-5 text-gray-600" />
                )}
              </button>

              {/* 로고 (사이드바가 열렸을 때만 표시) */}
              {isSidebarOpen && (
                <div
                  className="flex items-center space-x-3 cursor-pointer hover:bg-gray-50 rounded-lg p-2 transition-colors"
                  onClick={handleUserToggle}
                  title="사용자 화면으로 이동"
                >
                  <div className="w-8 h-8 bg-red-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold">W</span>
                  </div>
                  <div>
                    <h1 className="text-lg font-bold text-gray-900">IPBridge</h1>
                    <p className="text-xs text-red-500">시스템관리자</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* 우측: 페이지 제목 및 사용자 정보 */}
          <div className="flex-1 px-6 flex items-center justify-between">
            {/* 현재 페이지 표시 */}
            <div className="flex items-center space-x-4">
              <h2 className="text-lg font-semibold text-gray-900">
                {adminMenuItems.find(item => item.id === activeMenu)?.name || '시스템 대시보드'}
              </h2>
            </div>

            {/* 우측 영역 */}
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">
                마지막 접속: {new Date().toLocaleDateString('ko-KR')}
              </div>

              {/* 알림 */}
              <button className="text-gray-400 hover:text-gray-500">
                <Bell className="w-5 h-5" />
              </button>

              {/* 사용자 메뉴 */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setShowUserMenu(!showUserMenu)}
                  className="flex items-center space-x-3 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
                >
                  <div className="w-8 h-8 bg-red-500 rounded-full flex items-center justify-center">
                    <span className="text-white text-sm font-medium">
                      {user?.name?.charAt(0) || 'A'}
                    </span>
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium text-gray-900">
                      {user?.name || '관리자'}
                    </p>
                    <p className="text-xs text-gray-500">
                      시스템관리자
                    </p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </button>

                {/* 드롭다운 메뉴 */}
                {showUserMenu && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50 border border-gray-200">
                    <div className="px-4 py-2 text-sm text-gray-700 border-b border-gray-200">
                      <div className="font-medium">{user?.name || '관리자'}</div>
                      <div className="text-xs text-gray-500">{user?.email || 'admin@woongjin.co.kr'}</div>
                      <div className="text-xs text-gray-500">시스템관리자</div>
                    </div>

                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        handleUserToggle();
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <Users className="w-4 h-4" />
                      <span>사용자 화면</span>
                    </button>

                    <button
                      onClick={() => setShowUserMenu(false)}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <Settings className="w-4 h-4" />
                      <span>설정</span>
                    </button>

                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        handleLogout();
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <LogOut className="w-4 h-4" />
                      <span>로그아웃</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* 하단 콘텐츠 영역 */}
      <div className="flex flex-1">
        {/* 좌측 사이드바 */}
        <div className={`${isSidebarOpen ? 'w-64' : 'w-16'} bg-white shadow-lg flex flex-col transition-all duration-300 overflow-hidden`}>
          {/* 네비게이션 */}
          <nav className="flex-1 p-4 space-y-2">
            {/* 관리자 기능 */}
            <div className="mb-4">
              {adminMenuItems.map((item) => {
                const Icon = item.icon;
                const active = activeMenu === item.id;

                return (
                  <button
                    key={item.name}
                    onClick={() => handleMenuClick(item.id, item.path)}
                    className={`
                      flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors w-full text-left
                      ${active
                        ? 'bg-red-100 text-red-700 border-r-2 border-red-600'
                        : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                      }
                    `}
                    title={item.name}
                  >
                    <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span className={`${isSidebarOpen ? 'opacity-100' : 'opacity-0'} transition-opacity duration-300`}>
                      {item.name}
                    </span>
                  </button>
                );
              })}
            </div>
          </nav>
        </div>

        {/* 우측 메인 콘텐츠 */}
        <div className="flex-1 overflow-auto">
          {/* 모든 페이지 컴포넌트를 동시에 마운트하고 가시성만 제어 */}
          <div style={{ display: activeMenu === 'dashboard' ? 'block' : 'none' }}>
            <AdminDashboard />
          </div>
          <div style={{ display: activeMenu === 'monitoring' ? 'block' : 'none' }}>
            <SystemMonitoring />
          </div>
          <div style={{ display: activeMenu === 'containers' ? 'block' : 'none' }}>
            <ContainerManagement />
          </div>
          <div style={{ display: activeMenu === 'users' ? 'block' : 'none' }}>
            <UserManagement />
          </div>
          <div style={{ display: activeMenu === 'security' ? 'block' : 'none' }}>
            <SecurityPolicy />
          </div>
          <div style={{ display: activeMenu === 'audit' ? 'block' : 'none' }}>
            <AuditLog />
          </div>
          <div style={{ display: activeMenu === 'knowledge-base' ? 'block' : 'none' }}>
            <KnowledgeBaseManagement />
          </div>
          <div style={{ display: activeMenu === 'ai' ? 'block' : 'none' }}>
            <AIManagement />
          </div>
        </div>
      </div>

      {/* 모바일 하단 네비게이션 */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200">
        <div className="flex justify-around py-2">
          {adminMenuItems.slice(0, 5).map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.path}
                onClick={() => handleMenuClick(item.id, item.path)}
                className="flex flex-col items-center px-2 py-1 text-xs text-gray-600"
              >
                <Icon className="w-5 h-5 mb-1" />
                <span className="truncate">{item.name}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
