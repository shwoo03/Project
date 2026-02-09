"""
인스타그램 크롤링 서비스 (httpx 사용)
"""
import asyncio
import logging
import random
from typing import Dict, List, Any, Union
import httpx
from retry import async_api_retry
from config import get_settings

logger = logging.getLogger(__name__)

class InstagramService:
    def __init__(self, cookies_dict: Dict[str, str]):
        self.cookies_dict = cookies_dict
        self._csrftoken = cookies_dict.get("csrftoken", "")
        self.settings = get_settings()

    def _create_client(self) -> httpx.AsyncClient:
        """httpx 비동기 클라이언트 생성"""
        cookies = httpx.Cookies()
        for name, value in self.cookies_dict.items():
            cookies.set(name, value, domain=".instagram.com")
            
        headers = self.settings.request_headers.copy()
        headers["User-Agent"] = self.settings.user_agent
        
        return httpx.AsyncClient(
            cookies=cookies,
            headers=headers,
            timeout=self.settings.api_timeout
        )

    @async_api_retry
    async def _fetch_page(self, client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """단일 페이지 요청 (재시도 적용)"""
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    async def _fetch_all_users(self, client: httpx.AsyncClient, target_id: str, kind: str) -> List[Dict[str, Any]]:
        """팔로워 또는 팔로잉 전체 수집"""
        users_dict = {}
        max_id = ""
        
        logger.info(f"{kind} 데이터 수집 시작... (비동기)")
        
        # 헤더 업데이트 (저장된 csrftoken 사용)
        client.headers.update({
            "X-IG-App-ID": "936619743392459",
            "X-CSRFToken": self._csrftoken,
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
                data = await self._fetch_page(client, url, params)
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
                # 너무 빠르지 않게
                await asyncio.sleep(random.uniform(2, 4))
                logger.info(f"{len(users_dict)}명 수집 중...")
            else:
                logger.info("마지막 페이지 도달.")
                break
        
        return list(users_dict.values())

    async def get_followers_and_following(self) -> Dict[str, List[Dict[str, Any]]]:
        """팔로워/팔로잉 데이터 수집 메인 함수"""
        target_id = self.cookies_dict.get("ds_user_id")
        
        if not target_id:
            logger.error("'ds_user_id' 쿠키가 없습니다.")
            return {"followers": [], "following": []}
        
        async with self._create_client() as client:
            # 병렬로 수집하면 레이트 리밋 위험 → 순차 실행
            followers = await self._fetch_all_users(client, target_id, "followers")
            await asyncio.sleep(5)
            following = await self._fetch_all_users(client, target_id, "following")
        
        return {
            "followers": followers,
            "following": following
        }
