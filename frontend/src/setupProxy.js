const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function (app) {
  const target = process.env.REACT_APP_API_URL || 'http://localhost:8000';
  const isDevelopment = process.env.NODE_ENV === 'development';
  const isDebug = process.env.REACT_APP_DEBUG === 'true';

  console.log('🔗 setupProxy.js 설정 중...');
  console.log('📍 Target URL:', target);
  console.log('🌍 NODE_ENV:', process.env.NODE_ENV);
  console.log('🔄 REACT_APP_ENV:', process.env.REACT_APP_ENV);
  console.log('🐛 Debug Mode:', isDebug);

  // Docker/프로덕션 환경 감지: REACT_APP_API_URL이 명시적으로 설정된 경우 프록시 비활성화
  // Nginx가 프록시를 담당하므로 중복 프록시 방지
  const isExplicitApiUrl = process.env.REACT_APP_API_URL && 
                          process.env.REACT_APP_API_URL !== 'http://localhost:8000' &&
                          process.env.REACT_APP_API_URL !== 'http://127.0.0.1:8000';
  
  if (isExplicitApiUrl) {
    console.log('🐳 프로덕션/Docker 환경 감지 - setupProxy 비활성화');
    console.log('   REACT_APP_API_URL:', process.env.REACT_APP_API_URL);
    console.log('   (Nginx 또는 직접 연결이 프록시 담당)');
    console.log('✅ setupProxy.js 설정 완료 (bypass mode)');
    return; // 프록시 설정하지 않음
  }

  console.log('🔄 Proxy Rule: /api -> ' + target);

  // URL 유효성 검사
  try {
    new URL(target);
  } catch (error) {
    console.error('❌ 잘못된 API URL:', target);
    console.error('   환경 변수 REACT_APP_API_URL을 확인하세요');
  }

  // ⚠️ 중요: /api 경로만 프록시 설정
  // /ws, /ws-hmr, /sockjs-node 등은 제외 (HMR용)
  const proxyMiddleware = createProxyMiddleware('/api', {
    target: target,
    changeOrigin: true,
    secure: false,
    ws: true, // WebSocket 프록시 활성화 (/api 경로만)
    logLevel: isDebug ? 'debug' : 'warn', // info → warn (로그 감소)
    timeout: 180000,      // 🔧 3분으로 증가 (AI 처리 시간 고려)
    proxyTimeout: 180000, // 🔧 3분으로 증가 (AI 처리 시간 고려)
    onProxyReq: (proxyReq, req, res) => {
      // HTTP 요청만 로깅 (WebSocket 제외)
      if (isDebug) {
        const fullUrl = target + req.url;
        console.log('🚀 [PROXY REQUEST]', {
          method: req.method,
          originalUrl: req.url,
          targetUrl: fullUrl,
          timestamp: new Date().toISOString()
        });
      }
    },
    onProxyReqWs: (proxyReq, req, socket, options, head) => {
      // WebSocket 연결 로깅 (디버그 모드에서만)
      if (isDebug) {
        console.log('🔌 [WEBSOCKET PROXY]', {
          url: req.url,
          target: target + req.url,
          timestamp: new Date().toISOString()
        });
      }
    },
    onProxyRes: (proxyRes, req, res) => {
      // HTTP 응답 로깅 (디버그 모드에서만)
      if (isDebug) {
        console.log('📥 [PROXY RESPONSE]', {
          statusCode: proxyRes.statusCode,
          url: req.url,
          timestamp: new Date().toISOString()
        });
      }
    },
    onError: (err, req, res) => {
      // 에러 로깅 (디버그 모드에서만)
      if (isDebug) {
        console.error('❌ [PROXY ERROR]', {
          message: err.message,
          code: err.code,
          url: req.url,
          timestamp: new Date().toISOString()
        });
      }

      // WebSocket 에러는 socket 처리, HTTP 에러는 res 처리
      if (res && typeof res.writeHead === 'function') {
        // HTTP 에러 응답
        if (!res.headersSent) {
          res.writeHead(502, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({
            error: 'Proxy Error',
            message: err.message
          }));
        }
      }
      // WebSocket 에러는 조용히 무시 (재연결 시도는 클라이언트가 처리)
    }
  });

  // /api 경로만 프록시 적용
  app.use(proxyMiddleware);

  console.log('✅ setupProxy.js 설정 완료');
  console.log('📌 프록시 경로: /api/* -> ' + target);
  console.log('⏭️  HMR WebSocket: /ws 경로는 프록시하지 않음');

  // 테스트용 엔드포인트 추가
  app.use('/debug/proxy', (req, res) => {
    res.json({
      message: 'Proxy is working',
      target: target,
      timestamp: new Date().toISOString(),
      env: process.env.NODE_ENV,
      reactAppApiUrl: process.env.REACT_APP_API_URL
    });
  });
};