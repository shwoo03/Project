const socketProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const socketUrl = `${socketProtocol}//${window.location.host}/ws`;
let socket;

const containerList = document.getElementById('container-list');
const template = document.getElementById('container-card-template');

// Counters
const totalEl = document.getElementById('total-count');
const runningEl = document.getElementById('running-count');
const stoppedEl = document.getElementById('stopped-count');

function connectWebSocket() {
    socket = new WebSocket(socketUrl);

    socket.onopen = () => {
        console.log("WebSocket Connected");
    };

    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'stats_update') {
            updateDashboard(data.containers, data.stats);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket Disconnected. Reconnecting...");
        setTimeout(connectWebSocket, 3000);
    };
}

function updateDashboard(containers, stats) {
    // 1. Update Counts
    if (totalEl) totalEl.textContent = containers.length;

    const running = containers.filter(c => c.status === 'running').length;
    if (runningEl) runningEl.textContent = running;

    if (stoppedEl) stoppedEl.textContent = containers.length - running;

    // 2. Render Cards
    const currentCardIds = Array.from(document.querySelectorAll('.container-card')).map(el => el.dataset.id);
    const newIds = containers.map(c => c.id);
    const hasChanged = JSON.stringify(currentCardIds.sort()) !== JSON.stringify(newIds.sort());

    if (hasChanged || containerList.children.length === 0) {
        renderContainerCards(containers);
    }

    // 3. Update Stats (CPU/Mem)
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
        if (result.status !== 'success') {
            console.error(result.message);
            alert('Action failed: ' + result.message);
        }
    } catch (e) {
        console.error(e);
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
