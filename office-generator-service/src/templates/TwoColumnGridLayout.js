/**
 * Two-Column Grid Slide Layout Template
 * 
 * Layout: two-column-grid (Multi-column content)
 * - Primary use: Comparing items, feature lists
 * - Elements: Title, grid items (left/right columns)
 */

const { getIconConfig } = require('../utils/icons/icon-fetcher');
const logger = require('../utils/logger');

class TwoColumnGridLayout {
  /**
   * Render two-column grid slide
   * @param {Object} slide - PptxGenJS slide object
   * @param {Object} slideSpec - StructuredSlide data
   * @param {Object} theme - Theme configuration
   */
  render(slide, slideSpec, theme) {
    logger.debug('Rendering two-column-grid slide', { title: slideSpec.title });

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

    // Grid items
    const grid = slideSpec.visual_elements?.grid || [];

    if (grid.length > 0) {
      this._renderGrid(slide, grid, theme);
    } else if (slideSpec.content) {
      // Fallback: render content as text
      slide.addText(slideSpec.content, {
        x: 0.8,
        y: 1.5,
        w: 8.4,
        h: 3.5,
        fontSize: 16,
        color: '374151',
        fontFace: theme.fontFamily,
        valign: 'top'
      });
    }
  }

  /**
   * Render grid items in two columns
   * @private
   */
  _renderGrid(slide, gridItems, theme) {
    const columnWidth = 4.0;
    const columnGap = 0.5;
    const leftX = 0.8;
    const rightX = leftX + columnWidth + columnGap;
    const startY = 1.5;
    const itemHeight = 1.0;
    const itemGap = 0.3;

    gridItems.forEach((item, index) => {
      const isLeft = index % 2 === 0;
      const x = isLeft ? leftX : rightX;
      const row = Math.floor(index / 2);
      const y = startY + (row * (itemHeight + itemGap));

      // Don't render if it would overflow the slide
      if (y + itemHeight > 5.2) {
        logger.warn('Grid item would overflow slide, skipping', { index, y });
        return;
      }

      // Item container (subtle border)
      slide.addShape('rect', {
        x: x,
        y: y,
        w: columnWidth,
        h: itemHeight,
        fill: { color: 'F9FAFB' }, // gray-50
        line: { color: 'E5E7EB', width: 1 } // gray-200
      });

      // Icon (if provided)
      if (item.icon) {
        const iconConfig = getIconConfig(item.icon);
        slide.addText(iconConfig.text, {
          x: x + 0.2,
          y: y + 0.1,
          w: 0.4,
          h: 0.4,
          fontSize: iconConfig.options.fontSize,
          color: iconConfig.options.color,
          align: 'center',
          valign: 'middle'
        });
      }

      // Label
      const labelX = item.icon ? x + 0.7 : x + 0.2;
      slide.addText(item.label, {
        x: labelX,
        y: y + 0.15,
        w: columnWidth - (item.icon ? 0.9 : 0.4),
        h: 0.35,
        fontSize: 14,
        bold: true,
        color: '1F2937', // gray-800
        fontFace: theme.fontFamily,
        valign: 'top'
      });

      // Value
      slide.addText(item.value, {
        x: labelX,
        y: y + 0.55,
        w: columnWidth - (item.icon ? 0.9 : 0.4),
        h: 0.35,
        fontSize: 12,
        color: '6B7280', // gray-500
        fontFace: theme.fontFamily,
        valign: 'top'
      });
    });
  }
}

module.exports = TwoColumnGridLayout;
