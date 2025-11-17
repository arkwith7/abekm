/**
 * Standard error classes for the service
 */

class AppError extends Error {
  constructor(message, statusCode = 500, code = 'INTERNAL_ERROR') {
    super(message);
    this.statusCode = statusCode;
    this.code = code;
    this.isOperational = true;
    Error.captureStackTrace(this, this.constructor);
  }
}

class ValidationError extends AppError {
  constructor(message, details = null) {
    super(message, 400, 'VALIDATION_ERROR');
    this.details = details;
  }
}

class NotFoundError extends AppError {
  constructor(resource) {
    super(`${resource} not found`, 404, 'NOT_FOUND');
  }
}

class UnauthorizedError extends AppError {
  constructor(message = 'Unauthorized') {
    super(message, 401, 'UNAUTHORIZED');
  }
}

class ServiceUnavailableError extends AppError {
  constructor(message = 'Service temporarily unavailable') {
    super(message, 503, 'SERVICE_UNAVAILABLE');
  }
}

class GenerationError extends AppError {
  constructor(message, generator = 'unknown') {
    super(message, 500, 'GENERATION_ERROR');
    this.generator = generator;
  }
}

/**
 * Format error response
 */
function formatErrorResponse(error, requestId = null) {
  const response = {
    success: false,
    error: error.message || 'An error occurred',
    code: error.code || 'INTERNAL_ERROR',
    requestId
  };

  // Add details for validation errors
  if (error.details) {
    response.details = error.details;
  }

  // Add stack trace in development
  if (process.env.NODE_ENV === 'development' && error.stack) {
    response.stack = error.stack;
  }

  return response;
}

module.exports = {
  AppError,
  ValidationError,
  NotFoundError,
  UnauthorizedError,
  ServiceUnavailableError,
  GenerationError,
  formatErrorResponse
};
