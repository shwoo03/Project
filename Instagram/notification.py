"""
Discord Webhook 알림
"""
import json
import logging
import datetime
import requests

logger = logging.getLogger(__name__)


def send_discord_webhook(data, webhook_url):
    """수집 결과를 디스코드 웹훅으로 전송"""
    logger.info("[Discord] 리포트 전송 중...")
    
    followers_set = {u['username'] for u in data['followers']}
    following_set = {u['username'] for u in data['following']}
    
    not_following_back = sorted(list(following_set - followers_set))
    im_not_following = sorted(list(followers_set - following_set))

    def format_users_with_link(user_list):
        if not user_list:
            return "모두 맞팔 중"
        
        formatted_lines = []
        limit = 20
        
        for user in user_list[:limit]:
            link = f"[{user}](https://www.instagram.com/{user}/)"
            formatted_lines.append(f"- {link}")
            
        result = "\n".join(formatted_lines)
        
        if len(user_list) > limit:
            result += f"\n...외 {len(user_list) - limit}명"
            
        return result

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
                    {
                        "name": "", "value": "", "inline": False 
                    },
                    {
                        "name": f"나를 맞팔하지 않는 사람 ({len(not_following_back)}명)",
                        "value": format_users_with_link(not_following_back), 
                        "inline": False
                    },
                    {
                        "name": f"내가 맞팔하지 않는 사람 ({len(im_not_following)}명)",
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

    try:
        response = requests.post(
            webhook_url, 
            data=json.dumps(payload), 
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code == 204:
            logger.info("디스코드 전송 완료")
        else:
            logger.error(f"디스코드 에러 코드: {response.status_code}")
            logger.debug(response.text)
    except requests.Timeout:
        logger.error("디스코드 전송 타임아웃")
    except requests.RequestException as e:
        logger.error(f"전송 중 예외 발생: {e}")
