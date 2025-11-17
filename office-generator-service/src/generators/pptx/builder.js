const PptxGenJS = require('pptxgenjs');
const ThemeManager = require('./theme-manager');
const SlideRenderer = require('./slide-renderer');
const { AppError } = require('../../utils/errors');
const logger = require('../../utils/logger');

/**
 * Main PPTX Builder - orchestrates entire presentation generation
 */
class PptxBuilder {
  constructor(deckSpec) {
    this.spec = deckSpec;
    this.pptx = new PptxGenJS();
    this.themeManager = new ThemeManager();
    this.theme = null;
    this.renderer = null;
  }

  /**
   * Build the presentation
   */
  async build() {
    try {
      logger.info('Building PPTX presentation', {
        style: this.spec.style,
        slideCount: this.spec.slides?.length
      });

      // Initialize theme and renderer
      this.theme = this.themeManager.getTheme(this.spec.style || 'business');
      this.renderer = new SlideRenderer(this.pptx, this.theme);

      // Set presentation metadata
      this._setMetadata();

      // Define presentation layout
      this.pptx.defineLayout({ name: 'CUSTOM', width: 10, height: 5.625 });
      this.pptx.layout = 'CUSTOM';

      // Render slides
      this._renderSlides();

      // Generate file
      const buffer = await this._generateBuffer();

      logger.info('PPTX presentation built successfully', {
        slideCount: this.pptx.slides.length,
        sizeBytes: buffer.length
      });

      return buffer;
    } catch (error) {
      logger.error('PPTX generation failed', { error: error.message, stack: error.stack });
      throw new AppError(`PPTX generation failed: ${error.message}`, 500);
    }
  }

  /**
   * Set presentation metadata
   */
  _setMetadata() {
    this.pptx.author = this.spec.metadata?.author || 'WKMS AI Agent';
    this.pptx.company = this.spec.metadata?.company || 'WKMS';
    this.pptx.title = this.spec.title || 'AI Generated Presentation';
    this.pptx.subject = this.spec.metadata?.subject || 'Document Summary';
  }

  /**
   * Render all slides
   */
  _renderSlides() {
    const slides = this.spec.slides || [];

    if (slides.length === 0) {
      throw new AppError('No slides specified in DeckSpec', 400);
    }

    slides.forEach((slideSpec, index) => {
      try {
        const slide = this.pptx.addSlide();

        // Set background for all slides except special types
        if (!['title', 'thanks'].includes(slideSpec.type)) {
          slide.background = { color: 'FFFFFF' };
        }

        // Route to appropriate renderer
        switch (slideSpec.type) {
          case 'title':
            this.renderer.renderTitleSlide(slide, slideSpec);
            break;
          case 'agenda':
            this.renderer.renderAgendaSlide(slide, slideSpec);
            break;
          case 'thanks':
            this.renderer.renderThanksSlide(slide, slideSpec);
            break;
          case 'content':
          default:
            this.renderer.renderContentSlide(slide, slideSpec);
            break;
        }

        // Add footer with slide number
        this._addFooter(slide, index + 1, slides.length);
      } catch (error) {
        logger.error(`Error rendering slide ${index + 1}`, {
          type: slideSpec.type,
          error: error.message
        });
        throw new AppError(`Slide ${index + 1} rendering failed: ${error.message}`, 500);
      }
    });
  }

  /**
   * Add footer with slide number
   */
  _addFooter(slide, current, total) {
    // Skip footer for title and thanks slides
    if (current === 1 || current === total) {
      return;
    }

    slide.addText(`${current}`, {
      x: 9.2,
      y: 5.2,
      w: 0.6,
      h: 0.3,
      fontSize: 10,
      color: '999999',
      align: 'right',
      valign: 'bottom'
    });
  }

  /**
   * Generate presentation buffer
   */
  async _generateBuffer() {
    return new Promise((resolve, reject) => {
      this.pptx.write({ outputType: 'nodebuffer' })
        .then(buffer => resolve(buffer))
        .catch(error => reject(new AppError(`Buffer generation failed: ${error.message}`, 500)));
    });
  }
}

/**
 * Generate PPTX from DeckSpec
 */
async function generatePptx(deckSpec) {
  const builder = new PptxBuilder(deckSpec);
  return await builder.build();
}

module.exports = { PptxBuilder, generatePptx };
