/**
 * Image Placeholder Slide Layout Template
 * 
 * Layout: image-placeholder (Image-centric slide)
 * - Primary use: Visual content, diagrams
 * - Elements: Title, image placeholder, caption
 */

const logger = require('../utils/logger');

class ImagePlaceholderLayout {
  /**
   * Render image placeholder slide
   * @param {Object} slide - PptxGenJS slide object
   * @param {Object} slideSpec - StructuredSlide data
   * @param {Object} theme - Theme configuration
   */
  render(slide, slideSpec, theme) {
    logger.debug('Rendering image-placeholder slide', { title: slideSpec.title });

    // Background
    slide.background = { color: 'FFFFFF' };

    // Title
    slide.addText(slideSpec.title, {
      x: 0.5,
      y: 0.4,
      w: 9.0,
      h: 0.6,
      fontSize: 32,
      bold: true,
      color: theme.primaryColor,
      fontFace: theme.fontFamily
    });

    // Title underline
    slide.addShape('rect', {
      x: 0.5,
      y: 1.05,
      w: 2.0,
      h: 0.05,
      fill: { color: theme.accentColor }
    });

    const imageSpec = slideSpec.visual_elements?.image;

    if (imageSpec && imageSpec.url && imageSpec.url !== 'placeholder') {
      // Render actual image
      this._renderImage(slide, imageSpec);
    } else {
      // Render placeholder
      this._renderPlaceholder(slide, imageSpec, theme);
    }
  }

  /**
   * Render actual image
   * @private
   */
  _renderImage(slide, imageSpec) {
    try {
      slide.addImage({
        path: imageSpec.url,
        x: 1.5,
        y: 1.5,
        w: 7.0,
        h: 3.2
      });

      // Caption (if provided)
      if (imageSpec.alt) {
        slide.addText(imageSpec.alt, {
          x: 1.5,
          y: 4.8,
          w: 7.0,
          h: 0.4,
          fontSize: 12,
          color: '6B7280', // gray-500
          align: 'center',
          italic: true
        });
      }
    } catch (error) {
      logger.error('Failed to add image, rendering placeholder', { error: error.message });
      this._renderPlaceholder(slide, imageSpec);
    }
  }

  /**
   * Render image placeholder
   * @private
   */
  _renderPlaceholder(slide, imageSpec, theme) {
    // Placeholder box
    slide.addShape('rect', {
      x: 1.5,
      y: 1.5,
      w: 7.0,
      h: 3.2,
      fill: { color: 'F3F4F6' }, // gray-100
      line: { color: 'D1D5DB', width: 2, dashType: 'dash' } // gray-300
    });

    // Placeholder icon (image icon)
    slide.addText('🖼', {
      x: 4.5,
      y: 2.6,
      w: 1.0,
      h: 1.0,
      fontSize: 48,
      align: 'center',
      valign: 'middle'
    });

    // Placeholder text
    const placeholderText = imageSpec?.alt || '[이미지 영역]';
    slide.addText(placeholderText, {
      x: 1.5,
      y: 4.8,
      w: 7.0,
      h: 0.4,
      fontSize: 14,
      color: '9CA3AF', // gray-400
      align: 'center',
      italic: true
    });
  }
}

module.exports = ImagePlaceholderLayout;
