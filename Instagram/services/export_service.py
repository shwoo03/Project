"""
데이터 내보내기 서비스
"""
import csv
import logging
from io import BytesIO, StringIO
from typing import List, Any, Union

logger = logging.getLogger(__name__)

class ExportService:
    @staticmethod
    def create_csv(data: List[Union[dict, str]]) -> BytesIO:
        """데이터를 CSV 포맷으로 변환"""
        if not data:
            return BytesIO(b"")
            
        output = StringIO()
        
        try:
            # 데이터가 단순 문자열(username) 리스트인지, 객체(dict) 리스트인지 확인
            if isinstance(data[0], str):
                # 문자열 리스트인 경우 (non_followers, fans 등)
                writer = csv.writer(output)
                writer.writerow(["username"])  # 헤더
                for item in data:
                    writer.writerow([item])
            elif isinstance(data[0], dict):
                # 객체 리스트인 경우 (followers, following)
                # 모든 키를 수집하여 헤더로 사용 (순서 보장 없음, 정렬 권장)
                # 첫 번째 아이템의 키를 기준으로 하되, 모든 아이템의 키를 합집합으로 처리하는 것이 안전하지만
                # 성능상 첫 번째 아이템 키만 사용하는 경우가 많음. 여기서는 첫 번째 아이템 기준.
                headers = list(data[0].keys())
                writer = csv.DictWriter(output, fieldnames=headers)
                writer.writeheader()
                writer.writerows(data)
            else:
                logger.warning("지원하지 않는 데이터 형식입니다.")
                return BytesIO(b"")
                
            # String을 Bytes로 변환 (UTF-8 w/ BOM for Excel compatibility)
            csv_data = output.getvalue().encode('utf-8-sig')
            stream = BytesIO(csv_data)
            stream.seek(0)
            
            return stream
            
        except Exception as e:
            logger.error(f"CSV 생성 중 오류: {e}")
            raise e
        finally:
            output.close()
