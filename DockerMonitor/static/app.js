const socketProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const socketUrl = `${socketProtocol}//${window.location.host}/ws`;
let socket;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

const containerList = document.getElementById('container-list');
const template = document.getElementById('container-card-template');

// Counters
const totalEl = document.getElementById('total-count');
const runningEl = document.getElementById('running-count');
const stoppedEl = document.getElementById('stopped-count');

// Connection status
const connectionStatusEl = document.getElementById('connection-status');
const statusTextEl = connectionStatusEl?.querySelector('.status-text');

// Toast system
function showToast(message, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icons = {
        error: 'fa-circle-exclamation',
        success: 'fa-circle-check',
        warning: 'fa-triangle-exclamation',
        info: 'fa-circle-info'
    };

    toast.innerHTML = `
        <i class="fas ${icons[type] || icons.info}"></i>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.animation = 'slideIn 0.3s ease reverse';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Connection status management
function setConnectionStatus(status, text) {
    if (!connectionStatusEl) return;

    connectionStatusEl.className = `connection-status ${status}`;
    if (statusTextEl) {
        statusTextEl.textContent = text;
    }
}

function connectWebSocket() {
    setConnectionStatus('connecting', 'Connecting...');
    socket = new WebSocket(socketUrl);

    socket.onopen = () => {
        console.log("WebSocket Connected");
        reconnectAttempts = 0;
        setConnectionStatus('connected', 'Connected');
        showToast('WebSocket connected successfully', 'success', 3000);
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);

        if (data.type === 'error') {
            // Docker daemon offline
            setConnectionStatus('disconnected', 'Docker Offline');
            showDockerOfflineState(data.message);
            return;
        }

        if (data.type === 'stats_update') {
            // Docker is connected
            if (data.docker_connected) {
                setConnectionStatus('connected', 'Connected');
            }
            updateDashboard(data.containers, data.stats);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket Disconnected");
        setConnectionStatus('disconnected', 'Disconnected');

        if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
            reconnectAttempts++;
            const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
            console.log(`Reconnecting in ${delay / 1000}s... (attempt ${reconnectAttempts})`);

            setConnectionStatus('connecting', `Reconnecting (${reconnectAttempts})...`);
            setTimeout(connectWebSocket, delay);
        } else {
            showToast('Connection lost. Please refresh the page.', 'error', 10000);
        }
    };

    socket.onerror = (error) => {
        console.error("WebSocket Error:", error);
    };
}

function showDockerOfflineState(message) {
    containerList.innerHTML = `
        <div class="empty-state">
            <i class="fab fa-docker"></i>
            <h3>Docker Daemon Unavailable</h3>
            <p>${message || 'Please make sure Docker Desktop is running.'}</p>
        </div>
    `;

    // Reset counters
    if (totalEl) totalEl.textContent = '-';
    if (runningEl) runningEl.textContent = '-';
    if (stoppedEl) stoppedEl.textContent = '-';
}

function updateDashboard(containers, stats) {
    // 1. Update Counts
    if (totalEl) totalEl.textContent = containers.length;

    const running = containers.filter(c => c.status === 'running').length;
    if (runningEl) runningEl.textContent = running;

    if (stoppedEl) stoppedEl.textContent = containers.length - running;

    // 2. Handle empty state
    if (containers.length === 0) {
        containerList.innerHTML = `
            <div class="empty-state">
                <i class="fab fa-docker"></i>
                <h3>No Containers Found</h3>
                <p>Start a container to see it here.</p>
            </div>
        `;
        return;
    }

    // 3. Render Cards
    const currentCardIds = Array.from(document.querySelectorAll('.container-card')).map(el => el.dataset.id);
    const newIds = containers.map(c => c.id);
    const hasChanged = JSON.stringify(currentCardIds.sort()) !== JSON.stringify(newIds.sort());

    if (hasChanged || containerList.children.length === 0 || containerList.querySelector('.empty-state')) {
        renderContainerCards(containers);
    }

    // 4. Update Stats (CPU/Mem)
    updateStats(stats, containers);
}

function renderContainerCards(containers) {
    containerList.innerHTML = '';

    containers.forEach(container => {
        const clone = template.content.cloneNode(true);
        const card = clone.querySelector('.container-card');
        card.dataset.id = container.id;

        card.querySelector('.name-text').textContent = container.name;
        card.querySelector('.id-text').textContent = container.id.substring(0, 8);
        card.querySelector('.image-text').textContent = container.image;

        // Format Ports
        let portsText = "";
        if (container.ports) {
            const ports = Object.keys(container.ports);
            if (ports.length > 0) portsText = ports[0];
        }
        card.querySelector('.port-text').textContent = portsText;

        // Status
        const indicator = card.querySelector('.status-dot');
        if (container.status === 'running') {
            indicator.classList.add('running');
        } else {
            indicator.classList.remove('running');
        }

        // Buttons
        const startBtn = card.querySelector('.start-btn');
        const stopBtn = card.querySelector('.stop-btn');
        const restartBtn = card.querySelector('.restart-btn');

        // Check if buttons exist (restart might be optional in template)
        if (startBtn) startBtn.onclick = () => actionContainer(container.id, 'start');
        if (stopBtn) stopBtn.onclick = () => actionContainer(container.id, 'stop');
        if (restartBtn) restartBtn.onclick = () => actionContainer(container.id, 'restart');

        // Visibility Logic
        if (container.status === 'running') {
            if (startBtn) startBtn.style.display = 'none';
        } else {
            if (stopBtn) stopBtn.style.display = 'none';
            if (restartBtn) restartBtn.style.display = 'none';
        }

        containerList.appendChild(card);
    });
}

function updateStats(stats, containers) {
    stats.forEach(stat => {
        const card = document.querySelector(`.container-card[data-id="${stat.id}"]`);
        if (card) {
            const cpuVal = card.querySelector('.cpu-val');
            const memVal = card.querySelector('.mem-val');

            if (cpuVal) cpuVal.textContent = `${stat.cpu_percent}%`;
            if (memVal) memVal.textContent = formatBytes(stat.memory_usage);
        }
    });

    // Update status indicators and buttons if changed
    containers.forEach(c => {
        const card = document.querySelector(`.container-card[data-id="${c.id}"]`);
        if (card) {
            const indicator = card.querySelector('.status-dot');
            const startBtn = card.querySelector('.start-btn');
            const stopBtn = card.querySelector('.stop-btn');
            const restartBtn = card.querySelector('.restart-btn');

            if (c.status === 'running') {
                if (indicator) indicator.classList.add('running');
                if (startBtn) startBtn.style.display = 'none';
                if (stopBtn) stopBtn.style.display = 'inline-block';
                if (restartBtn) restartBtn.style.display = 'inline-block';
            } else {
                if (indicator) indicator.classList.remove('running');
                if (startBtn) startBtn.style.display = 'inline-block';
                if (stopBtn) stopBtn.style.display = 'none';
                if (restartBtn) restartBtn.style.display = 'none';
            }
        }
    });
}

async function actionContainer(id, action) {
    try {
        const res = await fetch(`/api/containers/${id}/action`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action })
        });
        const result = await res.json();
        if (result.status === 'success') {
            showToast(`Container ${action} successful`, 'success', 3000);
        } else {
            console.error(result.message);
            showToast(`Action failed: ${result.message}`, 'error');
        }
    } catch (e) {
        console.error(e);
        showToast(`Error: ${e.message}`, 'error');
    }
}

function formatBytes(bytes, decimals = 2) {
    if (!+bytes) return '0 B';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(dm))}${sizes[i]}`;
}

// Init
document.addEventListener('DOMContentLoaded', connectWebSocket);
