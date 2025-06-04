import requests
import json
import sys

if __name__ == "__main__":
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

    # data 에서 items 키를 가진 리스트에서 {} 를 기준으로 분리
    items = data.get('items', [])
    # print(items[0])

    first_item = items[0]
    print(f"최신 게시글 제목: {first_item.get('subject', '제목 없음')}")
    print(f"최신 게시글 날짜: {first_item.get('regdate', '날짜 없음')}")

