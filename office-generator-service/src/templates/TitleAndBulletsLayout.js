/**
 * Title and Bullets Slide Layout Template
 * 
 * Layout: title-and-bullets (Standard content slide)
 * - Primary use: Text-heavy content
 * - Elements: Title, bullet points, optional icons
 */

const { getIconConfig } = require('../utils/icons/icon-fetcher');
const logger = require('../utils/logger');

class TitleAndBulletsLayout {
  /**
   * Render title and bullets slide
   * @param {Object} slide - PptxGenJS slide object
   * @param {Object} slideSpec - StructuredSlide data
   * @param {Object} theme - Theme configuration
   */
  render(slide, slideSpec, theme) {
    logger.debug('Rendering title-and-bullets slide', { title: slideSpec.title });

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

    // Bullets
    const bullets = slideSpec.visual_elements?.bullets || [];
    const hasIcons = slideSpec.visual_elements?.icons && slideSpec.visual_elements.icons.length > 0;

    if (bullets.length > 0) {
      this._renderBullets(slide, bullets, hasIcons, slideSpec.visual_elements?.icons, theme);
    }

    // Fallback: render content as paragraph if no bullets
    if (bullets.length === 0 && slideSpec.content) {
      slide.addText(slideSpec.content, {
        x: 0.8,
        y: 1.5,
        w: 8.4,
        h: 3.5,
        fontSize: 16,
        color: '374151', // gray-700
        fontFace: theme.fontFamily,
        valign: 'top'
      });
    }
  }

  /**
   * Render bullet points with optional icons
   * @private
   */
  _renderBullets(slide, bullets, hasIcons, icons, theme) {
    const startY = 1.5;
    const lineHeight = 0.6;
    const maxBullets = Math.min(bullets.length, 8); // Limit to prevent overflow

    bullets.slice(0, maxBullets).forEach((bullet, index) => {
      const y = startY + (index * lineHeight);

      if (hasIcons && icons[index]) {
        // Icon + text
        const iconConfig = getIconConfig(icons[index]);

        // Icon
        slide.addText(iconConfig.text, {
          x: 0.8,
          y: y,
          w: 0.4,
          h: 0.5,
          fontSize: iconConfig.options.fontSize,
          color: iconConfig.options.color,
          bold: iconConfig.options.bold,
          align: 'center',
          valign: 'middle'
        });

        // Bullet text
        slide.addText(bullet, {
          x: 1.3,
          y: y,
          w: 7.9,
          h: 0.5,
          fontSize: 16,
          color: '374151', // gray-700
          fontFace: theme.fontFamily,
          valign: 'middle'
        });
      } else {
        // Standard bullet
        slide.addText(bullet, {
          x: 0.8,
          y: y,
          w: 8.4,
          h: 0.5,
          fontSize: 16,
          color: '374151', // gray-700
          fontFace: theme.fontFamily,
          bullet: { type: 'bullet', code: '2022' }, // Bullet character
          valign: 'middle'
        });
      }
    });
  }
}

module.exports = TitleAndBulletsLayout;
