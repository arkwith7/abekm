const themes = require('../../config/themes.json');

/**
 * Theme Manager - handles color themes and styling
 */
class ThemeManager {
  constructor() {
    this.themes = themes;
  }

  /**
   * Get theme by style name
   */
  getTheme(styleName = 'business') {
    const mapping = {
      'business': 'business',
      'minimal': 'minimal',
      'modern': 'modern_green',
      'playful': 'playful_violet',
      'corporate': 'corporate_blue',
      'professional': 'professional_gray'
    };

    const themeName = mapping[styleName] || 'business';
    return this.themes[themeName] || this.themes.business;
  }

  /**
   * Convert hex color to RGB object for PptxGenJS
   */
  hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : null;
  }

  /**
   * Get chart colors for theme
   */
  getChartColors(styleName = 'business') {
    const theme = this.getTheme(styleName);
    return theme.chartColors || ['0066CC', '6699FF', 'FF9900', '00B050', '7030A0'];
  }
}

module.exports = new ThemeManager();
