const express = require('express');
const { generatePptx } = require('../generators/pptx/builder');
const StructuredToPptxConverter = require('../converters/structured-to-pptx');
const { ValidationError } = require('../utils/errors');
const { recordMetrics } = require('../utils/metrics');
const logger = require('../utils/logger');

const router = express.Router();

/**
 * Validate DeckSpec
 */
function validateDeckSpec(deckSpec) {
  if (!deckSpec || typeof deckSpec !== 'object') {
    throw new ValidationError('Invalid DeckSpec: must be an object');
  }

  if (!Array.isArray(deckSpec.slides) || deckSpec.slides.length === 0) {
    throw new ValidationError('Invalid DeckSpec: slides array is required');
  }

  deckSpec.slides.forEach((slide, index) => {
    if (!slide.type) {
      throw new ValidationError(`Slide ${index + 1} missing type`);
    }
    if (!slide.title && slide.type !== 'title') {
      throw new ValidationError(`Slide ${index + 1} missing title`);
    }
  });
}

/**
 * POST /api/pptx/generate - Generate PowerPoint presentation
 * 
 * Request body:
 * {
 *   "deckSpec": {
 *     "title": "string",
 *     "style": "business|modern|playful|minimal|dark|vibrant",
 *     "metadata": { "author": "string", "company": "string" },
 *     "slides": [
 *       {
 *         "type": "title|agenda|content|thanks",
 *         "title": "string",
 *         "key_message": "string (optional)",
 *         "bullets": ["string"],
 *         "diagram": { "chart": {...} }
 *       }
 *     ]
 *   }
 * }
 * 
 * Response: Binary PPTX file
 */
router.post('/generate', async (req, res, next) => {
  const startTime = Date.now();

  try {
    const { deckSpec } = req.body;

    logger.info('Received PPTX generation request', {
      requestId: req.requestId,
      slideCount: deckSpec?.slides?.length,
      style: deckSpec?.style
    });

    // Validate DeckSpec
    validateDeckSpec(deckSpec);

    // Generate PPTX
    const buffer = await generatePptx(deckSpec);

    // Record metrics
    const duration = Date.now() - startTime;
    recordMetrics('pptx_generation', {
      slideCount: deckSpec.slides.length,
      style: deckSpec.style || 'business',
      durationMs: duration,
      sizeBytes: buffer.length
    });

    // Send file
    const filename = `${(deckSpec.title || 'presentation').replace(/[^a-zA-Z0-9가-힣]/g, '_')}.pptx`;

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.setHeader('Content-Length', buffer.length);
    res.setHeader('X-Generation-Time-Ms', duration);
    res.send(buffer);

    logger.info('PPTX generated successfully', {
      requestId: req.requestId,
      filename,
      sizeBytes: buffer.length,
      durationMs: duration
    });
  } catch (error) {
    next(error);
  }
});

/**
 * GET /api/pptx/health - Health check
 */
router.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'pptx-generator',
    timestamp: new Date().toISOString()
  });
});

/**
 * POST /api/pptx/convert - Convert StructuredOutline to PPTX
 * 
 * Request body:
 * {
 *   "outlineJson": {
 *     "title": "string",
 *     "theme": "business|modern|playful",
 *     "slides": [
 *       {
 *         "title": "string",
 *         "content": "string",
 *         "layout": "title|title-and-bullets|two-column-grid|divider|image-placeholder",
 *         "visual_elements": { ... }
 *       }
 *     ],
 *     "metadata": { ... }
 *   },
 *   "options": {
 *     "theme": "business"  // Optional override
 *   }
 * }
 * 
 * Response: Binary PPTX file
 */
router.post('/convert', async (req, res, next) => {
  const startTime = Date.now();

  try {
    const { outlineJson, options = {} } = req.body;

    logger.info('Received StructuredOutline conversion request', {
      requestId: req.requestId,
      title: outlineJson?.title,
      slideCount: outlineJson?.slides?.length,
      theme: outlineJson?.theme || options.theme
    });

    // Validate outlineJson
    if (!outlineJson || typeof outlineJson !== 'object') {
      throw new ValidationError('outlineJson is required and must be an object');
    }

    // Convert using StructuredToPptxConverter
    const buffer = await StructuredToPptxConverter.convert(outlineJson, options);

    // Record metrics
    const duration = Date.now() - startTime;
    recordMetrics('pptx_conversion', {
      slideCount: outlineJson.slides.length,
      theme: outlineJson.theme || options.theme || 'business',
      durationMs: duration,
      sizeBytes: buffer.length
    });

    // Send file
    const filename = `${(outlineJson.title || 'presentation').replace(/[^a-zA-Z0-9가-힣]/g, '_')}.pptx`;

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.presentationml.presentation');
    res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
    res.setHeader('Content-Length', buffer.length);
    res.setHeader('X-Generation-Time-Ms', duration);
    res.send(buffer);

    logger.info('StructuredOutline converted successfully', {
      requestId: req.requestId,
      filename,
      sizeBytes: buffer.length,
      durationMs: duration
    });
  } catch (error) {
    next(error);
  }
});

module.exports = router;
