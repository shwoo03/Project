import os
import requests
from bs4 import BeautifulSoup
import pymongo
import datetime
import time
import logging
from dotenv import load_dotenv

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_env_var():
    """
    .env 파일에서 환경변수 로드
    """
    # 현재 스크립트 파일의 디렉토리 경로
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logger.info(f".env loaded from {env_path}")
    else:
        logger.warning(f".env not found at {env_path}, trying system env vars")
        load_dotenv()

    mongo_uri = os.getenv("MONGO_URI")
    webhook_url = os.getenv("DISCORD_WEBHOOK")

    if not mongo_uri or not webhook_url:
        logger.error("MONGO_URI or DISCORD_WEBHOOK not found in environment variables.")
        return None

    return {
        "MONGO_URI": mongo_uri,
        "DISCORD_WEBHOOK": webhook_url
    }

def fetch_page(url, retries=3):
    """
    URL 페이지를 가져오는 함수 (재시도 로직 포함)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for i in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning(f"Attempt {i+1}/{retries} failed for {url}: {e}")
            time.sleep(2)
    
    logger.error(f"Failed to fetch {url} after {retries} attempts.")
    return None

def parse_contests():
    """
    K-CTF 사이트에서 대회 목록 및 상세 정보 파싱
    """
    base_url = "http://k-ctf.org"
    list_url = f"{base_url}/?status=registering"
    
    html = fetch_page(list_url)
    if not html:
        return []

    soup = BeautifulSoup(html, 'html.parser')
    contest_cards = soup.select("#contestWrapper-registering .contest-card-poster")
    
    contests = []
    
    logger.info(f"Found {len(contest_cards)} contests in list page.")

    for card in contest_cards:
        try:
            # 상세 페이지 링크 추출
            onclick_attr = card.get("onclick")
            if not onclick_attr:
                continue
                
            # location.href='/contests/...' 형태에서 URL 추출
            relative_link = onclick_attr.split("'")[1]
            detail_url = f"{base_url}{relative_link}"
            contest_id = relative_link.split("/")[-1] # URL의 마지막 부분을 ID로 사용

            # 상세 페이지 접속
            logger.info(f"Scraping detail page: {detail_url}")
            detail_html = fetch_page(detail_url)
            if not detail_html:
                continue
                
            detail_soup = BeautifulSoup(detail_html, 'html.parser')
            
            # 정보 추출
            title_elem = detail_soup.select_one("h1.text-3xl.font-bold")
            title = title_elem.text.strip() if title_elem else "Unknown Title"
            
            # 이미지 URL
            img_elem = detail_soup.select_one("img.object-cover")
            img_url = f"{base_url}{img_elem['src']}" if img_elem else ""
            
            # 기본 정보 (주최, 운영, 링크 등)
            host = "Unknown"
            link = ""
            
            info_divs = detail_soup.select(".space-y-3.text-sm > div")
            for div in info_divs:
                text = div.text.strip()
                if "주최:" in text:
                    host = text.replace("주최:", "").strip()
                elif "링크:" in text:
                    link_tag = div.select_one("a")
                    if link_tag:
                        link = link_tag['href']

            # 일정 정보
            schedule_section = detail_soup.find("h2", string="일정")
            schedule_text = ""
            apply_period = ""
            
            if schedule_section:
                schedule_container = schedule_section.parent
                
                # 대회 기간
                contest_period_elem = schedule_container.select_one(".border-l-4.border-blue-500 p.text-sm.text-gray-600")
                if contest_period_elem:
                    schedule_text = contest_period_elem.text.strip()
                
                # 신청 기간
                apply_period_elem = schedule_container.select_one(".border-l-4.border-green-500 p.text-sm.text-gray-600")
                if apply_period_elem:
                    apply_period = apply_period_elem.text.strip()

            # 대회 정보 (유형, 자격, 상금)
            contest_type = ""
            qualification = ""
            prize = ""
            
            info_sidebar = detail_soup.find("h3", string="대회 정보")
            if info_sidebar:
                sidebar_container = info_sidebar.parent
                sidebar_items = sidebar_container.select(".space-y-3.text-sm > div")
                
                for item in sidebar_items:
                    header = item.select_one("span.font-medium")
                    if not header:
                        continue
                    
                    header_text = header.text.strip()
                    content_p = item.select_one("p")
                    content = content_p.text.strip() if content_p else ""
                    
                    if "대회 유형:" in header_text:
                        contest_type = content
                    elif "참가 자격:" in header_text:
                        qualification = content
                    elif "상금:" in header_text:
                        prize = content

            contest_data = {
                "_id": contest_id, # 고유 ID
                "title": title,
                "url": detail_url,
                "image_url": img_url,
                "host": host,
                "link": link,
                "schedule": schedule_text,
                "apply_period": apply_period,
                "type": contest_type,
                "qualification": qualification,
                "prize": prize,
                "scraped_at": datetime.datetime.now()
            }
            
            contests.append(contest_data)
            time.sleep(1) # 서버 부하 방지

        except Exception as e:
            logger.error(f"Error parsing contest card: {e}")
            continue
            
    return contests

def send_discord_webhook(contest, webhook_url):
    """
    디스코드 웹훅 전송
    """
    embed = {
        "title": f"🚩 New CTF: {contest['title']}",
        "url": contest['url'],
        "color": 0xFF8C00, # Dark Orange
        "fields": [
            {"name": "주최", "value": contest['host'], "inline": True},
            {"name": "유형", "value": contest['type'], "inline": True},
            {"name": "참가 자격", "value": contest['qualification'][:1024], "inline": False}, # 1024자 제한
            {"name": "신청 기간", "value": contest['apply_period'], "inline": False},
            {"name": "대회 일정", "value": contest['schedule'], "inline": False},
            {"name": "상금", "value": contest['prize'][:1024], "inline": False},
            {"name": "공식 링크", "value": contest['link'] if contest['link'] else "N/A", "inline": False}
        ],
        "thumbnail": {"url": contest['image_url']},
        "footer": {"text": f"K-CTF Notification • {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"}
    }

    payload = {
        "username": "K-CTF Bot",
        "avatar_url": "https://k-ctf.org/static/img/logo.png", # 로고가 있다면
        "embeds": [embed]
    }

    try:
        response = requests.post(webhook_url, json=payload)
        if response.status_code == 204:
            logger.info(f"Webhook sent for {contest['title']}")
        else:
            logger.error(f"Failed to send webhook: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error sending webhook: {e}")

def sync_and_notify(current_contests, mongo_uri, webhook_url):
    """
    DB 동기화 및 알림 전송
    """
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client.get_database('webhook')
        collection = db['KCTF_Latest']
        status_collection = db['KCTF_Status'] # 스크립트 실행 상태 저장
        
        # 현재 DB에 있는 ID 목록
        stored_ids = [doc['_id'] for doc in collection.find({}, {"_id": 1})]
        current_ids = [c['_id'] for c in current_contests]
        
        # 신규 대회 (웹에는 있는데 DB엔 없음)
        new_contests = [c for c in current_contests if c['_id'] not in stored_ids]
        
        # 삭제된 대회 (DB엔 있는데 웹엔 없음 - 접수 마감 등)
        removed_ids = set(stored_ids) - set(current_ids)
        
        logger.info(f"Sync Status - New: {len(new_contests)}, Removed: {len(removed_ids)}")
        
        # 1. 신규 대회 처리
        for contest in new_contests:
            # DB 저장
            collection.insert_one(contest)
            logger.info(f"Saved new contest to DB: {contest['title']}")
            
            # 알림 전송
            send_discord_webhook(contest, webhook_url)
            time.sleep(1) # Rate limit 방지
            
        # 2. 삭제된 대회 처리
        if removed_ids:
            result = collection.delete_many({"_id": {"$in": list(removed_ids)}})
            logger.info(f"Removed {result.deleted_count} contests from DB.")
            
        # 3. 실행 시간 업데이트
        status_collection.update_one(
            {"_id": "scraper_status"},
            {"$set": {"last_run": datetime.datetime.now()}},
            upsert=True
        )
        logger.info("Updated last run time.")
            
    except Exception as e:
        logger.error(f"Database error: {e}")
    finally:
        client.close()

def check_last_run(mongo_uri):
    """
    오늘 이미 실행했는지 확인
    """
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client.get_database('webhook')
        status_collection = db['KCTF_Status']
        
        doc = status_collection.find_one({"_id": "scraper_status"})
        if not doc:
            return False
            
        last_run = doc.get("last_run")
        if not last_run:
            return False
            
        # 오늘 날짜와 비교
        if last_run.date() == datetime.datetime.now().date():
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking last run: {e}")
        return False

if __name__ == "__main__":
    logger.info("Starting K-CTF Notification Script")
    
    env_vars = get_env_var()
    if env_vars:
        # 오늘 이미 실행했는지 확인
        if check_last_run(env_vars["MONGO_URI"]):
            logger.info(f"Already ran today ({datetime.datetime.now().strftime('%Y-%m-%d')}). Exiting.")
            exit(0)

        contests = parse_contests()
        if contests:
            sync_and_notify(contests, env_vars["MONGO_URI"], env_vars["DISCORD_WEBHOOK"])
        else:
            logger.info("No contests found or parsing failed.")
            
    logger.info("Script finished.")
