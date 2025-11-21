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
        .env 파일에서 ID, PW, Webhook URL 불러오기 
        
        return: dict
            USERNAME: str
            PASSWORD: str 
            DISCORD_WEBHOOK: str
            형태로 반환 
    """
    load_dotenv()
    return {
        "USERNAME": os.getenv("USERNAME"),
        "PASSWORD": os.getenv("PASSWORD"),
        "DISCORD_WEBHOOK": os.getenv("DISCORD_WEBHOOK") 
    }

def set_playwright_and_login(username, password):
    """
        playwright 셋팅

        browser: 
            브라우저 런치 옵션 

        context:
            컨텍스트 정교화 

    """
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled", # 자동화 제어 플래그 숨김 
                "--no-sandbox",
                "--disable-infobars",
                "--window-size=1920,1080",
            ]
        )

        context = browser.new_context(
            # Chrome 최신 버전의 User Agent 설정 
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",

            # 뷰포트 설정 
            viewport= {"width": 1920, "height": 1080},

            # 지역 및 시간대 설정 
            locale="ko-KR",
            timezone_id="Asia/Seoul",

            # 권한 자동 거절 (위치, 알림 팝업이 스크립트 막는거 방지)
            permissions=["geolocation"],
            geolocation={"latitude": 37.5665, "longitude": 126.9780}, # 서울 좌표

            # Webdriver 속성 제거 
            java_script_enabled=True,
        )

        # 팀지 우회 스크립트 주입 
        context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )
        
        page = context.new_page()

        # 로그인 수행 
        print("인스타그램 접속...")
        page.goto("https://www.instagram.com/accounts/login/")
        page.wait_for_timeout(random.randint(500, 1500))

        # 정보 입력 
        print("아이디 및 비밀번호 입력...")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        page.wait_for_timeout(random.randint(500, 1500))
        page.keyboard.press("Enter")
        page.wait_for_timeout(5000)  # 로그인 처리 대기
        print("로그인 완료!")

        # 쿠키 추출 
        """
            나오는 값: 
                csrftoken, mid, 
        """
        cookies = context.cookies()
        cookies_dict = {}
        for cookie in cookies:
            cookies_dict[cookie['name']] = cookie['value']
        
        print("쿠키 추출 완료!")
        return cookies_dict

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
        users_list = []
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
                    users_list.append({
                        "id": user.get("pk"),
                        "username": user.get("username"),
                        "full_name": user.get("full_name")
                    })

            # 다음 페이지 커서 확인 
            next_max_id = data.get("next_max_id")

            if next_max_id:
                    max_id = next_max_id
                    print(f" -> {len(users_list)}명 수집 중... (잠시 대기)")
                    # [중요] Rate Limit 방지: 랜덤 딜레이
                    time.sleep(random.uniform(2, 4)) # 안전하게 시간 늘림
            else:
                print(" -> 마지막 페이지 도달.")
                break
            
        return users_list
        
    results["followers"] = fetch_all("followers")
        
    time.sleep(5)  # [수정] 대기 시간 조금 더 확보
        
    results["following"] = fetch_all("following")

    return results

def save_and_get_results_to_db(results, username):
    """
        결과를 DB에 저장 
    """

    # .env에서 MONGO_URI 불러오기 없으면 에러 발생 
    MONGO_URI = os.getenv("MONGO_URI") 
    if not MONGO_URI:
        print("Error: .env 파일에 MONGO_URI가 설정되지 않았습니다.")
        return

    client = pymongo.MongoClient(MONGO_URI)
    db = client.get_database('webhook')
    
    col_latest = db['Instagram_Latest']   # 최신 상태 저장소
    col_history = db['Instagram_History'] # 변동 내역 저장소
    
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

    # 2. 변동이 있거나, 첫 실행이면 History에 기록
    if new_users or lost_users or not prev_doc:
        history_doc = {
            "date": datetime.datetime.now(),
            "username": username,
            "diff": {
                "new": new_users,
                "lost": lost_users,
                "new_count": len(new_users),
                "lost_count": len(lost_users)
            }
        }
        col_history.insert_one(history_doc)
        print(f"[History] 변동 사항 기록됨 (New: {len(new_users)}, Lost: {len(lost_users)})")
    else:
        print("[History] 변동 사항이 없어 기록을 생략합니다.")

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

if __name__ == "__main__":
    # 1. 계정 정보 들고오기 
    env_vars = get_env_var()
    
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
    save_and_get_results_to_db(results, env_vars["USERNAME"])
    print("모든 작업 완료!")

    # 6. 결과 디스코드로 보내기
    send_discord_webhook(results, env_vars["DISCORD_WEBHOOK"])
