import requests
import winsound
import datetime


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
    return items[0]


if __name__ == "__main__":
    data = get_response_and_parse_to_json()
    first_item = get_json_first_item(data)


    print(f"최신 게시글 제목: {first_item.get('subject', '제목 없음')}")
    print(f"최신 게시글 날짜: {first_item.get('regdate', '날짜 없음')}")
    print(f"최신 게시글 링크: https://www.kitribob.kr/board/detail/1/{first_item.get('board_no', '번호 없음')}?current_page=1&per_page=15&st=subject&q=")

    base_date = "2025-06-15"
    base_datetime = datetime.datetime.strptime(base_date, "%Y-%m-%d")
    post_date_str = first_item.get('regdate', '')
    if post_date_str:
        post_datetime = datetime.datetime.strptime(post_date_str.split()[0], "%Y-%m-%d")
        
        if post_datetime > base_datetime:
            print(f"새로운 글이 발견되었습니다!")
            winsound.Beep(1000, 10000)
