const ChartBuilder = require('./chart-builder');

/**
 * Slide Renderer - renders different types of slides
 */
class SlideRenderer {
  constructor(pptx, theme) {
    this.pptx = pptx;
    this.theme = theme;
    this.chartBuilder = new ChartBuilder(pptx, theme);
  }

  /**
   * Render title slide
   */
  renderTitleSlide(slide, spec) {
    // Background gradient
    slide.background = { fill: this.theme.primary };

    // Title
    slide.addText(spec.title || 'Presentation', {
      x: 0.5,
      y: '40%',
      w: '90%',
      h: 1.5,
      align: 'center',
      fontSize: 44,
      bold: true,
      color: 'FFFFFF',
      fontFace: 'Arial, sans-serif'
    });

    // Subtitle / key message
    if (spec.key_message) {
      slide.addText(spec.key_message, {
        x: 0.5,
        y: '55%',
        w: '90%',
        h: 0.8,
        align: 'center',
        fontSize: 20,
        color: 'E0E0E0',
        fontFace: 'Arial, sans-serif',
        italic: true
      });
    }
  }

  /**
   * Render agenda/table of contents slide
   */
  renderAgendaSlide(slide, spec) {
    // Title
    slide.addText(spec.title || '목차', {
      x: 0.5,
      y: 0.5,
      w: '90%',
      h: 0.75,
      fontSize: 32,
      bold: true,
      color: this.theme.primary,
      fontFace: 'Arial, sans-serif'
    });

    // Agenda items with numbering
    const bullets = spec.bullets || [];
    const startY = 1.5;
    const itemHeight = 0.55;

    bullets.forEach((bullet, index) => {
      // Number circle
      slide.addShape(this.pptx.ShapeType.ellipse, {
        x: 0.8,
        y: startY + (index * itemHeight),
        w: 0.4,
        h: 0.4,
        fill: { color: this.theme.primary },
        line: { type: 'none' }
      });

      // Number text
      slide.addText((index + 1).toString(), {
        x: 0.8,
        y: startY + (index * itemHeight),
        w: 0.4,
        h: 0.4,
        align: 'center',
        valign: 'middle',
        fontSize: 16,
        bold: true,
        color: 'FFFFFF'
      });

      // Agenda item text
      slide.addText(bullet.length > 70 ? bullet.substring(0, 70) + '...' : bullet, {
        x: 1.4,
        y: startY + (index * itemHeight),
        w: 8,
        h: 0.4,
        fontSize: 18,
        color: this.theme.text,
        valign: 'middle',
        fontFace: 'Arial, sans-serif'
      });
    });
  }

  /**
   * Render thank you slide
   */
  renderThanksSlide(slide, spec) {
    slide.background = { fill: 'F8F9FA' };

    slide.addText(spec.title || '감사합니다', {
      x: 0,
      y: '40%',
      w: '100%',
      h: 1.2,
      align: 'center',
      fontSize: 48,
      bold: true,
      color: this.theme.primary,
      fontFace: 'Arial, sans-serif'
    });

    if (spec.key_message) {
      slide.addText(spec.key_message, {
        x: 0,
        y: '55%',
        w: '100%',
        h: 0.6,
        align: 'center',
        fontSize: 20,
        color: this.theme.text,
        fontFace: 'Arial, sans-serif'
      });
    }
  }

  /**
   * Render content slide
   */
  renderContentSlide(slide, spec, includeCharts = true) {
    const hasChart = includeCharts && spec.diagram?.chart;

    // Title
    slide.addText(spec.title || '', {
      x: 0.5,
      y: 0.5,
      w: '90%',
      h: 0.75,
      fontSize: 28,
      bold: true,
      color: this.theme.primary,
      fontFace: 'Arial, sans-serif'
    });

    // Key message
    if (spec.key_message) {
      slide.addText(spec.key_message, {
        x: 0.5,
        y: 1.4,
        w: '90%',
        h: 0.5,
        fontSize: 16,
        color: this.theme.text,
        italic: true,
        fontFace: 'Arial, sans-serif'
      });
    }

    const contentStartY = spec.key_message ? 2.2 : 1.6;

    // Two-column layout with chart
    if (hasChart) {
      this._addBullets(slide, spec.bullets || [], {
        x: 0.5,
        y: contentStartY,
        w: 4.5,
        h: 4
      });

      this.chartBuilder.addChart(slide, spec.diagram.chart, {
        x: 5.5,
        y: contentStartY,
        w: 6,
        h: 4
      });
    } else {
      // Single column layout
      this._addBullets(slide, spec.bullets || [], {
        x: 0.5,
        y: contentStartY,
        w: '90%',
        h: 4.5
      });
    }
  }

  /**
   * Add bullets to slide
   */
  _addBullets(slide, bullets, position) {
    if (!bullets || bullets.length === 0) return;

    // Limit bullets and truncate long text
    const limitedBullets = bullets.slice(0, 8).map(b => {
      const text = b.length > 100 ? b.substring(0, 100) + '...' : b;
      return {
        text: text,
        options: {
          bullet: { code: '2022' }, // Bullet character
          fontSize: 16,
          color: this.theme.text,
          fontFace: 'Arial, sans-serif'
        }
      };
    });

    slide.addText(limitedBullets, {
      ...position,
      valign: 'top'
    });
  }
}

module.exports = SlideRenderer;
