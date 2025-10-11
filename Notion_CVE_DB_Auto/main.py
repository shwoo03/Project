from notion_client import Client
from typing import Dict, List, Optional, Tuple, Any
import os
from dotenv import load_dotenv

# Notion API 설정 (필요 시 환경변수 사용 권장)
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise RuntimeError("환경변수 NOTION_TOKEN 및 NOTION_DATABASE_ID 가 필요합니다. 프로젝트 루트의 .env 파일에 설정하거나 OS 환경변수로 제공하세요.")

notion = Client(auth=NOTION_TOKEN)

"""
ID 자동작성 형식 변경:
 - 형식: {Target}-{취약점 유형}-{번호(3자리, 001부터)}
 - 번호는 Target별로 따로 매김 (타입 상관없이 같은 Target 묶음)
 - 부여 순서: '발견 날짜' 오름차순(가장 오래된 것부터) 1부터 증가
 - 날짜 속성이 없으면 생성일(created_time) 기준으로 오름차순 정렬
 - 상태값(처리 중/Accepted/폐기 등)은 무시하고 DB의 모든 항목을 대상으로 함
"""

# 속성 이름 (DB에 맞게 조정/환경변수로 오버라이드 가능)
DATE_PROP = os.getenv("NOTION_DATE_PROP", "발견 날짜")
TARGET_PROP = os.getenv("NOTION_TARGET_PROP", "Target")
TYPE_PROP = os.getenv("NOTION_TYPE_PROP", "취약점 유형")

# 상태/접두 관련 로직은 제거됨 (상태값 무시)


def _retrieve_db() -> Dict:
    return notion.databases.retrieve(database_id=DATABASE_ID)


# 과거 상태/별도 속성 로직 삭제됨


def _date_sort_spec(db: Dict, direction: str = "ascending") -> List[Dict]:
    # 날짜 속성이 있으면 그 속성으로, 없으면 생성일(created_time) 기준 정렬
    if DATE_PROP in db.get("properties", {}) and db["properties"][DATE_PROP].get("type") == "date":
        return [{"property": DATE_PROP, "direction": direction}]
    return [{"timestamp": "created_time", "direction": direction}]


def _extract_plain_text(prop_obj: Dict[str, Any]) -> str:
    t = prop_obj.get("type")
    if t == "select":
        opt = prop_obj.get("select") or {}
        return (opt.get("name") or "").strip()
    if t == "multi_select":
        opts = prop_obj.get("multi_select") or []
        names = [str(o.get("name") or "").strip() for o in opts if o]
        return "/".join([n for n in names if n])
    if t == "title":
        items = prop_obj.get("title") or []
        return "".join([(i.get("plain_text") or "") for i in items]).strip()
    if t == "rich_text":
        items = prop_obj.get("rich_text") or []
        return "".join([(i.get("plain_text") or "") for i in items]).strip()
    if t == "url":
        return (prop_obj.get("url") or "").strip()
    if t == "email":
        return (prop_obj.get("email") or "").strip()
    if t == "phone_number":
        return (prop_obj.get("phone_number") or "").strip()
    if t == "number":
        num = prop_obj.get("number")
        return "" if num is None else str(num)
    return ""


def _get_group_key(page: Dict) -> Optional[Tuple[str, str]]:
    props = page.get("properties", {})
    target_obj = props.get(TARGET_PROP)
    type_obj = props.get(TYPE_PROP)
    if not target_obj or not type_obj:
        return None
    target = _extract_plain_text(target_obj)
    vtype = _extract_plain_text(type_obj)
    if not target or not vtype:
        return None
    return (target, vtype)


def _query_all_pages_sorted(sorts: List[Dict]) -> List[Dict]:
    results: List[Dict] = []
    cursor: Optional[str] = None
    while True:
        resp = notion.databases.query(
            **{
                "database_id": DATABASE_ID,
                "sorts": sorts,
                "start_cursor": cursor,
            }
        )
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def _title_prop_name(db: Dict) -> str:
    for name, prop in db.get("properties", {}).items():
        if prop.get("type") == "title":
            return name
    raise RuntimeError("이 데이터베이스에 'title' 타입 속성이 없습니다. Notion DB 설정을 확인하세요.")


def update_page_title(page_id: str, title_prop: str, new_title: str):
    value = {
        "title": [
            {"type": "text", "text": {"content": new_title}}
        ]
    }
    notion.pages.update(page_id=page_id, properties={title_prop: value})


def main():
    db = _retrieve_db()
    # 상태값은 무시. 제목 생성만 수행.
    title_prop = _title_prop_name(db)
    sorts = _date_sort_spec(db, "ascending")  # 발견 날짜 오름차순

    pages = _query_all_pages_sorted(sorts)
    print(f"총 {len(pages)}건 수집됨. 제목을 '{TARGET_PROP}-{TYPE_PROP}-번호(3자리, 오름차순)' 으로 수정합니다.")

    # Target별 그룹핑 (오름차순 정렬된 순서를 유지)
    from collections import OrderedDict
    groups: Dict[str, List[Tuple[Dict, str]]] = OrderedDict()
    skipped = 0
    for p in pages:
        key = _get_group_key(p)
        if not key:
            skipped += 1
            continue
        target, vtype = key
        groups.setdefault(target, []).append((p, vtype))

    updated = 0
    for target, items in groups.items():
        print(f"Target '{target}': {len(items)}건 오름차순 번호(3자리) 부여")
        for idx, (page, vtype) in enumerate(items, start=1):
            idx3 = f"{idx:03d}"
            new_title = f"{target}-{vtype}-{idx3}"
            update_page_title(page["id"], title_prop, new_title)
            updated += 1
            print(f" - '{new_title}' 적용 (page: {page['id']})")

    if skipped:
        print(f"참고: {skipped}건은 '{TARGET_PROP}', '{TYPE_PROP}' 속성이 없어 스킵했습니다.")
    print(f"완료: {updated}건 제목 업데이트. 형식: '{{Target}}-{{취약점 유형}}-{{번호(3자리)}}' (번호는 Target별 오름차순)")


if __name__ == "__main__":
    main()
