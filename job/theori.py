import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from sync_utils import (
    DEFAULT_TIMEOUT,
    JobPosting,
    NotionClient,
    build_property_map,
    load_env,
    send_discord_notification,
    should_skip,
)

API_URL = "https://theori.io/api/service/position"
LOCATION_LABELS = {
    "Seoul": "Seoul, South Korea",
    "US": "US - Austin",
    "Remote": "Remote",
}


def fetch_positions(api_url: str) -> List[Dict[str, Any]]:
    resp = requests.get(api_url, timeout=DEFAULT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError("Unexpected response from Theori API.")
    return data


def parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def normalize_position(entry: Dict[str, Any], company: str, source_label: str) -> JobPosting:
    location_key = entry.get("location")
    location = LOCATION_LABELS.get(location_key, location_key)
    title = entry.get("title_eng") or entry.get("title_kor") or "Unknown Role"
    tags = [
        entry.get("dept"),
        entry.get("position_type"),
        location,
    ]

    due_date_raw = entry.get("due_date") or entry.get("deadline") or entry.get("created_at")
    return JobPosting(
        job_id=entry.get("id"),
        title=title,
        company=company,
        team=entry.get("dept"),
        role=entry.get("dept"),
        employment_type=entry.get("position_type"),
        location=location,
        open_date=parse_datetime(entry.get("created_at")),
        due_date=parse_datetime(due_date_raw),
        url=entry.get("link"),
        tags=[tag for tag in tags if tag],
        source=source_label,
    )


def main() -> None:
    load_env()
    notion_token = os.getenv("NOTION_TOKEN")
    notion_database_id = os.getenv("NOTION_DATABASE_ID")
    discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
    api_url = os.getenv("THEORI_API_URL", API_URL)
    company_name = os.getenv("THEORI_COMPANY_NAME", "Theori")
    source_label = os.getenv("THEORI_SOURCE_LABEL", "\ud2f0\uc624\ub9ac")
    dry_run = (
        "--dry-run" in sys.argv
        or os.getenv("THEORI_DRY_RUN", "").lower() in {"1", "true", "yes"}
    )

    if not notion_token or not notion_database_id:
        print(
            "NOTION_TOKEN\uacfc NOTION_DATABASE_ID \ud658\uacbd\ubcc0\uc218\uac00 \ud544\uc694\ud569\ub2c8\ub2e4.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("[INFO] Fetching Theori positions...")
    raw_positions = fetch_positions(api_url)
    positions = [
        normalize_position(position, company_name, source_label)
        for position in raw_positions
        if position.get("is_active")
    ]
    print(f"[INFO] Found {len(positions)} active positions on Theori.")

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

    for job in positions:
        if not job.url:
            continue
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
