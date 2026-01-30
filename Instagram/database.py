"""
MongoDB 데이터베이스 연동
"""
import logging
import datetime
import pymongo
import atexit

logger = logging.getLogger(__name__)

# MongoDB 싱글톤 클라이언트
_mongo_client = None


def get_mongo_client(mongo_uri):
    """MongoDB 클라이언트 싱글톤 패턴으로 반환"""
    global _mongo_client
    if _mongo_client is None and mongo_uri:
        try:
            _mongo_client = pymongo.MongoClient(mongo_uri)
            # 연결 테스트
            _mongo_client.admin.command('ping')
            logger.info("MongoDB 연결 성공")
        except pymongo.errors.ConnectionFailure as e:
            logger.error(f"MongoDB 연결 실패: {e}")
            _mongo_client = None
    return _mongo_client


def close_mongo_client():
    """프로그램 종료 시 MongoDB 연결 정리"""
    global _mongo_client
    if _mongo_client:
        _mongo_client.close()
        _mongo_client = None
        logger.info("MongoDB 연결 종료")


# 프로그램 종료 시 자동으로 연결 정리
atexit.register(close_mongo_client)


def check_last_run(username, mongo_uri):
    """
    오늘 이미 실행했는지 확인
    Return: True(이미 실행함), False(아직 안 함)
    """
    if not mongo_uri:
        return False

    try:
        client = get_mongo_client(mongo_uri)
        if not client:
            return False
        db = client.get_database('webhook')
        col_latest = db['Instagram_Latest']

        doc = col_latest.find_one({"_id": username})
        if not doc:
            return False
        
        last_updated = doc.get("last_updated")
        if not last_updated:
            return False
        
        if last_updated.date() == datetime.datetime.now().date():
            return True
        
        return False

    except pymongo.errors.PyMongoError as e:
        logger.warning(f"DB 확인 중 오류 발생: {e}")
        return False


def save_and_get_results_to_db(results, username, mongo_uri):
    """결과를 DB에 저장"""
    if not mongo_uri:
        logger.error(".env 파일에 MONGO_URI가 설정되지 않았습니다.")
        return

    try:
        client = get_mongo_client(mongo_uri)
        if not client:
            logger.error("MongoDB 클라이언트 생성 실패")
            return
        db = client.get_database('webhook')
        
        col_latest = db['Instagram_Latest']
        
        prev_doc = col_latest.find_one({"_id": username})
        
        current_data = results 
        
        if prev_doc:
            prev_ids = {u['id'] for u in prev_doc['followers']}
            curr_ids = {u['id'] for u in current_data['followers']}
            
            new_ids = curr_ids - prev_ids
            lost_ids = prev_ids - curr_ids
            
            new_users = [u for u in current_data['followers'] if u['id'] in new_ids]
            lost_users = [u for u in prev_doc['followers'] if u['id'] in lost_ids]
            
            if new_users or lost_users:
                logger.info(f"[Diff] 변동 사항 발견 (New: {len(new_users)}, Lost: {len(lost_users)})")
            else:
                logger.info("[Diff] 변동 사항 없음.")
        else:
            logger.info("첫 실행입니다. 기준 데이터를 생성합니다.")

        col_latest.replace_one(
            {"_id": username}, 
            {
                "followers": current_data["followers"],
                "following": current_data["following"],
                "last_updated": datetime.datetime.now()
            },
            upsert=True
        )
        logger.info("[Latest] 최신 상태 업데이트 완료")
        
    except pymongo.errors.PyMongoError as e:
        logger.error(f"DB 저장 중 오류 발생: {e}")
