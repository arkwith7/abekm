/**
 * StructuredOutline to PPTX Converter
 * 
 * Converts StructuredOutline (from Backend) to PowerPoint presentation
 * using layout-specific templates
 */

const PptxGenJS = require('pptxgenjs');
const ThemeManager = require('../generators/pptx/theme-manager');
const TitleSlideLayout = require('../templates/TitleSlideLayout');
const TitleAndBulletsLayout = require('../templates/TitleAndBulletsLayout');
const TwoColumnGridLayout = require('../templates/TwoColumnGridLayout');
const DividerSlideLayout = require('../templates/DividerSlideLayout');
const ImagePlaceholderLayout = require('../templates/ImagePlaceholderLayout');
const { AppError } = require('../utils/errors');
const logger = require('../utils/logger');

/**
 * StructuredOutline to PPTX Converter
 */
class StructuredToPptxConverter {
  constructor(outlineJson, options = {}) {
    this.outline = outlineJson;
    this.options = options;
    this.pptx = new PptxGenJS();
    this.themeManager = new ThemeManager();
    this.theme = null;

    // Layout renderers
    this.layoutRenderers = {
      'title': new TitleSlideLayout(),
      'title-and-bullets': new TitleAndBulletsLayout(),
      'two-column-grid': new TwoColumnGridLayout(),
      'divider': new DividerSlideLayout(),
      'image-placeholder': new ImagePlaceholderLayout()
    };
  }

  /**
   * Convert StructuredOutline to PPTX buffer
   * @returns {Promise<Buffer>} PPTX file buffer
   */
  async convert() {
    try {
      logger.info('Converting StructuredOutline to PPTX', {
        title: this.outline.title,
        slideCount: this.outline.slides?.length,
        theme: this.outline.theme
      });

      // Validate outline
      this._validateOutline();

      // Initialize theme
      const themeName = this.outline.theme || this.options.theme || 'business';
      this.theme = this.themeManager.getTheme(themeName);

      // Set presentation metadata
      this._setMetadata();

      // Define presentation layout (16:9 aspect ratio)
      this.pptx.defineLayout({ name: 'CUSTOM', width: 10, height: 5.625 });
      this.pptx.layout = 'CUSTOM';

      // Render all slides
      this._renderAllSlides();

      // Generate PPTX buffer
      const buffer = await this._generateBuffer();

      logger.info('PPTX conversion completed', {
        slideCount: this.pptx.slides.length,
        sizeBytes: buffer.length
      });

      return buffer;
    } catch (error) {
      logger.error('PPTX conversion failed', {
        error: error.message,
        stack: error.stack
      });
      throw new AppError(`PPTX conversion failed: ${error.message}`, 500);
    }
  }

  /**
   * Validate StructuredOutline structure
   * @private
   */
  _validateOutline() {
    if (!this.outline || typeof this.outline !== 'object') {
      throw new AppError('Invalid StructuredOutline: must be an object', 400);
    }

    if (!this.outline.title || typeof this.outline.title !== 'string') {
      throw new AppError('Invalid StructuredOutline: title is required', 400);
    }

    if (!Array.isArray(this.outline.slides) || this.outline.slides.length === 0) {
      throw new AppError('Invalid StructuredOutline: slides array is required', 400);
    }

    // Validate each slide
    this.outline.slides.forEach((slide, index) => {
      if (!slide.layout) {
        throw new AppError(`Slide ${index + 1}: layout is required`, 400);
      }

      if (!this.layoutRenderers[slide.layout]) {
        throw new AppError(
          `Slide ${index + 1}: unsupported layout '${slide.layout}'`,
          400
        );
      }

      if (!slide.title || typeof slide.title !== 'string') {
        throw new AppError(`Slide ${index + 1}: title is required`, 400);
      }
    });
  }

  /**
   * Set presentation metadata
   * @private
   */
  _setMetadata() {
    this.pptx.author = this.outline.metadata?.author || 'WKMS AI Agent';
    this.pptx.company = this.outline.metadata?.company || 'WKMS';
    this.pptx.title = this.outline.title;
    this.pptx.subject = this.outline.metadata?.subject || 'AI Generated Presentation';

    // Additional metadata if available
    if (this.outline.created_at) {
      this.pptx.revision = new Date(this.outline.created_at).toISOString().split('T')[0];
    }
  }

  /**
   * Render all slides using layout-specific renderers
   * @private
   */
  _renderAllSlides() {
    const slides = this.outline.slides || [];

    slides.forEach((slideSpec, index) => {
      try {
        logger.debug('Rendering slide', {
          index: index + 1,
          layout: slideSpec.layout,
          title: slideSpec.title
        });

        // Create new slide
        const slide = this.pptx.addSlide();

        // Get appropriate renderer
        const renderer = this.layoutRenderers[slideSpec.layout];

        if (!renderer) {
          logger.warn(`No renderer for layout '${slideSpec.layout}', using default`);
          this._renderDefaultSlide(slide, slideSpec);
          return;
        }

        // Render using layout-specific template
        renderer.render(slide, slideSpec, this.theme);

      } catch (error) {
        logger.error('Slide rendering failed', {
          index: index + 1,
          layout: slideSpec.layout,
          error: error.message
        });

        // Add error slide instead of failing completely
        this._renderErrorSlide(slide, slideSpec, error);
      }
    });
  }

  /**
   * Render default fallback slide
   * @private
   */
  _renderDefaultSlide(slide, slideSpec) {
    slide.background = { color: 'FFFFFF' };

    slide.addText(slideSpec.title, {
      x: 0.5,
      y: 0.5,
      w: 9.0,
      h: 0.8,
      fontSize: 28,
      bold: true,
      color: this.theme.primaryColor,
      fontFace: this.theme.fontFamily
    });

    if (slideSpec.content) {
      slide.addText(slideSpec.content, {
        x: 0.5,
        y: 1.5,
        w: 9.0,
        h: 3.5,
        fontSize: 16,
        color: '374151',
        fontFace: this.theme.fontFamily
      });
    }
  }

  /**
   * Render error slide
   * @private
   */
  _renderErrorSlide(slide, slideSpec, error) {
    slide.background = { color: 'FEF2F2' }; // red-50

    slide.addText('⚠ 슬라이드 렌더링 오류', {
      x: 0.5,
      y: 1.0,
      w: 9.0,
      h: 0.8,
      fontSize: 24,
      bold: true,
      color: 'DC2626', // red-600
      align: 'center'
    });

    slide.addText(`슬라이드: ${slideSpec.title}\n레이아웃: ${slideSpec.layout}\n오류: ${error.message}`, {
      x: 1.0,
      y: 2.0,
      w: 8.0,
      h: 2.0,
      fontSize: 14,
      color: '991B1B', // red-800
      align: 'center',
      valign: 'top'
    });
  }

  /**
   * Generate PPTX buffer
   * @private
   * @returns {Promise<Buffer>}
   */
  async _generateBuffer() {
    return new Promise((resolve, reject) => {
      this.pptx.write({ outputType: 'nodebuffer' })
        .then(buffer => {
          if (!Buffer.isBuffer(buffer)) {
            reject(new Error('Generated PPTX is not a valid buffer'));
            return;
          }
          resolve(buffer);
        })
        .catch(error => {
          logger.error('PPTX buffer generation failed', { error: error.message });
          reject(new AppError(`PPTX buffer generation failed: ${error.message}`, 500));
        });
    });
  }

  /**
   * Static method to convert StructuredOutline directly
   * @param {Object} outlineJson - StructuredOutline object
   * @param {Object} options - Conversion options
   * @returns {Promise<Buffer>} PPTX buffer
   */
  static async convert(outlineJson, options = {}) {
    const converter = new StructuredToPptxConverter(outlineJson, options);
    return converter.convert();
  }
}

module.exports = StructuredToPptxConverter;
