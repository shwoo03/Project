from typing import List, Optional
import requests
from . import config
from .models import JobPosting

def send_notification(
    jobs: List[JobPosting],
    source_label: Optional[str] = None,
) -> None:
    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url:
        return

    default_prefix = "채용 공고가 업데이트되었습니다."
    prefix = (
        f"{source_label} 채용 공고가 업데이트되었습니다."
        if source_label
        else default_prefix
    )

    chunks = [jobs[i : i + 10] for i in range(0, len(jobs), 10)]
    for chunk in chunks:
        embeds = []
        for job in chunk:
            description_parts: List[str] = []
            if job.role:
                description_parts.append(job.role)
            if job.employment_type:
                description_parts.append(job.employment_type)
            if job.experience:
                description_parts.append(job.experience)
            if job.due_date_display():
                description_parts.append(f"마감 {job.due_date_display()}")
            
            description = " | ".join(description_parts)
            
            embed = {
                "title": job.title,
                "url": job.url,
                "description": description or None,
                "fields": [],
            }
            
            if job.location:
                embed["fields"].append(
                    {"name": "근무지", "value": job.location, "inline": True}
                )
            if job.company:
                embed["fields"].append(
                    {"name": "회사", "value": job.company, "inline": True}
                )
            embeds.append(embed)

        payload = {
            "content": prefix,
            "embeds": embeds,
        }
        resp = requests.post(webhook_url, json=payload, timeout=config.DEFAULT_TIMEOUT)
        resp.raise_for_status()
