from notion_client import Client
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

# Notion API 설정 (필요 시 환경변수 사용 권장)
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise RuntimeError("환경변수 NOTION_TOKEN 및 NOTION_DATABASE_ID 가 필요합니다. 프로젝트 루트의 .env 파일에 설정하거나 OS 환경변수로 제공하세요.")

notion = Client(auth=NOTION_TOKEN)

# 속성 이름 (DB에 맞게 조정)
STATUS_PROP = "제보 상태"   # Status/Select 속성명
DATE_PROP = "발견 날짜"      # Date 속성명 (없으면 생성일로 정렬)
CVE_PROP = "CVE NUM"        # Text(리치 텍스트) 또는 Title 속성명

# 후보 상태명: 실제 DB 옵션 이름과 다를 수 있어 광범위하게 매칭
PROGRESS_CANDIDATES = [
    "처리 중", "처리중",
    "진행 중", "진행중",
    "제보 완료", "제보완료",
    "디벨롭중", "디벨롭 중", "개발중", "개발 중",
    "In progress", "In Progress", "Processing"
]
ACCEPTED_CANDIDATES = [
    "Accepted", "수락됨", "승인됨", "완료", "Done", "Resolved"
]
REJECTED_CANDIDATES = [
    "폐기", "무시", "Invalid", "Rejected", "Duplicate", "중복", "취소", "Canceled", "Cancelled"
]


def _norm(s: str) -> str:
    return "".join(s.split()).lower()


def _retrieve_db() -> Dict:
    return notion.databases.retrieve(database_id=DATABASE_ID)


def _status_filter_key(db: Dict) -> str:
    prop = db["properties"].get(STATUS_PROP)
    if not prop:
        raise RuntimeError(f"상태 속성 '{STATUS_PROP}' 를 DB에서 찾을 수 없습니다.")
    t = prop.get("type")
    if t in ("status", "select"):
        return t
    raise RuntimeError(f"상태 속성 '{STATUS_PROP}' 타입이 status/select 가 아닙니다: {t}")


def _cve_prop_type(db: Dict) -> str:
    prop = db["properties"].get(CVE_PROP)
    if not prop:
        raise RuntimeError(f"CVE 속성 '{CVE_PROP}' 를 DB에서 찾을 수 없습니다.")
    t = prop.get("type")
    if t in ("rich_text", "title"):
        return t
    raise RuntimeError(f"CVE 속성 '{CVE_PROP}' 타입이 텍스트가 아닙니다: {t}")


def _date_sort_spec(db: Dict) -> List[Dict]:
    # 날짜 속성이 있으면 그 속성으로, 없으면 생성일(created_time) 기준 정렬
    if DATE_PROP in db.get("properties", {}) and db["properties"][DATE_PROP].get("type") == "date":
        return [{"property": DATE_PROP, "direction": "ascending"}]
    return [{"timestamp": "created_time", "direction": "ascending"}]


def _build_status_prefix_map(db: Dict) -> Dict[str, str]:
    # DB에 실제 존재하는 옵션 이름들만 선별해서 매핑한다.
    prop_def = db["properties"][STATUS_PROP]
    kind = prop_def["type"]
    options = prop_def[kind].get("options", [])
    present: Dict[str, str] = { _norm(o["name"]): o["name"] for o in options }

    mapping: Dict[str, str] = {}
    for cand in PROGRESS_CANDIDATES:
        if _norm(cand) in present:
            mapping[present[_norm(cand)]] = "P"
    for cand in ACCEPTED_CANDIDATES:
        if _norm(cand) in present:
            mapping[present[_norm(cand)]] = "A"
    for cand in REJECTED_CANDIDATES:
        if _norm(cand) in present:
            mapping[present[_norm(cand)]] = "X"

    return mapping


def _build_group_status_map(db: Dict) -> Dict[str, List[str]]:
    # 실제 DB에 존재하는 옵션만 그룹(P/A/X)으로 수집
    prop_def = db["properties"][STATUS_PROP]
    kind = prop_def["type"]
    options = prop_def[kind].get("options", [])
    present: Dict[str, str] = { _norm(o["name"]): o["name"] for o in options }

    groups: Dict[str, List[str]] = {"P": [], "A": [], "X": []}
    for cand in PROGRESS_CANDIDATES:
        key = _norm(cand)
        if key in present and present[key] not in groups["P"]:
            groups["P"].append(present[key])
    for cand in ACCEPTED_CANDIDATES:
        key = _norm(cand)
        if key in present and present[key] not in groups["A"]:
            groups["A"].append(present[key])
    for cand in REJECTED_CANDIDATES:
        key = _norm(cand)
        if key in present and present[key] not in groups["X"]:
            groups["X"].append(present[key])

    # 비어있는 그룹은 제거
    return {k: v for k, v in groups.items() if v}


def query_pages_by_status(status_value: str, filter_key: str, sorts: List[Dict]):
    results = []
    cursor: Optional[str] = None
    while True:
        resp = notion.databases.query(
            **{
                "database_id": DATABASE_ID,
                "filter": {
                    "property": STATUS_PROP,
                    filter_key: {"equals": status_value},
                },
                "sorts": sorts,
                "start_cursor": cursor,
            }
        )
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def query_pages_by_status_group(status_values: List[str], filter_key: str, sorts: List[Dict]):
    results: List[Dict] = []
    cursor: Optional[str] = None
    if not status_values:
        return results

    if len(status_values) == 1:
        base_filter = {
            "property": STATUS_PROP,
            filter_key: {"equals": status_values[0]},
        }
    else:
        base_filter = {
            "or": [
                {"property": STATUS_PROP, filter_key: {"equals": s}} for s in status_values
            ]
        }

    while True:
        resp = notion.databases.query(
            **{
                "database_id": DATABASE_ID,
                "filter": base_filter,
                "sorts": sorts,
                "start_cursor": cursor,
            }
        )
        results.extend(resp["results"])
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def update_page_text(page_id: str, text_value: str, cve_prop_type: str):
    if cve_prop_type == "title":
        value = {
            "title": [
                {"type": "text", "text": {"content": text_value}}
            ]
        }
    else:
        value = {
            "rich_text": [
                {"type": "text", "text": {"content": text_value}}
            ]
        }
    notion.pages.update(page_id=page_id, properties={CVE_PROP: value})


def main():
    db = _retrieve_db()
    filter_key = _status_filter_key(db)  # 'status' 또는 'select'
    cve_prop_type = _cve_prop_type(db)   # 'rich_text' 또는 'title'
    sorts = _date_sort_spec(db)

    # 그룹(P/A/X)별 상태 묶음을 생성하고, 그룹 단위로 연속 번호 매김
    groups = _build_group_status_map(db)
    if not groups:
        print("경고: 상태 후보와 일치하는 DB 옵션이 없어 아무 것도 변경하지 않았습니다.")
        return

    for prefix, status_names in groups.items():
        pages = query_pages_by_status_group(status_names, filter_key, sorts)
        print(f"[{prefix}그룹: {', '.join(status_names)}] {len(pages)}건: 날짜 오름차순 정렬 후 번호 부여")
        for idx, page in enumerate(pages, start=1):
            code = f"{prefix}{idx}"
            update_page_text(page["id"], code, cve_prop_type)
            title = page.get("properties", {}).get("Name", {}).get("title", [{}])[0].get("plain_text", "")
            print(f" - {code} 적용 (page: {page['id']})")

    print("모든 대상 상태에 대해 CVE NUM 텍스트 업데이트 완료!")


if __name__ == "__main__":
    main()
