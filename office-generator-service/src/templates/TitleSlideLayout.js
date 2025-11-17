/**
 * Title Slide Layout Template
 * 
 * Layout: title (Full-screen title slide)
 * - Primary use: Presentation cover
 * - Elements: Title, subtitle (from content), background color
 */

const logger = require('../utils/logger');

class TitleSlideLayout {
  /**
   * Render title slide
   * @param {Object} slide - PptxGenJS slide object
   * @param {Object} slideSpec - StructuredSlide data
   * @param {Object} theme - Theme configuration
   */
  render(slide, slideSpec, theme) {
    logger.debug('Rendering title slide', { title: slideSpec.title });

    // Background
    slide.background = { fill: theme.primaryColor };

    // Main title
    slide.addText(slideSpec.title, {
      x: 0.5,
      y: 2.0,
      w: 9.0,
      h: 1.5,
      fontSize: 44,
      bold: true,
      color: 'FFFFFF',
      align: 'center',
      valign: 'middle',
      fontFace: theme.fontFamily
    });

    // Subtitle (from content field)
    if (slideSpec.content) {
      slide.addText(slideSpec.content, {
        x: 0.5,
        y: 3.7,
        w: 9.0,
        h: 0.8,
        fontSize: 20,
        color: 'E5E7EB', // gray-200
        align: 'center',
        valign: 'middle',
        fontFace: theme.fontFamily
      });
    }

    // Footer line
    slide.addShape('rect', {
      x: 0.5,
      y: 5.0,
      w: 9.0,
      h: 0.05,
      fill: { color: 'FFFFFF', transparency: 50 }
    });
  }
}

module.exports = TitleSlideLayout;
