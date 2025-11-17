import React, { useEffect, useState } from 'react';
import { authService } from '../../services/authService';
import { redirectToLogin } from '../../utils/navigation';

interface SessionWarningProps {
  warningMinutes?: number; // 몇 분 전에 경고할지 (기본: 5분)
}

const SessionWarning: React.FC<SessionWarningProps> = ({ warningMinutes = 5 }) => {
  const [showWarning, setShowWarning] = useState(false);
  const [remainingTimeMinutes, setRemainingTimeMinutes] = useState<number | null>(null);
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null);
  const [isSessionExpired, setIsSessionExpired] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false); // 중복 호출 방지

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    let secondTicker: NodeJS.Timeout | null = null;

    const checkSessionTime = () => {
      // 이미 세션이 만료된 상태라면 더 이상 체크하지 않음
      if (isSessionExpired) {
        return;
      }

      const timeUntilExpiry = authService.getTimeUntilExpiry();
      const seconds = authService.getTimeUntilExpirySeconds();

      if (timeUntilExpiry !== null) {
        setRemainingTimeMinutes(timeUntilExpiry);
        setRemainingSeconds(seconds);

        // 세션이 만료된 경우 (0분 이하) 자동 로그아웃 및 로그인 페이지로 이동
        if (timeUntilExpiry <= 0) {
          console.log('🚨 세션 만료 - 자동 로그아웃 및 로그인 페이지 이동');
          setIsSessionExpired(true); // 플래그 설정으로 추가 체크 방지
          if (interval) clearInterval(interval);
          if (secondTicker) clearInterval(secondTicker);
          authService.logout();
          redirectToLogin();
          return;
        }

        // 설정된 시간보다 적게 남았을 때 경고 표시
        if (timeUntilExpiry <= warningMinutes) {
          setShowWarning(true);
        } else {
          setShowWarning(false);
        }
      } else {
        // 토큰이 없거나 만료 시간 정보가 없는 경우
        console.log('🚨 세션 정보 없음 - 로그인 페이지로 이동');
        setIsSessionExpired(true); // 플래그 설정으로 추가 체크 방지
        if (interval) clearInterval(interval);
        if (secondTicker) clearInterval(secondTicker);
        authService.logout();
        redirectToLogin();
      }
    };

    // 세션 만료 이벤트 리스너 (다른 서비스에서 발생시킬 수 있음)
    const handleSessionExpired = () => {
      console.log('🚨 세션 만료 이벤트 감지 - 컴포넌트 정리');
      setIsSessionExpired(true);
      setShowWarning(false);
      if (interval) clearInterval(interval);
      if (secondTicker) clearInterval(secondTicker);
    };

    // refresh token 실패 이벤트 리스너
    const handleSessionInvalid = (event: any) => {
      console.log('🚨 세션 무효 이벤트 감지 - 강제 로그아웃', event.detail);
      setIsSessionExpired(true);
      setShowWarning(false);
      if (interval) clearInterval(interval);
      if (secondTicker) clearInterval(secondTicker);
      authService.logout();
      redirectToLogin();
    };

    // 이벤트 리스너 등록
    window.addEventListener('session:expired', handleSessionExpired);
    window.addEventListener('session:invalid', handleSessionInvalid);

    // 초기 체크
    checkSessionTime();

    // 세션이 만료되지 않았을 때만 정기 체크 시작
    if (!isSessionExpired) {
      // 10초마다 정기 체크
      interval = setInterval(checkSessionTime, 10000);
      // 1초마다 카운트다운
      secondTicker = setInterval(() => {
        if (!isSessionExpired) {
          const secs = authService.getTimeUntilExpirySeconds();
          setRemainingSeconds(secs);
        }
      }, 1000);
    }

    return () => {
      if (interval) clearInterval(interval);
      if (secondTicker) clearInterval(secondTicker);
      window.removeEventListener('session:expired', handleSessionExpired);
      window.removeEventListener('session:invalid', handleSessionInvalid);
    };
  }, [warningMinutes, isSessionExpired]); const handleExtendSession = async () => {
    // 이미 세션이 만료된 상태라면 연장 시도하지 않음
    if (isSessionExpired) {
      console.log('🚨 세션이 이미 만료되어 연장할 수 없습니다.');
      return;
    }

    // 이미 세션 연장 중이라면 중복 호출 방지
    if (isRefreshing) {
      console.log('⏳ 이미 세션 연장 진행 중 - 중복 호출 방지');
      return;
    }

    try {
      setIsRefreshing(true);
      console.log('🔄 세션 연장 시작...');
      // 실제 refresh 토큰 기반 연장 시도
      const refreshed = await authService.refreshAccessToken();

      if (refreshed === 'no_refresh_needed') {
        // 토큰이 아직 유효해서 갱신이 불필요한 경우
        console.log('✅ 액세스 토큰이 아직 유효함 - 세션 연장 불필요');
        setShowWarning(false);
        return;
      } else if (refreshed === true) {
        // 실제로 토큰이 갱신된 경우
        setShowWarning(false);
        console.log('✅ 세션 리프레시 성공 (토큰 갱신됨)');

        // 성공 알림 (선택사항)
        const successEvent = new CustomEvent('session:extended');
        window.dispatchEvent(successEvent);
      } else {
        console.log('🔴 세션 연장 실패 - 사용자에게 재시도 옵션 제공');
        // 바로 로그아웃하지 않고 사용자에게 알림
        alert('세션 연장에 실패했습니다. 잠시 후 다시 시도하거나 새로고침 후 다시 로그인해주세요.');
      }
    } catch (error) {
      console.error('❌ 세션 연장 중 오류:', error);
      alert('세션 연장 중 오류가 발생했습니다. 페이지를 새로고침하거나 다시 로그인해주세요.');
    } finally {
      setIsRefreshing(false); // 세션 연장 완료 후 플래그 해제
    }
  };

  if (!showWarning) return null;

  return (
    <div className="fixed top-4 right-4 z-50 bg-yellow-100 border-l-4 border-yellow-500 p-4 rounded-md shadow-lg max-w-sm">
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <svg className="h-5 w-5 text-yellow-500" viewBox="0 0 20 20" fill="currentColor">
            <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
          </svg>
        </div>
        <div className="ml-3 flex-1">
          <h3 className="text-sm font-medium text-yellow-800">
            세션 만료 경고
          </h3>
          <div className="mt-2 text-sm text-yellow-700">
            <p>
              {remainingTimeMinutes}분 ({remainingSeconds}s) 후 세션이 만료됩니다.
              계속 사용하시려면 세션을 연장해주세요.
            </p>
          </div>
          <div className="mt-3 flex space-x-2">
            <button
              type="button"
              onClick={handleExtendSession}
              className="bg-yellow-500 hover:bg-yellow-600 text-white px-3 py-1 rounded text-xs font-medium"
            >
              세션 연장
            </button>
            <button
              type="button"
              onClick={() => setShowWarning(false)}
              className="bg-gray-200 hover:bg-gray-300 text-gray-700 px-3 py-1 rounded text-xs font-medium"
            >
              닫기
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SessionWarning;
