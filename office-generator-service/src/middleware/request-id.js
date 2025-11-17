const { v4: uuidv4 } = require('uuid');

/**
 * Request ID middleware - adds unique ID to each request
 */
function requestId(req, res, next) {
  // Use existing request ID from header or generate new one
  req.requestId = req.headers['x-request-id'] || uuidv4();

  // Add to response headers
  res.setHeader('X-Request-Id', req.requestId);

  // Attach logger with request context
  req.log = require('../utils/logger').withRequest(req.requestId);

  next();
}

module.exports = requestId;
