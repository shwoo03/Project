import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from sync_utils import (
    DEFAULT_TIMEOUT,
    JobPosting,
    NotionClient,
    build_property_map,
    load_env,
    send_discord_notification,
    should_skip,
)

BASE_URL = "https://enki.career.greetinghr.com"
GUIDE_PATH = "/ko/guide?employments=INTERN_WORKER"

EMPLOYMENT_LABELS = {
    "PERMANENT_WORKER": "\uc815\uaddc\uc9c1",
    "TEMPORARY_WORKER": "\uacc4\uc57d\uc9c1",
    "INTERN_WORKER": "\uc778\ud134",
    "PART_TIME_WORKER": "\ud30c\ud2b8\ud0c0\uc784",
    "FREELANCER": "\ud504\ub9ac\ub79c\uc11c",
}

CAREER_LABELS = {
    "NOT_MATTER": "\uacbd\ub825 \ubb34\uad00",
    "NEWCOMER": "\uc2e0\uc785",
    "EXPERIENCED": "\uacbd\ub825",
}


def fetch_page(url: str) -> str:
    resp = requests.get(url, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def extract_openings(html: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise RuntimeError("Unable to locate __NEXT_DATA__ payload in Enki page.")
    data = json.loads(script.string)
    queries: List[Dict[str, Any]] = (
        data.get("props", {})
        .get("pageProps", {})
        .get("dehydratedState", {})
        .get("queries", [])
    )
    for query in queries:
        key = query.get("queryKey") or []
        if key and key[0] == "openings":
            state = query.get("state", {})
            openings = state.get("data")
            if isinstance(openings, list):
                return openings
    raise RuntimeError("Openings data not found in Enki payload.")


def to_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def pick_primary_position(opening: Dict[str, Any]) -> Dict[str, Any]:
    positions = (
        opening.get("openingJobPosition", {}).get("openingJobPositions") or []
    )
    if not positions:
        return {}
    for item in positions:
        if item.get("representative"):
            return item
    return positions[0]


def normalize_opening(opening: Dict[str, Any], source_label: str) -> JobPosting:
    job_id = str(opening.get("openingId"))
    primary = pick_primary_position(opening)

    job_label = None
    if isinstance(primary.get("job"), dict):
        job_label = primary["job"].get("job")
    role = job_label or opening.get("job")
    occupation_label = None
    if isinstance(primary.get("occupation"), dict):
        occupation_label = primary["occupation"].get("occupation")

    employment_type = (
        primary.get("jobPositionEmployment", {}).get("employmentType")
        or opening.get("employmentType")
    )
    employment_label = EMPLOYMENT_LABELS.get(employment_type, employment_type)

    career_type = (
        primary.get("jobPositionCareer", {}).get("careerType")
        or opening.get("careerInfo", {}).get("type")
    )
    experience_label = CAREER_LABELS.get(career_type, career_type)

    place_info = primary.get("place") or {}
    location = place_info.get("location") or opening.get("place")
    detail_location = place_info.get("detailPlace") or opening.get("detailPlace")

    due_date = to_datetime(opening.get("dueDate"))
    open_date = to_datetime(opening.get("openDate"))

    company = None
    if isinstance(opening.get("group"), dict):
        company = opening["group"].get("name")

    tags = []
    for candidate in [
        occupation_label,
        role,
        employment_label,
        experience_label,
        location,
    ]:
        if candidate and candidate not in tags:
            tags.append(candidate)

    return JobPosting(
        job_id=job_id,
        title=opening.get("title") or role or f"Opening {job_id}",
        company=company,
        team=role,
        role=occupation_label,
        employment_type=employment_label,
        experience=experience_label,
        location=location,
        detail_location=detail_location,
        due_date=due_date,
        open_date=open_date,
        url=urljoin(BASE_URL, f"/ko/o/{job_id}"),
        tags=tags,
        source=source_label,
    )


def main() -> None:
    load_env()
    notion_token = os.getenv("NOTION_TOKEN")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    guide_url = os.getenv("ENKI_GUIDE_URL", urljoin(BASE_URL, GUIDE_PATH))
    dry_run = (
        "--dry-run" in sys.argv
        or os.getenv("ENKI_DRY_RUN", "").lower() in {"1", "true", "yes"}
    )
    source_label = os.getenv("ENKI_SOURCE_LABEL", "\uc5d4\ud0a4")

    if not notion_token or not notion_database_id:
        print(
            "NOTION_TOKEN\uacfc NOTION_DATABASE_ID \ud658\uacbd\ubcc0\uc218\uac00 \ud544\uc694\ud569\ub2c8\ub2e4.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[INFO] Fetching job postings...")
    page_html = fetch_page(guide_url)
    raw_openings = extract_openings(page_html)
    jobs = [normalize_opening(entry, source_label) for entry in raw_openings]
    print(f"[INFO] Found {len(jobs)} openings on Enki.")

    property_map = build_property_map()
    try:
        notion = NotionClient(
            notion_token,
            notion_database_id,
            property_map.copy(),
        )
    except requests.HTTPError as exc:
        message = exc.response.text if exc.response is not None else str(exc)
        print(
            "[ERROR] Failed to access Notion database. "
            "Verify NOTION_DATABASE_ID and share it with the integration.",
            file=sys.stderr,
        )
        print(message, file=sys.stderr)
        sys.exit(1)

    indexes = notion.fetch_existing_indexes()
    meta_by_job_id = indexes.get("meta_by_job_id", {})
    meta_by_title = indexes.get("meta_by_title", {})

    created_jobs: List[JobPosting] = []
    for job in jobs:
        if should_skip(job, indexes):
            updated = False
            meta = None
            if job.job_id:
                meta = meta_by_job_id.get(job.job_id)
            if meta is None:
                meta = meta_by_title.get(job.title)
            if meta:
                if job.source and not meta.get("source"):
                    try:
                        notion.update_select_property(
                            meta["page_id"],
                            "source",
                            job.source,
                        )
                        meta["source"] = job.source
                        updated = True
                        print(
                            f"[INFO] Updated source for existing Notion entry {job.title}."
                        )
                    except requests.HTTPError as exc:
                        print(
                            f"[ERROR] Failed to update source for {job.title}: {exc}",
                                file=sys.stderr,
                            )
                due_iso = job.due_date_iso()
                if due_iso:
                    existing_due = meta.get("due_date")
                    if existing_due != due_iso:
                        try:
                            notion.update_date_property(
                                meta["page_id"],
                                "due_date",
                                due_iso,
                            )
                            meta["due_date"] = due_iso
                            updated = True
                            print(
                                f"[INFO] Updated due date for existing Notion entry {job.title}."
                            )
                        except requests.HTTPError as exc:
                            print(
                                f"[ERROR] Failed to update due date for {job.title}: {exc}",
                                file=sys.stderr,
                            )
                if job.url:
                    existing_link = meta.get("title_link")
                    if existing_link != job.url:
                        try:
                            notion.update_title_link(
                                meta["page_id"],
                                job.title,
                                job.url,
                            )
                            meta["title_link"] = job.url
                            updated = True
                            print(
                                f"[INFO] Updated link for existing Notion entry {job.title}."
                            )
                        except requests.HTTPError as exc:
                            print(
                                f"[ERROR] Failed to update link for {job.title}: {exc}",
                                file=sys.stderr,
                            )
            if updated:
                continue
            continue
        if dry_run:
            created_jobs.append(job)
            print(f"[DRY-RUN] Would add Notion entry for {job.title}.")
            continue
        try:
            notion.create_page(job)
            if job.job_id:
                indexes["job_ids"].add(job.job_id)
            indexes["links"].add(job.url)
            indexes["titles"].add(job.title)
            created_jobs.append(job)
            print(f"[INFO] Added Notion entry for {job.title}.")
        except requests.HTTPError as exc:
            print(
                f"[ERROR] Failed to create Notion page for {job.title}: {exc}",
                file=sys.stderr,
            )

    if created_jobs and not dry_run:
        print(f"[INFO] Sending Discord notification for {len(created_jobs)} new jobs.")
        try:
            send_discord_notification(discord_webhook, created_jobs, source_label)
        except requests.HTTPError as exc:
            print(f"[ERROR] Failed to send Discord notification: {exc}", file=sys.stderr)
    elif created_jobs and dry_run:
        print(f"[DRY-RUN] Skipped Discord notification for {len(created_jobs)} jobs.")
    else:
        print("[INFO] No new jobs to notify.")


if __name__ == "__main__":
    main()
