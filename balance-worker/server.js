const express = require('express');
const { checkLidlBalance } = require('./balance');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(express.json());

// Increase timeout for long-running requests (captcha can take 60s+)
app.use((req, res, next) => {
  req.setTimeout(300000); // 5 minutes
  res.setTimeout(300000);
  next();
});

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', service: 'vouchervault-balance-worker' });
});

// Lidl Ireland balance check
app.post('/check-lidl-balance', async (req, res) => {
  const { cardNumber, pin } = req.body;

  if (!cardNumber || !pin) {
    return res.status(400).json({
      success: false,
      error: 'cardNumber and pin are required'
    });
  }

  // Log the request (masked)
  const masked = cardNumber.substring(0, 4) + '****' + cardNumber.substring(cardNumber.length - 4);
  console.log(`[${new Date().toISOString()}] Checking Lidl balance for card ${masked}`);

  try {
    const result = await checkLidlBalance(cardNumber, pin);

    if (result.success) {
      console.log(`[${new Date().toISOString()}] Success: €${result.balance} - ${result.status}`);
    } else {
      console.log(`[${new Date().toISOString()}] Failed: ${result.error}`);
    }

    res.json(result);
  } catch (error) {
    console.error(`[${new Date().toISOString()}] Error:`, error.message);
    res.status(500).json({
      success: false,
      error: 'Internal server error during balance check'
    });
  }
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Balance worker listening on port ${PORT}`);
});
