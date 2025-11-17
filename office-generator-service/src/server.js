const express = require('express');
const config = require('./config');
const logger = require('./utils/logger');
const { requestIdMiddleware } = require('./middleware/request-id');
const { apiKeyMiddleware } = require('./middleware/api-key');
const { errorHandler } = require('./middleware/error-handler');
const apiRoutes = require('./routes');

const app = express();

// Middleware
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(requestIdMiddleware);
app.use(apiKeyMiddleware);

// Routes
app.use('/api', apiRoutes);

// Root endpoint
app.get('/', (req, res) => {
  res.json({
    service: 'Office Generator Service',
    version: '1.0.0',
    status: 'running',
    timestamp: new Date().toISOString()
  });
});

// Health check
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    uptime: process.uptime(),
    timestamp: new Date().toISOString()
  });
});

// Error handling
app.use(errorHandler);

// Start server
const PORT = config.port;
const server = app.listen(PORT, () => {
  logger.info(`Office Generator Service started on port ${PORT}`, {
    env: config.env,
    nodeVersion: process.version
  });
});

// Graceful shutdown
process.on('SIGTERM', () => {
  logger.info('SIGTERM received, shutting down gracefully...');
  server.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });
});

process.on('SIGINT', () => {
  logger.info('SIGINT received, shutting down gracefully...');
  server.close(() => {
    logger.info('Server closed');
    process.exit(0);
  });
});

// Unhandled promise rejections
process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled Rejection', { reason, promise });
});

// Uncaught exceptions
process.on('uncaughtException', (error) => {
  logger.error('Uncaught Exception', { error: error.message, stack: error.stack });
  process.exit(1);
});

module.exports = app;
