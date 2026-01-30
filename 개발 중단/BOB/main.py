import datetime
import time
from typing import Optional

import requests
import winsound


DATE_FILE = "date.txt"
DATE_FORMAT = "%Y-%m-%d"
DEFAULT_BASE_DATE = "2025-06-15"


def save_base_date(date_obj: datetime.date) -> None:
    """Persist the latest known post date yet checked."""
    with open(DATE_FILE, "w", encoding="utf-8") as file:
        file.write(date_obj.strftime(DATE_FORMAT))


def load_base_date() -> datetime.date:
    """Return the most recent date stored in date.txt, falling back to the default."""
    try:
        with open(DATE_FILE, "r", encoding="utf-8") as file:
            raw_lines = [line.strip() for line in file if line.strip()]
    except FileNotFoundError:
        default_date = datetime.datetime.strptime(DEFAULT_BASE_DATE, DATE_FORMAT).date()
        save_base_date(default_date)
        return default_date

    parsed_dates = []
    for raw in raw_lines:
        try:
            parsed_dates.append(datetime.datetime.strptime(raw.split()[0], DATE_FORMAT).date())
        except ValueError:
            continue

    if parsed_dates:
        return max(parsed_dates)

    default_date = datetime.datetime.strptime(DEFAULT_BASE_DATE, DATE_FORMAT).date()
    save_base_date(default_date)
    return default_date


def parse_post_date(post_date_str: str) -> Optional[datetime.date]:
    try:
        return datetime.datetime.strptime(post_date_str.split()[0], DATE_FORMAT).date()
    except (ValueError, IndexError):
        return None


def get_response_and_parse_to_json():
    url = "https://www.kitribob.kr/board/post/retrieve/1?current_page=1&per_page=15&st=subject&q="
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': 'https://www.kitribob.kr/board/1',
    }

    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status() 

    # print(f"!! 요청 성공: {response.status_code}")
    # print(response.text) -> 성공 { } 형태의 JSON 데이터 반환
    data = response.json()
    # print(f"!! JSON 데이터: {data}") -> 성공 파싱 완료 

    return data


def get_json_first_item(data):
    items = data.get('items', [])
    return items[0] if items else {}


if __name__ == "__main__":
    base_date = load_base_date()
    print(f"현재 기준 날짜: {base_date.strftime(DATE_FORMAT)}")

    while True:
        try:
            data = get_response_and_parse_to_json()
        except requests.RequestException as error:
            print(f"요청 중 오류 발생: {error}")
            time.sleep(30)
            continue

        first_item = get_json_first_item(data)
        if not first_item:
            print("게시글 데이터를 찾을 수 없습니다. 잠시 후 다시 시도합니다.")
            time.sleep(30)
            continue

        print(f"최신 게시글 제목: {first_item.get('subject', '제목 없음')}")
        print(f"최신 게시글 날짜: {first_item.get('regdate', '날짜 없음')}")
        print(
            "최신 게시글 링크: "
            f"https://www.kitribob.kr/board/detail/1/{first_item.get('board_no', '번호 없음')}?current_page=1&per_page=15&st=subject&q="
        )

        post_date_str = first_item.get('regdate', '')
        post_date = parse_post_date(post_date_str) if post_date_str else None

        if post_date and post_date > base_date:
            print("새로운 글 발견 !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            save_base_date(post_date)
            base_date = post_date
            winsound.Beep(2000, 1000000)
            break

        time.sleep(30)
