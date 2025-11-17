const express = require('express');
const pptxRoutes = require('./pptx.routes');

const router = express.Router();

// Mount PPTX routes
router.use('/pptx', pptxRoutes);

// API root
router.get('/', (req, res) => {
  res.json({
    service: 'Office Generator Service',
    version: '1.0.0',
    endpoints: {
      pptx: '/api/pptx/generate',
      health: '/api/pptx/health'
    }
  });
});

module.exports = router;
