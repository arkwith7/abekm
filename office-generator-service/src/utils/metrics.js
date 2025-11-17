/**
 * Simple metrics collector for monitoring
 */

class MetricsCollector {
  constructor() {
    this.metrics = {
      requests: {
        total: 0,
        success: 0,
        failed: 0,
        byEndpoint: {}
      },
      generation: {
        pptx: { count: 0, totalSlides: 0, totalCharts: 0, totalTime: 0 },
        docx: { count: 0, totalTime: 0 },
        xlsx: { count: 0, totalTime: 0 }
      },
      errors: {
        total: 0,
        byType: {}
      }
    };

    this.startTime = Date.now();
  }

  recordRequest(endpoint, success = true) {
    this.metrics.requests.total++;

    if (success) {
      this.metrics.requests.success++;
    } else {
      this.metrics.requests.failed++;
    }

    if (!this.metrics.requests.byEndpoint[endpoint]) {
      this.metrics.requests.byEndpoint[endpoint] = { total: 0, success: 0, failed: 0 };
    }

    this.metrics.requests.byEndpoint[endpoint].total++;

    if (success) {
      this.metrics.requests.byEndpoint[endpoint].success++;
    } else {
      this.metrics.requests.byEndpoint[endpoint].failed++;
    }
  }

  recordGeneration(type, slideCount = 0, chartCount = 0, timeMs = 0) {
    const gen = this.metrics.generation[type];

    if (gen) {
      gen.count++;
      gen.totalTime += timeMs;

      if (type === 'pptx') {
        gen.totalSlides += slideCount;
        gen.totalCharts += chartCount;
      }
    }
  }

  recordError(errorType) {
    this.metrics.errors.total++;

    if (!this.metrics.errors.byType[errorType]) {
      this.metrics.errors.byType[errorType] = 0;
    }

    this.metrics.errors.byType[errorType]++;
  }

  getMetrics() {
    const uptime = Math.floor((Date.now() - this.startTime) / 1000);

    return {
      uptime,
      timestamp: new Date().toISOString(),
      ...this.metrics
    };
  }

  // Prometheus-compatible format
  getPrometheusMetrics() {
    const lines = [];

    // Request metrics
    lines.push('# HELP office_generator_requests_total Total number of requests');
    lines.push('# TYPE office_generator_requests_total counter');
    lines.push(`office_generator_requests_total ${this.metrics.requests.total}`);

    lines.push('# HELP office_generator_requests_success Successful requests');
    lines.push('# TYPE office_generator_requests_success counter');
    lines.push(`office_generator_requests_success ${this.metrics.requests.success}`);

    lines.push('# HELP office_generator_requests_failed Failed requests');
    lines.push('# TYPE office_generator_requests_failed counter');
    lines.push(`office_generator_requests_failed ${this.metrics.requests.failed}`);

    // Generation metrics
    Object.entries(this.metrics.generation).forEach(([type, data]) => {
      lines.push(`# HELP office_generator_${type}_count Number of ${type} generated`);
      lines.push(`# TYPE office_generator_${type}_count counter`);
      lines.push(`office_generator_${type}_count ${data.count}`);

      if (data.count > 0) {
        const avgTime = data.totalTime / data.count;
        lines.push(`# HELP office_generator_${type}_avg_time_ms Average generation time`);
        lines.push(`# TYPE office_generator_${type}_avg_time_ms gauge`);
        lines.push(`office_generator_${type}_avg_time_ms ${avgTime.toFixed(2)}`);
      }
    });

    return lines.join('\n');
  }
}

// Singleton instance
const metricsCollector = new MetricsCollector();

module.exports = metricsCollector;
