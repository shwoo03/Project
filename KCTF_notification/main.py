import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime as dt
from pathlib import Path

# 설정
KCTF_URL = "http://k-ctf.org/?status=registering"
DISCORD_WEBHOOK_URL = "YOUR_DISCORD_WEBHOOK_URL_HERE"  # 디스코드 웹훅 URL을 여기에 입력하세요
CTF_LIST_FILE = Path(__file__).parent / "ctf_list.txt"


def load_existing_ctfs():
    """저장된 CTF 목록 불러오기"""
    if CTF_LIST_FILE.exists():
        with open(CTF_LIST_FILE, 'r', encoding='utf-8') as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_ctf_list(ctf_set):
    """CTF 목록 저장"""
    with open(CTF_LIST_FILE, 'w', encoding='utf-8') as f:
        for ctf in sorted(ctf_set):
            f.write(f"{ctf}\n")


def fetch_current_ctfs():
    """K-CTF 사이트에서 현재 신청 중인 CTF 목록 가져오기"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(KCTF_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # CTF 대회 제목 추출
        ctf_titles = []
        
        # 대회 제목을 포함하는 h3 태그 찾기
        for title_elem in soup.find_all('h3'):
            title = title_elem.get_text(strip=True)
            if title and title not in ['최근 업데이트', '신청 중인 대회']:
                ctf_titles.append(title)
        
        print(f"[{dt.now().strftime('%Y-%m-%d %H:%M:%S')}] 발견된 CTF 대회: {len(ctf_titles)}개")
        return set(ctf_titles)
        
    except Exception as e:
        print(f"[ERROR] CTF 정보 가져오기 실패: {e}")
        return set()


def send_discord_notification(new_ctf, organizer="", schedule=""):
    """디스코드 웹훅으로 알림 전송"""
    print(f"\n{'='*60}")
    print(f"🚨 새로운 CTF 대회 발견!")
    print(f"{'='*60}")
    print(f"대회명: {new_ctf}")
    if organizer:
        print(f"주최: {organizer}")
    if schedule:
        print(f"일정: {schedule}")
    print(f"{'='*60}\n")
    
    # ====== 디스코드 웹훅 전송 (테스트 후 주석 해제) ======
    # if DISCORD_WEBHOOK_URL == "YOUR_DISCORD_WEBHOOK_URL_HERE":
    #     print(f"[WARNING] 디스코드 웹훅 URL이 설정되지 않았습니다.")
    #     return
    # 
    # try:
    #     embed = {
    #         "title": "🚨 새로운 CTF 대회 등록!",
    #         "description": f"**{new_ctf}**",
    #         "color": 0xFF6B6B,  # 빨간색
    #         "fields": [
    #             {
    #                 "name": "상태",
    #                 "value": "✅ 신청 중",
    #                 "inline": True
    #             },
    #             {
    #                 "name": "확인하기",
    #                 "value": f"[K-CTF 사이트 바로가기]({KCTF_URL})",
    #                 "inline": True
    #             }
    #         ],
    #         "timestamp": dt.utcnow().isoformat(),
    #         "footer": {
    #             "text": "K-CTF 알림봇"
    #         }
    #     }
    #     
    #     if organizer:
    #         embed["fields"].insert(0, {
    #             "name": "주최",
    #             "value": organizer,
    #             "inline": False
    #         })
    #     
    #     if schedule:
    #         embed["fields"].insert(1 if organizer else 0, {
    #             "name": "📅 일정",
    #             "value": schedule,
    #             "inline": False
    #         })
    #     
    #     payload = {
    #         "embeds": [embed]
    #     }
    #     
    #     response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
    #     response.raise_for_status()
    #     print(f"[SUCCESS] 디스코드 알림 전송 완료: {new_ctf}")
    #     
    # except Exception as e:
    #     print(f"[ERROR] 디스코드 알림 전송 실패: {e}")


def check_new_ctfs():
    """새로운 CTF 확인 및 알림"""
    existing_ctfs = load_existing_ctfs()
    current_ctfs = fetch_current_ctfs()
    
    if not current_ctfs:
        print("[ERROR] 현재 CTF 목록을 가져올 수 없습니다.")
        return
    
    # 새로운 CTF 찾기
    new_ctfs = current_ctfs - existing_ctfs
    
    if new_ctfs:
        print(f"\n✨ 새로운 CTF 발견: {len(new_ctfs)}개")
        print("-" * 60)
        for ctf in sorted(new_ctfs):
            send_discord_notification(ctf)
        
        # 업데이트된 목록 저장
        save_ctf_list(current_ctfs)
        print(f"[SUCCESS] CTF 목록이 업데이트되었습니다. (총 {len(current_ctfs)}개)")
    else:
        print(f"✅ 새로운 CTF가 없습니다. (현재 {len(current_ctfs)}개)")
    
    # 사라진 CTF 확인
    removed_ctfs = existing_ctfs - current_ctfs
    if removed_ctfs:
        print(f"\n📌 신청 마감된 CTF: {len(removed_ctfs)}개")
        for ctf in sorted(removed_ctfs):
            print(f"  - {ctf}")
        # 목록 업데이트
        save_ctf_list(current_ctfs)


def main():
    """메인 실행 함수 - 한 번만 실행하고 종료"""
    print("=" * 60)
    print("K-CTF 신규 대회 알림봇")
    print("=" * 60)
    print(f"모니터링 URL: {KCTF_URL}")
    print(f"CTF 목록 파일: {CTF_LIST_FILE}")
    print(f"실행 시간: {dt.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 기존 목록 로드
    print("\n[1단계] 기존 CTF 목록 로드 중...")
    existing_ctfs = load_existing_ctfs()
    
    if not existing_ctfs:
        print("[INFO] 저장된 CTF 목록이 없습니다. 현재 목록을 초기화합니다.")
        current_ctfs = fetch_current_ctfs()
        if current_ctfs:
            save_ctf_list(current_ctfs)
            print(f"[SUCCESS] {len(current_ctfs)}개의 CTF를 초기 목록으로 저장했습니다.")
            print("\n초기화 완료! 다음 실행부터 새로운 대회를 감지합니다.")
        else:
            print("[ERROR] CTF 목록을 가져올 수 없습니다.")
    else:
        print(f"[INFO] {len(existing_ctfs)}개의 CTF가 저장되어 있습니다.")
        
        # 새로운 CTF 체크
        print("\n[2단계] 새로운 CTF 확인 중...")
        check_new_ctfs()
    
    print("\n" + "=" * 60)
    print("프로그램 실행 완료!")
    print("=" * 60)


if __name__ == "__main__":
    main()
