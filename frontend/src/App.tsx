import React, { useEffect } from 'react';
import { Route, BrowserRouter as Router, Routes, useNavigate } from 'react-router-dom';
import './App.css';

// Hooks
import { AuthProvider } from './hooks/useAuth';

// Context
import { GlobalAppProvider } from './contexts/GlobalAppContext';
import { SidebarProvider } from './contexts/SidebarContext';

// Utils
import { setGlobalNavigate } from './utils/navigation';

// Layouts
import { AdminLayout } from './layouts/AdminLayout';
import { ManagerLayout } from './layouts/ManagerLayout';
import { UserLayout } from './layouts/UserLayout';

// Components
import { ProtectedRoute } from './components/common/ProtectedRoute';
import RoleBasedRedirect from './components/common/RoleBasedRedirect';
import LoginPage from './components/LoginPage';

// Pages
import AdminDashboard from './pages/admin/AdminDashboard';
import AuditLog from './pages/admin/AuditLog';
import SecurityPolicy from './pages/admin/SecurityPolicy';
import SystemMonitoring from './pages/admin/SystemMonitoring';
import UserManagement from './pages/admin/UserManagement';
import ContainerManagement from './pages/manager/ContainerManagement';
import DocumentManagement from './pages/manager/DocumentManagement';
import ManagerDashboard from './pages/manager/ManagerDashboard';
import UserPermissionManagement from './pages/manager/UserPermissionManagement';
import AgentChatPage from './pages/user/AgentChatPage';
import ChatHistoryPage from './pages/user/chat/ChatHistoryPage';
// ⚠️ "일반 RAG 채팅" 비활성화 (2025-12-09) - AI Agents로 통합
// import ChatPage from './pages/user/ChatPage';
import ContainerExplorer from './pages/user/ContainerExplorer';
import { UserDashboard } from './pages/user/Dashboard';
import MyKnowledge from './pages/user/MyKnowledge';
import PermissionRequestsPage from './pages/user/PermissionRequestsPage';
import HTMLPresentationViewer from './pages/user/presentation/HTMLPresentationViewer';
import PresentationAgentChatPage from './pages/user/PresentationAgentChatPage';
import SearchPage from './pages/user/SearchPage';
import UserProfilePage from './pages/user/UserProfilePage';
import UserSettingsPage from './pages/user/UserSettingsPage';

// 네비게이션 설정 컴포넌트
const NavigationProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();

  useEffect(() => {
    setGlobalNavigate(navigate);

    // 세션 만료 이벤트 리스너 추가
    const handleSessionExpired = () => {
      console.log('🔔 글로벌 세션 만료 이벤트 감지');
      // 다른 탭이나 창에서도 동기화
      navigate('/login', { replace: true });
    };

    window.addEventListener('session:expired', handleSessionExpired);

    return () => {
      window.removeEventListener('session:expired', handleSessionExpired);
    };
  }, [navigate]);

  return <>{children}</>;
};

function App() {
  return (
    <SidebarProvider>
      <GlobalAppProvider>
        <AuthProvider>
          <Router
            future={{
              v7_startTransition: true,
              v7_relativeSplatPath: true
            }}
          >
            <NavigationProvider>
              <div className="App">
                <Routes>
                  {/* 공통 라우트 */}
                  <Route path="/login" element={<LoginPage />} />



                  <Route path="/unauthorized" element={
                    <div className="min-h-screen flex items-center justify-center">
                      <div className="text-center">
                        <h1 className="text-2xl font-bold text-gray-900 mb-4">접근 권한이 없습니다</h1>
                        <p className="text-gray-600 mb-4">이 페이지에 접근할 권한이 없습니다.</p>
                        <button
                          onClick={() => window.history.back()}
                          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                        >
                          돌아가기
                        </button>
                      </div>
                    </div>
                  } />

                  {/* 일반 사용자 라우트 */}
                  <Route element={<ProtectedRoute requiredRole="USER" />}>
                    <Route path="/user" element={<UserLayout />}>
                      <Route index element={<UserDashboard />} />
                      <Route path="search" element={<SearchPage />} />
                      <Route path="my-knowledge" element={<MyKnowledge />} />
                      <Route path="explore" element={<ContainerExplorer />} />
                      {/* ⚠️ "일반 RAG 채팅" 라우트 비활성화 (2025-12-09) */}
                      {/* AI Agents로 통합되어 더 이상 사용하지 않음 */}
                      {/* <Route path="chat" element={<ChatPage />} /> */}
                      <Route path="chat/history" element={<ChatHistoryPage />} />
                      <Route path="agent-chat" element={<AgentChatPage />} />
                      <Route path="agent-chat/presentation" element={<PresentationAgentChatPage />} />
                      <Route path="presentation/html" element={<HTMLPresentationViewer />} />
                      <Route path="profile" element={<UserProfilePage />} />
                      <Route path="permission-requests" element={<PermissionRequestsPage />} />
                      <Route path="settings" element={<UserSettingsPage />} />
                    </Route>
                  </Route>

                  {/* 지식관리자 라우트 */}
                  <Route element={<ProtectedRoute requiredRole="MANAGER" />}>
                    <Route path="/manager" element={<ManagerLayout />}>
                      <Route index element={<ManagerDashboard />} />
                      <Route path="containers" element={<ContainerManagement />} />
                      <Route path="permissions" element={<UserPermissionManagement />} />
                      <Route path="documents" element={<DocumentManagement />} />
                      <Route path="analytics" element={<div>분석 리포트 (개발 예정)</div>} />
                      <Route path="settings" element={<div>설정 (개발 예정)</div>} />
                      {/* 사용자 기능도 포함 */}
                      <Route path="search" element={<SearchPage />} />
                      <Route path="my-knowledge" element={<MyKnowledge />} />
                      {/* ⚠️ "일반 RAG 채팅" 비활성화 (2025-12-09) */}
                      {/* <Route path="chat" element={<ChatPage />} /> */}
                      <Route path="chat/history" element={<ChatHistoryPage />} />
                      <Route path="presentation/html" element={<HTMLPresentationViewer />} />
                    </Route>
                  </Route>

                  {/* 시스템관리자 라우트 */}
                  <Route element={<ProtectedRoute requiredRole="ADMIN" />}>
                    <Route path="/admin" element={<AdminLayout />}>
                      <Route index element={<AdminDashboard />} />
                      <Route path="monitoring" element={<SystemMonitoring />} />
                      <Route path="containers" element={<ContainerManagement />} />
                      <Route path="users" element={<UserManagement />} />
                      <Route path="security" element={<SecurityPolicy />} />
                      <Route path="audit" element={<AuditLog />} />
                      <Route path="settings" element={<div>시스템 설정 (개발 예정)</div>} />

                      {/* 지식 관리 기능 */}
                      <Route path="manager/containers" element={<ContainerManagement />} />
                      <Route path="manager/permissions" element={<UserPermissionManagement />} />
                      <Route path="manager/documents" element={<DocumentManagement />} />
                      <Route path="manager/analytics" element={<div>분석 리포트 (개발 예정)</div>} />

                      {/* 사용자 기능 */}
                      <Route path="user/search" element={<SearchPage />} />
                      <Route path="user/my-knowledge" element={<MyKnowledge />} />
                      {/* ⚠️ "일반 RAG 채팅" 비활성화 (2025-12-09) */}
                      {/* <Route path="user/chat" element={<ChatPage />} /> */}
                      <Route path="user/chat/history" element={<ChatHistoryPage />} />
                    </Route>
                  </Route>

                  {/* 기본 리다이렉트 */}
                  <Route path="/" element={<RoleBasedRedirect />} />
                </Routes>
              </div>
            </NavigationProvider>
          </Router>
        </AuthProvider>
      </GlobalAppProvider>
    </SidebarProvider>
  );
}

export default App;
