import { Eye, EyeOff, Lock, LogIn, User } from 'lucide-react';
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

const LoginPage: React.FC = () => {
  const [formData, setFormData] = useState({
    employeeId: '',
    password: ''
  });
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const { login, user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  // 로그인 상태 체크 및 역할별 리다이렉트
  useEffect(() => {
    if (isAuthenticated && user) {
      switch (user.role) {
        case 'ADMIN':
          navigate('/admin');
          break;
        case 'MANAGER':
          navigate('/manager');
          break;
        case 'USER':
        default:
          navigate('/user');
          break;
      }
    }
  }, [isAuthenticated, user, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.employeeId || !formData.password) {
      setError('사번과 비밀번호를 입력해주세요.');
      return;
    }

    setIsLoading(true);
    setError('');

    try {
      await login(formData.employeeId, formData.password);
      // 로그인 성공 후 역할별 리다이렉트는 useEffect에서 처리
    } catch (error: any) {
      console.error('Login failed:', error);
      setError('로그인에 실패했습니다. 사번과 비밀번호를 확인해주세요.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleInputChange = (field: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    if (error) setError(''); // 입력 시 에러 메시지 제거
  };

  const handleForgotPassword = () => {
    alert('비밀번호 재설정은 시스템 관리자에게 문의하세요.');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0">
        <div className="absolute top-10 left-10 w-64 h-64 bg-blue-200 rounded-full mix-blend-multiply filter blur-xl opacity-30 animate-blob"></div>
        <div className="absolute top-10 right-10 w-64 h-64 bg-purple-200 rounded-full mix-blend-multiply filter blur-xl opacity-30 animate-blob animation-delay-2000"></div>
        <div className="absolute -bottom-8 left-20 w-64 h-64 bg-indigo-200 rounded-full mix-blend-multiply filter blur-xl opacity-30 animate-blob animation-delay-4000"></div>
      </div>

      {/* Main content */}
      <div className="relative z-10 flex flex-col justify-center items-center min-h-screen px-4">
        {/* Logo and Title */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-blue-600 rounded-2xl mb-4 shadow-lg">
            <span className="text-2xl font-bold text-white">W</span>
          </div>
          {/* <h1 className="text-4xl font-bold text-gray-900 mb-2">ABEKM</h1> */}
          <p className="text-gray-600 text-lg">Enterpise Insight Knowledge Link</p>
        </div>

        {/* Login Form */}
        <div className="w-full max-w-md">
          <div className="bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl border border-white/20 p-8">
            <form id="loginForm" onSubmit={handleSubmit} className="space-y-6">
              {/* Employee ID Input */}
              <div>
                <label htmlFor="employeeId" className="block text-sm font-medium text-gray-700 mb-2">
                  사번
                </label>
                <div className="relative">
                  <User className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    id="employeeId"
                    type="text"
                    value={formData.employeeId}
                    onChange={(e) => handleInputChange('employeeId', e.target.value)}
                    className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    placeholder="사번을 입력하세요"
                    disabled={isLoading}
                  />
                </div>
              </div>

              {/* Password Input */}
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
                  비밀번호
                </label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
                  <input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    value={formData.password}
                    onChange={(e) => handleInputChange('password', e.target.value)}
                    className="w-full pl-10 pr-12 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors"
                    placeholder="비밀번호를 입력하세요"
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    disabled={isLoading}
                  >
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>

              {/* Error Message */}
              {error && (
                <div className="text-red-600 text-sm text-center bg-red-50 p-3 rounded-lg">
                  {error}
                </div>
              )}

              {/* Login Button */}
              <button
                type="submit"
                disabled={isLoading || !formData.employeeId || !formData.password}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-medium py-3 px-4 rounded-lg transition-colors duration-200 flex items-center justify-center space-x-2"
              >
                {isLoading ? (
                  <>
                    <div className="animate-spin rounded-full h-5 w-5 border-2 border-white border-t-transparent"></div>
                    <span>로그인 중...</span>
                  </>
                ) : (
                  <>
                    <LogIn className="w-5 h-5" />
                    <span>로그인</span>
                  </>
                )}
              </button>

              {/* Demo Login Button */}
              <button
                type="button"
                onClick={() => {
                  setFormData({
                    employeeId: 'ADMIN001',
                    password: 'admin123!'
                  });
                  // 자동으로 로그인 실행
                  setTimeout(() => {
                    const form = document.getElementById('loginForm') as HTMLFormElement;
                    if (form) {
                      form.requestSubmit();
                    }
                  }, 100);
                }}
                className="w-full flex items-center justify-center px-4 py-3 mt-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 focus:ring-4 focus:ring-gray-200 transition-all duration-200 font-medium border border-gray-300"
              >
                <div className="flex items-center">
                  <User className="h-5 w-5 mr-2" />
                  데모 로그인 (시스템관리자)
                </div>
              </button>

              {/* Additional Demo Accounts */}
              <div className="mt-2 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => {
                    setFormData({
                      employeeId: 'MSS001',
                      password: 'msservice123'
                    });
                    setTimeout(() => {
                      const form = document.getElementById('loginForm') as HTMLFormElement;
                      if (form) form.requestSubmit();
                    }, 100);
                  }}
                  className="flex items-center justify-center px-3 py-2 bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 text-sm border border-blue-200"
                >
                  지식관리자
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setFormData({
                      employeeId: '77107791',
                      password: 'staff2025'
                    });
                    setTimeout(() => {
                      const form = document.getElementById('loginForm') as HTMLFormElement;
                      if (form) form.requestSubmit();
                    }, 100);
                  }}
                  className="flex items-center justify-center px-3 py-2 bg-green-50 text-green-700 rounded-md hover:bg-green-100 text-sm border border-green-200"
                >
                  일반사용자
                </button>
              </div>

              {/* Forgot Password Link */}
              <div className="text-center">
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  className="text-sm text-blue-600 hover:text-blue-800 hover:underline"
                  disabled={isLoading}
                >
                  비밀번호를 잊으셨나요?
                </button>
              </div>
            </form>
          </div>

          {/* Footer */}
          <div className="text-center mt-8 text-sm text-gray-500">
            <p>© 2025 KMS. All rights reserved.</p>
          </div>
        </div>
      </div>

      {/* Custom CSS for animations */}
      <style dangerouslySetInnerHTML={{
        __html: `
          @keyframes blob {
            0% {
              transform: translate(0px, 0px) scale(1);
            }
            33% {
              transform: translate(30px, -50px) scale(1.1);
            }
            66% {
              transform: translate(-20px, 20px) scale(0.9);
            }
            100% {
              transform: translate(0px, 0px) scale(1);
            }
          }
          .animate-blob {
            animation: blob 7s infinite;
          }
          .animation-delay-2000 {
            animation-delay: 2s;
          }
          .animation-delay-4000 {
            animation-delay: 4s;
          }
        `
      }} />
    </div>
  );
};

export default LoginPage;
