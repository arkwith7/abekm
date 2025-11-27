import {
  Bell,
  ChevronDown,
  FileCheck,
  Folder,
  History,
  Home,
  LogOut,
  Menu,
  MessageSquare,
  Search,
  Settings,
  Shield,
  User,
  Users,
  X
} from 'lucide-react';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import SessionWarning from '../components/common/SessionWarning';
import { useWorkContext } from '../contexts/GlobalAppContext';
import { useSidebar } from '../contexts/SidebarContext';
import { SourcePageType } from '../contexts/types';
import { useAuth } from '../hooks/useAuth';

interface SubmenuItem {
  id: string;
  name: string;
  path: string;
  targetMenuId?: SourcePageType | string;
}

interface MenuItem {
  name: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
  id: string;
  badge?: string;
  hasSubmenu?: boolean;
  submenuItems?: SubmenuItem[];
}

const userMenuItems: MenuItem[] = [
  {
    name: '대시보드',
    path: '/user',
    icon: Home,
    exact: true,
    id: 'dashboard'
  },
  {
    name: '지식 컨테이너',
    path: '/user/my-knowledge',
    icon: Folder,
    id: 'my-knowledge'
  },
  {
    name: '지식 검색',
    path: '/user/search',
    icon: Search,
    id: 'search'
  },
  {
    name: '일반 RAG 채팅',
    path: '/user/chat',
    icon: MessageSquare,
    id: 'chat'
  },
  {
    name: 'AI Agents',
    path: '/user/agent-chat',
    icon: MessageSquare,
    id: 'agent-chat',
    badge: 'Beta'
  },
  {
    name: '대화 이력',
    path: '/user/chat/history',
    icon: History,
    id: 'chat-history'
  }
];

export const UserLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { isOpen: isSidebarOpen, toggle: toggleSidebar } = useSidebar();
  const { navigateWithContext } = useWorkContext();

  const menuItemRefs = useRef<Record<string, HTMLDivElement | null>>({});
  const dropdownRef = useRef<HTMLDivElement>(null);

  const activeMenu = useMemo(() => {
    if (location.pathname === '/user') return 'dashboard';
    if (location.pathname.startsWith('/user/my-knowledge')) return 'my-knowledge';
    if (location.pathname.startsWith('/user/search')) return 'search';
    if (location.pathname === '/user/agent-chat') return 'agent-chat';
    if (location.pathname.startsWith('/user/agent-chat/')) return 'agent-chat-sub';
    if (location.pathname.startsWith('/user/chat/history')) return 'chat-history';
    if (location.pathname.startsWith('/user/chat')) return 'chat';
    if (location.pathname.startsWith('/user/profile')) return 'profile';
    if (location.pathname.startsWith('/user/permission-requests')) return 'permission-requests';
    if (location.pathname.startsWith('/user/presentation/html')) return 'presentation-html';
    return 'dashboard';
  }, [location.pathname]);

  const activeAgentSubmenuId = useMemo(() => {
    const agentMenu = userMenuItems.find((item) => item.id === 'agent-chat');
    if (!agentMenu?.submenuItems) {
      return null;
    }
    const matched = agentMenu.submenuItems.find((subItem) => {
      if (subItem.path === '/user/agent-chat') {
        return location.pathname === subItem.path;
      }
      return location.pathname === subItem.path || location.pathname.startsWith(`${subItem.path}/`);
    });
    return matched?.id ?? null;
  }, [location.pathname]);

  const [showUserMenu, setShowUserMenu] = useState(false);
  const [hoveredMenuId, setHoveredMenuId] = useState<string | null>(null);
  const [submenuPosition, setSubmenuPosition] = useState<{ top: number; left: number }>({ top: 0, left: 0 });
  const [expandedMenuId, setExpandedMenuId] = useState<string | null>(null);
  const closeMenuTimerRef = useRef<NodeJS.Timeout | null>(null);

  const updateSubmenuPosition = useCallback((menuId: string) => {
    const element = menuItemRefs.current[menuId];
    if (!element) {
      return;
    }
    const rect = element.getBoundingClientRect();
    setSubmenuPosition({
      top: rect.top,
      left: rect.right + 12
    });
  }, []);

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

  useEffect(() => {
    if (!hoveredMenuId || isSidebarOpen) {
      return;
    }

    updateSubmenuPosition(hoveredMenuId);

    const handleResize = () => updateSubmenuPosition(hoveredMenuId);
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, [hoveredMenuId, isSidebarOpen, updateSubmenuPosition]);

  useEffect(() => {
    setHoveredMenuId(null);
  }, [isSidebarOpen]);

  const sourcePageMenuIds: SourcePageType[] = ['dashboard', 'my-knowledge', 'search', 'chat', 'agent-chat'];

  const handleMenuClick = (menuId: string, path: string) => {
    if (sourcePageMenuIds.includes(menuId as SourcePageType)) {
      try {
        navigateWithContext(menuId as SourcePageType);
      } catch (error) {
        console.warn('⚠️ navigateWithContext 실행 실패, 기본 네비게이션 사용:', error);
      }
    }

    if (location.pathname !== path) {
      navigate(path);
    }
  };

  const handleLogout = () => {
    logout();
  };

  const handleMenuMouseEnter = (item: MenuItem, event: React.MouseEvent<HTMLDivElement>) => {
    if (isSidebarOpen || !item.hasSubmenu || !item.submenuItems) {
      return;
    }
    // Clear any pending close timer
    if (closeMenuTimerRef.current) {
      clearTimeout(closeMenuTimerRef.current);
      closeMenuTimerRef.current = null;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    setHoveredMenuId(item.id);
    setSubmenuPosition({ top: rect.top, left: rect.right + 12 });
  };

  const handleMenuMouseLeave = (item: MenuItem, event: React.MouseEvent<HTMLDivElement>) => {
    if (isSidebarOpen || !item.hasSubmenu || !item.submenuItems) {
      return;
    }
    const related = event.relatedTarget as HTMLElement | null;
    if (related && related.dataset?.submenu === item.id) {
      return;
    }
    // Delay closing to allow mouse to reach submenu
    if (closeMenuTimerRef.current) {
      clearTimeout(closeMenuTimerRef.current);
    }
    closeMenuTimerRef.current = setTimeout(() => {
      setHoveredMenuId((current) => (current === item.id ? null : current));
    }, 150); // 150ms delay
  };

  const handleFlyoutMouseEnter = () => {
    // Clear close timer when mouse enters flyout
    if (closeMenuTimerRef.current) {
      clearTimeout(closeMenuTimerRef.current);
      closeMenuTimerRef.current = null;
    }
  };

  const handleFlyoutMouseLeave = (itemId: string) => {
    // Delay closing when mouse leaves flyout
    if (closeMenuTimerRef.current) {
      clearTimeout(closeMenuTimerRef.current);
    }
    closeMenuTimerRef.current = setTimeout(() => {
      setHoveredMenuId((current) => (current === itemId ? null : current));
    }, 150); // 150ms delay
  };

  const isFlyoutOpen = (item: MenuItem) => {
    if (isSidebarOpen) {
      return false;
    }
    return item.hasSubmenu && item.submenuItems && hoveredMenuId === item.id;
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <SessionWarning warningMinutes={5} />

      <header className="bg-white shadow-sm border-b border-gray-200 h-16 flex items-center">
        <div className="flex items-center justify-between w-full">
          <div
            className={`${isSidebarOpen ? 'w-64' : 'w-16'} px-6 border-r border-gray-200 h-16 flex items-center transition-all duration-300`}
          >
            <div className="flex items-center space-x-3 w-full">
              <button
                onClick={toggleSidebar}
                className="p-2 hover:bg-gray-100 rounded-lg transition-colors flex-shrink-0"
                title={isSidebarOpen ? '사이드바 닫기' : '사이드바 열기'}
              >
                {isSidebarOpen ? <X className="w-5 h-5 text-gray-600" /> : <Menu className="w-5 h-5 text-gray-600" />}
              </button>

              {isSidebarOpen && (
                <div
                  className="flex items-center space-x-3 cursor-pointer hover:bg-gray-50 rounded-lg p-2 transition-colors"
                  onClick={() => navigate('/user')}
                  title="대시보드로 이동"
                >
                  <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                    <span className="text-white font-bold">W</span>
                  </div>
                  <div>
                    <h1 className="text-lg font-bold text-gray-900">ABEKM</h1>
                    <p className="text-xs text-gray-500">지식관리시스템</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="flex-1 px-6 flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h2 className="text-lg font-semibold text-gray-900">
                {(() => {
                  const menuItem = userMenuItems.find((item) => item.id === activeMenu);
                  if (menuItem) return menuItem.name;
                  if (activeAgentSubmenuId) {
                    const agentMenu = userMenuItems.find((item) => item.id === 'agent-chat');
                    const activeSubItem = agentMenu?.submenuItems?.find((subItem) => subItem.id === activeAgentSubmenuId);
                    if (activeSubItem) return activeSubItem.name;
                  }
                  if (activeMenu === 'presentation-html') return '프레젠테이션 뷰어';
                  if (activeMenu === 'profile') return '사용자정보';
                  if (activeMenu === 'permission-requests') return '권한신청현황';
                  return '대시보드';
                })()}
              </h2>
            </div>

            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">마지막 접속: {new Date().toLocaleDateString('ko-KR')}</div>

              <div className="relative">
                <Bell className="w-5 h-5 text-gray-400 hover:text-gray-600 cursor-pointer" />
                <span className="absolute -top-1 -right-1 w-3 h-3 bg-red-500 rounded-full text-xs" />
              </div>

              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setShowUserMenu((prev) => !prev)}
                  className="flex items-center space-x-3 hover:bg-gray-50 rounded-lg p-2 transition-colors"
                >
                  <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                    <span className="text-white text-sm font-medium">{user?.name?.charAt(0) || 'U'}</span>
                  </div>
                  <div className="text-left">
                    <p className="text-sm font-medium text-gray-900">{user?.name || '사용자'}</p>
                    <p className="text-xs text-gray-500">{user?.role || 'USER'}</p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </button>

                {showUserMenu && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg py-1 z-50 border border-gray-200">
                    <div className="px-4 py-2 text-sm text-gray-700 border-b border-gray-200">
                      <div className="font-medium">{user?.name || '사용자'}</div>
                      <div className="text-xs text-gray-500">{user?.email || 'user@woongjin.co.kr'}</div>
                      <div className="text-xs text-gray-500">{user?.department || '일반사용자'}</div>
                    </div>

                    {user?.role === 'ADMIN' && (
                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          navigate('/admin');
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                      >
                        <Shield className="w-4 h-4" />
                        <span>시스템관리자 화면</span>
                      </button>
                    )}

                    {user?.role === 'MANAGER' && (
                      <button
                        onClick={() => {
                          setShowUserMenu(false);
                          navigate('/manager');
                        }}
                        className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                      >
                        <Users className="w-4 h-4" />
                        <span>지식관리자 화면</span>
                      </button>
                    )}

                    {(user?.role === 'ADMIN' || user?.role === 'MANAGER') && (
                      <div className="border-t border-gray-200 my-1" />
                    )}

                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        navigate('/user/profile');
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <User className="w-4 h-4" />
                      <span>사용자정보</span>
                    </button>

                    <button
                      onClick={() => {
                        setShowUserMenu(false);
                        navigate('/user/permission-requests');
                      }}
                      className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-100 flex items-center space-x-2"
                    >
                      <FileCheck className="w-4 h-4" />
                      <span>권한신청현황</span>
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

      <div className="flex flex-1">
        <div
          className={`${isSidebarOpen ? 'w-64' : 'w-16'} bg-white shadow-lg flex flex-col transition-all duration-300 overflow-hidden sidebar`}
        >
          <nav className="flex-1 p-4 space-y-2">
            <div className="mb-4">
              {userMenuItems.map((item) => {
                const Icon = item.icon;
                const hasSubmenu = item.hasSubmenu && item.submenuItems?.length;
                // 서브메뉴가 활성화되어 있으면 상위 메뉴는 비활성화
                const hasActiveSubmenu = hasSubmenu && activeAgentSubmenuId !== null;
                const isActive = activeMenu === item.id && !hasActiveSubmenu;

                return (
                  <div
                    key={item.id}
                    className="relative"
                    ref={(element) => {
                      menuItemRefs.current[item.id] = element;
                    }}
                    onMouseEnter={(event) => handleMenuMouseEnter(item, event)}
                    onMouseLeave={(event) => handleMenuMouseLeave(item, event)}
                  >
                    <button
                      onClick={() => {
                        if (hasSubmenu) {
                          if (isSidebarOpen) {
                            // 사이드바가 열려있으면 서브메뉴 토글
                            setExpandedMenuId((prev) => (prev === item.id ? null : item.id));
                          } else {
                            // 사이드바가 닫혀있으면 첫 번째 서브메뉴로 이동
                            const firstSubItem = item.submenuItems![0];
                            const targetMenuId = firstSubItem.targetMenuId ?? firstSubItem.id;
                            handleMenuClick(targetMenuId, firstSubItem.path);
                          }
                          return;
                        }
                        handleMenuClick(item.id, item.path);
                      }}
                      className={`
												flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors w-full text-left
												${isActive ? 'bg-blue-100 text-blue-700 border-r-2 border-blue-600' : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'}
											`}
                      title={item.name}
                    >
                      <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
                      {isSidebarOpen && (
                        <span className="flex items-center gap-2 opacity-100 transition-opacity duration-300">
                          <span>{item.name}</span>
                          {item.badge && (
                            <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-indigo-100 text-indigo-700 rounded">
                              {item.badge}
                            </span>
                          )}
                        </span>
                      )}
                    </button>

                    {hasSubmenu && isSidebarOpen && expandedMenuId === item.id && (
                      <div className="ml-8 mt-1 space-y-1">
                        {item.submenuItems!.map((subItem) => {
                          const isSubActive = subItem.path === '/user/agent-chat'
                            ? location.pathname === subItem.path
                            : (location.pathname === subItem.path || location.pathname.startsWith(`${subItem.path}/`));
                          // Fallback은 실제로 agent-chat 경로에 있을 때만 적용
                          const isOnAgentChatRoute = location.pathname.startsWith('/user/agent-chat');
                          const useFallbackHighlight = isOnAgentChatRoute && subItem.path === '/user/agent-chat' && !activeAgentSubmenuId;
                          return (
                            <button
                              key={subItem.id}
                              onClick={() => {
                                const targetMenuId = subItem.targetMenuId ?? subItem.id;
                                handleMenuClick(targetMenuId, subItem.path);
                              }}
                              className={`
													flex items-center px-3 py-1.5 rounded-lg text-sm transition-colors w-full text-left border
													${isSubActive || useFallbackHighlight ? 'bg-blue-100 text-blue-700 border-blue-200 font-semibold shadow-sm pl-3' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-transparent pl-3'}
												`}
                            >
                              {subItem.name}
                            </button>
                          );
                        })}
                      </div>
                    )}                    {hasSubmenu && isFlyoutOpen(item) && (
                      <div
                        data-submenu={item.id}
                        onMouseEnter={() => {
                          handleFlyoutMouseEnter();
                          setHoveredMenuId(item.id);
                        }}
                        onMouseLeave={() => handleFlyoutMouseLeave(item.id)}
                        className="fixed z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-2 w-56"
                        style={{
                          top: `${submenuPosition.top}px`,
                          left: `${submenuPosition.left}px`
                        }}
                      >
                        {item.submenuItems!.map((subItem) => {
                          const isSubActive = subItem.path === '/user/agent-chat'
                            ? location.pathname === subItem.path
                            : (location.pathname === subItem.path || location.pathname.startsWith(`${subItem.path}/`));
                          // Fallback은 실제로 agent-chat 경로에 있을 때만 적용
                          const isOnAgentChatRoute = location.pathname.startsWith('/user/agent-chat');
                          const useFallbackHighlight = isOnAgentChatRoute && subItem.path === '/user/agent-chat' && !activeAgentSubmenuId;
                          return (
                            <button
                              key={subItem.id}
                              onClick={() => {
                                const targetMenuId = subItem.targetMenuId ?? subItem.id;
                                handleMenuClick(targetMenuId, subItem.path);
                                setHoveredMenuId(null);
                              }}
                              className={`
											w-full text-left px-4 py-2 text-sm transition-colors flex items-center justify-between border
											${isSubActive || useFallbackHighlight ? 'bg-blue-100 text-blue-700 border-blue-200 font-semibold shadow-sm' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900 border-transparent'}
										`}
                            >
                              <span>{subItem.name}</span>
                              <span className="text-xs text-gray-400">↗</span>
                            </button>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </nav>
        </div>

        <div className="flex-1 overflow-auto">
          <Outlet />
        </div>
      </div>

      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200">
        <div className="flex justify-around py-2">
          {userMenuItems.slice(0, 5).map((item) => {
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
