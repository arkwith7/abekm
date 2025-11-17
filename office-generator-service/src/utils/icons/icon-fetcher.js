/**
 * Icon Fetcher - Handles Lucide icon processing for PPTX
 * 
 * Since PptxGenJS doesn't support SVG directly, we:
 * 1. Use Unicode/emoji alternatives where possible
 * 2. Provide icon text representations
 * 3. Future: Convert SVG to images
 */

const logger = require('../logger');

/**
 * Map of Lucide icon names to Unicode/emoji equivalents
 */
const ICON_MAP = {
  // Common icons
  'check': '✓',
  'check-circle': '✓',
  'x': '✗',
  'x-circle': '✗',
  'alert-circle': '⚠',
  'alert-triangle': '⚠',
  'info': 'ⓘ',

  // Arrows
  'arrow-right': '→',
  'arrow-left': '←',
  'arrow-up': '↑',
  'arrow-down': '↓',
  'chevron-right': '›',
  'chevron-left': '‹',
  'chevron-up': '⌃',
  'chevron-down': '⌄',

  // Common business icons
  'user': '👤',
  'users': '👥',
  'calendar': '📅',
  'clock': '🕐',
  'mail': '✉',
  'phone': '☎',
  'map-pin': '📍',
  'home': '🏠',
  'briefcase': '💼',
  'folder': '📁',
  'file': '📄',
  'star': '⭐',
  'heart': '❤',

  // Tech icons
  'settings': '⚙',
  'search': '🔍',
  'download': '⬇',
  'upload': '⬆',
  'share': '↗',
  'link': '🔗',
  'wifi': '📶',
  'battery': '🔋',

  // Status icons
  'trending-up': '📈',
  'trending-down': '📉',
  'target': '🎯',
  'zap': '⚡',
  'award': '🏆',
  'thumbs-up': '👍',
  'thumbs-down': '👎',

  // Shapes
  'circle': '●',
  'square': '■',
  'triangle': '▲',
  'minus': '−',
  'plus': '+',

  // Default
  'default': '•'
};

/**
 * Get icon character for a given Lucide icon name
 * @param {string} iconName - Lucide icon name
 * @returns {string} Unicode character or emoji
 */
function getIconCharacter(iconName) {
  if (!iconName) {
    return ICON_MAP.default;
  }

  const normalized = iconName.toLowerCase().trim();
  const char = ICON_MAP[normalized] || ICON_MAP.default;

  logger.debug('Icon mapping', { iconName, normalized, char });

  return char;
}

/**
 * Get icon configuration for PptxGenJS text object
 * @param {string} iconName - Lucide icon name
 * @returns {Object} Icon configuration with character and formatting
 */
function getIconConfig(iconName) {
  const char = getIconCharacter(iconName);

  return {
    text: char,
    options: {
      fontSize: 18,
      color: '2563EB', // Blue-600
      bold: false,
      breakLine: false
    }
  };
}

/**
 * Check if icon is available
 * @param {string} iconName - Lucide icon name
 * @returns {boolean} True if icon has a mapping
 */
function hasIcon(iconName) {
  if (!iconName) return false;
  const normalized = iconName.toLowerCase().trim();
  return normalized in ICON_MAP;
}

/**
 * Get all available icon names
 * @returns {string[]} Array of available icon names
 */
function getAvailableIcons() {
  return Object.keys(ICON_MAP).filter(key => key !== 'default');
}

module.exports = {
  getIconCharacter,
  getIconConfig,
  hasIcon,
  getAvailableIcons,
  ICON_MAP
};
