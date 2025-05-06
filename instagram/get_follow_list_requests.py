import requests
import time

# 쿠키 추출 다음 코드에서 requests 세션에 사용 
def extract_cookies(driver):
    raw_cookies = driver.get_cookies()
    cookie_dict = {cookie['name']: cookie['value'] for cookie in raw_cookies}
    return cookie_dict


# 팔로우/팔로잉 리스트 가져오기
def get_follow_list(user_id, follow_type, cookies, limit=None):
    assert follow_type in ['followers', 'following'] 
    
    url_base = f"https://www.instagram.com/api/v1/friendships/{user_id}/{follow_type}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-CSRFToken": cookies.get("csrftoken", ""),
        "X-IG-App-ID": "936619743392459",   # 웹/ 모바일 인지 확인하는 값임 사용자마다 모두 같음 
        "Referer": f"https://www.instagram.com/{user_id}/"
    }

    session = requests.Session()
    session.headers.update(headers)
    session.cookies.update(cookies)

    result = []
    next_max_id = None

    while True:
        params = {"count": 50}
        if next_max_id:
            params["max_id"] = next_max_id

        res = session.get(url_base, params=params)
        if res.status_code != 200:
            print(f"Debug 요청 실패!!!!!!!!!! {res.status_code}")
            break

        data = res.json()
        users = data.get("users", [])
        result.extend([user["username"] for user in users])

        if limit and len(result) >= limit:
            break

        next_max_id = data.get("next_max_id")
        if not next_max_id:
            break

        time.sleep(1)

    return result