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

  // Docker 환경 (REACT_APP_API_URL이 외부 URL인 경우)에서는 프록시 비활성화
  if (target && (target.includes('15.165.163.233') || target.startsWith('http://15.165'))) {
    console.log('🐳 Docker 환경 감지 - setupProxy 비활성화 (nginx가 프록시 담당)');
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

  const proxyMiddleware = createProxyMiddleware({
    target: target,
    changeOrigin: true,
    secure: false,
    logLevel: isDebug ? 'debug' : 'info',
    timeout: 30000,
    proxyTimeout: 30000,
    onProxyReq: (proxyReq, req, res) => {
      const fullUrl = target + req.url;
      console.log('🚀 [PROXY REQUEST]', {
        method: req.method,
        originalUrl: req.url,
        targetUrl: fullUrl,
        headers: req.headers,
        timestamp: new Date().toISOString()
      });
    },
    onProxyRes: (proxyRes, req, res) => {
      console.log('📥 [PROXY RESPONSE]', {
        statusCode: proxyRes.statusCode,
        statusMessage: proxyRes.statusMessage,
        url: req.url,
        headers: proxyRes.headers,
        timestamp: new Date().toISOString()
      });
    },
    onError: (err, req, res) => {
      console.error('❌ [PROXY ERROR]', {
        message: err.message,
        code: err.code,
        url: req.url,
        target: target,
        timestamp: new Date().toISOString()
      });

      // 에러 응답 전송
      if (!res.headersSent) {
        res.writeHead(502, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          error: 'Proxy Error',
          message: err.message,
          target: target,
          url: req.url
        }));
      }
    }
  });

  app.use('/api', proxyMiddleware);

  console.log('✅ setupProxy.js 설정 완료');

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