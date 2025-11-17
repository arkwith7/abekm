/**
 * Chart Builder - creates charts from data using PptxGenJS
 */
class ChartBuilder {
  constructor(pptx, theme) {
    this.pptx = pptx;
    this.theme = theme;
  }

  /**
   * Add chart to slide
   */
  addChart(slide, chartData, position) {
    if (!chartData || !chartData.categories || !chartData.series) {
      return;
    }

    try {
      const chartType = this._mapChartType(chartData.type);
      const data = this._prepareChartData(chartData);

      slide.addChart(chartType, data, {
        ...position,
        chartColors: this.theme.chartColors || ['0066CC', '6699FF', 'FF9900'],
        showTitle: !!chartData.title,
        title: chartData.title || '',
        titleFontSize: 14,
        titleColor: this.theme.primary,
        showLegend: true,
        legendPos: 'r',
        legendFontSize: 10,
        showValue: true,
        dataLabelFontSize: 10,
        dataLabelColor: '404040',
        valAxisHidden: false,
        catAxisHidden: false,
        showCatAxisTitle: false,
        showValAxisTitle: false,
        border: { pt: 1, color: 'E0E0E0' }
      });
    } catch (error) {
      throw new Error(`Chart generation failed: ${error.message}`);
    }
  }

  /**
   * Map chart type to PptxGenJS type
   */
  _mapChartType(type) {
    const mapping = {
      'bar': this.pptx.charts.BAR,
      'column': this.pptx.charts.BAR, // PptxGenJS uses BAR for vertical bars
      'line': this.pptx.charts.LINE,
      'pie': this.pptx.charts.PIE,
      'doughnut': this.pptx.charts.DOUGHNUT,
      'area': this.pptx.charts.AREA,
      'scatter': this.pptx.charts.SCATTER
    };

    return mapping[type?.toLowerCase()] || this.pptx.charts.BAR;
  }

  /**
   * Prepare chart data in PptxGenJS format
   */
  _prepareChartData(chartData) {
    const categories = chartData.categories || [];
    const series = chartData.series || [];

    // Handle multiple series
    if (series.length > 0) {
      return series.map(s => ({
        name: s.name || 'Data',
        labels: categories,
        values: s.data || s.values || []
      }));
    }

    // Fallback for single series
    return [{
      name: chartData.title || 'Data',
      labels: categories,
      values: []
    }];
  }
}

module.exports = ChartBuilder;
