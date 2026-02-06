const express = require("express");

const app = express();
const FLAG = "DH{This_is_fake_flag}";

function getClientIp(req) {
  const xff = req.headers["x-forwarded-for"];
  if (typeof xff === "string" && xff.length) {
    return xff.split(",")[0].trim();
  }
  return req.socket?.remoteAddress || "";
}

function normalizeIp(ip) {
  if (!ip) return "";
  if (ip.startsWith("::ffff:")) return ip.slice("::ffff:".length);
  return ip;
}

function isLocal(ip) {
  ip = normalizeIp(ip);
  return ip === "127.0.0.1" || ip === "::1";
}

function htmlEscape(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

app.disable("x-powered-by");

app.get("/", (req, res) => {
  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.end(`<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>whoami</title>
  <style>
    body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; background:#0b1020; color:#e7e9ff; margin:0; }
    .wrap{ max-width: 720px; margin: 0 auto; padding: 40px 20px; }
    .card{ background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); border-radius: 16px; padding: 18px; }
    a.btn{ display:inline-block; background:#4f7cff; color:white; text-decoration:none; padding:10px 14px; border-radius: 12px; margin-right:10px; }
    code{ background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 8px; }
    .muted{ color:#b6b9da; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>whoami</h1>
    <p class="muted">The server knows who you are. The question is… do you?</p>
    <div class="card">
      <p>This service identifies callers by <code>client IP</code> and unlocks a private page for trusted users.</p>
      <p>
        <a class="btn" href="/whoami">Check /whoami</a>
        <a class="btn" href="/admin">Go /admin</a>
      </p>
    </div>
  </div>
</body>
</html>`);
});

app.get("/whoami", (req, res) => {
  const raw = getClientIp(req);
  const ip = normalizeIp(raw);
  const role = isLocal(ip) ? "admin" : "guest";

  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify({
    ip,
    role,
    message: role === "admin"
      ? "Welcome back. The server knows you."
      : "I don't recognize you."
  }, null, 2));
});

app.get("/admin", (req, res) => {
  const raw = getClientIp(req);
  const ip = normalizeIp(raw);

  if (!isLocal(ip)) {
    res.status(403);
    res.setHeader("Content-Type", "text/html; charset=utf-8");
    res.end(`<!doctype html><html><head><meta charset="utf-8"><title>403</title></head>
<body style="font-family:system-ui;background:#0b1020;color:#e7e9ff;padding:24px">
  <h2>403 Forbidden</h2>
  <p>You are not who I think you are.</p>
  <p class="muted">Detected IP: <code>${htmlEscape(ip)}</code></p>
  <p class="muted">Try learning who you are first: <a href="/whoami" style="color:#4f7cff">/whoami</a></p>
</body></html>`);
    return;
  }

  res.setHeader("Content-Type", "text/html; charset=utf-8");
  res.end(`<!doctype html>
<html><head><meta charset="utf-8"><title>admin</title></head>
<body style="font-family:system-ui;background:#0b1020;color:#e7e9ff;padding:24px">
  <h2>Admin Panel</h2>
  <p>Identity confirmed: <code>${htmlEscape(ip)}</code></p>
  <p>Flag: <code>${htmlEscape(FLAG)}</code></p>
</body></html>`);
});

app.listen(3000, "0.0.0.0", () => {
  console.log(`[whoami] listening on 0.0.0.0:3000`);
});
