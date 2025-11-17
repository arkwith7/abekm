const winston = require('winston');

const { combine, timestamp, printf, colorize, errors } = winston.format;

// Custom format for structured logging
const logFormat = printf(({ level, message, timestamp, requestId, ...metadata }) => {
  let msg = `${timestamp} [${level}]`;

  if (requestId) {
    msg += ` [${requestId}]`;
  }

  msg += `: ${message}`;

  // Add metadata if present
  if (Object.keys(metadata).length > 0) {
    msg += ` ${JSON.stringify(metadata)}`;
  }

  return msg;
});

// JSON format for production
const jsonFormat = combine(
  timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  errors({ stack: true }),
  winston.format.json()
);

// Human-readable format for development
const devFormat = combine(
  colorize(),
  timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
  errors({ stack: true }),
  logFormat
);

// Create logger instance
const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: process.env.LOG_FORMAT === 'json' ? jsonFormat : devFormat,
  transports: [
    new winston.transports.Console(),
  ],
  exitOnError: false
});

// Add file transport in production
if (process.env.NODE_ENV === 'production') {
  logger.add(new winston.transports.File({
    filename: 'logs/error.log',
    level: 'error',
    maxsize: 10485760, // 10MB
    maxFiles: 5
  }));

  logger.add(new winston.transports.File({
    filename: 'logs/combined.log',
    maxsize: 10485760,
    maxFiles: 5
  }));
}

// Create child logger with request context
logger.withRequest = (requestId) => {
  return logger.child({ requestId });
};

module.exports = logger;
