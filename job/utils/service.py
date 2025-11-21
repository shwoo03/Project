import sys
from typing import List

import requests

from . import database
from .models import JobPosting
from .notion import NotionClient
from . import discord

def sync_jobs(jobs: List[JobPosting], source_label: str, dry_run: bool = False) -> None:
    """
    Sync a list of jobs to Notion and Discord.
    
    Workflow:
    1. Cleanup stale jobs from DB
    2. Filter out existing jobs (check DB)
    3. Create new Notion pages
    4. Save new jobs to DB
    5. Send Discord notification
    """
    print(f"[INFO] Processing {len(jobs)} jobs for {source_label}...")

    # 1. Cleanup stale jobs
    deleted_count = database.cleanup_stale_jobs(jobs, source_label)
    if deleted_count > 0:
        print(f"[INFO] Removed {deleted_count} stale jobs from DB.")

    # 2. Initialize Notion Client
    try:
        notion = NotionClient()
    except ValueError as e:
        print(f"[ERROR] Notion configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.HTTPError as exc:
        message = exc.response.text if exc.response is not None else str(exc)
        print(
            "[ERROR] Failed to access Notion database. "
            "Verify NOTION_DATABASE_ID and share it with the integration.",
            file=sys.stderr,
        )
        print(message, file=sys.stderr)
        sys.exit(1)

    created_jobs: List[JobPosting] = []

    # 3. Process each job
    for job in jobs:
        if not job.url:
            continue

        # Check if job already exists in DB
        if database.is_job_exists(job):
            continue

        if dry_run:
            created_jobs.append(job)
            print(f"[DRY-RUN] Would add Notion entry for {job.title}.")
            continue

        try:
            # Create Notion Page
            notion.create_page(job)
            print(f"[INFO] Added Notion entry for {job.title}.")

            # Save to MongoDB
            database.save_job(job)
            created_jobs.append(job)

        except requests.HTTPError as exc:
            print(
                f"[ERROR] Failed to create Notion page for {job.title}: {exc}",
                file=sys.stderr,
            )
        except Exception as exc:
            print(
                f"[ERROR] Failed to save job {job.title}: {exc}",
                file=sys.stderr,
            )

    # 4. Send Discord Notification
    if created_jobs and not dry_run:
        print(f"[INFO] Sending Discord notification for {len(created_jobs)} new jobs.")
        try:
            discord.send_notification(created_jobs, source_label)
        except requests.HTTPError as exc:
            print(f"[ERROR] Failed to send Discord notification: {exc}", file=sys.stderr)
    elif created_jobs and dry_run:
        print(f"[DRY-RUN] Skipped Discord notification for {len(created_jobs)} jobs.")
    else:
        print("[INFO] No new jobs to notify.")
