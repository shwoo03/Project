import datetime
import logging
from typing import Optional, Dict, List, Any
from .base import BaseRepository

logger = logging.getLogger(__name__)

class UserRepository(BaseRepository):
    def __init__(self, mongo_uri: str):
        super().__init__(mongo_uri)
        self.col_latest = self.db['Instagram_Latest']
        self.col_history = self.db['Instagram_History']

    def check_last_run(self, username: str) -> bool:
        """오늘 이미 실행했는지 확인"""
        try:
            doc = self.col_latest.find_one({"_id": username})
            if not doc:
                return False
            
            last_updated = doc.get("last_updated")
            if not last_updated:
                return False
            
            if last_updated.date() == datetime.datetime.now().date():
                return True
            return False
        except Exception as e:
            logger.warning(f"DB 확인 중 오류 발생: {e}")
            return False

    def save_results(self, username: str, results: Dict[str, Any]) -> Dict[str, List[Any]]:
        """최신 결과 저장 및 변동 사항 반환"""
        try:
            prev_doc = self.col_latest.find_one({"_id": username})
            
            current_data = results 
            new_users = []
            lost_users = []
            
            if prev_doc:
                prev_ids = {u['id'] for u in prev_doc.get('followers', [])}
                curr_ids = {u['id'] for u in current_data.get('followers', [])}
                
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

            self.col_latest.replace_one(
                {"_id": username}, 
                {
                    "followers": current_data.get("followers", []),
                    "following": current_data.get("following", []),
                    "last_updated": datetime.datetime.now()
                },
                upsert=True
            )
            logger.info("[Latest] 최신 상태 업데이트 완료")
            
            return {"new_followers": new_users, "lost_followers": lost_users}
            
        except Exception as e:
            logger.error(f"DB 저장 중 오류 발생: {e}")
            return {"new_followers": [], "lost_followers": []}

    def get_latest_data(self, username: str) -> Optional[Dict[str, Any]]:
        """최신 데이터 조회"""
        try:
            return self.col_latest.find_one({"_id": username})
        except Exception as e:
            logger.error(f"데이터 조회 실패: {e}")
            return None

    def save_history(self, username: str, results: Dict[str, Any]):
        """일별 히스토리 저장"""
        try:
            today = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            followers_count = len(results.get('followers', []))
            following_count = len(results.get('following', []))
            
            self.col_history.update_one(
                {"username": username, "date": today},
                {"$set": {
                    "followers_count": followers_count,
                    "following_count": following_count,
                    "timestamp": datetime.datetime.now()
                }},
                upsert=True
            )
            logger.info(f"[History] 히스토리 저장: {today.strftime('%Y-%m-%d')}")

        except Exception as e:
            logger.error(f"히스토리 저장 오류: {e}")


    def get_analysis(self, username: str) -> Dict[str, Any]:
        """팔로워/팔로잉 분석 데이터 반환 (맞팔 안 함, 팬 등)"""
        try:
            doc = self.col_latest.find_one({"_id": username})
            if not doc:
                return {
                    "followers": [],
                    "following": [],
                    "non_followers": [],
                    "fans": [],
                    "last_updated": None
                }

            followers = doc.get("followers", [])
            following = doc.get("following", [])
            last_updated = doc.get("last_updated")

            # username 집합 생성
            followers_set = {u['username'] for u in followers if 'username' in u}
            following_set = {u['username'] for u in following if 'username' in u}

            # 분석 (단순 문자열 리스트 반환)
            non_followers = sorted(list(following_set - followers_set))
            fans = sorted(list(followers_set - following_set))

            return {
                "followers": followers,
                "following": following,
                "non_followers": non_followers, # 나를 맞팔 안 함 (내가 팔로우함 - 나를 팔로우함)
                "fans": fans,                   # 나를 짝사랑 함 (나를 팔로우함 - 내가 팔로우함)
                "last_updated": last_updated
            }

        except Exception as e:
            logger.error(f"분석 데이터 조회 실패: {e}")
            return {
                "followers": [],
                "following": [],
                "non_followers": [],
                "fans": [],
                "last_updated": None
            }



    def get_history(self, username: str, days: int = 30) -> List[Dict[str, Any]]:
        """최근 N일간 히스토리 조회"""
        try:
            start_date = datetime.datetime.now() - datetime.timedelta(days=days)
            
            cursor = self.col_history.find(
                {"username": username, "date": {"$gte": start_date}},
                {"_id": 0, "date": 1, "followers_count": 1, "following_count": 1}
            ).sort("date", 1)
            
            return list(cursor)
        except Exception as e:
            logger.error(f"히스토리 조회 오류: {e}")
            return []

    def get_change_summary(self, username: str) -> Optional[Dict[str, Any]]:
        """최근 변동 사항 요약 (어제 vs 오늘)"""
        try:
            # 최근 2일 데이터 가져오기
            cursor = self.col_history.find(
                {"username": username}
            ).sort("date", -1).limit(2)
            
            records = list(cursor)
            
            if len(records) < 2:
                return {"has_change": False, "message": "비교할 데이터 없음"}
            
            today = records[0]
            yesterday = records[1]
            
            followers_diff = today['followers_count'] - yesterday['followers_count']
            following_diff = today['following_count'] - yesterday['following_count']
            
            return {
                "has_change": followers_diff != 0 or following_diff != 0,
                "followers_diff": followers_diff,
                "following_diff": following_diff,
                "today_followers": today['followers_count'],
                "yesterday_followers": yesterday['followers_count']
            }
        except Exception as e:
            logger.error(f"변동 요약 조회 오류: {e}")
            return None
