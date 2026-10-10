const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = process.env.PORT || 3000;
const DIST_DIR = path.resolve(__dirname, "..", "dist");

const MIME_TYPES = {
  '.html': 'text/html; charset=UTF-8',
  '.js': 'text/javascript; charset=UTF-8',
  '.mjs': 'text/javascript; charset=UTF-8',
  '.css': 'text/css; charset=UTF-8',
  '.json': 'application/json',
  '.wasm': 'application/wasm',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.gif': 'image/gif',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.webp': 'image/webp',
  '.xml': 'application/xml',
  '.dds': 'image/vnd-ms.dds',
  '.txt': 'text/plain; charset=UTF-8',
  '.py': 'text/x-python; charset=UTF-8',
  '.zip': 'application/zip',
  '.gz': 'application/gzip',
  '.tar': 'application/x-tar',
};

const server = http.createServer((req, res) => {
  // Supprimer les query params et décoder l'URL
  const cleanUrl = decodeURIComponent(req.url.split('?')[0]);
  let safePath = path.normalize(cleanUrl).replace(/^(\.\.[\/\\])+/, '');
  let filePath = path.join(DIST_DIR, safePath);

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      // Si c'est un répertoire, tenter index.html
      if (stats && stats.isDirectory()) {
        const indexPath = path.join(filePath, 'index.html');
        if (fs.existsSync(indexPath)) {
          return serveFile(indexPath, res);
        }
      }
      // SPA Fallback : servir dist/index.html
      const fallbackPath = path.join(DIST_DIR, 'index.html');
      return serveFile(fallbackPath, res);
    }
    serveFile(filePath, res);
  });
});

function serveFile(fileToServe, res) {
  const ext = path.extname(fileToServe).toLowerCase();
  const contentType = MIME_TYPES[ext] || 'application/octet-stream';

  fs.readFile(fileToServe, (err, data) => {
    if (err) {
      res.writeHead(500, { 'Content-Type': 'text/plain' });
      return res.end('Erreur de lecture du fichier : ' + err.message);
    }
    res.writeHead(200, {
      'Content-Type': contentType,
      'Cache-Control': 'no-cache',
    });
    res.end(data);
  });
}

server.listen(PORT, '0.0.0.0', () => {
  console.log(`[fOMODSIM v1.0] Serveur démarré : http://localhost:${PORT}`);
});
