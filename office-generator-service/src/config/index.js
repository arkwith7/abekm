require('dotenv').config();

const config = {
  // Server
  env: process.env.NODE_ENV || 'development',
  port: parseInt(process.env.PORT, 10) || 3001,
  host: process.env.HOST || '0.0.0.0',

  // Security
  apiKey: process.env.API_KEY || null,
  corsOrigin: process.env.CORS_ORIGIN ? process.env.CORS_ORIGIN.split(',') : ['*'],
  maxRequestSize: process.env.MAX_REQUEST_SIZE || '10mb',

  // File Generation
  outputDir: process.env.OUTPUT_DIR || '/tmp/office-output',
  maxSlides: parseInt(process.env.MAX_SLIDES, 10) || 60,
  maxBulletsPerSlide: parseInt(process.env.MAX_BULLETS_PER_SLIDE, 10) || 10,
  fileRetentionSeconds: parseInt(process.env.FILE_RETENTION_SECONDS, 10) || 300,

  // Features
  features: {
    pptx: process.env.ENABLE_PPTX === 'true' || true,
    docx: process.env.ENABLE_DOCX === 'true' || false,
    xlsx: process.env.ENABLE_XLSX === 'true' || false
  },

  // Monitoring
  enableMetrics: process.env.ENABLE_METRICS === 'true' || true,
  metricsPort: parseInt(process.env.METRICS_PORT, 10) || 9090,

  // Logging
  logLevel: process.env.LOG_LEVEL || 'info',
  logFormat: process.env.LOG_FORMAT || 'dev'
};

// Validate required config
if (config.env === 'production' && !config.apiKey) {
  console.warn('⚠️  Warning: API_KEY not set in production environment');
}

module.exports = config;
