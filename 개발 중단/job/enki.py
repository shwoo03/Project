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
    current_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(current_dir, ".env")
    
    if os.path.exists(env_path):
        load_dotenv(env_path)
    else:
        load_dotenv()

    mongo_uri = os.getenv("MONGO_URI")
    webhook_url = os.getenv("DISCORD_WEBHOOK")

    if not mongo_uri or not webhook_url:
        logger.error("MONGO_URI or DISCORD_WEBHOOK not found.")
        return None

    return {
        "MONGO_URI": mongo_uri,
        "DISCORD_WEBHOOK": webhook_url
    }

from playwright.sync_api import sync_playwright

def parse_jobs():
    """
    채용 공고 파싱 (Playwright 사용)
    """
    base_url = "https://enki.career.greetinghr.com"
    list_url = f"{base_url}/ko/guide?employments=INTERN_WORKER"
    
    jobs = []

    try:
        with sync_playwright() as p:
            # 브라우저 실행
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            logger.info(f"Accessing list page: {list_url}")
            page.goto(list_url)
            
            # 공고 목록이 로드될 때까지 대기 (최대 10초)
            try:
                page.wait_for_selector("a[href^='/ko/o/']", timeout=10000)
            except:
                logger.warning("Timeout waiting for job list. Page might be empty.")
                return []

            # 목록 페이지 파싱
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            job_links = soup.select("a[href^='/ko/o/']")
            
            logger.info(f"Found {len(job_links)} job postings.")

            for link_tag in job_links:
                try:
                    relative_link = link_tag['href']
                    if relative_link.endswith('/apply'):
                        continue
                        
                    detail_url = f"{base_url}{relative_link}"
                    job_id = relative_link.split("/")[-1]

                    logger.info(f"Scraping job: {detail_url}")
                    
                    # 상세 페이지 이동
                    page.goto(detail_url)
                    
                    # 핵심 내용(직군 등)이 로드될 때까지 대기
                    try:
                        page.wait_for_selector("span", timeout=5000)
                        time.sleep(1) # 렌더링 안정화 대기
                    except:
                        pass

                    detail_html = page.content()
                    detail_soup = BeautifulSoup(detail_html, 'html.parser')
                    
                    # 제목 추출
                    title = "Unknown Job"
                    og_title = detail_soup.find("meta", property="og:title")
                    if og_title:
                        title = og_title["content"]
                    else:
                        h1 = detail_soup.find("h1")
                        if h1:
                            title = h1.text.strip()

                    # 필드 추출
                    fields = {
                        "직군": "",
                        "직무": "",
                        "경력사항": "",
                        "고용형태": "",
                        "마감기한": ""
                    }
                    
                    spans = detail_soup.find_all("span")
                    for span in spans:
                        text = span.text.strip()
                        if text in fields:
                            try:
                                # 1. Label Span -> Parent Div -> Next Sibling Span
                                label_div = span.parent
                                value_span = label_div.find_next_sibling("span")
                                
                                if value_span:
                                    fields[text] = value_span.text.strip()
                            except:
                                pass

                    job_data = {
                        "_id": job_id,
                        "title": title,
                        "url": detail_url,
                        "group": fields["직군"],
                        "duty": fields["직무"],
                        "experience": fields["경력사항"],
                        "type": fields["고용형태"],
                        "deadline": fields["마감기한"],
                        "scraped_at": datetime.datetime.now()
                    }
                    
                    jobs.append(job_data)
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Error parsing job: {e}")
                    continue
            
            browser.close()

    except Exception as e:
        logger.error(f"Playwright error: {e}")
        return []
            
    return jobs

def send_discord_webhook(job, webhook_url):
    """
    디스코드 알림 전송
    """
    embed = {
        "title": f"📢 New Job Opening: {job['title']}",
        "url": job['url'],
        "color": 0x00ff00, # Green
        "fields": [
            {"name": "직군", "value": job['group'], "inline": True},
            {"name": "직무", "value": job['duty'], "inline": True},
            {"name": "고용형태", "value": job['type'], "inline": True},
            {"name": "마감기한", "value": job['deadline'], "inline": True},
            {"name": "경력사항", "value": job['experience'], "inline": False},
        ],
        "footer": {"text": f"Enki Job Notification • {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"}
    }

    payload = {
        "username": "Enki Bot",
        "embeds": [embed]
    }

    try:
        requests.post(webhook_url, json=payload)
        logger.info(f"Sent webhook for {job['title']}")
    except Exception as e:
        logger.error(f"Webhook error: {e}")

def sync_and_notify(current_jobs, mongo_uri, webhook_url):
    """
    DB 동기화 및 알림
    """
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client.get_database('webhook')
        collection = db['Job_Latest']
        status_collection = db['Job_Status']

        stored_ids = [doc['_id'] for doc in collection.find({}, {"_id": 1})]
        current_ids = [j['_id'] for j in current_jobs]

        new_jobs = [j for j in current_jobs if j['_id'] not in stored_ids]
        removed_ids = set(stored_ids) - set(current_ids)

        logger.info(f"Sync: {len(new_jobs)} new, {len(removed_ids)} removed")

        for job in new_jobs:
            collection.insert_one(job)
            send_discord_webhook(job, webhook_url)
            time.sleep(1)

        if removed_ids:
            collection.delete_many({"_id": {"$in": list(removed_ids)}})

        # 실행 시간 업데이트
        status_collection.update_one(
            {"_id": "scraper_status"},
            {"$set": {"last_run": datetime.datetime.now()}},
            upsert=True
        )

    except Exception as e:
        logger.error(f"DB Error: {e}")
    finally:
        client.close()

def check_last_run(mongo_uri):
    """
    하루 1회 실행 체크
    """
    try:
        client = pymongo.MongoClient(mongo_uri)
        db = client.get_database('webhook')
        status_collection = db['Job_Status']
        
        doc = status_collection.find_one({"_id": "scraper_status"})
        if not doc or not doc.get("last_run"):
            return False
            
        if doc["last_run"].date() == datetime.datetime.now().date():
            return True
            
        return False
    except:
        return False

if __name__ == "__main__":
    logger.info("Starting Job Scraper")
    env = get_env_var()
    if env:
        if check_last_run(env["MONGO_URI"]):
            logger.info("Already ran today. Exiting.")
            exit(0)
            
        jobs = parse_jobs()
        if jobs:
            sync_and_notify(jobs, env["MONGO_URI"], env["DISCORD_WEBHOOK"])
        else:
            logger.info("No jobs found.")
    logger.info("Finished.")
