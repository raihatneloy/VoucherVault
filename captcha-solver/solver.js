const { WidgetInstance } = require('friendly-challenge/compat');

async function solveCaptcha(sitekey, puzzleEndpoint) {
  return new Promise((resolve, reject) => {
    const element = {
      dataset: {
        sitekey: sitekey,
        start: 'auto',
        lang: 'en',
        puzzleEndpoint: puzzleEndpoint,
      },
      innerText: '',
      innerHTML: '',
      querySelector: () => null,
      isConnected: true,
      friendlyChallengeWidget: null,
    };

    const timeout = setTimeout(() => {
      reject(new Error('Captcha solving timed out after 120s'));
    }, 120000);

    try {
      const widget = new WidgetInstance(element, {
        sitekey: sitekey,
        puzzleEndpoint: puzzleEndpoint,
        startMode: 'auto',
        language: 'en',
        solutionFieldName: 'frc-captcha-solution',
        doneCallback: (solution) => {
          clearTimeout(timeout);
          resolve(solution);
        },
        errorCallback: (err) => {
          clearTimeout(timeout);
          reject(new Error(typeof err === 'string' ? err : (err.message || 'Unknown captcha error')));
        },
        skipStyleInjection: true,
        forceJSFallback: true,
      });
    } catch (err) {
      clearTimeout(timeout);
      reject(err);
    }
  });
}

const http = require('http');
const port = parseInt(process.env.PORT || '3001', 10);
const defaultSitekey = process.env.SITEKEY || 'FCMGDDIJTON17UAD';
const defaultPuzzleEndpoint = process.env.PUZZLE_ENDPOINT || 'https://eu.frcapi.com/api/v1/puzzle';

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method !== 'POST' || req.url !== '/solve') {
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'POST /solve with { sitekey? }' }));
    return;
  }

  let body = '';
  req.on('data', chunk => body += chunk);
  req.on('end', async () => {
    try {
      const data = JSON.parse(body || '{}');
      const sitekey = data.sitekey || defaultSitekey;
      const puzzleEndpoint = data.puzzleEndpoint || defaultPuzzleEndpoint;

      console.log('[solver] Solving captcha: sitekey=' + sitekey);
      const startTime = Date.now();
      const token = await solveCaptcha(sitekey, puzzleEndpoint);
      const elapsed = Date.now() - startTime;
      console.log('[solver] Solved in ' + elapsed + 'ms');

      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: true, token, elapsed_ms: elapsed }));
    } catch (err) {
      console.error('[solver] Error: ' + err.message);
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ success: false, error: err.message }));
    }
  });
});

server.listen(port, '127.0.0.1', () => {
  console.log('[solver] Captcha solver listening on http://127.0.0.1:' + port);
  console.log('[solver] Default sitekey: ' + defaultSitekey);
  console.log('[solver] Puzzle endpoint: ' + defaultPuzzleEndpoint);
});
