from notion_client import Client
from notion_client.errors import APIResponseError
from typing import Dict, List, Optional, Tuple, Any
import os
from dotenv import load_dotenv
import time
import random

# Notion API 설정 (.env 환경변수 사용 권장)
load_dotenv()
NOTION_TOKEN = os.getenv("NOTION_TOKEN")

# 단일 DB (Notion의 서로 다른 보기에서 사용)
DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

if not NOTION_TOKEN or not DATABASE_ID:
    raise RuntimeError(
        "환경변수 NOTION_TOKEN 와 NOTION_DATABASE_ID 가 필요합니다. 프로젝트 루트의 .env 파일을 설정하세요"
    )

notion = Client(auth=NOTION_TOKEN)

"""
번호 부여 규칙 (공통)
 - 제목 포맷: {Target}-{취약점 유형}-{번호(3자리)}
 - 번호는 그룹 기준으로 001부터 부여
 - 정렬 기준: 발견 날짜(존재 시) 또는 페이지 생성 시간 오름차순
 - 상태값 등은 무시하고 DB의 모든 페이지 대상으로 수행
"""

# 필드 이름 (.env로 커스터마이즈 가능)
DATE_PROP = os.getenv("NOTION_DATE_PROP", "발견 날짜")
TARGET_PROP = os.getenv("NOTION_TARGET_PROP", "Target")
TYPE_PROP = os.getenv("NOTION_TYPE_PROP", "취약점 유형")

# 번호 기록용 속성 (보기별 표시 용도)
PLATFORM_INDEX_PROP = os.getenv("NOTION_PLATFORM_INDEX_PROP", "플랫폼 번호")
TYPE_INDEX_PROP = os.getenv("NOTION_TYPE_INDEX_PROP", "유형 번호")


def _retrieve_db(database_id: str) -> Dict:
    return notion.databases.retrieve(database_id=database_id)


def _date_sort_spec(db: Dict, direction: str = "ascending") -> List[Dict]:
    # 발견 날짜가 있으면 그 필드 기준, 없으면 생성시간(created_time) 기준
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


def _title_prop_name(db: Dict) -> str:
    for name, prop in db.get("properties", {}).items():
        if prop.get("type") == "title":
            return name
    raise RuntimeError("해당 데이터베이스에 'title' 속성이 없습니다. Notion DB 설정을 확인하세요")


def _ensure_number_property(database_id: str, db: Dict, prop_name: str):
    if prop_name in (db.get("properties") or {}):
        return
    # 데이터베이스에 숫자 속성 추가
    notion.databases.update(
        database_id=database_id,
        properties={
            prop_name: {
                "number": {},
                "type": "number",
                "name": prop_name,
            }
        },
    )


def _update_page_with_retry(page_id: str, properties: Dict[str, Any]):
    backoff = 0.5
    for attempt in range(6):
        try:
            return notion.pages.update(page_id=page_id, properties=properties)
        except APIResponseError as e:
            # Handle transient conflicts or rate limits
            status = getattr(e, "status", None)
            if status in (409, 429) and attempt < 5:
                time.sleep(backoff + random.uniform(0, 0.2))
                backoff *= 2
                continue
            raise


def update_page_title(page_id: str, title_prop: str, new_title: str):
    value = {
        "title": [
            {"type": "text", "text": {"content": new_title}}
        ]
    }
    _update_page_with_retry(page_id=page_id, properties={title_prop: value})


def _query_all_pages_sorted(database_id: str, sorts: List[Dict]) -> List[Dict]:
    results: List[Dict] = []
    cursor: Optional[str] = None
    while True:
        resp = notion.databases.query(
            **{
                "database_id": database_id,
                "sorts": sorts,
                "start_cursor": cursor,
            }
        )
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return results


def _extract_target_and_type(page: Dict) -> Tuple[str, str]:
    props = page.get("properties", {})
    target_obj = props.get(TARGET_PROP)
    type_obj = props.get(TYPE_PROP)
    target = _extract_plain_text(target_obj or {})
    vtype = _extract_plain_text(type_obj or {})
    return target, vtype


def _process_both_numberings(database_id: str):
    """
    - 플랫폼(타겟)별 번호 → 제목에 반영(기존 동작 유지) + 선택적으로 숫자 속성에도 저장
    - 취약점 유형별 번호 → 별도의 숫자 속성(TYPE_INDEX_PROP)에 저장(제목은 변경하지 않음)
    """
    db = _retrieve_db(database_id)
    title_prop = _title_prop_name(db)
    sorts = _date_sort_spec(db, "ascending")

    # 필요한 숫자 속성 보장
    _ensure_number_property(database_id, db, PLATFORM_INDEX_PROP)
    # DB 스키마가 캐시되어 있을 수 있으므로 다시 읽기
    db = _retrieve_db(database_id)
    _ensure_number_property(database_id, db, TYPE_INDEX_PROP)

    pages = _query_all_pages_sorted(database_id, sorts)
    print(
        f"DB({database_id}): 총 {len(pages)}건에 대해 플랫폼별/유형별 번호를 각각 계산합니다."
    )

    from collections import OrderedDict
    by_target: Dict[str, List[Tuple[Dict, str]]] = OrderedDict()
    by_type: Dict[str, List[Tuple[Dict, str]]] = OrderedDict()
    skipped = 0

    for p in pages:
        target, vtype = _extract_target_and_type(p)
        if not target or not vtype:
            skipped += 1
            continue
        by_target.setdefault(target, []).append((p, vtype))
        by_type.setdefault(vtype, []).append((p, target))

    updated_title = 0
    updated_platform_idx = 0
    updated_type_idx = 0

    # 1) 플랫폼별 번호 → 제목 갱신 + 숫자 속성 저장
    for target, items in by_target.items():
        print(f"[플랫폼] 그룹 '{target}': {len(items)}건")
        for idx, (page, vtype) in enumerate(items, start=1):
            idx3 = f"{idx:03d}"
            new_title = f"{target}-{vtype}-{idx3}"
            # 제목과 플랫폼 번호를 한 번의 업데이트로 적용하여 충돌 방지
            props = {
                title_prop: {"title": [{"type": "text", "text": {"content": new_title}}]},
                PLATFORM_INDEX_PROP: {"number": idx},
            }
            _update_page_with_retry(page_id=page["id"], properties=props)
            updated_title += 1
            updated_platform_idx += 1
            print(f" - 제목/플랫폼번호 '{new_title}' / {idx} 적용 (page: {page['id']})")
            time.sleep(0.05)

    # 2) 취약점 유형별 번호 → 숫자 속성만 저장(제목은 그대로 둠)
    for vtype, items in by_type.items():
        print(f"[유형] 그룹 '{vtype}': {len(items)}건")
        for idx, (page, target) in enumerate(items, start=1):
            _update_page_with_retry(
                page_id=page["id"],
                properties={TYPE_INDEX_PROP: {"number": idx}},
            )
            updated_type_idx += 1
            print(f" - 유형번호 {idx} 적용 (page: {page['id']})")
            time.sleep(0.05)

    if skipped:
        print(f"참고: {skipped}건은 '{TARGET_PROP}', '{TYPE_PROP}' 속성이 없어 스킵했습니다.")
    print(
        f"완료: 제목 {updated_title}건, 플랫폼번호 {updated_platform_idx}건, 유형번호 {updated_type_idx}건 업데이트."
    )


def main():
    # 단일 DB에서 두 가지 보기 기준의 번호를 각각 반영
    _process_both_numberings(DATABASE_ID)


if __name__ == "__main__":
    main()
