"""
인스타그램 API 호출 (비동기 - httpx)
"""
import asyncio
import json
import random
import logging
import httpx
from retry import async_api_retry

logger = logging.getLogger(__name__)

# 저장된 csrftoken (쿠키 중복 방지용)
_csrftoken = ""


def create_async_client(cookies_dict):
    """추출한 쿠키로 httpx 비동기 클라이언트 생성"""
    global _csrftoken
    
    # csrftoken 미리 저장 (중복 쿠키 문제 방지)
    _csrftoken = cookies_dict.get("csrftoken", "")
    
    # 쿠키를 도메인별로 설정하여 중복 방지
    cookies = httpx.Cookies()
    for name, value in cookies_dict.items():
        cookies.set(name, value, domain=".instagram.com")
    
    client = httpx.AsyncClient(
        cookies=cookies,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "ko-KR",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        },
        timeout=30.0
    )
    return client


@async_api_retry
async def fetch_page(client, url, params):
    """단일 페이지 요청 (재시도 적용)"""
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


async def fetch_all_users(client, target_id, kind):
    """팔로워 또는 팔로잉 전체 수집"""
    users_dict = {}
    max_id = ""
    
    logger.info(f"{kind} 데이터 수집 시작... (비동기)")
    
    # 헤더 업데이트 (저장된 csrftoken 사용)
    client.headers.update({
        "X-IG-App-ID": "936619743392459",
        "X-CSRFToken": _csrftoken,
        "X-Requested-With": "XMLHttpRequest",
        "Referer": f"https://www.instagram.com/{target_id}/{kind}/"
    })

    
    while True:
        url = f"https://www.instagram.com/api/v1/friendships/{target_id}/{kind}/"
        params = {
            "count": 100,
            "search_surface": "follow_list_page",
            "max_id": max_id
        }
        
        try:
            data = await fetch_page(client, url, params)
        except httpx.HTTPStatusError as e:
            logger.error(f"API 요청 실패 (Status: {e.response.status_code})")
            break
        except Exception as e:
            logger.error(f"요청 중 오류: {e}")
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
            await asyncio.sleep(random.uniform(2, 4))
        else:
            logger.info("마지막 페이지 도달.")
            break
    
    return list(users_dict.values())


async def get_followers_and_following_async(cookies_dict):
    """비동기로 팔로워/팔로잉 수집"""
    target_id = cookies_dict.get("ds_user_id")
    
    if not target_id:
        logger.error("'ds_user_id' 쿠키가 없습니다.")
        return {"followers": [], "following": []}
    
    async with create_async_client(cookies_dict) as client:
        # 병렬로 수집하면 레이트 리밋 위험 → 순차 실행
        followers = await fetch_all_users(client, target_id, "followers")
        await asyncio.sleep(5)
        following = await fetch_all_users(client, target_id, "following")
    
    return {
        "followers": followers,
        "following": following
    }
