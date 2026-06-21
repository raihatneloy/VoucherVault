const { chromium } = require('playwright');

/**
 * Check a Lidl Ireland gift card balance using Playwright automation.
 *
 * @param {string} cardNumber - The 18-20 digit gift card number
 * @param {string} pin - The 4-digit PIN
 * @param {object} [options] - Optional settings
 * @param {number} [options.timeout=180000] - Max time to wait for captcha (ms)
 * @param {boolean} [options.headless=true] - Whether to run browser headless
 * @returns {Promise<{success: boolean, balance?: number, currency?: string, status?: string, expires?: string, error?: string}>}
 */
async function checkLidlBalance(cardNumber, pin, options = {}) {
  const {
    timeout = 180000,
    headless = true,
  } = options;

  // Validate inputs
  const cleanCard = cardNumber.trim().replace(/\s+/g, '');
  const cleanPin = pin.trim();

  if (cleanCard.length < 18 || cleanCard.length > 20) {
    return { success: false, error: 'Card number must be 18-20 digits' };
  }
  if (cleanPin.length !== 4) {
    return { success: false, error: 'PIN must be 4 digits' };
  }

  let browser;
  try {
    browser = await chromium.launch({
      headless,
      args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--no-first-run',
        '--no-default-browser-check',
        '--window-size=1920,1080'
      ]
    });

    const context = await browser.newContext({
      userAgent: 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.204 Safari/537.36',
      viewport: { width: 1920, height: 1080 },
      locale: 'en-GB',
      timezoneId: 'Europe/Dublin'
    });

    const page = await context.newPage();

    // Anti-detection
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => false });
      Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
      Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en-US', 'en'] });
    });

    // Navigate
    await page.goto('https://www.lidl.ie/c/gift-card-balance-check/s10073374', {
      waitUntil: 'networkidle',
      timeout: 60000,
    });

    // Dismiss cookie consent
    try {
      await page.evaluate(() => {
        const btn = document.querySelector('button.ot-button-order-2');
        if (btn) btn.click();
      });
      await page.waitForTimeout(2000);
    } catch (e) {
      // Cookie banner may not appear
    }

    // Fill card number
    const cardInput = page.locator('.AGiftyBalanceCheck__input-card-number input.ods-input__input');
    await cardInput.click();
    await cardInput.fill('');
    await cardInput.type(cleanCard, { delay: 15 });

    // Fill PIN
    const pinInput = page.locator('.AGiftyBalanceCheck__input-pin input.ods-input__input');
    await pinInput.click();
    await pinInput.fill('');
    await pinInput.type(cleanPin, { delay: 10 });

    // Friendly Captcha: try to click the button if visible, but don't worry
    // if it's not — the captcha auto-starts once the widget loads
    try {
      const captchaBtn = page.locator('button.frc-button');
      if (await captchaBtn.isVisible({ timeout: 3000 })) {
        await captchaBtn.click();
      }
    } catch (e) {
      // Captcha may have auto-started already
    }

    // Wait for a real captcha solution (skipping .UNFINISHED / .HEADLESS_ERROR)
    const deadline = Date.now() + timeout;
    let solved = false;
    while (Date.now() < deadline) {
      const state = await page.evaluate(() => {
        const sol = document.querySelector('input.frc-captcha-solution');
        return {
          value: sol?.value || '',
          length: sol?.value?.length || 0,
        };
      });
      if (state.length >= 50 && !state.value.startsWith('.')) {
        solved = true;
        break;
      }
      await page.waitForTimeout(2000);
    }

    if (!solved) {
      return { success: false, error: 'Captcha verification timed out' };
    }

    // Click REQUEST NOW
    await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      for (const btn of buttons) {
        if (btn.textContent.trim() === 'REQUEST NOW') {
          btn.click();
          break;
        }
      }
    });

    // Wait for results or errors to appear
    await page.waitForFunction(() => {
      const results = document.querySelector('.AGiftyBalanceCheck__results');
      const errors = document.querySelectorAll('.ods-alert:not(.AGiftyBalanceCheck--hidden)');
      return (results && !results.classList.contains('AGiftyBalanceCheck--hidden')) || errors.length > 0;
    }, { timeout: 60000 }).catch(() => {});

    // Extra settle time
    await page.waitForTimeout(3000);

    // Parse results
    const result = await page.evaluate(() => {
      const rv = document.querySelectorAll('.AGiftyBalanceCheck__result_value');
      const alerts = document.querySelectorAll('.ods-alert:not(.AGiftyBalanceCheck--hidden)');
      const balanceText = rv[0]?.textContent?.trim() || '';
      const statusText = rv[1]?.textContent?.trim() || '';
      const expiresText = rv[2]?.textContent?.trim() || '';
      const errors = Array.from(alerts).map(el => el.textContent.trim());

      let balance = null;
      let currency = 'EUR';
      if (balanceText) {
        const match = balanceText.match(/([\d.]+)\s*(\w+)/);
        if (match) {
          balance = parseFloat(match[1]);
          currency = match[2] || 'EUR';
        }
      }

      return { balance, currency, status: statusText, expires: expiresText, errors };
    });

    if (result.errors.length > 0) {
      return { success: false, error: result.errors.join('; '), ...result };
    }

    if (result.balance === null && !result.status) {
      return { success: false, error: 'Could not retrieve balance. Unexpected response.' };
    }

    return { success: true, ...result };

  } catch (error) {
    const message = error.message || String(error);
    if (message.includes('Timeout') || message.includes('timeout')) {
      return { success: false, error: 'Balance check timed out. Please try again.' };
    }
    return { success: false, error: `Balance check failed: ${message.substring(0, 200)}` };
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}

module.exports = { checkLidlBalance };
