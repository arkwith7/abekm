const { formatErrorResponse } = require('../utils/errors');
const logger = require('../utils/logger');
const metricsCollector = require('../utils/metrics');

/**
 * Global error handler middleware
 */
function errorHandler(err, req, res, next) {
  // Log error
  const logContext = {
    requestId: req.requestId,
    method: req.method,
    path: req.path,
    error: err.message,
    code: err.code
  };

  if (err.statusCode >= 500) {
    logger.error('Server error', logContext);
  } else {
    logger.warn('Client error', logContext);
  }

  // Record error metrics
  metricsCollector.recordError(err.code || 'UNKNOWN');

  // Send error response
  const statusCode = err.statusCode || 500;
  const errorResponse = formatErrorResponse(err, req.requestId);

  res.status(statusCode).json(errorResponse);
}

/**
 * 404 handler for unmatched routes
 */
function notFoundHandler(req, res) {
  res.status(404).json({
    success: false,
    error: 'Route not found',
    code: 'NOT_FOUND',
    path: req.path,
    requestId: req.requestId
  });
}

module.exports = {
  errorHandler,
  notFoundHandler
};
