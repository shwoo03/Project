import os
import requests
import time
import json
import random
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import pymongo
import datetime


def get_env_var():
    """
        .env 파일에서 ID, PW, Webhook URL, MONGO_URI 불러오기 
        
        return: dict
            USERNAME: str
            PASSWORD: str 
            DISCORD_WEBHOOK: str
            MONGO_URI: str
            형태로 반환 
    """
    # 시스템 환경변수 충돌 및 로딩 실패 방지를 위해 .env 파일을 직접 파싱
    env_vars = {}
    try:
        with open(".env", "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip().strip('"').strip("'")
    except Exception as e:
        # .env 파일이 없거나 읽을 수 없는 경우
        load_dotenv() 
        env_vars = os.environ

    # 변경된 변수명(USER_ID, USER_PASSWORD)으로 조회
    user_id = env_vars.get("USER_ID")
    user_password = env_vars.get("USER_PASSWORD")
    webhook = env_vars.get("DISCORD_WEBHOOK")
    mongo_uri = env_vars.get("MONGO_URI")
    
    if not user_id or not user_password:
        print(" -> [Fatal Error] .env 파일에서 USER_ID 또는 USER_PASSWORD를 찾을 수 없습니다.")
        return None 

    return {
        "USERNAME": user_id,
        "PASSWORD": user_password,
        "DISCORD_WEBHOOK": webhook,
        "MONGO_URI": mongo_uri
    }

def save_cookies(context, path="cookies.json"):
    """쿠키를 파일로 저장"""
    try:
        cookies = context.cookies()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        print(f" -> [Info] 쿠키 저장 완료: {path}")
    except Exception as e:
        print(f" -> [Warning] 쿠키 저장 실패: {e}")

def load_cookies(context, path="cookies.json"):
    """파일에서 쿠키 불러오기"""
    if not os.path.exists(path):
        return False
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
            context.add_cookies(cookies)
        print(f" -> [Info] 쿠키 불러오기 성공: {path}")
        return True
    except Exception as e:
        print(f" -> [Warning] 쿠키 불러오기 실패: {e}")
        return False

def set_playwright_and_login(username, password):
    """
    playwright 셋팅 및 로그인 수행 (Stealth 적용 + Race Condition 해결 + 쿠키 재사용)
    """
    with sync_playwright() as p:
        # 1. 브라우저 실행
        browser = p.chromium.launch(
            headless=True, # 서버 환경에서는 True여야 함
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled", 
                "--no-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport= {"width": 1920, "height": 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            permissions=["geolocation"],
            geolocation={"latitude": 37.5665, "longitude": 126.9780},
            java_script_enabled=True,
        )

        # Stealth 스크립트 주입
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            if (!window.chrome) { window.chrome = { runtime: {} }; }
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        
        page = context.new_page()

        # 2. 쿠키 로드 및 로그인 상태 확인
        if load_cookies(context):
            print(" -> 저장된 쿠키로 접속 시도...")
            page.goto("https://www.instagram.com/")
            time.sleep(3) # 페이지 로딩 대기

            # 로그인 성공 여부 확인 (네비게이션 바 또는 프로필 아이콘 등)
            # '검색', '홈', '프로필' 등의 aria-label이 있는 링크가 뜨면 로그인 성공으로 간주
            try:
                # 홈 버튼이나 프로필 링크가 뜰 때까지 잠시 대기
                page.wait_for_selector('svg[aria-label="홈"]', timeout=5000)
                print(" -> [성공] 쿠키로 로그인 유지 확인됨!")
                
                # 쿠키 리턴
                cookies = context.cookies()
                cookies_dict = {c['name']: c['value'] for c in cookies}
                if 'ds_user_id' in cookies_dict:
                    return cookies_dict
                else:
                    print(" -> [Warning] 로그인 된 것 같으나 ds_user_id가 없음. 재로그인 시도.")
            except:
                print(" -> [Info] 쿠키가 만료되었거나 로그인이 풀림. 다시 로그인합니다.")
        
        # 3. (쿠키 없거나 실패 시) 직접 로그인 진행
        print("인스타그램 로그인 페이지 접속...")
        try:
            page.goto("https://www.instagram.com/accounts/login/", timeout=60000) # 60초 대기
        except Exception as e:
            print(f" -> [Error] 페이지 접속 실패: {e}")
            return {}
        
        # 페이지 로딩 대기 (input 태그가 뜰 때까지)
        try:
            # 20초 동안 username 입력창 대기
            page.wait_for_selector('input[name="username"]', timeout=20000)
        except Exception as e:
            print("[Error] 로그인 페이지 로딩 시간 초과. (화면이 안 떴거나 차단됨)")
            # 디버깅용 스크린샷
            page.screenshot(path="login_page_error.png")
            print(" -> 'login_page_error.png' 스크린샷을 저장했습니다. 확인해보세요.")
            return {}

        # 정보 입력
        print("아이디 및 비밀번호 입력...")
        try:
            page.fill('input[name="username"]', username)
            page.fill('input[name="password"]', password)
        except Exception as e:
             print(f" -> [Error] 입력창을 찾을 수 없습니다: {e}")
             page.screenshot(path="input_error.png")
             return {}

        time.sleep(random.uniform(1, 2))
        
        page.keyboard.press("Enter")
        print("로그인 시도 중... (완료 대기)")

        # 4. 로그인 완료 대기 (URL 변경 or 홈 화면 요소 등장)
        try:
            # 최대 30초 대기. 홈 화면의 특정 요소(예: svg[aria-label="홈"])가 뜰 때까지
            # 또는 URL이 메인으로 바뀔 때까지
            page.wait_for_url("https://www.instagram.com/", timeout=20000)
            print(" -> 메인 URL 진입 성공")
        except Exception as e:
            print(f" -> [Warning] URL 변경 감지 실패: {e}")

        # 5. 각종 팝업 처리 (정보 저장, 알림 설정 등)
        # "나중에 하기" 버튼들을 순차적으로 찾아서 클릭
        popups_handled = 0
        for _ in range(3): # 최대 3번 정도 팝업이 연달아 뜰 수 있음
            try:
                # '나중에 하기' 또는 'Not Now' 버튼 (div 또는 button)
                # text=나중에 하기, role=button 등을 포괄적으로 검색
                not_now_btn = page.wait_for_selector('div[role="button"]:has-text("나중에 하기"), button:has-text("나중에 하기")', timeout=3000)
                if not_now_btn:
                    print(" -> 팝업 발견 ('나중에 하기'), 클릭합니다.")
                    not_now_btn.click()
                    time.sleep(2)
                    popups_handled += 1
                else:
                    break # 팝업 없으면 루프 탈출
            except:
                break # 타임아웃이면 팝업 없는 것

        # 6. 쿠키 추출 및 저장
        print("로그인 프로세스 완료, 쿠키 확인 중...")
        
        # ds_user_id 확인 (최대 20초)
        cookies_dict = {}
        found_cookie = False    
        for i in range(20):
            cookies = context.cookies()
            if any(c['name'] == 'ds_user_id' for c in cookies):
                found_cookie = True
                for cookie in cookies:
                    cookies_dict[cookie['name']] = cookie['value']
                break
            if i % 5 == 0:
                print(f" -> 쿠키 생성 대기 중... ({i+1}/20)")
            time.sleep(1) 
        
        if found_cookie:
            print(f" -> 핵심 쿠키(ds_user_id) 획득 성공! (ID: {cookies_dict.get('ds_user_id')})")
            # [중요] 성공한 쿠키 저장
            save_cookies(context)
            return cookies_dict
        else:
            print(" -> [Error] 로그인 실패 또는 쿠키 획득 시간 초과.")
            # 디버깅을 위해 스크린샷 저장 (선택 사항)
            page.screenshot(path="login_failed.png")
            print(" -> 'login_failed.png' 스크린샷을 저장했습니다.")
            return {}

def create_requests_session(cookies_dict):
    """
        추출한 쿠키로 requests 세션 생성
    """

    session = requests.Session()
    
    # 쿠키 설정 
    for name, value in cookies_dict.items():
        session.cookies.set(name, value)
    
    # 헤더 설정 
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })

    return session

def requests_and_get_followers_and_following(session):
    """
        세션으로 인스타그램 팔로워, 팔로잉 정보 가져오기
    """
    # 내 User ID(pk) 확인 
    target_id = session.cookies.get("ds_user_id")
    
    # target_id가 없는 경우 처리
    if not target_id:
        print("[Error] 'ds_user_id' 쿠키가 없습니다. 로그인이 제대로 되지 않았을 수 있습니다.")
        return {"followers": [], "following": []}

    # 2. 필수 헤더 추가 
    session.headers.update({
        "X-IG-App-ID": "936619743392459", 
        "X-CSRFToken": session.cookies.get("csrftoken"),
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.instagram.com/{target_id}/followers/"
    })

    results = {
        "followers": [],
        "following": []
    }

    def fetch_all(kind):
        users_dict = {} # 중복 제거를 위해 dict 사용 (key: user_id)
        max_id = ""

        print(f"{kind} 데이터 수집 시작...")

        while True:
            url = f"https://www.instagram.com/api/v1/friendships/{target_id}/{kind}/"

            params = {
                "count": 100,
                "search_surface": "follow_list_page",
                "max_id": max_id
            }

            response = session.get(url, params=params)

            # 상태 코드 확인 및 예외 처리 추가
            if response.status_code != 200:
                print(f" -> [Error] API 요청 실패 (Status: {response.status_code})")
                print(f" -> 응답 내용(일부): {response.text[:300]}") # 에러 내용 확인용
                break

            try:
                data = response.json()
            except json.JSONDecodeError:
                print(" -> [Error] 응답이 JSON 형식이 아닙니다. (HTML 반환됨)")
                print(f" -> 응답 내용(일부): {response.text[:300]}")
                break

            for user in data.get("users", []):
                uid = user.get("pk")
                if uid not in users_dict:
                    users_dict[uid] = {
                        "id": uid,
                        "username": user.get("username"),
                        "full_name": user.get("full_name")
                    }

            # 다음 페이지 커서 확인 
            next_max_id = data.get("next_max_id")

            if next_max_id:
                    max_id = next_max_id
                    print(f" -> {len(users_dict)}명 수집 중... (잠시 대기)")
                    # [중요] Rate Limit 방지: 랜덤 딜레이
                    time.sleep(random.uniform(2, 4)) # 안전하게 시간 늘림
            else:
                print(" -> 마지막 페이지 도달.")
                break
            
        return list(users_dict.values())
        
    results["followers"] = fetch_all("followers")
        
    time.sleep(5)  # [수정] 대기 시간 조금 더 확보
        
    results["following"] = fetch_all("following")

    return results

def save_and_get_results_to_db(results, username, mongo_uri):
    """
        결과를 DB에 저장 
    """

    if not mongo_uri:
        print("Error: .env 파일에 MONGO_URI가 설정되지 않았습니다.")
        return

    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client.get_database('webhook')
        
        col_latest = db['Instagram_Latest']   # 최신 상태 저장소
        col_latest = db['Instagram_Latest']   # 최신 상태 저장소
        # col_history = db['Instagram_History'] # [삭제] 변동 내역 저장소 사용 안 함
        
        # 1. 비교를 위해 저장된 최신 상태 가져오기
        prev_doc = col_latest.find_one({"_id": username})
        
        new_users = []
        lost_users = []

        current_data = results 
        
        if prev_doc:
            prev_ids = {u['id'] for u in prev_doc['followers']}
            curr_ids = {u['id'] for u in current_data['followers']}
            
            # Diff 계산
            new_ids = curr_ids - prev_ids
            lost_ids = prev_ids - curr_ids
            
            # 상세 정보 매핑
            new_users = [u for u in current_data['followers'] if u['id'] in new_ids]
            
            # 나간 사람 정보는 이전 문서(prev_doc)에서 찾아야 함
            lost_users = [u for u in prev_doc['followers'] if u['id'] in lost_ids]
        else:
            print("첫 실행입니다. 기준 데이터를 생성합니다.")

        # 2. 변동 사항 로그만 출력 (DB 저장은 안 함)
        if new_users or lost_users:
            print(f" -> [Diff] 변동 사항 발견 (New: {len(new_users)}, Lost: {len(lost_users)})")
        else:
            print(" -> [Diff] 변동 사항 없음.")

        # 3. Latest 상태 업데이트 (항상 최신으로 덮어쓰기)
        # replace_one(filter, replacement, upsert=True)
        col_latest.replace_one(
            {"_id": username}, 
            {
                "followers": current_data["followers"],
                "following": current_data["following"],
                "last_updated": datetime.datetime.now()
            },
            upsert=True
        )
        print("[Latest] 최신 상태 업데이트 완료")
    except Exception as e:
        print(f"[Error] DB 저장 중 오류 발생: {e}")
def send_discord_webhook(data, webhook_url):
    """
    수집 결과를 디스코드 웹훅으로 전송 (이미지 레이아웃 복원 + 링크 기능 추가)
    """
    print("[Discord] 리포트 전송 중...")
    
    # 1. 데이터 가공 (Set 연산)
    followers_set = {u['username'] for u in data['followers']}
    following_set = {u['username'] for u in data['following']}
    
    # A: 나를 맞팔하지 않는 사람
    not_following_back = sorted(list(following_set - followers_set))
    
    # B: 내가 맞팔하지 않는 사람
    im_not_following = sorted(list(followers_set - following_set))

    # 2. 리스트 포맷팅 (링크 생성 함수, 코드 블록 제거)
    def format_users_with_link(user_list):
        if not user_list:
            return "모두 맞팔 중"
        
        formatted_lines = []
        # 디스코드 글자수 제한 고려하여 최대 20명까지만 표시
        limit = 20
        
        for user in user_list[:limit]:
            # [username](url) 형태의 마크다운 링크
            link = f"[{user}](https://www.instagram.com/{user}/)"
            formatted_lines.append(f"- {link}")
            
        result = "\n".join(formatted_lines)
        
        if len(user_list) > limit:
            result += f"\n...외 {len(user_list) - limit}명"
            
        return result

    # 3. Embed 메시지 구성 (요청하신 이미지 스타일 복원)
    payload = {
        "username": "Insta", # 봇 이름 복원
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png",
        "embeds": [
            {
                "title": "Instagram Daily Report",
                "description": f"현재 계정의 팔로워/팔로잉 현황 분석 결과.\n**{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}** 기준",
                "color": 14758252, # 인스타그램 브랜드 컬러 (E1306C)
                "fields": [
                    {
                        "name": "팔로워 (Followers)",
                        "value": f"**{len(followers_set)}**명",
                        "inline": True
                    },
                    {
                        "name": "팔로잉 (Following)",
                        "value": f"**{len(following_set)}**명",
                        "inline": True
                    },
                    {
                        "name": "", "value": "", "inline": False 
                    },
                    {
                        "name": f"나를 맞팔하지 않는 사람 ({len(not_following_back)}명)",
                        # 코드 블록(```)을 제거해야 링크가 작동합니다.
                        "value": format_users_with_link(not_following_back), 
                        "inline": False
                    },
                    {
                        "name": f"내가 맞팔하지 않는 사람 ({len(im_not_following)}명)",
                        # 코드 블록(```)을 제거해야 링크가 작동합니다.
                        "value": format_users_with_link(im_not_following),
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Automated by Python Playwright & Requests"
                }
            }
        ]
    }

    # 4. 전송 (Requests POST)
    try:
        response = requests.post(
            webhook_url, 
            data=json.dumps(payload), 
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 204:
            print(" -> [성공] 디스코드 전송 완료")
        else:
            print(f" -> [실패] 디스코드 에러 코드: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f" -> [에러] 전송 중 예외 발생: {e}")

def check_last_run(username, mongo_uri):
    """
    오늘 이미 실행했는지 확인
    Return: True(이미 실행함), False(아직 안 함)
    """
    if not mongo_uri:
        return False

    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client.get_database('webhook')
        col_latest = db['Instagram_Latest']

        doc = col_latest.find_one({"_id": username})
        if not doc:
            return False
        
        last_updated = doc.get("last_updated")
        if not last_updated:
            return False
        
        # 날짜 비교 (YYYY-MM-DD)
        if last_updated.date() == datetime.datetime.now().date():
            return True
        
        return False

    except Exception as e:
        print(f" -> [Warning] DB 확인 중 오류 발생: {e}")
        return False

if __name__ == "__main__":
    # 1. 계정 정보 들고오기 
    env_vars = get_env_var()
    if not env_vars:
        print("프로그램을 종료합니다.")
        exit(1)
    
    # [추가] 오늘 이미 실행했는지 확인
    if check_last_run(env_vars["USERNAME"], env_vars["MONGO_URI"]):
        print(f" -> [Info] 오늘({datetime.datetime.now().strftime('%Y-%m-%d')}) 이미 실행된 기록이 있습니다.")
        print(" -> 스크립트를 종료합니다.")
        exit(0)
    
    # 2. playwright 실행 및 로그인 후 쿠키 추출 
    cookies_dict = set_playwright_and_login(env_vars["USERNAME"], env_vars["PASSWORD"])

    # 3. 추출한 쿠키로 requests 세션 생성
    session = create_requests_session(cookies_dict)
    print("Requests 세션 생성 완료!")

    # 4. 세션으로 인스타그램 팔로워, 팔로잉 정보 가져오기
    results = requests_and_get_followers_and_following(session)
    print("[결과] 팔로워 수:", len(results["followers"]))
    print("[결과] 팔로잉 수:", len(results["following"]))

    # 5. 결과를 DB에 저장 
    save_and_get_results_to_db(results, env_vars["USERNAME"], env_vars["MONGO_URI"])
    print("모든 작업 완료!")

    # 6. 결과 디스코드로 보내기
    send_discord_webhook(results, env_vars["DISCORD_WEBHOOK"])
