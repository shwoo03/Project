from typing import List
from urllib.parse import urljoin
import re

import requests
from bs4 import BeautifulSoup

from utils import config
from utils.models import JobPosting

BASE_URL = "https://enki.career.greetinghr.com"

def scrape_jobs() -> List[JobPosting]:
    """Scrape job postings from Enki website."""
    url = config.ENKI_GUIDE_URL
    
    # Fetch HTML
    resp = requests.get(url, timeout=config.DEFAULT_TIMEOUT)
    resp.raise_for_status()
    html = resp.text
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    
    # Find all job links (pattern: /ko/o/{job_id})
    job_links = soup.find_all("a", href=re.compile(r"/ko/o/\d+"))
    
    jobs = []
    for link in job_links:
        href = link.get("href")
        if not href:
            continue
            
        # Extract job ID from URL
        match = re.search(r"/ko/o/(\d+)", href)
        if not match:
            continue
        
        job_id = match.group(1)
        full_url = urljoin(BASE_URL, href)
        
        # Get job title from link text
        title = link.get_text(strip=True)
        if not title:
            continue
        
        # Filter: Only include intern positions (인턴)
        if "인턴" not in title:
            continue
        
        job = JobPosting(
            job_id=job_id,
            title=title,
            url=full_url,
            company="주식회사 엔키화이트햇",
            source=config.ENKI_SOURCE_LABEL,
        )
        jobs.append(job)
    
    return jobs
