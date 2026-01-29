// Package web provides embedded dashboard HTML/CSS/JS
package web

import "github.com/gofiber/fiber/v2"

// handleDashboard serves the main dashboard HTML
func (s *Server) handleDashboard(c *fiber.Ctx) error {
	c.Set("Content-Type", "text/html; charset=utf-8")
	return c.SendString(dashboardHTML)
}

// handleDashboardJS serves the dashboard JavaScript
func (s *Server) handleDashboardJS(c *fiber.Ctx) error {
	c.Set("Content-Type", "application/javascript; charset=utf-8")
	return c.SendString(dashboardJS)
}

// handleDashboardCSS serves the dashboard CSS
func (s *Server) handleDashboardCSS(c *fiber.Ctx) error {
	c.Set("Content-Type", "text/css; charset=utf-8")
	return c.SendString(dashboardCSS)
}

const dashboardHTML = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🛡️ FluxFuzzer Dashboard</title>
    <link rel="stylesheet" href="/dashboard.css">
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
</head>
<body>
    <div class="app">
        <!-- Sidebar -->
        <aside class="sidebar">
            <div class="logo">
                <span class="logo-icon">🛡️</span>
                <span class="logo-text">FluxFuzzer</span>
            </div>
            <nav class="nav">
                <a href="#" class="nav-item active" data-page="dashboard">
                    <span class="nav-icon">📊</span>
                    Dashboard
                </a>
                <a href="#" class="nav-item" data-page="logs">
                    <span class="nav-icon">📝</span>
                    Request Logs
                </a>
                <a href="#" class="nav-item" data-page="anomalies">
                    <span class="nav-icon">⚠️</span>
                    Anomalies
                </a>
                <a href="#" class="nav-item" data-page="wordlists">
                    <span class="nav-icon">📚</span>
                    Wordlists
                </a>
                <a href="#" class="nav-item" data-page="settings">
                    <span class="nav-icon">⚙️</span>
                    Settings
                </a>
            </nav>
            <div class="sidebar-footer">
                <span class="version">v0.1.0-dev</span>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="main">
            <!-- Header -->
            <header class="header">
                <h1 class="page-title">Dashboard</h1>
                <div class="header-actions">
                    <span class="status-indicator" id="status-indicator">
                        <span class="status-dot"></span>
                        <span class="status-text">Idle</span>
                    </span>
                </div>
            </header>

            <!-- Dashboard Content -->
            <div class="content" id="dashboard-page">
                <!-- Control Panel -->
                <section class="control-panel glass-card">
                    <h2 class="section-title">🎯 Target Configuration</h2>
                    <div class="control-form">
                        <div class="form-group">
                            <label for="target-url">Target URL</label>
                            <input type="text" id="target-url" placeholder="http://target.com/api/FUZZ" class="input">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="wordlist">Wordlist</label>
                                <select id="wordlist" class="input">
                                    <option value="common">common.txt</option>
                                    <option value="sqli">sqli.txt</option>
                                    <option value="xss">xss.txt</option>
                                </select>
                            </div>
                            <div class="form-group">
                                <label for="workers">Workers</label>
                                <input type="number" id="workers" value="50" min="1" max="500" class="input">
                            </div>
                            <div class="form-group">
                                <label for="rps">RPS Limit</label>
                                <input type="number" id="rps" value="100" min="1" max="5000" class="input">
                            </div>
                        </div>
                        <div class="button-group">
                            <button class="btn btn-primary" id="start-btn">
                                <span class="btn-icon">▶️</span> Start Fuzzing
                            </button>
                            <button class="btn btn-danger" id="stop-btn" disabled>
                                <span class="btn-icon">⏹️</span> Stop
                            </button>
                        </div>
                    </div>
                </section>

                <!-- Stats Grid -->
                <section class="stats-grid">
                    <div class="stat-card glass-card">
                        <div class="stat-icon">🚀</div>
                        <div class="stat-content">
                            <span class="stat-value" id="total-requests">0</span>
                            <span class="stat-label">Total Requests</span>
                        </div>
                    </div>
                    <div class="stat-card glass-card">
                        <div class="stat-icon">✅</div>
                        <div class="stat-content">
                            <span class="stat-value" id="success-requests">0</span>
                            <span class="stat-label">Success (2xx/3xx)</span>
                        </div>
                    </div>
                    <div class="stat-card glass-card">
                        <div class="stat-icon">❌</div>
                        <div class="stat-content">
                            <span class="stat-value" id="failed-requests">0</span>
                            <span class="stat-label">Failed (4xx/5xx)</span>
                        </div>
                    </div>
                    <div class="stat-card glass-card anomaly-card">
                        <div class="stat-icon">⚠️</div>
                        <div class="stat-content">
                            <span class="stat-value" id="anomalies-found">0</span>
                            <span class="stat-label">Anomalies Found</span>
                        </div>
                    </div>
                    <div class="stat-card glass-card">
                        <div class="stat-icon">⚡</div>
                        <div class="stat-content">
                            <span class="stat-value" id="rps-value">0</span>
                            <span class="stat-label">Requests/sec</span>
                        </div>
                    </div>
                    <div class="stat-card glass-card">
                        <div class="stat-icon">⏱️</div>
                        <div class="stat-content">
                            <span class="stat-value" id="elapsed-time">0s</span>
                            <span class="stat-label">Elapsed Time</span>
                        </div>
                    </div>
                </section>

                <!-- Live Feed -->
                <section class="live-feed glass-card">
                    <div class="section-header">
                        <h2 class="section-title">📡 Live Request Feed</h2>
                        <button class="btn btn-small" id="clear-logs">Clear</button>
                    </div>
                    <div class="log-container" id="log-container">
                        <div class="log-placeholder">
                            <span class="placeholder-icon">📭</span>
                            <span class="placeholder-text">Waiting for requests...</span>
                        </div>
                    </div>
                </section>

                <!-- Current Payload -->
                <section class="current-payload glass-card">
                    <h2 class="section-title">🔧 Current Payload</h2>
                    <code class="payload-display" id="current-payload">-</code>
                </section>
            </div>

            <!-- Logs Page (hidden by default) -->
            <div class="content hidden" id="logs-page">
                <section class="glass-card">
                    <h2 class="section-title">📝 Request Logs</h2>
                    <div class="table-container">
                        <table class="data-table" id="logs-table">
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Method</th>
                                    <th>URL</th>
                                    <th>Status</th>
                                    <th>Time (ms)</th>
                                    <th>Size</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                </section>
            </div>

            <!-- Anomalies Page (hidden by default) -->
            <div class="content hidden" id="anomalies-page">
                <section class="glass-card">
                    <h2 class="section-title">⚠️ Detected Anomalies</h2>
                    <div class="anomaly-list" id="anomaly-list">
                        <div class="log-placeholder">
                            <span class="placeholder-icon">✨</span>
                            <span class="placeholder-text">No anomalies detected yet</span>
                        </div>
                    </div>
                </section>
            </div>
        </main>
    </div>

    <script src="/dashboard.js"></script>
</body>
</html>`

const dashboardCSS = `:root {
    --bg-primary: #0a0a0f;
    --bg-secondary: #12121a;
    --bg-tertiary: #1a1a24;
    --text-primary: #ffffff;
    --text-secondary: #a0a0b0;
    --text-muted: #606070;
    --accent-primary: #00d4ff;
    --accent-secondary: #7c3aed;
    --accent-success: #10b981;
    --accent-warning: #f59e0b;
    --accent-danger: #ef4444;
    --border-color: rgba(255, 255, 255, 0.08);
    --glass-bg: rgba(255, 255, 255, 0.03);
    --glass-border: rgba(255, 255, 255, 0.08);
    --shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    --radius: 12px;
    --font-mono: 'JetBrains Mono', monospace;
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
    overflow-x: hidden;
}

/* Background Animation */
body::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: 
        radial-gradient(circle at 20% 80%, rgba(0, 212, 255, 0.08) 0%, transparent 50%),
        radial-gradient(circle at 80% 20%, rgba(124, 58, 237, 0.08) 0%, transparent 50%),
        radial-gradient(circle at 40% 40%, rgba(16, 185, 129, 0.04) 0%, transparent 40%);
    pointer-events: none;
    z-index: -1;
}

.app {
    display: flex;
    min-height: 100vh;
}

/* Sidebar */
.sidebar {
    width: 240px;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    position: fixed;
    height: 100vh;
    z-index: 100;
}

.logo {
    padding: 24px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid var(--border-color);
}

.logo-icon {
    font-size: 28px;
}

.logo-text {
    font-size: 20px;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}

.nav {
    padding: 16px 12px;
    flex: 1;
}

.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    margin-bottom: 4px;
    border-radius: 8px;
    color: var(--text-secondary);
    text-decoration: none;
    transition: all 0.2s ease;
}

.nav-item:hover {
    background: var(--glass-bg);
    color: var(--text-primary);
}

.nav-item.active {
    background: linear-gradient(135deg, rgba(0, 212, 255, 0.15), rgba(124, 58, 237, 0.15));
    color: var(--accent-primary);
    border: 1px solid rgba(0, 212, 255, 0.2);
}

.nav-icon {
    font-size: 18px;
}

.sidebar-footer {
    padding: 16px 24px;
    border-top: 1px solid var(--border-color);
}

.version {
    font-size: 12px;
    color: var(--text-muted);
    font-family: var(--font-mono);
}

/* Main Content */
.main {
    flex: 1;
    margin-left: 240px;
    min-height: 100vh;
}

.header {
    padding: 24px 32px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border-color);
    background: rgba(10, 10, 15, 0.8);
    backdrop-filter: blur(10px);
    position: sticky;
    top: 0;
    z-index: 50;
}

.page-title {
    font-size: 24px;
    font-weight: 600;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 16px;
    border-radius: 20px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
}

.status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-muted);
}

.status-indicator.running .status-dot {
    background: var(--accent-success);
    animation: pulse 1.5s infinite;
}

@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.2); }
}

.status-text {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}

.content {
    padding: 24px 32px;
}

.content.hidden {
    display: none;
}

/* Glass Card */
.glass-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius);
    padding: 24px;
    backdrop-filter: blur(10px);
    margin-bottom: 24px;
}

.section-title {
    font-size: 16px;
    font-weight: 600;
    margin-bottom: 20px;
    color: var(--text-primary);
}

.section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
}

.section-header .section-title {
    margin-bottom: 0;
}

/* Control Panel */
.control-form {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.form-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.form-group label {
    font-size: 13px;
    font-weight: 500;
    color: var(--text-secondary);
}

.form-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

.input {
    padding: 12px 16px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    color: var(--text-primary);
    font-size: 14px;
    font-family: var(--font-mono);
    transition: all 0.2s ease;
}

.input:focus {
    outline: none;
    border-color: var(--accent-primary);
    box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
}

.input::placeholder {
    color: var(--text-muted);
}

.button-group {
    display: flex;
    gap: 12px;
    margin-top: 8px;
}

.btn {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    border: none;
    cursor: pointer;
    transition: all 0.2s ease;
}

.btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.btn-primary {
    background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
    color: white;
}

.btn-primary:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 20px rgba(0, 212, 255, 0.3);
}

.btn-danger {
    background: var(--accent-danger);
    color: white;
}

.btn-danger:hover:not(:disabled) {
    background: #dc2626;
}

.btn-small {
    padding: 8px 16px;
    font-size: 12px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
}

.btn-small:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}

/* Stats Grid */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 16px;
    margin-bottom: 24px;
}

.stat-card {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
}

.stat-icon {
    font-size: 28px;
}

.stat-content {
    display: flex;
    flex-direction: column;
}

.stat-value {
    font-size: 24px;
    font-weight: 700;
    font-family: var(--font-mono);
    color: var(--text-primary);
}

.stat-label {
    font-size: 12px;
    color: var(--text-muted);
    margin-top: 4px;
}

.anomaly-card {
    border-color: rgba(245, 158, 11, 0.3);
    background: rgba(245, 158, 11, 0.05);
}

.anomaly-card .stat-value {
    color: var(--accent-warning);
}

/* Log Container */
.log-container {
    max-height: 400px;
    overflow-y: auto;
    font-family: var(--font-mono);
    font-size: 12px;
}

.log-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 48px;
    color: var(--text-muted);
}

.placeholder-icon {
    font-size: 48px;
    margin-bottom: 16px;
}

.placeholder-text {
    font-size: 14px;
}

.log-entry {
    display: flex;
    gap: 12px;
    padding: 8px 12px;
    border-radius: 6px;
    margin-bottom: 4px;
    background: var(--bg-tertiary);
    align-items: center;
}

.log-entry.success {
    border-left: 3px solid var(--accent-success);
}

.log-entry.error {
    border-left: 3px solid var(--accent-danger);
}

.log-entry.anomaly {
    border-left: 3px solid var(--accent-warning);
    background: rgba(245, 158, 11, 0.1);
}

.log-time {
    color: var(--text-muted);
    min-width: 80px;
}

.log-method {
    font-weight: 600;
    min-width: 50px;
}

.log-url {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.log-status {
    min-width: 40px;
    text-align: center;
    padding: 2px 8px;
    border-radius: 4px;
    font-weight: 600;
}

.log-status.s2xx { background: rgba(16, 185, 129, 0.2); color: var(--accent-success); }
.log-status.s3xx { background: rgba(0, 212, 255, 0.2); color: var(--accent-primary); }
.log-status.s4xx { background: rgba(249, 115, 22, 0.2); color: #f97316; }
.log-status.s5xx { background: rgba(239, 68, 68, 0.2); color: var(--accent-danger); }

.log-time-ms {
    min-width: 60px;
    text-align: right;
    color: var(--text-secondary);
}

/* Current Payload */
.payload-display {
    display: block;
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    font-family: var(--font-mono);
    font-size: 14px;
    color: var(--accent-primary);
    word-break: break-all;
}

/* Anomaly List */
.anomaly-item {
    padding: 16px;
    background: var(--bg-tertiary);
    border-radius: 8px;
    margin-bottom: 12px;
    border-left: 3px solid var(--accent-warning);
}

.anomaly-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.anomaly-severity {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
}

.severity-high {
    background: rgba(239, 68, 68, 0.2);
    color: var(--accent-danger);
}

.severity-medium {
    background: rgba(245, 158, 11, 0.2);
    color: var(--accent-warning);
}

.severity-low {
    background: rgba(0, 212, 255, 0.2);
    color: var(--accent-primary);
}

.anomaly-url {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text-primary);
    margin-bottom: 8px;
}

.anomaly-reason {
    font-size: 13px;
    color: var(--text-secondary);
}

/* Table */
.table-container {
    overflow-x: auto;
}

.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

.data-table th,
.data-table td {
    padding: 12px 16px;
    text-align: left;
    border-bottom: 1px solid var(--border-color);
}

.data-table th {
    background: var(--bg-tertiary);
    font-weight: 600;
    color: var(--text-secondary);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.data-table tbody tr:hover {
    background: var(--glass-bg);
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 8px;
    height: 8px;
}

::-webkit-scrollbar-track {
    background: var(--bg-tertiary);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
    background: var(--text-muted);
}

/* Responsive */
@media (max-width: 1400px) {
    .stats-grid {
        grid-template-columns: repeat(3, 1fr);
    }
}

@media (max-width: 1024px) {
    .sidebar {
        width: 200px;
    }
    .main {
        margin-left: 200px;
    }
    .stats-grid {
        grid-template-columns: repeat(2, 1fr);
    }
    .form-row {
        grid-template-columns: 1fr;
    }
}`

const dashboardJS = `// FluxFuzzer Dashboard JavaScript

class FluxFuzzerDashboard {
    constructor() {
        this.ws = null;
        this.isRunning = false;
        this.logs = [];
        this.anomalies = [];
        this.maxLogs = 100;
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.connectWebSocket();
        this.updateUI();
    }

    bindEvents() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigateTo(item.dataset.page);
            });
        });

        // Start/Stop buttons
        document.getElementById('start-btn').addEventListener('click', () => this.startFuzzing());
        document.getElementById('stop-btn').addEventListener('click', () => this.stopFuzzing());
        
        // Clear logs
        document.getElementById('clear-logs').addEventListener('click', () => this.clearLogs());
    }

    navigateTo(page) {
        // Update nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === page);
        });
        
        // Update title
        const titles = {
            dashboard: 'Dashboard',
            logs: 'Request Logs',
            anomalies: 'Anomalies',
            wordlists: 'Wordlists',
            settings: 'Settings'
        };
        document.querySelector('.page-title').textContent = titles[page] || 'Dashboard';
        
        // Show/hide pages
        document.querySelectorAll('.content').forEach(content => {
            content.classList.add('hidden');
        });
        const pageEl = document.getElementById(page + '-page');
        if (pageEl) pageEl.classList.remove('hidden');
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = protocol + '//' + window.location.host + '/ws';
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleMessage(message);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected, reconnecting...');
            setTimeout(() => this.connectWebSocket(), 2000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleMessage(message) {
        switch (message.type) {
            case 'stats':
                this.updateStats(message.data);
                break;
            case 'log':
                this.addLog(message.data);
                break;
            case 'anomaly':
                this.addAnomaly(message.data);
                break;
        }
    }

    updateStats(stats) {
        this.isRunning = stats.isRunning;
        
        document.getElementById('total-requests').textContent = this.formatNumber(stats.totalRequests);
        document.getElementById('success-requests').textContent = this.formatNumber(stats.successRequests);
        document.getElementById('failed-requests').textContent = this.formatNumber(stats.failedRequests);
        document.getElementById('anomalies-found').textContent = this.formatNumber(stats.anomaliesFound);
        document.getElementById('rps-value').textContent = stats.requestsPerSec.toFixed(1);
        document.getElementById('elapsed-time').textContent = stats.elapsedTime || '0s';
        document.getElementById('current-payload').textContent = stats.currentPayload || '-';
        
        this.updateUI();
    }

    addLog(log) {
        this.logs.unshift(log);
        if (this.logs.length > this.maxLogs) {
            this.logs.pop();
        }
        this.renderLogs();
    }

    addAnomaly(anomaly) {
        this.anomalies.unshift(anomaly);
        this.renderAnomalies();
        
        // Update anomaly count
        const count = document.getElementById('anomalies-found');
        count.textContent = parseInt(count.textContent) + 1;
    }

    renderLogs() {
        const container = document.getElementById('log-container');
        
        if (this.logs.length === 0) {
            container.innerHTML = '<div class="log-placeholder"><span class="placeholder-icon">📭</span><span class="placeholder-text">Waiting for requests...</span></div>';
            return;
        }
        
        container.innerHTML = this.logs.map(log => {
            const statusClass = 's' + Math.floor(log.statusCode / 100) + 'xx';
            const entryClass = log.isAnomaly ? 'anomaly' : (log.statusCode >= 400 ? 'error' : 'success');
            const time = new Date(log.timestamp).toLocaleTimeString();
            
            return '<div class="log-entry ' + entryClass + '">' +
                '<span class="log-time">' + time + '</span>' +
                '<span class="log-method">' + log.method + '</span>' +
                '<span class="log-url">' + log.url + '</span>' +
                '<span class="log-status ' + statusClass + '">' + log.statusCode + '</span>' +
                '<span class="log-time-ms">' + log.responseTime + 'ms</span>' +
            '</div>';
        }).join('');
    }

    renderAnomalies() {
        const container = document.getElementById('anomaly-list');
        
        if (this.anomalies.length === 0) {
            container.innerHTML = '<div class="log-placeholder"><span class="placeholder-icon">✨</span><span class="placeholder-text">No anomalies detected yet</span></div>';
            return;
        }
        
        container.innerHTML = this.anomalies.map(a => {
            const severityClass = 'severity-' + a.severity.toLowerCase();
            return '<div class="anomaly-item">' +
                '<div class="anomaly-header">' +
                    '<span class="anomaly-time">' + new Date(a.timestamp).toLocaleString() + '</span>' +
                    '<span class="anomaly-severity ' + severityClass + '">' + a.severity + '</span>' +
                '</div>' +
                '<div class="anomaly-url">' + a.url + '</div>' +
                '<div class="anomaly-reason">Reason: ' + a.reason + '</div>' +
            '</div>';
        }).join('');
    }

    clearLogs() {
        this.logs = [];
        this.renderLogs();
    }

    async startFuzzing() {
        const targetUrl = document.getElementById('target-url').value;
        const wordlist = document.getElementById('wordlist').value;
        const workers = parseInt(document.getElementById('workers').value);
        const rps = parseInt(document.getElementById('rps').value);
        
        if (!targetUrl) {
            alert('Please enter a target URL');
            return;
        }
        
        try {
            const response = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ targetUrl, wordlist, workers, rps })
            });
            
            if (response.ok) {
                this.isRunning = true;
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to start fuzzing:', error);
        }
    }

    async stopFuzzing() {
        try {
            const response = await fetch('/api/stop', { method: 'POST' });
            if (response.ok) {
                this.isRunning = false;
                this.updateUI();
            }
        } catch (error) {
            console.error('Failed to stop fuzzing:', error);
        }
    }

    updateUI() {
        const startBtn = document.getElementById('start-btn');
        const stopBtn = document.getElementById('stop-btn');
        const indicator = document.getElementById('status-indicator');
        
        startBtn.disabled = this.isRunning;
        stopBtn.disabled = !this.isRunning;
        
        if (this.isRunning) {
            indicator.classList.add('running');
            indicator.querySelector('.status-text').textContent = 'Running';
        } else {
            indicator.classList.remove('running');
            indicator.querySelector('.status-text').textContent = 'Idle';
        }
    }

    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }
}

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new FluxFuzzerDashboard();
});`
