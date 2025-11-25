import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

// 개발 환경에서 StrictMode 비활성화 (WebSocket 중복 연결 방지)
// 프로덕션 환경에서는 StrictMode 활성화 (최적화 체크)
const isDevelopment = process.env.NODE_ENV === 'development';

if (isDevelopment) {
  console.log('🔧 [DEV MODE] React StrictMode 비활성화 (WebSocket 안정성)');
  root.render(<App />);
} else {
  console.log('🚀 [PROD MODE] React StrictMode 활성화');
  root.render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}
