const http = require("http");
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const port = Number(process.env.PORT || 8000);
const host = "127.0.0.1";

const mime = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".csv": "text/csv; charset=utf-8",
  ".md": "text/markdown; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml",
};

function send(res, status, body, type = "text/plain; charset=utf-8") {
  res.writeHead(status, {
    "content-type": type,
    "cache-control": "no-store",
  });
  res.end(body);
}

const server = http.createServer((req, res) => {
  const url = new URL(req.url || "/", `http://${host}:${port}`);
  const pathname = decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname);
  const target = path.resolve(root, `.${pathname}`);

  if (!target.startsWith(root + path.sep) && target !== root) {
    send(res, 403, "Forbidden");
    return;
  }

  fs.stat(target, (statErr, stat) => {
    if (statErr || !stat.isFile()) {
      send(res, 404, "Not found");
      return;
    }

    res.writeHead(200, {
      "content-type": mime[path.extname(target).toLowerCase()] || "application/octet-stream",
      "cache-control": "no-store",
    });
    fs.createReadStream(target).pipe(res);
  });
});

server.listen(port, host, () => {
  console.log(`13F preview ready at http://${host}:${port}/index.html`);
});
