"""
인스타그램 API 호출 (팔로워/팔로잉 수집)
"""
import time
import json
import random
import logging
import requests

logger = logging.getLogger(__name__)


def create_requests_session(cookies_dict):
    """추출한 쿠키로 requests 세션 생성"""
    session = requests.Session()
    
    for name, value in cookies_dict.items():
        session.cookies.set(name, value)
    
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })

    return session


def requests_and_get_followers_and_following(session):
    """세션으로 인스타그램 팔로워, 팔로잉 정보 가져오기"""
    target_id = session.cookies.get("ds_user_id")
    
    if not target_id:
        logger.error("'ds_user_id' 쿠키가 없습니다. 로그인이 제대로 되지 않았을 수 있습니다.")
        return {"followers": [], "following": []}

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
        users_dict = {}
        max_id = ""

        logger.info(f"{kind} 데이터 수집 시작...")

        while True:
            url = f"https://www.instagram.com/api/v1/friendships/{target_id}/{kind}/"

            params = {
                "count": 100,
                "search_surface": "follow_list_page",
                "max_id": max_id
            }

            try:
                response = session.get(url, params=params)
            except requests.RequestException as e:
                logger.error(f"네트워크 요청 실패: {e}")
                break

            if response.status_code != 200:
                logger.error(f"API 요청 실패 (Status: {response.status_code})")
                logger.debug(f"응답 내용(일부): {response.text[:300]}")
                break

            try:
                data = response.json()
            except json.JSONDecodeError:
                logger.error("응답이 JSON 형식이 아닙니다. (HTML 반환됨)")
                logger.debug(f"응답 내용(일부): {response.text[:300]}")
                break

            for user in data.get("users", []):
                uid = user.get("pk")
                if uid not in users_dict:
                    users_dict[uid] = {
                        "id": uid,
                        "username": user.get("username"),
                        "full_name": user.get("full_name")
                    }

            next_max_id = data.get("next_max_id")

            if next_max_id:
                max_id = next_max_id
                logger.info(f"{len(users_dict)}명 수집 중... (잠시 대기)")
                time.sleep(random.uniform(2, 4))
            else:
                logger.info("마지막 페이지 도달.")
                break
            
        return list(users_dict.values())
        
    results["followers"] = fetch_all("followers")
    time.sleep(5)
    results["following"] = fetch_all("following")

    return results
