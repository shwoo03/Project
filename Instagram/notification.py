"""
Discord Webhook 알림 (비동기 httpx 사용)
"""
import logging
import datetime
from typing import Any

import httpx

logger = logging.getLogger(f"instagram.{__name__}")


def _format_users_with_link(user_list: list[str], limit: int = 20) -> str:
    """유저 리스트를 인스타그램 링크가 포함된 마크다운으로 포맷"""
    if not user_list:
        return "모두 맞팔 중"

    formatted_lines = [
        f"- [{user}](https://www.instagram.com/{user}/)"
        for user in user_list[:limit]
    ]
    result = "\n".join(formatted_lines)

    if len(user_list) > limit:
        result += f"\n...외 {len(user_list) - limit}명"

    return result


async def _send_payload(webhook_url: str, payload: dict[str, Any]) -> None:
    """Discord webhook으로 payload 전송 (공통 헬퍼)"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                webhook_url,
                json=payload,
                timeout=30
            )
        if response.status_code == 204:
            logger.info("디스코드 전송 완료")
        else:
            logger.error(f"디스코드 에러 코드: {response.status_code}")
            logger.debug(response.text)
    except httpx.TimeoutException:
        logger.error("디스코드 전송 타임아웃")
    except httpx.RequestError as e:
        logger.error(f"전송 중 예외 발생: {e}")


async def send_discord_webhook(data: dict[str, Any], webhook_url: str) -> None:
    """수집 결과를 디스코드 웹훅으로 전송 (비동기)"""
    logger.info("[Discord] 리포트 전송 중...")

    followers_set = {u['username'] for u in data['followers']}
    following_set = {u['username'] for u in data['following']}

    not_following_back = sorted(list(following_set - followers_set))
    im_not_following = sorted(list(followers_set - following_set))

    payload = {
        "username": "Insta",
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png",
        "embeds": [
            {
                "title": "Instagram Daily Report",
                "description": f"현재 계정의 팔로워/팔로잉 현황 분석 결과.\n**{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}** 기준",
                "color": 14758252,
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
                    {"name": "", "value": "", "inline": False},
                    {
                        "name": f"나를 맞팔하지 않는 사람 ({len(not_following_back)}명)",
                        "value": _format_users_with_link(not_following_back),
                        "inline": False
                    },
                    {
                        "name": f"내가 맞팔하지 않는 사람 ({len(im_not_following)}명)",
                        "value": _format_users_with_link(im_not_following),
                        "inline": False
                    }
                ],
                "footer": {
                    "text": "Automated by Python Playwright & httpx"
                }
            }
        ]
    }

    await _send_payload(webhook_url, payload)


async def send_change_notification(
    new_followers: list[dict[str, str]],
    lost_followers: list[dict[str, str]],
    webhook_url: str
) -> None:
    """팔로워 변동 즉시 알림 (비동기)"""
    if not webhook_url or webhook_url.lower() in ["none", ""]:
        return

    if not new_followers and not lost_followers:
        return

    logger.info("[Discord] 변동 알림 전송 중...")

    fields: list[dict[str, Any]] = []

    if new_followers:
        names = [u['username'] for u in new_followers]
        new_list = _format_users_with_link(names, limit=10)
        fields.append({
            "name": f"🎉 새 팔로워 (+{len(new_followers)}명)",
            "value": new_list,
            "inline": False
        })

    if lost_followers:
        names = [u['username'] for u in lost_followers]
        lost_list = _format_users_with_link(names, limit=10)
        fields.append({
            "name": f"😢 언팔로우 (-{len(lost_followers)}명)",
            "value": lost_list,
            "inline": False
        })

    payload = {
        "username": "Insta Alert",
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/a/a5/Instagram_icon.png",
        "embeds": [
            {
                "title": "🔔 팔로워 변동 알림",
                "description": f"**{datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}** 기준",
                "color": 16744576 if lost_followers else 5763719,
                "fields": fields,
                "footer": {
                    "text": "Instagram Tracker"
                }
            }
        ]
    }

    await _send_payload(webhook_url, payload)
