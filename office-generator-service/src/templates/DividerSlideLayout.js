/**
 * Divider Slide Layout Template
 * 
 * Layout: divider (Section separator)
 * - Primary use: Transition between sections
 * - Elements: Title, optional subtitle/content
 */

const logger = require('../utils/logger');

class DividerSlideLayout {
  /**
   * Render divider slide
   * @param {Object} slide - PptxGenJS slide object
   * @param {Object} slideSpec - StructuredSlide data
   * @param {Object} theme - Theme configuration
   */
  render(slide, slideSpec, theme) {
    logger.debug('Rendering divider slide', { title: slideSpec.title });

    // Background with gradient effect
    slide.background = { fill: theme.primaryColor };

    // Decorative shape (top-left)
    slide.addShape('rect', {
      x: 0,
      y: 0,
      w: 3.0,
      h: 0.3,
      fill: { color: theme.accentColor }
    });

    // Main title (centered)
    slide.addText(slideSpec.title, {
      x: 1.0,
      y: 2.3,
      w: 8.0,
      h: 1.0,
      fontSize: 40,
      bold: true,
      color: 'FFFFFF',
      align: 'center',
      valign: 'middle',
      fontFace: theme.fontFamily
    });

    // Subtitle/Content (if provided)
    if (slideSpec.content) {
      slide.addText(slideSpec.content, {
        x: 1.0,
        y: 3.5,
        w: 8.0,
        h: 0.7,
        fontSize: 18,
        color: 'E5E7EB', // gray-200
        align: 'center',
        valign: 'middle',
        fontFace: theme.fontFamily
      });
    }

    // Decorative shape (bottom-right)
    slide.addShape('rect', {
      x: 7.0,
      y: 5.325,
      w: 3.0,
      h: 0.3,
      fill: { color: theme.accentColor }
    });
  }
}

module.exports = DividerSlideLayout;
