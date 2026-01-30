"""
인스타그램 팔로워 추적기 - 통합 웹 대시보드
웹에서 모든 기능 제어 가능
"""
import asyncio
import logging
import datetime
import os
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('instagram_tracker.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 모듈 import
from config import get_env_var
from auth_async import login_async
from api_async import get_followers_and_following_async
from database import get_mongo_client, check_last_run, save_and_get_results_to_db, save_history, get_history, get_change_summary
from notification import send_discord_webhook, send_change_notification
from scheduler import get_scheduler, schedule_daily_run, remove_schedule, get_schedule_info, shutdown_scheduler

# 상태 관리
class AppState:
    is_running: bool = False
    last_log: str = ""
    progress: int = 0
    websocket_clients: list = []

state = AppState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 실행"""
    logger.info("대시보드 서버 시작")
    get_scheduler()  # 스케줄러 초기화
    yield
    shutdown_scheduler()  # 스케줄러 종료
    logger.info("대시보드 서버 종료")


app = FastAPI(
    title="Instagram Follower Tracker",
    description="인스타그램 팔로워 추적 대시보드",
    version="2.0.0",
    lifespan=lifespan
)


# WebSocket 클라이언트에 메시지 브로드캐스트
async def broadcast_log(message: str):
    state.last_log = message
    for client in state.websocket_clients:
        try:
            await client.send_json({"type": "log", "message": message})
        except:
            pass


async def broadcast_progress(progress: int, status: str):
    state.progress = progress
    for client in state.websocket_clients:
        try:
            await client.send_json({"type": "progress", "progress": progress, "status": status})
        except:
            pass


def get_db_data():
    """MongoDB에서 최신 데이터 조회"""
    env_vars = get_env_var()
    if not env_vars or not env_vars.get("MONGO_URI"):
        return None
    
    client = get_mongo_client(env_vars["MONGO_URI"])
    if not client:
        return None
    
    db = client.get_database('webhook')
    col_latest = db['Instagram_Latest']
    doc = col_latest.find_one({"_id": env_vars["USERNAME"]})
    return doc


async def run_tracker_task():
    """백그라운드에서 팔로워 추적 실행"""
    if state.is_running:
        await broadcast_log("⚠️ 이미 실행 중입니다.")
        return
    
    state.is_running = True
    
    try:
        await broadcast_progress(5, "환경 변수 로드 중...")
        env_vars = get_env_var()
        if not env_vars:
            await broadcast_log("❌ 환경 변수 로드 실패")
            return
        
        await broadcast_progress(10, "오늘 실행 여부 확인 중...")
        # 중복 실행 체크 (웹에서는 건너뛰기 옵션 제공)
        
        await broadcast_progress(20, "인스타그램 로그인 중...")
        await broadcast_log("🔐 Playwright 로그인 시작...")
        cookies_dict = await login_async(env_vars["USERNAME"], env_vars["PASSWORD"])
        
        if not cookies_dict:
            await broadcast_log("❌ 로그인 실패")
            await broadcast_progress(0, "실패")
            return
        
        await broadcast_log("✅ 로그인 성공!")
        await broadcast_progress(40, "팔로워 데이터 수집 중...")
        
        results = await get_followers_and_following_async(cookies_dict)
        
        await broadcast_log(f"📊 팔로워: {len(results['followers'])}명, 팔로잉: {len(results['following'])}명")
        await broadcast_progress(70, "데이터베이스 저장 중...")
        
        diff_result = save_and_get_results_to_db(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
        save_history(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
        await broadcast_log("💾 DB 저장 완료! (히스토리 포함)")
        
        # 변동 사항 알림
        new_followers = diff_result.get("new_followers", [])
        lost_followers = diff_result.get("lost_followers", [])
        
        if new_followers or lost_followers:
            await broadcast_log(f"🔔 변동 감지: +{len(new_followers)} / -{len(lost_followers)}")
        
        await broadcast_progress(85, "Discord 알림 전송 중...")
        
        if env_vars.get("DISCORD_WEBHOOK") and env_vars["DISCORD_WEBHOOK"].lower() not in ["none", ""]:
            # 전체 리포트
            send_discord_webhook(results, env_vars["DISCORD_WEBHOOK"])
            # 변동 알림 (변동이 있을 때만)
            if new_followers or lost_followers:
                send_change_notification(new_followers, lost_followers, env_vars["DISCORD_WEBHOOK"])
            await broadcast_log("📨 Discord 전송 완료!")
        else:
            await broadcast_log("ℹ️ Discord Webhook 미설정")
        
        await broadcast_progress(100, "완료!")
        await broadcast_log("🎉 모든 작업이 완료되었습니다!")
        
    except Exception as e:
        await broadcast_log(f"❌ 오류 발생: {str(e)}")
        await broadcast_progress(0, "오류")
        logger.error(f"Tracker 실행 오류: {e}")
    finally:
        state.is_running = False


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """실시간 로그 WebSocket"""
    await websocket.accept()
    state.websocket_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트 메시지 처리 (핑 등)
    except WebSocketDisconnect:
        state.websocket_clients.remove(websocket)


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """메인 대시보드 HTML"""
    data = get_db_data()
    
    followers_count = len(data.get("followers", [])) if data else 0
    following_count = len(data.get("following", [])) if data else 0
    last_updated = data.get("last_updated", "없음") if data else "없음"
    
    if isinstance(last_updated, datetime.datetime):
        last_updated = last_updated.strftime('%Y-%m-%d %H:%M:%S')
    
    # 맞팔 분석
    not_following_back_count = 0
    im_not_following_count = 0
    not_following_back_list = []
    im_not_following_list = []
    
    if data:
        followers_set = {u['username'] for u in data.get("followers", [])}
        following_set = {u['username'] for u in data.get("following", [])}
        not_following_back_list = sorted(list(following_set - followers_set))
        im_not_following_list = sorted(list(followers_set - following_set))
        not_following_back_count = len(not_following_back_list)
        im_not_following_count = len(im_not_following_list)
    
    def render_user_list(users, limit=30):
        if not users:
            return '<div class="empty">모두 맞팔 중! ✅</div>'
        html = '<ul class="user-list">'
        for user in users[:limit]:
            html += f'<li><a href="https://www.instagram.com/{user}/" target="_blank">{user}</a></li>'
        if len(users) > limit:
            html += f'<li class="more">...외 {len(users) - limit}명</li>'
        html += '</ul>'
        return html
    
    return f"""
    <!DOCTYPE html>
    <html lang="ko">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Instagram Tracker Dashboard</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
                color: #fff;
                min-height: 100vh;
            }}
            .container {{ max-width: 1400px; margin: 0 auto; padding: 30px; }}
            
            header {{
                text-align: center;
                margin-bottom: 40px;
            }}
            header h1 {{
                font-size: 2.8rem;
                background: linear-gradient(90deg, #f093fb, #f5576c, #4facfe);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 10px;
            }}
            .subtitle {{ color: #888; font-size: 0.95rem; }}
            
            .stats-grid {{
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 20px;
                margin-bottom: 30px;
            }}
            .stat-card {{
                background: rgba(255,255,255,0.08);
                border-radius: 20px;
                padding: 25px;
                text-align: center;
                backdrop-filter: blur(10px);
                border: 1px solid rgba(255,255,255,0.1);
                transition: transform 0.3s, box-shadow 0.3s;
            }}
            .stat-card:hover {{
                transform: translateY(-5px);
                box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            }}
            .stat-card .number {{
                font-size: 3rem;
                font-weight: 700;
                background: linear-gradient(90deg, #4facfe, #00f2fe);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }}
            .stat-card .label {{ color: #aaa; margin-top: 8px; }}
            
            .control-panel {{
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 30px;
                margin-bottom: 30px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .control-panel h2 {{
                margin-bottom: 20px;
                color: #f5576c;
            }}
            
            .run-btn {{
                background: linear-gradient(90deg, #f093fb, #f5576c);
                border: none;
                padding: 18px 50px;
                font-size: 1.1rem;
                color: white;
                border-radius: 50px;
                cursor: pointer;
                transition: transform 0.2s, box-shadow 0.2s;
                font-weight: 600;
            }}
            .run-btn:hover {{
                transform: scale(1.05);
                box-shadow: 0 10px 30px rgba(245, 87, 108, 0.4);
            }}
            .run-btn:disabled {{
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }}
            
            .progress-container {{
                margin-top: 25px;
                display: none;
            }}
            .progress-bar {{
                height: 8px;
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                overflow: hidden;
            }}
            .progress-fill {{
                height: 100%;
                background: linear-gradient(90deg, #4facfe, #00f2fe);
                width: 0%;
                transition: width 0.3s;
            }}
            .progress-status {{
                margin-top: 10px;
                color: #888;
                font-size: 0.9rem;
            }}
            
            .log-container {{
                margin-top: 20px;
                background: rgba(0,0,0,0.3);
                border-radius: 12px;
                padding: 15px;
                max-height: 200px;
                overflow-y: auto;
                font-family: 'Consolas', monospace;
                font-size: 0.85rem;
            }}
            .log-line {{
                padding: 5px 0;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }}
            
            .lists-grid {{
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 25px;
            }}
            .list-card {{
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 25px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .list-card h3 {{
                color: #f5576c;
                margin-bottom: 15px;
                font-size: 1.1rem;
            }}
            .user-list {{
                list-style: none;
                max-height: 350px;
                overflow-y: auto;
            }}
            .user-list li {{
                padding: 10px 0;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }}
            .user-list a {{
                color: #4facfe;
                text-decoration: none;
                transition: color 0.2s;
            }}
            .user-list a:hover {{ color: #00f2fe; }}
            .user-list .more {{ color: #888; font-style: italic; }}
            .empty {{ color: #4ade80; }}
            
            /* 토스트 알림 */
            .toast {{
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 20px 30px;
                border-radius: 15px;
                font-size: 1.1rem;
                font-weight: 600;
                z-index: 1000;
                animation: slideIn 0.5s ease, fadeOut 0.5s ease 4.5s;
                box-shadow: 0 10px 40px rgba(0,0,0,0.3);
            }}
            .toast.success {{
                background: linear-gradient(135deg, #4ade80, #22c55e);
                color: white;
            }}
            .toast.error {{
                background: linear-gradient(135deg, #f87171, #ef4444);
                color: white;
            }}
            @keyframes slideIn {{
                from {{ transform: translateX(100%); opacity: 0; }}
                to {{ transform: translateX(0); opacity: 1; }}
            }}
            @keyframes fadeOut {{
                from {{ opacity: 1; }}
                to {{ opacity: 0; }}
            }}
            
            /* 완료 배너 */
            .completion-banner {{
                display: none;
                background: linear-gradient(135deg, #4ade80, #22c55e);
                border-radius: 15px;
                padding: 25px;
                margin-top: 20px;
                text-align: center;
                animation: pulse 1s ease infinite;
            }}
            .completion-banner.show {{ display: block; }}
            .completion-banner h3 {{ font-size: 1.5rem; margin-bottom: 10px; }}
            .completion-banner p {{ opacity: 0.9; }}
            @keyframes pulse {{
                0%, 100% {{ transform: scale(1); }}
                50% {{ transform: scale(1.02); }}
            }}
            
            .trend-section {{
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 25px;
                margin-bottom: 30px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .trend-section h2 {{
                color: #4facfe;
                margin-bottom: 20px;
            }}
            
            .schedule-section {{
                background: rgba(255,255,255,0.05);
                border-radius: 20px;
                padding: 25px;
                margin-bottom: 30px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .schedule-section h2 {{
                color: #fbbf24;
                margin-bottom: 20px;
            }}
            .schedule-controls {{
                display: flex;
                align-items: center;
                gap: 20px;
                flex-wrap: wrap;
            }}
            .schedule-time {{
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .time-input {{
                width: 60px;
                padding: 10px;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 8px;
                background: rgba(0,0,0,0.3);
                color: white;
                text-align: center;
                font-size: 1.2rem;
            }}
            .schedule-btn {{
                padding: 10px 20px;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                background: linear-gradient(90deg, #4facfe, #00f2fe);
                color: white;
            }}
            .schedule-btn.danger {{
                background: linear-gradient(90deg, #f87171, #ef4444);
            }}
            .schedule-status {{
                margin-top: 15px;
                padding: 10px;
                border-radius: 8px;
                background: rgba(0,0,0,0.2);
            }}
            
            .search-input {{
                width: 100%;
                padding: 12px;
                margin-bottom: 15px;
                border: 1px solid rgba(255,255,255,0.2);
                border-radius: 10px;
                background: rgba(0,0,0,0.3);
                color: white;
                font-size: 1rem;
            }}
            .search-input::placeholder {{ color: #888; }}
            .search-input:focus {{
                outline: none;
                border-color: #4facfe;
            }}
            
            @media (max-width: 900px) {{
                .stats-grid {{ grid-template-columns: repeat(2, 1fr); }}
                .lists-grid {{ grid-template-columns: 1fr; }}
            }}
        </style>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>📊 Instagram Follower Tracker</h1>
                <p class="subtitle">마지막 업데이트: {last_updated}</p>
            </header>
            
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="number">{followers_count}</div>
                    <div class="label">팔로워</div>
                </div>
                <div class="stat-card">
                    <div class="number">{following_count}</div>
                    <div class="label">팔로잉</div>
                </div>
                <div class="stat-card">
                    <div class="number">{not_following_back_count}</div>
                    <div class="label">맞팔 안 해주는</div>
                </div>
                <div class="stat-card">
                    <div class="number">{im_not_following_count}</div>
                    <div class="label">내가 맞팔 안 한</div>
                </div>
            </div>
            
            <div class="control-panel">
                <h2>🎮 컨트롤 패널</h2>
                <button class="run-btn" id="runBtn" onclick="runTracker()">
                    🚀 지금 실행하기
                </button>
                
                <div class="progress-container" id="progressContainer">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progressFill"></div>
                    </div>
                    <div class="progress-status" id="progressStatus">준비 중...</div>
                </div>
                
                <div class="completion-banner" id="completionBanner">
                    <h3>🎉 작업 완료!</h3>
                    <p>팔로워 데이터가 성공적으로 업데이트되었습니다. 잠시 후 페이지가 새로고침됩니다...</p>
                </div>
                
                <div class="log-container" id="logContainer"></div>
            </div>
            
            <div class="trend-section">
                <h2>📈 팔로워 트렌드</h2>
                <canvas id="trendChart" width="400" height="150"></canvas>
            </div>
            
            <div class="schedule-section">
                <h2>⏰ 자동 실행 스케줄</h2>
                <div class="schedule-controls">
                    <div class="schedule-time">
                        <label>매일</label>
                        <input type="number" id="scheduleHour" min="0" max="23" value="9" class="time-input">
                        <span>:</span>
                        <input type="number" id="scheduleMinute" min="0" max="59" value="0" class="time-input">
                        <span>에 실행</span>
                    </div>
                    <div class="schedule-buttons">
                        <button onclick="setSchedule()" class="schedule-btn">저장</button>
                        <button onclick="removeSchedule()" class="schedule-btn danger">삭제</button>
                    </div>
                </div>
                <div id="scheduleStatus" class="schedule-status"></div>
            </div>
            
            <div class="lists-grid">
                <div class="list-card">
                    <h3>❌ 나를 맞팔하지 않는 사람 ({not_following_back_count}명)</h3>
                    <input type="text" class="search-input" placeholder="🔍 검색..." onkeyup="filterList(this, 'notFollowingList')">
                    <div id="notFollowingList">{render_user_list(not_following_back_list)}</div>
                </div>
                <div class="list-card">
                    <h3>🤝 내가 맞팔하지 않는 사람 ({im_not_following_count}명)</h3>
                    <input type="text" class="search-input" placeholder="🔍 검색..." onkeyup="filterList(this, 'imNotFollowingList')">
                    <div id="imNotFollowingList">{render_user_list(im_not_following_list)}</div>
                </div>
            </div>
        </div>
        
        <script>
            let ws = null;
            
            function showToast(message, type = 'success') {{
                const toast = document.createElement('div');
                toast.className = 'toast ' + type;
                toast.textContent = message;
                document.body.appendChild(toast);
                
                setTimeout(() => toast.remove(), 5000);
            }}
            
            function connectWebSocket() {{
                const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
                ws = new WebSocket(protocol + '//' + window.location.host + '/ws');
                
                ws.onmessage = function(event) {{
                    const data = JSON.parse(event.data);
                    
                    if (data.type === 'log') {{
                        addLog(data.message);
                    }} else if (data.type === 'progress') {{
                        updateProgress(data.progress, data.status);
                    }}
                }};
                
                ws.onclose = function() {{
                    setTimeout(connectWebSocket, 3000);
                }};
            }}
            
            function addLog(message) {{
                const container = document.getElementById('logContainer');
                const line = document.createElement('div');
                line.className = 'log-line';
                line.textContent = new Date().toLocaleTimeString() + ' - ' + message;
                container.appendChild(line);
                container.scrollTop = container.scrollHeight;
                
                // 완료 메시지 감지
                if (message.includes('모든 작업이 완료')) {{
                    showToast('✅ 팔로워 추적 완료!');
                }}
                if (message.includes('오류 발생')) {{
                    showToast('❌ ' + message, 'error');
                }}
            }}
            
            function updateProgress(progress, status) {{
                const progressFill = document.getElementById('progressFill');
                const progressStatus = document.getElementById('progressStatus');
                const runBtn = document.getElementById('runBtn');
                const banner = document.getElementById('completionBanner');
                
                progressFill.style.width = progress + '%';
                progressStatus.textContent = status + ' (' + progress + '%)';
                
                if (progress === 100) {{
                    // 완료!
                    runBtn.disabled = false;
                    runBtn.textContent = '✅ 완료! 새로고침 중...';
                    runBtn.style.background = 'linear-gradient(90deg, #4ade80, #22c55e)';
                    banner.classList.add('show');
                    
                    // 3초 후 새로고침
                    setTimeout(() => location.reload(), 3000);
                }} else if (progress === 0 && status === '오류') {{
                    runBtn.disabled = false;
                    runBtn.textContent = '🔄 다시 시도';
                    runBtn.style.background = 'linear-gradient(90deg, #f87171, #ef4444)';
                }}
            }}
            
            async function runTracker() {{
                const btn = document.getElementById('runBtn');
                btn.disabled = true;
                btn.textContent = '⏳ 실행 중...';
                
                document.getElementById('progressContainer').style.display = 'block';
                document.getElementById('completionBanner').classList.remove('show');
                document.getElementById('logContainer').innerHTML = '';
                
                try {{
                    const response = await fetch('/api/run', {{ method: 'POST' }});
                    const result = await response.json();
                    addLog(result.message);
                }} catch (error) {{
                    addLog('❌ 요청 실패: ' + error.message);
                    btn.disabled = false;
                    btn.textContent = '🚀 지금 실행하기';
                }}
            }}
            
            connectWebSocket();
            
            // 트렌드 차트 로드
            async function loadTrendChart() {{
                try {{
                    const response = await fetch('/api/history?days=14');
                    const data = await response.json();
                    
                    if (!data.history || data.history.length === 0) {{
                        document.querySelector('.trend-section').innerHTML = 
                            '<h2>📈 팔로워 트렌드</h2><p style="color:#888;">데이터가 아직 없습니다. 추적을 실행해주세요.</p>';
                        return;
                    }}
                    
                    const labels = data.history.map(h => h.date);
                    const followersData = data.history.map(h => h.followers);
                    const followingData = data.history.map(h => h.following);
                    
                    const ctx = document.getElementById('trendChart').getContext('2d');
                    new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: labels,
                            datasets: [
                                {{
                                    label: '팔로워',
                                    data: followersData,
                                    borderColor: '#4facfe',
                                    backgroundColor: 'rgba(79, 172, 254, 0.1)',
                                    tension: 0.3,
                                    fill: true
                                }},
                                {{
                                    label: '팔로잉',
                                    data: followingData,
                                    borderColor: '#f5576c',
                                    backgroundColor: 'rgba(245, 87, 108, 0.1)',
                                    tension: 0.3,
                                    fill: true
                                }}
                            ]
                        }},
                        options: {{
                            responsive: true,
                            plugins: {{
                                legend: {{
                                    labels: {{ color: '#fff' }}
                                }}
                            }},
                            scales: {{
                                x: {{
                                    ticks: {{ color: '#888' }},
                                    grid: {{ color: 'rgba(255,255,255,0.05)' }}
                                }},
                                y: {{
                                    ticks: {{ color: '#888' }},
                                    grid: {{ color: 'rgba(255,255,255,0.05)' }}
                                }}
                            }}
                        }}
                    }});
                }} catch (error) {{
                    console.error('차트 로드 실패:', error);
                }}
            }}
            
            loadTrendChart();
            
            // 스케줄 관리 함수
            async function loadSchedule() {{
                try {{
                    const response = await fetch('/api/schedule');
                    const data = await response.json();
                    
                    document.getElementById('scheduleHour').value = data.hour || 9;
                    document.getElementById('scheduleMinute').value = data.minute || 0;
                    
                    const statusEl = document.getElementById('scheduleStatus');
                    if (data.enabled) {{
                        statusEl.innerHTML = `✅ 스케줄 활성: 다음 실행 ${{data.next_run || '계산 중...'}}`;
                        statusEl.style.color = '#4ade80';
                    }} else {{
                        statusEl.innerHTML = '❌ 스케줄 비활성';
                        statusEl.style.color = '#f87171';
                    }}
                }} catch (error) {{
                    console.error('스케줄 로드 실패:', error);
                }}
            }}
            
            async function setSchedule() {{
                const hour = parseInt(document.getElementById('scheduleHour').value);
                const minute = parseInt(document.getElementById('scheduleMinute').value);
                
                try {{
                    const response = await fetch(`/api/schedule?hour=${{hour}}&minute=${{minute}}`, {{ method: 'POST' }});
                    const data = await response.json();
                    
                    showToast(data.message, data.status === 'success' ? 'success' : 'error');
                    loadSchedule();
                }} catch (error) {{
                    showToast('스케줄 설정 실패', 'error');
                }}
            }}
            
            async function removeSchedule() {{
                try {{
                    const response = await fetch('/api/schedule', {{ method: 'DELETE' }});
                    const data = await response.json();
                    
                    showToast(data.message, 'success');
                    loadSchedule();
                }} catch (error) {{
                    showToast('스케줄 삭제 실패', 'error');
                }}
            }}
            
            // 사용자 검색 필터
            function filterList(inputEl, listId) {{
                const query = inputEl.value.toLowerCase();
                const listEl = document.getElementById(listId);
                const items = listEl.querySelectorAll('.user-item');
                
                items.forEach(item => {{
                    const username = item.textContent.toLowerCase();
                    if (username.includes(query)) {{
                        item.style.display = '';
                    }} else {{
                        item.style.display = 'none';
                    }}
                }});
            }}
            
            // 페이지 로드 시 스케줄 정보 가져오기
            loadSchedule();
        </script>
    </body>
    </html>
    """


@app.post("/api/run")
async def api_run(background_tasks: BackgroundTasks):
    """팔로워 추적 실행 API"""
    if state.is_running:
        return JSONResponse({"status": "error", "message": "이미 실행 중입니다"}, status_code=409)
    
    background_tasks.add_task(run_tracker_task)
    return {"status": "started", "message": "🚀 팔로워 추적을 시작합니다..."}


@app.get("/api/status")
async def api_status():
    """상태 API"""
    data = get_db_data()
    return {
        "is_running": state.is_running,
        "progress": state.progress,
        "last_log": state.last_log,
        "has_data": data is not None,
        "last_updated": data.get("last_updated") if data else None,
        "followers_count": len(data.get("followers", [])) if data else 0,
        "following_count": len(data.get("following", [])) if data else 0
    }


@app.get("/api/latest")
async def api_latest():
    """최신 데이터 API"""
    data = get_db_data()
    if not data:
        return {"error": "데이터가 없습니다"}
    
    followers = data.get("followers", [])
    following = data.get("following", [])
    followers_set = {u['username'] for u in followers}
    following_set = {u['username'] for u in following}
    
    return {
        "last_updated": data.get("last_updated"),
        "followers_count": len(followers),
        "following_count": len(following),
        "not_following_back": sorted(list(following_set - followers_set)),
        "im_not_following": sorted(list(followers_set - following_set))
    }


@app.get("/api/history")
async def api_history(days: int = 30):
    """히스토리 데이터 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    history = get_history(env_vars["USERNAME"], env_vars["MONGO_URI"], days)
    
    # 날짜를 문자열로 변환
    formatted = []
    for record in history:
        formatted.append({
            "date": record["date"].strftime("%Y-%m-%d") if record.get("date") else None,
            "followers": record.get("followers_count", 0),
            "following": record.get("following_count", 0)
        })
    
    return {"history": formatted}


@app.get("/api/changes")
async def api_changes():
    """변동 요약 API"""
    env_vars = get_env_var()
    if not env_vars:
        return {"error": "환경 변수 로드 실패"}
    
    summary = get_change_summary(env_vars["USERNAME"], env_vars["MONGO_URI"])
    return summary or {"has_change": False, "message": "데이터 없음"}


@app.get("/api/schedule")
async def api_get_schedule():
    """현재 스케줄 정보 조회"""
    return get_schedule_info()


@app.post("/api/schedule")
async def api_set_schedule(hour: int = 9, minute: int = 0):
    """스케줄 설정"""
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return {"error": "잘못된 시간 형식"}
    
    success = schedule_daily_run(hour, minute, run_tracker_task)
    if success:
        return {"status": "success", "message": f"스케줄 설정: 매일 {hour:02d}:{minute:02d}"}
    return {"status": "error", "message": "스케줄 설정 실패"}


@app.delete("/api/schedule")
async def api_delete_schedule():
    """스케줄 삭제"""
    success = remove_schedule()
    if success:
        return {"status": "success", "message": "스케줄이 삭제되었습니다"}
    return {"status": "info", "message": "삭제할 스케줄이 없습니다"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


