const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');

const HOST = '0.0.0.0';
const PORT = process.env.PORT ? Number(process.env.PORT) : 4173;
const ROOT = __dirname;
const CERT_DIR = path.join(ROOT, 'certs');
const CERT_KEY_PATH = path.join(CERT_DIR, 'localhost.key');
const CERT_CRT_PATH = path.join(CERT_DIR, 'localhost.crt');

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.pdf': 'application/pdf',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.txt': 'text/plain; charset=utf-8'
};

function send(res, statusCode, body, contentType = 'text/plain; charset=utf-8') {
  res.writeHead(statusCode, {
    'Content-Type': contentType,
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

function resolvePath(urlPath) {
  const safePath = decodeURIComponent(urlPath.split('?')[0]);
  const normalized = path.normalize(safePath).replace(/^(\.\.[\\/])+/, '');
  const target = normalized === path.sep || normalized === '/' ? 'index.html' : normalized.replace(/^[/\\]/, '');
  return path.join(ROOT, target);
}

function requestHandler(req, res) {
  const filePath = resolvePath(req.url || '/');

  if (!filePath.startsWith(ROOT)) {
    send(res, 403, 'Forbidden');
    return;
  }

  fs.stat(filePath, (statErr, stats) => {
    if (statErr) {
      send(res, 404, 'Not Found');
      return;
    }

    const finalPath = stats.isDirectory() ? path.join(filePath, 'index.html') : filePath;
    fs.readFile(finalPath, (readErr, data) => {
      if (readErr) {
        send(res, 500, 'Server Error');
        return;
      }

      const ext = path.extname(finalPath).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';
      send(res, 200, data, contentType);
    });
  });
}

function startHttpServer() {
  const server = http.createServer(requestHandler);
  server.listen(PORT, HOST, () => {
    console.log(`UOGA Hunt Planner local server running at http://${HOST}:${PORT}`);
  });
}

function startHttpsServer() {
  const tlsOptions = {
    key: fs.readFileSync(CERT_KEY_PATH),
    cert: fs.readFileSync(CERT_CRT_PATH)
  };
  const httpsServer = https.createServer(tlsOptions, requestHandler);
  httpsServer.listen(PORT, HOST, () => {
    console.log(`UOGA Hunt Planner local server running at https://${HOST}:${PORT}`);
  });
}

const hasCert = fs.existsSync(CERT_KEY_PATH) && fs.existsSync(CERT_CRT_PATH);
if (hasCert) {
  startHttpsServer();
} else {
  startHttpServer();
}
