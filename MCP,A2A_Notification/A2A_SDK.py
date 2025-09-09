import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import os

def get_latest_tag_time(github_tags_url):
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
    times = {}
    if not os.path.exists(filepath):
        return times
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if "=" in line:
                key, date_str = line.split("=")
                key = key.strip()
                date_str = date_str.strip()
                try:
                    # 여러 포맷 시도
                    try:
                        times[key] = datetime.strptime(date_str, "%Y-%m-%d:%H:%M")
                    except Exception:
                        times[key] = datetime.strptime(date_str, "%Y-%m-%d %H:%M")
                except Exception:
                    print(f"[경고] {key}의 시간 파싱 실패: {date_str}")
                    times[key] = None
    return times

def write_check_times(filepath, times):
    with open(filepath, "w", encoding="utf-8") as f:
        for key, dt in times.items():
            if dt:
                f.write(f"{key} = {dt.strftime('%Y-%m-%d:%H:%M')}\n")

def send_discord_webhook(webhook_url, content):
    data = {"content": content}
    response = requests.post(webhook_url, json=data)
    response.raise_for_status()

def main():
    time_file = os.path.join(os.path.dirname(__file__), "time.txt")
    webhook_url = "https://discordapp.com/api/webhooks/1414626304598343810/-3jW1nDpt84Chx3PRdiOqhSCg8FvQ9IUSeITgxvogzYDdFXWw4Pci1c6yr8o44txK-Tf"
    repos = {
        "a2a_python_sdk": "https://github.com/a2aproject/a2a-python/tags",
        "a2a_js_sdk": "https://github.com/a2aproject/a2a-js/tags",
        "a2a_java_sdk": "https://github.com/a2aproject/a2a-java/tags",
        "a2a_dotnet_sdk": "https://github.com/a2aproject/a2a-dotnet/tags"
    }

    check_times = read_check_times(time_file)

    updated = False
    for key, url in repos.items():
        latest_tag_time = get_latest_tag_time(url)
        last_check_time = check_times.get(key)
        if latest_tag_time:
            # 1분의 여유를 두어 비교 (최신 태그 시간이 마지막 체크 시간 + 1분보다 클 때만 알림)
            if last_check_time is None or latest_tag_time > (last_check_time + timedelta(minutes=1)):
                message = f"[{key}] 새로운 태그가 등록되었습니다! {latest_tag_time.strftime('%Y-%m-%d %H:%M')}\n태그 페이지: {url}"
                send_discord_webhook(webhook_url, message)
                check_times[key] = latest_tag_time
                updated = True
    if updated:
        write_check_times(time_file, check_times)