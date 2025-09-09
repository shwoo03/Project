#!/usr/bin/env python3

from __future__ import annotations

import os
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

try:  
    from dotenv import load_dotenv  
    load_dotenv()
except Exception:
    pass

from config import DISCORD_WEBHOOK_URL, REPOS

def get_latest_tag_time(github_tags_url: str) -> datetime | None:
    """해당 태그 페이지에서 가장 최근 태그 시간을 UTC datetime으로 반환."""
    response = requests.get(github_tags_url, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    time_tags = soup.find_all("relative-time")
    if not time_tags:
        return None
    latest_time_str = time_tags[0]["datetime"]
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S UTC"):
        try:
            return datetime.strptime(latest_time_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"지원되지 않는 datetime 형식: {latest_time_str}")

def read_check_times(filepath: str) -> dict[str, datetime | None]:
    times: dict[str, datetime | None] = {}
    if not os.path.exists(filepath):
        return times
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if "=" not in line:
                continue
            key, date_str = line.split("=", 1)
            key = key.strip()
            date_str = date_str.strip()
            parsed: datetime | None = None
            for fmt in ("%Y-%m-%d:%H:%M", "%Y-%m-%d %H:%M"):
                try:
                    parsed = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            times[key] = parsed
    return times

def write_check_times(filepath: str, times: dict[str, datetime | None]) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        for key, dt in times.items():
            if dt:
                f.write(f"{key} = {dt.strftime('%Y-%m-%d:%H:%M')}\n")

def send_discord_webhook(webhook_url: str, content: str) -> None:
    data = {"content": content}
    response = requests.post(webhook_url, json=data, timeout=10)
    response.raise_for_status()

def check_repository_group(group_name: str, repos: dict[str, str], check_times: dict[str, datetime | None], webhook_url: str) -> bool:
    updated = False
    for key, url in repos.items():
        try:
            latest_tag_time = get_latest_tag_time(url)
            last_check_time = check_times.get(key)
            if latest_tag_time and (last_check_time is None or latest_tag_time > (last_check_time + timedelta(minutes=1))):
                message = (
                    f"[{group_name}/{key}] 새 태그 감지: {latest_tag_time.strftime('%Y-%m-%d %H:%M UTC')}\n"
                    f"태그 페이지: {url}"
                )
                print(f"알림 발송: {group_name}/{key}")
                send_discord_webhook(webhook_url, message)
                check_times[key] = latest_tag_time
                updated = True
            else:
                print(f"변경 없음: {group_name}/{key}")
        except Exception as e:  # 네트워크/파싱 등 개별 오류 계속 진행
            print(f"오류 발생 ({group_name}/{key}): {e}")
    return updated

def main() -> None:
    time_file = os.path.join(os.path.dirname(__file__), "time.txt")
    webhook_url = DISCORD_WEBHOOK_URL
    if not webhook_url:
        raise RuntimeError("DISCORD_WEBHOOK_URL이 설정되지 않았습니다 (.env 확인)")
    check_times = read_check_times(time_file)
    print(f"저장된 체크 시간 개수: {len(check_times)}")
    overall_updated = False
    for group_name, repos in REPOS.items():
        print(f"\n=== {group_name} 그룹 체크 중 ===")
        if check_repository_group(group_name, repos, check_times, webhook_url):
            overall_updated = True
    if overall_updated:
        write_check_times(time_file, check_times)
        print(f"\n체크 시간 파일 업데이트 완료: {time_file}")
    else:
        print("\n변경사항 없음")

if __name__ == "__main__":  # pragma: no cover
    main()
