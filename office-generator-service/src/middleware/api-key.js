const { UnauthorizedError } = require('../utils/errors');

/**
 * API Key authentication middleware
 */
function apiKey(req, res, next) {
  // Skip in development if API_KEY not set
  if (process.env.NODE_ENV === 'development' && !process.env.API_KEY) {
    return next();
  }

  const providedKey = req.headers['x-api-key'];
  const validKey = process.env.API_KEY;

  if (!validKey) {
    // API key not configured - allow all (log warning)
    req.log?.warn('API_KEY not configured - authentication disabled');
    return next();
  }

  if (!providedKey || providedKey !== validKey) {
    return next(new UnauthorizedError('Invalid or missing API key'));
  }

  next();
}

module.exports = apiKey;
