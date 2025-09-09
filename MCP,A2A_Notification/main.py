<<<<<<< HEAD
#!/usr/bin/env python3
"""
GitHub 저장소 태그 모니터링 및 Discord 알림 시스템
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

# .env 파일에서 환경변수 로드 (python-dotenv가 설치된 경우)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # python-dotenv가 없으면 시스템 환경변수만 사용
    pass

from config import DISCORD_WEBHOOK_URL, REPOS

def get_latest_tag_time(github_tags_url):
    """GitHub 저장소의 최신 태그 시간을 가져옵니다."""
    response = requests.get(github_tags_url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    time_tags = soup.find_all("relative-time")
    if not time_tags:
        return None
    
    latest_time_str = time_tags[0]["datetime"]
    try:
        latest_time = datetime.strptime(latest_time_str, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        latest_time = datetime.strptime(latest_time_str, "%Y-%m-%d %H:%M:%S UTC")
    return latest_time

def read_check_times(filepath):
    """시간 파일에서 마지막 체크 시간들을 읽습니다."""
    times = {}
    if not os.path.exists(filepath):
        return times
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, date_str = line.split("=", 1)
                key = key.strip()
                date_str = date_str.strip()
                try:
                    # 여러 포맷 시도
                    try:
                        times[key] = datetime.strptime(date_str, "%Y-%m-%d:%H:%M")
                    except ValueError:
                        times[key] = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                except ValueError:
                    print(f"[경고] {key}의 시간 파싱 실패: {date_str}")
                    times[key] = None
    return times

def write_check_times(filepath, times):
    """시간 파일에 마지막 체크 시간들을 저장합니다."""
    with open(filepath, "w", encoding="utf-8") as f:
        for key, dt in times.items():
            if dt:
                f.write(f"{key} = {dt.strftime('%Y-%m-%d:%H:%M')}\n")

def send_discord_webhook(webhook_url, content):
    """Discord 웹훅으로 메시지를 전송합니다."""
    data = {"content": content}
    response = requests.post(webhook_url, json=data)
    response.raise_for_status()

def check_repository_group(group_name, repos, check_times, webhook_url):
    """저장소 그룹의 태그를 체크하고 알림을 발송합니다."""
    updated = False
    
    for key, url in repos.items():
        try:
            latest_tag_time = get_latest_tag_time(url)
            last_check_time = check_times.get(key)
            
            if latest_tag_time:
                # 1분의 여유를 두어 비교 (최신 태그 시간이 마지막 체크 시간 + 1분보다 클 때만 알림)
                if last_check_time is None or latest_tag_time > (last_check_time + timedelta(minutes=1)):
                    message = f"[{key}] 새로운 태그가 등록되었습니다! {latest_tag_time.strftime('%Y-%m-%d %H:%M')}\n태그 페이지: {url}"
                    print(f"알림 발송: {key}")
                    send_discord_webhook(webhook_url, message)
                    check_times[key] = latest_tag_time
                    updated = True
                else:
                    print(f"변경 없음: {key}")
            else:
                print(f"태그 없음: {key}")
                
        except Exception as e:
            print(f"오류 발생 ({key}): {e}")
    
    return updated

def main():
    """메인 실행 함수"""
    time_file = os.path.join(os.path.dirname(__file__), "time.txt")
    webhook_url = DISCORD_WEBHOOK_URL
    
    # 현재 저장된 체크 시간들을 읽음
    check_times = read_check_times(time_file)
    print(f"저장된 체크 시간 개수: {len(check_times)}")
    
    overall_updated = False
    
    # 모든 저장소 그룹을 순회하며 체크
    for group_name, repos in REPOS.items():
        print(f"\n=== {group_name} 그룹 체크 중 ===")
        updated = check_repository_group(group_name, repos, check_times, webhook_url)
        if updated:
            overall_updated = True
    
    # 변경사항이 있으면 파일에 저장
    if overall_updated:
        write_check_times(time_file, check_times)
        print(f"\n체크 시간 파일 업데이트 완료: {time_file}")
    else:
        print(f"\n변경사항 없음")

if __name__ == "__main__":
    main()
=======
import MCP_SDK
import A2A_SDK
import lang
import A2A_ADK
import fast_mcp

if __name__ == "__main__":
    MCP_SDK.main()
    A2A_SDK.main()
    lang.main()
    A2A_ADK.main()
    fast_mcp.main()
>>>>>>> 35b13b18449b4a5bab6245f002866e150211264f
