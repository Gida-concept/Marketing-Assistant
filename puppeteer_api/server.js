const express = require('express');
const puppeteer = require('puppeteer');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');

const app = express();

// Security middleware
app.use(helmet({
  contentSecurityPolicy: false,
}));
app.use(cors());

// Rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per window
  message: { error: 'Rate limit exceeded' }
});
app.use('/audit', limiter);

// Launch Puppeteer browser
let browser;
async function initBrowser() {
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--no-first-run',
        '--no-zygote',
        '--disable-gpu'
      ],
      timeout: 30000
    });
    console.log('Puppeteer browser launched successfully');
  } catch (error) {
    console.error('Failed to launch Puppeteer browser:', error);
    process.exit(1);
  }
}

// Initialize browser on startup
initBrowser();

// Graceful shutdown
process.on('SIGINT', async () => {
  console.log('Shutting down gracefully...');
  if (browser) {
    await browser.close();
  }
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('Shutting down gracefully...');
  if (browser) {
    await browser.close();
  }
  process.exit(0);
});

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', service: 'puppeteer-audit-api' });
});

// Audit endpoint
app.post('/audit', express.json(), async (req, res) => {
  const { url } = req.body;

  // Input validation
  if (!url || typeof url !== 'string') {
    return res.status(400).json({
      success: false,
      error: 'URL is required and must be a string'
    });
  }

  // Basic URL sanitization
  let normalizedUrl = url.trim();
  if (!normalizedUrl.match(/^https?:\/\//i)) {
    normalizedUrl = 'https://' + normalizedUrl;
  }

  // Validate URL format
  try {
    new URL(normalizedUrl);
  } catch (err) {
    return res.status(400).json({
      success: false,
      error: 'Invalid URL format'
    });
  }

  let page;
  try {
    page = await browser.newPage();

    // Set realistic user agent
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36');

    // Enable request interception to detect SSL issues
    await page.setRequestInterception(true);
    let sslError = null;
    page.on('requestfailed', (request) => {
      if (request.failure().errorText.includes('SSL')) {
        sslError = request.failure().errorText;
      }
    });

    // Measure navigation timing
    const start = Date.now();
    const response = await page.goto(normalizedUrl, {
      waitUntil: 'networkidle0',
      timeout: 30000
    });
    const loadTime = Date.now() - start;

    // Check SSL status from response
    const responseHeaders = response?.headers() || {};
    const isSSL = normalizedUrl.startsWith('https://');
    let sslStatus = isSSL;

    // Additional SSL check
    if (isSSL && !sslError) {
      try {
        const securityDetails = response.securityDetails();
        sslStatus = securityDetails !== null;
      } catch (e) {
        sslStatus = true; // Assume valid if we can't determine
      }
    }

    // Extract emails using regex
    const content = await page.content();
    const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;
    const emails = [...new Set(content.match(emailRegex) || [])].slice(0, 5); // Dedupe and limit

    // Count H1 tags
    const h1Count = await page.$$eval('h1', els => els.length);

    // Close page
    await page.close();

    // Return audit results
    return res.status(200).json({
      success: true,
      data: {
        emails,
        load_time: parseFloat((loadTime / 1000).toFixed(2)),
        ssl: sslStatus,
        h1_count: h1Count
      }
    });

  } catch (error) {
    console.error('Audit failed for', normalizedUrl, ':', error.message);

    // Clean up page if it exists
    if (page) {
      try {
        await page.close();
      } catch (closeError) {
        console.error('Failed to close page:', closeError.message);
      }
    }

    // Return appropriate error message
    let errorMessage = 'Unknown error during audit';
    if (error.name === 'TimeoutError') {
      errorMessage = 'Page load timed out after 30 seconds';
    } else if (error.message.includes('net::ERR_NAME_NOT_RESOLVED')) {
      errorMessage = 'Domain does not exist';
    } else if (error.message.includes('net::ERR_CONNECTION_REFUSED')) {
      errorMessage = 'Connection refused by server';
    } else if (error.message.includes('net::ERR_CERT')) {
      errorMessage = 'SSL certificate error';
    } else if (error.message.includes('net::ERR_BLOCKED_BY_CLIENT')) {
      errorMessage = 'Request blocked by client';
    }

    return res.status(200).json({
      success: false,
      error: errorMessage
    });

  }
});

// Handle unsupported methods
app.all('/audit', (req, res) => {
  if (req.method !== 'POST') {
    return res.status(405).json({
      success: false,
      error: 'Method not allowed. Use POST.'
    });
  }
});

// Handle 404
app.use('*', (req, res) => {
  res.status(404).json({
    error: 'Endpoint not found'
  });
});

// Error handling middleware
app.use((error, req, res, next) => {
  console.error('Unhandled error:', error);
  res.status(500).json({
    success: false,
    error: 'Internal server error'
  });
});

// Start server
const PORT = process.env.PORT || 3001;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Puppeteer audit API running on port ${PORT}`);
});

module.exports = app;