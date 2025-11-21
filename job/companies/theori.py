from typing import List, Dict, Any
from datetime import datetime

import requests

from utils import config
from utils.models import JobPosting

LOCATION_LABELS = {
    "seoul": "서울",
    "pangyo": "판교",
}

def scrape_jobs() -> List[JobPosting]:
    """Scrape job postings from Theori API."""
    url = config.THEORI_API_URL
    
    # Fetch data
    resp = requests.get(url, timeout=config.DEFAULT_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    
    # Normalize to JobPosting
    jobs = []
    for position in data:
        if not position.get("is_active"):
            continue
        
        job = _normalize_position(position)
        jobs.append(job)
    
    return jobs

def _normalize_position(position: Dict[str, Any]) -> JobPosting:
    """Convert Theori API position to JobPosting."""
    position_id = position.get("id")
    title = position.get("title", "")
    slug = position.get("slug", "")
    url = f"https://theori.io/careers/{slug}" if slug else ""
    
    location_raw = position.get("location", "")
    location = LOCATION_LABELS.get(location_raw.lower(), location_raw)
    
    posted_at_str = position.get("posted_at")
    posted_at = None
    if posted_at_str:
        try:
            posted_at = datetime.fromisoformat(posted_at_str.replace("Z", "+00:00"))
        except Exception:
            pass
    
    return JobPosting(
        job_id=str(position_id) if position_id else None,
        title=title,
        url=url,
        company=config.THEORI_COMPANY_NAME,
        location=location,
        open_date=posted_at,
        source=config.THEORI_SOURCE_LABEL,
    )
